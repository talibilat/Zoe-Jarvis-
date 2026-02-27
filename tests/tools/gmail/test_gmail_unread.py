from __future__ import annotations

import pytest

import src.tools.emails.gmail.gmail_unread as gmail_unread


class _Executable:
    def __init__(self, payload: dict):
        self._payload = payload

    def execute(self) -> dict:
        return self._payload


class _FakeMessagesResource:
    def __init__(self, pages_by_token: dict, details_by_id: dict):
        self.pages_by_token = pages_by_token
        self.details_by_id = details_by_id
        self.list_calls: list[dict] = []
        self.get_calls: list[dict] = []

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        page_token = kwargs.get("pageToken")
        return _Executable(self.pages_by_token.get(page_token, {"messages": []}))

    def get(self, **kwargs):
        self.get_calls.append(kwargs)
        return _Executable(self.details_by_id[kwargs["id"]])


class _FakeService:
    def __init__(self, messages_resource: _FakeMessagesResource):
        self._messages = messages_resource

    def users(self):
        return self

    def messages(self):
        return self._messages


def _patch_service(monkeypatch, service: _FakeService) -> None:
    monkeypatch.setattr(gmail_unread, "gmail_client", lambda: "creds")
    monkeypatch.setattr(gmail_unread, "build", lambda *_args, **_kwargs: service)


def test_get_unread_count_single_page(monkeypatch) -> None:
    messages = _FakeMessagesResource(
        {None: {"messages": [{"id": "1"}, {"id": "2"}]}}, {}
    )
    _patch_service(monkeypatch, _FakeService(messages))

    assert gmail_unread.get_unread_count() == 2


def test_get_unread_count_multiple_pages(monkeypatch) -> None:
    messages = _FakeMessagesResource(
        {
            None: {"messages": [{"id": "1"}], "nextPageToken": "p2"},
            "p2": {"messages": [{"id": "2"}, {"id": "3"}]},
        },
        {},
    )
    _patch_service(monkeypatch, _FakeService(messages))

    assert gmail_unread.get_unread_count() == 3


def test_get_unread_count_clamps_batch_size_minimum(monkeypatch) -> None:
    messages = _FakeMessagesResource({None: {"messages": []}}, {})
    _patch_service(monkeypatch, _FakeService(messages))

    gmail_unread.get_unread_count(batch_size=0)
    assert messages.list_calls[0]["maxResults"] == 1


def test_get_unread_count_clamps_batch_size_maximum(monkeypatch) -> None:
    messages = _FakeMessagesResource({None: {"messages": []}}, {})
    _patch_service(monkeypatch, _FakeService(messages))

    gmail_unread.get_unread_count(batch_size=50_000)
    assert messages.list_calls[0]["maxResults"] == 500


def test_get_unread_count_forwards_query(monkeypatch) -> None:
    messages = _FakeMessagesResource({None: {"messages": []}}, {})
    _patch_service(monkeypatch, _FakeService(messages))

    gmail_unread.get_unread_count(query="from:billing@example.com")
    assert messages.list_calls[0]["q"] == "from:billing@example.com"


def test_get_unread_email_summary_limit_none_returns_all(monkeypatch) -> None:
    messages = _FakeMessagesResource(
        {
            None: {"messages": [{"id": "1"}], "nextPageToken": "p2"},
            "p2": {"messages": [{"id": "2"}]},
        },
        {
            "1": {
                "id": "1",
                "threadId": "t1",
                "payload": {"headers": []},
                "snippet": "s1",
            },
            "2": {
                "id": "2",
                "threadId": "t2",
                "payload": {"headers": []},
                "snippet": "s2",
            },
        },
    )
    _patch_service(monkeypatch, _FakeService(messages))

    result = gmail_unread.get_unread_email_summary(limit=None)
    assert [item["id"] for item in result] == ["1", "2"]


def test_get_unread_email_summary_limit_all_string_returns_all(monkeypatch) -> None:
    messages = _FakeMessagesResource(
        {None: {"messages": [{"id": "1"}, {"id": "2"}]}},
        {
            "1": {
                "id": "1",
                "threadId": "t1",
                "payload": {"headers": []},
                "snippet": "",
            },
            "2": {
                "id": "2",
                "threadId": "t2",
                "payload": {"headers": []},
                "snippet": "",
            },
        },
    )
    _patch_service(monkeypatch, _FakeService(messages))

    result = gmail_unread.get_unread_email_summary(limit="all")
    assert len(result) == 2


def test_get_unread_email_summary_limit_numeric_string(monkeypatch) -> None:
    messages = _FakeMessagesResource(
        {None: {"messages": [{"id": "1"}, {"id": "2"}, {"id": "3"}]}},
        {
            "1": {
                "id": "1",
                "threadId": "t1",
                "payload": {"headers": []},
                "snippet": "",
            },
            "2": {
                "id": "2",
                "threadId": "t2",
                "payload": {"headers": []},
                "snippet": "",
            },
            "3": {
                "id": "3",
                "threadId": "t3",
                "payload": {"headers": []},
                "snippet": "",
            },
        },
    )
    _patch_service(monkeypatch, _FakeService(messages))

    result = gmail_unread.get_unread_email_summary(limit="2")
    assert len(result) == 2
    assert messages.list_calls[0]["maxResults"] == 2


def test_get_unread_email_summary_negative_limit_returns_empty(monkeypatch) -> None:
    messages = _FakeMessagesResource({None: {"messages": [{"id": "1"}]}}, {})
    _patch_service(monkeypatch, _FakeService(messages))

    result = gmail_unread.get_unread_email_summary(limit=-9)
    assert result == []
    assert messages.list_calls == []


def test_get_unread_email_summary_uses_default_header_values(monkeypatch) -> None:
    messages = _FakeMessagesResource(
        {None: {"messages": [{"id": "1"}]}},
        {
            "1": {
                "id": "1",
                "threadId": "t1",
                "payload": {"headers": [{"name": "Date", "value": "Mon"}]},
                "snippet": "hello",
            }
        },
    )
    _patch_service(monkeypatch, _FakeService(messages))

    result = gmail_unread.get_unread_email_summary(limit=1)
    assert result[0]["subject"] == "(no subject)"
    assert result[0]["from"] == "(unknown sender)"
    assert result[0]["date"] == "Mon"


def test_get_unread_email_summary_invalid_limit_string_raises_value_error(
    monkeypatch,
) -> None:
    messages = _FakeMessagesResource({None: {"messages": []}}, {})
    _patch_service(monkeypatch, _FakeService(messages))

    with pytest.raises(ValueError):
        gmail_unread.get_unread_email_summary(limit="not-a-number")
