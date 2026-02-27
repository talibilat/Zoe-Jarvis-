from __future__ import annotations

from typing import Dict, List, Optional, Union

from langchain_core.tools import tool

from .gmail_count import count_total_emails
from .gmail_draft import gmail_create_draft as gmail_create_draft_impl
from .gmail_send_email import gmail_send_email as gmail_send_email_impl
from .gmail_threads import show_chatty_threads as show_chatty_threads_impl
from .gmail_upload import (
    gmail_create_draft_with_attachments as gmail_create_draft_with_attachments_impl,
    gmail_send_email_with_attachments as gmail_send_email_with_attachments_impl,
)
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
def gmail_chatty_threads(
    min_messages: int = 3,
    max_threads: int = 100,
    query: Optional[str] = None,
) -> List[Dict[str, int | str]]:
    """Return thread metadata for longer conversations (default: >=3 messages)."""

    return show_chatty_threads_impl(
        min_messages=min_messages,
        max_threads=max_threads,
        query=query,
    )


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


@tool
def gmail_send_email(
    email_to: str,
    subject: str,
    body: str,
    email_from: str = "me",
) -> Dict | None:
    """Send a Gmail email and return the Gmail send response payload."""

    return gmail_send_email_impl(
        email_to=email_to,
        email_from=email_from,
        subject=subject,
        body=body,
    )


@tool
def gmail_create_draft_with_attachments(
    email_to: str,
    subject: str,
    body: str,
    attachment_paths: List[str],
    email_from: str = "me",
) -> Dict | None:
    """Create a Gmail draft with one or more file attachments."""

    return gmail_create_draft_with_attachments_impl(
        email_to=email_to,
        email_from=email_from,
        subject=subject,
        body=body,
        attachment_paths=attachment_paths,
    )


@tool
def gmail_send_email_with_attachments(
    email_to: str,
    subject: str,
    body: str,
    attachment_paths: List[str],
    email_from: str = "me",
) -> Dict | None:
    """Send a Gmail message with one or more file attachments."""

    return gmail_send_email_with_attachments_impl(
        email_to=email_to,
        email_from=email_from,
        subject=subject,
        body=body,
        attachment_paths=attachment_paths,
    )
