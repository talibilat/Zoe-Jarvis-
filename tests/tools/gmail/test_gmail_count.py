from __future__ import annotations

from unittest.mock import MagicMock

import src.tools.emails.gmail.gmail_count as gmail_count


def _make_execute(payload: dict) -> MagicMock:
    request = MagicMock()
    request.execute.return_value = payload
    return request


def _make_service(
    *,
    pages: list[dict] | None = None,
    profile: dict | None = None,
) -> tuple[MagicMock, MagicMock]:
    service = MagicMock()
    users = service.users.return_value
    messages = users.messages.return_value

    pages = pages or [{"messages": []}]
    messages.list.side_effect = [_make_execute(page) for page in pages]
    users.getProfile.return_value.execute.return_value = profile or {
        "messagesTotal": 0,
        "threadsTotal": 0,
    }
    return service, messages


def test_enumerate_messages_single_page() -> None:
    service, _ = _make_service(pages=[{"messages": [{"id": "1"}, {"id": "2"}]}])
    assert gmail_count.enumerate_messages(service) == 2


def test_enumerate_messages_multiple_pages() -> None:
    service, _ = _make_service(
        pages=[
            {"messages": [{"id": "1"}], "nextPageToken": "next"},
            {"messages": [{"id": "2"}, {"id": "3"}]},
        ]
    )
    assert gmail_count.enumerate_messages(service) == 3


def test_enumerate_messages_handles_missing_messages_key() -> None:
    service, _ = _make_service(pages=[{"nextPageToken": None}])
    assert gmail_count.enumerate_messages(service) == 0


def test_enumerate_messages_forwards_batch_size() -> None:
    service, messages = _make_service(pages=[{"messages": []}])
    gmail_count.enumerate_messages(service, batch_size=123)
    assert messages.list.call_args.kwargs["maxResults"] == 123


def test_enumerate_messages_include_spam_true_by_default() -> None:
    service, messages = _make_service(pages=[{"messages": []}])
    gmail_count.enumerate_messages(service)
    assert messages.list.call_args.kwargs["includeSpamTrash"] is True


def test_enumerate_messages_include_spam_false() -> None:
    service, messages = _make_service(pages=[{"messages": []}])
    gmail_count.enumerate_messages(service, include_spam_trash=False)
    assert messages.list.call_args.kwargs["includeSpamTrash"] is False


def test_count_total_emails_returns_profile_totals(monkeypatch) -> None:
    service, _ = _make_service(profile={"messagesTotal": 42, "threadsTotal": 24})
    monkeypatch.setattr(gmail_count, "build", lambda *_args, **_kwargs: service)
    monkeypatch.setattr(gmail_count, "gmail_client", lambda: "creds")

    assert gmail_count.count_total_emails([]) == (42, 24)


def test_count_total_emails_builds_with_gmail_credentials(monkeypatch) -> None:
    service, _ = _make_service(profile={"messagesTotal": 1, "threadsTotal": 2})
    build_mock = MagicMock(return_value=service)
    monkeypatch.setattr(gmail_count, "build", build_mock)
    monkeypatch.setattr(gmail_count, "gmail_client", lambda: "test-creds")

    gmail_count.count_total_emails([])
    assert build_mock.call_args.kwargs["credentials"] == "test-creds"


def test_count_total_emails_calls_enumerate_when_flag_is_set(monkeypatch) -> None:
    service, _ = _make_service(profile={"messagesTotal": 1, "threadsTotal": 2})
    enumerate_mock = MagicMock(return_value=999)
    monkeypatch.setattr(gmail_count, "build", lambda *_args, **_kwargs: service)
    monkeypatch.setattr(gmail_count, "gmail_client", lambda: "creds")
    monkeypatch.setattr(gmail_count, "enumerate_messages", enumerate_mock)

    gmail_count.count_total_emails(["--enumerate"])
    enumerate_mock.assert_called_once_with(service)


def test_count_total_emails_skips_enumerate_when_flag_not_set(monkeypatch) -> None:
    service, _ = _make_service(profile={"messagesTotal": 1, "threadsTotal": 2})
    enumerate_mock = MagicMock(return_value=999)
    monkeypatch.setattr(gmail_count, "build", lambda *_args, **_kwargs: service)
    monkeypatch.setattr(gmail_count, "gmail_client", lambda: "creds")
    monkeypatch.setattr(gmail_count, "enumerate_messages", enumerate_mock)

    gmail_count.count_total_emails([])
    enumerate_mock.assert_not_called()
