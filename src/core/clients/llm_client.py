from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Callable, Sequence

from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from langchain_openai import AzureChatOpenAI, ChatOpenAI

try:
    from langchain_anthropic import ChatAnthropic
except ImportError:  # pragma: no cover - handled at runtime when Claude is requested.
    ChatAnthropic = None


PROVIDER_ALIASES = {
    "azure": "azure_openai",
    "azure_openai": "azure_openai",
    "openai": "openai",
    "claude": "claude",
    "anthropic": "claude",
    "ollama": "ollama",
}

PROVIDER_PING_MESSAGE = "Reply with exactly OK."


@dataclass(frozen=True)
class ProviderCandidate:
    provider_id: str
    display_name: str
    make_model: Callable[[], object]


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _short_error(exc: Exception) -> str:
    message = str(exc).strip()
    if not message:
        return exc.__class__.__name__
    first_line = message.splitlines()[0]
    return first_line if len(first_line) <= 220 else f"{first_line[:217]}..."


def _resolve_forced_provider() -> str | None:
    configured = _env("LLM_PROVIDER").lower()
    if not configured:
        return None
    normalized = PROVIDER_ALIASES.get(configured)
    if normalized:
        return normalized
    accepted = ", ".join(sorted(PROVIDER_ALIASES))
    raise RuntimeError(
        f"Unsupported LLM_PROVIDER='{configured}'. Supported values: {accepted}"
    )


def _discover_candidates() -> list[ProviderCandidate]:
    candidates: list[ProviderCandidate] = []

    azure_key = _env("AZURE_OPENAI_API_KEY")
    azure_endpoint = _env("AZURE_OPENAI_ENDPOINT")
    azure_deployment = _env("AZURE_OPENAI_DEPLOYMENT")
    azure_api_version = _env("AZURE_OPENAI_API_VERSION")
    if all([azure_key, azure_endpoint, azure_deployment, azure_api_version]):
        candidates.append(
            ProviderCandidate(
                provider_id="azure_openai",
                display_name=f"Azure OpenAI ({azure_deployment})",
                make_model=lambda key=azure_key, endpoint=azure_endpoint, deployment=azure_deployment, version=azure_api_version: (
                    AzureChatOpenAI(
                        api_key=key,
                        azure_endpoint=endpoint,
                        azure_deployment=deployment,
                        api_version=version,
                    )
                ),
            )
        )

    openai_key = _env("OPENAI_API_KEY")
    openai_model = _env("OPENAI_MODEL") or "gpt-4o"
    if openai_key:
        candidates.append(
            ProviderCandidate(
                provider_id="openai",
                display_name=f"OpenAI ({openai_model})",
                make_model=lambda key=openai_key, model=openai_model: ChatOpenAI(
                    api_key=key,
                    model=model,
                ),
            )
        )

    claude_key = _env("ANTHROPIC_API_KEY") or _env("CLAUDE_API_KEY")
    claude_model = _env("CLAUDE_MODEL") or "claude-3-5-sonnet-latest"
    if claude_key:
        if ChatAnthropic is None:
            candidates.append(
                ProviderCandidate(
                    provider_id="claude",
                    display_name=f"Claude ({claude_model})",
                    make_model=lambda: (_ for _ in ()).throw(
                        RuntimeError(
                            "Claude support requires `langchain-anthropic`. Install it with: pip install langchain-anthropic"
                        )
                    ),
                )
            )
        else:
            candidates.append(
                ProviderCandidate(
                    provider_id="claude",
                    display_name=f"Claude ({claude_model})",
                    make_model=lambda key=claude_key, model=claude_model: ChatAnthropic(
                        anthropic_api_key=key,
                        model=model,
                    ),
                )
            )

    ollama_model = _env("OLLAMA_MODEL")
    ollama_base_url = _env("OLLAMA_BASE_URL")
    if ollama_model or ollama_base_url:
        resolved_model = ollama_model or "llama3.1"
        candidates.append(
            ProviderCandidate(
                provider_id="ollama",
                display_name=f"Ollama ({resolved_model})",
                make_model=lambda model=resolved_model, base_url=ollama_base_url: (
                    ChatOllama(
                        model=model,
                        base_url=base_url or None,
                    )
                ),
            )
        )

    return candidates


def _validate_candidates(
    candidates: Sequence[ProviderCandidate],
) -> tuple[list[tuple[ProviderCandidate, object]], list[tuple[ProviderCandidate, str]]]:
    working: list[tuple[ProviderCandidate, object]] = []
    failed: list[tuple[ProviderCandidate, str]] = []

    print("Validating configured LLM providers...")
    for candidate in candidates:
        print(f"- Testing {candidate.display_name}...")
        try:
            model = candidate.make_model()
            model.invoke([HumanMessage(content=PROVIDER_PING_MESSAGE)])
        except Exception as exc:
            reason = _short_error(exc)
            failed.append((candidate, reason))
            print(f"  Failed: {reason}")
            continue

        working.append((candidate, model))
        print("  OK")

    return working, failed


def _choose_model(
    working: Sequence[tuple[ProviderCandidate, object]],
    prompt_on_multiple: bool,
) -> tuple[ProviderCandidate, object]:
    forced_provider = _resolve_forced_provider()
    if forced_provider:
        for candidate, model in working:
            if candidate.provider_id == forced_provider:
                print(f"Using provider from LLM_PROVIDER='{forced_provider}'.")
                return candidate, model
        available = (
            ", ".join(candidate.provider_id for candidate, _ in working) or "none"
        )
        raise RuntimeError(
            f"LLM_PROVIDER='{forced_provider}' is not available. Verified providers: {available}"
        )

    if len(working) == 1:
        return working[0]

    if not prompt_on_multiple or not sys.stdin.isatty():
        print(
            f"Multiple providers are valid. Defaulting to {working[0][0].display_name}. "
            "Set LLM_PROVIDER to force a provider."
        )
        return working[0]

    print("Multiple providers are configured and working.")
    for index, (candidate, _) in enumerate(working, start=1):
        print(f"{index}. {candidate.display_name} [{candidate.provider_id}]")

    default_idx = 1
    while True:
        raw = input(
            f"Choose provider [1-{len(working)}] (default {default_idx}): "
        ).strip()
        if raw == "":
            return working[default_idx - 1]
        if raw.isdigit():
            selected_idx = int(raw)
            if 1 <= selected_idx <= len(working):
                return working[selected_idx - 1]
        print(f"Invalid choice '{raw}'. Enter a number between 1 and {len(working)}.")


def build_chat_model(tools: Sequence | None = None, prompt_on_multiple: bool = True):
    """Return a verified chat model bound to tools.

    Providers are detected from environment variables, validated with a test call,
    and selected via terminal prompt when multiple are available.
    """

    candidates = _discover_candidates()
    if not candidates:
        raise RuntimeError(
            "No model credentials found. Configure one of: "
            "Azure OpenAI (AZURE_OPENAI_*), OpenAI (OPENAI_API_KEY), "
            "Claude (ANTHROPIC_API_KEY or CLAUDE_API_KEY), or Ollama (OLLAMA_MODEL)."
        )

    working, failed = _validate_candidates(candidates)
    if not working:
        details = "\n".join(
            f"- {candidate.display_name}: {reason}" for candidate, reason in failed
        )
        raise RuntimeError(f"No configured provider passed verification.\n{details}")

    selected_provider, selected_model = _choose_model(
        working=working,
        prompt_on_multiple=prompt_on_multiple,
    )
    print(f"Using provider: {selected_provider.display_name}")
    return selected_model.bind_tools(tools) if tools else selected_model
