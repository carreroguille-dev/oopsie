import logging
import re
import tempfile
from functools import wraps
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ChatType, ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.agent.core import OopsieAgent

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096
_SPACE_SELECT_RE = re.compile(r"\[SPACE_SELECT:\s*(.+?)\]")


def _authorized_only(allowed_user_id: int):
    """Decorator that restricts handlers to a single Telegram user."""
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if update.effective_user.id != allowed_user_id:
                return
            if update.effective_chat.type != ChatType.PRIVATE:
                return
            return await func(update, context)
        return wrapper
    return decorator


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


async def _send_long_message(
    update: Update, text: str, reply_markup=None,
) -> None:
    """Send a message, splitting into chunks if it exceeds Telegram's limit.

    Tries Markdown parse mode first; falls back to plain text if Telegram
    rejects the markup (unmatched delimiters, unsupported syntax, etc.).
    ``reply_markup`` is only attached to the **last** chunk.
    """
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


def create_bot(
    agent: OopsieAgent,
    bot_token: str,
    allowed_user_id: int,
) -> Application:
    """Create and return the Telegram bot application."""
    logger.info("Creating Telegram bot for allowed_user_id=%s", allowed_user_id)

    auth = _authorized_only(allowed_user_id)

    @auth
    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        username = update.effective_user.username or "unknown"
        logger.info("/start command received from user_id=%s, username=%s", user_id, username)
        agent.reset()
        await update.message.reply_text(
            "¡Hola! Soy Oopsie, tu asistente de tareas. ¿En qué te ayudo?"
        )

    @auth
    async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        logger.info("/reset command received from user_id=%s", user_id)
        agent.reset()
        await update.message.reply_text("¡Chat reiniciado! ¿En qué te ayudo?")

    @auth
    async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = update.message.text
        if not text or not text.strip():
            logger.debug("Received empty text message, ignoring")
            return

        user_id = update.effective_user.id
        logger.info("Text message received from user_id=%s (length=%d chars)", user_id, len(text))

        try:
            await update.message.chat.send_action(ChatAction.TYPING)
            response = agent.process_message(text)
            clean_text, space_names = _extract_space_select(response)
            markup = _build_space_keyboard(space_names) if space_names else None
            await _send_long_message(update, clean_text, reply_markup=markup)
            logger.info("Response sent to user_id=%s (length=%d chars)", user_id, len(clean_text))
        except Exception as e:
            logger.error("Failed to handle text message from user_id=%s", user_id, exc_info=True)
            await update.message.reply_text("Lo siento, ocurrió un error al procesar tu mensaje.")

    @auth
    async def handle_space_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        space_name = query.data.removeprefix("space:")
        user_id = update.effective_user.id
        logger.info("Space selected via button: '%s' by user_id=%s", space_name, user_id)

        try:
            await query.message.chat.send_action(ChatAction.TYPING)
            response = agent.process_message(space_name)
            clean_text, space_names = _extract_space_select(response)
            markup = _build_space_keyboard(space_names) if space_names else None

            try:
                await query.message.reply_text(
                    clean_text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup,
                )
            except Exception:
                await query.message.reply_text(clean_text, reply_markup=markup)

            logger.info("Response sent to user_id=%s (length=%d chars)", user_id, len(clean_text))
        except Exception:
            logger.error("Failed to handle space selection for user_id=%s", user_id, exc_info=True)
            await query.message.reply_text("Lo siento, ocurrió un error al procesar tu selección.")

    app = Application.builder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CallbackQueryHandler(handle_space_selection, pattern="^space:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Telegram bot handlers registered successfully")
    return app
