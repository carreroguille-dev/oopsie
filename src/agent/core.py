import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from src.agent.tools.definitions import ALL_TOOLS

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 10

_PROMPT_PATH = Path(__file__).parent / "prompts" / "system_prompt.txt"


def _build_system_prompt() -> str:
    """Load system prompt template and inject current date."""
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    today = datetime.now().strftime("%Y-%m-%d (%A)")
    return template.format(current_date=today)


class OopsieAgent:
    def __init__(self, model: str, api_key: str, base_url: str,
                 temperature: float = 0.7, max_tokens: int = 2048, user_id: str = None):
        llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        self.graph = create_react_agent(
            model=llm,
            tools=ALL_TOOLS,
            checkpointer=MemorySaver(),
            prompt=_build_system_prompt(),
        )

        self._thread_id = str(uuid.uuid4())
        self._session_id = f"session-{uuid.uuid4()}"
        self._user_id = user_id
        self._model = model
        self._langfuse_enabled = self._check_langfuse()

    def _check_langfuse(self) -> bool:
        """Verify Langfuse is available and credentials are set."""
        if not os.getenv("LANGFUSE_SECRET_KEY") or not os.getenv("LANGFUSE_PUBLIC_KEY"):
            logger.info("Langfuse disabled: missing API keys.")
            return False
        try:
            self._get_langfuse_handler_class()
            logger.info("Langfuse enabled.")
            return True
        except ImportError:
            logger.warning("Langfuse disabled: package not installed or import failed.")
            return False

    @staticmethod
    def _get_langfuse_handler_class():
        """Return the CallbackHandler class, trying both import paths."""
        try:
            from langfuse.callback import CallbackHandler
            return CallbackHandler
        except ImportError:
            from langfuse.langchain import CallbackHandler
            return CallbackHandler

    def _create_langfuse_handler(self):
        """Create a fresh Langfuse callback handler for a single invocation."""
        if not self._langfuse_enabled:
            return None

        try:
            CallbackHandler = self._get_langfuse_handler_class()
            return CallbackHandler()
        except Exception as e:
            logger.warning("Failed to create Langfuse handler: %s", e)
            return None

    def _langfuse_metadata(self) -> dict:
        """Build the Langfuse metadata dict for the invoke config."""
        metadata = {
            "langfuse_session_id": self._session_id,
            "langfuse_tags": ["langgraph", "agent"],
            "model": self._model,
        }
        if self._user_id:
            metadata["langfuse_user_id"] = self._user_id
        return metadata

    def process_message(self, user_message: str) -> str:
        """Process a user message. Returns the final text response."""
        config = {"configurable": {"thread_id": self._thread_id}}

        handler = self._create_langfuse_handler()
        if handler:
            config["callbacks"] = [handler]
            config["metadata"] = self._langfuse_metadata()

        result = self.graph.invoke(
            {"messages": [("user", user_message)]},
            config=config,
        )
        response = self._extract_response(result["messages"])
        self._trim_history(config, result["messages"])
        return response

    def _trim_history(self, config: dict, messages: list) -> None:
        """Trim conversation history to the last MAX_HISTORY_MESSAGES.
        """
        if len(messages) <= MAX_HISTORY_MESSAGES:
            return

        cut_idx = len(messages) - MAX_HISTORY_MESSAGES

        while cut_idx < len(messages) and isinstance(messages[cut_idx], ToolMessage):
            cut_idx += 1

        to_drop = messages[:cut_idx]
        if not to_drop:
            return

        removals = [RemoveMessage(id=m.id) for m in to_drop]
        self.graph.update_state(config, {"messages": removals})

    @staticmethod
    def _extract_response(messages: list) -> str:
        """Extract the final text response from the current turn only."""
        last_human_idx = 0
        for i, msg in enumerate(messages):
            if isinstance(msg, HumanMessage):
                last_human_idx = i

        for msg in reversed(messages[last_human_idx + 1:]):
            if isinstance(msg, AIMessage) and isinstance(msg.content, str) and msg.content.strip():
                return msg.content
        return "No pude generar una respuesta. Intenta de nuevo."

    def reset(self):
        """Start a new conversation by switching thread ID and session."""
        self._thread_id = str(uuid.uuid4())
        self._session_id = f"session-{uuid.uuid4()}"

    @property
    def session_id(self) -> str:
        """Get current session ID."""
        return self._session_id
    
    @property
    def user_id(self) -> str:
        """Get current user ID."""
        return self._user_id
    
    def set_user_id(self, user_id: str):
        """Update user ID for tracking."""
        self._user_id = user_id
