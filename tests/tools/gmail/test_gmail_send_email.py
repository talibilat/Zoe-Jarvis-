from __future__ import annotations

import base64
import importlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

gmail_send = importlib.import_module("src.tools.emails.gmail.gmail_send_email")


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

    def has_scopes(self, _scopes) -> bool:
        return True


class FakeFlow:
    def __init__(self, creds: FakeCreds):
        self._creds = creds
        self.run_calls = 0

    def run_local_server(self, *, port: int):
        self.run_calls += 1
        assert port == 0
        return self._creds


def _invoke_default_call() -> dict | None:
    return gmail_send.gmail_send_email(
        email_to="to@example.com",
        email_from="from@example.com",
        subject="Hello",
        body="This is a body",
    )


def _service_with_send_response(response: dict | None = None) -> MagicMock:
    service = MagicMock()
    service.users.return_value.messages.return_value.send.return_value.execute.return_value = (
        response or {"id": "sent-1", "threadId": "thread-1"}
    )
    return service


def test_send_uses_existing_valid_token_without_oauth(
    monkeypatch, tmp_path: Path
) -> None:
    token_file = tmp_path / "token.json"
    backup_file = tmp_path / "token.json.bak"
    creds_file = tmp_path / "credentials.json"

    token_file.write_text(
        '{"scopes":["https://www.googleapis.com/auth/gmail.compose"]}',
        encoding="utf-8",
    )
    creds_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(gmail_send, "TOKEN_FILE", str(token_file))
    monkeypatch.setattr(gmail_send, "TOKEN_BACKUP_FILE", str(backup_file))
    monkeypatch.setattr(gmail_send, "CREDS_FILE", str(creds_file))

    creds = FakeCreds(valid=True)
    monkeypatch.setattr(
        gmail_send.Credentials,
        "from_authorized_user_file",
        lambda *_args, **_kwargs: creds,
    )

    oauth_factory = MagicMock()
    monkeypatch.setattr(
        gmail_send.InstalledAppFlow,
        "from_client_secrets_file",
        oauth_factory,
    )

    service = _service_with_send_response()
    build_mock = MagicMock(return_value=service)
    monkeypatch.setattr(gmail_send, "build", build_mock)

    result = _invoke_default_call()

    assert result == {"id": "sent-1", "threadId": "thread-1"}
    oauth_factory.assert_not_called()
    assert build_mock.call_args.kwargs["credentials"] is creds


def test_send_calls_messages_send_with_encoded_payload(
    monkeypatch,
    tmp_path: Path,
) -> None:
    token_file = tmp_path / "token.json"
    backup_file = tmp_path / "token.json.bak"
    creds_file = tmp_path / "credentials.json"

    token_file.write_text(
        '{"scopes":["https://www.googleapis.com/auth/gmail.compose"]}',
        encoding="utf-8",
    )
    creds_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(gmail_send, "TOKEN_FILE", str(token_file))
    monkeypatch.setattr(gmail_send, "TOKEN_BACKUP_FILE", str(backup_file))
    monkeypatch.setattr(gmail_send, "CREDS_FILE", str(creds_file))

    creds = FakeCreds(valid=True)
    monkeypatch.setattr(
        gmail_send.Credentials,
        "from_authorized_user_file",
        lambda *_args, **_kwargs: creds,
    )

    oauth_factory = MagicMock(return_value=FakeFlow(FakeCreds(valid=True)))
    monkeypatch.setattr(
        gmail_send.InstalledAppFlow,
        "from_client_secrets_file",
        oauth_factory,
    )

    service = _service_with_send_response({"id": "abc", "threadId": "t1"})
    monkeypatch.setattr(gmail_send, "build", lambda *_args, **_kwargs: service)

    result = _invoke_default_call()

    assert result == {"id": "abc", "threadId": "t1"}
    send_kwargs = service.users.return_value.messages.return_value.send.call_args.kwargs
    assert send_kwargs["userId"] == "me"

    encoded_raw = send_kwargs["body"]["raw"]
    decoded = base64.urlsafe_b64decode(encoded_raw.encode("utf-8")).decode("utf-8")

    assert "To: to@example.com" in decoded
    assert "From: from@example.com" in decoded
    assert "Subject: Hello" in decoded
    assert "This is a body" in decoded


def test_send_raises_runtime_error_on_http_error(monkeypatch, tmp_path: Path) -> None:
    token_file = tmp_path / "token.json"
    backup_file = tmp_path / "token.json.bak"
    creds_file = tmp_path / "credentials.json"

    token_file.write_text(
        '{"scopes":["https://www.googleapis.com/auth/gmail.compose"]}',
        encoding="utf-8",
    )
    creds_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(gmail_send, "TOKEN_FILE", str(token_file))
    monkeypatch.setattr(gmail_send, "TOKEN_BACKUP_FILE", str(backup_file))
    monkeypatch.setattr(gmail_send, "CREDS_FILE", str(creds_file))

    creds = FakeCreds(valid=True)
    monkeypatch.setattr(
        gmail_send.Credentials,
        "from_authorized_user_file",
        lambda *_args, **_kwargs: creds,
    )
    monkeypatch.setattr(
        gmail_send.InstalledAppFlow,
        "from_client_secrets_file",
        MagicMock(),
    )

    service = _service_with_send_response()
    service.users.return_value.messages.return_value.send.return_value.execute.side_effect = HttpError(
        resp=SimpleNamespace(status=500, reason="boom"), content=b""
    )
    monkeypatch.setattr(gmail_send, "build", lambda *_args, **_kwargs: service)

    with pytest.raises(RuntimeError, match="Gmail send failed"):
        _invoke_default_call()


def test_send_reauths_when_token_missing_compose_scope(
    monkeypatch, tmp_path: Path
) -> None:
    token_file = tmp_path / "token.json"
    backup_file = tmp_path / "token.json.bak"
    creds_file = tmp_path / "credentials.json"

    token_file.write_text(
        '{"scopes":["https://www.googleapis.com/auth/gmail.readonly"]}',
        encoding="utf-8",
    )
    creds_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(gmail_send, "TOKEN_FILE", str(token_file))
    monkeypatch.setattr(gmail_send, "TOKEN_BACKUP_FILE", str(backup_file))
    monkeypatch.setattr(gmail_send, "CREDS_FILE", str(creds_file))

    from_file_mock = MagicMock(return_value=FakeCreds(valid=True))
    monkeypatch.setattr(
        gmail_send.Credentials,
        "from_authorized_user_file",
        from_file_mock,
    )

    oauth_creds = FakeCreds(valid=True, payload='{"token":"oauth-token"}')
    oauth_factory = MagicMock(return_value=FakeFlow(oauth_creds))
    monkeypatch.setattr(
        gmail_send.InstalledAppFlow,
        "from_client_secrets_file",
        oauth_factory,
    )

    service = _service_with_send_response()
    build_mock = MagicMock(return_value=service)
    monkeypatch.setattr(gmail_send, "build", build_mock)

    result = _invoke_default_call()

    assert result == {"id": "sent-1", "threadId": "thread-1"}
    from_file_mock.assert_not_called()
    oauth_factory.assert_called_once_with(str(creds_file), gmail_send.SCOPES)
    assert build_mock.call_args.kwargs["credentials"] is oauth_creds
