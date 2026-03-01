from __future__ import annotations

from types import SimpleNamespace

import pytest
from googleapiclient.errors import HttpError

import src.tools.emails.gmail.gmail_filters as gmail_filters


class _Executable:
    def __init__(self, payload: dict):
        self._payload = payload

    def execute(self) -> dict:
        return self._payload


class _FakeFiltersResource:
    def __init__(
        self,
        *,
        create_payload: dict | None = None,
        list_payload: dict | None = None,
        get_payload: dict | None = None,
    ):
        self.create_payload = create_payload or {"id": "f1"}
        self.list_payload = list_payload or {"filter": []}
        self.get_payload = get_payload or {"id": "f1"}
        self.create_calls: list[dict] = []
        self.list_calls: list[dict] = []
        self.get_calls: list[dict] = []
        self.delete_calls: list[dict] = []

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return _Executable(self.create_payload)

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        return _Executable(self.list_payload)

    def get(self, **kwargs):
        self.get_calls.append(kwargs)
        return _Executable(self.get_payload)

    def delete(self, **kwargs):
        self.delete_calls.append(kwargs)
        return _Executable({})


class _FakeSettingsResource:
    def __init__(self, filters_resource: _FakeFiltersResource):
        self._filters = filters_resource

    def filters(self):
        return self._filters


class _FakeService:
    def __init__(self, settings_resource: _FakeSettingsResource):
        self._settings = settings_resource

    def users(self):
        return self

    def settings(self):
        return self._settings


def test_create_filter_forwards_payload(monkeypatch) -> None:
    filters_resource = _FakeFiltersResource(create_payload={"id": "f1"})
    monkeypatch.setattr(
        gmail_filters,
        "_gmail_service",
        lambda: _FakeService(_FakeSettingsResource(filters_resource)),
    )

    result = gmail_filters.create_filter(
        criteria={"from": "sender@example.com"},
        action={"removeLabelIds": ["INBOX"]},
    )

    assert result == {"id": "f1"}
    assert filters_resource.create_calls[0]["body"] == {
        "criteria": {"from": "sender@example.com"},
        "action": {"removeLabelIds": ["INBOX"]},
    }


def test_create_filter_rejects_empty_criteria_or_action(monkeypatch) -> None:
    filters_resource = _FakeFiltersResource()
    monkeypatch.setattr(
        gmail_filters,
        "_gmail_service",
        lambda: _FakeService(_FakeSettingsResource(filters_resource)),
    )

    with pytest.raises(ValueError, match="criteria"):
        gmail_filters.create_filter(criteria={}, action={"addLabelIds": ["STARRED"]})

    with pytest.raises(ValueError, match="action"):
        gmail_filters.create_filter(criteria={"query": "project"}, action={})


def test_list_filters_returns_filter_entries(monkeypatch) -> None:
    filters_resource = _FakeFiltersResource(
        list_payload={"filter": [{"id": "f1"}, {"id": "f2"}]}
    )
    monkeypatch.setattr(
        gmail_filters,
        "_gmail_service",
        lambda: _FakeService(_FakeSettingsResource(filters_resource)),
    )

    result = gmail_filters.list_filters()

    assert result == [{"id": "f1"}, {"id": "f2"}]
    assert filters_resource.list_calls[0]["userId"] == "me"


def test_list_filters_returns_empty_when_key_missing(monkeypatch) -> None:
    filters_resource = _FakeFiltersResource(list_payload={})
    monkeypatch.setattr(
        gmail_filters,
        "_gmail_service",
        lambda: _FakeService(_FakeSettingsResource(filters_resource)),
    )

    assert gmail_filters.list_filters() == []


def test_get_filter_forwards_id(monkeypatch) -> None:
    filters_resource = _FakeFiltersResource(get_payload={"id": "f9"})
    monkeypatch.setattr(
        gmail_filters,
        "_gmail_service",
        lambda: _FakeService(_FakeSettingsResource(filters_resource)),
    )

    result = gmail_filters.get_filter("f9")

    assert result == {"id": "f9"}
    assert filters_resource.get_calls[0] == {"userId": "me", "id": "f9"}


def test_get_filter_rejects_empty_id(monkeypatch) -> None:
    filters_resource = _FakeFiltersResource()
    monkeypatch.setattr(
        gmail_filters,
        "_gmail_service",
        lambda: _FakeService(_FakeSettingsResource(filters_resource)),
    )

    with pytest.raises(ValueError, match="filter_id"):
        gmail_filters.get_filter(" ")


def test_delete_filter_returns_true_and_forwards_id(monkeypatch) -> None:
    filters_resource = _FakeFiltersResource()
    monkeypatch.setattr(
        gmail_filters,
        "_gmail_service",
        lambda: _FakeService(_FakeSettingsResource(filters_resource)),
    )

    result = gmail_filters.delete_filter("f1")

    assert result is True
    assert filters_resource.delete_calls[0] == {"userId": "me", "id": "f1"}


def test_delete_filter_rejects_empty_id(monkeypatch) -> None:
    filters_resource = _FakeFiltersResource()
    monkeypatch.setattr(
        gmail_filters,
        "_gmail_service",
        lambda: _FakeService(_FakeSettingsResource(filters_resource)),
    )

    with pytest.raises(ValueError, match="filter_id"):
        gmail_filters.delete_filter(" ")


def test_create_filter_raises_runtime_error_on_http_error(monkeypatch) -> None:
    class _FailingFiltersResource(_FakeFiltersResource):
        def create(self, **kwargs):
            self.create_calls.append(kwargs)

            class _FailingRequest:
                def execute(self):
                    raise HttpError(
                        resp=SimpleNamespace(status=500, reason="boom"),
                        content=b"",
                    )

            return _FailingRequest()

    resource = _FailingFiltersResource()
    monkeypatch.setattr(
        gmail_filters,
        "_gmail_service",
        lambda: _FakeService(_FakeSettingsResource(resource)),
    )

    with pytest.raises(RuntimeError, match="creating filter"):
        gmail_filters.create_filter(
            criteria={"from": "a@b.com"}, action={"addLabelIds": []}
        )


def test_list_filters_raises_runtime_error_on_http_error(monkeypatch) -> None:
    class _FailingFiltersResource(_FakeFiltersResource):
        def list(self, **kwargs):
            self.list_calls.append(kwargs)

            class _FailingRequest:
                def execute(self):
                    raise HttpError(
                        resp=SimpleNamespace(status=500, reason="boom"),
                        content=b"",
                    )

            return _FailingRequest()

    resource = _FailingFiltersResource()
    monkeypatch.setattr(
        gmail_filters,
        "_gmail_service",
        lambda: _FakeService(_FakeSettingsResource(resource)),
    )

    with pytest.raises(RuntimeError, match="listing filters"):
        gmail_filters.list_filters()


def test_get_filter_raises_runtime_error_on_http_error(monkeypatch) -> None:
    class _FailingFiltersResource(_FakeFiltersResource):
        def get(self, **kwargs):
            self.get_calls.append(kwargs)

            class _FailingRequest:
                def execute(self):
                    raise HttpError(
                        resp=SimpleNamespace(status=500, reason="boom"),
                        content=b"",
                    )

            return _FailingRequest()

    resource = _FailingFiltersResource()
    monkeypatch.setattr(
        gmail_filters,
        "_gmail_service",
        lambda: _FakeService(_FakeSettingsResource(resource)),
    )

    with pytest.raises(RuntimeError, match="getting filter"):
        gmail_filters.get_filter("f1")


def test_delete_filter_raises_runtime_error_on_http_error(monkeypatch) -> None:
    class _FailingFiltersResource(_FakeFiltersResource):
        def delete(self, **kwargs):
            self.delete_calls.append(kwargs)

            class _FailingRequest:
                def execute(self):
                    raise HttpError(
                        resp=SimpleNamespace(status=500, reason="boom"),
                        content=b"",
                    )

            return _FailingRequest()

    resource = _FailingFiltersResource()
    monkeypatch.setattr(
        gmail_filters,
        "_gmail_service",
        lambda: _FakeService(_FakeSettingsResource(resource)),
    )

    with pytest.raises(RuntimeError, match="deleting filter"):
        gmail_filters.delete_filter("f1")
