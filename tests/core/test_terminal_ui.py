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


def test_format_helpers_call_colorize(monkeypatch) -> None:
    colorize_mock = MagicMock(side_effect=lambda text, **_kwargs: text)
    monkeypatch.setattr(ui, "colorize", colorize_mock)

    assert ui.format_user_line("Hi") == "You: Hi"
    assert ui.format_assistant_line("Hello") == "Zoe: Hello"
    assert ui.format_system_line("Ready") == "Ready"

    assert colorize_mock.call_count == 3
