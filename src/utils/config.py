"""Load configuration from YAML file and environment variables."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Load .env from project root
_project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_project_root / ".env")


def load_config() -> dict:
    """Load config from config.yaml (or config.example.yaml as fallback)."""
    config_dir = _project_root / "config"
    config_path = config_dir / "config.yaml"
    if not config_path.exists():
        config_path = config_dir / "config.example.yaml"

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Inject env vars into config
    config["notion"] = {
        "api_key": os.getenv("NOTION_API_KEY", ""),
        "root_page_id": os.getenv("NOTION_ROOT_PAGE_ID", ""),
    }
    config["openrouter"] = {
        "api_key": os.getenv("OPENROUTER_API_KEY", ""),
    }
    config["telegram"] = {
        "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "user_id": int(os.getenv("TELEGRAM_USER_ID", "0")),
    }
    config["langfuse"] = {
        "secret_key": os.getenv("LANGFUSE_SECRET_KEY", ""),
        "public_key": os.getenv("LANGFUSE_PUBLIC_KEY", ""),
        "host": os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    }

    return config
