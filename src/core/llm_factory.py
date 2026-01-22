from __future__ import annotations

import os
from typing import Sequence

from langchain_openai import AzureChatOpenAI, ChatOpenAI


def build_chat_model(tools: Sequence | None = None):
    """Return a chat model bound to tools, preferring Azure OpenAI when configured."""

    azure_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION")

    openai_key = os.getenv("OPENAI_API_KEY")
    openai_model = (os.getenv("OPENAI_MODEL") or "gpt-4o").strip() or "gpt-4o"

    if azure_key and azure_endpoint and azure_deployment and azure_api_version:
        print(f"Using Azure OpenAI deployment '{azure_deployment}' (version {azure_api_version}).")
        llm = AzureChatOpenAI(
            azure_deployment=azure_deployment,
            api_version=azure_api_version,
            azure_endpoint=azure_endpoint,
        )
    elif openai_key:
        print(f"Using OpenAI model '{openai_model}'.")
        llm = ChatOpenAI(model=openai_model)
    else:
        raise RuntimeError(
            "No model credentials found. Set Azure OpenAI env vars or OPENAI_API_KEY."
        )

    return llm.bind_tools(tools) if tools else llm
