"""Tool implementations for the CLI agent."""

from .emails.email_main import EMAIL_TOOLS
from .emails.gmail import (
    gmail_chatty_threads,
    gmail_create_label,
    gmail_create_draft,
    gmail_create_draft_with_attachments,
    gmail_delete_label,
    gmail_list_labels,
    gmail_modify_message_labels,
    gmail_modify_thread_labels,
    gmail_search_messages,
    gmail_search_threads,
    gmail_send_email,
    gmail_send_email_with_attachments,
    gmail_total_counts,
    gmail_unread_count,
    gmail_unread_summary,
)
from .mathematical_operations import MATHEMATICAL_TOOLS, add, multiply, subtract

AGENT_TOOLS = [*MATHEMATICAL_TOOLS, *EMAIL_TOOLS]

__all__ = [
    "add",
    "subtract",
    "multiply",
    "gmail_total_counts",
    "gmail_unread_count",
    "gmail_unread_summary",
    "gmail_list_labels",
    "gmail_create_label",
    "gmail_delete_label",
    "gmail_modify_message_labels",
    "gmail_modify_thread_labels",
    "gmail_search_messages",
    "gmail_search_threads",
    "gmail_chatty_threads",
    "gmail_create_draft",
    "gmail_send_email",
    "gmail_create_draft_with_attachments",
    "gmail_send_email_with_attachments",
    "MATHEMATICAL_TOOLS",
    "EMAIL_TOOLS",
    "AGENT_TOOLS",
]
