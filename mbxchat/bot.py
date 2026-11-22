import asyncio
import logging

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

from mbxchat import config
from mbxchat.ui import Progress, copy_button, correction, esc, fold, keyboard, spoiler

log = logging.getLogger(__name__)

# The / menu is built from this list, so it can't drift from the handlers registered below.
COMMANDS = [
    ("help", "What I can do"),
    ("demo", "Preview of the chat UI"),
]

HELP = (
    "<b>MbxChat</b>: practise writing Korean.\n\n"
    "Send me any text and I'll offer to capture it (\"how do I say…\").\n\n"
    + "\n".join(f"/{name}  {desc}" for name, desc in COMMANDS)
    + "\n\nComing next: /grammar, /practice, /stop, /pause, /queue, /stats."
)


async def gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None or user.id != config.TELEGRAM_ALLOWED_USER_ID:
        log.info("ignored update from user %s", user.id if user else None)
        raise ApplicationHandlerStop


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(HELP)


async def free_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    await query.answer("Noted")
    await query.edit_message_text(
        f"➕ <i>{esc(text)}</i>\nCapturing isn't built yet; nothing was saved.",
        parse_mode=ParseMode.HTML,
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


def build_app(token: str) -> Application:
    app = Application.builder().token(token).post_init(post_init).build()
    app.add_handler(TypeHandler(Update, gate), group=-1)
    private = filters.ChatType.PRIVATE
    app.add_handler(CommandHandler(["start", "help"], help_cmd, filters=private))
    app.add_handler(CommandHandler("demo", demo_cmd, filters=private))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & private, free_text))
    app.add_handler(CallbackQueryHandler(on_capture, pattern=r"^cap:"))
    app.add_handler(CallbackQueryHandler(on_demo, pattern=r"^demo:"))
    app.add_error_handler(report_error)
    return app
