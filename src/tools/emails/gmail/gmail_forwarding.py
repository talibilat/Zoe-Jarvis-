from __future__ import annotations

import os

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    "https://www.googleapis.com/auth/gmail.settings.basic",
    "https://www.googleapis.com/auth/gmail.settings.sharing",
]
TOKEN_FILE = (os.getenv("GMAIL_TOKEN_FILE") or "token.json").strip() or "token.json"
TOKEN_BACKUP_FILE = (
    os.getenv("GMAIL_TOKEN_BACKUP_FILE") or "token.json.bak"
).strip() or "token.json.bak"
CREDS_FILE = (
    os.getenv("GMAIL_CREDENTIALS_FILE") or "credentials.json"
).strip() or "credentials.json"
ALLOWED_DISPOSITIONS = {
    "leaveInInbox",
    "archive",
    "trash",
    "markRead",
}


def _load_forwarding_credentials() -> Credentials:
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
    return build("gmail", "v1", credentials=_load_forwarding_credentials())


def enable_forwarding(
    forwarding_email: str,
    disposition: str = "trash",
    enabled: bool = True,
) -> dict | None:
    """Create a forwarding address and enable auto-forwarding if verified."""
    normalized_email = (forwarding_email or "").strip()
    if not normalized_email:
        raise ValueError("forwarding_email must not be empty.")

    normalized_disposition = (disposition or "").strip()
    if normalized_disposition not in ALLOWED_DISPOSITIONS:
        raise ValueError(
            "disposition must be one of: leaveInInbox, archive, trash, markRead."
        )

    try:
        service = _gmail_service()

        forwarding_address = (
            service.users()
            .settings()
            .forwardingAddresses()
            .create(userId="me", body={"forwardingEmail": normalized_email})
            .execute()
        )

        verification_status = (
            forwarding_address.get("verificationStatus") or ""
        ).lower()
        if verification_status != "accepted":
            return {
                "forwarding_address": forwarding_address,
                "auto_forwarding": None,
            }

        auto_forwarding = (
            service.users()
            .settings()
            .updateAutoForwarding(
                userId="me",
                body={
                    "emailAddress": forwarding_address.get("forwardingEmail"),
                    "enabled": enabled,
                    "disposition": normalized_disposition,
                },
            )
            .execute()
        )

        return {
            "forwarding_address": forwarding_address,
            "auto_forwarding": auto_forwarding,
        }

    except HttpError as error:
        print(f"An error occurred: {error}")
        return None
