from __future__ import annotations

import base64
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

import src.tools.emails.gmail.gmail_upload as gmail_upload


def _draft_service(payload: dict | None = None) -> MagicMock:
    service = MagicMock()
    service.users.return_value.drafts.return_value.create.return_value.execute.return_value = (
        payload or {"id": "draft-1", "message": {"id": "msg-1"}}
    )
    return service


def _sent_service(payload: dict | None = None) -> MagicMock:
    service = MagicMock()
    service.users.return_value.messages.return_value.send.return_value.execute.return_value = (
        payload or {"id": "sent-1", "threadId": "thread-1"}
    )
    return service


def _decode_raw_message(encoded_raw: str):
    raw_bytes = base64.urlsafe_b64decode(encoded_raw.encode("utf-8"))
    return BytesParser(policy=default).parsebytes(raw_bytes)


def test_validate_attachment_paths_requires_at_least_one_path() -> None:
    with pytest.raises(ValueError):
        gmail_upload._validate_attachment_paths([])


def test_validate_attachment_paths_rejects_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.txt"

    with pytest.raises(FileNotFoundError):
        gmail_upload._validate_attachment_paths([str(missing)])


def test_validate_attachment_paths_rejects_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        gmail_upload._validate_attachment_paths([str(tmp_path)])


def test_create_draft_with_attachments_encodes_payload(
    monkeypatch, tmp_path: Path
) -> None:
    attachment = tmp_path / "report.txt"
    attachment.write_text("hello world", encoding="utf-8")

    service = _draft_service({"id": "draft-abc", "message": {"id": "msg-abc"}})
    build_mock = MagicMock(return_value=service)

    monkeypatch.setattr(gmail_upload, "_load_compose_credentials", lambda: "creds")
    monkeypatch.setattr(gmail_upload, "build", build_mock)

    result = gmail_upload.gmail_create_draft_with_attachments(
        email_to="to@example.com",
        email_from="from@example.com",
        subject="Subject",
        body="Body text",
        attachment_paths=[str(attachment)],
    )

    assert result == {"id": "draft-abc", "message": {"id": "msg-abc"}}
    assert build_mock.call_args.kwargs["credentials"] == "creds"

    create_kwargs = (
        service.users.return_value.drafts.return_value.create.call_args.kwargs
    )
    assert create_kwargs["userId"] == "me"

    parsed = _decode_raw_message(create_kwargs["body"]["message"]["raw"])
    assert parsed["To"] == "to@example.com"
    assert parsed["From"] == "from@example.com"
    assert parsed["Subject"] == "Subject"

    attachments = list(parsed.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename() == "report.txt"
    assert attachments[0].get_payload(decode=True) == b"hello world"


def test_send_email_with_attachments_uses_messages_send(
    monkeypatch,
    tmp_path: Path,
) -> None:
    attachment = tmp_path / "notes.csv"
    attachment.write_text("a,b\n1,2\n", encoding="utf-8")

    service = _sent_service({"id": "sent-xyz", "threadId": "thread-xyz"})
    monkeypatch.setattr(gmail_upload, "_load_compose_credentials", lambda: "creds")
    monkeypatch.setattr(gmail_upload, "build", lambda *_args, **_kwargs: service)

    result = gmail_upload.gmail_send_email_with_attachments(
        email_to="to@example.com",
        email_from="from@example.com",
        subject="Data",
        body="Attached",
        attachment_paths=[str(attachment)],
    )

    assert result == {"id": "sent-xyz", "threadId": "thread-xyz"}
    send_kwargs = service.users.return_value.messages.return_value.send.call_args.kwargs
    assert send_kwargs["userId"] == "me"

    parsed = _decode_raw_message(send_kwargs["body"]["raw"])
    attachments = list(parsed.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename() == "notes.csv"


def test_create_draft_with_attachments_returns_none_on_http_error(
    monkeypatch, tmp_path: Path
) -> None:
    attachment = tmp_path / "report.txt"
    attachment.write_text("hello world", encoding="utf-8")

    service = _draft_service()
    service.users.return_value.drafts.return_value.create.return_value.execute.side_effect = HttpError(
        resp=SimpleNamespace(status=500, reason="boom"), content=b""
    )

    monkeypatch.setattr(gmail_upload, "_load_compose_credentials", lambda: "creds")
    monkeypatch.setattr(gmail_upload, "build", lambda *_args, **_kwargs: service)

    result = gmail_upload.gmail_create_draft_with_attachments(
        email_to="to@example.com",
        email_from="from@example.com",
        subject="Subject",
        body="Body text",
        attachment_paths=[str(attachment)],
    )

    assert result is None


def test_send_email_with_attachments_raises_on_http_error(
    monkeypatch, tmp_path: Path
) -> None:
    attachment = tmp_path / "notes.csv"
    attachment.write_text("a,b\n1,2\n", encoding="utf-8")

    service = _sent_service()
    service.users.return_value.messages.return_value.send.return_value.execute.side_effect = HttpError(
        resp=SimpleNamespace(status=500, reason="boom"), content=b""
    )

    monkeypatch.setattr(gmail_upload, "_load_compose_credentials", lambda: "creds")
    monkeypatch.setattr(gmail_upload, "build", lambda *_args, **_kwargs: service)

    with pytest.raises(RuntimeError, match="Gmail attachment send failed"):
        gmail_upload.gmail_send_email_with_attachments(
            email_to="to@example.com",
            email_from="from@example.com",
            subject="Data",
            body="Attached",
            attachment_paths=[str(attachment)],
        )
