from __future__ import annotations

from unittest.mock import MagicMock

import src.tools.emails.gmail.gmail_search as gmail_search


class _Executable:
    def __init__(self, payload: dict):
        self._payload = payload

    def execute(self) -> dict:
        return self._payload


class _FakeMessagesResource:
    def __init__(self, list_payload: dict, details_by_id: dict[str, dict]):
        self.list_payload = list_payload
        self.details_by_id = details_by_id
        self.list_calls: list[dict] = []
        self.get_calls: list[dict] = []

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        return _Executable(self.list_payload)

    def get(self, **kwargs):
        self.get_calls.append(kwargs)
        return _Executable(self.details_by_id[kwargs["id"]])


class _FakeThreadsResource:
    def __init__(self, list_payload: dict, details_by_id: dict[str, dict]):
        self.list_payload = list_payload
        self.details_by_id = details_by_id
        self.list_calls: list[dict] = []
        self.get_calls: list[dict] = []

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        return _Executable(self.list_payload)

    def get(self, **kwargs):
        self.get_calls.append(kwargs)
        return _Executable(self.details_by_id[kwargs["id"]])


class _FakeService:
    def __init__(
        self,
        *,
        messages_resource: _FakeMessagesResource,
        threads_resource: _FakeThreadsResource,
    ):
        self._messages = messages_resource
        self._threads = threads_resource

    def users(self):
        return self

    def messages(self):
        return self._messages

    def threads(self):
        return self._threads


def _patch_service(monkeypatch, service: _FakeService):
    monkeypatch.setattr(gmail_search, "gmail_client", lambda: "creds")
    build_mock = MagicMock(return_value=service)
    monkeypatch.setattr(gmail_search, "build", build_mock)
    return build_mock


def test_search_messages_forwards_filters_and_returns_details(monkeypatch) -> None:
    messages = _FakeMessagesResource(
        list_payload={"messages": [{"id": "m1", "threadId": "t1"}]},
        details_by_id={
            "m1": {
                "id": "m1",
                "threadId": "t1",
                "snippet": "hello snippet",
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": "Project Update"},
                        {"name": "From", "value": "boss@example.com"},
                        {"name": "Date", "value": "Mon"},
                    ]
                },
            }
        },
    )
    threads = _FakeThreadsResource(list_payload={"threads": []}, details_by_id={})
    build_mock = _patch_service(
        monkeypatch,
        _FakeService(messages_resource=messages, threads_resource=threads),
    )

    result = gmail_search.search_messages(
        query="from:boss@example.com",
        label_ids=["INBOX", " Label_1 "],
        max_results=999,
        include_spam_trash=True,
    )

    assert build_mock.call_args.kwargs["credentials"] == "creds"
    assert messages.list_calls[0]["q"] == "from:boss@example.com"
    assert messages.list_calls[0]["labelIds"] == ["INBOX", "Label_1"]
    assert messages.list_calls[0]["maxResults"] == 500
    assert messages.list_calls[0]["includeSpamTrash"] is True
    assert result == [
        {
            "id": "m1",
            "thread_id": "t1",
            "subject": "Project Update",
            "from": "boss@example.com",
            "date": "Mon",
            "snippet": "hello snippet",
        }
    ]


def test_search_messages_without_details_skips_get_calls(monkeypatch) -> None:
    messages = _FakeMessagesResource(
        list_payload={"messages": [{"id": "m1", "threadId": "t1"}]},
        details_by_id={
            "m1": {
                "id": "m1",
                "threadId": "t1",
                "payload": {"headers": []},
            }
        },
    )
    threads = _FakeThreadsResource(list_payload={"threads": []}, details_by_id={})
    _patch_service(
        monkeypatch,
        _FakeService(messages_resource=messages, threads_resource=threads),
    )

    result = gmail_search.search_messages(include_details=False)

    assert result == [{"id": "m1", "thread_id": "t1"}]
    assert messages.get_calls == []


def test_search_threads_forwards_filters_and_returns_details(monkeypatch) -> None:
    messages = _FakeMessagesResource(list_payload={"messages": []}, details_by_id={})
    threads = _FakeThreadsResource(
        list_payload={"threads": [{"id": "t1"}]},
        details_by_id={
            "t1": {
                "id": "t1",
                "snippet": "thread snippet",
                "messages": [
                    {
                        "payload": {
                            "headers": [
                                {"name": "Subject", "value": "Launch Plan"},
                                {"name": "From", "value": "lead@example.com"},
                                {"name": "Date", "value": "Tue"},
                            ]
                        }
                    },
                    {"payload": {"headers": []}},
                ],
            }
        },
    )
    _patch_service(
        monkeypatch,
        _FakeService(messages_resource=messages, threads_resource=threads),
    )

    result = gmail_search.search_threads(
        query="in:inbox",
        label_ids=["INBOX"],
        max_results=2,
    )

    assert threads.list_calls[0]["q"] == "in:inbox"
    assert threads.list_calls[0]["labelIds"] == ["INBOX"]
    assert threads.list_calls[0]["maxResults"] == 2
    assert result == [
        {
            "thread_id": "t1",
            "message_count": 2,
            "subject": "Launch Plan",
            "from": "lead@example.com",
            "date": "Tue",
            "snippet": "thread snippet",
        }
    ]


def test_search_threads_without_details_skips_get_calls(monkeypatch) -> None:
    messages = _FakeMessagesResource(list_payload={"messages": []}, details_by_id={})
    threads = _FakeThreadsResource(
        list_payload={"threads": [{"id": "t1"}]},
        details_by_id={
            "t1": {
                "id": "t1",
                "messages": [],
            }
        },
    )
    _patch_service(
        monkeypatch,
        _FakeService(messages_resource=messages, threads_resource=threads),
    )

    result = gmail_search.search_threads(include_details=False)

    assert result == [{"thread_id": "t1"}]
    assert threads.get_calls == []
