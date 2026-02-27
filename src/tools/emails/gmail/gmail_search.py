"""Helpers for Gmail message/thread search via q and labelIds filters."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from googleapiclient.discovery import build

from src.core.clients.gmail_client import gmail_client


def _extract_header(headers: list[dict], name: str) -> str:
    target = name.lower()
    for header in headers:
        if (header.get("name") or "").lower() == target:
            return header.get("value") or ""
    return ""


def _normalize_label_ids(label_ids: Optional[Sequence[str]]) -> list[str]:
    if not label_ids:
        return []
    normalized: list[str] = []
    for value in label_ids:
        candidate = (value or "").strip()
        if candidate and candidate not in normalized:
            normalized.append(candidate)
    return normalized


def _list_kwargs(
    *,
    query: Optional[str],
    label_ids: Optional[Sequence[str]],
    max_results: int,
    include_spam_trash: bool,
) -> dict:
    kwargs = {
        "userId": "me",
        "maxResults": max(1, min(max_results, 500)),
    }

    normalized_query = (query or "").strip()
    if normalized_query:
        kwargs["q"] = normalized_query

    resolved_label_ids = _normalize_label_ids(label_ids)
    if resolved_label_ids:
        kwargs["labelIds"] = resolved_label_ids

    if include_spam_trash:
        kwargs["includeSpamTrash"] = True

    return kwargs


def search_messages(
    *,
    query: Optional[str] = None,
    label_ids: Optional[Sequence[str]] = None,
    max_results: int = 50,
    include_spam_trash: bool = False,
    include_details: bool = True,
) -> List[Dict[str, str]]:
    """Search messages using Gmail q/labelIds filters."""
    service = build("gmail", "v1", credentials=gmail_client())

    response = (
        service.users()
        .messages()
        .list(
            **_list_kwargs(
                query=query,
                label_ids=label_ids,
                max_results=max_results,
                include_spam_trash=include_spam_trash,
            )
        )
        .execute()
    )

    messages = response.get("messages", [])
    if not include_details:
        return [
            {
                "id": message.get("id") or "",
                "thread_id": message.get("threadId") or "",
            }
            for message in messages
            if message.get("id")
        ]

    results: List[Dict[str, str]] = []
    for message in messages:
        message_id = message.get("id")
        if not message_id:
            continue

        detail = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=message_id,
                format="metadata",
                metadataHeaders=["Subject", "From", "Date"],
            )
            .execute()
        )
        headers = detail.get("payload", {}).get("headers", [])

        results.append(
            {
                "id": detail.get("id") or message_id,
                "thread_id": detail.get("threadId") or (message.get("threadId") or ""),
                "subject": _extract_header(headers, "Subject") or "(no subject)",
                "from": _extract_header(headers, "From") or "(unknown sender)",
                "date": _extract_header(headers, "Date"),
                "snippet": detail.get("snippet") or "",
            }
        )

    return results


def search_threads(
    *,
    query: Optional[str] = None,
    label_ids: Optional[Sequence[str]] = None,
    max_results: int = 50,
    include_spam_trash: bool = False,
    include_details: bool = True,
) -> List[Dict[str, int | str]]:
    """Search threads using Gmail q/labelIds filters."""
    service = build("gmail", "v1", credentials=gmail_client())

    response = (
        service.users()
        .threads()
        .list(
            **_list_kwargs(
                query=query,
                label_ids=label_ids,
                max_results=max_results,
                include_spam_trash=include_spam_trash,
            )
        )
        .execute()
    )

    threads = response.get("threads", [])
    if not include_details:
        return [
            {
                "thread_id": thread.get("id") or "",
            }
            for thread in threads
            if thread.get("id")
        ]

    results: List[Dict[str, int | str]] = []
    for thread in threads:
        thread_id = thread.get("id")
        if not thread_id:
            continue

        detail = (
            service.users()
            .threads()
            .get(
                userId="me",
                id=thread_id,
                format="metadata",
                metadataHeaders=["Subject", "From", "Date"],
            )
            .execute()
        )

        messages = detail.get("messages", [])
        first_headers = (
            messages[0].get("payload", {}).get("headers", []) if messages else []
        )

        results.append(
            {
                "thread_id": detail.get("id") or thread_id,
                "message_count": len(messages),
                "subject": _extract_header(first_headers, "Subject") or "(no subject)",
                "from": _extract_header(first_headers, "From") or "(unknown sender)",
                "date": _extract_header(first_headers, "Date"),
                "snippet": detail.get("snippet") or "",
            }
        )

    return results
