import logging
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096
_SPACE_SELECT_RE = re.compile(r"\[SPACE_SELECT:\s*(.+?)\]")


def _extract_space_select(text: str) -> tuple[str, list[str] | None]:
    """Strip the [SPACE_SELECT: ...] marker and return (clean_text, space_names)."""
    match = _SPACE_SELECT_RE.search(text)
    if not match:
        return text, None
    space_names = [s.strip() for s in match.group(1).split(",") if s.strip()]
    clean = text[:match.start()].rstrip()
    return clean, space_names or None


def _build_space_keyboard(space_names: list[str]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(name, callback_data=f"space:{name}")]
        for name in space_names
    ]
    return InlineKeyboardMarkup(buttons)


async def _send_long_message(update: Update, text: str, reply_markup=None) -> None:
    """Send a message, splitting into chunks if it exceeds Telegram's limit."""
    if not text:
        if reply_markup:
            await update.message.reply_text("Elige un espacio:", reply_markup=reply_markup)
        return

    num_chunks = (len(text) + MAX_MESSAGE_LENGTH - 1) // MAX_MESSAGE_LENGTH
    if num_chunks > 1:
        logger.debug("Splitting message into %d chunk(s) (total length=%d)", num_chunks, len(text))

    chunks = [text[i:i + MAX_MESSAGE_LENGTH] for i in range(0, len(text), MAX_MESSAGE_LENGTH)]
    for idx, chunk in enumerate(chunks):
        markup = reply_markup if idx == len(chunks) - 1 else None
        try:
            await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
        except Exception as e:
            logger.warning("Markdown parsing failed, falling back to plain text: %s", e)
            await update.message.reply_text(chunk, reply_markup=markup)
