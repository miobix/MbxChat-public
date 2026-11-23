"""Practice loop (SPEC §7d): prompts from the pool, an LLM grader, a resurfacing ladder, pings."""
import re
from datetime import date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from mbxchat import config
from mbxchat.capture import ask

LADDER = (3, 10, 30, 90)
SESSION_IDLE = timedelta(minutes=30)
LATE_ANSWER = timedelta(hours=12)
GRAMMAR_MAX_LEVEL = 4  # new grammar points come from levels 1-4 first, then 5-6


class Grade(BaseModel):
    # Field order is generation order: the verdict comes after the model has listed the errors.
    issues: list[str] = Field(description="Each real error, in English: 'wrong → right: why'. Empty if none")
    corrected: str = Field(description="The learner's sentence with exactly the listed errors fixed")
    model_answer: str = Field(description="A full Korean sentence a native speaker would say here")
    note: str = Field(description="At most one short English sentence worth remembering, or empty")
    verdict: Literal["correct", "minor", "wrong"] = Field(
        description="correct: no issues. minor: understandable, small slips (spelling, spacing, a particle, "
        "slightly unnatural). wrong: meaning off, broken grammar, or the required grammar missing"
    )


GRADER_SYSTEM = (
    "You are a kind but exact Korean teacher. Grade one learner answer to the task. A reference "
    "answer, when given, is one good answer; other correct answers are just as right. Judge "
    "grammar, word choice, naturalness and register for the situation. Do not invent errors."
)


def _conn():
    return psycopg.connect(config.DATABASE_URL, row_factory=dict_row)


def now() -> datetime:
    return datetime.now(ZoneInfo(config.PRACTICE_TZ))


# --- sessions --------------------------------------------------------------------------------

def current_session() -> int | None:
    """The open session, closing any that sat idle past SESSION_IDLE."""
    with _conn() as conn:
        conn.execute(
            "UPDATE session SET closed_at = now() WHERE closed_at IS NULL AND last_at < now() - %s",
            (SESSION_IDLE,),
        )
        row = conn.execute("SELECT id FROM session WHERE closed_at IS NULL ORDER BY id DESC LIMIT 1").fetchone()
    return row["id"] if row else None


def open_session() -> int:
    with _conn() as conn:
        conn.execute("UPDATE session SET closed_at = now() WHERE closed_at IS NULL")
        return conn.execute("INSERT INTO session DEFAULT VALUES RETURNING id").fetchone()["id"]


def close_session() -> bool:
    with _conn() as conn:
        return conn.execute("UPDATE session SET closed_at = now() WHERE closed_at IS NULL").rowcount > 0


# --- choosing a prompt -----------------------------------------------------------------------

_NOT_RECENT = (
    "NOT EXISTS (SELECT 1 FROM prompt p WHERE p.source = {src} AND p.ref = {ref} "
    "AND p.sent_at > now() - interval '1 day')"
)
_UNDRILLED = "NOT EXISTS (SELECT 1 FROM drill d WHERE d.source = {src} AND d.ref = {ref})"
_CAPTURE, _ITEM = "'capture'", "'item'"


def _fresh(src: str, ref: str) -> str:
    return _NOT_RECENT.format(src=src, ref=ref) + " AND " + _UNDRILLED.format(src=src, ref=ref)


def _new_translation(conn) -> tuple[str, int] | None:
    """Captures first, then the graded sentences."""
    row = conn.execute(
        f"SELECT 'capture' AS source, id FROM capture c WHERE kind = 'sentence' AND {_fresh(_CAPTURE, 'c.id')} "
        "ORDER BY id LIMIT 1"
    ).fetchone()
    row = row or conn.execute(
        f"SELECT 'item' AS source, id FROM item i WHERE kind = 'sentence' AND {_fresh(_ITEM, 'i.id')} "
        "ORDER BY level, id LIMIT 1"
    ).fetchone()
    return (row["source"], row["id"]) if row else None


def _new_grammar(conn) -> tuple[str, int] | None:
    row = conn.execute(
        f"SELECT id FROM item i WHERE kind = 'grammar' AND {_fresh(_ITEM, 'i.id')} "
        "AND NOT EXISTS (SELECT 1 FROM known_grammar k WHERE k.item_id = i.id) "
        "ORDER BY level > %s, random() LIMIT 1", (GRAMMAR_MAX_LEVEL,)
    ).fetchone()
    return ("item", row["id"]) if row else None


def _pick(conn, today: date) -> tuple[str, int]:
    due = conn.execute(
        "SELECT source, ref FROM drill d WHERE due <= %s AND "
        + _NOT_RECENT.format(src="d.source", ref="d.ref") + " ORDER BY due, id LIMIT 1", (today,)
    ).fetchone()
    if due:
        return due["source"], due["ref"]
    last = conn.execute("SELECT kind FROM prompt ORDER BY id DESC LIMIT 1").fetchone()
    order = (_new_translation, _new_grammar) if last and last["kind"] == "grammar" else (_new_grammar, _new_translation)
    for find in order:
        if found := find(conn):
            return found
    row = conn.execute("SELECT source, ref FROM drill ORDER BY due, id LIMIT 1").fetchone()
    return row["source"], row["ref"]


def _build(conn, source: str, ref: int) -> dict:
    p = {"source": source, "ref": ref, "kind": "translate", "situation": "", "register": "",
         "reference": None, "grammar_id": None, "word": None}
    if source == "capture":
        c = conn.execute("SELECT text, situation, polite FROM capture WHERE id = %s", (ref,)).fetchone()
        return p | {"en": c["text"], "situation": c["situation"], "reference": c["polite"]}
    i = conn.execute("SELECT kind, ko, en, data FROM item WHERE id = %s", (ref,)).fetchone()
    if i["kind"] == "sentence":
        g = conn.execute("SELECT id FROM item WHERE kind = 'grammar' AND key = %s", (i["data"].get("grammar_id"),)).fetchone()
        return p | {"en": i["en"], "reference": i["ko"], "register": i["data"].get("register", ""),
                    "grammar_id": g["id"] if g else None}
    word = conn.execute(
        "SELECT ko, en FROM item WHERE kind = 'term' AND data->>'status' = 'learning' ORDER BY random() LIMIT 1"
    ).fetchone()
    return p | {"kind": "grammar", "en": i["ko"], "grammar_id": ref,
                "word": f"{word['ko']} ({word['en']})" if word else None}


_COLUMNS = ("session_id", "source", "ref", "kind", "en", "situation", "register", "reference", "grammar_id", "word")


def next_prompt(session_id: int) -> dict:
    with _conn() as conn:
        p = _build(conn, *_pick(conn, now().date())) | {"session_id": session_id}
        row = conn.execute(
            f"INSERT INTO prompt ({', '.join(_COLUMNS)}) VALUES ({', '.join(['%s'] * len(_COLUMNS))}) RETURNING id",
            [p[k] for k in _COLUMNS],
        ).fetchone()
        conn.execute("UPDATE session SET last_at = now() WHERE id = %s", (session_id,))
    return p | {"id": row["id"]}


def get_prompt(prompt_id: int) -> dict | None:
    with _conn() as conn:
        return conn.execute("SELECT * FROM prompt WHERE id = %s", (prompt_id,)).fetchone()


def waiting(session_id: int | None) -> dict | None:
    """The prompt awaiting an answer: in the open session, or (session None) any from the last 12 h."""
    where = "session_id = %s" if session_id else "sent_at > now() - %s"
    with _conn() as conn:
        return conn.execute(
            f"SELECT * FROM prompt WHERE {where} AND answered_at IS NULL AND NOT skipped ORDER BY id DESC LIMIT 1",
            (session_id or LATE_ANSWER,),
        ).fetchone()


# --- grading and the ladder ------------------------------------------------------------------

def task(p: dict) -> str:
    if p["kind"] == "grammar":
        return f"Write one Korean sentence using the grammar {p['en']}" + (f" and the word {p['word']}" if p["word"] else "")
    return f"Say this in Korean: {p['en']}"


def grade(p: dict, answer: str, model: str | None = None) -> Grade:
    if p["reference"] and bare(answer) == bare(p["reference"]):
        return Grade(issues=[], corrected=answer, model_answer=p["reference"], note="", verdict="correct")
    lines = [f"Task: {task(p)}"]
    lines += [f"Situation: {p['situation']}"] * bool(p["situation"])
    lines += [f"Register: {p['register']}"] * bool(p["register"])
    lines += [f"Reference answer: {p['reference']}"] * bool(p["reference"])
    lines.append(f"Learner's answer: {answer}")
    if p.get("hint"):
        lines.append(f"A spelling checker suggests: {p['hint']} (it can be wrong, and misses many errors)")
    g = ask(Grade, GRADER_SYSTEM, "\n".join(lines), model or config.GRADER_MODEL)
    g.issues = [i for i in g.issues if "→" in i]
    if g.verdict == "correct" and (g.issues or bare(g.corrected) != bare(answer)):
        g.verdict = "minor"  # gemma sometimes fixes the sentence and still says correct
    return g


def bare(s: str) -> str:
    return re.sub(r"[\s.?!,]", "", s)


def schedule(step: int, verdict: str, today: date) -> tuple[int, date]:
    """(new step, due date): correct climbs the ladder, minor holds, wrong restarts tomorrow."""
    if verdict == "wrong":
        return 0, today + timedelta(days=1)
    days = LADDER[min(step, len(LADDER) - 1)]
    return (step + 1 if verdict == "correct" else step), today + timedelta(days=days)


def record(p: dict, answer: str, g: Grade) -> None:
    with _conn() as conn:
        claimed = conn.execute(
            "UPDATE prompt SET answer = %s, grade = %s, answered_at = now() WHERE id = %s AND answered_at IS NULL",
            (answer, g.model_dump_json(), p["id"]),
        ).rowcount
        if not claimed:
            return
        row = conn.execute("SELECT step FROM drill WHERE source = %s AND ref = %s", (p["source"], p["ref"])).fetchone()
        step, due = schedule(row["step"] if row else 0, g.verdict, now().date())
        conn.execute(
            "INSERT INTO drill (source, ref, step, due, last_verdict, times) VALUES (%s, %s, %s, %s, %s, 1) "
            "ON CONFLICT (source, ref) DO UPDATE SET step = EXCLUDED.step, due = EXCLUDED.due, "
            "last_verdict = EXCLUDED.last_verdict, times = drill.times + 1",
            (p["source"], p["ref"], step, due, g.verdict),
        )
        if p["session_id"]:
            conn.execute("UPDATE session SET last_at = now() WHERE id = %s", (p["session_id"],))


def skip(prompt_id: int) -> None:
    with _conn() as conn:
        p = conn.execute(
            "UPDATE prompt SET skipped = true WHERE id = %s AND answered_at IS NULL RETURNING source, ref", (prompt_id,)
        ).fetchone()
        if p:
            conn.execute(
                "UPDATE drill SET due = GREATEST(due, %s) WHERE source = %s AND ref = %s",
                (now().date() + timedelta(days=1), p["source"], p["ref"]),
            )


# --- pings and /pause ------------------------------------------------------------------------

def get_setting(key: str) -> str | None:
    with _conn() as conn:
        row = conn.execute("SELECT value FROM setting WHERE key = %s", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(key: str, value: str | None) -> None:
    with _conn() as conn:
        if value is None:
            conn.execute("DELETE FROM setting WHERE key = %s", (key,))
        else:
            conn.execute(
                "INSERT INTO setting (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (key, value),
            )


def ping_due(at: datetime, pings: list[time], last: datetime | None) -> datetime | None:
    """The latest ping time today that has passed, is under 30 min old, and was not sent yet."""
    passed = [datetime.combine(at.date(), t, at.tzinfo) for t in pings]
    passed = [p for p in passed if p <= at and at - p < SESSION_IDLE and (last is None or p > last)]
    return max(passed, default=None)


_DURATION = re.compile(r"^(\d+)\s*([mhd])$")
_UNITS = {"m": "minutes", "h": "hours", "d": "days"}


def parse_duration(text: str) -> timedelta | None:
    if m := _DURATION.match(text.strip().lower()):
        return timedelta(**{_UNITS[m[2]]: int(m[1])})
    return None
