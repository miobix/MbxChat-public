import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.error import BadRequest

from mbxchat.ui import COPY_TEXT_LIMIT, Progress, copy_button, correction, fold, keyboard, spoiler, word_diff


def test_word_diff_marks_only_changed_words():
    assert word_diff("가게 갈거야, 사올게 있니?", "가게 갈 거야, 사 올 거 있어?") == (
        "가게 <s>갈거야, 사올게 있니?</s> <b>갈 거야, 사 올 거 있어?</b>"
    )
    assert word_diff("저는 매운 음식이 좋아해요.", "저는 매운 음식을 좋아해요.") == (
        "저는 매운 <s>음식이</s> <b>음식을</b> 좋아해요."
    )
    assert word_diff("a < b", "a < b") == "a &lt; b"


def test_correction_escapes_both_sides():
    assert correction("<a>", "b&c") == "<s>&lt;a&gt;</s> → <b>b&amp;c</b>"


def test_spoiler_and_fold_wrap_html():
    assert spoiler("<b>x</b>") == "<tg-spoiler><b>x</b></tg-spoiler>"
    assert fold("x") == "<blockquote expandable>x</blockquote>"


def test_keyboard_rows_and_data():
    kb = keyboard([("A", "a:1"), ("B", "b:2")], [("C", "c:3")])
    assert [[b.callback_data for b in row] for row in kb.inline_keyboard] == [["a:1", "b:2"], ["c:3"]]


def test_keyboard_refuses_data_over_64_bytes():
    with pytest.raises(ValueError):
        keyboard([("A", "가" * 22)])  # 66 bytes in UTF-8


def test_copy_button_truncates_to_telegram_limit():
    button = copy_button("Copy", "x" * 300).inline_keyboard[0][0]
    assert len(button.copy_text.text) == COPY_TEXT_LIMIT


def _progress():
    bot = MagicMock()
    bot.send_chat_action = AsyncMock()
    message = MagicMock(edit_text=AsyncMock())
    bot.send_message = AsyncMock(return_value=message)
    return Progress(bot, 42), bot, message


def test_progress_sends_once_then_edits_in_place():
    p, bot, message = _progress()

    async def run():
        await p.start("one")
        await p.step("two")
        await p.done("<b>done</b>")

    asyncio.run(run())
    bot.send_message.assert_awaited_once()
    assert [c.args[0] for c in message.edit_text.await_args_list] == ["⏳ two", "<b>done</b>"]
    assert bot.send_chat_action.await_count == 2


def test_progress_ignores_not_modified_but_raises_other_errors():
    p, _, message = _progress()

    async def run(error):
        await p.start("one")
        message.edit_text.side_effect = error
        await p.step("one")

    asyncio.run(run(BadRequest("Message is not modified: same content")))
    with pytest.raises(BadRequest):
        asyncio.run(run(BadRequest("Message to edit not found")))
