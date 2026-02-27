from __future__ import annotations

import base64
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

import src.tools.gmail.gmail_draft as gmail_draft


class FakeCreds:
    def __init__(
        self,
        *,
        valid: bool,
        expired: bool = False,
        refresh_token: str | None = None,
        payload: str = '{"token":"new-token"}',
    ):
        self.valid = valid
        self.expired = expired
        self.refresh_token = refresh_token
        self._payload = payload
        self.refresh_calls = 0

    def refresh(self, _request) -> None:
        self.refresh_calls += 1
        self.valid = True
        self.expired = False

    def to_json(self) -> str:
        return self._payload


class FakeFlow:
    def __init__(self, creds: FakeCreds):
        self._creds = creds
        self.run_calls = 0
        self.last_port: int | None = None

    def run_local_server(self, *, port: int):
        self.run_calls += 1
        self.last_port = port
        return self._creds


@pytest.fixture
def draft_paths(monkeypatch, tmp_path: Path) -> tuple[Path, Path, Path]:
    token_file = tmp_path / "token.json"
    backup_file = tmp_path / "token.json.bak"
    creds_file = tmp_path / "credentials.json"
    creds_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(gmail_draft, "TOKEN_FILE", str(token_file))
    monkeypatch.setattr(gmail_draft, "TOKEN_BACKUP_FILE", str(backup_file))
    monkeypatch.setattr(gmail_draft, "CREDS_FILE", str(creds_file))
    return token_file, backup_file, creds_file


def _service_with_draft_response(response: dict | None = None) -> MagicMock:
    service = MagicMock()
    service.users.return_value.drafts.return_value.create.return_value.execute.return_value = (
        response or {"id": "draft-1", "message": {"id": "msg-1"}}
    )
    return service


def _patch_build(monkeypatch, service: MagicMock) -> MagicMock:
    build_mock = MagicMock(return_value=service)
    monkeypatch.setattr(gmail_draft, "build", build_mock)
    return build_mock


def _invoke_default_call() -> dict | None:
    return gmail_draft.gmail_create_draft(
        email_to="to@example.com",
        email_from="from@example.com",
        subject="Hello",
        body="This is a body",
    )


def test_uses_existing_valid_token_without_refresh_or_oauth(
    monkeypatch, draft_paths
) -> None:
    token_file, _, _ = draft_paths
    token_file.write_text("existing-token", encoding="utf-8")
    creds = FakeCreds(valid=True)

    monkeypatch.setattr(
        gmail_draft.Credentials,
        "from_authorized_user_file",
        lambda *_args, **_kwargs: creds,
    )
    oauth_mock = MagicMock()
    monkeypatch.setattr(
        gmail_draft.InstalledAppFlow, "from_client_secrets_file", oauth_mock
    )
    service = _service_with_draft_response()
    _patch_build(monkeypatch, service)

    result = _invoke_default_call()
    assert result["id"] == "draft-1"
    assert creds.refresh_calls == 0
    oauth_mock.assert_not_called()


def test_refreshes_expired_credentials_with_refresh_token(
    monkeypatch, draft_paths
) -> None:
    token_file, _, _ = draft_paths
    token_file.write_text("old-token", encoding="utf-8")
    creds = FakeCreds(valid=False, expired=True, refresh_token="refresh")

    monkeypatch.setattr(
        gmail_draft.Credentials,
        "from_authorized_user_file",
        lambda *_args, **_kwargs: creds,
    )
    monkeypatch.setattr(
        gmail_draft.InstalledAppFlow, "from_client_secrets_file", MagicMock()
    )
    service = _service_with_draft_response()
    _patch_build(monkeypatch, service)

    _invoke_default_call()
    assert creds.refresh_calls == 1
    assert token_file.read_text(encoding="utf-8") == creds.to_json()


def test_runs_oauth_flow_when_token_is_missing(monkeypatch, draft_paths) -> None:
    _, _, _ = draft_paths
    oauth_creds = FakeCreds(valid=True, payload='{"token":"oauth-token"}')
    flow = FakeFlow(oauth_creds)

    monkeypatch.setattr(
        gmail_draft.Credentials,
        "from_authorized_user_file",
        lambda *_args, **_kwargs: None,
    )
    flow_factory = MagicMock(return_value=flow)
    monkeypatch.setattr(
        gmail_draft.InstalledAppFlow, "from_client_secrets_file", flow_factory
    )
    service = _service_with_draft_response()
    _patch_build(monkeypatch, service)

    _invoke_default_call()
    assert flow.run_calls == 1
    assert flow.last_port == 0


def test_writes_backup_when_token_exists(monkeypatch, draft_paths) -> None:
    token_file, backup_file, _ = draft_paths
    token_file.write_text("old-token-content", encoding="utf-8")
    creds = FakeCreds(valid=False, expired=True, refresh_token="refresh")

    monkeypatch.setattr(
        gmail_draft.Credentials,
        "from_authorized_user_file",
        lambda *_args, **_kwargs: creds,
    )
    monkeypatch.setattr(
        gmail_draft.InstalledAppFlow, "from_client_secrets_file", MagicMock()
    )
    service = _service_with_draft_response()
    _patch_build(monkeypatch, service)

    _invoke_default_call()
    assert backup_file.read_text(encoding="utf-8") == "old-token-content"
    assert token_file.read_text(encoding="utf-8") == creds.to_json()


def test_skips_backup_when_backup_path_matches_token(monkeypatch, draft_paths) -> None:
    token_file, _, _ = draft_paths
    token_file.write_text("old-token-content", encoding="utf-8")
    monkeypatch.setattr(gmail_draft, "TOKEN_BACKUP_FILE", str(token_file))
    creds = FakeCreds(valid=False, expired=True, refresh_token="refresh")

    monkeypatch.setattr(
        gmail_draft.Credentials,
        "from_authorized_user_file",
        lambda *_args, **_kwargs: creds,
    )
    monkeypatch.setattr(
        gmail_draft.InstalledAppFlow, "from_client_secrets_file", MagicMock()
    )
    service = _service_with_draft_response()
    _patch_build(monkeypatch, service)

    _invoke_default_call()
    assert token_file.read_text(encoding="utf-8") == creds.to_json()


def test_sends_encoded_email_payload_in_create_request(
    monkeypatch, draft_paths
) -> None:
    token_file, _, _ = draft_paths
    token_file.write_text("old-token", encoding="utf-8")
    creds = FakeCreds(valid=True)
    monkeypatch.setattr(
        gmail_draft.Credentials,
        "from_authorized_user_file",
        lambda *_args, **_kwargs: creds,
    )
    monkeypatch.setattr(
        gmail_draft.InstalledAppFlow, "from_client_secrets_file", MagicMock()
    )
    service = _service_with_draft_response()
    _patch_build(monkeypatch, service)

    _invoke_default_call()

    create_kwargs = (
        service.users.return_value.drafts.return_value.create.call_args.kwargs
    )
    encoded_raw = create_kwargs["body"]["message"]["raw"]
    decoded = base64.urlsafe_b64decode(encoded_raw.encode("utf-8")).decode("utf-8")

    assert create_kwargs["userId"] == "me"
    assert "To: to@example.com" in decoded
    assert "From: from@example.com" in decoded
    assert "Subject: Hello" in decoded
    assert "This is a body" in decoded


def test_returns_draft_payload_on_success(monkeypatch, draft_paths) -> None:
    token_file, _, _ = draft_paths
    token_file.write_text("old-token", encoding="utf-8")
    creds = FakeCreds(valid=True)
    monkeypatch.setattr(
        gmail_draft.Credentials,
        "from_authorized_user_file",
        lambda *_args, **_kwargs: creds,
    )
    monkeypatch.setattr(
        gmail_draft.InstalledAppFlow, "from_client_secrets_file", MagicMock()
    )
    service = _service_with_draft_response({"id": "abc", "message": {"id": "msg"}})
    _patch_build(monkeypatch, service)

    result = _invoke_default_call()
    assert result == {"id": "abc", "message": {"id": "msg"}}


def test_returns_none_on_http_error(monkeypatch, draft_paths) -> None:
    token_file, _, _ = draft_paths
    token_file.write_text("old-token", encoding="utf-8")
    creds = FakeCreds(valid=True)
    monkeypatch.setattr(
        gmail_draft.Credentials,
        "from_authorized_user_file",
        lambda *_args, **_kwargs: creds,
    )
    monkeypatch.setattr(
        gmail_draft.InstalledAppFlow, "from_client_secrets_file", MagicMock()
    )

    service = _service_with_draft_response()
    service.users.return_value.drafts.return_value.create.return_value.execute.side_effect = HttpError(
        resp=SimpleNamespace(status=400, reason="bad"), content=b"bad"
    )
    _patch_build(monkeypatch, service)

    assert _invoke_default_call() is None


def test_build_receives_selected_credentials(monkeypatch, draft_paths) -> None:
    token_file, _, _ = draft_paths
    token_file.write_text("old-token", encoding="utf-8")
    creds = FakeCreds(valid=True)
    monkeypatch.setattr(
        gmail_draft.Credentials,
        "from_authorized_user_file",
        lambda *_args, **_kwargs: creds,
    )
    monkeypatch.setattr(
        gmail_draft.InstalledAppFlow, "from_client_secrets_file", MagicMock()
    )
    service = _service_with_draft_response()
    build_mock = _patch_build(monkeypatch, service)

    _invoke_default_call()
    assert build_mock.call_args.kwargs["credentials"] == creds


def test_oauth_flow_uses_configured_credentials_file_and_scopes(
    monkeypatch, draft_paths
) -> None:
    _, _, creds_file = draft_paths
    oauth_creds = FakeCreds(valid=True, payload='{"token":"oauth-token"}')
    flow = FakeFlow(oauth_creds)
    flow_factory = MagicMock(return_value=flow)

    monkeypatch.setattr(
        gmail_draft.Credentials,
        "from_authorized_user_file",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        gmail_draft.InstalledAppFlow, "from_client_secrets_file", flow_factory
    )
    service = _service_with_draft_response()
    _patch_build(monkeypatch, service)

    _invoke_default_call()
    assert flow_factory.call_args.args[0] == str(creds_file)
    assert flow_factory.call_args.args[1] == gmail_draft.SCOPES
