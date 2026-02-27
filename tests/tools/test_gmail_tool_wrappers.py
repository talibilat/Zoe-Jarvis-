from __future__ import annotations

from unittest.mock import MagicMock

import src.tools.emails.gmail.gmail_main as gmail_tool


def test_gmail_total_counts_wrapper(monkeypatch) -> None:
    monkeypatch.setattr(gmail_tool, "count_total_emails", lambda _argv: (12, 5))
    assert gmail_tool.gmail_total_counts.invoke({}) == {
        "messages_total": 12,
        "threads_total": 5,
    }


def test_gmail_unread_count_wrapper_forwards_params(monkeypatch) -> None:
    inner = MagicMock(return_value=9)
    monkeypatch.setattr(gmail_tool, "get_unread_count", inner)

    result = gmail_tool.gmail_unread_count.invoke(
        {"query": "from:alerts@example.com", "batch_size": 123}
    )

    assert result == 9
    inner.assert_called_once_with(query="from:alerts@example.com", batch_size=123)


def test_gmail_unread_summary_wrapper_forwards_params(monkeypatch) -> None:
    payload = [{"id": "1", "subject": "Hello"}]
    inner = MagicMock(return_value=payload)
    monkeypatch.setattr(gmail_tool, "get_unread_email_summary", inner)

    result = gmail_tool.gmail_unread_summary.invoke(
        {"limit": "all", "query": "is:unread category:primary"}
    )

    assert result == payload
    inner.assert_called_once_with(limit="all", query="is:unread category:primary")


def test_gmail_chatty_threads_wrapper_forwards_params(monkeypatch) -> None:
    payload = [{"thread_id": "t1", "subject": "Quarterly Update", "message_count": 4}]
    inner = MagicMock(return_value=payload)
    monkeypatch.setattr(gmail_tool, "show_chatty_threads_impl", inner)

    result = gmail_tool.gmail_chatty_threads.invoke(
        {"min_messages": 4, "max_threads": 50, "query": "label:inbox"}
    )

    assert result == payload
    inner.assert_called_once_with(
        min_messages=4,
        max_threads=50,
        query="label:inbox",
    )


def test_gmail_chatty_threads_wrapper_uses_defaults(monkeypatch) -> None:
    inner = MagicMock(return_value=[])
    monkeypatch.setattr(gmail_tool, "show_chatty_threads_impl", inner)

    gmail_tool.gmail_chatty_threads.invoke({})

    inner.assert_called_once_with(
        min_messages=3,
        max_threads=100,
        query=None,
    )


def test_gmail_create_draft_wrapper_forwards_payload(monkeypatch) -> None:
    payload = {"id": "draft-1", "message": {"id": "msg-1"}}
    inner = MagicMock(return_value=payload)
    monkeypatch.setattr(gmail_tool, "gmail_create_draft_impl", inner)

    result = gmail_tool.gmail_create_draft.invoke(
        {
            "email_to": "to@example.com",
            "email_from": "from@example.com",
            "subject": "Subject",
            "body": "Body",
        }
    )

    assert result == payload
    inner.assert_called_once_with(
        email_to="to@example.com",
        email_from="from@example.com",
        subject="Subject",
        body="Body",
    )


def test_gmail_create_draft_wrapper_uses_default_sender(monkeypatch) -> None:
    inner = MagicMock(return_value={"id": "draft-2", "message": {"id": "msg-2"}})
    monkeypatch.setattr(gmail_tool, "gmail_create_draft_impl", inner)

    gmail_tool.gmail_create_draft.invoke(
        {
            "email_to": "to@example.com",
            "subject": "Subject",
            "body": "Body",
        }
    )

    assert inner.call_args.kwargs["email_from"] == "me"


def test_gmail_send_email_wrapper_forwards_payload(monkeypatch) -> None:
    payload = {"id": "sent-1", "threadId": "thread-1"}
    inner = MagicMock(return_value=payload)
    monkeypatch.setattr(gmail_tool, "gmail_send_email_impl", inner)

    result = gmail_tool.gmail_send_email.invoke(
        {
            "email_to": "to@example.com",
            "email_from": "from@example.com",
            "subject": "Subject",
            "body": "Body",
        }
    )

    assert result == payload
    inner.assert_called_once_with(
        email_to="to@example.com",
        email_from="from@example.com",
        subject="Subject",
        body="Body",
    )


def test_gmail_send_email_wrapper_uses_default_sender(monkeypatch) -> None:
    inner = MagicMock(return_value={"id": "sent-2", "threadId": "thread-2"})
    monkeypatch.setattr(gmail_tool, "gmail_send_email_impl", inner)

    gmail_tool.gmail_send_email.invoke(
        {
            "email_to": "to@example.com",
            "subject": "Subject",
            "body": "Body",
        }
    )

    assert inner.call_args.kwargs["email_from"] == "me"


def test_gmail_create_draft_with_attachments_wrapper_forwards_payload(
    monkeypatch,
) -> None:
    payload = {"id": "draft-attach-1", "message": {"id": "msg-1"}}
    inner = MagicMock(return_value=payload)
    monkeypatch.setattr(gmail_tool, "gmail_create_draft_with_attachments_impl", inner)

    result = gmail_tool.gmail_create_draft_with_attachments.invoke(
        {
            "email_to": "to@example.com",
            "email_from": "from@example.com",
            "subject": "Subject",
            "body": "Body",
            "attachment_paths": ["/tmp/a.txt", "/tmp/b.csv"],
        }
    )

    assert result == payload
    inner.assert_called_once_with(
        email_to="to@example.com",
        email_from="from@example.com",
        subject="Subject",
        body="Body",
        attachment_paths=["/tmp/a.txt", "/tmp/b.csv"],
    )


def test_gmail_create_draft_with_attachments_wrapper_uses_default_sender(
    monkeypatch,
) -> None:
    inner = MagicMock(return_value={"id": "draft-attach-2", "message": {"id": "msg-2"}})
    monkeypatch.setattr(gmail_tool, "gmail_create_draft_with_attachments_impl", inner)

    gmail_tool.gmail_create_draft_with_attachments.invoke(
        {
            "email_to": "to@example.com",
            "subject": "Subject",
            "body": "Body",
            "attachment_paths": ["/tmp/a.txt"],
        }
    )

    assert inner.call_args.kwargs["email_from"] == "me"


def test_gmail_send_email_with_attachments_wrapper_forwards_payload(
    monkeypatch,
) -> None:
    payload = {"id": "sent-attach-1", "threadId": "thread-1"}
    inner = MagicMock(return_value=payload)
    monkeypatch.setattr(gmail_tool, "gmail_send_email_with_attachments_impl", inner)

    result = gmail_tool.gmail_send_email_with_attachments.invoke(
        {
            "email_to": "to@example.com",
            "email_from": "from@example.com",
            "subject": "Subject",
            "body": "Body",
            "attachment_paths": ["/tmp/a.txt", "/tmp/b.csv"],
        }
    )

    assert result == payload
    inner.assert_called_once_with(
        email_to="to@example.com",
        email_from="from@example.com",
        subject="Subject",
        body="Body",
        attachment_paths=["/tmp/a.txt", "/tmp/b.csv"],
    )


def test_gmail_send_email_with_attachments_wrapper_uses_default_sender(
    monkeypatch,
) -> None:
    inner = MagicMock(return_value={"id": "sent-attach-2", "threadId": "thread-2"})
    monkeypatch.setattr(gmail_tool, "gmail_send_email_with_attachments_impl", inner)

    gmail_tool.gmail_send_email_with_attachments.invoke(
        {
            "email_to": "to@example.com",
            "subject": "Subject",
            "body": "Body",
            "attachment_paths": ["/tmp/a.txt"],
        }
    )

    assert inner.call_args.kwargs["email_from"] == "me"
