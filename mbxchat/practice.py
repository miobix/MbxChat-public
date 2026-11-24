"""Practice loop (SPEC §7d, §7f): prompts, an LLM grader, a resurfacing ladder, learner memory, pings."""
import logging
import re
import unicodedata
from datetime import date, datetime, time, timedelta
from difflib import SequenceMatcher
from typing import Literal
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from mbxchat import config, metrics
from mbxchat.capture import _kiwi, ask

log = logging.getLogger(__name__)
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


# --- choosing a prompt (SPEC §7d, §7f) -------------------------------------------------------
# Captures are never prompted back (they are in Anki). The ladder lives on grammar points, so a
# drill comes back as a new sentence; pool sentences are used once, generated ones are one-off.

_SEEN_TODAY = "EXISTS (SELECT 1 FROM prompt p WHERE p.grammar_id = {g} AND p.sent_at > now() - interval '1 day')"
_IN_SESSION = "EXISTS (SELECT 1 FROM prompt p WHERE p.grammar_id = {g} AND p.session_id = %(s)s)"
_FREE = f"NOT {_SEEN_TODAY} AND NOT {_IN_SESSION}"


class Generated(BaseModel):
    en: str = Field(description="One short everyday English sentence to translate into Korean")
    formality: Literal["friend", "coworker_chat", "polite"]


GENERATE_SYSTEM = (
    "You write translation drills for a Korean learner. Write one short, everyday English sentence whose "
    "natural Korean translation needs the given grammar point and the given word. Never write Korean."
)


def _due_grammar(conn, s: int, today: date) -> int | None:
    row = conn.execute(
        "SELECT d.ref FROM drill d JOIN item i ON i.id = d.ref AND i.kind = 'grammar' "
        f"WHERE d.source = 'item' AND d.due <= %(t)s AND {_FREE.format(g='d.ref')} ORDER BY d.due, random() LIMIT 1",
        {"s": s, "t": today},
    ).fetchone()
    return row["ref"] if row else None


def _new_grammar(conn, s: int) -> int | None:
    row = conn.execute(
        "SELECT id FROM item i WHERE kind = 'grammar' "
        "AND NOT EXISTS (SELECT 1 FROM drill d WHERE d.source = 'item' AND d.ref = i.id) "
        f"AND NOT EXISTS (SELECT 1 FROM known_grammar k WHERE k.item_id = i.id) AND {_FREE.format(g='i.id')} "
        "ORDER BY level > %(m)s, random() LIMIT 1", {"s": s, "m": GRAMMAR_MAX_LEVEL},
    ).fetchone()
    return row["id"] if row else None


def _any_grammar(conn, s: int) -> int:
    return conn.execute(
        f"SELECT id FROM item i WHERE kind = 'grammar' ORDER BY {_IN_SESSION.format(g='i.id')}, random() LIMIT 1", {"s": s}
    ).fetchone()["id"]


def _term(conn) -> str | None:
    w = conn.execute(
        "SELECT ko, en FROM item WHERE kind = 'term' AND data->>'status' = 'learning' ORDER BY random() LIMIT 1"
    ).fetchone()
    return f"{w['ko']} ({w['en']})" if w else None


def _grammar_prompt(conn, g: int, word: str | None = None) -> dict:
    ko = conn.execute("SELECT ko FROM item WHERE id = %s", (g,)).fetchone()["ko"]
    return {"source": "item", "ref": g, "kind": "grammar", "en": ko, "grammar_id": g, "word": word or _term(conn)}


def _translate_prompt(conn, s: int) -> dict | None:
    """A pool sentence never prompted before; when they run out, a generated one around a new grammar point."""
    row = conn.execute(
        "SELECT i.id, i.ko, i.en, i.data, g.id AS grammar_id FROM item i "
        "LEFT JOIN item g ON g.kind = 'grammar' AND g.key = i.data->>'grammar_id' WHERE i.kind = 'sentence' "
        "AND NOT EXISTS (SELECT 1 FROM prompt p WHERE p.source = 'item' AND p.ref = i.id) "
        f"AND (g.id IS NULL OR {_FREE.format(g='g.id')}) ORDER BY i.level, random() LIMIT 1", {"s": s}
    ).fetchone()
    if row:
        return {"source": "item", "ref": row["id"], "kind": "translate", "en": row["en"], "reference": row["ko"],
                "register": row["data"].get("register", ""), "grammar_id": row["grammar_id"]}
    if (g := _new_grammar(conn, s)) is None:
        return None
    p = _grammar_prompt(conn, g)
    try:
        gen = ask(Generated, GENERATE_SYSTEM, f"Grammar point: {p['en']}\nWord: {p['word'] or 'any'}")
        return p | {"kind": "translate", "en": gen.en, "register": gen.formality, "word": None}
    except Exception:
        log.warning("generating a translate prompt failed; serving the grammar point instead", exc_info=True)
        return p


def weak_points(conn) -> list[dict]:
    """Same grammar point (or same fix, without one) at least twice in 30 days, not used cleanly since (SPEC §7f)."""
    rows = conn.execute(
        "SELECT category, (array_agg(fix ORDER BY created_at DESC))[1] AS fix, grammar_id, count(*) AS n, "
        "max(created_at) AS last, (array_agg(wrong ORDER BY created_at DESC))[1] AS wrong FROM mistake "
        "WHERE category <> 'other' AND created_at > now() - interval '30 days' "
        "GROUP BY category, grammar_id, CASE WHEN grammar_id IS NULL THEN fix END "
        "HAVING count(*) >= 2 ORDER BY count(*) DESC, max(created_at) DESC"
    ).fetchall()
    # ponytail: "clean since" = a later correct answer on the grammar point, or the word written right.
    return [r for r in rows if not conn.execute(
        "SELECT 1 FROM prompt WHERE answered_at > %(last)s AND ("
        "(%(g)s::bigint IS NOT NULL AND grammar_id = %(g)s AND grade->>'verdict' = 'correct') "
        "OR (%(cat)s = 'spelling' AND strpos(answer, %(fix)s) > 0))",
        {"last": r["last"], "g": r["grammar_id"], "cat": r["category"], "fix": r["fix"]},
    ).fetchone()]


def weak() -> list[dict]:
    with _conn() as conn:
        return weak_points(conn)


def _steered(conn, s: int, today: date) -> dict | None:
    recent = "p.sent_at > now() - interval '3 days'"
    for w in weak_points(conn):
        focus = f"🎯 You missed {w['fix']} {w['n']} times"
        if w["grammar_id"] and not conn.execute(
            f"SELECT 1 FROM prompt p WHERE p.grammar_id = %s AND ({recent} OR p.session_id = %s)", (w["grammar_id"], s)
        ).fetchone():
            return _grammar_prompt(conn, w["grammar_id"]) | {"focus": focus}
        if w["category"] == "spelling" and not conn.execute(
            f"SELECT 1 FROM prompt p WHERE p.word = %s AND {recent}", (w["fix"],)
        ).fetchone():
            g = _due_grammar(conn, s, today) or _new_grammar(conn, s) or _any_grammar(conn, s)
            return _grammar_prompt(conn, g, w["fix"]) | {"focus": focus}
    return None


def _pick(conn, s: int, today: date) -> dict:
    last = conn.execute("SELECT pick, kind FROM prompt ORDER BY id DESC LIMIT 2").fetchall()
    if "weak" not in [r["pick"] for r in last] and (p := _steered(conn, s, today)):
        return p | {"pick": "weak"}
    if (not last or last[0]["pick"] != "due") and (g := _due_grammar(conn, s, today)):
        return _grammar_prompt(conn, g) | {"pick": "due"}
    finders = [lambda: _translate_prompt(conn, s), lambda: (g := _new_grammar(conn, s)) and _grammar_prompt(conn, g)]
    if not last or last[0]["kind"] != "grammar":
        finders.reverse()
    for find in finders:
        if p := find():
            return p
    return _grammar_prompt(conn, _due_grammar(conn, s, today) or _any_grammar(conn, s))


_COLUMNS = ("session_id", "source", "ref", "kind", "en", "situation", "register", "reference", "grammar_id", "word",
            "pick", "focus")
_DEFAULTS = {"situation": "", "register": "", "reference": None, "grammar_id": None, "word": None, "pick": "new", "focus": None}


def next_prompt(session_id: int) -> dict:
    with _conn() as conn:
        p = _DEFAULTS | _pick(conn, session_id, now().date()) | {"session_id": session_id}
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
        metrics.GRADES.labels("reference").inc()
        return Grade(issues=[], corrected=answer, model_answer=p["reference"], note="", verdict="correct")
    lines = [f"Task: {task(p)}"]
    lines += [f"Situation: {p['situation']}"] * bool(p["situation"])
    lines += [f"Register: {p['register']}"] * bool(p["register"])
    lines += [f"Reference answer: {p['reference']}"] * bool(p["reference"])
    lines.append(f"Learner's answer: {answer}")
    if p.get("hint"):
        lines.append(f"A spelling checker suggests: {p['hint']} (it can be wrong, and misses many errors)")
    metrics.GRADES.labels("llm").inc()
    g = ask(Grade, GRADER_SYSTEM, "\n".join(lines), model or config.GRADER_MODEL)
    g.issues = [i for i in g.issues if "→" in i]
    if g.verdict == "correct" and (g.issues or bare(g.corrected) != bare(answer)):
        g.verdict = "minor"  # gemma sometimes fixes the sentence and still says correct
    return g


def bare(s: str) -> str:
    return re.sub(r"[\s.?!,]", "", s)


# --- learner memory (SPEC §7f) ------------------------------------------------------------------

def _surface(text: str, toks) -> str:
    return text[toks[0].start:toks[-1].end] if toks else ""


def tag(answer: str, corrected: str) -> list[tuple[str, str, str, str]]:
    """(category, wrong, fix, fix morphemes) per difference between the answer and its correction."""
    out = []
    aw, cw = re.findall(r"[^\s.?!,]+", answer), re.findall(r"[^\s.?!,]+", corrected)
    for op, i1, i2, j1, j2 in SequenceMatcher(None, aw, cw, autojunk=False).get_opcodes():
        if op == "replace" and "".join(aw[i1:i2]) == "".join(cw[j1:j2]):
            out.append(("spacing", " ".join(aw[i1:i2]), " ".join(cw[j1:j2]), ""))
    ta = [t for t in _kiwi().tokenize(answer) if not t.tag.startswith("S")]
    tc = [t for t in _kiwi().tokenize(corrected) if not t.tag.startswith("S")]
    sm = SequenceMatcher(None, [t.form for t in ta], [t.form for t in tc], autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        a, c = ta[i1:i2], tc[j1:j2]
        wrong, fix = _surface(answer, a), _surface(corrected, c)
        if op == "equal" or bare(wrong) == bare(fix):
            continue
        tags = {t.tag[0] for t in c or a}  # judged on the fix, so a misspelt particle (한태 → 에게) still counts
        if tags <= {"J"} and len(bare(wrong)) <= 2:
            category = "particle"
        elif tags <= {"E"} and len(bare(wrong)) <= 3:
            category = "ending"
        elif wrong and fix and abs(len(wrong) - len(fix)) <= 1 and SequenceMatcher(
            None, unicodedata.normalize("NFD", wrong), unicodedata.normalize("NFD", fix)
        ).ratio() >= 0.6:
            category = "spelling"
        else:
            category = "other"
        out.append((category, wrong, fix, "".join(t.form for t in c)))
    return out


def _grammar_forms(conn) -> dict[str, int]:
    """NIKL form and its related variants, without hyphens and sense digits ('-던데2' → '던데') → grammar item
    id. A main form beats a variant, a lower level beats a higher one."""
    rows = conn.execute(
        "SELECT id, data->>'form' AS form, data->>'related' AS related FROM item WHERE kind = 'grammar' ORDER BY level, id"
    ).fetchall()
    forms: dict[str, int] = {}
    for key in ("form", "related"):
        for r in rows:
            for f in (r[key] or "").split(","):
                forms.setdefault(re.sub(r"[-\d\s]", "", f), r["id"])
    forms.pop("", None)
    return forms


# --- routing free text in a session (SPEC §7e) --------------------------------------------------

class Route(BaseModel):
    kind: Literal["answer", "capture", "question"] = Field(
        description="answer: an attempt at the task. capture: they want to know how to say something "
        "else (how do I say…, the word for…). question: they ask about Korean, a word, a grammar point or the task"
    )


class Explanation(BaseModel):
    text: str = Field(description="The answer in English, with short Korean examples where useful; at most 120 words")


ROUTE_SYSTEM = "A learner is doing a Korean writing drill. Classify their message against the current task."
EXPLAIN_SYSTEM = (
    "You are a concise Korean tutor. Answer the learner's question directly, at their level, in English, "
    "with one or two short Korean examples when they help. Do not give away the answer to the current task."
)


def route(p: dict, text: str) -> str:
    """'answer' / 'capture' / 'question'. Mostly-Hangul text is an answer with no model call (captures
    are English phrases), except a single Korean word: a word heard somewhere, to capture."""
    letters = [c for c in text if c.isalpha()]
    if letters and sum("가" <= c <= "힣" for c in letters) / len(letters) >= 0.5:
        return "capture" if len(text.split()) == 1 else "answer"
    return ask(Route, ROUTE_SYSTEM, f"Current task: {task(p)}\nMessage: {text}").kind


def explain(p: dict, question: str) -> str:
    return ask(Explanation, EXPLAIN_SYSTEM, f"Current task: {task(p)}\nQuestion: {question}").text


def schedule(step: int, verdict: str, today: date) -> tuple[int, date]:
    """(new step, due date): correct climbs the ladder, minor holds, wrong restarts at the first rung."""
    if verdict == "wrong":
        return 0, today + timedelta(days=LADDER[0])
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
        if p["grammar_id"]:
            row = conn.execute("SELECT step FROM drill WHERE source = 'item' AND ref = %s", (p["grammar_id"],)).fetchone()
            step, due = schedule(row["step"] if row else 0, g.verdict, now().date())
            conn.execute(
                "INSERT INTO drill (source, ref, step, due, last_verdict, times) VALUES ('item', %s, %s, %s, %s, 1) "
                "ON CONFLICT (source, ref) DO UPDATE SET step = EXCLUDED.step, due = EXCLUDED.due, "
                "last_verdict = EXCLUDED.last_verdict, times = drill.times + 1",
                (p["grammar_id"], step, due, g.verdict),
            )
        try:
            forms, tags = _grammar_forms(conn), tag(answer, g.corrected)
        except Exception:  # memory is a bonus; it must never cost the grade
            log.warning("tagging mistakes for prompt %s failed", p["id"], exc_info=True)
            forms, tags = {}, []
        for category, wrong, fix, form in tags:
            conn.execute(
                "INSERT INTO mistake (prompt_id, category, wrong, fix, grammar_id) VALUES (%s, %s, %s, %s, %s)",
                (p["id"], category, wrong, fix, forms.get(form) if category in ("particle", "ending") else None),
            )
        if p["session_id"]:
            conn.execute("UPDATE session SET last_at = now() WHERE id = %s", (p["session_id"],))


def skip(prompt_id: int) -> None:
    with _conn() as conn:
        p = conn.execute(
            "UPDATE prompt SET skipped = true WHERE id = %s AND answered_at IS NULL RETURNING grammar_id", (prompt_id,)
        ).fetchone()
        if p and p["grammar_id"]:
            conn.execute(
                "UPDATE drill SET due = GREATEST(due, %s) WHERE source = 'item' AND ref = %s",
                (now().date() + timedelta(days=1), p["grammar_id"]),
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
