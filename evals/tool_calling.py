"""Tool-calling check (unit 7 planning): can a local model drive capture with tools?

Fake read-only tools, no network besides Ollama. Each prompt runs a tool loop until the model
calls submit_word or submit_sentence (or MAX_STEPS). Host only:
PYTHONUTF8=1 .venv/Scripts/python -m evals.tool_calling MODEL [MODEL ...]
"""
import json
import re
import statistics
import sys
import time

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama

from evals.grader_eval import HERE
from mbxchat import config

MAX_STEPS = 8
REPEATS = 2


@tool
def krdict_lookup(word: str) -> str:
    """Look up a Korean word (dictionary form) in the Korean-English learner's dictionary."""
    return f"{word}: dictionary entry found (fake)."


@tool
def library_examples(lemma: str, k: int = 2) -> list[str]:
    """Real sentences using a Korean lemma, from the learner's reading library."""
    return [f"예문 {i + 1}: ...{lemma}..." for i in range(min(k, 4))]


@tool
def known_items(query: str) -> str:
    """Whether a Korean word or grammar point is already known or being learned."""
    return f"{query}: not in the learner's items."


@tool
def submit_word(korean: str, english: str, examples: list[str]) -> str:
    """Finish a single-word capture: the Korean word, its English meaning, 2-4 example sentences."""
    return "ok"


@tool
def submit_sentence(casual: str, polite: str, chunks: list[str]) -> str:
    """Finish a sentence capture: casual and polite Korean versions and 1-3 reusable chunks."""
    return "ok"


TOOLS = [krdict_lookup, library_examples, known_items, submit_word, submit_sentence]
BY_NAME = {t.name: t for t in TOOLS}
SYSTEM = (
    "You help an intermediate learner of Korean capture what they want to say. If they ask for "
    "a single word, find the Korean word, check it in the dictionary, get example sentences, "
    "then call submit_word. If they want a sentence, write casual and polite Korean, check "
    "unusual words in the dictionary, then call submit_sentence. Always finish with a submit tool."
)
PROMPTS = [  # (text, expected submit)
    ("the word for optimization, a coworker said it", "submit_word"),
    ("word: deadline", "submit_word"),
    ("how do you say 'commute' as a noun", "submit_word"),
    ("Korean for receipt?", "submit_word"),
    ("procrastinate", "submit_word"),
    ("I'm running late, start without me // to a friend", "submit_sentence"),
    ("Could you check the report before the meeting tomorrow? // to my boss", "submit_sentence"),
    ("This is way too spicy for me // at dinner with friends", "submit_sentence"),
    ("Is it okay if I pay by card? // to a shop clerk", "submit_sentence"),
    ("Thank you for taking care of me while I was sick // to my mother-in-law", "submit_sentence"),
]


def run(model: str, text: str) -> dict:
    llm = ChatOllama(model=model, base_url=config.OLLAMA_URL, temperature=0.2, reasoning=False).bind_tools(TOOLS)
    msgs = [SystemMessage(SYSTEM), HumanMessage(text)]
    calls, bad, t = [], 0, time.perf_counter()
    for _ in range(MAX_STEPS):
        reply = llm.invoke(msgs)
        msgs.append(reply)
        bad += len(reply.invalid_tool_calls)
        if not reply.tool_calls:
            break  # answered in text without submitting
        for c in reply.tool_calls:
            calls.append({"name": c["name"], "args": c["args"]})
            try:
                out = BY_NAME[c["name"]].invoke(c["args"])
            except Exception as e:  # unknown tool or args failing the schema
                bad += 1
                out = f"error: {e}"
            msgs.append(ToolMessage(json.dumps(out, ensure_ascii=False), tool_call_id=c["id"]))
        if any(c["name"].startswith("submit_") for c in reply.tool_calls):
            break
    submit = next((c for c in reversed(calls) if c["name"].startswith("submit_")), None)
    return {"calls": calls, "bad": bad, "submit": submit, "seconds": round(time.perf_counter() - t, 1)}


def main(models: list[str]) -> None:
    rows, log = [], []
    for m in models:
        runs = []
        for text, want in PROMPTS:
            for _ in range(REPEATS):
                r = run(m, text) | {"model": m, "prompt": text, "want": want}
                runs.append(r)
                print(m, text, r["submit"] and r["submit"]["name"], r["seconds"], flush=True)
        log += runs
        rows.append({
            "model": m, "runs": len(runs),
            "finished": sum(bool(r["submit"]) for r in runs),
            "right_path": sum(bool(r["submit"]) and r["submit"]["name"] == r["want"] for r in runs),
            "looked_up_korean": sum(any(c["name"] == "krdict_lookup" and re.search("[가-힣]", str(c["args"]))
                                        for c in r["calls"]) for r in runs),
            "library_on_words": sum(any(c["name"] == "library_examples" for c in r["calls"])
                                    for r in runs if r["want"] == "submit_word"),
            "bad_calls": sum(r["bad"] for r in runs),
            "median_calls": statistics.median(len(r["calls"]) for r in runs),
            "median_s": statistics.median(r["seconds"] for r in runs),
        })
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "tool_calling.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    for row in rows:
        print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
