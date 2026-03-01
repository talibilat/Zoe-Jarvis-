from __future__ import annotations

from unittest.mock import MagicMock

import src.core.terminal_ui as ui


def test_colors_enabled_prefers_no_color(monkeypatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("FORCE_COLOR", "1")

    assert ui._colors_enabled() is False


def test_colors_enabled_force_color(monkeypatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "1")

    assert ui._colors_enabled() is True


def test_colors_enabled_falls_back_to_tty(monkeypatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    fake_stdout = type("Stdout", (), {"isatty": lambda self: True})()
    monkeypatch.setattr(ui.sys, "stdout", fake_stdout)

    assert ui._colors_enabled() is True


def test_colorize_returns_plain_text_when_colors_disabled(monkeypatch) -> None:
    monkeypatch.setattr(ui, "_colors_enabled", lambda: False)

    assert ui.colorize("hello", tone="success", bold=True) == "hello"


def test_colorize_applies_ansi_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(ui, "_colors_enabled", lambda: True)

    colored = ui.colorize("hello", tone="success", bold=True)

    assert colored.startswith("\033[")
    assert colored.endswith(ui.RESET)
    assert "hello" in colored


def test_classify_user_text_categories() -> None:
    assert ui.classify_user_text("exit") == "user_command"
    assert ui.classify_user_text("What is this") == "user_question"
    assert ui.classify_user_text("check gmail unread") == "user_email"
    assert ui.classify_user_text("multiply 2 and 3") == "user_math"
    assert ui.classify_user_text("hello there") == "user_default"


def test_classify_assistant_text_categories() -> None:
    assert ui.classify_assistant_text("Could you confirm?") == "assistant_question"
    assert ui.classify_assistant_text("Sorry, I cannot do that") == "assistant_error"
    assert ui.classify_assistant_text("Done. I sent it") == "assistant_action"
    assert (
        ui.classify_assistant_text("The mailbox has 2 messages") == "assistant_default"
    )


def test_classify_assistant_stream_text_categories() -> None:
    assert ui.classify_assistant_stream_text('{"id":"1"}') == "assistant_structured"
    assert ui.classify_assistant_stream_text("[1, 2, 3]") == "assistant_structured"
    assert (
        ui.classify_assistant_stream_text("Could you confirm?") == "assistant_question"
    )


def test_format_assistant_stream_chunk_uses_stream_tone(monkeypatch) -> None:
    seen: dict[str, str] = {}

    def fake_colorize(text: str, *, tone: str, bold: bool = False) -> str:
        seen["tone"] = tone
        return f"{tone}:{text}:{bold}"

    monkeypatch.setattr(ui, "colorize", fake_colorize)

    result = ui.format_assistant_stream_chunk("{", accumulated_text='{"id":"1"}')

    assert result == "assistant_structured:{:False"
    assert seen["tone"] == "assistant_structured"


def test_format_assistant_output_formats_gmail_payload(monkeypatch) -> None:
    monkeypatch.setattr(ui, "_colors_enabled", lambda: False)
    payload = (
        '[{"subject":"Security alert","from":"Google <no-reply@accounts.google.com>",'
        '"date":"Sat, 28 Feb 2026 23:42:22 GMT",'
        '"snippet":"If you didn&#39;t allow this access"}]'
        " Here are your 1 most recent unread Gmail messages:"
    )

    formatted = ui.format_assistant_output(payload)

    assert formatted.startswith(
        "Zoe: Here are your 1 most recent unread Gmail messages:"
    )
    assert "  1. Security alert" in formatted
    assert "From: Google <no-reply@accounts.google.com>" in formatted
    assert "Snippet: If you didn't allow this access" in formatted


def test_format_assistant_output_defaults_for_plain_text(monkeypatch) -> None:
    monkeypatch.setattr(ui, "_colors_enabled", lambda: False)

    assert ui.format_assistant_output("Hello") == "Zoe: Hello"


def test_format_gmail_unread_summary_limits_visible_items(monkeypatch) -> None:
    monkeypatch.setattr(ui, "_colors_enabled", lambda: False)
    emails = [
        {
            "subject": f"Subject {index}",
            "from": "sender@example.com",
            "date": "Mon, 1 Mar 2026 10:00:00 +0000",
            "snippet": "Snippet text",
        }
        for index in range(1, 13)
    ]

    formatted = ui.format_gmail_unread_summary(
        emails,
        intro="Here are your emails:",
        max_items=10,
    )

    assert "1. Subject 1" in formatted
    assert "10. Subject 10" in formatted
    assert "11. Subject 11" not in formatted
    assert "... and 2 more emails." in formatted


def test_format_helpers_call_colorize(monkeypatch) -> None:
    colorize_mock = MagicMock(side_effect=lambda text, **_kwargs: text)
    monkeypatch.setattr(ui, "colorize", colorize_mock)

    assert ui.format_user_line("Hi") == "You: Hi"
    assert ui.format_assistant_line("Hello") == "Zoe: Hello"
    assert ui.format_system_line("Ready") == "Ready"

    assert colorize_mock.call_count == 3
