from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CREDS_FILE = Path(
    (os.getenv("GMAIL_CREDENTIALS_FILE") or "credentials.json").strip()
    or "credentials.json"
)
TOKEN_FILE = Path(
    (os.getenv("GMAIL_TOKEN_FILE") or "token.json").strip() or "token.json"
)
TOKEN_BACKUP_FILE = Path(
    (os.getenv("GMAIL_TOKEN_BACKUP_FILE") or "token.json.bak").strip()
    or "token.json.bak"
)


def _backup_existing_token() -> None:
    if TOKEN_FILE.exists() and TOKEN_BACKUP_FILE != TOKEN_FILE:
        TOKEN_BACKUP_FILE.write_text(TOKEN_FILE.read_text(), encoding="utf-8")


def _run_oauth_flow() -> Credentials:
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
    return flow.run_local_server(port=8080, open_browser=True)


def gmail_client() -> Credentials:
    """
    Load cached Gmail OAuth credentials or trigger the browser flow once.
    """
    creds: Optional[Credentials] = None
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        except Exception:
            # Treat malformed/legacy token files the same as missing credentials.
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                creds = None

        if not creds or not creds.valid:
            creds = _run_oauth_flow()

        _backup_existing_token()
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    return creds
