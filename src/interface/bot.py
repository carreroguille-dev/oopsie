"""Telegram bot interface for Oopsie — thin layer, no business logic."""

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
from src.voice.transcriber import Transcriber

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
    for i in range(0, len(text), MAX_MESSAGE_LENGTH):
        chunk = text[i:i + MAX_MESSAGE_LENGTH]
        try:
            await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await update.message.reply_text(chunk)


def create_bot(
    agent: OopsieAgent,
    transcriber: Transcriber | None,
    bot_token: str,
    allowed_user_id: int,
) -> Application:
    """Create and return the Telegram bot application."""

    auth = _authorized_only(allowed_user_id)

    @auth
    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        agent.reset()
        await update.message.reply_text(
            "¡Hola! Soy Oopsie, tu asistente de tareas. ¿En qué te ayudo?"
        )

    @auth
    async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        agent.reset()
        await update.message.reply_text("¡Chat reiniciado! ¿En qué te ayudo?")

    @auth
    async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = update.message.text
        if not text or not text.strip():
            return

        await update.message.chat.send_action(ChatAction.TYPING)
        response = agent.process_message(text)
        await _send_long_message(update, response)

    @auth
    async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not transcriber:
            await update.message.reply_text("El reconocimiento de voz no está disponible.")
            return

        voice = update.message.voice
        voice_file = await context.bot.get_file(voice.file_id)

        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            await voice_file.download_to_drive(str(tmp_path))
            text = transcriber.transcribe(str(tmp_path))

            if not text.strip():
                await update.message.reply_text("No pude entender el audio.")
                return

            await update.message.chat.send_action(ChatAction.TYPING)
            response = agent.process_message(text)
            await _send_long_message(update, f"🎤 {text}\n\n{response}")
        finally:
            tmp_path.unlink(missing_ok=True)

    app = Application.builder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    return app
