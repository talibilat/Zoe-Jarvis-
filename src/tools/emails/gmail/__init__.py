"""Gmail-specific tool wrappers and provider helpers."""

from .gmail_main import (
    gmail_create_draft,
    gmail_total_counts,
    gmail_unread_count,
    gmail_unread_summary,
)

GMAIL_TOOLS = [
    gmail_total_counts,
    gmail_unread_count,
    gmail_unread_summary,
    gmail_create_draft,
]

__all__ = [
    "gmail_total_counts",
    "gmail_unread_count",
    "gmail_unread_summary",
    "gmail_create_draft",
    "GMAIL_TOOLS",
]
