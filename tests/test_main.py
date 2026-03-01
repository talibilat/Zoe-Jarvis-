from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage


def _load_main_module(monkeypatch):
    fake_speech = types.ModuleType("src.core.speech_service")
    fake_speech.speak_text = lambda _text: None
    fake_speech.transcribe_speech = lambda: None

    monkeypatch.setitem(sys.modules, "src.core.speech_service", fake_speech)
    sys.modules.pop("main", None)

    return importlib.import_module("main")


def test_main_loop_runs_conversation_and_logs(monkeypatch) -> None:
    main_module = _load_main_module(monkeypatch)

    app = MagicMock()
    stream_mock = MagicMock(
        return_value=[
            HumanMessage(content="hello"),
            AIMessage(content="assistant response"),
        ]
    )

    transcribe_mock = MagicMock(side_effect=["hello", "exit"])
    speak_mock = MagicMock()
    log_mock = MagicMock(return_value=Path("/tmp/logging.txt"))
    append_stream_chunks_mock = MagicMock()

    monkeypatch.setattr(main_module, "build_app", MagicMock(return_value=app))
    monkeypatch.setattr(main_module, "stream_agent_response", stream_mock)
    monkeypatch.setattr(main_module, "transcribe_speech", transcribe_mock)
    monkeypatch.setattr(main_module, "speak_text", speak_mock)
    monkeypatch.setattr(main_module, "log_conversation", log_mock)
    monkeypatch.setattr(main_module, "append_stream_chunks", append_stream_chunks_mock)
    monkeypatch.setattr(main_module, "format_system_line", lambda text, **_kwargs: text)
    monkeypatch.setattr(main_module, "format_user_line", lambda text: text)
    monkeypatch.setattr(main_module, "format_assistant_line", lambda text: text)

    main_module.main()

    stream_mock.assert_called_once()
    assert stream_mock.call_args.kwargs["stream_mode"] == ["messages", "updates"]
    speak_mock.assert_called_once_with("assistant response")
    log_mock.assert_called_once()


def test_main_uses_stream_modes_from_env(monkeypatch) -> None:
    main_module = _load_main_module(monkeypatch)

    app = MagicMock()
    stream_mock = MagicMock(
        return_value=[
            HumanMessage(content="hello"),
            AIMessage(content="assistant response"),
        ]
    )

    transcribe_mock = MagicMock(side_effect=["hello", "exit"])
    speak_mock = MagicMock()
    log_mock = MagicMock(return_value=Path("/tmp/logging.txt"))
    append_stream_chunks_mock = MagicMock()

    monkeypatch.setenv("STREAM_MODES", "values")
    monkeypatch.setattr(main_module, "build_app", MagicMock(return_value=app))
    monkeypatch.setattr(main_module, "stream_agent_response", stream_mock)
    monkeypatch.setattr(main_module, "transcribe_speech", transcribe_mock)
    monkeypatch.setattr(main_module, "speak_text", speak_mock)
    monkeypatch.setattr(main_module, "log_conversation", log_mock)
    monkeypatch.setattr(main_module, "append_stream_chunks", append_stream_chunks_mock)
    monkeypatch.setattr(main_module, "format_system_line", lambda text, **_kwargs: text)
    monkeypatch.setattr(main_module, "format_user_line", lambda text: text)
    monkeypatch.setattr(main_module, "format_assistant_line", lambda text: text)

    main_module.main()

    assert stream_mock.call_args.kwargs["stream_mode"] == ["values"]


def test_main_passes_streamed_chunks_to_log(monkeypatch) -> None:
    main_module = _load_main_module(monkeypatch)

    app = MagicMock()

    def fake_stream_agent_response(
        _app, _history, on_chunk, *, stream_mode, on_stream=None
    ):
        assert stream_mode == ["messages", "updates"]
        assert on_stream is not None
        on_chunk("Hel")
        on_chunk("lo")
        return [
            HumanMessage(content="hello"),
            AIMessage(content="Hello"),
        ]

    transcribe_mock = MagicMock(side_effect=["hello", "exit"])
    speak_mock = MagicMock()
    log_mock = MagicMock(return_value=Path("/tmp/logging.txt"))
    append_stream_chunks_mock = MagicMock()

    monkeypatch.setattr(main_module, "build_app", MagicMock(return_value=app))
    monkeypatch.setattr(
        main_module, "stream_agent_response", fake_stream_agent_response
    )
    monkeypatch.setattr(main_module, "transcribe_speech", transcribe_mock)
    monkeypatch.setattr(main_module, "speak_text", speak_mock)
    monkeypatch.setattr(main_module, "log_conversation", log_mock)
    monkeypatch.setattr(main_module, "append_stream_chunks", append_stream_chunks_mock)
    monkeypatch.setattr(main_module, "format_system_line", lambda text, **_kwargs: text)
    monkeypatch.setattr(main_module, "format_user_line", lambda text: text)
    monkeypatch.setattr(main_module, "format_assistant_line", lambda text: text)

    main_module.main()

    assert log_mock.call_args.kwargs["stream_chunks"] == [["Hel", "lo"]]
    append_stream_chunks_mock.assert_called_once_with(
        1,
        ["Hel", "lo"],
        start_chunk_index=1,
        initialize=True,
    )


def test_main_loop_skips_logging_when_no_conversation(monkeypatch) -> None:
    main_module = _load_main_module(monkeypatch)

    transcribe_mock = MagicMock(side_effect=["exit"])
    log_mock = MagicMock()

    monkeypatch.setattr(main_module, "build_app", MagicMock(return_value=MagicMock()))
    monkeypatch.setattr(main_module, "transcribe_speech", transcribe_mock)
    monkeypatch.setattr(main_module, "log_conversation", log_mock)
    monkeypatch.setattr(main_module, "format_system_line", lambda text, **_kwargs: text)
    monkeypatch.setattr(main_module, "format_user_line", lambda text: text)
    monkeypatch.setattr(main_module, "format_assistant_line", lambda text: text)

    main_module.main()

    log_mock.assert_not_called()
