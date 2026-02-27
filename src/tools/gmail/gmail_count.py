"""
Quick Gmail mailbox counter.

Run:
    python gmail_count.py
    python gmail_count.py --enumerate
"""

from __future__ import annotations

import argparse
from typing import Optional, Sequence

from googleapiclient.discovery import build

from src.core.clients.gmail_client import gmail_client


def enumerate_messages(
    service, *, batch_size: int = 500, include_spam_trash: bool = True
) -> int:
    total = 0
    page_token: Optional[str] = None
    while True:
        resp = (
            service.users()
            .messages()
            .list(
                userId="me",
                maxResults=batch_size,
                pageToken=page_token,
                includeSpamTrash=include_spam_trash,
            )
            .execute()
        )
        total += len(resp.get("messages", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return total


def count_total_emails(
    argv: Sequence[str] | None = None,
) -> tuple[int | None, int | None]:
    parser = argparse.ArgumentParser(
        description="Count Gmail messages for the current user."
    )
    parser.add_argument(
        "--enumerate",
        action="store_true",
        help="Page through every message to verify the total (slower).",
    )
    args = parser.parse_args(argv)

    service = build("gmail", "v1", credentials=gmail_client())

    profile = service.users().getProfile(userId="me").execute()
    total_messages = profile.get("messagesTotal")
    total_threads = profile.get("threadsTotal")

    if args.enumerate:
        enumerate_messages(service)

    return total_messages, total_threads
