from __future__ import annotations

import base64
import mimetypes
import os
from email.message import EmailMessage
from pathlib import Path
from typing import Sequence

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]
TOKEN_FILE = (os.getenv("GMAIL_TOKEN_FILE") or "token.json").strip() or "token.json"
TOKEN_BACKUP_FILE = (
    os.getenv("GMAIL_TOKEN_BACKUP_FILE") or "token.json.bak"
).strip() or "token.json.bak"
CREDS_FILE = (
    os.getenv("GMAIL_CREDENTIALS_FILE") or "credentials.json"
).strip() or "credentials.json"


def _load_compose_credentials() -> Credentials:
    creds = None

    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception:
            creds = None
        if creds and not creds.has_scopes(SCOPES):
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                creds = None

        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        if os.path.exists(TOKEN_FILE) and TOKEN_BACKUP_FILE != TOKEN_FILE:
            with open(TOKEN_FILE, "r", encoding="utf-8") as current_token:
                with open(TOKEN_BACKUP_FILE, "w", encoding="utf-8") as backup_token:
                    backup_token.write(current_token.read())

        with open(TOKEN_FILE, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    return creds


def _validate_attachment_paths(attachment_paths: Sequence[str]) -> list[Path]:
    if not attachment_paths:
        raise ValueError("attachment_paths must include at least one file path.")

    normalized_paths: list[Path] = []
    for raw_path in attachment_paths:
        file_path = Path(raw_path).expanduser()
        if not file_path.exists():
            raise FileNotFoundError(f"Attachment file does not exist: {file_path}")
        if not file_path.is_file():
            raise ValueError(f"Attachment path is not a file: {file_path}")
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
) -> dict | None:
    """Create a Gmail draft with one or more file attachments."""
    paths = _validate_attachment_paths(attachment_paths)
    creds = _load_compose_credentials()

    try:
        service = build("gmail", "v1", credentials=creds)
        message = _build_message(
            email_to=email_to,
            email_from=email_from,
            subject=subject,
            body=body,
            attachment_paths=paths,
        )
        draft = (
            service.users()
            .drafts()
            .create(userId="me", body={"message": {"raw": _encode_message(message)}})
            .execute()
        )
        return draft

    except HttpError as error:
        print(f"An error occurred: {error}")
        return None


def gmail_send_email_with_attachments(
    email_to: str,
    email_from: str,
    subject: str,
    body: str,
    attachment_paths: Sequence[str],
) -> dict | None:
    """Send a Gmail message with one or more file attachments."""
    paths = _validate_attachment_paths(attachment_paths)
    creds = _load_compose_credentials()

    try:
        service = build("gmail", "v1", credentials=creds)
        message = _build_message(
            email_to=email_to,
            email_from=email_from,
            subject=subject,
            body=body,
            attachment_paths=paths,
        )
        sent_message = (
            service.users()
            .messages()
            .send(userId="me", body={"raw": _encode_message(message)})
            .execute()
        )
        return sent_message

    except HttpError as error:
        print(f"An error occurred: {error}")
        return None
