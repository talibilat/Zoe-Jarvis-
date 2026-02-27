from __future__ import annotations

import importlib
import sys
import types
from unittest.mock import MagicMock


def _load_speech_service_module(monkeypatch):
    fake_sr = types.ModuleType("speech_recognition")

    class WaitTimeoutError(Exception):
        pass

    class UnknownValueError(Exception):
        pass

    class FakeSource:
        pass

    class FakeMicrophone:
        def __init__(self, device_index=None):
            self.device_index = device_index

        def __enter__(self):
            return FakeSource()

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeRecognizer:
        def __init__(self):
            self.adjust_calls = 0
            self.listen_calls = 0

        def adjust_for_ambient_noise(self, source, duration=0.5) -> None:
            del source
            self.adjust_calls += 1
            self.last_duration = duration

        def listen(self, source, timeout=None, phrase_time_limit=None):
            del source
            self.listen_calls += 1
            self.last_timeout = timeout
            self.last_phrase_time_limit = phrase_time_limit
            return "audio-bytes"

        def recognize_google(self, audio):
            del audio
            return "  hello world  "

    fake_sr.Recognizer = FakeRecognizer
    fake_sr.Microphone = FakeMicrophone
    fake_sr.WaitTimeoutError = WaitTimeoutError
    fake_sr.UnknownValueError = UnknownValueError

    fake_pyttsx3 = types.ModuleType("pyttsx3")

    class FakeEngine:
        def __init__(self):
            self._voices = [types.SimpleNamespace(name="default voice", id="voice-1")]
            self.said = []
            self.run_calls = 0
            self.properties = {}

        def getProperty(self, name):
            if name == "voices":
                return self._voices
            return self.properties.get(name)

        def setProperty(self, name, value):
            self.properties[name] = value

        def say(self, text):
            self.said.append(text)

        def runAndWait(self):
            self.run_calls += 1

    engine = FakeEngine()
    fake_pyttsx3.init = lambda: engine

    monkeypatch.setitem(sys.modules, "speech_recognition", fake_sr)
    monkeypatch.setitem(sys.modules, "pyttsx3", fake_pyttsx3)
    sys.modules.pop("src.core.speech_service", None)

    module = importlib.import_module("src.core.speech_service")
    return module, engine


def test_speak_text_success(monkeypatch) -> None:
    speech_service, engine = _load_speech_service_module(monkeypatch)

    speech_service.speak_text("hello")

    assert engine.said == ["hello"]
    assert engine.run_calls == 1
    assert engine.properties["rate"] == 180
    assert engine.properties["volume"] == 1.0


def test_speak_text_logs_error_on_failure(monkeypatch) -> None:
    speech_service, _engine = _load_speech_service_module(monkeypatch)
    monkeypatch.setattr(
        speech_service.pyttsx3,
        "init",
        MagicMock(side_effect=RuntimeError("tts failure")),
    )
    error_mock = MagicMock()
    monkeypatch.setattr(speech_service.logging, "error", error_mock)

    speech_service.speak_text("hello")

    error_mock.assert_called_once()


def test_transcribe_speech_success_and_single_ambient_calibration(monkeypatch) -> None:
    speech_service, _engine = _load_speech_service_module(monkeypatch)
    speech_service._ambient_calibrated = False

    first = speech_service.transcribe_speech(timeout=1, phrase_time_limit=2)
    second = speech_service.transcribe_speech(timeout=1, phrase_time_limit=2)

    assert first == "hello world"
    assert second == "hello world"
    assert speech_service.recognizer.adjust_calls == 1
    assert speech_service.recognizer.listen_calls == 2


def test_transcribe_speech_handles_wait_timeout(monkeypatch) -> None:
    speech_service, _engine = _load_speech_service_module(monkeypatch)

    def _raise_timeout(*_args, **_kwargs):
        raise speech_service.sr.WaitTimeoutError()

    monkeypatch.setattr(speech_service.recognizer, "listen", _raise_timeout)
    info_mock = MagicMock()
    monkeypatch.setattr(speech_service.logging, "info", info_mock)

    assert speech_service.transcribe_speech() is None
    info_mock.assert_called_once()


def test_transcribe_speech_handles_unknown_value(monkeypatch) -> None:
    speech_service, _engine = _load_speech_service_module(monkeypatch)

    def _raise_unknown(*_args, **_kwargs):
        raise speech_service.sr.UnknownValueError()

    monkeypatch.setattr(speech_service.recognizer, "recognize_google", _raise_unknown)
    info_mock = MagicMock()
    monkeypatch.setattr(speech_service.logging, "info", info_mock)

    assert speech_service.transcribe_speech() is None
    info_mock.assert_called_once()


def test_transcribe_speech_handles_generic_listen_error(monkeypatch) -> None:
    speech_service, _engine = _load_speech_service_module(monkeypatch)

    def _raise_error(*_args, **_kwargs):
        raise RuntimeError("microphone failure")

    monkeypatch.setattr(speech_service.recognizer, "listen", _raise_error)
    error_mock = MagicMock()
    monkeypatch.setattr(speech_service.logging, "error", error_mock)

    assert speech_service.transcribe_speech() is None
    error_mock.assert_called_once()


def test_transcribe_speech_handles_generic_recognition_error(monkeypatch) -> None:
    speech_service, _engine = _load_speech_service_module(monkeypatch)

    def _raise_error(*_args, **_kwargs):
        raise RuntimeError("recognition failure")

    monkeypatch.setattr(speech_service.recognizer, "recognize_google", _raise_error)
    error_mock = MagicMock()
    monkeypatch.setattr(speech_service.logging, "error", error_mock)

    assert speech_service.transcribe_speech() is None
    error_mock.assert_called_once()
