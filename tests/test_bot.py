import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import BotCommandScopeChat
from telegram.error import NetworkError
from telegram.ext import ApplicationHandlerStop

from mbxchat import bot, config

ALLOWED = 1001


@pytest.fixture(autouse=True)
def _allowed_user(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_ALLOWED_USER_ID", ALLOWED)


def run(coro):
    return asyncio.run(coro)


def _update_from(user_id):
    update = MagicMock()
    update.effective_user = MagicMock(id=user_id) if user_id is not None else None
    return update


def test_gate_lets_the_allowed_user_through():
    run(bot.gate(_update_from(ALLOWED), MagicMock()))


@pytest.mark.parametrize("user_id", [999, None])
def test_gate_stops_everyone_else(user_id):
    with pytest.raises(ApplicationHandlerStop):
        run(bot.gate(_update_from(user_id), MagicMock()))


def test_help_lists_every_menu_command():
    update = MagicMock()
    update.message.reply_html = AsyncMock()
    run(bot.help_cmd(update, MagicMock()))
    text = update.message.reply_html.await_args.args[0]
    for name, _ in bot.COMMANDS:
        assert f"/{name}" in text


def test_free_text_asks_before_capturing():
    update = MagicMock()
    update.message.reply_html = AsyncMock()
    run(bot.free_text(update, MagicMock()))
    call = update.message.reply_html.await_args
    assert call.args[0] == "Capture this?"
    assert [b.callback_data for b in call.kwargs["reply_markup"].inline_keyboard[0]] == ["cap:yes", "cap:no"]
    assert call.kwargs["do_quote"] is True


def _query(data, original_text=None):
    update = MagicMock()
    q = update.callback_query
    q.data = data
    q.answer = AsyncMock()
    q.edit_message_text = AsyncMock()
    q.message.delete = AsyncMock()
    q.message.reply_to_message = MagicMock(text=original_text) if original_text else None
    return update, q


def test_capture_yes_edits_in_place_with_escaped_original():
    update, q = _query("cap:yes", "how do I say <this>?")
    run(bot.on_capture(update, MagicMock()))
    assert "how do I say &lt;this&gt;?" in q.edit_message_text.await_args.args[0]
    q.message.delete.assert_not_awaited()


def test_capture_no_removes_the_question():
    update, q = _query("cap:no")
    run(bot.on_capture(update, MagicMock()))
    q.message.delete.assert_awaited_once()
    q.edit_message_text.assert_not_awaited()


def test_demo_approve_edits_in_place():
    update, q = _query("demo:ok")
    run(bot.on_demo(update, MagicMock()))
    assert q.edit_message_text.await_args.args[0].startswith("✅ Approved")


def test_demo_error_button_raises():
    update, _ = _query("demo:boom")
    with pytest.raises(RuntimeError):
        run(bot.on_demo(update, MagicMock()))


def _context(error):
    context = MagicMock()
    context.error = error
    context.bot.send_message = AsyncMock()
    return context


def test_errors_are_reported_to_the_allowed_chat():
    context = _context(RuntimeError("boom <x>"))
    run(bot.report_error(None, context))
    chat_id, text = context.bot.send_message.await_args.args
    assert chat_id == ALLOWED
    assert "RuntimeError: boom &lt;x&gt;" in text


def test_network_errors_stay_in_the_log():
    context = _context(NetworkError("connection reset"))
    run(bot.report_error(None, context))
    context.bot.send_message.assert_not_awaited()


def test_menu_is_cleared_globally_and_set_for_the_allowed_chat_only():
    app = MagicMock()
    app.bot.delete_my_commands = AsyncMock()
    app.bot.set_my_commands = AsyncMock()
    run(bot.post_init(app))
    app.bot.delete_my_commands.assert_awaited_once_with()
    call = app.bot.set_my_commands.await_args
    assert call.args[0] == bot.COMMANDS
    assert call.kwargs["scope"] == BotCommandScopeChat(ALLOWED)


def test_build_app_registers_handlers_without_network():
    app = bot.build_app("123:fake")
    assert [type(h).__name__ for h in app.handlers[-1]] == ["TypeHandler"]  # gate runs first
    assert len(app.handlers[0]) == 5
    assert app.error_handlers


def test_config_problems_name_what_is_missing(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(config, "TELEGRAM_ALLOWED_USER_ID", None)
    problems = config.bot_config_problems()
    assert len(problems) == 2 and "TELEGRAM_BOT_TOKEN" in problems[0]
