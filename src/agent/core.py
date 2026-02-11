"""OopsieAgent — LangGraph ReAct agent."""

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


def _get_langfuse_handler():
    """Return Langfuse callback handler if keys are configured, else None."""
    if os.getenv("LANGFUSE_SECRET_KEY") and os.getenv("LANGFUSE_PUBLIC_KEY"):
        try:
            from langfuse.langchain import CallbackHandler
            return CallbackHandler()
        except Exception:
            pass
    return None


class OopsieAgent:
    def __init__(self, model: str, api_key: str, base_url: str,
                 temperature: float = 0.7, max_tokens: int = 2048):
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
        self._langfuse = _get_langfuse_handler()

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
        """Extract the final text response from the message list.

        Some models (e.g. Kimi K2.5 via OpenRouter) put the text response
        in the same AIMessage that contains tool_calls, then return empty
        content on the follow-up call. Walk the messages in reverse to find
        the last AIMessage with actual text content.
        """
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content and msg.content.strip():
                return msg.content
        return "No pude generar una respuesta. Intenta de nuevo."

    def reset(self):
        """Start a new conversation by switching thread ID."""
        self._thread_id = str(uuid.uuid4())
