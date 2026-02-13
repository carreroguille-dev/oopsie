"""Entry point for Oopsie."""

import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from src.utils.config import load_config
from src.notion.client import NotionService
from src.agent.tools.definitions import set_notion_service
from src.agent.core import OopsieAgent
from src.voice.transcriber import Transcriber
from src.interface.bot import create_bot


def main():
    config = load_config()

    # Notion — inject into tools module
    notion = NotionService(
        api_key=config["notion"]["api_key"],
        root_page_id=config["notion"]["root_page_id"],
    )
    set_notion_service(notion)

    # Fix existing databases that may be missing properties
    try:
        for space in notion.list_spaces():
            notion.ensure_space_properties(space["id"])
        print("Notion spaces verified.")
    except Exception as e:
        print(f"Warning: could not verify space properties: {e}")

    # Agent (LLM + LangGraph)
    llm_cfg = config["llm"]

    agent = OopsieAgent(
        model=llm_cfg["model"],
        api_key=config["openrouter"]["api_key"],
        base_url=llm_cfg["base_url"],
        temperature=llm_cfg["temperature"],
        max_tokens=llm_cfg["max_tokens"],
    )

    # Voice (optional — skip if faster-whisper fails to load)
    transcriber = None
    try:
        voice_cfg = config.get("voice", {})
        transcriber = Transcriber(
            model_size=voice_cfg.get("model_size", "small"),
            language=voice_cfg.get("language", "es"),
        )
    except Exception as e:
        print(f"Voice disabled: {e}")

    # Telegram bot
    tg_cfg = config["telegram"]
    app = create_bot(agent, transcriber, tg_cfg["bot_token"], tg_cfg["user_id"])
    print("Oopsie bot started. Polling for messages...")
    app.run_polling()


if __name__ == "__main__":
    main()
