from __future__ import annotations

import builtins
from unittest.mock import MagicMock

import pytest

import src.core.clients.llm_client as llm_client


def _clear_llm_env(monkeypatch) -> None:
    for key in (
        "LLM_PROVIDER",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT",
        "AZURE_OPENAI_API_VERSION",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "ANTHROPIC_API_KEY",
        "CLAUDE_API_KEY",
        "CLAUDE_MODEL",
        "OLLAMA_MODEL",
        "OLLAMA_BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)


def test_short_error_behavior() -> None:
    assert llm_client._short_error(Exception()) == "Exception"

    long_message = "x" * 300
    assert llm_client._short_error(Exception(long_message)).endswith("...")


def test_resolve_forced_provider(monkeypatch) -> None:
    _clear_llm_env(monkeypatch)
    assert llm_client._resolve_forced_provider() is None

    monkeypatch.setenv("LLM_PROVIDER", "azure")
    assert llm_client._resolve_forced_provider() == "azure_openai"


def test_resolve_forced_provider_invalid_value(monkeypatch) -> None:
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "invalid-provider")

    with pytest.raises(RuntimeError, match="Unsupported LLM_PROVIDER"):
        llm_client._resolve_forced_provider()


def test_discover_candidates_openai(monkeypatch) -> None:
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")

    captured = {}

    class FakeOpenAI:
        def __init__(self, *, api_key: str, model: str):
            captured["api_key"] = api_key
            captured["model"] = model

    monkeypatch.setattr(llm_client, "ChatOpenAI", FakeOpenAI)

    candidates = llm_client._discover_candidates()

    assert [candidate.provider_id for candidate in candidates] == ["openai"]
    candidates[0].make_model()
    assert captured == {"api_key": "test-key", "model": "gpt-test"}


def test_discover_candidates_claude_without_dependency(monkeypatch) -> None:
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(llm_client, "ChatAnthropic", None)

    candidates = llm_client._discover_candidates()

    assert [candidate.provider_id for candidate in candidates] == ["claude"]
    with pytest.raises(RuntimeError, match="langchain-anthropic"):
        candidates[0].make_model()


def test_discover_candidates_ollama_defaults_model(monkeypatch) -> None:
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")

    captured = {}

    class FakeOllama:
        def __init__(self, *, model: str, base_url: str | None):
            captured["model"] = model
            captured["base_url"] = base_url

    monkeypatch.setattr(llm_client, "ChatOllama", FakeOllama)

    candidates = llm_client._discover_candidates()

    assert [candidate.provider_id for candidate in candidates] == ["ollama"]
    candidates[0].make_model()
    assert captured == {
        "model": "llama3.1",
        "base_url": "http://localhost:11434",
    }


def test_validate_candidates_splits_working_and_failed(monkeypatch) -> None:
    monkeypatch.setattr(llm_client, "format_system_line", lambda text, **_kwargs: text)

    class WorkingModel:
        def __init__(self):
            self.calls = 0

        def invoke(self, _messages) -> None:
            self.calls += 1

    class BrokenModel:
        def invoke(self, _messages) -> None:
            raise RuntimeError("boom")

    good_model = WorkingModel()
    good = llm_client.ProviderCandidate(
        provider_id="good",
        display_name="Good",
        make_model=lambda: good_model,
    )
    bad = llm_client.ProviderCandidate(
        provider_id="bad",
        display_name="Bad",
        make_model=lambda: BrokenModel(),
    )

    working, failed = llm_client._validate_candidates([good, bad])

    assert working == [(good, good_model)]
    assert failed == [(bad, "boom")]
    assert good_model.calls == 1


def test_choose_model_with_forced_provider(monkeypatch) -> None:
    monkeypatch.setattr(llm_client, "_resolve_forced_provider", lambda: "openai")
    monkeypatch.setattr(llm_client, "format_system_line", lambda text, **_kwargs: text)

    openai_candidate = llm_client.ProviderCandidate("openai", "OpenAI", lambda: None)
    openai_model = object()

    selected_candidate, selected_model = llm_client._choose_model(
        working=[(openai_candidate, openai_model)],
        prompt_on_multiple=True,
    )

    assert selected_candidate is openai_candidate
    assert selected_model is openai_model


def test_choose_model_forced_provider_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(llm_client, "_resolve_forced_provider", lambda: "azure_openai")

    openai_candidate = llm_client.ProviderCandidate("openai", "OpenAI", lambda: None)

    with pytest.raises(RuntimeError, match="not available"):
        llm_client._choose_model(
            working=[(openai_candidate, object())],
            prompt_on_multiple=True,
        )


def test_choose_model_defaults_first_when_non_interactive(monkeypatch) -> None:
    monkeypatch.setattr(llm_client, "_resolve_forced_provider", lambda: None)
    monkeypatch.setattr(llm_client, "format_system_line", lambda text, **_kwargs: text)
    monkeypatch.setattr(
        llm_client.sys,
        "stdin",
        type("FakeStdin", (), {"isatty": lambda self: False})(),
    )

    first = (llm_client.ProviderCandidate("openai", "OpenAI", lambda: None), object())
    second = (llm_client.ProviderCandidate("ollama", "Ollama", lambda: None), object())

    selected_candidate, _ = llm_client._choose_model(
        working=[first, second],
        prompt_on_multiple=True,
    )

    assert selected_candidate is first[0]


def test_choose_model_interactive_selection(monkeypatch) -> None:
    monkeypatch.setattr(llm_client, "_resolve_forced_provider", lambda: None)
    monkeypatch.setattr(llm_client, "format_system_line", lambda text, **_kwargs: text)
    monkeypatch.setattr(
        llm_client.sys,
        "stdin",
        type("FakeStdin", (), {"isatty": lambda self: True})(),
    )

    answers = iter(["invalid", "2"])
    monkeypatch.setattr(builtins, "input", lambda _prompt: next(answers))

    first = (llm_client.ProviderCandidate("openai", "OpenAI", lambda: None), object())
    second_model = object()
    second = (
        llm_client.ProviderCandidate("ollama", "Ollama", lambda: None),
        second_model,
    )

    selected_candidate, selected_model = llm_client._choose_model(
        working=[first, second],
        prompt_on_multiple=True,
    )

    assert selected_candidate is second[0]
    assert selected_model is second_model


def test_build_chat_model_raises_when_no_candidates(monkeypatch) -> None:
    monkeypatch.setattr(llm_client, "_discover_candidates", lambda: [])

    with pytest.raises(RuntimeError, match="No model credentials found"):
        llm_client.build_chat_model()


def test_build_chat_model_raises_when_validation_fails(monkeypatch) -> None:
    candidate = llm_client.ProviderCandidate("openai", "OpenAI", lambda: None)
    monkeypatch.setattr(llm_client, "_discover_candidates", lambda: [candidate])
    monkeypatch.setattr(
        llm_client,
        "_validate_candidates",
        lambda _candidates: ([], [(candidate, "bad key")]),
    )

    with pytest.raises(
        RuntimeError, match="No configured provider passed verification"
    ):
        llm_client.build_chat_model()


def test_build_chat_model_binds_tools_when_supplied(monkeypatch) -> None:
    candidate = llm_client.ProviderCandidate("openai", "OpenAI", lambda: None)
    model = MagicMock()
    model.bind_tools.return_value = "bound-model"

    monkeypatch.setattr(llm_client, "_discover_candidates", lambda: [candidate])
    monkeypatch.setattr(
        llm_client,
        "_validate_candidates",
        lambda _candidates: ([(candidate, model)], []),
    )
    monkeypatch.setattr(
        llm_client,
        "_choose_model",
        lambda **_kwargs: (candidate, model),
    )
    monkeypatch.setattr(llm_client, "format_system_line", lambda text, **_kwargs: text)

    result = llm_client.build_chat_model(tools=["tool-1"], prompt_on_multiple=False)

    assert result == "bound-model"
    model.bind_tools.assert_called_once_with(["tool-1"])


def test_build_chat_model_returns_raw_model_without_tools(monkeypatch) -> None:
    candidate = llm_client.ProviderCandidate("openai", "OpenAI", lambda: None)
    model = MagicMock()

    monkeypatch.setattr(llm_client, "_discover_candidates", lambda: [candidate])
    monkeypatch.setattr(
        llm_client,
        "_validate_candidates",
        lambda _candidates: ([(candidate, model)], []),
    )
    monkeypatch.setattr(
        llm_client,
        "_choose_model",
        lambda **_kwargs: (candidate, model),
    )
    monkeypatch.setattr(llm_client, "format_system_line", lambda text, **_kwargs: text)

    result = llm_client.build_chat_model(tools=None, prompt_on_multiple=False)

    assert result is model
    model.bind_tools.assert_not_called()
