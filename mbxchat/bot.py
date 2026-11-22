import asyncio
import logging

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

from mbxchat import capture, config, grammar
from mbxchat.ui import Progress, copy_button, correction, esc, fold, keyboard, spoiler

log = logging.getLogger(__name__)

# The / menu is built from this list, so it can't drift from the handlers registered below.
COMMANDS = [
    ("help", "What I can do"),
    ("grammar", "Explain a grammar point: /grammar 는데"),
    ("demo", "Preview of the chat UI"),
]

HELP = (
    "<b>MbxChat</b>: practise writing Korean.\n\n"
    "Send me any text and I'll offer to capture it (\"how do I say…\").\n\n"
    + "\n".join(f"/{name}  {desc}" for name, desc in COMMANDS)
    + "\n\nComing next: /practice, /stop, /pause, /queue, /stats."
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
    await update.message.reply_html(
        "Capture this?",
        reply_markup=keyboard([("➕ Capture", "cap:yes"), ("✖ No", "cap:no")]),
        do_quote=True,
    )


async def on_capture(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query.data == "cap:no":
        await query.answer()
        await query.message.delete()
        return
    original = query.message.reply_to_message
    text = original.text if original and original.text else ""
    await query.answer()
    await query.edit_message_text(f"➕ <i>{esc(text)}</i>", parse_mode=ParseMode.HTML)
    capture_id = await asyncio.to_thread(capture.new_capture, text)
    progress = Progress(context.bot, query.message.chat_id)
    await progress.start("Drafting…")
    try:
        await _run(context, query.message.chat_id, capture_id, {"text": text}, progress)
    except Exception as e:
        log.exception("capture %s failed", capture_id)
        await progress.done(f"⚠️ Capture failed: <code>{esc(type(e).__name__)}: {esc(str(e)[:200])}</code>")


# Label shown once the key node has finished, i.e. what runs next.
NEXT_STEP = {
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
    if state.interrupts:
        await _send_card(context.bot, chat_id, capture_id, state.interrupts[0].value, len(state.values["chunks"]))
    elif progress is None:
        n = state.values.get("saved", 0)
        await context.bot.send_message(chat_id, f"Done: {n} chunk{'' if n == 1 else 's'} saved.")


def _summary(v: dict) -> str:
    r, d = v["review"], v["draft"]
    lines = [f"<b>Polite:</b> {esc(r['polite'])}", f"<b>Casual:</b> {esc(r['casual'])}", f"<i>{esc(d['note'])}</i>"]
    if r["issues"]:
        lines.append(fold("<b>Critic fixed:</b>\n" + "\n".join(f"• {esc(i)}" for i in r["issues"])))
    lines += [f"⚠️ {esc(n)}" for n in v["findings"]["notes"]]
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


async def _pending(context, capture_id: int, i: int) -> dict | None:
    """The chunk awaiting a decision, if it is still chunk i of this capture."""
    graph = context.application.bot_data["graph"]
    state = await asyncio.to_thread(graph.get_state, {"configurable": {"thread_id": str(capture_id)}})
    if state.interrupts and state.interrupts[0].value["i"] == i:
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
    text = f"⚠️ Something failed: <code>{esc(type(err).__name__)}: {esc(str(err)[:200])}</code>"
    try:
        await context.bot.send_message(config.TELEGRAM_ALLOWED_USER_ID, text, parse_mode=ParseMode.HTML)
    except Exception:
        log.exception("could not report the error in chat")


async def post_init(app: Application) -> None:
    await app.bot.delete_my_commands()  # default scope: strangers see no menu
    await app.bot.set_my_commands(COMMANDS, scope=BotCommandScopeChat(config.TELEGRAM_ALLOWED_USER_ID))


def build_app(token: str, graph=None) -> Application:
    app = Application.builder().token(token).post_init(post_init).build()
    app.bot_data["graph"] = graph
    app.add_handler(TypeHandler(Update, gate), group=-1)
    private = filters.ChatType.PRIVATE
    app.add_handler(CommandHandler(["start", "help"], help_cmd, filters=private))
    app.add_handler(CommandHandler("demo", demo_cmd, filters=private))
    app.add_handler(CommandHandler("grammar", grammar_cmd, filters=private))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & private, free_text))
    app.add_handler(CallbackQueryHandler(on_capture, pattern=r"^cap:", block=False))  # long on CPU
    app.add_handler(CallbackQueryHandler(on_chunk, pattern=r"^ch:\d+:\d+:(ok|ed|sk)$"))
    app.add_handler(CallbackQueryHandler(on_demo, pattern=r"^demo:"))
    app.add_handler(CallbackQueryHandler(on_grammar, pattern=r"^(gram|known|unknown):\d+$"))
    app.add_error_handler(report_error)
    return app
