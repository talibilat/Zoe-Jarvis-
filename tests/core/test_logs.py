from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

import src.core.logs as logs


def test_log_conversation_writes_expected_sections(monkeypatch, tmp_path) -> None:
    log_path = tmp_path / "logging.txt"
    monkeypatch.setattr(logs, "LOG_FILE", log_path)

    messages = [
        HumanMessage(content="Hi"),
        AIMessage(content="Hello"),
        ToolMessage(content="tool output", tool_call_id="tool-1"),
        SystemMessage(content="system note"),
    ]

    result_path = logs.log_conversation(messages)

    assert result_path == log_path
    text = log_path.read_text(encoding="utf-8")
    assert text.startswith("Your Conversation Log:\n")
    assert "You: Hi\n" in text
    assert "AI: Hello\n\n" in text
    assert "Tool: tool output\n" in text
    assert "SystemMessage: system note\n" in text
    assert text.endswith("End of Conversation\n")


def test_log_conversation_includes_stream_chunks_section(monkeypatch, tmp_path) -> None:
    log_path = tmp_path / "logging.txt"
    monkeypatch.setattr(logs, "LOG_FILE", log_path)

    messages = [
        HumanMessage(content="Hi"),
        AIMessage(content="Hello there"),
    ]

    logs.log_conversation(messages, stream_chunks=[["Hel", "lo\nthere"]])

    text = log_path.read_text(encoding="utf-8")
    assert "Streaming Chunks:\n" in text
    assert "Turn 1:\n" in text
    assert "  1. Hel\n" in text
    assert "  2. lo\\nthere\n" in text


def test_append_stream_chunk_writes_live_updates(monkeypatch, tmp_path) -> None:
    log_path = tmp_path / "logging.txt"
    monkeypatch.setattr(logs, "LOG_FILE", log_path)

    logs.append_stream_chunk(1, "Hel", chunk_index=1, initialize=True)
    logs.append_stream_chunk(1, "lo\nthere", chunk_index=2)

    text = log_path.read_text(encoding="utf-8")
    assert text.startswith("Live Streaming Chunks:\n")
    assert "Turn 1, chunk 1: Hel\n" in text
    assert "Turn 1, chunk 2: lo\\nthere\n" in text


def test_log_conversation_redacts_email_addresses(monkeypatch, tmp_path) -> None:
    log_path = tmp_path / "logging.txt"
    monkeypatch.setattr(logs, "LOG_FILE", log_path)
    monkeypatch.setattr(logs, "REDACT_LOGS", True)

    messages = [
        HumanMessage(content="Email me at alice@example.com"),
        AIMessage(content="Will do."),
    ]

    logs.log_conversation(messages)

    text = log_path.read_text(encoding="utf-8")
    assert "alice@example.com" not in text
    assert "[REDACTED_EMAIL]" in text


def test_append_stream_chunks_appends_batch(monkeypatch, tmp_path) -> None:
    log_path = tmp_path / "logging.txt"
    monkeypatch.setattr(logs, "LOG_FILE", log_path)
    monkeypatch.setattr(logs, "REDACT_LOGS", False)

    logs.append_stream_chunks(
        2,
        ["A", "B"],
        start_chunk_index=3,
        initialize=True,
    )

    text = log_path.read_text(encoding="utf-8")
    assert "Turn 2, chunk 3: A\n" in text
    assert "Turn 2, chunk 4: B\n" in text
