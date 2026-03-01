from __future__ import annotations

from typing import Any

from googleapiclient.errors import HttpError

from src.core.clients.gmail_client import execute_gmail_request, get_gmail_service

SCOPES = ["https://www.googleapis.com/auth/gmail.settings.basic"]


def _gmail_service():
    return get_gmail_service(SCOPES)


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
        return execute_gmail_request(
            service.users().settings().filters().create(userId="me", body=body)
        )
    except HttpError as error:
        raise RuntimeError(f"Gmail API error while creating filter: {error}") from error


def list_filters() -> list[dict]:
    """List Gmail filters for the authenticated user."""
    try:
        service = _gmail_service()
        response = execute_gmail_request(
            service.users().settings().filters().list(userId="me")
        )
        return response.get("filter", [])
    except HttpError as error:
        raise RuntimeError(f"Gmail API error while listing filters: {error}") from error


def get_filter(filter_id: str) -> dict | None:
    """Get a Gmail filter by ID."""
    normalized_filter_id = (filter_id or "").strip()
    if not normalized_filter_id:
        raise ValueError("filter_id must not be empty.")

    try:
        service = _gmail_service()
        return execute_gmail_request(
            service.users()
            .settings()
            .filters()
            .get(userId="me", id=normalized_filter_id)
        )
    except HttpError as error:
        raise RuntimeError(f"Gmail API error while getting filter: {error}") from error


def delete_filter(filter_id: str) -> bool:
    """Delete a Gmail filter by ID and return True on success."""
    normalized_filter_id = (filter_id or "").strip()
    if not normalized_filter_id:
        raise ValueError("filter_id must not be empty.")

    try:
        service = _gmail_service()
        execute_gmail_request(
            service.users()
            .settings()
            .filters()
            .delete(userId="me", id=normalized_filter_id)
        )
        return True
    except HttpError as error:
        raise RuntimeError(f"Gmail API error while deleting filter: {error}") from error
