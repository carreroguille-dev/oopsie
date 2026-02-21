"""Load configuration from YAML file and environment variables."""

import logging
import os
from pathlib import Path
from typing import TypedDict

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_project_root = Path(__file__).resolve().parent.parent.parent


class LlmConfig(TypedDict):
    model: str
    base_url: str
    temperature: float
    max_tokens: int
    model_kwargs: dict


class VoiceConfig(TypedDict):
    model: str
    base_url: str
    language: str
    api_key: str


class NotionConfig(TypedDict):
    api_key: str
    root_page_id: str


class OpenRouterConfig(TypedDict):
    api_key: str


class TelegramConfig(TypedDict):
    bot_token: str
    user_id: int


class LangfuseConfig(TypedDict):
    secret_key: str
    public_key: str
    host: str


class AppConfig(TypedDict):
    llm: LlmConfig
    voice: VoiceConfig
    notion: NotionConfig
    openrouter: OpenRouterConfig
    telegram: TelegramConfig
    langfuse: LangfuseConfig
    timezone: str


def load_config() -> AppConfig:
    """Load config from config.yaml (or config.example.yaml as fallback)."""
    load_dotenv(_project_root / ".env")
    config_dir = _project_root / "config"
    config_path = config_dir / "config.yaml"

    if not config_path.exists():
        logger.warning("config.yaml not found, falling back to config.example.yaml")
        config_path = config_dir / "config.example.yaml"

    logger.info("Loading configuration from: %s", config_path)

    try:
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except Exception:
        logger.error("Failed to load YAML configuration from %s", config_path, exc_info=True)
        raise

    # Inject env vars into config
    logger.debug("Injecting environment variables into config")

    config["notion"] = NotionConfig(
        api_key=os.getenv("NOTION_API_KEY", ""),
        root_page_id=os.getenv("NOTION_ROOT_PAGE_ID", ""),
    )
    config["openrouter"] = OpenRouterConfig(
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
    )
    config["telegram"] = TelegramConfig(
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        user_id=int(os.getenv("TELEGRAM_USER_ID", "0")),
    )
    config["langfuse"] = LangfuseConfig(
        secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
        host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )
    config.setdefault("voice", {})
    config["voice"]["api_key"] = os.getenv("GROQ_API_KEY", "")

    # Validate critical env vars
    missing_vars = []
    if not config["notion"]["api_key"]:
        missing_vars.append("NOTION_API_KEY")
    if not config["notion"]["root_page_id"]:
        missing_vars.append("NOTION_ROOT_PAGE_ID")
    if not config["openrouter"]["api_key"]:
        missing_vars.append("OPENROUTER_API_KEY")
    if not config["telegram"]["bot_token"]:
        missing_vars.append("TELEGRAM_BOT_TOKEN")
    if config["telegram"]["user_id"] == 0:
        missing_vars.append("TELEGRAM_USER_ID")

    if missing_vars:
        logger.error("Missing required environment variables: %s", ", ".join(missing_vars))
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

    logger.info("Configuration loaded successfully with all required environment variables")
    return config
