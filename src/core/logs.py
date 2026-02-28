from __future__ import annotations

from pathlib import Path
from typing import Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

BASE_DIR = Path(__file__).resolve().parents[1]
LOG_FILE = BASE_DIR / "logging.txt"
LIVE_STREAM_HEADER = "Live Streaming Chunks:\n"


def _format_chunk_line(chunk: str) -> str:
    return chunk.replace("\n", "\\n")


def append_stream_chunk(
    turn_index: int,
    chunk: str,
    *,
    chunk_index: int,
    initialize: bool = False,
) -> Path:
    """Append one streamed chunk to the log file during runtime."""

    if initialize or not LOG_FILE.exists():
        with LOG_FILE.open("w", encoding="utf-8") as file:
            file.write(LIVE_STREAM_HEADER)

    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(
            f"Turn {turn_index}, chunk {chunk_index}: {_format_chunk_line(chunk)}\n"
        )

    return LOG_FILE


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
