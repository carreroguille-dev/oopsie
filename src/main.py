"""Entry point for Oopsie."""

from src.utils.config import load_config
from src.notion.client import NotionService
from src.agent.tools.definitions import set_notion_service
from src.agent.core import OopsieAgent
from src.voice.transcriber import Transcriber
from src.interface.app import create_app


def main():
    config = load_config()

    # Notion — inject into tools module
    notion = NotionService(
        api_key=config["notion"]["api_key"],
        root_page_id=config["notion"]["root_page_id"],
    )
    set_notion_service(notion)

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

    # Interface
    ui_cfg = config.get("interface", {})
    app = create_app(agent, transcriber)
    app.launch(
        server_name=ui_cfg.get("server_name", "0.0.0.0"),
        server_port=ui_cfg.get("server_port", 7860),
    )


if __name__ == "__main__":
    main()
