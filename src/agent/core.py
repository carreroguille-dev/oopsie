"""OopsieAgent — LangGraph ReAct agent."""

import uuid
from datetime import datetime
from pathlib import Path

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
            state_modifier=_build_system_prompt(),
        )

        self._thread_id = str(uuid.uuid4())

    def process_message(self, user_message: str) -> str:
        """Process a user message. Returns the final text response."""
        config = {"configurable": {"thread_id": self._thread_id}}
        result = self.graph.invoke(
            {"messages": [("user", user_message)]},
            config=config,
        )
        return result["messages"][-1].content

    def reset(self):
        """Start a new conversation by switching thread ID."""
        self._thread_id = str(uuid.uuid4())
