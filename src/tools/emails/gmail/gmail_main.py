from __future__ import annotations

from typing import Dict, List, Optional, Union

from langchain_core.tools import tool

from .gmail_count import count_total_emails
from .gmail_draft import gmail_create_draft as gmail_create_draft_impl
from .gmail_filters import (
    create_filter as create_filter_impl,
    delete_filter as delete_filter_impl,
    get_filter as get_filter_impl,
    list_filters as list_filters_impl,
)
from .gmail_forwarding import enable_forwarding as enable_forwarding_impl
from .gmail_labels import (
    gmail_create_label as gmail_create_label_impl,
    gmail_delete_label as gmail_delete_label_impl,
    gmail_list_labels as gmail_list_labels_impl,
    gmail_modify_message_labels as gmail_modify_message_labels_impl,
    gmail_modify_thread_labels as gmail_modify_thread_labels_impl,
)
from .gmail_messages import list_messages as list_messages_impl
from .gmail_search import (
    search_messages as search_messages_impl,
    search_threads as search_threads_impl,
)
from .gmail_send_email import gmail_send_email as gmail_send_email_impl
from .gmail_signature import update_signature as update_signature_impl
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
def gmail_list_labels(label_type: Optional[str] = None) -> List[Dict[str, str]]:
    """Return Gmail labels. Optional filter: label_type SYSTEM or USER."""

    return gmail_list_labels_impl(label_type=label_type)


@tool
def gmail_create_label(
    name: str,
    label_list_visibility: str = "labelShow",
    message_list_visibility: str = "show",
) -> Dict | None:
    """Create a Gmail label and return the label payload."""

    return gmail_create_label_impl(
        name=name,
        label_list_visibility=label_list_visibility,
        message_list_visibility=message_list_visibility,
    )


@tool
def gmail_delete_label(label: str) -> bool:
    """Delete a Gmail label by ID or exact name."""

    return gmail_delete_label_impl(label=label)


@tool
def gmail_modify_message_labels(
    message_id: str,
    add_labels: Optional[List[str]] = None,
    remove_labels: Optional[List[str]] = None,
) -> Dict | None:
    """Add/remove labels on a Gmail message using label IDs or names."""

    return gmail_modify_message_labels_impl(
        message_id=message_id,
        add_labels=add_labels,
        remove_labels=remove_labels,
    )


@tool
def gmail_modify_thread_labels(
    thread_id: str,
    add_labels: Optional[List[str]] = None,
    remove_labels: Optional[List[str]] = None,
) -> Dict | None:
    """Add/remove labels on all existing messages in a Gmail thread."""

    return gmail_modify_thread_labels_impl(
        thread_id=thread_id,
        add_labels=add_labels,
        remove_labels=remove_labels,
    )


@tool
def gmail_search_messages(
    query: Optional[str] = None,
    label_ids: Optional[List[str]] = None,
    max_results: int = 50,
    include_spam_trash: bool = False,
    include_details: bool = True,
) -> List[Dict[str, str]]:
    """Search Gmail messages by query and/or labelIds."""

    return search_messages_impl(
        query=query,
        label_ids=label_ids,
        max_results=max_results,
        include_spam_trash=include_spam_trash,
        include_details=include_details,
    )


@tool
def gmail_list_messages(
    label_ids: Optional[List[str]] = None,
    max_results: int = 50,
    include_spam_trash: bool = False,
    include_details: bool = True,
    query: Optional[str] = None,
) -> List[Dict[str, str]]:
    """List Gmail messages (defaults to INBOX when label_ids is omitted)."""

    return list_messages_impl(
        label_ids=label_ids,
        max_results=max_results,
        include_spam_trash=include_spam_trash,
        include_details=include_details,
        query=query,
    )


@tool
def gmail_search_threads(
    query: Optional[str] = None,
    label_ids: Optional[List[str]] = None,
    max_results: int = 50,
    include_spam_trash: bool = False,
    include_details: bool = True,
) -> List[Dict[str, int | str]]:
    """Search Gmail threads by query and/or labelIds."""

    return search_threads_impl(
        query=query,
        label_ids=label_ids,
        max_results=max_results,
        include_spam_trash=include_spam_trash,
        include_details=include_details,
    )


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
def gmail_enable_forwarding(
    forwarding_email: str,
    disposition: str = "trash",
    enabled: bool = True,
) -> Dict | None:
    """Enable Gmail auto-forwarding for a verified forwarding address."""

    return enable_forwarding_impl(
        forwarding_email=forwarding_email,
        disposition=disposition,
        enabled=enabled,
    )


@tool
def gmail_create_filter(criteria: Dict, action: Dict) -> Dict | None:
    """Create a Gmail filter with criteria and action payloads."""

    return create_filter_impl(criteria=criteria, action=action)


@tool
def gmail_list_filters() -> List[Dict]:
    """List Gmail filters for the authenticated user."""

    return list_filters_impl()


@tool
def gmail_get_filter(filter_id: str) -> Dict | None:
    """Get a Gmail filter by ID."""

    return get_filter_impl(filter_id=filter_id)


@tool
def gmail_delete_filter(filter_id: str) -> bool:
    """Delete a Gmail filter by ID."""

    return delete_filter_impl(filter_id=filter_id)


@tool
def gmail_update_signature(
    signature: str = "Automated Signature",
    send_as_email: Optional[str] = None,
    display_name: Optional[str] = None,
) -> str | None:
    """Update Gmail signature for a send-as identity and return updated value."""

    return update_signature_impl(
        signature=signature,
        send_as_email=send_as_email,
        display_name=display_name,
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
