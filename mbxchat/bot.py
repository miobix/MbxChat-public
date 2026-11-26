import asyncio
import logging
from datetime import datetime

from langgraph.types import Command
from telegram import BotCommandScopeChat, Update
from telegram.constants import ParseMode
from telegram.error import NetworkError
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)

from mbxchat import anki, capture, config, grammar, metrics, practice
from mbxchat.ui import Progress, copy_button, correction, esc, fold, keyboard, spoiler, word_diff

log = logging.getLogger(__name__)

# The / menu is built from this list, so it can't drift from the handlers registered below.
COMMANDS = [
    ("practice", "Start practising"),
    ("stop", "End the practice session"),
    ("pause", "Mute pings for a while: /pause 3h"),
    ("help", "What I can do"),
    ("grammar", "Explain a grammar point: /grammar 는데"),
    ("queue", "Cards waiting for Anki"),
    ("weak", "Mistakes you keep making"),
    ("demo", "Preview of the chat UI"),
]

HELP = (
    "<b>MbxChat</b>: practise writing Korean.\n\n"
    "Send me any text and I'll offer to capture it (\"how do I say…\"). Add the situation after "
    "<code>//</code>: <i>can we push the meeting // to my boss</i>.\n\n"
    + "\n".join(f"/{name}  {desc}" for name, desc in COMMANDS)
    + "\n\nComing next: /stats."
)


async def gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None or user.id != config.TELEGRAM_ALLOWED_USER_ID:
        log.info("ignored update from user %s", user.id if user else None)
        raise ApplicationHandlerStop


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(HELP)


async def free_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if editing := context.chat_data.pop("editing", None):
        await _finish_edit(update, context, *editing)
        return
    session = await asyncio.to_thread(practice.current_session)
    if session and (p := await asyncio.to_thread(practice.waiting, session)):
        await _route(context, update.message, p)
        return
    rows = [[("➕ Capture", "cap:yes"), ("✖ No", "cap:no")]]
    if not session and (late := await asyncio.to_thread(practice.waiting, None)):
        rows.append([("✍️ It's my answer to the last prompt", f"late:{late['id']}")])
    await update.message.reply_html("Capture this?", reply_markup=keyboard(*rows), do_quote=True)


async def on_capture(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query.data == "cap:no":
        await query.answer()
        await query.message.delete()
        return
    original = query.message.reply_to_message
    text, situation = capture.split_situation(original.text if original and original.text else "")
    await query.answer()
    shown = f"➕ <i>{esc(text)}</i>" + (f"\n📍 {esc(situation)}" if situation else "")
    await query.edit_message_text(shown, parse_mode=ParseMode.HTML)
    await _capture(context, query.message.chat_id, text, situation)


async def _capture(context, chat_id: int, text: str, situation: str = "") -> None:
    capture_id = await asyncio.to_thread(capture.new_capture, text, situation)
    progress = Progress(context.bot, chat_id)
    await progress.start("Drafting…")
    try:
        await _run(context, chat_id, capture_id, {"text": text, "situation": situation}, progress)
    except Exception as e:
        log.exception("capture %s failed", capture_id)
        await progress.done(f"⚠️ Capture failed: <code>{esc(type(e).__name__)}: {esc(str(e)[:200])}</code>")


# Label shown once the key node has finished, i.e. what runs next.
NEXT_STEP = {
    "agent": "Checking words in krdict and your library…",
    "draft": "Checking words in krdict and your library…",
    "lookup": "Critic reviewing…",
    "critic": "Picking chunks…",
}


async def _run(context, chat_id: int, capture_id: int, graph_input, progress: Progress | None = None):
    """Advance one capture's graph to its next interrupt or its end, then show where it stands."""
    graph = context.application.bot_data["graph"]
    cfg = {"configurable": {"thread_id": str(capture_id)}}
    steps = graph.stream(graph_input, cfg, stream_mode="updates")
    while (update := await asyncio.to_thread(next, steps, None)) is not None:
        for node in update:
            if progress and node in NEXT_STEP:
                await progress.step(NEXT_STEP[node])
    state = await asyncio.to_thread(graph.get_state, cfg)
    if progress:
        await progress.done(_summary(state.values))
    if state.interrupts and "word" in state.interrupts[0].value:
        await _send_word_card(context.bot, chat_id, capture_id, state.interrupts[0].value["word"])
    elif state.interrupts:
        await _send_card(context.bot, chat_id, capture_id, state.interrupts[0].value, len(state.values["chunks"]))
    elif progress is None and state.values.get("kind") == "word":
        if state.values.get("saved"):
            await context.bot.send_message(chat_id, await _word_to_anki(capture_id))
    elif progress is None:
        n = state.values.get("saved", 0)
        text = f"Done: {n} chunk{'' if n == 1 else 's'} saved."
        if n:
            text += " " + await _to_anki()
        await context.bot.send_message(chat_id, text)


async def _word_to_anki(capture_id: int) -> str:
    try:
        await asyncio.to_thread(anki.push)
    except anki.Closed:
        pass
    deck = config.ANKI_WORD_DECK
    return {
        "in": f"In Anki, deck {deck}.",
        "duplicate": f"Already in {deck}: nothing added.",
        "queued": "Anki is closed: the card is queued, sent once it opens.",
        "refused": "Anki refused the card: see /queue.",
    }[await asyncio.to_thread(anki.word_outcome, capture_id)]


async def _to_anki() -> str:
    try:
        await asyncio.to_thread(anki.push)
    except anki.Closed:
        n = len(await asyncio.to_thread(anki.queued))
        return f"Anki is closed: {n} card{'' if n == 1 else 's'} queued, sent once it opens."
    return "In Anki."


async def queue_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    status = await _to_anki()
    rows = await asyncio.to_thread(anki.queued)
    if not rows:
        await update.message.reply_html("Nothing waiting: every chunk is in Anki.")
        return
    lines = [f"• {esc(ko)}" + (f"  ⚠️ <i>{esc(err)}</i>" if err else "") for ko, err in rows]
    head = esc(status) if status.startswith("Anki is closed") else "Anki refused these:"
    await update.message.reply_html(head + "\n" + "\n".join(lines))


async def weak_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = await asyncio.to_thread(practice.weak)
    if not rows:
        await update.message.reply_html("No repeated mistakes in the last 30 days.")
        return
    lines = [f"• <b>{esc(r['fix'])}</b> ({r['category']}, {r['n']}×)" + (f": not <s>{esc(r['wrong'])}</s>" if r["wrong"] else "")
             for r in rows]
    await update.message.reply_html("Repeated in the last 30 days:\n" + "\n".join(lines))


async def forever(name: str, every: float, step) -> None:
    """Run step() every `every` seconds for good; a repeated error is logged once."""
    last = None
    while True:
        await asyncio.sleep(every)
        try:
            await step()
            last = None
        except Exception as e:
            if repr(e) != last:
                log.exception("%s failed", name)
            last = repr(e)


async def anki_step(app: Application) -> None:
    """Send queued chunks; quiet while Anki is closed."""
    try:
        n = await asyncio.to_thread(anki.push)
    except anki.Closed:
        return
    if n:
        await app.bot.send_message(
            config.TELEGRAM_ALLOWED_USER_ID, f"📇 {n} queued card{'' if n == 1 else 's'} now in Anki."
        )


async def ping_step(app: Application) -> None:
    at = practice.now()
    last = await asyncio.to_thread(practice.get_setting, "last_ping")
    due = practice.ping_due(at, config.PRACTICE_PINGS, datetime.fromisoformat(last) if last else None)
    if due is None:
        return
    await asyncio.to_thread(practice.set_setting, "last_ping", due.isoformat())
    paused = await asyncio.to_thread(practice.get_setting, "paused_until")
    if paused and datetime.fromisoformat(paused) > at or await asyncio.to_thread(practice.current_session):
        return
    session = await asyncio.to_thread(practice.open_session)
    await _send_prompt(app.bot, config.TELEGRAM_ALLOWED_USER_ID, session, "🔔 Practice time.\n\n")


# --- practice ------------------------------------------------------------------------------

VERDICT = {"correct": "✅ Correct", "minor": "🟡 Nearly", "wrong": "❌ Not quite"}


def _prompt_html(p: dict) -> str:
    focus = f"<i>{esc(p['focus'])}</i>\n" if p.get("focus") else ""
    if p["kind"] == "grammar":
        text = f"{focus}✍️ Write a sentence with <b>{esc(p['en'])}</b>"
        return text + (f" using <b>{esc(p['word'])}</b>" if p["word"] else "")
    lines = [f"{focus}✍️ <b>In Korean:</b> {esc(p['en'])}"]
    lines += [f"📍 {esc(p['situation'])}"] * bool(p["situation"])
    lines += [f"<i>{esc(p['register'].replace('_', ' '))}</i>"] * bool(p["register"])
    return "\n".join(lines)


async def _send_prompt(bot, chat_id: int, session: int, lead: str = "") -> None:
    p = await asyncio.to_thread(practice.next_prompt, session)
    key = f"pr:{p['id']}"
    row = [("⏭ Skip", f"{key}:sk"), ("⏹ Stop", f"{key}:st")]
    if p["grammar_id"]:
        row.insert(0, ("📖 Grammar", f"{key}:gr"))
    if p["kind"] == "grammar" and p["word"]:
        row.insert(1, (f"🔤 {_bare_word(p)}", f"{key}:wd"))
    await bot.send_message(chat_id, lead + _prompt_html(p), parse_mode=ParseMode.HTML, reply_markup=keyboard(row))


def _bare_word(p: dict) -> str:
    return p["word"].split(" (")[0]


def _graded(answer: str, g: practice.Grade) -> str:
    lines = [f"<b>{VERDICT[g.verdict]}</b>"]
    fixed = practice.bare(g.corrected) != practice.bare(answer)
    if fixed:
        lines.append(f"<b>Corrected:</b> {word_diff(answer, g.corrected)}")
    lines += [f"• {esc(i)}" for i in g.issues]
    if not fixed or practice.bare(g.corrected) != practice.bare(g.model_answer):
        lines.append(f"<b>Model answer:</b> {spoiler(esc(g.model_answer))}")
    if g.note:
        lines.append(fold(esc(g.note)) if len(g.note) > 120 else f"<i>{esc(g.note)}</i>")
    return "\n".join(lines)


async def _answer(context, message, p: dict, late: bool = False) -> None:
    answer = message.text.strip()
    progress = Progress(context.bot, message.chat_id)
    await progress.start("Grading…")
    try:
        g = await asyncio.to_thread(practice.grade, p, answer)
    except Exception as e:
        log.exception("grading prompt %s failed", p["id"])
        await progress.done(f"⚠️ Grading failed: <code>{esc(type(e).__name__)}: {esc(str(e)[:200])}</code>")
        return
    await asyncio.to_thread(practice.record, p, answer, g)
    await progress.done(_graded(answer, g))
    if g.verdict == "correct":
        await message.set_reaction("👍")
    session = await asyncio.to_thread(practice.open_session if late else practice.current_session)
    if session:
        await _send_prompt(context.bot, message.chat_id, session)


ROUTE_TEXT = {"capture": "Looks like something to capture.", "question": "Looks like a question."}


async def _route(context, message, p: dict) -> None:
    """Grade an answer; offer capture or an explanation for anything else, never run unasked."""
    try:
        kind = await asyncio.to_thread(practice.route, p, message.text)
    except Exception:
        log.exception("routing failed; grading as an answer")
        kind = "answer"
    if kind == "answer":
        await _answer(context, message, p)
        return
    # The guess only orders the buttons: a wrong one costs a tap, never a wrong action.
    capture_, ask = ("➕ Capture", "cap:yes"), ("💬 Answer it", f"ask:{p['id']}")
    first = [capture_, ask] if kind == "capture" else [ask, capture_]
    rows = [first, [("✍️ Grade it as my answer", f"late:{p['id']}")]]
    await message.reply_html(ROUTE_TEXT[kind], reply_markup=keyboard(*rows), do_quote=True)


async def on_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    p = await asyncio.to_thread(practice.get_prompt, int(query.data.removeprefix("ask:")))
    original = query.message.reply_to_message
    if p is None or original is None:
        await query.answer("Already handled")
        await query.message.delete()
        return
    await query.answer()
    await query.edit_message_text("💬 Thinking…")
    markup = None
    try:
        e = await asyncio.to_thread(practice.explain, p, original.text)
        text = e.text
        word = e.card(original.text)
        if word and len(f"sv:{word}".encode()) <= 64:  # Telegram's callback_data limit
            markup = keyboard([(f"➕ Save {word} as a card", f"sv:{word}")])
    except Exception as e:
        log.exception("explaining failed")
        text = f"⚠️ Could not answer: {type(e).__name__}: {str(e)[:200]}"
    waiting = "" if p["answered_at"] or p["skipped"] else "\n\n<i>The prompt above is still waiting for your answer.</i>"
    await query.edit_message_text(esc(text) + waiting, parse_mode=ParseMode.HTML, reply_markup=markup)


async def on_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(None)
    await _capture(context, query.message.chat_id, query.data.removeprefix("sv:"))


async def practice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = await asyncio.to_thread(practice.open_session)
    await _send_prompt(context.bot, update.message.chat_id, session)


async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    closed = await asyncio.to_thread(practice.close_session)
    await update.message.reply_html("Session ended." if closed else "No session open.")


async def pause_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    arg = " ".join(context.args or [])
    if arg.lower() in ("off", "0"):
        await asyncio.to_thread(practice.set_setting, "paused_until", None)
        await update.message.reply_html("Pings are back on.")
        return
    if span := practice.parse_duration(arg):
        until = practice.now() + span
        await asyncio.to_thread(practice.set_setting, "paused_until", until.isoformat())
        await update.message.reply_html(f"Pings muted until {until:%a %H:%M}. <code>/pause off</code> to undo.")
        return
    paused = await asyncio.to_thread(practice.get_setting, "paused_until")
    state = f"muted until {datetime.fromisoformat(paused):%a %H:%M}" if paused and datetime.fromisoformat(paused) > practice.now() else "on"
    times = ", ".join(f"{t:%H:%M}" for t in config.PRACTICE_PINGS)
    await update.message.reply_html(f"Pings ({times}) are {state}. Mute with <code>/pause 3h</code>, <code>30m</code> or <code>2d</code>.")


async def on_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    _, prompt_id, action = query.data.split(":")
    p = await asyncio.to_thread(practice.get_prompt, int(prompt_id))
    if action == "gr":
        point = await asyncio.to_thread(grammar.get, config.DATABASE_URL, p["grammar_id"])
        await query.answer()
        if point:
            await query.message.reply_html(grammar.explainer(point))
        return
    if action == "wd":
        await query.answer()
        await _capture(context, query.message.chat_id, _bare_word(p))
        return
    session = await asyncio.to_thread(practice.current_session)
    if p["answered_at"] or p["skipped"] or session != p["session_id"]:
        await query.answer("Already handled")
        await query.edit_message_reply_markup(None)
        return
    await query.answer()
    if action == "st":
        await asyncio.to_thread(practice.close_session)
        await query.edit_message_text(_prompt_html(p) + "\n\n⏹ Session ended.", parse_mode=ParseMode.HTML)
        return
    await asyncio.to_thread(practice.skip, p["id"])
    await query.edit_message_text(f"⏭ <s>{esc(p['en'])}</s>", parse_mode=ParseMode.HTML)
    await _send_prompt(context.bot, query.message.chat_id, session)


async def on_late(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    p = await asyncio.to_thread(practice.get_prompt, int(query.data.removeprefix("late:")))
    original = query.message.reply_to_message
    if p is None or p["answered_at"] or original is None:
        await query.answer("Already handled")
        await query.message.delete()
        return
    await query.answer()
    await query.message.delete()
    await _answer(context, original, p, late=True)


EXAMPLE_SOURCE = {"library": "from your library", "krdict": "from krdict", "model": "model-written, unchecked"}


def _word_summary(v: dict) -> str:
    w = v["word"]
    lines = [f"<b>{esc(w['korean'])}</b> · {esc(w['english'])}"]
    if w["entries"]:
        gloss = " | ".join(g for e in w["entries"] for g in e["glosses"][:1]) or "?"
        where = f"not in the learners' dictionary; root <b>{esc(w['root'])}</b>" if w["root"] else "krdict"
        lines.append(f"📖 {where}: {esc(gloss)}")
    else:
        lines.append("📖 not in the learners' dictionary")
    if w["examples"]:
        lines.append(f"<i>Examples, {EXAMPLE_SOURCE[w['source']]}:</i>")
        lines += [f"• {esc(e)}" for e in w["examples"]]
    lines += [f"⚠️ {esc(n)}" for n in v["findings"]["notes"]]
    return "\n".join(lines)


def _summary(v: dict) -> str:
    if v.get("kind") == "word":
        return _word_summary(v)
    r, d = v["review"], v["draft"]
    lines = [f"<b>Polite:</b> {esc(r['polite'])}", f"<b>Casual:</b> {esc(r['casual'])}", f"<i>{esc(d['note'])}</i>"]
    if r["issues"]:
        lines.append(fold("<b>Critic fixed:</b>\n" + "\n".join(f"• {esc(i)}" for i in r["issues"])))
    lines += [f"⚠️ {esc(n)}" for n in v.get("agent_notes", []) + v["findings"]["notes"]]
    n = len(v["chunks"])
    lines.append(f"{n} chunk{'' if n == 1 else 's'} to review below." if n else "No chunks worth a card this time.")
    return "\n".join(lines)


async def _send_card(bot, chat_id: int, capture_id: int, value: dict, total: int) -> None:
    c, i = value["chunk"], value["i"]
    key = f"ch:{capture_id}:{i}"
    await bot.send_message(
        chat_id,
        f"<b>Chunk {i + 1}/{total}</b> · {esc(c['kind'])}\n<b>{esc(c['ko'])}</b>  {esc(c['gloss'])}\n"
        f"<i>{esc(c['register_note'])}</i>\n{esc(c['sentence'])}",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard([("✅ Approve", f"{key}:ok"), ("✏️ Edit", f"{key}:ed"), ("⏭ Skip", f"{key}:sk")]),
    )


async def _send_word_card(bot, chat_id: int, capture_id: int, w: dict) -> None:
    await bot.send_message(
        chat_id, f"Save <b>{esc(w['korean'])}</b> · {esc(w['english'])} as a card?", parse_mode=ParseMode.HTML,
        reply_markup=keyboard([("✅ Approve", f"wd:{capture_id}:ok"), ("⏭ Skip", f"wd:{capture_id}:sk")]),
    )


async def on_word(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    _, capture_id, action = query.data.split(":")
    graph = context.application.bot_data["graph"]
    state = await asyncio.to_thread(graph.get_state, {"configurable": {"thread_id": capture_id}})
    if not (state.interrupts and "word" in state.interrupts[0].value):
        await query.answer("Already handled")
        await query.edit_message_reply_markup(None)
        return
    w = state.interrupts[0].value["word"]
    await query.answer("Saved" if action == "ok" else None)
    outcome = f"✅ <b>{esc(w['korean'])}</b>  {esc(w['english'])}" if action == "ok" else f"⏭ <s>{esc(w['korean'])}</s>"
    await query.edit_message_text(outcome, parse_mode=ParseMode.HTML)
    await _run(context, query.message.chat_id, int(capture_id), Command(resume={"action": action}))


async def _pending(context, capture_id: int, i: int) -> dict | None:
    """The chunk awaiting a decision, if it is still chunk i of this capture."""
    graph = context.application.bot_data["graph"]
    state = await asyncio.to_thread(graph.get_state, {"configurable": {"thread_id": str(capture_id)}})
    if state.interrupts and state.interrupts[0].value.get("i") == i:
        return state.interrupts[0].value["chunk"]
    return None


async def on_chunk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    _, capture_id, i, action = query.data.split(":")
    capture_id, i = int(capture_id), int(i)
    chunk = await _pending(context, capture_id, i)
    if chunk is None:
        await query.answer("Already handled")
        await query.edit_message_reply_markup(None)
        return
    if action == "ed":
        await query.answer()
        # ponytail: in memory, a restart forgets it; tap ✏️ again. Persist if that bites.
        context.chat_data["editing"] = (capture_id, i, query.message.message_id)
        await query.message.reply_html(
            "Tap to copy, edit it, and send it back:", reply_markup=copy_button("📋 Copy chunk", chunk["ko"])
        )
        return
    approved = action == "ok"
    await query.answer("Saved" if approved else None)
    outcome = f"✅ <b>{esc(chunk['ko'])}</b>  {esc(chunk['gloss'])}" if approved else f"⏭ <s>{esc(chunk['ko'])}</s>"
    await query.edit_message_text(outcome, parse_mode=ParseMode.HTML)
    await _run(context, query.message.chat_id, capture_id, Command(resume={"action": "ok" if approved else "skip"}))


async def _finish_edit(update: Update, context, capture_id: int, i: int, card_id: int) -> None:
    chunk = await _pending(context, capture_id, i)
    if chunk is None:
        await update.message.reply_html("That chunk was already handled.")
        return
    text = update.message.text.strip()
    await context.bot.edit_message_text(
        f"✏️ <b>{esc(text)}</b>  {esc(chunk['gloss'])}", chat_id=update.message.chat_id,
        message_id=card_id, parse_mode=ParseMode.HTML,
    )
    await _run(context, update.message.chat_id, capture_id, Command(resume={"action": "edit", "ko": text}))


MAX_CHOICES = 10


async def grammar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args or [])
    if not text:
        await update.message.reply_html("Which form? For example <code>/grammar 는데</code>")
        return
    hits = grammar.match(text, await asyncio.to_thread(grammar.load, config.DATABASE_URL))
    fresh = [p for p in hits if not p.known]
    if not hits:
        await update.message.reply_html(f"No grammar point matches <b>{esc(text)}</b>.")
    elif not fresh:
        titles = ", ".join(esc(p.title) for p in hits)
        await update.message.reply_html(
            f"{titles}: marked as known, so I skip it.",
            reply_markup=keyboard(*([(f"↩ Not known: {p.title}", f"unknown:{p.id}")] for p in hits[:MAX_CHOICES])),
        )
    elif len(fresh) == 1:
        await update.message.reply_html(grammar.explainer(fresh[0]), reply_markup=_know_key(fresh[0]))
    else:
        more = f" (first {MAX_CHOICES} of {len(fresh)})" if len(fresh) > MAX_CHOICES else ""
        await update.message.reply_html(
            f"<b>{esc(text)}</b> matches several points{more}. Which one?",
            reply_markup=keyboard(*([(f"{p.title} · L{p.level}", f"gram:{p.id}")] for p in fresh[:MAX_CHOICES])),
        )


def _know_key(p: grammar.Point):
    return keyboard([("✓ I know this", f"known:{p.id}")])


async def on_grammar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    action, _, item_id = query.data.partition(":")
    if action == "known":
        await asyncio.to_thread(grammar.mark_known, config.DATABASE_URL, int(item_id))
    elif action == "unknown":
        await asyncio.to_thread(grammar.unmark_known, config.DATABASE_URL, int(item_id))
    point = await asyncio.to_thread(grammar.get, config.DATABASE_URL, int(item_id))
    if point is None:
        await query.answer("That point is gone; the pool was re-imported.")
        return
    if action == "known":
        await query.answer("Marked as known")
        await query.edit_message_text(
            grammar.explainer(point) + "\n\n✓ Marked as known; I won't explain it again.",
            parse_mode=ParseMode.HTML,
        )
    else:
        await query.answer("Back in play" if action == "unknown" else None)
        await query.edit_message_text(
            grammar.explainer(point), parse_mode=ParseMode.HTML, reply_markup=_know_key(point)
        )


DEMO_DRAFT = "이번 주에 일이 산더미처럼 쌓였어요."
DEMO_CARD = (
    "<b>Capture:</b> I'm swamped at work this week\n\n"
    f"<b>Polite:</b> {esc(DEMO_DRAFT)}\n"
    "<b>Casual:</b> 이번 주에 일이 산더미야.\n\n"
    f"<b>Correction:</b> 일이 {correction('많아요', '산더미처럼 쌓였어요')}\n"
    f"<b>Model answer:</b> {spoiler(esc(DEMO_DRAFT))}\n"
    + fold(
        "<b>Why:</b> 산더미 is a mountain-sized pile. 일이 산더미처럼 쌓이다 is the everyday way to "
        "say work has piled up; 많다 is correct but flat. The casual 산더미야 drops the verb, which "
        "only works with friends."
    )
)
DEMO_KEYS = keyboard(
    [("✅ Approve", "demo:ok"), ("✏️ Edit", "demo:edit"), ("⏭ Skip", "demo:skip")],
    [("⏳ Progress", "demo:progress"), ("👍 React", "demo:react"), ("💥 Error", "demo:boom")],
)


async def demo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(DEMO_CARD, reply_markup=DEMO_KEYS, do_quote=True)


async def on_demo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    action = query.data.removeprefix("demo:")
    if action == "ok":
        await query.answer("Saved (demo)")
        await query.edit_message_text("✅ Approved: 일이 산더미처럼 쌓이다 (demo, nothing saved)")
    elif action == "skip":
        await query.answer()
        await query.edit_message_text("⏭ Skipped (demo)")
    elif action == "edit":
        await query.answer()
        await query.message.reply_html(
            "Tap to copy the draft, edit it, and send it back:",
            reply_markup=copy_button("📋 Copy draft", DEMO_DRAFT),
        )
    elif action == "progress":
        await query.answer()
        progress = Progress(context.bot, query.message.chat_id)
        await progress.start("Checking spelling…")
        for step in ("Grammar model…", "Writing feedback…"):
            await asyncio.sleep(1.2)
            await progress.step(step)
        await asyncio.sleep(1.2)
        await progress.done("✅ Feedback ready (demo)")
    elif action == "react":
        await query.answer()
        target = query.message.reply_to_message
        if target:
            await target.set_reaction("👍")
    elif action == "boom":
        await query.answer()
        raise RuntimeError("forced error from the demo")


async def report_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    err = context.error
    if isinstance(err, NetworkError):
        log.warning("network error (Telegram retries on its own): %s", err)
        return
    log.error("unhandled error", exc_info=err)
    metrics.ERRORS.inc()
    text = f"⚠️ Something failed: <code>{esc(type(err).__name__)}: {esc(str(err)[:200])}</code>"
    try:
        await context.bot.send_message(config.TELEGRAM_ALLOWED_USER_ID, text, parse_mode=ParseMode.HTML)
    except Exception:
        log.exception("could not report the error in chat")


async def post_init(app: Application) -> None:
    await app.bot.delete_my_commands()  # default scope: strangers see no menu
    await app.bot.set_my_commands(COMMANDS, scope=BotCommandScopeChat(config.TELEGRAM_ALLOWED_USER_ID))
    app.bot_data["loops"] = [
        asyncio.create_task(forever("Anki retry", config.ANKI_RETRY_SECONDS, lambda: anki_step(app))),
        asyncio.create_task(forever("practice ping", 30, lambda: ping_step(app))),
    ]


async def post_stop(app: Application) -> None:
    loops = app.bot_data.pop("loops", [])
    for task in loops:
        task.cancel()
    await asyncio.gather(*loops, return_exceptions=True)


def build_app(token: str, graph=None) -> Application:
    app = (
        Application.builder().token(token).post_init(post_init).post_stop(post_stop)
        .get_updates_request(metrics.PollRequest(connection_pool_size=1)).build()
    )
    app.bot_data["graph"] = graph
    app.add_handler(TypeHandler(Update, gate), group=-1)
    private = filters.ChatType.PRIVATE
    app.add_handler(CommandHandler(["start", "help"], help_cmd, filters=private))
    app.add_handler(CommandHandler("demo", demo_cmd, filters=private))
    app.add_handler(CommandHandler("grammar", grammar_cmd, filters=private))
    app.add_handler(CommandHandler("queue", queue_cmd, filters=private))
    app.add_handler(CommandHandler("weak", weak_cmd, filters=private))
    app.add_handler(CommandHandler("practice", practice_cmd, filters=private))
    app.add_handler(CommandHandler("stop", stop_cmd, filters=private))
    app.add_handler(CommandHandler("pause", pause_cmd, filters=private))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & private, free_text, block=False))  # grading
    app.add_handler(CallbackQueryHandler(on_prompt, pattern=r"^pr:\d+:(sk|st|gr|wd)$"))
    app.add_handler(CallbackQueryHandler(on_late, pattern=r"^late:\d+$", block=False))
    app.add_handler(CallbackQueryHandler(on_ask, pattern=r"^ask:\d+$", block=False))
    app.add_handler(CallbackQueryHandler(on_save, pattern=r"^sv:", block=False))
    app.add_handler(CallbackQueryHandler(on_capture, pattern=r"^cap:", block=False))  # long on CPU
    app.add_handler(CallbackQueryHandler(on_chunk, pattern=r"^ch:\d+:\d+:(ok|ed|sk)$"))
    app.add_handler(CallbackQueryHandler(on_word, pattern=r"^wd:\d+:(ok|sk)$"))
    app.add_handler(CallbackQueryHandler(on_demo, pattern=r"^demo:"))
    app.add_handler(CallbackQueryHandler(on_grammar, pattern=r"^(gram|known|unknown):\d+$"))
    app.add_error_handler(report_error)
    return app
