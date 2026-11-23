"""Capture agent (SPEC §7e): decides word vs sentence and writes the Korean, with the MCP tools.

Grounding is not the agent's choice: after it submits, capture's `lookup` (sentence) or
`word_lookup` (word) always runs. Here the model may use the tools to choose its Korean.
"""
import ast
import asyncio
import json
import logging
import re

import psycopg
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_ollama import ChatOllama
from langgraph.config import get_config
from langgraph.types import interrupt

from mbxchat import capture, config, krdict

log = logging.getLogger(__name__)
MAX_STEPS = 6

SYSTEM = (
    "You help an intermediate learner of Korean capture something they want to say.\n"
    "- If they ask for one word or term (\"the word for X\", \"Korean for X?\", a single English word), "
    "find the Korean word and call submit_word.\n"
    "- Otherwise write the sentence in Korean, casual (반말, to a close friend) and polite (해요체), "
    "fitting the situation if one is given, and call submit_sentence.\n"
    "You may check a Korean word with the tools first (always in Korean, dictionary form). "
    "Always finish with exactly one submit tool."
)


@tool
def submit_word(korean: str, english: str, examples: list[str]) -> str:
    """Finish a word capture: the Korean word in dictionary form, its English meaning, and 2-3
    natural example sentences in Korean."""
    return "ok"


@tool
def submit_sentence(casual: str, polite: str, note: str) -> str:
    """Finish a sentence capture: the casual (반말) and polite (해요체) Korean, and one short
    English line on a word choice worth knowing."""
    return "ok"


def _llm():
    return ChatOllama(model=config.CAPTURE_MODEL, base_url=config.OLLAMA_URL, temperature=0.2, reasoning=False)


async def _mcp_tools() -> list:
    return await MultiServerMCPClient({"mbxchat": {"transport": "streamable_http", "url": config.MCP_URL}}).get_tools()


def text_call(content: str, names) -> dict | None:
    """A tool call the model wrote as text, `submit_sentence(casual="…", polite="…")`, if it parses
    cleanly with literal arguments; small models do this instead of a structured call."""
    try:
        node = ast.parse(content.strip().strip("`").strip(), mode="eval").body
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in names and not node.args:
            return {"name": node.func.id, "args": {k.arg: ast.literal_eval(k.value) for k in node.keywords},
                    "id": "text-call"}
    except (SyntaxError, ValueError):
        pass
    return None


async def _run(meaning: str) -> dict:
    notes: list[str] = []
    try:
        tools = await _mcp_tools()
    except Exception as e:  # the MCP server is a helper: draft without it
        log.warning("MCP tools unavailable: %s", e)
        tools, notes = [], [f"tool server unavailable: {e}"]
    by_name = {t.name: t for t in [*tools, submit_word, submit_sentence]}
    llm = _llm().bind_tools(list(by_name.values()))
    msgs = [SystemMessage(SYSTEM), HumanMessage(meaning)]
    calls = 0
    for _ in range(MAX_STEPS):
        reply = await llm.ainvoke(msgs)
        msgs.append(reply)
        wanted = reply.tool_calls or [c for c in [text_call(reply.content, by_name)] if c]
        if not wanted:
            msgs.append(HumanMessage(f"Call submit_word or submit_sentence now, as a tool call, with your "
                                     f"Korean for: {meaning}"))
            continue
        for c in wanted:
            if c["name"] in ("submit_word", "submit_sentence"):
                try:
                    by_name[c["name"]].args_schema.model_validate(c["args"])
                except Exception as e:
                    msgs.append(ToolMessage(f"error: {e}", tool_call_id=c["id"]))
                    continue
                return {"kind": c["name"].removeprefix("submit_"), "args": c["args"], "calls": calls, "notes": notes}
            calls += 1
            tool_ = by_name.get(c["name"])
            try:
                out = await tool_.ainvoke(c["args"]) if tool_ else f"error: no tool {c['name']}"
            except Exception as e:  # bad arguments or a tool failure: tell the model, keep going
                out = f"error: {e}"
            msgs.append(ToolMessage(out if isinstance(out, str) else json.dumps(out, ensure_ascii=False, default=str),
                                    tool_call_id=c["id"]))
    raise capture.CaptureError(f"the agent did not finish in {MAX_STEPS} steps")


def agent(state: capture.State) -> capture.State:
    out = asyncio.run(_run(capture._meaning(state)))
    a = out["args"]
    if out["kind"] == "sentence":
        return {"kind": "sentence", "agent_calls": out["calls"], "agent_notes": out["notes"],
                "draft": {"casual": a["casual"], "polite": a["polite"], "note": a.get("note", "")}}
    return {"kind": "word", "agent_calls": out["calls"], "agent_notes": out["notes"],
            "word": {"korean": a["korean"].strip(), "english": a["english"].strip(),
                     "model_examples": [e.strip() for e in a.get("examples", []) if e.strip()][:3]}}


ROOT_SUFFIXES = ("스럽다", "하다", "되다", "화", "적")
SENTENCE_END = re.compile(r"(다|요|까|죠|[.?!…])[\"'”’)\]]*$")


def stem(word: str) -> str:
    """The part every form keeps: 미루다 → 미루, 최적화 → 최적화."""
    return word[:-1] if word.endswith("다") and len(word) > 2 else word


def is_sentence(text: str) -> bool:
    """A full sentence (it ends like one), not a transcript fragment."""
    return len(text.strip()) >= 6 and bool(SENTENCE_END.search(text.strip()))


def root_of(word: str) -> str | None:
    """최적화 → 최적, 연기되다 → 연기: the Sino-Korean root krdict often lists when the derivation is missing."""
    for s in ROOT_SUFFIXES:
        if word.endswith(s) and len(word) - len(s) >= 2:
            return word[: -len(s)]
    return None


def word_lookup(state: capture.State) -> capture.State:
    """Enforced grounding for a word: krdict (one root fallback), then examples: full sentences from
    the library, else krdict's (one more request), else the model's, marked by `source`."""
    capture_id = int(get_config()["configurable"]["thread_id"])
    with psycopg.connect(config.DATABASE_URL) as conn:  # idempotent: keeps word captures out of practice
        conn.execute("UPDATE capture SET kind = 'word' WHERE id = %s", (capture_id,))
    w = dict(state["word"]) | {"entries": [], "root": None, "examples": [], "source": "model"}
    notes = list(state.get("agent_notes", []))
    if krdict.enabled():
        try:
            w["entries"] = krdict.search(w["korean"])
            if not w["entries"] and (root := root_of(w["korean"])) and (entries := krdict.search(root)):
                w["root"], w["entries"] = root, entries
        except krdict.Unavailable as e:
            notes.append(f"krdict unavailable: {e}")
    if config.MBXREAD_URL:
        try:
            if hits := [h for h in capture.usage(w["korean"], w["korean"]) if is_sentence(h) and stem(w["korean"]) in h]:
                w["examples"], w["source"] = hits, "library"
        except capture.Unavailable as e:
            notes.append(f"MbxRead usage unavailable: {e}")
    exact = [e for e in w["entries"] if e["word"] == (w["root"] or w["korean"])]
    if not w["examples"] and exact:
        try:
            # the entry page also carries examples of related entries: keep the ones using the word
            if found := [e for e in krdict.examples(exact[0]["target_code"], 8) if stem(w["root"] or w["korean"]) in e]:
                w["examples"], w["source"] = found, "krdict"
        except krdict.Unavailable as e:
            notes.append(f"krdict unavailable: {e}")
    if not w["examples"]:  # model examples that use another word (데드라인 card, 마감일 examples) are dropped
        w["examples"] = [e for e in w["model_examples"] if stem(w["korean"]) in e]
    w["examples"] = [re.sub(r"\s+", " ", e) for e in w["examples"]][:3]
    return {"word": w, "findings": {"krdict": {}, "usage": {}, "notes": notes}}


def word_review(state: capture.State) -> capture.State:
    # Re-runs from the top on resume: no side effects here.
    return {"decisions": [interrupt({"word": state["word"]})]}


def dictionary_line(w: dict) -> str:
    gloss = " | ".join(g for e in w["entries"] for g in e["glosses"][:1])
    if not w["entries"]:
        return "not in the learners' dictionary"
    return f"root {w['root']}: {gloss}" if w["root"] else gloss


def word_save(state: capture.State) -> capture.State:
    if state["decisions"][0]["action"] != "ok":
        return {"saved": 0}
    w = state["word"]
    capture_id = int(get_config()["configurable"]["thread_id"])
    with psycopg.connect(config.DATABASE_URL) as conn:
        conn.execute(
            "INSERT INTO word_card (capture_id, korean, english, dictionary, examples) VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (capture_id) DO NOTHING",
            (capture_id, w["korean"], w["english"], dictionary_line(w), json.dumps(w["examples"], ensure_ascii=False)),
        )
    return {"saved": 1}
