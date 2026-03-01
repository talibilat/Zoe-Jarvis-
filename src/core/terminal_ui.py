from __future__ import annotations

import ast
import html
import json
import os
import sys
from typing import Any, Sequence


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
    "assistant_structured": "96",
    "gmail_header": "92",
    "gmail_index": "94",
    "gmail_subject": "96",
    "gmail_sender": "95",
    "gmail_date": "93",
    "gmail_snippet": "37",
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


def classify_assistant_stream_text(text: str) -> str:
    normalized = text.lstrip()
    if normalized.startswith("[") or normalized.startswith("{"):
        return "assistant_structured"
    return classify_assistant_text(text)


def format_user_line(text: str) -> str:
    return colorize(f"You: {text}", tone=classify_user_text(text), bold=True)


def format_assistant_line(text: str) -> str:
    return colorize(f"Zoe: {text}", tone=classify_assistant_text(text))


def format_system_line(text: str, *, tone: str = "system", bold: bool = False) -> str:
    return colorize(text, tone=tone, bold=bold)


def _extract_first_list_literal(text: str) -> tuple[str, int, int] | None:
    start = -1
    depth = 0
    in_string = False
    quote_char = ""
    escaped = False

    for index, char in enumerate(text):
        if start == -1:
            if char == "[":
                start = index
                depth = 1
            continue

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote_char:
                in_string = False
            continue

        if char in {"'", '"'}:
            in_string = True
            quote_char = char
            continue

        if char == "[":
            depth += 1
            continue

        if char == "]":
            depth -= 1
            if depth == 0:
                end = index + 1
                return text[start:end], start, end

    return None


def _parse_list_literal(raw_text: str) -> list[Any] | None:
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(raw_text)
        except (SyntaxError, ValueError):
            return None

    return parsed if isinstance(parsed, list) else None


def _normalize_text(value: Any, *, fallback: str = "") -> str:
    text = html.unescape(str(value or fallback))
    return " ".join(text.split()) or fallback


def _truncate_text(text: str, *, max_chars: int = 220) -> str:
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 3].rstrip()}..."


def _extract_gmail_unread_payload(
    text: str,
) -> tuple[list[dict[str, str]], str] | None:
    literal_match = _extract_first_list_literal(text)
    if literal_match is None:
        return None

    raw_list, start, end = literal_match
    parsed = _parse_list_literal(raw_list)
    if not parsed:
        return None

    required_keys = {"subject", "from", "date", "snippet"}
    formatted_items: list[dict[str, str]] = []

    for item in parsed:
        if not isinstance(item, dict) or not required_keys.issubset(item.keys()):
            return None
        formatted_items.append(
            {
                "subject": _normalize_text(
                    item.get("subject"), fallback="(no subject)"
                ),
                "from": _normalize_text(item.get("from"), fallback="(unknown sender)"),
                "date": _normalize_text(item.get("date"), fallback="(no date)"),
                "snippet": _truncate_text(
                    _normalize_text(item.get("snippet"), fallback="(no snippet)")
                ),
            }
        )

    before = text[:start].strip()
    after = text[end:].strip()
    intro = " ".join(part for part in (before, after) if part)
    if not intro:
        intro = (
            f"Here are your {len(formatted_items)} most recent unread Gmail messages:"
        )

    return formatted_items, intro


def format_gmail_unread_summary(
    emails: Sequence[dict[str, str]], *, intro: str, max_items: int = 10
) -> str:
    lines = [colorize(f"Zoe: {intro}", tone="gmail_header", bold=True)]
    visible_emails = list(emails[:max_items])

    for index, email in enumerate(visible_emails, start=1):
        lines.append(
            (
                f"{colorize(f'  {index}.', tone='gmail_index', bold=True)} "
                f"{colorize(email['subject'], tone='gmail_subject', bold=True)}"
            )
        )
        lines.append(colorize(f"     From: {email['from']}", tone="gmail_sender"))
        lines.append(colorize(f"     Date: {email['date']}", tone="gmail_date"))
        lines.append(
            colorize(f"     Snippet: {email['snippet']}", tone="gmail_snippet")
        )

    hidden_count = len(emails) - len(visible_emails)
    if hidden_count > 0:
        lines.append(
            colorize(
                f"     ... and {hidden_count} more emails. Ask for CSV/export to view all.",
                tone="info",
            )
        )

    return "\n".join(lines)


def format_assistant_output(text: str) -> str:
    payload = _extract_gmail_unread_payload(text)
    if payload is None:
        return format_assistant_line(text)
    emails, intro = payload
    return format_gmail_unread_summary(emails, intro=intro)


def format_assistant_stream_chunk(chunk: str, *, accumulated_text: str) -> str:
    return colorize(
        chunk,
        tone=classify_assistant_stream_text(accumulated_text),
    )
