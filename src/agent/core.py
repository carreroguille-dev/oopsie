import contextlib
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from src.notion_cache.space_cache import SpaceCache

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 10

_PROMPT_PATH = Path(__file__).parent / "prompts" / "system_prompt.txt"
_DAYS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def _build_system_prompt(space_cache: SpaceCache | None = None, timezone: str = "Europe/Madrid") -> str:
    """Load system prompt template, inject current date and cached spaces."""
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    now = datetime.now(ZoneInfo(timezone))
    day_name = _DAYS_ES[now.weekday()]
    today = now.strftime(f"%d/%m/%Y ({day_name})")
    prompt = template.format(current_date=today)

    if space_cache:
        spaces = space_cache.get_spaces()
        if spaces:
            prompt += "\n\n<espacios_disponibles uso=\"interno\">\n"
            for name, space_id in spaces.items():
                prompt += f'<space name="{name}" id="{space_id}"/>\n'
            prompt += "</espacios_disponibles>"

    return prompt


class OopsieAgent:
    def __init__(self, model: str, api_key: str, base_url: str,
                 temperature: float, max_tokens: int, tools: list,
                 user_id: str = None, space_cache: SpaceCache | None = None,
                 model_kwargs: dict | None = None, timezone: str = "UTC"):
        logger.info("Initializing OopsieAgent with model=%s, base_url=%s, temperature=%.2f, max_tokens=%d",
                   model, base_url, temperature, max_tokens)

        self._space_cache = space_cache
        self._timezone = timezone

        extra = dict(model_kwargs or {})
        top_p = extra.pop("top_p", None)

        llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            extra_body=extra if extra else None,
        )

        self.graph = create_react_agent(
            model=llm,
            tools=tools,
            checkpointer=MemorySaver(),
            prompt=lambda state: [SystemMessage(content=_build_system_prompt(self._space_cache, self._timezone))] + state["messages"],
        )

        self._thread_id = str(uuid.uuid4())
        self._session_id = f"session-{uuid.uuid4()}"
        self._user_id = user_id
        self._model = model
        self._langfuse_enabled = self._check_langfuse()

        logger.info("OopsieAgent initialized with thread_id=%s, session_id=%s",
                   self._thread_id, self._session_id)

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
            from langfuse.langchain import CallbackHandler  # v3 canonical path
            return CallbackHandler
        except ImportError:
            from langfuse.callback import CallbackHandler  # v2 fallback
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

    async def process_message(self, user_message: str) -> str:
        """Process a user message. Returns the final text response."""
        logger.debug("Processing message (length=%d chars)", len(user_message))

        config = {"configurable": {"thread_id": self._thread_id}}

        handler = self._create_langfuse_handler()
        if handler:
            config["callbacks"] = [handler]
            config["metadata"] = self._langfuse_metadata()
            logger.debug("Langfuse handler attached to request")

        try:
            ctx = (
                handler.client.start_as_current_span(name="oopsie-agent")
                if handler
                else contextlib.nullcontext()
            )
            with ctx:
                result = await self.graph.ainvoke(
                    {"messages": [("user", user_message)]},
                    config=config,
                )
            response = self._extract_response(result["messages"])
            await self._trim_history(config, result["messages"])
            logger.info("Message processed successfully, response length=%d chars", len(response))
            return response
        except Exception as e:
            logger.error("Failed to process message", exc_info=True)
            raise
        finally:
            if handler:
                handler.client.flush()

    async def _trim_history(self, config: dict, messages: list) -> None:
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
        await self.graph.aupdate_state(config, {"messages": removals})
        logger.debug("Trimmed %d message(s) from history", len(to_drop))

    @staticmethod
    def _extract_response(messages: list) -> str:
        """Extract the final text response from the current turn only."""
        last_human_idx = 0
        for i, msg in enumerate(messages):
            if isinstance(msg, HumanMessage):
                last_human_idx = i

        for msg in reversed(messages[last_human_idx + 1:]):
            if isinstance(msg, AIMessage) and isinstance(msg.content, str) and msg.content.strip():
                logger.debug("AIMessage content type=%s, value=%r", type(msg.content), msg.content)
                return msg.content
        return "No pude generar una respuesta. Intenta de nuevo."

    def reset(self):
        """Start a new conversation by switching thread ID and session."""
        old_thread = self._thread_id
        self._thread_id = str(uuid.uuid4())
        self._session_id = f"session-{uuid.uuid4()}"
        logger.info("Conversation reset: old_thread=%s, new_thread=%s, new_session=%s",
                   old_thread, self._thread_id, self._session_id)

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
        logger.debug("User ID updated to: %s", user_id)
        self._user_id = user_id
