from __future__ import annotations

from pathlib import Path
from typing import Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

BASE_DIR = Path(__file__).resolve().parents[1]
LOG_FILE = BASE_DIR / "logging.txt"


def log_conversation(messages: Sequence[BaseMessage]) -> Path:
    """Persist the full conversation to a simple text log."""

    with LOG_FILE.open("w", encoding="utf-8") as file:
        file.write("Your Conversation Log:\n")
        for message in messages:
            content = (
                message.content if isinstance(message.content, str) else str(message.content)
            )
            if isinstance(message, HumanMessage):
                prefix = "You"
                suffix = "\n"
            elif isinstance(message, AIMessage):
                prefix = "AI"
                suffix = "\n\n"
            elif isinstance(message, ToolMessage):
                prefix = "Tool"
                suffix = "\n"
            else:
                prefix = message.__class__.__name__
                suffix = "\n"
            file.write(f"{prefix}: {content}{suffix}")
        file.write("End of Conversation\n")

    return LOG_FILE
