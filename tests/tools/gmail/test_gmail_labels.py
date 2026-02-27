from __future__ import annotations

from types import SimpleNamespace

import pytest
from googleapiclient.errors import HttpError

import src.tools.emails.gmail.gmail_labels as gmail_labels


class _Executable:
    def __init__(self, payload: dict):
        self._payload = payload

    def execute(self) -> dict:
        return self._payload


class _FakeLabelsResource:
    def __init__(
        self,
        *,
        list_payload: dict | None = None,
        create_payload: dict | None = None,
    ):
        self.list_payload = list_payload or {"labels": []}
        self.create_payload = create_payload or {"id": "Label_1", "name": "Projects"}
        self.list_calls: list[dict] = []
        self.create_calls: list[dict] = []
        self.delete_calls: list[dict] = []

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        return _Executable(self.list_payload)

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return _Executable(self.create_payload)

    def delete(self, **kwargs):
        self.delete_calls.append(kwargs)
        return _Executable({})


class _FakeMessagesResource:
    def __init__(self, modify_payload: dict | None = None):
        self.modify_payload = modify_payload or {"id": "m1", "labelIds": ["Label_1"]}
        self.modify_calls: list[dict] = []

    def modify(self, **kwargs):
        self.modify_calls.append(kwargs)
        return _Executable(self.modify_payload)


class _FakeThreadsResource:
    def __init__(self, modify_payload: dict | None = None):
        self.modify_payload = modify_payload or {
            "id": "t1",
            "historyId": "123",
        }
        self.modify_calls: list[dict] = []

    def modify(self, **kwargs):
        self.modify_calls.append(kwargs)
        return _Executable(self.modify_payload)


class _FakeService:
    def __init__(
        self,
        *,
        labels_resource: _FakeLabelsResource,
        messages_resource: _FakeMessagesResource | None = None,
        threads_resource: _FakeThreadsResource | None = None,
    ):
        self._labels = labels_resource
        self._messages = messages_resource or _FakeMessagesResource()
        self._threads = threads_resource or _FakeThreadsResource()

    def users(self):
        return self

    def labels(self):
        return self._labels

    def messages(self):
        return self._messages

    def threads(self):
        return self._threads


def test_gmail_list_labels_returns_all_and_filtered(monkeypatch) -> None:
    labels = {
        "labels": [
            {"id": "INBOX", "name": "INBOX", "type": "SYSTEM"},
            {"id": "Label_1", "name": "Projects", "type": "USER"},
        ]
    }
    service = _FakeService(labels_resource=_FakeLabelsResource(list_payload=labels))
    monkeypatch.setattr(gmail_labels, "_gmail_service", lambda: service)

    all_labels = gmail_labels.gmail_list_labels()
    user_labels = gmail_labels.gmail_list_labels(label_type="USER")

    assert len(all_labels) == 2
    assert user_labels == [{"id": "Label_1", "name": "Projects", "type": "USER"}]


def test_gmail_list_labels_rejects_invalid_label_type(monkeypatch) -> None:
    service = _FakeService(labels_resource=_FakeLabelsResource())
    monkeypatch.setattr(gmail_labels, "_gmail_service", lambda: service)

    with pytest.raises(ValueError, match="label_type"):
        gmail_labels.gmail_list_labels(label_type="INVALID")


def test_gmail_create_label_forwards_payload(monkeypatch) -> None:
    labels_resource = _FakeLabelsResource(
        create_payload={"id": "Label_2", "name": "Work"}
    )
    service = _FakeService(labels_resource=labels_resource)
    monkeypatch.setattr(gmail_labels, "_gmail_service", lambda: service)

    result = gmail_labels.gmail_create_label(name="Work")

    assert result == {"id": "Label_2", "name": "Work"}
    assert labels_resource.create_calls[0]["userId"] == "me"
    assert labels_resource.create_calls[0]["body"]["name"] == "Work"


def test_gmail_delete_label_resolves_name_to_id(monkeypatch) -> None:
    labels_resource = _FakeLabelsResource(
        list_payload={"labels": [{"id": "Label_1", "name": "Projects", "type": "USER"}]}
    )
    service = _FakeService(labels_resource=labels_resource)
    monkeypatch.setattr(gmail_labels, "_gmail_service", lambda: service)

    result = gmail_labels.gmail_delete_label("Projects")

    assert result is True
    assert labels_resource.delete_calls[0]["id"] == "Label_1"


def test_gmail_delete_label_raises_for_unknown_label(monkeypatch) -> None:
    service = _FakeService(
        labels_resource=_FakeLabelsResource(list_payload={"labels": []})
    )
    monkeypatch.setattr(gmail_labels, "_gmail_service", lambda: service)

    with pytest.raises(ValueError, match="Unknown Gmail label"):
        gmail_labels.gmail_delete_label("DoesNotExist")


def test_gmail_modify_message_labels_resolves_names_and_ids(monkeypatch) -> None:
    labels_resource = _FakeLabelsResource(
        list_payload={
            "labels": [
                {"id": "INBOX", "name": "INBOX", "type": "SYSTEM"},
                {"id": "Label_1", "name": "Projects", "type": "USER"},
                {"id": "Label_2", "name": "Archive", "type": "USER"},
            ]
        }
    )
    messages_resource = _FakeMessagesResource(
        modify_payload={"id": "m1", "labelIds": ["INBOX", "Label_1"]}
    )
    service = _FakeService(
        labels_resource=labels_resource,
        messages_resource=messages_resource,
    )
    monkeypatch.setattr(gmail_labels, "_gmail_service", lambda: service)

    result = gmail_labels.gmail_modify_message_labels(
        message_id="m1",
        add_labels=["Projects", "INBOX"],
        remove_labels=["Label_2"],
    )

    assert result == {"id": "m1", "labelIds": ["INBOX", "Label_1"]}
    call = messages_resource.modify_calls[0]
    assert call["userId"] == "me"
    assert call["id"] == "m1"
    assert call["body"] == {
        "addLabelIds": ["Label_1", "INBOX"],
        "removeLabelIds": ["Label_2"],
    }


def test_gmail_modify_thread_labels_requires_non_empty_changes(monkeypatch) -> None:
    labels_resource = _FakeLabelsResource(list_payload={"labels": []})
    threads_resource = _FakeThreadsResource()
    service = _FakeService(
        labels_resource=labels_resource,
        threads_resource=threads_resource,
    )
    monkeypatch.setattr(gmail_labels, "_gmail_service", lambda: service)

    with pytest.raises(ValueError, match="at least one label"):
        gmail_labels.gmail_modify_thread_labels(thread_id="t1")


def test_gmail_delete_label_rejects_empty_label(monkeypatch) -> None:
    service = _FakeService(
        labels_resource=_FakeLabelsResource(list_payload={"labels": []})
    )
    monkeypatch.setattr(gmail_labels, "_gmail_service", lambda: service)

    with pytest.raises(ValueError, match="label must not be empty"):
        gmail_labels.gmail_delete_label("   ")


def test_gmail_create_label_rejects_empty_name(monkeypatch) -> None:
    service = _FakeService(labels_resource=_FakeLabelsResource())
    monkeypatch.setattr(gmail_labels, "_gmail_service", lambda: service)

    with pytest.raises(ValueError, match="cannot be empty"):
        gmail_labels.gmail_create_label(name=" ")


def test_gmail_create_label_raises_runtime_error_on_http_error(monkeypatch) -> None:
    class _FailingLabelsResource(_FakeLabelsResource):
        def create(self, **kwargs):
            self.create_calls.append(kwargs)

            class _FailingRequest:
                def execute(self):
                    raise HttpError(
                        resp=SimpleNamespace(status=500, reason="boom"),
                        content=b"",
                    )

            return _FailingRequest()

    service = _FakeService(labels_resource=_FailingLabelsResource())
    monkeypatch.setattr(gmail_labels, "_gmail_service", lambda: service)

    with pytest.raises(RuntimeError, match="creating label"):
        gmail_labels.gmail_create_label(name="Important")


def test_gmail_modify_message_labels_raises_on_unknown_label(monkeypatch) -> None:
    service = _FakeService(
        labels_resource=_FakeLabelsResource(list_payload={"labels": []})
    )
    monkeypatch.setattr(gmail_labels, "_gmail_service", lambda: service)

    with pytest.raises(ValueError, match="Unknown Gmail label"):
        gmail_labels.gmail_modify_message_labels(
            message_id="m1",
            add_labels=["DoesNotExist"],
        )


def test_gmail_modify_thread_labels_raises_runtime_error_on_http_error(
    monkeypatch,
) -> None:
    class _FailingThreadsResource(_FakeThreadsResource):
        def modify(self, **kwargs):
            self.modify_calls.append(kwargs)

            class _FailingRequest:
                def execute(self):
                    raise HttpError(
                        resp=SimpleNamespace(status=500, reason="boom"),
                        content=b"",
                    )

            return _FailingRequest()

    labels_resource = _FakeLabelsResource(
        list_payload={"labels": [{"id": "Label_1", "name": "Projects", "type": "USER"}]}
    )
    service = _FakeService(
        labels_resource=labels_resource,
        threads_resource=_FailingThreadsResource(),
    )
    monkeypatch.setattr(gmail_labels, "_gmail_service", lambda: service)

    with pytest.raises(RuntimeError, match="modifying thread labels"):
        gmail_labels.gmail_modify_thread_labels(
            thread_id="t1",
            add_labels=["Projects"],
        )
