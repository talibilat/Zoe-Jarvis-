from __future__ import annotations

from types import SimpleNamespace

import pytest
from googleapiclient.errors import HttpError

import src.tools.emails.gmail.gmail_forwarding as gmail_forwarding


class _Executable:
    def __init__(self, payload: dict):
        self._payload = payload

    def execute(self) -> dict:
        return self._payload


class _FakeForwardingAddressesResource:
    def __init__(self, create_payload: dict):
        self.create_payload = create_payload
        self.create_calls: list[dict] = []

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return _Executable(self.create_payload)


class _FakeSettingsResource:
    def __init__(
        self,
        forwarding_addresses_resource: _FakeForwardingAddressesResource,
        auto_forwarding_payload: dict,
    ):
        self._forwarding_addresses = forwarding_addresses_resource
        self._auto_forwarding_payload = auto_forwarding_payload
        self.update_calls: list[dict] = []

    def forwardingAddresses(self):
        return self._forwarding_addresses

    def updateAutoForwarding(self, **kwargs):
        self.update_calls.append(kwargs)
        return _Executable(self._auto_forwarding_payload)


class _FakeService:
    def __init__(self, settings_resource: _FakeSettingsResource):
        self._settings = settings_resource

    def users(self):
        return self

    def settings(self):
        return self._settings


def test_enable_forwarding_enables_auto_forwarding_when_accepted(monkeypatch) -> None:
    forwarding_addresses = _FakeForwardingAddressesResource(
        create_payload={
            "forwardingEmail": "dest@example.com",
            "verificationStatus": "accepted",
        }
    )
    settings = _FakeSettingsResource(
        forwarding_addresses_resource=forwarding_addresses,
        auto_forwarding_payload={"enabled": True, "disposition": "trash"},
    )
    monkeypatch.setattr(
        gmail_forwarding, "_gmail_service", lambda: _FakeService(settings)
    )
    monkeypatch.setenv("GMAIL_FORWARDING_ALLOWLIST", "dest@example.com")

    result = gmail_forwarding.enable_forwarding("dest@example.com", confirm=True)

    assert result == {
        "forwarding_address": {
            "forwardingEmail": "dest@example.com",
            "verificationStatus": "accepted",
        },
        "auto_forwarding": {"enabled": True, "disposition": "trash"},
    }
    assert forwarding_addresses.create_calls[0]["body"] == {
        "forwardingEmail": "dest@example.com"
    }
    assert settings.update_calls[0]["body"] == {
        "emailAddress": "dest@example.com",
        "enabled": True,
        "disposition": "trash",
    }


def test_enable_forwarding_skips_auto_forwarding_when_not_verified(
    monkeypatch,
) -> None:
    forwarding_addresses = _FakeForwardingAddressesResource(
        create_payload={
            "forwardingEmail": "dest@example.com",
            "verificationStatus": "pending",
        }
    )
    settings = _FakeSettingsResource(
        forwarding_addresses_resource=forwarding_addresses,
        auto_forwarding_payload={"enabled": True},
    )
    monkeypatch.setattr(
        gmail_forwarding, "_gmail_service", lambda: _FakeService(settings)
    )
    monkeypatch.setenv("GMAIL_FORWARDING_ALLOWLIST", "dest@example.com")

    result = gmail_forwarding.enable_forwarding("dest@example.com", confirm=True)

    assert result == {
        "forwarding_address": {
            "forwardingEmail": "dest@example.com",
            "verificationStatus": "pending",
        },
        "auto_forwarding": None,
    }
    assert settings.update_calls == []


def test_enable_forwarding_rejects_empty_email(monkeypatch) -> None:
    forwarding_addresses = _FakeForwardingAddressesResource(create_payload={})
    settings = _FakeSettingsResource(
        forwarding_addresses_resource=forwarding_addresses,
        auto_forwarding_payload={},
    )
    monkeypatch.setattr(
        gmail_forwarding, "_gmail_service", lambda: _FakeService(settings)
    )

    with pytest.raises(ValueError, match="forwarding_email"):
        gmail_forwarding.enable_forwarding("   ")


def test_enable_forwarding_rejects_invalid_disposition(monkeypatch) -> None:
    forwarding_addresses = _FakeForwardingAddressesResource(create_payload={})
    settings = _FakeSettingsResource(
        forwarding_addresses_resource=forwarding_addresses,
        auto_forwarding_payload={},
    )
    monkeypatch.setattr(
        gmail_forwarding, "_gmail_service", lambda: _FakeService(settings)
    )

    with pytest.raises(ValueError, match="disposition"):
        gmail_forwarding.enable_forwarding("dest@example.com", disposition="invalid")


def test_enable_forwarding_requires_confirm(monkeypatch) -> None:
    forwarding_addresses = _FakeForwardingAddressesResource(create_payload={})
    settings = _FakeSettingsResource(
        forwarding_addresses_resource=forwarding_addresses,
        auto_forwarding_payload={},
    )
    monkeypatch.setattr(
        gmail_forwarding, "_gmail_service", lambda: _FakeService(settings)
    )
    monkeypatch.setenv("GMAIL_FORWARDING_ALLOWLIST", "dest@example.com")

    with pytest.raises(ValueError, match="confirm=True"):
        gmail_forwarding.enable_forwarding("dest@example.com")


def test_enable_forwarding_rejects_non_allowlisted_target(monkeypatch) -> None:
    forwarding_addresses = _FakeForwardingAddressesResource(create_payload={})
    settings = _FakeSettingsResource(
        forwarding_addresses_resource=forwarding_addresses,
        auto_forwarding_payload={},
    )
    monkeypatch.setattr(
        gmail_forwarding, "_gmail_service", lambda: _FakeService(settings)
    )
    monkeypatch.setenv("GMAIL_FORWARDING_ALLOWLIST", "other@example.com")

    with pytest.raises(PermissionError, match="not in GMAIL_FORWARDING_ALLOWLIST"):
        gmail_forwarding.enable_forwarding("dest@example.com", confirm=True)


def test_enable_forwarding_forwards_custom_disposition_and_enabled(
    monkeypatch,
) -> None:
    forwarding_addresses = _FakeForwardingAddressesResource(
        create_payload={
            "forwardingEmail": "dest@example.com",
            "verificationStatus": "accepted",
        }
    )
    settings = _FakeSettingsResource(
        forwarding_addresses_resource=forwarding_addresses,
        auto_forwarding_payload={"enabled": False, "disposition": "archive"},
    )
    monkeypatch.setattr(
        gmail_forwarding, "_gmail_service", lambda: _FakeService(settings)
    )
    monkeypatch.setenv("GMAIL_FORWARDING_ALLOWLIST", "dest@example.com")

    result = gmail_forwarding.enable_forwarding(
        "dest@example.com", disposition="archive", enabled=False, confirm=True
    )

    assert result == {
        "forwarding_address": {
            "forwardingEmail": "dest@example.com",
            "verificationStatus": "accepted",
        },
        "auto_forwarding": {"enabled": False, "disposition": "archive"},
    }
    assert settings.update_calls[0]["body"]["enabled"] is False
    assert settings.update_calls[0]["body"]["disposition"] == "archive"


def test_enable_forwarding_raises_runtime_error_on_http_error(monkeypatch) -> None:
    class _FailingForwardingAddressesResource(_FakeForwardingAddressesResource):
        def create(self, **kwargs):
            self.create_calls.append(kwargs)

            class _FailingRequest:
                def execute(self):
                    raise HttpError(
                        resp=SimpleNamespace(status=500, reason="boom"),
                        content=b"",
                    )

            return _FailingRequest()

    forwarding_addresses = _FailingForwardingAddressesResource(create_payload={})
    settings = _FakeSettingsResource(
        forwarding_addresses_resource=forwarding_addresses,
        auto_forwarding_payload={},
    )
    monkeypatch.setattr(
        gmail_forwarding, "_gmail_service", lambda: _FakeService(settings)
    )
    monkeypatch.setenv("GMAIL_FORWARDING_ALLOWLIST", "dest@example.com")

    with pytest.raises(RuntimeError, match="configuring forwarding"):
        gmail_forwarding.enable_forwarding("dest@example.com", confirm=True)
