from __future__ import annotations

import os
from pathlib import Path

CALENDAR_EVENTS_SCOPE = "https://www.googleapis.com/auth/calendar.events"
GMAIL_MODIFY_SCOPE = "https://www.googleapis.com/auth/gmail.modify"


def oauth_scopes(*, with_gmail: bool) -> list[str]:
    scopes = [CALENDAR_EVENTS_SCOPE]
    if with_gmail:
        scopes.append(GMAIL_MODIFY_SCOPE)
    return scopes


def _safe_env_value(value: str, name: str) -> str:
    if "\n" in value or "\r" in value:
        raise ValueError(f"OAuth value {name} contains an unexpected newline")
    return value


def write_env_file(
    path: Path,
    *,
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> None:
    values = {
        "GOOGLE_CLIENT_ID": _safe_env_value(client_id, "client_id"),
        "GOOGLE_CLIENT_SECRET": _safe_env_value(client_secret, "client_secret"),
        "GOOGLE_REFRESH_TOKEN": _safe_env_value(refresh_token, "refresh_token"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(f"{name}={value}\n" for name, value in values.items()),
        encoding="utf-8",
    )
    os.chmod(path, 0o600)


def authorize_google(
    credentials_path: Path, output_path: Path, *, with_gmail: bool = False
) -> Path:
    """Run Google's desktop OAuth flow and save only the values needed for sync."""
    if not credentials_path.is_file():
        raise RuntimeError(
            f"Google credentials file does not exist: {credentials_path}"
        )
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as error:
        raise RuntimeError("Google authorization support is not installed") from error

    flow = InstalledAppFlow.from_client_secrets_file(
        str(credentials_path),
        scopes=oauth_scopes(with_gmail=with_gmail),
    )
    credentials = flow.run_local_server(
        port=0,
        access_type="offline",
        prompt="consent",
        success_message="Family Calendar is connected. You may close this browser tab.",
    )
    if not credentials.refresh_token:
        raise RuntimeError(
            "Google did not provide a refresh token; remove the app from your Google "
            "Account permissions and authorize again"
        )
    if not credentials.client_id or credentials.client_secret is None:
        raise RuntimeError(
            "Google authorization did not return complete client credentials"
        )
    write_env_file(
        output_path,
        client_id=credentials.client_id,
        client_secret=credentials.client_secret,
        refresh_token=credentials.refresh_token,
    )
    return output_path
