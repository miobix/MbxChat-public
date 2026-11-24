import psycopg
import pytest

from mbxchat import config, importer


@pytest.fixture(autouse=True)
def mbxread_set(monkeypatch):
    monkeypatch.setattr(config, "MBXREAD_URL", "http://mbxread")


def test_term_import_is_skipped_when_mbxread_is_not_set(db_url, monkeypatch):
    monkeypatch.setattr(config, "MBXREAD_URL", "")
    monkeypatch.setattr(importer, "fetch_terms", lambda url: 1 / 0)
    assert importer.import_personal() == ["term: skipped, MBXREAD_URL not set"]


def _counts(url):
    with psycopg.connect(url) as conn:
        return dict(conn.execute("SELECT kind, count(*) FROM item GROUP BY kind").fetchall())


def _ids(url):
    with psycopg.connect(url) as conn:
        return conn.execute("SELECT kind, key, id FROM item ORDER BY id").fetchall()


def test_every_grammar_point_has_a_complete_refresher():
    refreshers = importer.load_refreshers()
    for kind, key, level, title, _, data in importer.grammar_rows():
        ref = refreshers[key]
        assert ref["file"] == f"L{level}.md", key
        assert ref["register"] in ("both", "spoken", "written", "formal", "dated"), key
        assert 2 <= len(ref["examples"]) <= 3, key
        assert ref["explanation"], key
    assert len(refreshers) == 336


def test_public_counts_match_the_sources(db_url):
    report = importer.import_public()
    assert _counts(db_url) == {"grammar": 336, "sentence": 20, "word": 5543}
    assert report[0] == "grammar: 336 rows, 0 removed"
    with psycopg.connect(db_url) as conn:
        known = conn.execute("SELECT count(*) FROM known_grammar").fetchone()[0]
    assert known == len(importer.BASICS)


def test_reimport_is_idempotent(db_url):
    importer.import_public()
    before = _ids(db_url)
    importer.import_public()
    assert _ids(db_url) == before


def test_rows_gone_from_the_source_are_removed(db_url):
    with psycopg.connect(db_url) as conn:
        importer.replace(conn, "word", [("word", "가다", None, "가다", None, {}),
                                        ("word", "오다", None, "오다", None, {})])
        assert importer.replace(conn, "word", [("word", "가다", None, "가다", None, {})]) == (1, 1)
    assert _counts(db_url) == {"word": 1}


TERMS = [
    {"id": 7, "lemma": "흐르다", "translation": "flow", "sentence": "강이 흐른다.", "status": "learning"},
    {"id": 8, "lemma": "가끔", "translation": "sometimes", "sentence": "", "status": "known"},
    {"id": 9, "lemma": "음", "translation": "um", "sentence": "", "status": "ignored"},
]


def test_term_import_skips_ignored_and_leaves_other_kinds_alone(db_url, monkeypatch):
    with psycopg.connect(db_url) as conn:
        importer.replace(conn, "wish", [("wish", "1", None, None, "Seeded wish", {})])
    monkeypatch.setattr(importer, "fetch_terms", lambda url: TERMS)
    assert importer.import_personal() == ["term: 2 rows, 0 removed"]
    assert _counts(db_url) == {"wish": 1, "term": 2}


def test_mbxread_down_is_skipped_and_existing_terms_kept(db_url, monkeypatch):
    monkeypatch.setattr(importer, "fetch_terms", lambda url: TERMS)
    importer.import_personal()

    def down(url):
        raise OSError("connection refused")

    monkeypatch.setattr(importer, "fetch_terms", down)
    assert importer.import_personal() == ["term: skipped, MbxRead unavailable (connection refused)"]
    assert _counts(db_url) == {"term": 2}


def test_basics_are_seeded_on_the_first_import_only(db_url):
    importer.import_public()
    with psycopg.connect(db_url) as conn:
        conn.execute("DELETE FROM known_grammar")
    importer.import_public()
    with psycopg.connect(db_url) as conn:
        assert conn.execute("SELECT count(*) FROM known_grammar").fetchone()[0] == 0


def test_a_sharp_drop_in_terms_is_refused(db_url, monkeypatch):
    monkeypatch.setattr(importer, "fetch_terms", lambda url: TERMS)
    importer.import_personal()
    monkeypatch.setattr(importer, "fetch_terms", lambda url: [])
    assert importer.import_personal()[0].startswith("term: refused, MbxRead sent 0 terms but 2 are stored")
    assert _counts(db_url) == {"term": 2}
