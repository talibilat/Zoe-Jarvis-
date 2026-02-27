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


def test_get_last_ai_message_returns_latest_ai(monkeypatch) -> None:
    main_module = _load_main_module(monkeypatch)

    messages = [
        HumanMessage(content="hello"),
        AIMessage(content="first"),
        AIMessage(content="second"),
    ]

    result = main_module.get_last_ai_message(messages)

    assert isinstance(result, AIMessage)
    assert result.content == "second"


def test_build_model_call_invokes_llm_with_system_prompt(monkeypatch) -> None:
    main_module = _load_main_module(monkeypatch)
    llm = MagicMock()
    llm.invoke.return_value = AIMessage(content="ok")

    model_call = main_module.build_model_call(llm)
    result = model_call({"messages": [HumanMessage(content="hi")]})

    assert result == {"messages": [llm.invoke.return_value]}


def test_main_loop_runs_conversation_and_logs(monkeypatch) -> None:
    main_module = _load_main_module(monkeypatch)

    app = MagicMock()
    app.invoke.return_value = {
        "messages": [
            HumanMessage(content="hello"),
            AIMessage(content="assistant response"),
        ]
    }

    transcribe_mock = MagicMock(side_effect=["hello", "exit"])
    speak_mock = MagicMock()
    log_mock = MagicMock(return_value=Path("/tmp/logging.txt"))

    monkeypatch.setattr(main_module, "build_app", MagicMock(return_value=app))
    monkeypatch.setattr(main_module, "transcribe_speech", transcribe_mock)
    monkeypatch.setattr(main_module, "speak_text", speak_mock)
    monkeypatch.setattr(main_module, "log_conversation", log_mock)
    monkeypatch.setattr(main_module, "format_system_line", lambda text, **_kwargs: text)
    monkeypatch.setattr(main_module, "format_user_line", lambda text: text)
    monkeypatch.setattr(main_module, "format_assistant_line", lambda text: text)

    main_module.main()

    app.invoke.assert_called_once()
    speak_mock.assert_called_once_with("assistant response")
    log_mock.assert_called_once()


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
