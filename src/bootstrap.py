import logging
import os

from src.notion.client import NotionService
from src.agent.tools.definitions import build_tools
from src.agent.core import OopsieAgent
from src.notion_cache.space_cache import SpaceCache
from src.voice.transcriber import Transcriber

logger = logging.getLogger(__name__)


def build_notion(config: dict) -> NotionService:
    """Initialise the Notion service and verify space properties."""
    notion = NotionService(
        api_key=config["notion"]["api_key"],
        root_page_id=config["notion"]["root_page_id"],
    )
    logger.info(
        "Notion service initialised with root_page_id=%s",
        config["notion"]["root_page_id"][:8] + "...",
    )

    try:
        spaces = notion.list_spaces()
        logger.info("Found %d existing space(s)", len(spaces))
        for space in spaces:
            notion.ensure_space_properties(space["id"])
        logger.info("Notion spaces verified successfully")
    except Exception:
        logger.warning("Could not verify space properties", exc_info=True)

    return notion


def build_space_cache(notion: NotionService, ttl: int = 1800) -> SpaceCache:
    """Load and return a warm SpaceCache."""
    cache = SpaceCache(notion, ttl=ttl)
    cache.load()
    logger.info("Space cache initialised")
    return cache


def build_agent(config: dict, notion: NotionService, space_cache: SpaceCache) -> OopsieAgent:
    """Build and return the OopsieAgent with all tools wired up."""
    tools = build_tools(notion, space_cache)
    logger.info("Agent tools built (%d tools)", len(tools))

    llm_cfg = config["llm"]
    agent = OopsieAgent(
        model=llm_cfg["model"],
        api_key=config["openrouter"]["api_key"],
        base_url=llm_cfg["base_url"],
        temperature=llm_cfg["temperature"],
        max_tokens=llm_cfg["max_tokens"],
        tools=tools,
        space_cache=space_cache,
        model_kwargs=llm_cfg.get("model_kwargs", {}),
    )
    logger.info(
        "Agent initialised with model=%s, temperature=%.2f, max_tokens=%d",
        llm_cfg["model"],
        llm_cfg["temperature"],
        llm_cfg["max_tokens"],
    )
    return agent


def build_transcriber(config: dict) -> Transcriber | None:
    """Return a Transcriber if GROQ_API_KEY is available, otherwise None."""
    groq_api_key = os.getenv("GROQ_API_KEY", "")
    if not groq_api_key:
        logger.warning("GROQ_API_KEY not set — voice messages will not be transcribed")
        return None

    voice_cfg = config.get("voice", {})
    transcriber = Transcriber(
        api_key=groq_api_key,
        base_url=voice_cfg["base_url"],
        model=voice_cfg["model"],
        language=voice_cfg["language"],
    )
    logger.info("Transcriber initialised with model=%s", voice_cfg["model"])
    return transcriber
