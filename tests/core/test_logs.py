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
