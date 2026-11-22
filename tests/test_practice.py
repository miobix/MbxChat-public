import asyncio
from datetime import date, datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import psycopg
import pytest

from mbxchat import bot, capture, config, importer, practice

TODAY = date(2026, 11, 22)
GOOD = practice.Grade(verdict="correct", corrected="회의를 미뤄요.", issues=[], model_answer="회의를 미뤄요.", note="")
BAD = practice.Grade(verdict="wrong", corrected="회의를 미뤄요.", issues=["회의가 → 회의를: object"],
                     model_answer="회의를 미뤄요.", note="")


def test_ladder_climbs_holds_and_restarts():
    assert practice.schedule(0, "correct", TODAY) == (1, TODAY + timedelta(days=3))
    assert practice.schedule(3, "correct", TODAY) == (4, TODAY + timedelta(days=90))
    assert practice.schedule(9, "correct", TODAY) == (10, TODAY + timedelta(days=90))
    assert practice.schedule(2, "minor", TODAY) == (2, TODAY + timedelta(days=30))
    assert practice.schedule(3, "wrong", TODAY) == (0, TODAY + timedelta(days=1))


def test_a_correct_verdict_with_a_fix_becomes_minor(monkeypatch):
    p = {"kind": "translate", "en": "x", "situation": "", "register": "", "reference": None, "word": None}
    monkeypatch.setattr(practice, "ask", lambda *a: GOOD.model_copy(update={"corrected": "회의가 연기됐어요."}))
    assert practice.grade(p, "회의를 미뤄요").verdict == "minor"
    monkeypatch.setattr(practice, "ask", lambda *a: GOOD.model_copy())
    assert practice.grade(p, "회의를 미뤄요").verdict == "correct"  # punctuation alone is no fix


def test_ping_due_fires_once_and_never_late():
    tz = ZoneInfo("Asia/Seoul")
    pings = [time(10), time(13)]
    at = datetime(2026, 11, 22, 13, 10, tzinfo=tz)
    assert practice.ping_due(at, pings, None) == at.replace(minute=0)
    assert practice.ping_due(at, pings, at.replace(minute=0)) is None
    assert practice.ping_due(at.replace(minute=40), pings, None) is None  # back after downtime: skip
    assert practice.ping_due(at.replace(hour=9), pings, None) is None


def test_parse_duration():
    assert practice.parse_duration("3h") == timedelta(hours=3)
    assert practice.parse_duration(" 30m") == timedelta(minutes=30)
    assert practice.parse_duration("2d") == timedelta(days=2)
    assert practice.parse_duration("soon") is None


@pytest.fixture
def pool(db_url, monkeypatch):
    importer.import_public()
    monkeypatch.setattr(practice, "ask", lambda schema, system, user: GOOD)
    cid = capture.new_capture("the meeting got pushed", "to my boss")
    with psycopg.connect(db_url) as conn:
        conn.execute("UPDATE capture SET polite = '회의가 미뤄졌어요.' WHERE id = %s", (cid,))
    return cid


def test_prompts_alternate_grammar_and_translation_captures_first(pool):
    s = practice.open_session()
    first, second, third = (practice.next_prompt(s) for _ in range(3))
    assert first["kind"] == "grammar" and first["grammar_id"] == first["ref"]
    assert (second["source"], second["ref"], second["situation"]) == ("capture", pool, "to my boss")
    assert second["reference"] == "회의가 미뤄졌어요."
    assert third["kind"] == "grammar" and third["ref"] != first["ref"]


def test_grammar_prompts_skip_known_points_and_prefer_levels_up_to_4(pool, db_url):
    s = practice.open_session()
    with psycopg.connect(db_url) as conn:
        known = {r[0] for r in conn.execute("SELECT item_id FROM known_grammar")}
        levels = dict(conn.execute("SELECT id, level FROM item WHERE kind = 'grammar'").fetchall())
    for _ in range(6):
        p = practice.next_prompt(s)
        if p["kind"] == "grammar":
            assert p["ref"] not in known and levels[p["ref"]] <= practice.GRAMMAR_MAX_LEVEL


def test_a_miss_comes_back_when_due(pool, db_url):
    s = practice.open_session()
    practice.next_prompt(s)
    p = practice.next_prompt(s)  # the capture
    practice.record(p, "회의가 미뤘어요", BAD)
    with psycopg.connect(db_url) as conn:
        step, due = conn.execute("SELECT step, due FROM drill WHERE source = 'capture'").fetchone()
        assert step == 0 and due == practice.now().date() + timedelta(days=1)
        conn.execute("UPDATE drill SET due = current_date - 1")
        conn.execute("UPDATE prompt SET sent_at = now() - interval '2 days'")
    assert practice.next_prompt(s)["source"] == "capture"


def test_idle_sessions_close_after_30_minutes(pool, db_url):
    s = practice.open_session()
    assert practice.current_session() == s
    with psycopg.connect(db_url) as conn:
        conn.execute("UPDATE session SET last_at = now() - interval '31 minutes'")
    assert practice.current_session() is None


# --- chat flow --------------------------------------------------------------------------------

def _context():
    context = MagicMock(chat_data={})
    context.bot.send_message = AsyncMock(return_value=MagicMock(edit_text=AsyncMock()))
    context.bot.send_chat_action = AsyncMock()
    return context


def _message(text):
    msg = MagicMock(chat_id=1001, text=text)
    msg.reply_html, msg.set_reaction = AsyncMock(), AsyncMock()
    return msg


def test_answer_in_a_session_is_graded_and_the_next_prompt_follows(pool):
    context = _context()
    asyncio.run(bot.practice_cmd(MagicMock(message=_message("/practice")), context))
    assert "Write a sentence with" in context.bot.send_message.await_args.args[1]
    msg = _message("회의를 미뤄요.")
    asyncio.run(bot.free_text(MagicMock(message=msg), context))
    graded = context.bot.send_message.return_value.edit_text.await_args.args[0]
    assert graded.startswith("<b>✅ Correct</b>") and "<tg-spoiler>" in graded
    msg.set_reaction.assert_awaited_with("👍")
    assert "In Korean:" in context.bot.send_message.await_args.args[1]  # the next prompt


def test_graded_reply_diffs_the_correction_and_skips_a_duplicate_model_answer():
    g = BAD.model_copy(update={"verdict": "minor"})
    text = bot._graded("회의가 미뤄요.", g)
    assert "<s>회의가</s> <b>회의를</b> 미뤄요." in text and "Model answer" not in text
    other = g.model_copy(update={"model_answer": "회의를 다음 주로 미뤄요."})
    assert "<b>Model answer:</b> <tg-spoiler>" in bot._graded("회의가 미뤄요.", other)


def test_skip_and_stop_buttons(pool):
    context = _context()
    s = practice.open_session()
    p = practice.next_prompt(s)
    update = MagicMock()
    q = update.callback_query
    q.answer, q.edit_message_text, q.edit_message_reply_markup = AsyncMock(), AsyncMock(), AsyncMock()
    q.message.chat_id = 1001
    q.data = f"pr:{p['id']}:sk"
    asyncio.run(bot.on_prompt(update, context))
    assert practice.get_prompt(p["id"])["skipped"]
    nxt = practice.waiting(s)
    q.data = f"pr:{nxt['id']}:st"
    asyncio.run(bot.on_prompt(update, context))
    assert practice.current_session() is None
    q.data = f"pr:{nxt['id']}:sk"
    asyncio.run(bot.on_prompt(update, context))
    q.answer.assert_awaited_with("Already handled")


def test_a_late_answer_can_still_be_graded(pool):
    context = _context()
    s = practice.open_session()
    practice.next_prompt(s)
    practice.close_session()
    msg = _message("늦은 답이에요.")
    asyncio.run(bot.free_text(MagicMock(message=msg), context))
    rows = msg.reply_html.await_args.kwargs["reply_markup"].inline_keyboard
    assert rows[1][0].callback_data.startswith("late:")


def test_ping_opens_a_session_once(pool, monkeypatch):
    monkeypatch.setattr(config, "PRACTICE_PINGS", [time(10)])
    monkeypatch.setattr(practice, "now", lambda: datetime(2026, 11, 22, 10, 5, tzinfo=ZoneInfo("UTC")))
    app = MagicMock()
    app.bot.send_message = AsyncMock()
    asyncio.run(bot.ping_step(app))
    assert app.bot.send_message.await_args.args[1].startswith("🔔 Practice time.")
    assert practice.current_session() is not None
    asyncio.run(bot.ping_step(app))
    assert app.bot.send_message.await_count == 1


def test_pause_mutes_pings(pool, monkeypatch):
    monkeypatch.setattr(config, "PRACTICE_PINGS", [time(10)])
    monkeypatch.setattr(practice, "now", lambda: datetime(2026, 11, 22, 10, 5, tzinfo=ZoneInfo("UTC")))
    practice.set_setting("paused_until", datetime(2026, 11, 22, 12, tzinfo=ZoneInfo("UTC")).isoformat())
    app = MagicMock()
    app.bot.send_message = AsyncMock()
    asyncio.run(bot.ping_step(app))
    app.bot.send_message.assert_not_awaited()
