"""Email tool registry that combines all configured email providers."""

from __future__ import annotations

from src.tools.emails.gmail import GMAIL_TOOLS

EMAIL_PROVIDER_TOOLS = {
    "gmail": GMAIL_TOOLS,
}


def get_email_tools() -> list:
    tools = []
    for provider_tools in EMAIL_PROVIDER_TOOLS.values():
        tools.extend(provider_tools)
    return tools


EMAIL_TOOLS = get_email_tools()

__all__ = ["EMAIL_PROVIDER_TOOLS", "EMAIL_TOOLS", "get_email_tools"]
