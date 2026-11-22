import asyncio

import psycopg
import pytest

from mbxchat import anki, capture


class FakeAnki:
    def __init__(self):
        self.open, self.models, self.notes, self.refuse = False, ["Basic"], {}, set()

    def __call__(self, action, **p):
        if not self.open:
            raise anki.Closed("connection refused")
        if action == "modelNames":
            return self.models
        if action == "createModel":
            self.models.append(p["modelName"])
        elif action == "findNotes":
            tag = p["query"].removeprefix("tag:")
            return [i for i, n in self.notes.items() if tag in n["tags"]]
        elif action == "addNote":
            if p["note"]["fields"]["Chunk"] in self.refuse:
                raise RuntimeError("cannot create note")
            self.notes[len(self.notes) + 100] = p["note"]
            return len(self.notes) + 99


@pytest.fixture
def fake(db_url, monkeypatch):
    f = FakeAnki()
    monkeypatch.setattr(anki, "invoke", f)
    cid = capture.new_capture("x")
    with psycopg.connect(db_url) as conn:
        for ko in ("다음 주로 미뤄지다", "회의가 미뤄지다"):
            conn.execute(
                "INSERT INTO chunk (capture_id, ko, gloss, kind, register_note, sentence) "
                "VALUES (%s, %s, 'g', 'collocation', 'everyday', '회의가 다음 주로 미뤄졌어요.')", (cid, ko)
            )
    return f


def test_closed_anki_keeps_the_queue_and_opening_it_adds_each_card_once(fake):
    with pytest.raises(anki.Closed):
        anki.push()
    assert len(anki.queued()) == 2
    fake.open = True
    assert anki.push() == 2
    assert anki.push() == 0
    assert len(fake.notes) == 2 and anki.queued() == []
    assert anki.MODEL in fake.models
    assert fake.notes[100]["fields"]["Blanked"] == "회의가 […]어요."


def test_a_note_added_before_a_crash_is_found_by_its_tag(fake, db_url):
    fake.open = True
    anki.push()
    with psycopg.connect(db_url) as conn:
        conn.execute("UPDATE chunk SET anki_note_id = NULL")
    assert anki.push() == 2
    assert len(fake.notes) == 2


def test_notes_from_an_earlier_database_do_not_match(fake):
    fake.open = True
    fake.notes[1] = {"tags": ["mbxchat-1"], "fields": {}}  # tag of chunk 1 before a reset
    assert anki.push() == 2
    assert len(fake.notes) == 3


def test_a_refused_note_is_parked_and_not_retried(fake):
    fake.open, fake.refuse = True, {"회의가 미뤄지다"}
    assert anki.push() == 1
    assert anki.queued() == [("회의가 미뤄지다", "cannot create note")]
    fake.refuse = set()
    assert anki.push() == 0


def test_queue_command_tries_anki_then_lists_what_waits(fake):
    from unittest.mock import AsyncMock, MagicMock

    from mbxchat import bot

    update = MagicMock()
    update.message.reply_html = AsyncMock()
    asyncio.run(bot.queue_cmd(update, MagicMock()))
    assert update.message.reply_html.await_args.args[0].startswith("Anki is closed: 2 cards queued")
    fake.open = True
    asyncio.run(bot.queue_cmd(update, MagicMock()))
    assert update.message.reply_html.await_args.args[0] == "Nothing waiting: every chunk is in Anki."


@pytest.mark.parametrize("chunk, sentence, front", [
    ("~려고 오다", "공부를 하려고 온 건 아니에요.", "공부를 하[…] 건 아니에요."),
    ("일이 산더미처럼 쌓이다", "이번 주에 일이 산더미처럼 쌓였어요.", "이번 주에 […]어요."),
    ("~(으)ㄹ 수 있다", "갈 수 있어요", "갈 […]어요"),
    ("사과", "배를 먹어요", ""),
])
def test_blank_hides_the_chunk_in_its_sentence(chunk, sentence, front):
    assert anki.blank(chunk, sentence) == front
