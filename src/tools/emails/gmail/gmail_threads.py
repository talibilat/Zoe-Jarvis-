"""Helpers to inspect Gmail threads with longer conversations."""

from __future__ import annotations

from typing import Dict, List, Optional

from googleapiclient.discovery import build

from src.core.clients.gmail_client import gmail_client


def _extract_subject(headers: list[dict]) -> str:
    for header in headers:
        if (header.get("name") or "").lower() == "subject":
            return header.get("value") or ""
    return ""


def show_chatty_threads(
    *,
    min_messages: int = 3,
    max_threads: int = 100,
    query: Optional[str] = None,
) -> List[Dict[str, int | str]]:
    """Return threads that contain at least ``min_messages`` and have a subject."""
    min_messages = max(1, min_messages)
    max_threads = max(1, min(max_threads, 500))

    service = build("gmail", "v1", credentials=gmail_client())

    list_kwargs = {
        "userId": "me",
        "maxResults": max_threads,
    }
    if query and query.strip():
        list_kwargs["q"] = query.strip()

    threads = service.users().threads().list(**list_kwargs).execute().get("threads", [])

    chatty_threads: List[Dict[str, int | str]] = []
    for thread in threads:
        thread_id = thread.get("id")
        if not thread_id:
            continue

        detail = service.users().threads().get(userId="me", id=thread_id).execute()
        messages = detail.get("messages", [])
        message_count = len(messages)
        if message_count < min_messages:
            continue

        first_payload = messages[0].get("payload", {}) if messages else {}
        subject = _extract_subject(first_payload.get("headers", []))
        if not subject:
            continue

        chatty_threads.append(
            {
                "thread_id": detail.get("id", thread_id),
                "subject": subject,
                "message_count": message_count,
            }
        )

    return chatty_threads
