import pytest

from mbxchat import config, krdict

SEARCH = """<channel><total>2</total>
<item><word>최적화</word><pos>명사</pos><target_code>71583</target_code>
  <sense><definition>가장 알맞은 상태로 만듦.</definition>
    <translation><trans_word>optimization</trans_word></translation></sense></item>
<item><word>최적화되다</word><pos>동사</pos><target_code>71584</target_code>
  <sense><translation><trans_word>be optimized</trans_word></translation></sense></item>
</channel>"""
VIEW = """<channel><item><word_info><sense_info>
  <example_info><type>구</type><example>시스템 최적화</example></example_info>
  <example_info><type>문장</type><example>성능을 최적화했어요.</example></example_info>
  <example_info><type>문장</type><example>성능을 최적화했어요.</example></example_info>
</sense_info></word_info></item></channel>"""


@pytest.fixture
def fetch(db_url, monkeypatch):
    monkeypatch.setattr(config, "KRDICT_API_KEY", "test-key")
    monkeypatch.setattr(krdict, "GAP", 0)
    calls = []

    def fake(url):
        calls.append(url)
        return VIEW if "/view?" in url else SEARCH

    monkeypatch.setattr(krdict, "_fetch", fake)
    return calls


def test_search_parses_entries_and_caches_the_answer(fetch):
    want = [{"word": "최적화", "pos": "명사", "target_code": "71583", "glosses": ["optimization"]},
            {"word": "최적화되다", "pos": "동사", "target_code": "71584", "glosses": ["be optimized"]}]
    assert krdict.search("최적화") == want
    assert krdict.search("최적화") == want
    assert len(fetch) == 1 and "key=test-key" in fetch[0]


def test_examples_are_one_request_deduplicated(fetch):
    assert krdict.examples("71583") == ["시스템 최적화", "성능을 최적화했어요."]
    assert len(fetch) == 1


def test_the_first_failure_pauses_every_call_and_survives_a_restart(fetch, monkeypatch):
    def down(url):
        fetch.append(url)
        raise OSError("HTTP 503")

    monkeypatch.setattr(krdict, "_fetch", down)
    with pytest.raises(krdict.Unavailable, match="paused for 30 min"):
        krdict.search("뷁")
    with pytest.raises(krdict.Unavailable, match="paused after a failure"):
        krdict.search("꿹")
    assert len(fetch) == 1


def test_an_error_answer_counts_as_a_failure(fetch, monkeypatch):
    monkeypatch.setattr(krdict, "_fetch", lambda url: "<error><error_code>020</error_code><message>bad key</message></error>")
    with pytest.raises(krdict.Unavailable, match="bad key"):
        krdict.search("뷁")


def test_cached_answers_still_work_during_the_pause(fetch, monkeypatch):
    krdict.search("최적화")
    monkeypatch.setattr(krdict, "_fetch", lambda url: (_ for _ in ()).throw(OSError("down")))
    with pytest.raises(krdict.Unavailable):
        krdict.search("뷁")
    assert krdict.search("최적화")[0]["word"] == "최적화"


def test_network_calls_are_spaced_by_the_gap(fetch, monkeypatch):
    import time
    monkeypatch.setattr(krdict, "GAP", 0.3)
    stamps = []
    monkeypatch.setattr(krdict, "_fetch", lambda url: stamps.append(time.monotonic()) or SEARCH)
    krdict.search("하나")
    krdict.search("하나")  # cached: no request, no wait
    krdict.search("둘")
    assert len(stamps) == 2 and stamps[1] - stamps[0] >= 0.3
