from __future__ import annotations

import os

from googleapiclient.errors import HttpError

from src.core.clients.gmail_client import execute_gmail_request, get_gmail_service

SCOPES = [
    "https://www.googleapis.com/auth/gmail.settings.basic",
    "https://www.googleapis.com/auth/gmail.settings.sharing",
]
ALLOWED_DISPOSITIONS = {
    "leaveInInbox",
    "archive",
    "trash",
    "markRead",
}
FORWARDING_ALLOWLIST_ENV = "GMAIL_FORWARDING_ALLOWLIST"


def _gmail_service():
    return get_gmail_service(SCOPES)


def _parse_forwarding_allowlist() -> list[str]:
    raw = (os.getenv(FORWARDING_ALLOWLIST_ENV) or "").strip()
    if not raw:
        return []
    return [entry.strip().lower() for entry in raw.split(",") if entry.strip()]


def _is_allowlisted_address(email: str, allowlist: list[str]) -> bool:
    normalized_email = email.strip().lower()
    _, _, domain = normalized_email.partition("@")

    for entry in allowlist:
        if entry.startswith("@"):
            if normalized_email.endswith(entry):
                return True
            continue

        if "@" in entry:
            if normalized_email == entry:
                return True
            continue

        if domain == entry:
            return True

    return False


def _validate_forwarding_guardrails(forwarding_email: str, *, confirm: bool) -> None:
    if not confirm:
        raise ValueError(
            "Forwarding changes require explicit confirmation. Re-run with confirm=True."
        )

    allowlist = _parse_forwarding_allowlist()
    if not allowlist:
        raise PermissionError(
            "Forwarding is disabled until GMAIL_FORWARDING_ALLOWLIST is configured."
        )

    if not _is_allowlisted_address(forwarding_email, allowlist):
        raise PermissionError(
            f"Forwarding target '{forwarding_email}' is not in GMAIL_FORWARDING_ALLOWLIST."
        )


def enable_forwarding(
    forwarding_email: str,
    disposition: str = "trash",
    enabled: bool = True,
    confirm: bool = False,
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

    _validate_forwarding_guardrails(normalized_email, confirm=confirm)

    try:
        service = _gmail_service()

        forwarding_address = execute_gmail_request(
            service.users()
            .settings()
            .forwardingAddresses()
            .create(userId="me", body={"forwardingEmail": normalized_email})
        )

        verification_status = (
            forwarding_address.get("verificationStatus") or ""
        ).lower()
        if verification_status != "accepted":
            return {
                "forwarding_address": forwarding_address,
                "auto_forwarding": None,
            }

        auto_forwarding = execute_gmail_request(
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
        )

        return {
            "forwarding_address": forwarding_address,
            "auto_forwarding": auto_forwarding,
        }

    except HttpError as error:
        raise RuntimeError(
            f"Gmail API error while configuring forwarding: {error}"
        ) from error
