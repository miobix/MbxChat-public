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
    assert practice.schedule(3, "wrong", TODAY) == (0, TODAY + timedelta(days=3))


def test_a_correct_verdict_with_a_fix_becomes_minor(monkeypatch):
    p = {"kind": "translate", "en": "x", "situation": "", "register": "", "reference": None, "word": None}
    praised = {"corrected": "회의가 연기됐어요.", "note": "Your answer is correct!"}
    monkeypatch.setattr(practice, "ask", lambda *a: GOOD.model_copy(update=praised))
    g = practice.grade(p, "회의를 미뤄요")
    assert (g.verdict, g.note) == ("minor", "")  # the note was written for "correct"
    monkeypatch.setattr(practice, "ask", lambda *a: GOOD.model_copy())
    assert practice.grade(p, "회의를 미뤄요").verdict == "correct"  # punctuation alone is no fix


def test_a_reference_match_is_correct_without_a_model_call(monkeypatch):
    p = {"kind": "translate", "en": "x", "situation": "", "register": "", "reference": "회의가 미뤄졌어요.", "word": None}
    monkeypatch.setattr(practice, "ask", lambda *a: BAD)
    assert practice.grade(p, "회의가 미뤄졌어요").verdict == "correct"
    assert practice.grade(p, "회의 미뤄졌어요").verdict == "wrong"


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
    monkeypatch.setattr(practice, "ask", lambda *a: GOOD)
    cid = capture.new_capture("the meeting got pushed", "to my boss")
    with psycopg.connect(db_url) as conn:
        conn.execute("UPDATE capture SET polite = '회의가 미뤄졌어요.' WHERE id = %s", (cid,))
    return cid


def test_prompts_alternate_and_never_serve_captures(pool):
    s = practice.open_session()
    prompts = [practice.next_prompt(s) for _ in range(4)]
    assert all(p["source"] == "item" for p in prompts)
    assert [p["kind"] for p in prompts] == ["grammar", "translate", "grammar", "translate"]
    assert prompts[0]["grammar_id"] == prompts[0]["ref"]
    assert prompts[1]["reference"]  # a pool sentence, used once
    grammar = [p["grammar_id"] for p in prompts if p["grammar_id"]]
    assert len(grammar) == len(set(grammar))  # one prompt per grammar point per session


def test_pool_sentences_run_out_into_generated_prompts(pool, db_url, monkeypatch):
    with psycopg.connect(db_url) as conn:
        conn.execute("DELETE FROM item WHERE kind = 'sentence' AND id <> (SELECT min(id) FROM item WHERE kind = 'sentence')")
    gen = practice.Generated(en="I only have ten minutes.", formality="friend")
    asked = []
    monkeypatch.setattr(practice, "ask", lambda schema, system, user, *a: asked.append(user) or (
        gen if schema is practice.Generated else GOOD))
    s = practice.open_session()
    kinds = [practice.next_prompt(s) for _ in range(4)]
    pool_sentence, generated = kinds[1], kinds[3]
    assert pool_sentence["reference"] and generated["reference"] is None
    assert (generated["en"], generated["register"]) == ("I only have ten minutes.", "friend")
    assert generated["source"] == "item" and generated["ref"] == generated["grammar_id"]
    assert "Word:" not in asked[-1]  # no learning terms in this database: no word line (it once said "any")


def test_a_failed_generation_serves_the_grammar_point(pool, db_url, monkeypatch):
    with psycopg.connect(db_url) as conn:
        conn.execute("DELETE FROM item WHERE kind = 'sentence'")
    s = practice.open_session()
    practice.next_prompt(s)
    p = practice.next_prompt(s)  # the fixture's ask returns a Grade, not Generated: generation fails
    assert p["kind"] == "grammar" and p["grammar_id"]


def test_grammar_prompts_skip_known_points_and_prefer_levels_up_to_4(pool, db_url):
    s = practice.open_session()
    with psycopg.connect(db_url) as conn:
        known = {r[0] for r in conn.execute("SELECT item_id FROM known_grammar")}
        levels = dict(conn.execute("SELECT id, level FROM item WHERE kind = 'grammar'").fetchall())
    for _ in range(6):
        p = practice.next_prompt(s)
        if p["kind"] == "grammar":
            assert p["ref"] not in known and levels[p["ref"]] <= practice.GRAMMAR_MAX_LEVEL


def test_a_miss_comes_back_in_3_days_as_its_grammar_point(pool, db_url):
    s = practice.open_session()
    p = practice.next_prompt(s)
    practice.record(p, "회의가 미뤘어요", BAD)
    with psycopg.connect(db_url) as conn:
        step, due = conn.execute("SELECT step, due FROM drill WHERE ref = %s", (p["grammar_id"],)).fetchone()
        assert step == 0 and due == practice.now().date() + timedelta(days=3)
        conn.execute("UPDATE drill SET due = current_date - 1")
        conn.execute("UPDATE prompt SET sent_at = now() - interval '2 days', session_id = NULL")
    again = practice.next_prompt(practice.open_session())
    assert (again["grammar_id"], again["pick"]) == (p["grammar_id"], "due")


def test_tag_sorts_differences_into_categories():
    assert practice.tag("건물 담강자에게 연락이 왔어요!", "건물 담당자에게 연락이 왔어요!") == [
        ("spelling", "담강자", "담당자", "담당자")]
    tags = practice.tag("가요 친구한태 소개 받았어요", "가요를 친구에게 소개받았어요.")
    assert ("particle", "", "를", "를") in tags and ("particle", "한태", "에게", "에게") in tags
    assert [t[:3] for t in practice.tag("가게 갈 거야, 사 올 거 있니?", "가게 갈 거야, 사 올 거 있어?")] == [("ending", "니", "어")]
    assert practice.tag("출발하기전에 물 마셔야지", "출발하기 전에 물 마셔야지.") == [
        ("spacing", "출발하기전에", "출발하기 전에", "")]
    assert practice.tag("회의를 미뤄요", "회의를 미뤄요.") == []


def test_a_repeated_mistake_steers_practice(pool, db_url):
    """SPEC §8 unit 8 'done when': the same slip twice → a 🎯 prompt that uses the word, once in three."""
    slip = GOOD.model_copy(update={"verdict": "minor", "corrected": "건물 담당자에게 연락이 왔어요."})
    s = practice.open_session()
    for _ in range(2):
        practice.record(practice.next_prompt(s), "건물 담강자에게 연락이 왔어요", slip)
    assert [(w["category"], w["fix"], w["n"]) for w in practice.weak()] == [("spelling", "담당자", 2)]
    steered = practice.next_prompt(s)
    assert steered["pick"] == "weak" and steered["word"] == "담당자" and steered["focus"] == "🎯 You missed 담당자 2 times"
    assert "🎯 You missed 담당자 2 times" in bot._prompt_html(steered)
    following = [practice.next_prompt(s) for _ in range(2)]
    assert all(p["pick"] != "weak" for p in following)  # at most one in three
    practice.record(following[-1], "건물 담당자에게 연락이 왔어요.", GOOD)
    assert practice.weak() == []  # written right since: no longer weak


def test_particle_variants_count_as_one_grammar_point_and_steer_to_it(pool, db_url):
    s = practice.open_session()
    for answer, fixed in (("책 읽어요", "책을 읽어요."), ("사과 먹어요", "사과를 먹어요.")):
        p = practice.next_prompt(s)
        practice.record(p, answer, GOOD.model_copy(update={"verdict": "minor", "corrected": fixed}))
    with psycopg.connect(db_url) as conn:
        target = conn.execute("SELECT id FROM item WHERE kind = 'grammar' AND ko = '을/를'").fetchone()[0]
        conn.execute("UPDATE prompt SET sent_at = now() - interval '4 days', session_id = NULL")
    [w] = practice.weak()
    assert (w["category"], w["grammar_id"], w["n"], w["fix"]) == ("particle", target, 2, "를")
    steered = practice.next_prompt(practice.open_session())
    assert (steered["kind"], steered["grammar_id"], steered["pick"]) == ("grammar", target, "weak")


def test_a_tagging_failure_still_records_the_grade(pool, db_url, monkeypatch):
    monkeypatch.setattr(practice, "tag", lambda *a: 1 / 0)
    p = practice.next_prompt(practice.open_session())
    practice.record(p, "회의가 미뤘어요", BAD)
    assert practice.get_prompt(p["id"])["grade"]["verdict"] == "wrong"


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


# --- routing free text in a session ----------------------------------------------------------------

def _no_model(*a, **k):
    raise AssertionError("no model call expected")


def test_korean_is_an_answer_without_a_model_call(monkeypatch):
    monkeypatch.setattr(practice, "ask", _no_model)
    p = {"kind": "sentence", "en": "I'm late"}
    assert practice.route(p, "저 늦었어요.") == "answer"
    assert practice.route(p, "제가 late 했어요") == "answer"  # mostly Hangul
    assert practice.route(p, "최적화") == "capture"  # a single Korean word: heard somewhere, to capture


def test_other_text_is_classified_by_the_model(monkeypatch):
    seen = []
    monkeypatch.setattr(practice, "ask", lambda schema, system, user: seen.append(user) or practice.Route(kind="question"))
    assert practice.route({"kind": "sentence", "en": "I'm late"}, "what's the difference between 늦다 and 지각하다?") == "question"
    assert "Say this in Korean: I'm late" in seen[0]


def _session_prompt(context):
    asyncio.run(bot.practice_cmd(MagicMock(message=_message("/practice")), context))
    return practice.waiting(practice.current_session())


def test_a_question_in_a_session_is_offered_not_graded(pool, monkeypatch):
    context = _context()
    p = _session_prompt(context)
    monkeypatch.setattr(practice, "route", lambda p, text: "question")
    monkeypatch.setattr(practice, "grade", _no_model)
    msg = _message("what does 는데 mean?")
    asyncio.run(bot.free_text(MagicMock(message=msg), context))
    rows = msg.reply_html.await_args.kwargs["reply_markup"].inline_keyboard
    assert [b.callback_data for r in rows for b in r] == [f"ask:{p['id']}", "cap:yes", f"late:{p['id']}"]
    assert practice.waiting(practice.current_session())["id"] == p["id"]  # still waiting

    update = MagicMock()
    q = update.callback_query
    q.answer, q.edit_message_text = AsyncMock(), AsyncMock()
    q.data, q.message.reply_to_message = f"ask:{p['id']}", msg
    monkeypatch.setattr(practice, "explain", lambda p, question: practice.Explanation(text="는데 sets up background.", word=""))
    asyncio.run(bot.on_ask(update, context))
    assert q.edit_message_text.await_args.args[0].startswith("는데 sets up background.")
    assert "still waiting" in q.edit_message_text.await_args.args[0]
    assert q.edit_message_text.await_args.kwargs["reply_markup"] is None


def test_an_answer_about_a_word_offers_it_as_a_card(pool, monkeypatch):
    context = _context()
    p = _session_prompt(context)
    update = MagicMock()
    q = update.callback_query
    q.answer, q.edit_message_text, q.edit_message_reply_markup = AsyncMock(), AsyncMock(), AsyncMock()
    q.data, q.message.reply_to_message.text = f"ask:{p['id']}", "what's patience in Korean?"
    monkeypatch.setattr(practice, "explain", lambda p, question: practice.Explanation(text="인내.", word="인내 (innae)"))
    asyncio.run(bot.on_ask(update, context))
    button = q.edit_message_text.await_args.kwargs["reply_markup"].inline_keyboard[0][0]
    assert (button.text, button.callback_data) == ("➕ Save 인내 as a card", "sv:인내")

    started = []
    monkeypatch.setattr(bot, "_capture", AsyncMock(side_effect=lambda ctx, chat, text: started.append(text)))
    q.data = "sv:인내"
    asyncio.run(bot.on_save(update, context))
    assert started == ["인내"]
    q.edit_message_reply_markup.assert_awaited_with(None)


def test_a_grammar_prompt_with_a_word_offers_its_card(pool, monkeypatch):
    context = _context()
    with psycopg.connect(config.DATABASE_URL) as conn:
        importer.replace(conn, "term", [("term", "미루다", None, "미루다", "put off", {"status": "learning"})])
    p = _session_prompt(context)
    assert p["kind"] == "grammar" and p["word"] == "미루다 (put off)"
    row = context.bot.send_message.await_args.kwargs["reply_markup"].inline_keyboard[0]
    word = "미루다"
    assert (row[1].text, row[1].callback_data) == (f"🔤 {word}", f"pr:{p['id']}:wd")

    started = []
    monkeypatch.setattr(bot, "_capture", AsyncMock(side_effect=lambda ctx, chat, text: started.append(text)))
    update = MagicMock()
    q = update.callback_query
    q.answer = AsyncMock()
    q.data = f"pr:{p['id']}:wd"
    asyncio.run(bot.on_prompt(update, context))
    assert started == [word]
    assert practice.waiting(practice.current_session())["id"] == p["id"]  # still waiting


def test_a_capture_in_a_session_offers_capture_or_grading(pool, monkeypatch):
    context = _context()
    p = _session_prompt(context)
    monkeypatch.setattr(practice, "route", lambda p, text: "capture")
    msg = _message("how do I say I'm stuck in traffic")
    asyncio.run(bot.free_text(MagicMock(message=msg), context))
    rows = msg.reply_html.await_args.kwargs["reply_markup"].inline_keyboard
    assert [b.callback_data for r in rows for b in r] == ["cap:yes", f"ask:{p['id']}", f"late:{p['id']}"]


def test_a_routing_failure_falls_back_to_grading(pool, monkeypatch):
    context = _context()
    _session_prompt(context)
    monkeypatch.setattr(practice, "route", lambda p, text: 1 / 0)
    msg = _message("hmm")
    asyncio.run(bot.free_text(MagicMock(message=msg), context))
    assert context.bot.send_message.return_value.edit_text.await_args.args[0].startswith("<b>")  # graded


def test_a_register_reads_as_words():
    p = {"kind": "translate", "en": "x", "situation": "", "register": "office_speech", "reference": None, "word": None}
    assert "<i>office speech</i>" in bot._prompt_html(p)


def test_a_card_is_offered_only_for_the_word_the_question_is_about():
    cases = [  # raw model outputs from the live check (DECISIONS, unit 12)
        ("what does 미루다 mean?", "미루다 (miruda)", "미루다"),
        ("whats patience in korean?", "인내", "인내"),
        ("what's the meaning of 인지 here?", "미루다", None),
        ("is it 인간 or 사람 here?", "사람 (saram)", None),
        ("should this be polite or casual?", "Polite (Formal/Standard): ~ㅂ니다/습니다", None),
        ("what does 꿈꾸다 mean exactly", "to dream", None),
        ("what does 꿈꿔요 mean", "꿈꾸다", "꿈꾸다"),
    ]
    for question, word, want in cases:
        assert practice.Explanation(text="", word=word).card(question) == want, question
