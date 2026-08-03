from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .ical import CalendarEvent, to_google_event


class CalendarGateway(Protocol):
    def find_by_ical_uid(self, uid: str) -> list[dict[str, object]]: ...

    def import_event(self, payload: dict[str, object]) -> None: ...

    def patch_event(self, event_id: str, payload: dict[str, object]) -> None: ...


def _fingerprint(payload: dict[str, object]) -> str:
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _managed_payload(event: CalendarEvent, reminder_minutes: int) -> dict[str, object]:
    payload = to_google_event(event, reminder_minutes=reminder_minutes)
    fingerprint = _fingerprint(payload)
    payload["extendedProperties"] = {
        "private": {
            "family_schedule_hash": fingerprint,
            "family_schedule_managed": "true",
        }
    }
    return payload


def sync_events(
    events: list[CalendarEvent],
    gateway: CalendarGateway,
    *,
    reminder_minutes: int,
) -> dict[str, int]:
    results = {"created": 0, "updated": 0, "skipped": 0}
    for event in events:
        payload = _managed_payload(event, reminder_minutes)
        matches = gateway.find_by_ical_uid(event.uid)
        if len(matches) > 1:
            raise RuntimeError(
                f"Found {len(matches)} Google Calendar events with iCalUID {event.uid!r}; "
                "resolve the duplicate before syncing"
            )
        if not matches:
            gateway.import_event(payload)
            results["created"] += 1
            continue

        existing = matches[0]
        private = (
            existing.get("extendedProperties", {})
            if isinstance(existing.get("extendedProperties"), dict)
            else {}
        )
        private_values = private.get("private", {}) if isinstance(private, dict) else {}
        desired_hash = payload["extendedProperties"]["private"]["family_schedule_hash"]  # type: ignore[index]
        if (
            isinstance(private_values, dict)
            and private_values.get("family_schedule_hash") == desired_hash
        ):
            results["skipped"] += 1
            continue

        event_id = existing.get("id")
        if not isinstance(event_id, str) or not event_id:
            raise RuntimeError(
                f"Existing event {event.uid!r} has no Google Calendar event ID"
            )
        patch = dict(payload)
        patch.pop("iCalUID", None)
        gateway.patch_event(event_id, patch)
        results["updated"] += 1
    return results


@dataclass(frozen=True)
class GoogleCredentials:
    client_id: str
    client_secret: str
    refresh_token: str

    @classmethod
    def from_environment(cls, env_file: Path = Path(".env")) -> GoogleCredentials:
        names = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN")
        file_values: dict[str, str] = {}
        if env_file.is_file():
            for raw_line in env_file.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, value = line.split("=", 1)
                if name in names:
                    file_values[name] = value
        values = {name: os.environ.get(name) or file_values.get(name) for name in names}
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise RuntimeError(
                "Missing Google OAuth environment variables: " + ", ".join(missing)
            )
        return cls(*(str(values[name]) for name in names))


def refresh_google_access_token(credentials: GoogleCredentials) -> str:
    body = urlencode(
        {
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "refresh_token": credentials.refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    request = Request(
        "https://oauth2.googleapis.com/token",
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(
            f"Google OAuth token refresh failed with HTTP {error.code}"
        ) from error
    token = result.get("access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("Google OAuth response did not contain an access token")
    return token


class GoogleCalendarGateway:
    def __init__(self, calendar_id: str, credentials: GoogleCredentials) -> None:
        self.calendar_id = calendar_id
        self.access_token = refresh_google_access_token(credentials)

    def _request_json(
        self,
        method: str,
        url: str,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
                "User-Agent": "family-schedule/0.1",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise RuntimeError(
                f"Google Calendar API request failed with HTTP {error.code}"
            ) from error

    @property
    def _events_url(self) -> str:
        calendar_id = quote(self.calendar_id, safe="")
        return f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"

    def find_by_ical_uid(self, uid: str) -> list[dict[str, object]]:
        query = urlencode({"iCalUID": uid, "showDeleted": "false", "maxResults": 10})
        result = self._request_json("GET", f"{self._events_url}?{query}")
        items = result.get("items", [])
        if not isinstance(items, list):
            raise RuntimeError(  # noqa: TRY004 - malformed external API response
                "Google Calendar API returned an invalid events list"
            )
        return [item for item in items if isinstance(item, dict)]

    def import_event(self, payload: dict[str, object]) -> None:
        self._request_json("POST", f"{self._events_url}/import", payload)

    def patch_event(self, event_id: str, payload: dict[str, object]) -> None:
        safe_event_id = quote(event_id, safe="")
        self._request_json("PATCH", f"{self._events_url}/{safe_event_id}", payload)
