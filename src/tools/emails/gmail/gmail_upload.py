from __future__ import annotations

import base64
import mimetypes
import os
from email.message import EmailMessage
from pathlib import Path
from typing import Sequence

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.core.clients.gmail_client import execute_gmail_request, get_gmail_credentials

SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]
ATTACHMENT_ALLOWED_DIRS_ENV = "GMAIL_ATTACHMENT_ALLOWED_DIRS"
ATTACHMENT_MAX_BYTES_ENV = "GMAIL_ATTACHMENT_MAX_BYTES"
DEFAULT_ATTACHMENT_MAX_BYTES = 10 * 1024 * 1024


def _format_send_http_error(error: HttpError) -> str:
    status = getattr(getattr(error, "resp", None), "status", "unknown")
    details = str(error)
    if status == 403 and "insufficient authentication scopes" in details.lower():
        return (
            "Gmail attachment send failed due to missing OAuth scopes. "
            "Re-authenticate with gmail.compose by deleting token.json (or using "
            "a different GMAIL_TOKEN_FILE) and retry."
        )
    return f"Gmail attachment send failed (HTTP {status}): {details}"


def _format_draft_http_error(error: HttpError) -> str:
    status = getattr(getattr(error, "resp", None), "status", "unknown")
    return f"Gmail attachment draft failed (HTTP {status}): {error}"


def _load_compose_credentials():
    return get_gmail_credentials(SCOPES)


def _gmail_service():
    return build("gmail", "v1", credentials=_load_compose_credentials())


def _attachment_max_bytes() -> int:
    raw = (os.getenv(ATTACHMENT_MAX_BYTES_ENV) or "").strip()
    if not raw:
        return DEFAULT_ATTACHMENT_MAX_BYTES

    try:
        max_bytes = int(raw)
    except ValueError as exc:
        raise ValueError(
            f"{ATTACHMENT_MAX_BYTES_ENV} must be an integer byte count."
        ) from exc

    if max_bytes <= 0:
        raise ValueError(f"{ATTACHMENT_MAX_BYTES_ENV} must be greater than zero.")
    return max_bytes


def _allowed_attachment_roots() -> list[Path]:
    raw = (os.getenv(ATTACHMENT_ALLOWED_DIRS_ENV) or "").strip()
    if not raw:
        return [Path.cwd().resolve()]

    roots: list[Path] = []
    for segment in raw.split(","):
        candidate = segment.strip()
        if not candidate:
            continue
        roots.append(Path(candidate).expanduser().resolve())

    if not roots:
        return [Path.cwd().resolve()]
    return roots


def _is_within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _require_attachment_confirmation(*, confirm: bool) -> None:
    if not confirm:
        raise ValueError(
            "Attachment operations require explicit confirmation. Re-run with confirm=True."
        )


def _validate_attachment_paths(attachment_paths: Sequence[str]) -> list[Path]:
    if not attachment_paths:
        raise ValueError("attachment_paths must include at least one file path.")

    max_bytes = _attachment_max_bytes()
    allowed_roots = _allowed_attachment_roots()
    normalized_paths: list[Path] = []

    for raw_path in attachment_paths:
        file_path = Path(raw_path).expanduser().resolve()
        if not file_path.exists():
            raise FileNotFoundError(f"Attachment file does not exist: {file_path}")
        if not file_path.is_file():
            raise ValueError(f"Attachment path is not a file: {file_path}")

        if not any(_is_within_root(file_path, root) for root in allowed_roots):
            allowed_preview = ", ".join(str(root) for root in allowed_roots)
            raise PermissionError(
                f"Attachment path '{file_path}' is outside allowed roots: {allowed_preview}"
            )

        file_size = file_path.stat().st_size
        if file_size > max_bytes:
            raise ValueError(
                f"Attachment '{file_path.name}' is {file_size} bytes; "
                f"max allowed is {max_bytes} bytes."
            )

        normalized_paths.append(file_path)

    return normalized_paths


def _build_message(
    *,
    email_to: str,
    email_from: str,
    subject: str,
    body: str,
    attachment_paths: Sequence[Path],
) -> EmailMessage:
    message = EmailMessage()
    message["To"] = email_to
    message["From"] = email_from
    message["Subject"] = subject
    message.set_content(body)

    for file_path in attachment_paths:
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type:
            maintype, subtype = mime_type.split("/", 1)
        else:
            maintype, subtype = "application", "octet-stream"

        with file_path.open("rb") as attachment_file:
            message.add_attachment(
                attachment_file.read(),
                maintype=maintype,
                subtype=subtype,
                filename=file_path.name,
            )

    return message


def _encode_message(message: EmailMessage) -> str:
    return base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")


def gmail_create_draft_with_attachments(
    email_to: str,
    email_from: str,
    subject: str,
    body: str,
    attachment_paths: Sequence[str],
    confirm: bool = False,
) -> dict:
    """Create a Gmail draft with one or more file attachments."""
    _require_attachment_confirmation(confirm=confirm)
    paths = _validate_attachment_paths(attachment_paths)

    try:
        service = _gmail_service()
        message = _build_message(
            email_to=email_to,
            email_from=email_from,
            subject=subject,
            body=body,
            attachment_paths=paths,
        )
        draft = execute_gmail_request(
            service.users()
            .drafts()
            .create(userId="me", body={"message": {"raw": _encode_message(message)}})
        )
        return draft
    except HttpError as error:
        raise RuntimeError(_format_draft_http_error(error)) from error


def gmail_send_email_with_attachments(
    email_to: str,
    email_from: str,
    subject: str,
    body: str,
    attachment_paths: Sequence[str],
    confirm: bool = False,
) -> dict:
    """Send a Gmail message with one or more file attachments."""
    _require_attachment_confirmation(confirm=confirm)
    paths = _validate_attachment_paths(attachment_paths)

    try:
        service = _gmail_service()
        message = _build_message(
            email_to=email_to,
            email_from=email_from,
            subject=subject,
            body=body,
            attachment_paths=paths,
        )
        sent_message = execute_gmail_request(
            service.users()
            .messages()
            .send(userId="me", body={"raw": _encode_message(message)})
        )
        return sent_message
    except HttpError as error:
        raise RuntimeError(_format_send_http_error(error)) from error
