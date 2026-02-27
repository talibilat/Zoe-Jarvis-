from __future__ import annotations

from unittest.mock import MagicMock

import src.tools.emails.gmail.gmail_threads as gmail_threads


class _Executable:
    def __init__(self, payload: dict):
        self._payload = payload

    def execute(self) -> dict:
        return self._payload


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
    def __init__(self, threads_resource: _FakeThreadsResource):
        self._threads = threads_resource

    def users(self):
        return self

    def threads(self):
        return self._threads


def _patch_service(monkeypatch, service: _FakeService):
    monkeypatch.setattr(gmail_threads, "gmail_client", lambda: "creds")
    build_mock = MagicMock(return_value=service)
    monkeypatch.setattr(gmail_threads, "build", build_mock)
    return build_mock


def test_show_chatty_threads_filters_by_message_count_and_subject(monkeypatch) -> None:
    resource = _FakeThreadsResource(
        list_payload={"threads": [{"id": "t1"}, {"id": "t2"}, {"id": "t3"}]},
        details_by_id={
            "t1": {
                "id": "t1",
                "messages": [
                    {
                        "payload": {
                            "headers": [
                                {"name": "Subject", "value": "Quarterly Update"}
                            ]
                        }
                    },
                    {"payload": {"headers": []}},
                    {"payload": {"headers": []}},
                ],
            },
            "t2": {
                "id": "t2",
                "messages": [
                    {
                        "payload": {
                            "headers": [{"name": "Subject", "value": "Too short"}]
                        }
                    },
                    {"payload": {"headers": []}},
                ],
            },
            "t3": {
                "id": "t3",
                "messages": [
                    {"payload": {"headers": [{"name": "From", "value": "a@b.c"}]}},
                    {"payload": {"headers": []}},
                    {"payload": {"headers": []}},
                    {"payload": {"headers": []}},
                ],
            },
        },
    )

    _patch_service(monkeypatch, _FakeService(resource))

    result = gmail_threads.show_chatty_threads()

    assert result == [
        {
            "thread_id": "t1",
            "subject": "Quarterly Update",
            "message_count": 3,
        }
    ]
    assert [call["id"] for call in resource.get_calls] == ["t1", "t2", "t3"]


def test_show_chatty_threads_forwards_query_and_clamps_max_threads(monkeypatch) -> None:
    resource = _FakeThreadsResource(list_payload={"threads": []}, details_by_id={})
    build_mock = _patch_service(monkeypatch, _FakeService(resource))

    gmail_threads.show_chatty_threads(max_threads=9999, query="label:inbox")

    assert build_mock.call_args.kwargs["credentials"] == "creds"
    assert resource.list_calls[0]["maxResults"] == 500
    assert resource.list_calls[0]["q"] == "label:inbox"


def test_show_chatty_threads_clamps_minimums(monkeypatch) -> None:
    resource = _FakeThreadsResource(
        list_payload={"threads": [{"id": "t1"}]},
        details_by_id={
            "t1": {
                "id": "t1",
                "messages": [
                    {
                        "payload": {
                            "headers": [{"name": "Subject", "value": "Single message"}]
                        }
                    }
                ],
            }
        },
    )

    _patch_service(monkeypatch, _FakeService(resource))

    result = gmail_threads.show_chatty_threads(min_messages=0, max_threads=0)

    assert result == [
        {
            "thread_id": "t1",
            "subject": "Single message",
            "message_count": 1,
        }
    ]
    assert resource.list_calls[0]["maxResults"] == 1


def test_show_chatty_threads_handles_empty_list_payload(monkeypatch) -> None:
    resource = _FakeThreadsResource(list_payload={}, details_by_id={})
    _patch_service(monkeypatch, _FakeService(resource))

    result = gmail_threads.show_chatty_threads()

    assert result == []
    assert resource.get_calls == []
