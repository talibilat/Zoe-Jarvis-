from __future__ import annotations

from src.tools import AGENT_TOOLS
from src.tools.emails.email_main import EMAIL_PROVIDER_TOOLS, EMAIL_TOOLS
from src.tools.emails.gmail import GMAIL_TOOLS
from src.tools.mathematical_operations import MATHEMATICAL_TOOLS


def _tool_names(tools: list) -> list[str]:
    return [tool.name for tool in tools]


def test_gmail_tools_registry_contains_expected_tools() -> None:
    expected = {
        "gmail_total_counts",
        "gmail_unread_count",
        "gmail_unread_summary",
        "gmail_list_labels",
        "gmail_create_label",
        "gmail_delete_label",
        "gmail_modify_message_labels",
        "gmail_modify_thread_labels",
        "gmail_enable_forwarding",
        "gmail_create_filter",
        "gmail_list_filters",
        "gmail_get_filter",
        "gmail_delete_filter",
        "gmail_list_messages",
        "gmail_search_messages",
        "gmail_search_threads",
        "gmail_chatty_threads",
        "gmail_create_draft",
        "gmail_send_email",
        "gmail_update_signature",
        "gmail_create_draft_with_attachments",
        "gmail_send_email_with_attachments",
    }

    assert set(_tool_names(GMAIL_TOOLS)) == expected


def test_email_registry_exposes_gmail_tools() -> None:
    assert EMAIL_PROVIDER_TOOLS["gmail"] == GMAIL_TOOLS
    assert set(_tool_names(EMAIL_TOOLS)) == set(_tool_names(GMAIL_TOOLS))


def test_agent_tools_combines_math_and_email_tools() -> None:
    assert AGENT_TOOLS == [*MATHEMATICAL_TOOLS, *EMAIL_TOOLS]


def test_agent_tool_names_are_unique() -> None:
    names = _tool_names(AGENT_TOOLS)
    assert len(names) == len(set(names))
