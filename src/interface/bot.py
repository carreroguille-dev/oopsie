import logging
import tempfile
from functools import wraps
from pathlib import Path

from telegram import Update
from telegram.constants import ChatAction, ChatType, ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.agent.core import OopsieAgent

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096


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


async def _send_long_message(update: Update, text: str) -> None:
    """Send a message, splitting into chunks if it exceeds Telegram's limit.

    Tries Markdown parse mode first; falls back to plain text if Telegram
    rejects the markup (unmatched delimiters, unsupported syntax, etc.).
    """
    num_chunks = (len(text) + MAX_MESSAGE_LENGTH - 1) // MAX_MESSAGE_LENGTH
    if num_chunks > 1:
        logger.debug("Splitting message into %d chunk(s) (total length=%d)", num_chunks, len(text))

    for i in range(0, len(text), MAX_MESSAGE_LENGTH):
        chunk = text[i:i + MAX_MESSAGE_LENGTH]
        try:
            await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.warning("Markdown parsing failed, falling back to plain text: %s", e)
            await update.message.reply_text(chunk)


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
            await _send_long_message(update, response)
            logger.info("Response sent to user_id=%s (length=%d chars)", user_id, len(response))
        except Exception as e:
            logger.error("Failed to handle text message from user_id=%s", user_id, exc_info=True)
            await update.message.reply_text("Lo siento, ocurrió un error al procesar tu mensaje.")

    app = Application.builder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Telegram bot handlers registered successfully")
    return app
