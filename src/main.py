"""Entry point for Oopsie."""

import logging

from src.utils.config import load_config, AppConfig
from src.interface.bot import create_bot
from src.bootstrap import build_notion, build_space_cache, build_agent, build_transcriber

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.info("Starting Oopsie application")

    config: AppConfig = load_config()
    logger.info("Configuration loaded successfully")

    notion      = build_notion(config)
    space_cache = build_space_cache(notion)
    agent       = build_agent(config, notion, space_cache)
    transcriber = build_transcriber(config)

    tg_cfg = config["telegram"]
    app = create_bot(
        agent,
        tg_cfg["bot_token"],
        tg_cfg["user_id"],
        transcriber=transcriber,
        notion=notion,
        timezone=config["timezone"],
    )

    logger.info("Telegram bot created for user_id=%s", tg_cfg["user_id"])
    logger.info("Oopsie bot started. Polling for messages...")

    try:
        app.run_polling(drop_pending_updates=True)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")


if __name__ == "__main__":
    main()
