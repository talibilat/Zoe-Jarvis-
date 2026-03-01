from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

BASE_DIR = Path(__file__).resolve().parents[1]
LOG_FILE = BASE_DIR / "logging.txt"
LIVE_STREAM_HEADER = "Live Streaming Chunks:\n"
REDACT_LOGS = os.getenv("LOG_REDACT_SENSITIVE", "true").strip().lower() not in {
    "0",
    "false",
    "no",
}
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def _redact_sensitive_text(text: str) -> str:
    if not REDACT_LOGS:
        return text
    return EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)


def _format_chunk_line(chunk: str) -> str:
    return _redact_sensitive_text(chunk.replace("\n", "\\n"))


def append_stream_chunks(
    turn_index: int,
    chunks: Sequence[str],
    *,
    start_chunk_index: int = 1,
    initialize: bool = False,
) -> Path:
    """Append streamed chunks to the log file during runtime."""

    if not chunks:
        return LOG_FILE

    if initialize or not LOG_FILE.exists():
        with LOG_FILE.open("w", encoding="utf-8") as file:
            file.write(LIVE_STREAM_HEADER)

    with LOG_FILE.open("a", encoding="utf-8") as file:
        for offset, chunk in enumerate(chunks):
            chunk_index = start_chunk_index + offset
            file.write(
                f"Turn {turn_index}, chunk {chunk_index}: {_format_chunk_line(chunk)}\n"
            )

    return LOG_FILE


def append_stream_chunk(
    turn_index: int,
    chunk: str,
    *,
    chunk_index: int,
    initialize: bool = False,
) -> Path:
    """Append one streamed chunk to the log file during runtime."""

    return append_stream_chunks(
        turn_index,
        [chunk],
        start_chunk_index=chunk_index,
        initialize=initialize,
    )


def log_conversation(
    messages: Sequence[BaseMessage],
    *,
    stream_chunks: Sequence[Sequence[str]] | None = None,
) -> Path:
    """Persist the full conversation to a simple text log."""

    with LOG_FILE.open("w", encoding="utf-8") as file:
        file.write("Your Conversation Log:\n")
        for message in messages:
            content = (
                message.content
                if isinstance(message.content, str)
                else str(message.content)
            )
            content = _redact_sensitive_text(content)
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

        if stream_chunks:
            file.write("\nStreaming Chunks:\n")
            for turn_index, chunks in enumerate(stream_chunks, start=1):
                if not chunks:
                    continue
                file.write(f"Turn {turn_index}:\n")
                for chunk_index, chunk in enumerate(chunks, start=1):
                    file.write(f"  {chunk_index}. {_format_chunk_line(chunk)}\n")

        file.write("End of Conversation\n")

    return LOG_FILE
