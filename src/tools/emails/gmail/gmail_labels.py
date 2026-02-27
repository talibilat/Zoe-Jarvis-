from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/gmail.modify",
]
TOKEN_FILE = (os.getenv("GMAIL_TOKEN_FILE") or "token.json").strip() or "token.json"
TOKEN_BACKUP_FILE = (
    os.getenv("GMAIL_TOKEN_BACKUP_FILE") or "token.json.bak"
).strip() or "token.json.bak"
CREDS_FILE = (
    os.getenv("GMAIL_CREDENTIALS_FILE") or "credentials.json"
).strip() or "credentials.json"


def _load_label_credentials() -> Credentials:
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
    return build("gmail", "v1", credentials=_load_label_credentials())


def _labels_list(service) -> list[dict]:
    return service.users().labels().list(userId="me").execute().get("labels", [])


def _resolve_label_ids(service, labels: Optional[Sequence[str]]) -> list[str]:
    if not labels:
        return []

    available_labels = _labels_list(service)

    id_set = {
        str(label.get("id", "")): str(label.get("id", ""))
        for label in available_labels
        if label.get("id")
    }
    name_to_id = {
        (label.get("name") or "").strip().lower(): str(label.get("id", ""))
        for label in available_labels
        if label.get("id") and label.get("name")
    }

    resolved: list[str] = []
    for raw_label in labels:
        candidate = (raw_label or "").strip()
        if not candidate:
            continue

        if candidate in id_set:
            label_id = id_set[candidate]
        else:
            label_id = name_to_id.get(candidate.lower(), "")

        if not label_id:
            raise ValueError(f"Unknown Gmail label: {candidate}")
        if label_id not in resolved:
            resolved.append(label_id)

    return resolved


def gmail_list_labels(label_type: Optional[str] = None) -> List[Dict[str, str]]:
    """Return Gmail labels. Optional label_type filter: SYSTEM or USER."""
    normalized_type = (label_type or "").strip().upper()
    if normalized_type and normalized_type not in {"SYSTEM", "USER"}:
        raise ValueError("label_type must be one of: SYSTEM, USER, or omitted.")

    service = _gmail_service()
    labels = _labels_list(service)

    filtered: List[Dict[str, str]] = []
    for label in labels:
        label_type_value = str(label.get("type") or "")
        if normalized_type and label_type_value != normalized_type:
            continue
        filtered.append(
            {
                "id": str(label.get("id") or ""),
                "name": str(label.get("name") or ""),
                "type": label_type_value,
            }
        )

    return filtered


def gmail_create_label(
    name: str,
    label_list_visibility: str = "labelShow",
    message_list_visibility: str = "show",
) -> dict | None:
    """Create a Gmail label and return the label payload."""
    normalized_name = (name or "").strip()
    if not normalized_name:
        raise ValueError("Label name cannot be empty.")

    service = _gmail_service()
    body = {
        "name": normalized_name,
        "labelListVisibility": label_list_visibility,
        "messageListVisibility": message_list_visibility,
    }

    try:
        return service.users().labels().create(userId="me", body=body).execute()
    except HttpError as error:
        raise RuntimeError(f"Gmail API error while creating label: {error}") from error


def gmail_delete_label(label: str) -> bool:
    """Delete a Gmail label by ID or exact name. Returns True on success."""
    service = _gmail_service()
    resolved_ids = _resolve_label_ids(service, [label])
    if not resolved_ids:
        raise ValueError("label must not be empty.")

    try:
        service.users().labels().delete(userId="me", id=resolved_ids[0]).execute()
        return True
    except HttpError as error:
        raise RuntimeError(f"Gmail API error while deleting label: {error}") from error


def gmail_modify_message_labels(
    message_id: str,
    add_labels: Optional[Sequence[str]] = None,
    remove_labels: Optional[Sequence[str]] = None,
) -> dict | None:
    """Add/remove labels on a message. Labels may be IDs or exact names."""
    normalized_message_id = (message_id or "").strip()
    if not normalized_message_id:
        raise ValueError("message_id must not be empty.")

    service = _gmail_service()
    add_label_ids = _resolve_label_ids(service, add_labels)
    remove_label_ids = _resolve_label_ids(service, remove_labels)

    if not add_label_ids and not remove_label_ids:
        raise ValueError("Provide at least one label to add or remove.")

    body = {
        "addLabelIds": add_label_ids,
        "removeLabelIds": remove_label_ids,
    }

    try:
        return (
            service.users()
            .messages()
            .modify(userId="me", id=normalized_message_id, body=body)
            .execute()
        )
    except HttpError as error:
        raise RuntimeError(
            f"Gmail API error while modifying message labels: {error}"
        ) from error


def gmail_modify_thread_labels(
    thread_id: str,
    add_labels: Optional[Sequence[str]] = None,
    remove_labels: Optional[Sequence[str]] = None,
) -> dict | None:
    """Add/remove labels on all existing messages in a thread."""
    normalized_thread_id = (thread_id or "").strip()
    if not normalized_thread_id:
        raise ValueError("thread_id must not be empty.")

    service = _gmail_service()
    add_label_ids = _resolve_label_ids(service, add_labels)
    remove_label_ids = _resolve_label_ids(service, remove_labels)

    if not add_label_ids and not remove_label_ids:
        raise ValueError("Provide at least one label to add or remove.")

    body = {
        "addLabelIds": add_label_ids,
        "removeLabelIds": remove_label_ids,
    }

    try:
        return (
            service.users()
            .threads()
            .modify(userId="me", id=normalized_thread_id, body=body)
            .execute()
        )
    except HttpError as error:
        raise RuntimeError(
            f"Gmail API error while modifying thread labels: {error}"
        ) from error
