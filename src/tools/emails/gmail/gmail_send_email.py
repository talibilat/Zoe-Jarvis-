from __future__ import annotations

import base64
import json
import os
from email.message import EmailMessage

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


def _read_declared_scopes(token_path: str) -> set[str]:
    try:
        with open(token_path, "r", encoding="utf-8") as token:
            payload = json.load(token)
    except (OSError, json.JSONDecodeError, TypeError):
        return set()

    declared_scopes = payload.get("scopes") or payload.get("scope")
    if isinstance(declared_scopes, str):
        return {scope for scope in declared_scopes.split() if scope}
    if isinstance(declared_scopes, list):
        return {str(scope).strip() for scope in declared_scopes if str(scope).strip()}

    return set()


def _token_has_required_scopes(token_path: str, required_scopes: list[str]) -> bool:
    declared_scopes = _read_declared_scopes(token_path)
    return bool(declared_scopes) and set(required_scopes).issubset(declared_scopes)


def _format_send_http_error(error: HttpError) -> str:
    status = getattr(getattr(error, "resp", None), "status", "unknown")
    details = str(error)
    if status == 403 and "insufficient authentication scopes" in details.lower():
        return (
            "Gmail send failed due to missing OAuth scopes. Re-authenticate with "
            "gmail.compose by deleting token.json (or using a different "
            "GMAIL_TOKEN_FILE) and retry."
        )
    return f"Gmail send failed (HTTP {status}): {details}"


def _load_compose_credentials() -> Credentials:
    creds = None

    if os.path.exists(TOKEN_FILE) and _token_has_required_scopes(TOKEN_FILE, SCOPES):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception:
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


def gmail_send_email(
    email_to: str,
    email_from: str,
    subject: str,
    body: str,
) -> dict:
    """Send a Gmail email and return the send response payload."""
    creds = _load_compose_credentials()

    try:
        service = build("gmail", "v1", credentials=creds)

        message = EmailMessage()
        message["To"] = email_to
        message["From"] = email_from
        message["Subject"] = subject
        message.set_content(body)

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        sent_message = (
            service.users()
            .messages()
            .send(userId="me", body={"raw": encoded_message})
            .execute()
        )

        return sent_message

    except HttpError as error:
        raise RuntimeError(_format_send_http_error(error)) from error
