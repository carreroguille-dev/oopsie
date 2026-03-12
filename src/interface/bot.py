import datetime
import logging

import pytz
from telegram.error import NetworkError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    Defaults,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

from src.agent.core import OopsieAgent
from src.interface.handlers import Handlers
from src.notifications.reminder import send_due_soon_reminder
from src.voice.transcriber import Transcriber

logger = logging.getLogger(__name__)


async def _error_handler(update, context) -> None:
    if isinstance(context.error, NetworkError):
        logger.warning("Transient network error (will retry): %s", context.error)
        return
    logger.error("Unhandled error", exc_info=context.error)


def create_bot(
    agent: OopsieAgent,
    bot_token: str,
    allowed_user_id: int,
    transcriber: Transcriber | None = None,
    notion=None,
    timezone: str = "UTC",
    reminder_days_ahead: int = 1,
) -> Application:
    """Create and return the Telegram bot application."""
    logger.info("Creating Telegram bot for allowed_user_id=%s", allowed_user_id)

    handlers = Handlers(agent, allowed_user_id, transcriber)

    tz = pytz.timezone(timezone)
    app = (
        Application.builder()
        .token(bot_token)
        .defaults(Defaults(tzinfo=tz))
        .request(HTTPXRequest(
            connect_timeout=20.0,
            read_timeout=30.0,
            write_timeout=30.0,
            pool_timeout=30.0,
        ))
        .get_updates_request(HTTPXRequest(
            connect_timeout=20.0,
            read_timeout=60.0,
        ))
        .build()
    )

    app.add_error_handler(_error_handler)

    app.add_handler(CommandHandler("start", handlers.start_command))
    app.add_handler(CommandHandler("reset", handlers.reset_command))
    app.add_handler(CallbackQueryHandler(handlers.handle_space_selection, pattern="^space:"))
    app.add_handler(MessageHandler(filters.VOICE, handlers.handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_text))

    logger.info("Telegram bot handlers registered successfully")

    if notion is not None and app.job_queue is not None:
        run_time = datetime.time(9, 0, 0)
        app.job_queue.run_daily(
            send_due_soon_reminder,
            time=run_time,
            data={"notion": notion, "user_id": allowed_user_id, "timezone": timezone,
                  "reminder_days_ahead": reminder_days_ahead},
            name="due_soon_reminder",
        )
        logger.info("Scheduled due-soon reminder daily at 09:00 %s (days_ahead=%d)",
                    timezone, reminder_days_ahead)
    elif notion is not None:
        logger.warning("APScheduler not available — due-soon reminder will not run. Install APScheduler.")

    return app
