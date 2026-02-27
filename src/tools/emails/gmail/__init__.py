"""Gmail-specific tool wrappers and provider helpers."""

from .gmail_main import (
    gmail_create_draft,
    gmail_create_draft_with_attachments,
    gmail_send_email,
    gmail_send_email_with_attachments,
    gmail_total_counts,
    gmail_unread_count,
    gmail_unread_summary,
)

GMAIL_TOOLS = [
    gmail_total_counts,
    gmail_unread_count,
    gmail_unread_summary,
    gmail_create_draft,
    gmail_send_email,
    gmail_create_draft_with_attachments,
    gmail_send_email_with_attachments,
]

__all__ = [
    "gmail_total_counts",
    "gmail_unread_count",
    "gmail_unread_summary",
    "gmail_create_draft",
    "gmail_send_email",
    "gmail_create_draft_with_attachments",
    "gmail_send_email_with_attachments",
    "GMAIL_TOOLS",
]
