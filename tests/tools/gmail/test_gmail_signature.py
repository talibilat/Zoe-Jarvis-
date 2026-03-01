from __future__ import annotations

from types import SimpleNamespace

import pytest
from googleapiclient.errors import HttpError

import src.tools.emails.gmail.gmail_signature as gmail_signature


class _Executable:
    def __init__(self, payload: dict):
        self._payload = payload

    def execute(self) -> dict:
        return self._payload


class _FakeSendAsResource:
    def __init__(self, aliases: list[dict], patch_payload: dict):
        self.aliases = aliases
        self.patch_payload = patch_payload
        self.list_calls: list[dict] = []
        self.patch_calls: list[dict] = []

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        return _Executable({"sendAs": self.aliases})

    def patch(self, **kwargs):
        self.patch_calls.append(kwargs)
        return _Executable(self.patch_payload)


class _FakeService:
    def __init__(self, send_as_resource: _FakeSendAsResource):
        self._send_as = send_as_resource

    def users(self):
        return self

    def settings(self):
        return self

    def sendAs(self):
        return self._send_as


def test_update_signature_uses_primary_alias(monkeypatch) -> None:
    send_as = _FakeSendAsResource(
        aliases=[
            {
                "sendAsEmail": "alias@example.com",
                "displayName": "Alias",
                "isPrimary": False,
            },
            {
                "sendAsEmail": "primary@example.com",
                "displayName": "Primary User",
                "isPrimary": True,
            },
        ],
        patch_payload={"signature": "Automated Signature"},
    )
    monkeypatch.setattr(
        gmail_signature, "_gmail_service", lambda: _FakeService(send_as)
    )

    result = gmail_signature.update_signature()

    assert result == "Automated Signature"
    assert send_as.list_calls[0]["userId"] == "me"
    assert send_as.patch_calls[0]["sendAsEmail"] == "primary@example.com"
    assert send_as.patch_calls[0]["body"] == {
        "displayName": "Primary User",
        "signature": "Automated Signature",
    }


def test_update_signature_forwards_explicit_alias_and_display_name(
    monkeypatch,
) -> None:
    send_as = _FakeSendAsResource(
        aliases=[
            {
                "sendAsEmail": "team@example.com",
                "displayName": "Team",
                "isPrimary": True,
            }
        ],
        patch_payload={"signature": "Team Signature"},
    )
    monkeypatch.setattr(
        gmail_signature, "_gmail_service", lambda: _FakeService(send_as)
    )

    result = gmail_signature.update_signature(
        signature="Team Signature",
        send_as_email="team@example.com",
        display_name="Ops Team",
    )

    assert result == "Team Signature"
    assert send_as.patch_calls[0]["body"] == {
        "displayName": "Ops Team",
        "signature": "Team Signature",
    }


def test_update_signature_rejects_empty_signature(monkeypatch) -> None:
    send_as = _FakeSendAsResource(aliases=[], patch_payload={})
    monkeypatch.setattr(
        gmail_signature, "_gmail_service", lambda: _FakeService(send_as)
    )

    with pytest.raises(ValueError, match="signature"):
        gmail_signature.update_signature(signature="   ")


def test_update_signature_raises_for_unknown_alias(monkeypatch) -> None:
    send_as = _FakeSendAsResource(
        aliases=[{"sendAsEmail": "primary@example.com", "isPrimary": True}],
        patch_payload={},
    )
    monkeypatch.setattr(
        gmail_signature, "_gmail_service", lambda: _FakeService(send_as)
    )

    with pytest.raises(ValueError, match="Unknown sendAsEmail"):
        gmail_signature.update_signature(send_as_email="missing@example.com")


def test_update_signature_raises_when_aliases_missing(monkeypatch) -> None:
    send_as = _FakeSendAsResource(aliases=[], patch_payload={})
    monkeypatch.setattr(
        gmail_signature, "_gmail_service", lambda: _FakeService(send_as)
    )

    with pytest.raises(RuntimeError, match="No send-as aliases"):
        gmail_signature.update_signature()


def test_update_signature_raises_when_alias_has_no_send_as_email(monkeypatch) -> None:
    send_as = _FakeSendAsResource(
        aliases=[{"displayName": "Broken Alias", "isPrimary": True}],
        patch_payload={},
    )
    monkeypatch.setattr(
        gmail_signature, "_gmail_service", lambda: _FakeService(send_as)
    )

    with pytest.raises(RuntimeError, match="does not include sendAsEmail"):
        gmail_signature.update_signature()


def test_update_signature_defaults_display_name_to_send_as_email(monkeypatch) -> None:
    send_as = _FakeSendAsResource(
        aliases=[
            {
                "sendAsEmail": "primary@example.com",
                "displayName": "",
                "isPrimary": True,
            }
        ],
        patch_payload={"signature": "Automated Signature"},
    )
    monkeypatch.setattr(
        gmail_signature, "_gmail_service", lambda: _FakeService(send_as)
    )

    gmail_signature.update_signature()

    assert send_as.patch_calls[0]["body"]["displayName"] == "primary@example.com"


def test_update_signature_raises_runtime_error_on_http_error(monkeypatch) -> None:
    class _FailingRequest:
        def execute(self):
            raise HttpError(
                resp=SimpleNamespace(status=500, reason="boom"), content=b""
            )

    class _FailingSendAsResource(_FakeSendAsResource):
        def patch(self, **kwargs):
            self.patch_calls.append(kwargs)
            return _FailingRequest()

    send_as = _FailingSendAsResource(
        aliases=[
            {
                "sendAsEmail": "primary@example.com",
                "displayName": "Primary",
                "isPrimary": True,
            }
        ],
        patch_payload={},
    )
    monkeypatch.setattr(
        gmail_signature, "_gmail_service", lambda: _FakeService(send_as)
    )

    with pytest.raises(RuntimeError, match="updating signature"):
        gmail_signature.update_signature()
