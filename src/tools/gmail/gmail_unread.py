"""
Minimal helpers to count and inspect unread Gmail messages.

Only two entry points are exposed so they can be called directly from other tools.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Union

from googleapiclient.discovery import build

from src.core.clients.gmail_client import gmail_client


def get_unread_count(*, query: str = "is:unread", batch_size: int = 500) -> int:
    """
    Return the number of unread Gmail messages matching the given query.
    """
    service = build("gmail", "v1", credentials=gmail_client())
    batch_size = max(1, min(batch_size, 500))

    total = 0
    page_token: Optional[str] = None

    while True:
        response = (
            service.users()
            .messages()
            .list(
                userId="me",
                q=query,
                maxResults=batch_size,
                pageToken=page_token,
            )
            .execute()
        )
        total += len(response.get("messages", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return total


def get_unread_email_summary(
    *,
    limit: Optional[Union[str, int]] = None,
    query: str = "is:unread",
) -> List[Dict[str, str]]:
    """
    Return metadata for unread emails (subject, sender, date, snippet).

    Parameters
    ----------
    limit: None | "all" | int
        - None or "all": return every unread email.
        - Positive integer: return up to that many items (top K).
    query: str
        Gmail search query (default: is:unread).
    """
    if isinstance(limit, str):
        stripped = limit.strip().lower()
        if stripped in {"", "all"}:
            limit = None
        else:
            limit = max(0, int(stripped))
    elif isinstance(limit, int):
        limit = max(0, limit)
    else:
        limit = None

    service = build("gmail", "v1", credentials=gmail_client())

    emails: List[Dict[str, str]] = []
    page_token: Optional[str] = None
    remaining = limit

    while True:
        max_results = 500
        if remaining is not None:
            if remaining == 0:
                break
            max_results = min(max_results, remaining)

        response = (
            service.users()
            .messages()
            .list(
                userId="me",
                q=query,
                maxResults=max_results,
                pageToken=page_token,
            )
            .execute()
        )

        for msg in response.get("messages", []):
            detail = (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=msg["id"],
                    format="metadata",
                    metadataHeaders=["Subject", "From", "Date"],
                )
                .execute()
            )
            headers = detail.get("payload", {}).get("headers", [])
            header_map = {
                (h.get("name") or "").lower(): h.get("value") for h in headers if "name" in h
            }
            emails.append(
                {
                    "id": detail.get("id"),
                    "threadId": detail.get("threadId"),
                    "subject": header_map.get("subject", "(no subject)"),
                    "from": header_map.get("from", "(unknown sender)"),
                    "date": header_map.get("date", ""),
                    "snippet": detail.get("snippet", ""),
                }
            )

            if remaining is not None:
                remaining -= 1
                if remaining == 0:
                    break

        if remaining == 0:
            break

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return emails
