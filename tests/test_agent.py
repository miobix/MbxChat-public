"""Capture agent (SPEC §7e): a scripted model and in-process tools; graph, Postgres and krdict cache real."""
import psycopg
import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.types import Command

from mbxchat import agent, bot, capture, config, db, krdict

REVIEW = capture.Review(casual="나 늦어.", polite="저 늦어요.", issues=[])
CHUNKS = capture.Chunks(items=[])


def _call(name, **args):
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": f"c{name}"}])


class ScriptedLLM:
    def __init__(self, replies):
        self.replies, self.seen = list(replies), []

    def bind_tools(self, tools):
        self.tools = [t.name for t in tools]
        return self

    async def ainvoke(self, msgs):
        self.seen.append(list(msgs))
        return self.replies.pop(0) if self.replies else AIMessage("thinking…")


@tool
async def krdict_lookup(word: str) -> dict:
    """Fake krdict tool."""
    return {"available": True, "entries": []}


def _search(word):
    return {"최적": [{"word": "최적", "pos": "명사", "target_code": "9", "glosses": ["optimum"]}]}.get(word, [])


@pytest.fixture
def run(db_url, monkeypatch):
    """Runs one capture in agent mode with the given model replies; returns (state, llm)."""
    monkeypatch.setattr(config, "KRDICT_API_KEY", "k")
    monkeypatch.setattr(config, "MBXREAD_URL", "")
    monkeypatch.setattr(krdict, "search", _search)
    monkeypatch.setattr(krdict, "examples", lambda code, k=4: ["최적의 조건이에요."])
    monkeypatch.setattr(capture, "ask", lambda schema, s, u: {capture.Review: REVIEW, capture.Chunks: CHUNKS}[schema])
    monkeypatch.setattr(capture, "content_lemmas", lambda text: [])

    async def tools():
        return [krdict_lookup]
    monkeypatch.setattr(agent, "_mcp_tools", tools)
    saver = db.checkpointer(db_url)
    graph = capture.build(saver, mode="agent")

    def go(replies, text="x", resume=None):
        llm = ScriptedLLM(replies)
        monkeypatch.setattr(agent, "_llm", lambda: llm)
        cid = capture.new_capture(text)
        cfg = {"configurable": {"thread_id": str(cid)}}
        graph.invoke({"text": text}, cfg)
        if resume:
            graph.invoke(Command(resume={"action": resume}), cfg)
        return graph.get_state(cfg).values | {"capture_id": cid}, llm
    yield go
    saver.conn.close()


def test_a_sentence_goes_through_the_unit_3_chain(run):
    state, llm = run([_call("krdict_lookup", word="늦다"),
                      _call("submit_sentence", casual="나 늦어.", polite="저 늦어요.", note="늦다 = be late")])
    assert state["kind"] == "sentence" and state["agent_calls"] == 1
    assert state["draft"] == {"casual": "나 늦어.", "polite": "저 늦어요.", "note": "늦다 = be late"}
    assert state["review"] == REVIEW.model_dump() and state["saved"] == 0
    assert {"krdict_lookup", "submit_word", "submit_sentence"} <= set(llm.tools)


def test_a_word_is_grounded_with_the_root_fallback_and_krdict_examples(run):
    state, _ = run([_call("submit_word", korean="최적화", english="optimization", examples=["최적화가 필요해요."])])
    w = state["word"]
    assert state["kind"] == "word" and "review" not in state and "saved" not in state  # waits for the card tap
    assert (w["root"], w["entries"][0]["glosses"], w["examples"], w["source"]) == (
        "최적", ["optimum"], ["최적의 조건이에요."], "krdict")
    assert "not in the learners' dictionary; root <b>최적</b>: optimum" in bot._summary(state)


def test_a_word_nowhere_keeps_the_model_examples_marked(run, monkeypatch):
    monkeypatch.setattr(krdict, "search", lambda word: [])
    state, _ = run([_call("submit_word", korean="뷁뷁", english="nonsense", examples=["뷁뷁이에요."])])
    assert (state["word"]["examples"], state["word"]["source"]) == (["뷁뷁이에요."], "model")
    assert "model-written, unchecked" in bot._summary(state)


def test_an_answer_in_text_is_nudged_then_an_unfinished_agent_fails(run):
    state, llm = run([AIMessage("최적화"), _call("submit_word", korean="최적화", english="opt", examples=[])])
    assert state["kind"] == "word" and "Finish now" in llm.seen[1][-1].content
    with pytest.raises(capture.CaptureError, match="did not finish"):
        run([])


def test_a_bad_submit_is_sent_back_to_the_model(run):
    state, llm = run([_call("submit_sentence", casual="나 늦어."),
                      _call("submit_sentence", casual="나 늦어.", polite="저 늦어요.", note="")])
    assert state["kind"] == "sentence" and "error" in llm.seen[1][-1].content


def test_without_the_tool_server_the_agent_still_drafts(run, monkeypatch):
    async def down():
        raise OSError("connection refused")
    monkeypatch.setattr(agent, "_mcp_tools", down)
    state, llm = run([_call("submit_sentence", casual="나 늦어.", polite="저 늦어요.", note="")])
    assert state["agent_notes"] == ["tool server unavailable: connection refused"]
    assert set(llm.tools) == {"submit_word", "submit_sentence"}
    assert "⚠️ tool server unavailable" in bot._summary(state)


@pytest.mark.parametrize("word, root", [("최적화", "최적"), ("연기되다", "연기"), ("공부하다", "공부"),
                                        ("자연스럽다", "자연"), ("화", None), ("미루다", None)])
def test_root_of(word, root):
    assert agent.root_of(word) == root


def _word_cards(db_url):
    with psycopg.connect(db_url) as conn:
        return conn.execute("SELECT korean, english, dictionary, examples FROM word_card").fetchall()


def test_an_approved_word_lands_in_the_outbox_and_stays_out_of_practice(run, db_url):
    from mbxchat import practice
    state, _ = run([_call("submit_word", korean="최적화", english="optimization", examples=[])], resume="ok")
    assert state["saved"] == 1
    assert _word_cards(db_url) == [("최적화", "optimization", "root 최적: optimum", ["최적의 조건이에요."])]
    with psycopg.connect(db_url) as conn:
        assert conn.execute("SELECT kind FROM capture WHERE id = %s", (state["capture_id"],)).fetchone()[0] == "word"
        assert practice._new_translation(conn) is None or practice._new_translation(conn)[0] == "item"


def test_a_skipped_word_saves_nothing(run, db_url):
    state, _ = run([_call("submit_word", korean="최적화", english="optimization", examples=[])], resume="sk")
    assert state["saved"] == 0 and _word_cards(db_url) == []


def test_library_fragments_are_dropped_for_full_sentences(run, monkeypatch):
    monkeypatch.setattr(config, "MBXREAD_URL", "http://mbxread")
    monkeypatch.setattr(capture, "usage", lambda lemma, s: ["해서 어떻게 최적화를 좀 달할 수", "성능을 최적화했어요."])
    state, _ = run([_call("submit_word", korean="최적화", english="optimization", examples=[])])
    assert (state["word"]["examples"], state["word"]["source"]) == (["성능을 최적화했어요."], "library")
    monkeypatch.setattr(capture, "usage", lambda lemma, s: ["어렵다 보니까 이게 최적화가 제일"])
    state, _ = run([_call("submit_word", korean="최적화", english="optimization", examples=[])])
    assert state["word"]["source"] == "krdict"
