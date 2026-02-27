from __future__ import annotations

import os
from typing import Optional

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/gmail.settings.basic"]
TOKEN_FILE = (os.getenv("GMAIL_TOKEN_FILE") or "token.json").strip() or "token.json"
TOKEN_BACKUP_FILE = (
    os.getenv("GMAIL_TOKEN_BACKUP_FILE") or "token.json.bak"
).strip() or "token.json.bak"
CREDS_FILE = (
    os.getenv("GMAIL_CREDENTIALS_FILE") or "credentials.json"
).strip() or "credentials.json"


def _load_settings_credentials() -> Credentials:
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


def _gmail_service():
    return build("gmail", "v1", credentials=_load_settings_credentials())


def _select_alias(aliases: list[dict], send_as_email: Optional[str]) -> dict:
    if not aliases:
        raise RuntimeError("No send-as aliases found for authenticated Gmail account.")

    normalized_target = (send_as_email or "").strip().lower()
    if normalized_target:
        for alias in aliases:
            if (alias.get("sendAsEmail") or "").strip().lower() == normalized_target:
                return alias
        raise ValueError(f"Unknown sendAsEmail: {send_as_email}")

    for alias in aliases:
        if alias.get("isPrimary"):
            return alias

    return aliases[0]


def update_signature(
    signature: str = "Automated Signature",
    send_as_email: Optional[str] = None,
    display_name: Optional[str] = None,
) -> str | None:
    """Update Gmail signature for a send-as identity and return updated signature."""
    normalized_signature = (signature or "").strip()
    if not normalized_signature:
        raise ValueError("signature must not be empty.")

    service = _gmail_service()
    aliases = (
        service.users()
        .settings()
        .sendAs()
        .list(userId="me")
        .execute()
        .get("sendAs", [])
    )
    selected_alias = _select_alias(aliases, send_as_email)

    resolved_send_as_email = (selected_alias.get("sendAsEmail") or "").strip()
    if not resolved_send_as_email:
        raise RuntimeError("Selected alias does not include sendAsEmail.")

    resolved_display_name = (display_name or "").strip()
    if not resolved_display_name:
        resolved_display_name = (
            selected_alias.get("displayName") or ""
        ).strip() or resolved_send_as_email

    body = {
        "displayName": resolved_display_name,
        "signature": normalized_signature,
    }

    try:
        result = (
            service.users()
            .settings()
            .sendAs()
            .patch(
                userId="me",
                sendAsEmail=resolved_send_as_email,
                body=body,
            )
            .execute()
        )
        return result.get("signature")

    except HttpError as error:
        print(f"An error occurred: {error}")
        return None
