from __future__ import annotations

from unittest.mock import MagicMock

import src.tools.emails.gmail.gmail_messages as gmail_messages


def test_list_messages_defaults_to_inbox(monkeypatch) -> None:
    payload = [{"id": "m1", "thread_id": "t1"}]
    inner = MagicMock(return_value=payload)
    monkeypatch.setattr(gmail_messages, "search_messages", inner)

    result = gmail_messages.list_messages()

    assert result == payload
    inner.assert_called_once_with(
        query=None,
        label_ids=["INBOX"],
        max_results=50,
        include_spam_trash=False,
        include_details=True,
    )


def test_list_messages_forwards_custom_filters(monkeypatch) -> None:
    payload = [{"id": "m1", "thread_id": "t1"}]
    inner = MagicMock(return_value=payload)
    monkeypatch.setattr(gmail_messages, "search_messages", inner)

    result = gmail_messages.list_messages(
        label_ids=["CATEGORY_PERSONAL"],
        max_results=25,
        include_spam_trash=True,
        include_details=False,
        query="from:alerts@example.com",
    )

    assert result == payload
    inner.assert_called_once_with(
        query="from:alerts@example.com",
        label_ids=["CATEGORY_PERSONAL"],
        max_results=25,
        include_spam_trash=True,
        include_details=False,
    )


def test_list_messages_preserves_explicit_empty_label_ids(monkeypatch) -> None:
    payload = []
    inner = MagicMock(return_value=payload)
    monkeypatch.setattr(gmail_messages, "search_messages", inner)

    result = gmail_messages.list_messages(label_ids=[])

    assert result == payload
    inner.assert_called_once_with(
        query=None,
        label_ids=[],
        max_results=50,
        include_spam_trash=False,
        include_details=True,
    )
