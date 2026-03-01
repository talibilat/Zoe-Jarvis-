from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

READONLY_SCOPES: tuple[str, ...] = ("https://www.googleapis.com/auth/gmail.readonly",)
RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})
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


def _normalize_scopes(scopes: Sequence[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for scope in scopes:
        candidate = (scope or "").strip()
        if candidate and candidate not in normalized:
            normalized.append(candidate)
    if not normalized:
        raise ValueError("At least one Gmail OAuth scope is required.")
    return tuple(normalized)


def _read_declared_scopes(token_path: Path) -> set[str]:
    try:
        payload = json.loads(token_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return set()

    declared_scopes = payload.get("scopes") or payload.get("scope")
    if isinstance(declared_scopes, str):
        return {scope for scope in declared_scopes.split() if scope}
    if isinstance(declared_scopes, list):
        return {str(scope).strip() for scope in declared_scopes if str(scope).strip()}
    return set()


def _token_has_required_scopes(
    token_path: Path, required_scopes: Sequence[str]
) -> bool:
    declared_scopes = _read_declared_scopes(token_path)
    if not declared_scopes:
        # Legacy token files may omit explicit scopes; attempt loading before forcing OAuth.
        return True
    return set(required_scopes).issubset(declared_scopes)


def _backup_existing_token() -> None:
    if TOKEN_FILE.exists() and TOKEN_BACKUP_FILE != TOKEN_FILE:
        TOKEN_BACKUP_FILE.write_text(TOKEN_FILE.read_text(), encoding="utf-8")


def _persist_token(creds: Credentials) -> None:
    _backup_existing_token()
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")


def _run_oauth_flow(
    required_scopes: Sequence[str], *, port: int = 0, open_browser: bool = True
) -> Credentials:
    flow = InstalledAppFlow.from_client_secrets_file(
        str(CREDS_FILE), list(required_scopes)
    )
    try:
        return flow.run_local_server(port=port, open_browser=open_browser)
    except TypeError:
        # Older or test doubles may not accept open_browser.
        return flow.run_local_server(port=port)


def get_gmail_credentials(
    required_scopes: Sequence[str],
    *,
    oauth_port: int = 0,
    open_browser: bool = True,
) -> Credentials:
    """Load cached Gmail credentials for the required scopes or trigger OAuth."""

    normalized_scopes = _normalize_scopes(required_scopes)
    creds: Optional[Credentials] = None
    if TOKEN_FILE.exists() and _token_has_required_scopes(
        TOKEN_FILE, normalized_scopes
    ):
        try:
            creds = Credentials.from_authorized_user_file(
                str(TOKEN_FILE), list(normalized_scopes)
            )
        except Exception:
            creds = None

    updated_token = False
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                updated_token = True
            except RefreshError:
                creds = None

        if not creds or not creds.valid:
            creds = _run_oauth_flow(
                normalized_scopes,
                port=oauth_port,
                open_browser=open_browser,
            )
            updated_token = True

        if updated_token:
            _persist_token(creds)

    return creds


def get_gmail_service(
    required_scopes: Sequence[str],
    *,
    oauth_port: int = 0,
    open_browser: bool = True,
):
    """Build a Gmail API service with credentials for the required scopes."""

    creds = get_gmail_credentials(
        required_scopes,
        oauth_port=oauth_port,
        open_browser=open_browser,
    )
    return build("gmail", "v1", credentials=creds)


def execute_gmail_request(
    request: Any,
    *,
    retries: int = 3,
    retry_status_codes: Sequence[int] = tuple(RETRYABLE_STATUS_CODES),
    backoff_base_seconds: float = 0.5,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Any:
    """Execute a Gmail request with bounded retry for transient HTTP statuses."""

    max_attempts = max(1, retries)
    retryable_statuses = set(retry_status_codes)

    for attempt in range(max_attempts):
        try:
            return request.execute()
        except HttpError as error:
            if attempt >= max_attempts - 1:
                raise
            status = getattr(getattr(error, "resp", None), "status", None)
            if status not in retryable_statuses:
                raise
            delay_seconds = max(0.0, backoff_base_seconds) * (2**attempt)
            sleep_fn(delay_seconds)

    # Defensive fallback; loop always returns or raises.
    raise RuntimeError("Gmail request execution failed unexpectedly.")


def gmail_client() -> Credentials:
    """Backward-compatible read-only Gmail credential loader."""

    return get_gmail_credentials(
        READONLY_SCOPES,
        oauth_port=8080,
        open_browser=True,
    )
