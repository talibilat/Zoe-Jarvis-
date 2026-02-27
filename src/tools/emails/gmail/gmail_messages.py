"""Helpers for listing Gmail messages, defaulting to INBOX."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from .gmail_search import search_messages


def list_messages(
    *,
    label_ids: Optional[Sequence[str]] = None,
    max_results: int = 50,
    include_spam_trash: bool = False,
    include_details: bool = True,
    query: Optional[str] = None,
) -> List[Dict[str, str]]:
    """List Gmail messages using messages.list semantics.

    By default this lists inbox messages (`labelIds=['INBOX']`).
    """
    effective_label_ids = ["INBOX"] if label_ids is None else label_ids

    return search_messages(
        query=query,
        label_ids=effective_label_ids,
        max_results=max_results,
        include_spam_trash=include_spam_trash,
        include_details=include_details,
    )
