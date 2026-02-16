"""Entry point for Oopsie."""

import logging
import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from src.utils.config import load_config
from src.notion.client import NotionService
from src.agent.tools.definitions import set_notion_service
from src.agent.core import OopsieAgent
from src.interface.bot import create_bot

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.info("Starting Oopsie application")

    try:
        config = load_config()
        logger.info("Configuration loaded successfully")
    except Exception as e:
        logger.critical("Failed to load configuration", exc_info=True)
        raise

    try:
        notion = NotionService(
            api_key=config["notion"]["api_key"],
            root_page_id=config["notion"]["root_page_id"],
        )
        set_notion_service(notion)
        logger.info("Notion service initialized with root_page_id=%s", config["notion"]["root_page_id"][:8] + "...")
    except Exception as e:
        logger.critical("Failed to initialize Notion service", exc_info=True)
        raise

    try:
        spaces = notion.list_spaces()
        logger.info("Found %d existing space(s)", len(spaces))
        for space in spaces:
            notion.ensure_space_properties(space["id"])
        logger.info("Notion spaces verified successfully")
    except Exception as e:
        logger.warning("Could not verify space properties: %s", e)

    llm_cfg = config["llm"]
    try:
        agent = OopsieAgent(
            model=llm_cfg["model"],
            api_key=config["openrouter"]["api_key"],
            base_url=llm_cfg["base_url"],
            temperature=llm_cfg["temperature"],
            max_tokens=llm_cfg["max_tokens"],
        )
        logger.info("Agent initialized with model=%s, temperature=%.2f, max_tokens=%d",
                   llm_cfg["model"], llm_cfg["temperature"], llm_cfg["max_tokens"])
    except Exception as e:
        logger.critical("Failed to initialize agent", exc_info=True)
        raise

    try:
        tg_cfg = config["telegram"]
        app = create_bot(agent, tg_cfg["bot_token"], tg_cfg["user_id"])
        logger.info("Telegram bot created for user_id=%s", tg_cfg["user_id"])
        logger.info("Oopsie bot started successfully. Polling for messages...")
        app.run_polling()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical("Failed to start or run Telegram bot", exc_info=True)
        raise


if __name__ == "__main__":
    main()
