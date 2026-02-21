import logging
import os
import tempfile
from pathlib import Path

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ContextTypes

from src.agent.core import OopsieAgent
from src.interface.auth import _authorized_only
from src.interface.formatting import (
    _build_space_keyboard,
    _extract_space_select,
    _send_long_message,
)
from src.voice.transcriber import Transcriber

logger = logging.getLogger(__name__)


class Handlers:
    """Encapsulates all Telegram handler methods with their dependencies."""

    def __init__(
        self,
        agent: OopsieAgent,
        allowed_user_id: int,
        transcriber: Transcriber | None = None,
    ):
        self._agent = agent
        self._transcriber = transcriber

        auth = _authorized_only(allowed_user_id)
        self.start_command = auth(self._start_command)
        self.reset_command = auth(self._reset_command)
        self.handle_text = auth(self._handle_text)
        self.handle_space_selection = auth(self._handle_space_selection)
        self.handle_voice = auth(self._handle_voice)

    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        username = update.effective_user.username or "unknown"
        logger.info("/start command received from user_id=%s, username=%s", user_id, username)
        self._agent.reset()
        await update.message.reply_text(
            "¡Hola! Soy Oopsie, tu asistente de tareas. ¿En qué te ayudo?"
        )

    async def _reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        logger.info("/reset command received from user_id=%s", user_id)
        self._agent.reset()
        await update.message.reply_text("¡Chat reiniciado! ¿En qué te ayudo?")

    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = update.message.text
        if not text or not text.strip():
            logger.debug("Received empty text message, ignoring")
            return

        user_id = update.effective_user.id
        logger.info("Text message received from user_id=%s (length=%d chars)", user_id, len(text))

        try:
            await update.message.chat.send_action(ChatAction.TYPING)
            response = await self._agent.process_message(text)
            clean_text, space_names = _extract_space_select(response)
            markup = _build_space_keyboard(space_names) if space_names else None
            await _send_long_message(update, clean_text, reply_markup=markup)
            logger.info("Response sent to user_id=%s (length=%d chars)", user_id, len(clean_text))
            logger.debug("Raw agent response (length=%d): %r", len(response or ""), response)
        except Exception:
            logger.error("Failed to handle text message from user_id=%s", user_id, exc_info=True)
            await update.message.reply_text("Lo siento, ocurrió un error al procesar tu mensaje.")

    async def _handle_space_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        space_name = query.data.removeprefix("space:")
        user_id = update.effective_user.id
        logger.info("Space selected via button: '%s' by user_id=%s", space_name, user_id)

        try:
            await query.message.chat.send_action(ChatAction.TYPING)
            response = await self._agent.process_message(space_name)
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

    async def _handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._transcriber:
            await update.message.reply_text("No tengo soporte de voz configurado.")
            return

        user_id = update.effective_user.id
        logger.info("Voice message received from user_id=%s", user_id)

        tmp_path = None
        try:
            tg_file = await context.bot.get_file(update.message.voice.file_id)
            fd, tmp_path = tempfile.mkstemp(suffix=".ogg")
            os.close(fd)
            await tg_file.download_to_drive(tmp_path)

            await update.message.chat.send_action(ChatAction.TYPING)
            text = await self._transcriber.transcribe(tmp_path)
            if not text:
                await update.message.reply_text("No pude entender el audio.")
                return

            logger.info("Voice transcribed for user_id=%s: '%s'", user_id, text[:60])
            response = await self._agent.process_message(text)
            clean_text, space_names = _extract_space_select(response)
            markup = _build_space_keyboard(space_names) if space_names else None
            await _send_long_message(update, clean_text, reply_markup=markup)
            logger.info("Voice response sent to user_id=%s (length=%d chars)", user_id, len(clean_text))
        except Exception:
            logger.error("Failed to handle voice message from user_id=%s", user_id, exc_info=True)
            await update.message.reply_text("Lo siento, ocurrió un error al procesar tu mensaje de voz.")
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)
