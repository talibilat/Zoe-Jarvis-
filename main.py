from __future__ import annotations

import ast
import json
import os
from typing import Any, List

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)

from src.agent import (
    DEFAULT_STREAM_MODES,
    build_app,
    get_last_ai_text,
    resolve_stream_modes,
    stream_agent_response,
)
from src.core.logger import configure_logger, logger
from src.core.logs import append_stream_chunks, log_conversation
from src.core.speech_service import speak_text, transcribe_speech
from src.core.terminal_ui import (
    format_assistant_output,
    format_assistant_line,
    format_assistant_stream_chunk,
    format_system_line,
    format_user_line,
)


def _log(message: str, *, level: str = "INFO") -> None:
    logger.log(level, message)


def _log_blank_line() -> None:
    _log("")


def _log_inline(message: str) -> None:
    logger.opt(raw=True).log("INFO", message)


def _preview_text(value: Any, *, max_length: int = 80) -> str:
    text = " ".join(str(value).split())
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3].rstrip()}..."


def _is_json_like(text: str) -> bool:
    stripped = text.lstrip()
    return stripped.startswith("{") or stripped.startswith("[")


def _parse_json_like(text: str) -> Any | None:
    stripped = text.strip()
    if not _is_json_like(stripped):
        return None

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        try:
            return ast.literal_eval(stripped)
        except (SyntaxError, ValueError):
            return None


def _summarize_tool_args(args: Any) -> str:
    if not isinstance(args, dict) or not args:
        return "no arguments"

    parts: List[str] = []
    for index, (key, value) in enumerate(args.items(), start=1):
        if index > 3:
            parts.append("...")
            break
        parts.append(f"{key}={_preview_text(value, max_length=40)}")
    return ", ".join(parts)


def _summarize_tool_result(content: Any) -> str:
    text = content if isinstance(content, str) else str(content)
    parsed = _parse_json_like(text)

    if isinstance(parsed, list):
        if not parsed:
            return "0 records"
        if all(isinstance(item, dict) for item in parsed):
            return f"{len(parsed)} records"
        return f"{len(parsed)} items"

    if isinstance(parsed, dict):
        if parsed.get("error"):
            return f"error: {_preview_text(parsed['error'])}"
        keys = list(parsed.keys())
        key_preview = ", ".join(keys[:5])
        if len(keys) > 5:
            key_preview += ", ..."
        return f"object keys: {key_preview or '(none)'}"

    lowered = text.lower()
    if "httperror" in lowered or "insufficient permission" in lowered:
        return _preview_text(text, max_length=160)
    return _preview_text(text, max_length=120)


def _extract_updates_payload(chunk: Any) -> dict[str, Any] | None:
    payload = chunk
    if (
        isinstance(chunk, tuple)
        and len(chunk) == 2
        and isinstance(chunk[0], tuple)
        and isinstance(chunk[1], dict)
    ):
        payload = chunk[1]

    return payload if isinstance(payload, dict) else None


def _extract_balanced_json_segment(text: str, start: int) -> tuple[str, int] | None:
    if start < 0 or start >= len(text):
        return None

    opening = text[start]
    if opening not in {"[", "{"}:
        return None
    closing = "]" if opening == "[" else "}"

    depth = 0
    in_string = False
    escaped = False
    quote_char = ""

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote_char:
                in_string = False
            continue

        if char in {'"', "'"}:
            in_string = True
            quote_char = char
            continue

        if char == opening:
            depth += 1
            continue
        if char == closing:
            depth -= 1
            if depth == 0:
                return text[start : index + 1], index + 1

    return None


def _strip_embedded_json_payloads(text: str) -> str:
    if not text:
        return text

    output_parts: list[str] = []
    index = 0

    while index < len(text):
        char = text[index]
        if char not in {"[", "{"}:
            output_parts.append(char)
            index += 1
            continue

        segment = _extract_balanced_json_segment(text, index)
        if segment is None:
            output_parts.append(char)
            index += 1
            continue

        raw_segment, end_index = segment
        parsed = _parse_json_like(raw_segment)
        if isinstance(parsed, (list, dict)):
            index = end_index
            while index < len(text) and text[index].isspace():
                index += 1
            continue

        output_parts.append(char)
        index += 1

    sanitized = "".join(output_parts).strip()
    return sanitized or text


def _safe_speak(text: str) -> None:
    try:
        speak_text(text)
    except KeyboardInterrupt:
        _log_blank_line()
        _log(
            format_system_line("Speech playback interrupted.", tone="warning"),
            level="WARNING",
        )
    except Exception as error:  # pragma: no cover - dependent on local TTS runtime
        _log(
            format_system_line(
                f"Speech playback failed: {error}",
                tone="warning",
            ),
            level="WARNING",
        )


def main() -> None:
    configure_logger()
    app = build_app()
    stream_modes = resolve_stream_modes(os.getenv("STREAM_MODES"))
    conversation_history: List[BaseMessage] = []
    streamed_chunk_log: List[List[str]] = []
    live_stream_log_initialized = False
    turn_count = 0
    missed_input_count = 0

    _log(
        format_system_line(
            "Say 'exit' to quit. I'm listening for your question or math problem.",
            tone="system",
            bold=True,
        )
    )
    if stream_modes != list(DEFAULT_STREAM_MODES):
        _log(
            format_system_line(
                f"Streaming modes: {', '.join(stream_modes)}", tone="info"
            )
        )
    while True:
        try:
            _log_blank_line()
            _log(format_system_line("Listening...", tone="listening", bold=True))
            user_input = transcribe_speech()
        except (EOFError, KeyboardInterrupt):
            _log_blank_line()
            break

        if user_input is None:
            missed_input_count += 1
            if missed_input_count == 1 or missed_input_count % 5 == 0:
                _log(
                    format_system_line(
                        "I didn't catch that. Please try again.",
                        tone="warning",
                    ),
                    level="WARNING",
                )
            continue

        user_input = user_input.strip()
        if not user_input:
            continue
        missed_input_count = 0

        _log(format_user_line(user_input))

        if user_input.lower() == "exit":
            break

        conversation_history.append(HumanMessage(content=user_input))
        turn_count += 1
        _log(format_system_line("[Phase] Analyzing your request...", tone="info"))
        streamed_chunks: List[str] = []
        pending_stream_log_chunks: List[str] = []
        logged_chunk_count = 0
        accumulated_text = ""
        stream_state = {
            "started": False,
            "mode": "undecided",
            "hide_remaining_tokens": False,
        }
        phase_state = {
            "seen_tool_calls": set(),
            "seen_tool_results": set(),
            "tool_names_by_call_id": {},
            "finalizing_printed": False,
        }

        def emit_phase(message: str, *, tone: str = "info") -> None:
            level = (
                "ERROR"
                if tone == "error"
                else "WARNING"
                if tone == "warning"
                else "INFO"
            )
            _log(format_system_line(f"[Phase] {message}", tone=tone), level=level)

        def on_stream(mode: str, chunk: Any) -> None:
            if mode != "updates":
                return

            payload = _extract_updates_payload(chunk)
            if payload is None:
                return

            for node_update in payload.values():
                if not isinstance(node_update, dict):
                    continue
                messages = node_update.get("messages")
                if not isinstance(messages, list):
                    continue

                for message in messages:
                    if isinstance(message, AIMessage):
                        tool_calls = getattr(message, "tool_calls", None) or []
                        if tool_calls:
                            for tool_call in tool_calls:
                                call_id = tool_call.get("id") or str(tool_call)
                                if call_id in phase_state["seen_tool_calls"]:
                                    continue
                                phase_state["seen_tool_calls"].add(call_id)
                                tool_name = tool_call.get("name", "tool")
                                phase_state["tool_names_by_call_id"][call_id] = (
                                    tool_name
                                )
                                args_summary = _summarize_tool_args(
                                    tool_call.get("args")
                                )
                                emit_phase(
                                    f"Calling `{tool_name}` ({args_summary}).",
                                    tone="info",
                                )
                        elif (
                            phase_state["seen_tool_calls"]
                            and not phase_state["finalizing_printed"]
                        ):
                            phase_state["finalizing_printed"] = True
                            emit_phase("Preparing final response.", tone="info")

                    if isinstance(message, ToolMessage):
                        stream_state["hide_remaining_tokens"] = True
                        result_id = message.tool_call_id or str(message)
                        if result_id in phase_state["seen_tool_results"]:
                            continue
                        phase_state["seen_tool_results"].add(result_id)
                        tool_name = phase_state["tool_names_by_call_id"].get(
                            result_id, "tool"
                        )
                        result_summary = _summarize_tool_result(message.content)
                        tone = (
                            "error"
                            if "error" in result_summary.lower()
                            or "insufficient permission" in result_summary.lower()
                            else "success"
                        )
                        emit_phase(
                            f"`{tool_name}` returned {result_summary}.",
                            tone=tone,
                        )

        def on_chunk(chunk: str) -> None:
            nonlocal live_stream_log_initialized
            nonlocal logged_chunk_count
            nonlocal accumulated_text

            streamed_chunks.append(chunk)
            pending_stream_log_chunks.append(chunk)
            if len(pending_stream_log_chunks) >= 8:
                append_stream_chunks(
                    turn_count,
                    list(pending_stream_log_chunks),
                    start_chunk_index=logged_chunk_count + 1,
                    initialize=not live_stream_log_initialized,
                )
                logged_chunk_count += len(pending_stream_log_chunks)
                pending_stream_log_chunks.clear()
                live_stream_log_initialized = True

            if stream_state["hide_remaining_tokens"]:
                return

            accumulated_text += chunk
            if stream_state["mode"] == "undecided":
                stripped = accumulated_text.lstrip()
                if not stripped:
                    return
                if _is_json_like(stripped):
                    stream_state["mode"] = "structured"
                    if not stream_state["started"]:
                        _log_blank_line()
                        _log_inline(format_assistant_line(""))
                        stream_state["started"] = True
                    _log_inline(
                        format_system_line(
                            " [Formatting data for readability...]",
                            tone="info",
                        )
                    )
                    return

                stream_state["mode"] = "plain"

            if not stream_state["started"]:
                _log_blank_line()
                _log_inline(format_assistant_line(""))
                stream_state["started"] = True
            if stream_state["mode"] == "structured":
                return
            _log_inline(
                format_assistant_stream_chunk(
                    chunk,
                    accumulated_text=accumulated_text,
                )
            )

        conversation_history = stream_agent_response(
            app,
            conversation_history,
            on_chunk,
            stream_mode=stream_modes,
            on_stream=on_stream,
        )
        if pending_stream_log_chunks:
            append_stream_chunks(
                turn_count,
                list(pending_stream_log_chunks),
                start_chunk_index=logged_chunk_count + 1,
                initialize=not live_stream_log_initialized,
            )
            logged_chunk_count += len(pending_stream_log_chunks)
            pending_stream_log_chunks.clear()
            live_stream_log_initialized = True
        if streamed_chunks:
            streamed_chunk_log.append(list(streamed_chunks))
        content = get_last_ai_text(conversation_history)
        content_for_output = (
            _strip_embedded_json_payloads(content)
            if stream_state["hide_remaining_tokens"]
            else content
        )

        if content_for_output:
            formatted_output = format_assistant_output(content_for_output)
            if stream_state["started"]:
                _log_blank_line()
                if stream_state[
                    "mode"
                ] == "structured" or formatted_output != format_assistant_line(
                    content_for_output
                ):
                    _log(formatted_output)
                    _log_blank_line()
                else:
                    _log_blank_line()
            else:
                _log_blank_line()
                _log(formatted_output)
                _log_blank_line()
            _safe_speak(content_for_output)
        else:
            _log_blank_line()
            _log(format_assistant_line("I was not able to generate a response."))
            _log_blank_line()

    if conversation_history:
        log_path = log_conversation(
            conversation_history,
            stream_chunks=streamed_chunk_log,
        )
        _log(
            format_system_line(
                f"Conversation saved to {log_path.name}", tone="success", bold=True
            )
        )
    else:
        _log(format_system_line("No conversation to save.", tone="info"))


if __name__ == "__main__":
    main()
