"""Record the demo conversations (SPEC §7h) by driving the real bot handlers.

Runs in a one-off container of the bot's image (command in SPEC §7h): a scratch database seeded
with public pools only, its own MCP server without MbxRead, Anki unreachable, the real model.
Writes demo/conversations.json.
"""
import os

SCRATCH = os.environ["DATABASE_URL"].rsplit("/", 1)[0] + "/mbxchat_demo"
os.environ.update(
    DATABASE_URL=SCRATCH, MBXREAD_URL="", MCP_PORT="8016", MCP_URL="http://127.0.0.1:8016/mcp",
    ANKI_URL="http://127.0.0.1:1", TELEGRAM_ALLOWED_USER_ID="1", PRACTICE_TZ="Asia/Seoul",
)

import asyncio  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import socket  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from telegram import Update  # noqa: E402
from telegram.request import BaseRequest  # noqa: E402

from mbxchat import bot, capture, db, importer, practice  # noqa: E402

OUT = Path(__file__).with_name("conversations.json")
USER = {"id": 1, "is_bot": False, "first_name": "Learner"}
BOT = {"id": 2, "is_bot": True, "first_name": "MbxChat", "username": "mbxchat_demo_bot"}
CHAT = {"id": 1, "type": "private"}


class Recorder(BaseRequest):
    """Answers the Bot API locally and keeps every visible change as an event."""

    def __init__(self):
        self.messages: dict[int, dict] = {}
        self.events: list[dict] = []
        self.next_id = 1
        self.t0 = time.monotonic()

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    @property
    def read_timeout(self):
        return 5

    def event(self, **e):
        self.events.append({"t": round(time.monotonic() - self.t0, 2)} | e)

    def store(self, text, sender, reply_to=None, markup=None) -> dict:
        m = {"message_id": self.next_id, "date": int(time.time()), "chat": CHAT, "from": sender, "text": text}
        if reply_to:
            m["reply_to_message"] = self.messages[reply_to]
        if markup:
            m["reply_markup"] = markup
        self.messages[self.next_id] = m
        self.next_id += 1
        return m

    async def do_request(self, url, method, request_data=None, **kw):
        name, p = url.rsplit("/", 1)[1], (request_data.parameters if request_data else {})
        result = True
        if name == "getMe":
            result = BOT
        elif name == "sendMessage":
            reply = (p.get("reply_parameters") or {}).get("message_id")
            m = self.store(p["text"], BOT, reply, p.get("reply_markup"))
            self.event(op="send", id=m["message_id"], html=p["text"], reply_to=reply, buttons=_labels(p))
            result = m
        elif name == "editMessageText":
            m = self.messages[p["message_id"]]
            m["text"] = p["text"]
            m.pop("reply_markup", None)
            if p.get("reply_markup"):
                m["reply_markup"] = p["reply_markup"]
            self.event(op="edit", id=m["message_id"], html=p["text"], buttons=_labels(p))
            result = m
        elif name == "editMessageReplyMarkup":
            self.event(op="edit_buttons", id=p["message_id"], buttons=_labels(p))
        elif name == "deleteMessage":
            self.event(op="delete", id=p["message_id"])
        elif name == "setMessageReaction":
            self.event(op="react", id=p["message_id"], emoji=p["reaction"][0]["emoji"])
        elif name == "answerCallbackQuery" and p.get("text"):
            self.event(op="toast", text=p["text"])
        elif name not in ("sendChatAction", "answerCallbackQuery"):
            raise RuntimeError(f"recorder does not fake {name}")
        return 200, json.dumps({"ok": True, "result": result}).encode()


def _labels(p) -> list[list[str]]:
    markup = p.get("reply_markup") or {}
    return [[b["text"] for b in row] for row in markup.get("inline_keyboard", [])]


class Driver:
    def __init__(self, app, rec: Recorder):
        self.app, self.rec, self.update_id = app, rec, 0

    async def _process(self, data: dict):
        self.update_id += 1
        await self.app.process_update(Update.de_json({"update_id": self.update_id} | data, self.app.bot))

    async def say(self, text: str):
        m = self.rec.store(text, USER)
        self.rec.event(op="user", id=m["message_id"], text=text)
        if text.startswith("/"):
            m["entities"] = [{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}]
        await self._process({"message": m})

    def last_message(self, needle: str = "") -> dict:
        return next(m for m in reversed(self.rec.messages.values()) if m["from"]["is_bot"] and needle in m["text"])

    def last_with(self, label: str) -> dict | None:
        for m in reversed(self.rec.messages.values()):
            for row in (m.get("reply_markup") or {}).get("inline_keyboard", []):
                for b in row:
                    if b["text"].startswith(label):
                        return m | {"_button": b}
        return None

    async def tap(self, label: str):
        m = self.last_with(label)
        if m is None:
            raise RuntimeError(f"no button {label!r}")
        b = m.pop("_button")
        self.rec.event(op="tap", id=m["message_id"], label=b["text"])
        await self._process({"callback_query": {
            "id": str(self.update_id), "from": USER, "chat_instance": "demo", "data": b["callback_data"], "message": m,
        }})


class LearnerAnswer(BaseModel):
    korean: str = Field(description="One Korean sentence only: no emoji, romanization, English or comments")


def learner_answer(task: str) -> str:
    return capture.ask(LearnerAnswer, "You write sample answers for a Korean learning app demo.",
                       f"Task: {task}\nWrite it correctly and naturally, polite 해요체.").korean


def plant_slip(korean: str) -> tuple[str, str]:
    """Drop the first object particle (else the subject particle), the way a beginner does."""
    toks = capture._kiwi().tokenize(korean)
    for tag in ("JKO", "JKS"):
        if t := next((t for t in toks if t.tag == tag), None):
            return korean[:t.start] + korean[t.end:], f"dropped {t.form}"
    return korean, ""


def scratch_db():
    admin = SCRATCH.rsplit("/", 1)[0] + "/postgres"
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute("DROP DATABASE IF EXISTS mbxchat_demo WITH (FORCE)")
        conn.execute("CREATE DATABASE mbxchat_demo")
    db.init()
    for line in importer.import_public():
        print("content", line)
    # Demo history written for the purpose: two past slips on 을/를, so practice has a weak point.
    with psycopg.connect(SCRATCH, autocommit=True, row_factory=dict_row) as conn:
        g = practice._grammar_forms(conn)["를"]
        ko = conn.execute("SELECT ko FROM item WHERE id = %s", (g,)).fetchone()["ko"]
        s = conn.execute("INSERT INTO session (started_at, last_at, closed_at) VALUES "
                         "(now() - interval '5 days', now() - interval '5 days', now() - interval '5 days') "
                         "RETURNING id").fetchone()["id"]
        for days, answer, wrong, fix in ((5, "저는 커피 마셔요.", "커피", "커피를"), (4, "책 읽어요.", "책", "책을")):
            p = conn.execute(
                "INSERT INTO prompt (session_id, source, ref, kind, en, grammar_id, sent_at, answered_at, answer, grade) "
                "VALUES (%s, 'item', %s, 'grammar', %s, %s, now() - make_interval(days => %s), "
                "now() - make_interval(days => %s), %s, '{\"verdict\": \"minor\"}') RETURNING id",
                (s, g, ko, g, days, days, answer),
            ).fetchone()["id"]
            conn.execute("INSERT INTO mistake (prompt_id, category, wrong, fix, grammar_id, created_at) "
                         "VALUES (%s, 'particle', %s, %s, %s, now() - make_interval(days => %s))",
                         (p, wrong, fix, g, days))


def wait_port(port: int, timeout: float = 30):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            socket.create_connection(("127.0.0.1", port), 1).close()
            return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError(f"nothing listening on {port}")


PRAISE = re.compile(r"\b(is|are) (perfectly |completely |entirely |grammatically )?(correct|natural|perfect)\b"
                    r"|both are (good|fine|correct)|well done|perfectly (natural|correct)", re.I)
VERDICTS = {"✅ Correct": "correct", "🟡 Nearly": "minor", "❌ Not quite": "wrong"}


def check(events: list[dict], kind: str, slip: bool | None = None) -> list[str]:
    """Reasons to drop a recorded run; empty means keep."""
    sent = [e["html"] for e in events if e["op"] in ("send", "edit")]
    flags = [f"failure: {h[:60]}" for h in sent if "⚠️" in h or "failed" in h.lower()]
    if kind == "word" and not any("📖 krdict:" in h for h in sent):
        flags.append("word not found in krdict")
    if kind == "sentence" and not any("<b>Chunk " in h for h in sent):
        flags.append("no chunk to review")
    if kind == "practice":
        graded = [h for h in sent if any(h.startswith(f"<b>{v}") for v in VERDICTS)]
        if not graded:
            return flags + ["answer was not graded"]
        verdict = next(VERDICTS[v] for v in VERDICTS if graded[0].startswith(f"<b>{v}"))
        if slip and verdict == "correct":
            flags.append("planted slip graded correct")
        if not slip and verdict != "correct":
            flags.append(f"clean answer graded {verdict}")
        note = re.sub(r"<[^>]+>", "", graded[0].split(chr(10), 1)[-1])
        if verdict != "correct" and PRAISE.search(note.split("Model answer:")[-1]):
            flags.append("note praises an answer not marked correct")
    return flags


async def record(app, run) -> tuple[str, list[dict], list[str]]:
    rec = Recorder()
    app.bot._request = (rec, rec)  # ponytail: private slot; ApplicationBuilder.request() would also need get_updates
    label, flags = await run(Driver(app, rec))
    return label, rec.events, flags + check(rec.events, *run.check)


def item(kind: str, **check_args):
    def wrap(fn):
        fn.check = (kind, *check_args.values())
        return fn
    return wrap


def grammar_run(form: str):
    @item("grammar")
    async def run(d: Driver):
        await d.say(f"/grammar {form}")
        rows = d.last_message().get("reply_markup", {}).get("inline_keyboard", [])
        if rows and " · L" in rows[0][0]["text"]:
            await d.tap(rows[0][0]["text"])
        return f"/grammar {form}", []
    return run


def capture_run(text: str, kind: str):
    @item(kind)
    async def run(d: Driver):
        with psycopg.connect(SCRATCH, autocommit=True) as conn:  # each run shows only its own Anki queue
            conn.execute("DELETE FROM chunk; DELETE FROM word_card")
        await d.say(text)
        await d.tap("➕ Capture")
        while d.last_with("✅ Approve"):
            await d.tap("✅ Approve")
        return text, []
    return run


def practice_run(slip: bool):
    @item("practice", slip=slip)
    async def run(d: Driver):
        practice.close_session()
        await d.say("/practice")
        p = practice.waiting(practice.current_session())
        answer, planted = learner_answer(practice.task(p)), ""
        if slip:
            answer, planted = plant_slip(answer)
        print(f"   {answer} ({planted or 'clean'})")
        flags = ["no particle to drop"] if slip and not planted else []
        if re.search(r"[A-Za-z()]|[^\w\s.,?!~…-]", answer):
            flags.append("learner answer is not one clean Korean sentence")
        await d.say(answer)
        graded = max(i for i, e in enumerate(d.rec.events) if e["op"] == "edit")
        del d.rec.events[graded + 1:]  # the run ends at the grade; the next prompt is not shown
        task = practice.task(p).removeprefix("Say this in Korean: ")
        return task.replace("Write one Korean sentence using the grammar ", "Grammar: "), flags
    return run


KRDICT = '<a href="https://krdict.korean.go.kr/eng">krdict</a>'
ANKI = "Approved cards go into Anki if it is open, or queue until it is."
NOTES_GRAMMAR = [
    "The grammar list (336 points, levels 1-6) is from NIKL's international Korean curriculum, under KOGL "
    'type 1. <a href="https://www.korean.go.kr/front/reportData/reportDataView.do?mn_id=45&report_seq=932">Source</a>',
    "The explanations are original writing, served without a model call. Attribution in "
    '<a href="https://github.com/miobix/MbxChat-public/blob/main/docs/DATA.md">DATA.md</a>.',
]
NOTES_SENTENCE = [
    "Chunks are the reusable pieces of a sentence: a collocation, a set expression or a grammar pattern in "
    "use. They make better flashcards than whole sentences.",
    f"The capture agent drafts a casual and a polite version and checks rare words against {KRDICT}, the "
    "learner dictionary of the National Institute of Korean Language. A critic model reviews both, then up "
    "to three chunks are picked. You approve, edit or skip each one.",
    "On the live app, the critic also gets example sentences retrieved from the companion MbxRead library "
    "(hybrid search), as evidence of real usage.",
    ANKI,
]
NOTES_WORD = [
    f"Meanings and examples are checked against {KRDICT}, the learner dictionary of the National Institute "
    "of Korean Language.",
    ANKI,
]
NOTES_PRACTICE = [
    "The learner answers here were written by the model.",
    "In half of them the recorder dropped a particle (을/를 or 이/가) to plant a beginner slip for the grader "
    "to catch.",
    "Two earlier 을/를 slips were seeded, so practice has a weak point to steer at (🎯). Missed points come "
    "back sooner.",
]


GROUPS = [
    ("Grammar lookup", NOTES_GRAMMAR,
     [grammar_run(f) for f in ("는데", "아서", "거든요", "(으)니까", "(으)면서", "기로 하다")]),
    ("Capture a sentence",
     NOTES_SENTENCE,
     [capture_run(t, "sentence") for t in (
         "can we push the meeting to next week? // to my team lead",
         "I'm running ten minutes late // texting a friend",
         "could you send me that file again? // to a coworker",
         "let's grab lunch tomorrow // to a friend",
         "thank you for waiting // to a customer",
         "I haven't decided yet",
         "is this seat taken?",
         "I'll think about it and get back to you // to a client",
         "it was nice meeting you // after a first meeting",
         "do you want to get coffee? // to a friend",
         "sorry, I didn't catch that // on the phone",
         "the printer isn't working again // to a coworker",
     )]),
    ("Capture a word", NOTES_WORD,
     [capture_run(w, "word") for w in ("postpone", "umbrella", "receipt", "colleague", "to be tired", "schedule")]),
    ("Practice and memory",
     NOTES_PRACTICE,
     [practice_run(slip) for slip in [True, False] * 7]),
]


async def main(only: list[str]):
    app = bot.build_app("2:demo", capture.build(db.checkpointer()))
    for handlers in app.handlers.values():
        for h in handlers:
            h.block = True  # background handlers would race the next scripted step
    app.bot._request = (Recorder(), Recorder())
    await app.initialize()
    old = json.loads(OUT.read_text(encoding="utf-8")) if only and OUT.exists() else {"groups": [], "dropped": []}
    groups, dropped = [], [d for d in old["dropped"] if not any(d["group"].startswith(o) for o in only)]
    for title, note, runs in GROUPS:
        if only and not any(title.startswith(o) for o in only):
            groups.append(next(g for g in old["groups"] if g["title"] == title))
            continue
        items = []
        for run in runs:
            label, events, flags = await record(app, run)
            print(f"{title} | {label} | {len(events)} events | {', '.join(flags) or 'ok'}")
            if flags:
                dropped.append({"group": title, "label": label, "flags": flags})
            else:
                items.append({"label": label, "events": events})
        groups.append({"title": title, "note": note, "items": items})
    await app.shutdown()
    kept = sum(len(g["items"]) for g in groups)
    OUT.write_text(json.dumps({
        "recorded": time.strftime("%Y-%m-%d"), "model": os.getenv("CAPTURE_MODEL", "gemma4:e4b"),
        "kept": kept, "dropped": dropped, "groups": groups,
    }, ensure_ascii=False, indent=1) + chr(10), encoding="utf-8")
    print(f"wrote {OUT}: {kept} kept, {len(dropped)} dropped")


def drop(label: str, reason: str):
    """After a human read: move a kept run to the dropped list, with the reason."""
    data = json.loads(OUT.read_text(encoding="utf-8"))
    for g in data["groups"]:
        for it in g["items"]:
            if it["label"] == label:
                g["items"].remove(it)
                data["dropped"].append({"group": g["title"], "label": label, "flags": [f"review: {reason}"]})
                data["kept"] -= 1
                OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + chr(10), encoding="utf-8")
                return
    raise SystemExit(f"no kept run labelled {label!r}")


if __name__ == "__main__" and sys.argv[1:2] == ["drop"]:
    drop(*sys.argv[2:4])
elif __name__ == "__main__":
    scratch_db()
    mcp = subprocess.Popen([sys.executable, "-m", "mbxchat.mcp_server"])
    try:
        wait_port(8016)
        asyncio.run(main(sys.argv[1:]))
    finally:
        mcp.terminate()
