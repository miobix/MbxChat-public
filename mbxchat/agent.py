"""Capture agent (SPEC §7e): decides word vs sentence and writes the Korean, with the MCP tools.

Grounding is not the agent's choice: after it submits, capture's `lookup` (sentence) or
`word_lookup` (word) always runs. Here the model may use the tools to choose its Korean.
"""
import asyncio
import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_ollama import ChatOllama

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
        if not reply.tool_calls:
            msgs.append(HumanMessage("Finish now with submit_word or submit_sentence."))
            continue
        for c in reply.tool_calls:
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


def root_of(word: str) -> str | None:
    """최적화 → 최적, 연기되다 → 연기: the Sino-Korean root krdict often lists when the derivation is missing."""
    for s in ROOT_SUFFIXES:
        if word.endswith(s) and len(word) - len(s) >= 2:
            return word[: -len(s)]
    return None


def word_lookup(state: capture.State) -> capture.State:
    """Enforced grounding for a word: krdict (one root fallback), then examples from the library,
    else krdict's (one more request), else the model's, marked by `source`."""
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
            if hits := capture.usage(w["korean"], w["korean"]):
                w["examples"], w["source"] = hits, "library"
        except capture.Unavailable as e:
            notes.append(f"MbxRead usage unavailable: {e}")
    exact = [e for e in w["entries"] if e["word"] == (w["root"] or w["korean"])]
    if not w["examples"] and exact:
        try:
            if found := krdict.examples(exact[0]["target_code"], 3):
                w["examples"], w["source"] = found, "krdict"
        except krdict.Unavailable as e:
            notes.append(f"krdict unavailable: {e}")
    if not w["examples"]:
        w["examples"] = w["model_examples"]
    w["examples"] = [re.sub(r"\s+", " ", e) for e in w["examples"]][:3]
    return {"word": w, "findings": {"krdict": {}, "usage": {}, "notes": notes}}
