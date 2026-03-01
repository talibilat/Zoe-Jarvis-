from __future__ import annotations

from typing import Optional

from googleapiclient.errors import HttpError

from src.core.clients.gmail_client import execute_gmail_request, get_gmail_service

SCOPES = ["https://www.googleapis.com/auth/gmail.settings.basic"]


def _gmail_service():
    return get_gmail_service(SCOPES)


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
    aliases = execute_gmail_request(
        service.users().settings().sendAs().list(userId="me")
    ).get("sendAs", [])
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
        result = execute_gmail_request(
            service.users()
            .settings()
            .sendAs()
            .patch(
                userId="me",
                sendAsEmail=resolved_send_as_email,
                body=body,
            )
        )
        return result.get("signature")
    except HttpError as error:
        raise RuntimeError(
            f"Gmail API error while updating signature: {error}"
        ) from error
