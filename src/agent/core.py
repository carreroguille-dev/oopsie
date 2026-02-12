import os
import uuid
from datetime import datetime
from pathlib import Path

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from src.agent.tools.definitions import ALL_TOOLS

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
        self._langfuse = self._get_langfuse_handler()

    def _get_langfuse_handler(self):
        """Return Langfuse callback handler if keys are configured, else None."""
        if os.getenv("LANGFUSE_SECRET_KEY") and os.getenv("LANGFUSE_PUBLIC_KEY"):
            try:
                from langfuse.langchain import CallbackHandler

                handler_kwargs = {
                    "session_id": self._session_id,
                    "tags": ["langgraph", "agent"],
                    "metadata": {"model": self._model}
                }

                if self._user_id:
                    handler_kwargs["user_id"] = self._user_id

                return CallbackHandler(**handler_kwargs)
            except Exception:
                pass
        return None

    def process_message(self, user_message: str) -> str:
        """Process a user message. Returns the final text response."""
        config = {"configurable": {"thread_id": self._thread_id}}

        if self._langfuse:
            config["callbacks"] = [self._langfuse]

        result = self.graph.invoke(
            {"messages": [("user", user_message)]},
            config=config,
        )
        return self._extract_response(result["messages"])

    @staticmethod
    def _extract_response(messages: list) -> str:
        """Extract the final text response from the message list."""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content and msg.content.strip():
                return msg.content
        return "No pude generar una respuesta. Intenta de nuevo."

    def reset(self):
        """Start a new conversation by switching thread ID."""
        self._thread_id = str(uuid.uuid4())
        self._session_id = f"session-{uuid.uuid4()}"
        
        self._langfuse = self._get_langfuse_handler()

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
