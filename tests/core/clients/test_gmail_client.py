from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from google.auth.exceptions import RefreshError

import src.core.clients.gmail_client as gmail_client_module


class FakeCreds:
    def __init__(
        self,
        *,
        valid: bool,
        expired: bool = False,
        refresh_token: str | None = None,
        payload: str = '{"token":"updated"}',
        refresh_error: Exception | None = None,
    ):
        self.valid = valid
        self.expired = expired
        self.refresh_token = refresh_token
        self.payload = payload
        self.refresh_error = refresh_error
        self.refresh_calls = 0

    def refresh(self, _request) -> None:
        self.refresh_calls += 1
        if self.refresh_error:
            raise self.refresh_error
        self.valid = True
        self.expired = False

    def to_json(self) -> str:
        return self.payload


class FakeFlow:
    def __init__(self, creds: FakeCreds):
        self.creds = creds
        self.run_calls = 0
        self.last_port: int | None = None
        self.last_open_browser: bool | None = None

    def run_local_server(self, *, port: int, open_browser: bool):
        self.run_calls += 1
        self.last_port = port
        self.last_open_browser = open_browser
        return self.creds


@pytest.fixture
def patched_paths(monkeypatch, tmp_path: Path) -> tuple[Path, Path, Path]:
    token_file = tmp_path / "token.json"
    backup_file = tmp_path / "token.json.bak"
    creds_file = tmp_path / "credentials.json"
    creds_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(gmail_client_module, "TOKEN_FILE", token_file)
    monkeypatch.setattr(gmail_client_module, "TOKEN_BACKUP_FILE", backup_file)
    monkeypatch.setattr(gmail_client_module, "CREDS_FILE", creds_file)
    return token_file, backup_file, creds_file


def test_valid_token_skips_oauth(monkeypatch, patched_paths) -> None:
    token_file, _, _ = patched_paths
    token_file.write_text("old-token", encoding="utf-8")
    creds = FakeCreds(valid=True)

    monkeypatch.setattr(
        gmail_client_module.Credentials,
        "from_authorized_user_file",
        lambda *_args, **_kwargs: creds,
    )
    oauth_factory = MagicMock()
    monkeypatch.setattr(
        gmail_client_module.InstalledAppFlow,
        "from_client_secrets_file",
        oauth_factory,
    )

    result = gmail_client_module.gmail_client()
    assert result is creds
    oauth_factory.assert_not_called()


def test_refresh_success_rewrites_token_and_creates_backup(
    monkeypatch, patched_paths
) -> None:
    token_file, backup_file, _ = patched_paths
    token_file.write_text("old-token", encoding="utf-8")
    creds = FakeCreds(valid=False, expired=True, refresh_token="refresh")

    monkeypatch.setattr(
        gmail_client_module.Credentials,
        "from_authorized_user_file",
        lambda *_args, **_kwargs: creds,
    )
    oauth_factory = MagicMock()
    monkeypatch.setattr(
        gmail_client_module.InstalledAppFlow,
        "from_client_secrets_file",
        oauth_factory,
    )

    gmail_client_module.gmail_client()
    assert creds.refresh_calls == 1
    assert token_file.read_text(encoding="utf-8") == creds.to_json()
    assert backup_file.read_text(encoding="utf-8") == "old-token"
    oauth_factory.assert_not_called()


def test_refresh_error_falls_back_to_oauth(monkeypatch, patched_paths) -> None:
    token_file, backup_file, _ = patched_paths
    token_file.write_text("old-token", encoding="utf-8")
    expired_creds = FakeCreds(
        valid=False,
        expired=True,
        refresh_token="refresh",
        refresh_error=RefreshError("invalid_grant"),
    )
    oauth_creds = FakeCreds(valid=True, payload='{"token":"oauth-token"}')
    flow = FakeFlow(oauth_creds)
    oauth_factory = MagicMock(return_value=flow)

    monkeypatch.setattr(
        gmail_client_module.Credentials,
        "from_authorized_user_file",
        lambda *_args, **_kwargs: expired_creds,
    )
    monkeypatch.setattr(
        gmail_client_module.InstalledAppFlow,
        "from_client_secrets_file",
        oauth_factory,
    )

    result = gmail_client_module.gmail_client()
    assert result is oauth_creds
    assert expired_creds.refresh_calls == 1
    assert flow.run_calls == 1
    assert token_file.read_text(encoding="utf-8") == oauth_creds.to_json()
    assert backup_file.read_text(encoding="utf-8") == "old-token"


def test_malformed_token_file_falls_back_to_oauth(monkeypatch, patched_paths) -> None:
    token_file, _, _ = patched_paths
    token_file.write_text("bad-json", encoding="utf-8")
    oauth_creds = FakeCreds(valid=True, payload='{"token":"oauth-token"}')
    flow = FakeFlow(oauth_creds)
    oauth_factory = MagicMock(return_value=flow)

    monkeypatch.setattr(
        gmail_client_module.Credentials,
        "from_authorized_user_file",
        MagicMock(side_effect=ValueError("bad token file")),
    )
    monkeypatch.setattr(
        gmail_client_module.InstalledAppFlow,
        "from_client_secrets_file",
        oauth_factory,
    )

    result = gmail_client_module.gmail_client()
    assert result is oauth_creds
    assert flow.run_calls == 1


def test_backup_is_skipped_when_backup_path_equals_token(
    monkeypatch, patched_paths
) -> None:
    token_file, _, _ = patched_paths
    token_file.write_text("old-token", encoding="utf-8")
    monkeypatch.setattr(gmail_client_module, "TOKEN_BACKUP_FILE", token_file)
    creds = FakeCreds(valid=False, expired=True, refresh_token="refresh")

    monkeypatch.setattr(
        gmail_client_module.Credentials,
        "from_authorized_user_file",
        lambda *_args, **_kwargs: creds,
    )
    monkeypatch.setattr(
        gmail_client_module.InstalledAppFlow,
        "from_client_secrets_file",
        MagicMock(),
    )

    gmail_client_module.gmail_client()
    assert token_file.read_text(encoding="utf-8") == creds.to_json()
