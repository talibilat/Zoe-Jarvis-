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

from src.core.clients.gmail_client import (
    execute_gmail_request,
    gmail_client,
)


def _gmail_service():
    return build("gmail", "v1", credentials=gmail_client())


def enumerate_messages(
    service, *, batch_size: int = 500, include_spam_trash: bool = True
) -> int:
    total = 0
    page_token: Optional[str] = None
    while True:
        resp = execute_gmail_request(
            service.users()
            .messages()
            .list(
                userId="me",
                maxResults=batch_size,
                pageToken=page_token,
                includeSpamTrash=include_spam_trash,
            )
        )
        total += len(resp.get("messages", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return total


def get_mailbox_totals(
    *,
    enumerate_all: bool = False,
    batch_size: int = 500,
    include_spam_trash: bool = True,
) -> tuple[int | None, int | None]:
    """Return Gmail mailbox totals for the authenticated user."""

    service = _gmail_service()
    profile = execute_gmail_request(service.users().getProfile(userId="me"))
    total_messages = profile.get("messagesTotal")
    total_threads = profile.get("threadsTotal")

    if enumerate_all:
        enumerate_messages(
            service,
            batch_size=batch_size,
            include_spam_trash=include_spam_trash,
        )

    return total_messages, total_threads


def count_total_emails(
    argv: Sequence[str] | None = None,
) -> tuple[int | None, int | None]:
    """Backward-compatible entry point that parses CLI args then returns totals."""

    parser = argparse.ArgumentParser(
        description="Count Gmail messages for the current user."
    )
    parser.add_argument(
        "--enumerate",
        action="store_true",
        help="Page through every message to verify the total (slower).",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=500,
        help="Page size for --enumerate mode (max 500).",
    )
    args = parser.parse_args(argv)

    return get_mailbox_totals(
        enumerate_all=args.enumerate,
        batch_size=max(1, min(args.page_size, 500)),
    )


def main(argv: Sequence[str] | None = None) -> int:
    count_total_emails(argv)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
