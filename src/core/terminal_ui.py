from __future__ import annotations

import os
import sys


RESET = "\033[0m"

ANSI_COLORS = {
    "default": "0",
    "system": "94",
    "info": "96",
    "listening": "95",
    "prompt": "36",
    "success": "92",
    "warning": "93",
    "error": "91",
    "user_question": "96",
    "user_email": "35",
    "user_math": "93",
    "user_command": "91",
    "user_default": "97",
    "assistant_question": "93",
    "assistant_action": "92",
    "assistant_error": "91",
    "assistant_default": "97",
}

QUESTION_PREFIXES = (
    "what",
    "why",
    "how",
    "when",
    "where",
    "who",
    "can",
    "could",
    "would",
    "should",
    "do",
    "does",
    "did",
    "is",
    "are",
    "am",
    "will",
    "may",
)


def _colors_enabled() -> bool:
    if os.getenv("NO_COLOR"):
        return False
    if os.getenv("FORCE_COLOR"):
        return True
    return sys.stdout.isatty()


def colorize(text: str, *, tone: str = "default", bold: bool = False) -> str:
    if not _colors_enabled():
        return text

    color_code = ANSI_COLORS.get(tone, ANSI_COLORS["default"])
    prefix = f"\033[1;{color_code}m" if bold else f"\033[{color_code}m"
    return f"{prefix}{text}{RESET}"


def classify_user_text(text: str) -> str:
    normalized = text.strip().lower()

    if normalized in {"exit", "quit", "bye", "stop"}:
        return "user_command"
    if "?" in text or normalized.split(" ", 1)[0] in QUESTION_PREFIXES:
        return "user_question"
    if any(
        token in normalized for token in ("email", "gmail", "inbox", "unread", "draft")
    ):
        return "user_email"
    if any(
        token in normalized
        for token in (
            "add",
            "sum",
            "subtract",
            "minus",
            "multiply",
            "times",
            "calculate",
        )
    ):
        return "user_math"
    return "user_default"


def classify_assistant_text(text: str) -> str:
    normalized = text.strip().lower()

    if "?" in text:
        return "assistant_question"
    if any(
        token in normalized
        for token in (
            "sorry",
            "error",
            "failed",
            "cannot",
            "can't",
            "not able",
            "unable",
            "invalid",
        )
    ):
        return "assistant_error"
    if any(
        token in normalized
        for token in ("sure", "done", "created", "sent", "found", "here", "okay", "ok")
    ):
        return "assistant_action"
    return "assistant_default"


def format_user_line(text: str) -> str:
    return colorize(f"You: {text}", tone=classify_user_text(text), bold=True)


def format_assistant_line(text: str) -> str:
    return colorize(f"Zoe: {text}", tone=classify_assistant_text(text))


def format_system_line(text: str, *, tone: str = "system", bold: bool = False) -> str:
    return colorize(text, tone=tone, bold=bold)
