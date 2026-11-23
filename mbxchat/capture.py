"""Capture workflow (SPEC §7c): draft → lookup → critic → chunks → review (interrupts) → save."""
import json
import logging
import urllib.error
import urllib.request
from functools import cache
from typing import Literal, TypedDict

import psycopg
from langchain_core.exceptions import OutputParserException
from langchain_ollama import ChatOllama
from langgraph.config import get_config
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel, Field, ValidationError

from mbxchat import config, krdict

log = logging.getLogger(__name__)

CONTENT_TAGS = {"NNG", "NNP", "VV", "VA", "MAG", "XR"}
MAX_KRDICT = 4


class CaptureError(Exception):
    """A step failed in a way the user should hear about."""


class Unavailable(Exception):
    pass


class Draft(BaseModel):
    casual: str = Field(description="Casual Korean (반말), as said to a close friend")
    polite: str = Field(description="Polite Korean (해요체)")
    note: str = Field(description="One short line in English on a word choice worth knowing")


class Review(BaseModel):
    casual: str = Field(description="The casual sentence, corrected if needed")
    polite: str = Field(description="The polite sentence, corrected if needed")
    issues: list[str] = Field(
        description="Only changes you actually made, one per entry, in English: 'wrong → right: why'. "
        "Empty list if you changed nothing"
    )


class Chunk(BaseModel):
    ko: str = Field(description="A reusable Korean chunk in dictionary form, 2-6 words")
    gloss: str = Field(description="A short English gloss of the chunk")
    kind: Literal["collocation", "expression", "grammar"]
    register_note: str = Field(description="When it fits: casual, polite, written, …")
    sentence: str = Field(description="The full Korean sentence it comes from, copied exactly")


class Chunks(BaseModel):
    items: list[Chunk] = Field(description="0 to 3 chunks worth an Anki card", max_length=3)


class State(TypedDict, total=False):
    text: str
    situation: str
    draft: dict
    findings: dict
    review: dict
    chunks: list[dict]
    decisions: list[dict]
    saved: int
    kind: str  # agent mode: "sentence" or "word"
    word: dict
    agent_calls: int
    agent_notes: list[str]


def ask(schema: type[BaseModel], system: str, user: str, model: str | None = None) -> BaseModel:
    llm = ChatOllama(
        model=model or config.CAPTURE_MODEL, base_url=config.OLLAMA_URL, temperature=0.2, reasoning=False
    ).with_structured_output(schema, method="json_schema")
    try:
        return llm.invoke([("system", system), ("human", user)])
    except (OutputParserException, ValidationError):
        log.warning("invalid %s from the model, retrying once", schema.__name__)
    try:
        return llm.invoke([("system", system), ("human", user)])
    except (OutputParserException, ValidationError) as e:
        raise CaptureError(f"the model returned an invalid {schema.__name__} twice") from e


# --- lookups -------------------------------------------------------------------------------

@cache
def _kiwi():
    from kiwipiepy import Kiwi

    return Kiwi()


def content_lemmas(text: str) -> list[str]:
    seen = {}
    for t in _kiwi().tokenize(text):
        if t.tag in CONTENT_TAGS:
            seen.setdefault(t.form + "다" if t.tag in ("VV", "VA") else t.form, None)
    return list(seen)


def nikl_grades(lemmas: list[str]) -> dict[str, str]:
    with psycopg.connect(config.DATABASE_URL) as conn:
        rows = conn.execute(
            "SELECT key, data->>'grade' FROM item WHERE kind = 'word' AND key = ANY(%s)", (lemmas,)
        ).fetchall()
    return dict(rows)


def _mbxread(path: str, body: dict | None = None, timeout: float = 20) -> object:
    url = f"{config.MBXREAD_URL.rstrip('/')}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data, {"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:200]
        raise Unavailable(f"HTTP {e.code}: {detail}") from e
    except (OSError, ValueError) as e:
        raise Unavailable(str(e)) from e


def krdict_gloss(lemma: str) -> str | None:
    """First English gloss of up to 3 krdict entries (homographs), None if none."""
    entries = krdict.search(lemma)
    return " | ".join(e["glosses"][0] if e["glosses"] else "?" for e in entries) if entries else None


def usage(lemma: str, sentence: str) -> list[str]:
    found = _mbxread("/api/usage", {"lemma": lemma, "sentence": sentence, "k": 2, "method": "hybrid"})
    return [h["text"] for h in found["hits"]]


# --- nodes ---------------------------------------------------------------------------------

DRAFT_SYSTEM = (
    "You help an intermediate learner say things in natural, everyday Korean. The user writes what "
    "they want to say, in English, maybe with a situation (who to, where, mood). Give one casual and "
    "one polite sentence that a Korean speaker would actually say in that situation."
)
CRITIC_SYSTEM = (
    "You are a strict Korean editor. Check two learner-facing sentences for grammar, word choice, "
    "naturalness and register. Dictionary and library evidence is provided; a word the dictionary "
    "does not know may not exist. Fix what is wrong, keep what is right, list each fix."
)
CHUNKS_SYSTEM = (
    "From these Korean sentences, pick at most 3 reusable chunks a learner should put on flashcards: "
    "collocations, set expressions, or grammar patterns in use. Skip single basic words and anything "
    "a beginner already knows. Give each chunk in dictionary form. Zero chunks is a fine answer."
)


def split_situation(message: str) -> tuple[str, str]:
    """'what to say // situation' → (what to say, situation)."""
    text, _, situation = message.partition("//")
    return text.strip(), situation.strip()


def _meaning(state: State) -> str:
    situation = state.get("situation")
    return state["text"] + (f"\nSituation: {situation}" if situation else "")


def draft(state: State) -> State:
    return {"draft": ask(Draft, DRAFT_SYSTEM, _meaning(state)).model_dump()}


def lookup(state: State) -> State:
    d = state["draft"]
    lemmas = content_lemmas(f"{d['casual']} {d['polite']}")
    grades = nikl_grades(lemmas)
    rare = [lemma for lemma in lemmas if lemma not in grades]
    findings: dict = {"krdict": {}, "usage": {}, "notes": []}
    for lemma in rare[:MAX_KRDICT] if krdict.enabled() else []:
        try:
            findings["krdict"][lemma] = krdict_gloss(lemma)
        except krdict.Unavailable as e:
            findings["notes"].append(f"krdict unavailable: {e}")
            break
    beyond_beginner = rare + [lemma for lemma in lemmas if grades.get(lemma) in ("B", "C")]
    for lemma in beyond_beginner[:2] if config.MBXREAD_URL else []:
        try:
            findings["usage"][lemma] = usage(lemma, d["polite"])
        except Unavailable as e:
            findings["notes"].append(f"MbxRead usage unavailable: {e}")
            break
    return {"findings": findings}


def critic(state: State) -> State:
    d, f = state["draft"], state["findings"]
    evidence = [f"{k}: {v}" if v else f"{k}: NOT IN THE DICTIONARY" for k, v in f["krdict"].items()]
    examples = [f"{k}: {s}" for k, hits in f["usage"].items() for s in hits]
    prompt = (
        f"What the learner wants to say: {_meaning(state)}\n\nCasual: {d['casual']}\nPolite: {d['polite']}"
        f"\n\nDictionary: {'; '.join(evidence) or 'all words are common'}"
        f"\nLibrary sentences using these words: {' | '.join(examples) or 'none'}"
    )
    review = ask(Review, CRITIC_SYSTEM, prompt).model_dump()
    review["issues"] = [i for i in review["issues"] if "→" in i]  # gemma sometimes lists field names
    return {"review": review}


def chunks(state: State) -> State:
    r = state["review"]
    prompt = f"Meaning: {_meaning(state)}\n\nCasual: {r['casual']}\nPolite: {r['polite']}"
    found = [c.model_dump() for c in ask(Chunks, CHUNKS_SYSTEM, prompt).items[:3]]
    for c in found:
        c["sentence"] = full_sentence(c["sentence"], [r["polite"], r["casual"]])
    return {"chunks": found}


def full_sentence(quoted: str, sentences: list[str]) -> str:
    """Models shorten the source sentence ("회의가 연기돼서..."); take the reviewed one it came from."""
    stem = quoted.rstrip(".… ")
    return next((s for s in sentences if s.startswith(stem)), max(sentences, key=lambda s: len(set(s) & set(stem))))


def review(state: State) -> State:
    # Re-runs from the top on every resume: nothing here may have side effects.
    return {"decisions": [interrupt({"i": i, "chunk": c}) for i, c in enumerate(state["chunks"])]}


def save(state: State) -> State:
    capture_id = int(get_config()["configurable"]["thread_id"])
    rows = [
        (capture_id, d.get("ko") or c["ko"], c["gloss"], c["kind"], c["register_note"], c["sentence"])
        for c, d in zip(state["chunks"], state["decisions"]) if d["action"] != "skip"
    ]
    with psycopg.connect(config.DATABASE_URL) as conn:
        r = state["review"]
        conn.execute("UPDATE capture SET polite = %s, casual = %s WHERE id = %s", (r["polite"], r["casual"], capture_id))
        conn.cursor().executemany(
            "INSERT INTO chunk (capture_id, ko, gloss, kind, register_note, sentence) "
            "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING", rows
        )
    return {"saved": len(rows)}


NODES = {"draft": draft, "lookup": lookup, "critic": critic, "chunks": chunks, "review": review, "save": save}


def build(checkpointer, mode: str | None = None):
    """`workflow`: the fixed unit 3 chain. `agent` (SPEC §7e): the agent drafts a sentence (then the
    same chain from lookup) or finds a word (then word_lookup)."""
    g = StateGraph(State)
    names = list(NODES)
    if (mode or config.CAPTURE_MODE) == "agent":
        from mbxchat import agent

        names = names[1:]
        g.add_node("agent", agent.agent)
        for name, node in (("word_lookup", agent.word_lookup), ("word_review", agent.word_review),
                           ("word_save", agent.word_save)):
            g.add_node(name, node)
        g.add_edge(START, "agent")
        g.add_conditional_edges("agent", lambda s: "word_lookup" if s["kind"] == "word" else "lookup")
        g.add_edge("word_lookup", "word_review")
        g.add_edge("word_review", "word_save")
        g.add_edge("word_save", END)
    else:
        g.add_edge(START, names[0])
    for name in names:
        g.add_node(name, NODES[name])
    for a, b in zip(names, [*names[1:], END]):
        g.add_edge(a, b)
    return g.compile(checkpointer=checkpointer)


def new_capture(text: str, situation: str = "") -> int:
    with psycopg.connect(config.DATABASE_URL) as conn:
        return conn.execute(
            "INSERT INTO capture (text, situation) VALUES (%s, %s) RETURNING id", (text, situation)
        ).fetchone()[0]


def model_problem() -> str | None:
    """Ollama pins by tag only, so check the pulled model is the evaluated one."""
    try:
        with urllib.request.urlopen(f"{config.OLLAMA_URL.rstrip('/')}/api/tags", timeout=5) as resp:
            models = {m["name"]: m["digest"] for m in json.load(resp)["models"]}
    except (OSError, ValueError) as e:
        return f"Ollama unreachable at {config.OLLAMA_URL}: {e}"
    digest = models.get(config.CAPTURE_MODEL)
    if digest is None:
        return f"{config.CAPTURE_MODEL} is not pulled in Ollama"
    if not digest.startswith(config.CAPTURE_MODEL_ID):
        return f"{config.CAPTURE_MODEL} is {digest[:12]}, expected {config.CAPTURE_MODEL_ID}"
    return None
