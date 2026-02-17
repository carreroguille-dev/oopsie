"""Entry point for Oopsie."""

import logging
import os

from src.utils.config import load_config
from src.notion.client import NotionService
from src.agent.tools.definitions import set_notion_service, set_space_cache
from src.agent.core import OopsieAgent
from src.cache.space_cache import SpaceCache
from src.interface.bot import create_bot
from src.voice.transcriber import Transcriber

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

    space_cache = SpaceCache(notion, ttl=1800)
    space_cache.load()
    set_space_cache(space_cache)
    logger.info("Space cache initialized")

    llm_cfg = config["llm"]
    try:
        agent = OopsieAgent(
            model=llm_cfg["model"],
            api_key=config["openrouter"]["api_key"],
            base_url=llm_cfg["base_url"],
            temperature=llm_cfg["temperature"],
            max_tokens=llm_cfg["max_tokens"],
            space_cache=space_cache,
            model_kwargs=llm_cfg.get("model_kwargs", {}),
        )
        logger.info("Agent initialized with model=%s, temperature=%.2f, max_tokens=%d",
                   llm_cfg["model"], llm_cfg["temperature"], llm_cfg["max_tokens"])
    except Exception as e:
        logger.critical("Failed to initialize agent", exc_info=True)
        raise

    voice_cfg = config.get("voice", {})
    groq_api_key = os.getenv("GROQ_API_KEY", "")
    if groq_api_key:
        transcriber = Transcriber(
            api_key=groq_api_key,
            base_url=voice_cfg["base_url"],
            model=voice_cfg["model"],
            language=voice_cfg["language"],
        )
    else:
        transcriber = None
        logger.warning("GROQ_API_KEY not set — voice messages will not be transcribed")

    try:
        tg_cfg = config["telegram"]
        app = create_bot(agent, tg_cfg["bot_token"], tg_cfg["user_id"], transcriber=transcriber)
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
