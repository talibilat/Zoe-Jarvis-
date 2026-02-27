from __future__ import annotations

import os
from typing import Any

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


def _load_filter_credentials() -> Credentials:
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
    return build("gmail", "v1", credentials=_load_filter_credentials())


def create_filter(criteria: dict[str, Any], action: dict[str, Any]) -> dict | None:
    """Create a Gmail filter and return its payload."""
    if not criteria:
        raise ValueError("criteria must not be empty.")
    if not action:
        raise ValueError("action must not be empty.")

    body = {
        "criteria": criteria,
        "action": action,
    }

    try:
        service = _gmail_service()
        return (
            service.users()
            .settings()
            .filters()
            .create(userId="me", body=body)
            .execute()
        )
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None


def list_filters() -> list[dict]:
    """List Gmail filters for the authenticated user."""
    try:
        service = _gmail_service()
        response = service.users().settings().filters().list(userId="me").execute()
        return response.get("filter", [])
    except HttpError as error:
        print(f"An error occurred: {error}")
        return []


def get_filter(filter_id: str) -> dict | None:
    """Get a Gmail filter by ID."""
    normalized_filter_id = (filter_id or "").strip()
    if not normalized_filter_id:
        raise ValueError("filter_id must not be empty.")

    try:
        service = _gmail_service()
        return (
            service.users()
            .settings()
            .filters()
            .get(userId="me", id=normalized_filter_id)
            .execute()
        )
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None


def delete_filter(filter_id: str) -> bool:
    """Delete a Gmail filter by ID and return True on success."""
    normalized_filter_id = (filter_id or "").strip()
    if not normalized_filter_id:
        raise ValueError("filter_id must not be empty.")

    try:
        service = _gmail_service()
        service.users().settings().filters().delete(
            userId="me", id=normalized_filter_id
        ).execute()
        return True
    except HttpError as error:
        print(f"An error occurred: {error}")
        return False
