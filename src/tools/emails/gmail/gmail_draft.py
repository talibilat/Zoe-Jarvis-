from __future__ import annotations

import base64
import os
from email.message import EmailMessage
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.core.clients import gmail_client as gmail_client_module
from src.core.clients.gmail_client import execute_gmail_request

SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]
TOKEN_FILE = (os.getenv("GMAIL_TOKEN_FILE") or "token.json").strip() or "token.json"
TOKEN_BACKUP_FILE = (
    os.getenv("GMAIL_TOKEN_BACKUP_FILE") or "token.json.bak"
).strip() or "token.json.bak"
CREDS_FILE = (
    os.getenv("GMAIL_CREDENTIALS_FILE") or "credentials.json"
).strip() or "credentials.json"


def _sync_shared_client_settings() -> None:
    gmail_client_module.TOKEN_FILE = Path(TOKEN_FILE)
    gmail_client_module.TOKEN_BACKUP_FILE = Path(TOKEN_BACKUP_FILE)
    gmail_client_module.CREDS_FILE = Path(CREDS_FILE)
    gmail_client_module.Credentials = Credentials
    gmail_client_module.InstalledAppFlow = InstalledAppFlow


def _load_compose_credentials():
    _sync_shared_client_settings()
    return gmail_client_module.get_gmail_credentials(SCOPES, oauth_port=0)


def _gmail_service():
    return build("gmail", "v1", credentials=_load_compose_credentials())


def gmail_create_draft(
    email_to: str,
    email_from: str,
    subject: str,
    body: str,
) -> dict:
    """Create and insert a draft email."""

    message = EmailMessage()
    message.set_content(body)
    message["To"] = email_to
    message["From"] = email_from
    message["Subject"] = subject

    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    create_message = {"message": {"raw": encoded_message}}

    try:
        service = _gmail_service()
        draft = execute_gmail_request(
            service.users().drafts().create(userId="me", body=create_message)
        )
        return draft
    except HttpError as error:
        raise RuntimeError(f"Gmail API error while creating draft: {error}") from error
