from __future__ import annotations

from typing import Dict, List, Optional, Union

from langchain_core.tools import tool

from .gmail_count import count_total_emails
from .gmail_draft import gmail_create_draft as gmail_create_draft_impl
from .gmail_unread import (
    get_unread_count,
    get_unread_email_summary,
)


@tool
def gmail_total_counts() -> Dict[str, int | None]:
    """Return total Gmail mailbox counts (messages and threads) for the authenticated user."""

    messages_total, threads_total = count_total_emails([])
    return {"messages_total": messages_total, "threads_total": threads_total}


@tool
def gmail_unread_count(query: str = "is:unread", batch_size: int = 500) -> int:
    """Return unread Gmail message count for the given Gmail search query."""

    return get_unread_count(query=query, batch_size=batch_size)


@tool
def gmail_unread_summary(
    limit: Optional[Union[str, int]] = 5, query: str = "is:unread"
) -> List[Dict[str, str]]:
    """Return unread Gmail email metadata (subject, sender, date, snippet)."""

    return get_unread_email_summary(limit=limit, query=query)


@tool
def gmail_create_draft(
    email_to: str,
    subject: str,
    body: str,
    email_from: str = "me",
) -> Dict | None:
    """Create a Gmail draft email and return the Gmail draft response payload."""

    return gmail_create_draft_impl(
        email_to=email_to,
        email_from=email_from,
        subject=subject,
        body=body,
    )
