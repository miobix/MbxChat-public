import asyncio
from unittest.mock import AsyncMock, MagicMock

import psycopg
import pytest
from langchain_core.exceptions import OutputParserException
from langgraph.types import Command

from mbxchat import bot, capture, db, importer

DRAFT = capture.Draft(casual="회의가 다음 주로 미뤄졌어.", polite="회의가 다음 주로 미뤄졌어요.", note="미뤄지다 = be pushed back")
REVIEW = capture.Review(casual=DRAFT.casual, polite=DRAFT.polite, issues=[])
CHUNKS = capture.Chunks(items=[
    capture.Chunk(ko="다음 주로 미뤄지다", gloss="be pushed to next week", kind="collocation",
                  register_note="everyday", sentence="회의가 다음 주로..."),
    capture.Chunk(ko="회의가 미뤄지다", gloss="a meeting is postponed", kind="collocation",
                  register_note="everyday", sentence="회의가 다음 주로 미뤄졌어요."),
])


@pytest.fixture
def offline(db_url, monkeypatch):
    """Canned model answers and an MbxRead that knows every word; the graph and Postgres are real."""
    importer.import_public()
    answers = {capture.Draft: DRAFT, capture.Review: REVIEW, capture.Chunks: CHUNKS}
    monkeypatch.setattr(capture, "ask", lambda schema, system, user: answers[schema])
    monkeypatch.setattr(capture, "KRDICT_GAP", 0)
    calls = []

    def mbxread(path, body=None, timeout=20):
        calls.append(path)
        return {"hits": [{"text": "예문입니다."}]} if body else [{"definitions": [{"en_word": "gloss"}]}]

    monkeypatch.setattr(capture, "_mbxread", mbxread)
    return calls


@pytest.fixture
def graph(db_url):
    saver = db.checkpointer(db_url)
    yield capture.build(saver)
    saver.conn.close()


def _chunks(url):
    with psycopg.connect(url) as conn:
        return conn.execute("SELECT ko FROM chunk ORDER BY id").fetchall()


def _start(graph, text="the meeting got pushed to next week"):
    capture_id = capture.new_capture(text)
    cfg = {"configurable": {"thread_id": str(capture_id)}}
    graph.invoke({"text": text}, cfg)
    return cfg


def test_graph_interrupts_per_chunk_and_saves_approved_and_edited(offline, graph, db_url):
    cfg = _start(graph)
    assert graph.get_state(cfg).interrupts[0].value["i"] == 0
    graph.invoke(Command(resume={"action": "edit", "ko": "다음 주로 미루다"}), cfg)
    assert graph.get_state(cfg).interrupts[0].value["i"] == 1
    graph.invoke(Command(resume={"action": "ok"}), cfg)
    state = graph.get_state(cfg)
    assert not state.interrupts and state.values["saved"] == 2
    assert _chunks(db_url) == [("다음 주로 미루다",), ("회의가 미뤄지다",)]


def test_skipped_chunks_are_not_saved_and_save_is_idempotent(offline, graph, db_url, monkeypatch):
    cfg = _start(graph)
    graph.invoke(Command(resume={"action": "skip"}), cfg)
    graph.invoke(Command(resume={"action": "ok"}), cfg)
    values = graph.get_state(cfg).values
    assert values["saved"] == 1 and _chunks(db_url) == [("회의가 미뤄지다",)]
    monkeypatch.setattr(capture, "get_config", lambda: cfg)
    capture.save(values)  # a re-run of the node adds nothing
    assert _chunks(db_url) == [("회의가 미뤄지다",)]


def test_shortened_chunk_sentence_is_restored(offline, graph):
    cfg = _start(graph)
    assert graph.get_state(cfg).values["chunks"][0]["sentence"] == "회의가 다음 주로 미뤄졌어요."


def test_lookup_checks_krdict_only_beyond_the_nikl_pool(offline, db_url):
    state = {"draft": {"casual": "산더미처럼 쌓였어.", "polite": "일이 산더미처럼 쌓였어요."}}
    findings = capture.lookup(state)["findings"]
    assert set(findings["krdict"]) == {lemma for lemma in capture.content_lemmas("일이 산더미처럼 쌓였어요.")
                                       if lemma not in capture.nikl_grades([lemma])}
    assert "일" not in findings["krdict"]  # grade A, in the pool
    assert findings["notes"] == []


def test_lookup_stops_at_the_first_krdict_failure_and_carries_on(offline, monkeypatch):
    calls = []

    def down(path, body=None, timeout=20):
        calls.append(path)
        raise capture.Unavailable("HTTP 503: krdict paused")

    monkeypatch.setattr(capture, "_mbxread", down)
    monkeypatch.setattr(capture, "content_lemmas", lambda text: ["뷁뷁", "꿹꿹", "쀍쀍"])
    findings = capture.lookup({"draft": {"casual": "", "polite": ""}})["findings"]
    assert sum(c.startswith("/api/dict") for c in calls) == 1
    assert findings["notes"] == ["krdict unavailable: HTTP 503: krdict paused",
                                 "MbxRead usage unavailable: HTTP 503: krdict paused"]


class _FlakyLLM:
    def __init__(self, failures):
        self.failures = failures

    def with_structured_output(self, schema, method):
        return self

    def invoke(self, messages):
        if self.failures:
            self.failures -= 1
            raise OutputParserException("bad json")
        return DRAFT


def test_invalid_model_output_is_retried_once(monkeypatch):
    monkeypatch.setattr(capture, "ChatOllama", lambda **kw: _FlakyLLM(1))
    assert capture.ask(capture.Draft, "s", "u") is DRAFT
    monkeypatch.setattr(capture, "ChatOllama", lambda **kw: _FlakyLLM(2))
    with pytest.raises(capture.CaptureError, match="invalid Draft twice"):
        capture.ask(capture.Draft, "s", "u")


# --- the chat flow ----------------------------------------------------------------------------

def _context(graph):
    context = MagicMock(chat_data={})
    context.application.bot_data = {"graph": graph}
    context.bot.send_message = AsyncMock(return_value=MagicMock(edit_text=AsyncMock()))
    context.bot.send_chat_action = AsyncMock()
    context.bot.edit_message_text = AsyncMock()
    return context


def _tap(data, chat_id=1001):
    update = MagicMock()
    q = update.callback_query
    q.data = data
    q.answer, q.edit_message_text, q.edit_message_reply_markup = AsyncMock(), AsyncMock(), AsyncMock()
    q.message.chat_id = chat_id
    q.message.reply_html = AsyncMock()
    q.message.reply_to_message.text = "the meeting got pushed to next week"
    return update, q


def _sent(context):
    return [c.args[1] for c in context.bot.send_message.await_args_list]


def test_capture_button_runs_the_graph_and_sends_the_first_card(offline, graph):
    context = _context(graph)
    update, q = _tap("cap:yes")
    asyncio.run(bot.on_capture(update, context))
    progress = context.bot.send_message.return_value.edit_text.await_args_list
    assert "Critic reviewing…" in progress[1].args[0]
    assert "2 chunks to review below." in progress[-1].args[0]
    card = context.bot.send_message.await_args_list[-1]
    assert "<b>다음 주로 미뤄지다</b>" in card.args[1]
    assert card.kwargs["reply_markup"].inline_keyboard[0][0].callback_data.endswith(":0:ok")


def test_capture_failure_is_reported_in_the_progress_message(offline, graph, monkeypatch):
    def broken(schema, system, user):
        raise capture.CaptureError("the model returned an invalid Draft twice")

    monkeypatch.setattr(capture, "ask", broken)
    context = _context(graph)
    asyncio.run(bot.on_capture(_tap("cap:yes")[0], context))
    last = context.bot.send_message.return_value.edit_text.await_args.args[0]
    assert last.startswith("⚠️ Capture failed: <code>CaptureError: the model returned an invalid Draft twice")


def test_buttons_and_edit_walk_through_every_chunk(offline, graph, db_url):
    context = _context(graph)
    cid = capture.new_capture("x")
    asyncio.run(bot._run(context, 1001, cid, {"text": "x"}))

    update, q = _tap(f"ch:{cid}:0:ed")
    asyncio.run(bot.on_chunk(update, context))
    assert context.chat_data["editing"][:2] == (cid, 0)

    msg = MagicMock(chat_id=1001, text=" 다음 주로 미루다 ")
    msg.reply_html = AsyncMock()
    asyncio.run(bot.free_text(MagicMock(message=msg), context))
    assert "✏️ <b>다음 주로 미루다</b>" in context.bot.edit_message_text.await_args.args[0]

    update, q = _tap(f"ch:{cid}:1:ok")
    asyncio.run(bot.on_chunk(update, context))
    assert _sent(context)[-1] == "Done: 2 chunks saved. Anki is closed: 2 cards queued, sent once it opens."
    assert _chunks(db_url) == [("다음 주로 미루다",), ("회의가 미뤄지다",)]


def test_a_stale_button_is_already_handled(offline, graph):
    context = _context(graph)
    cid = capture.new_capture("x")
    asyncio.run(bot._run(context, 1001, cid, {"text": "x"}))
    update, q = _tap(f"ch:{cid}:1:ok")
    asyncio.run(bot.on_chunk(update, context))
    q.answer.assert_awaited_with("Already handled")


def test_krdict_glosses_cover_homographs(monkeypatch):
    monkeypatch.setattr(capture, "KRDICT_GAP", 0)
    entries = [{"definitions": [{"en_word": "boost"}]}, {"definitions": [{"en_word": "earlier"}]}]
    monkeypatch.setattr(capture, "_mbxread", lambda path: entries)
    assert capture.krdict_gloss("진작") == "boost | earlier"
    monkeypatch.setattr(capture, "_mbxread", lambda path: [])
    assert capture.krdict_gloss("뷁") is None


def test_critic_keeps_only_real_fixes(monkeypatch):
    review = capture.Review(casual="a", polite="b", issues=["casual", "polite", "먹었어요 → 드셨어요: honorific"])
    monkeypatch.setattr(capture, "ask", lambda *a: review)
    state = {"text": "t", "draft": {"casual": "a", "polite": "b"}, "findings": {"krdict": {}, "usage": {}}}
    assert capture.critic(state)["review"]["issues"] == ["먹었어요 → 드셨어요: honorific"]
