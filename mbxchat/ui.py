"""Chat UI building blocks (SPEC §7a). Helpers that take `html` expect already-escaped HTML."""
import difflib
import html as _html

from telegram import Bot, CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest

COPY_TEXT_LIMIT = 256  # Telegram's cap on a copy button's text


def esc(text: str) -> str:
    return _html.escape(text, quote=False)


def correction(wrong: str, right: str) -> str:
    return f"<s>{esc(wrong)}</s> → <b>{esc(right)}</b>"


def word_diff(old: str, new: str) -> str:
    """`new` with the words that changed from `old` shown as <s>old</s> <b>new</b>."""
    a, b = old.split(), new.split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op == "equal":
            out.append(esc(" ".join(a[i1:i2])))
            continue
        if i2 > i1:
            out.append(f"<s>{esc(' '.join(a[i1:i2]))}</s>")
        if j2 > j1:
            out.append(f"<b>{esc(' '.join(b[j1:j2]))}</b>")
    return " ".join(out)


def spoiler(html: str) -> str:
    return f"<tg-spoiler>{html}</tg-spoiler>"


def fold(html: str) -> str:
    return f"<blockquote expandable>{html}</blockquote>"


def keyboard(*rows: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """Each row is [(label, callback_data), ...]; callback data is a short key, ≤ 64 bytes."""
    for row in rows:
        for _, data in row:
            if len(data.encode()) > 64:
                raise ValueError(f"callback data over 64 bytes: {data!r}")
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=data) for label, data in row] for row in rows]
    )


def copy_button(label: str, text: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, copy_text=CopyTextButton(text[:COPY_TEXT_LIMIT]))]]
    )


class Progress:
    """One status message edited as work advances, with the typing indicator kept alive."""

    def __init__(self, bot: Bot, chat_id: int):
        self.bot, self.chat_id, self.message = bot, chat_id, None

    async def start(self, text: str) -> None:
        await self.bot.send_chat_action(self.chat_id, ChatAction.TYPING)
        self.message = await self.bot.send_message(
            self.chat_id, f"⏳ {esc(text)}", parse_mode=ParseMode.HTML
        )

    async def step(self, text: str) -> None:
        await self.bot.send_chat_action(self.chat_id, ChatAction.TYPING)
        await self._edit(f"⏳ {esc(text)}")

    async def done(self, html: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
        await self._edit(html, reply_markup)

    async def _edit(self, html: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
        try:
            await self.message.edit_text(html, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        except BadRequest as e:
            if "not modified" not in str(e).lower():
                raise
