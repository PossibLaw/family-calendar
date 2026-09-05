from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .ical import CalendarEvent, to_google_event


class CalendarGateway(Protocol):
    def find_by_ical_uid(self, uid: str) -> list[dict[str, object]]: ...

    def find_adoptable(self, event: CalendarEvent) -> list[dict[str, object]]: ...

    def import_event(self, payload: dict[str, object]) -> None: ...

    def patch_event(self, event_id: str, payload: dict[str, object]) -> None: ...


def _window(moment: str, days: int) -> str:
    """Bracket a start time by a day so a timed or all-day event is covered."""
    text = moment if "T" in moment else f"{moment}T00:00:00Z"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return (parsed.astimezone(UTC) + timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _starts_at(candidate: object, start: dict[str, object]) -> bool:
    if not isinstance(candidate, dict):
        return False
    other = candidate.get("start")
    if not isinstance(other, dict):
        return False
    wanted = start.get("dateTime") or start.get("date")
    found = other.get("dateTime") or other.get("date")
    if not isinstance(wanted, str) or not isinstance(found, str):
        return False
    if "T" not in wanted or "T" not in found:
        return wanted == found
    return datetime.fromisoformat(wanted) == datetime.fromisoformat(found)


def _describe_match(event: dict[str, object]) -> str:
    """Name one conflicting event well enough to find it in Google Calendar."""
    identifier = event.get("id")
    summary = event.get("summary")
    start = event.get("start")
    when = ""
    if isinstance(start, dict):
        when = str(start.get("dateTime") or start.get("date") or "")
    properties = event.get("extendedProperties")
    private = properties.get("private", {}) if isinstance(properties, dict) else {}
    managed = (
        isinstance(private, dict) and private.get("family_schedule_managed") == "true"
    )
    parts = [f"id={identifier!r}", f"summary={summary!r}"]
    if when:
        parts.append(f"start={when}")
    parts.append(f"managed_by_this_repo={'yes' if managed else 'no'}")
    return " ".join(parts)


def _fingerprint(payload: dict[str, object]) -> str:
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _managed_payload(event: CalendarEvent, reminder_minutes: int) -> dict[str, object]:
    payload = to_google_event(event, reminder_minutes=reminder_minutes)
    fingerprint = _fingerprint(payload)
    # iCalUID cannot be changed after an event exists, so an adopted event can
    # never be found by UID. Record the source UID as a private property too, and
    # match on either, so adoption survives every later run.
    payload["extendedProperties"] = {
        "private": {
            "family_schedule_hash": fingerprint,
            "family_schedule_managed": "true",
            "family_schedule_uid": event.uid,
        }
    }
    return payload


def _private_properties(event: dict[str, object]) -> dict[str, object]:
    properties = event.get("extendedProperties")
    if not isinstance(properties, dict):
        return {}
    private = properties.get("private")
    return private if isinstance(private, dict) else {}


def is_managed(event: dict[str, object]) -> bool:
    return _private_properties(event).get("family_schedule_managed") == "true"


@dataclass(frozen=True)
class SyncAction:
    """One decided change, resolved before anything is written."""

    kind: str  # "create", "adopt", "update" or "skip"
    event: CalendarEvent
    payload: dict[str, object]
    event_id: str | None = None
    existing_summary: str | None = None


def _resolve(
    event: CalendarEvent, payload: dict[str, object], gateway: CalendarGateway
) -> SyncAction:
    matches = gateway.find_by_ical_uid(event.uid)
    if len(matches) > 1:
        listed = "; ".join(_describe_match(match) for match in matches)
        raise RuntimeError(
            f"Found {len(matches)} Google Calendar events with iCalUID "
            f"{event.uid!r}; delete the extra one before syncing. "
            f"Conflicting events: {listed}"
        )

    if not matches:
        # Google's own Import screen does not preserve iCalUID, so a hand-imported
        # event is invisible to the lookup above and would be recreated as a
        # duplicate. Adopt an identical unmanaged event instead of adding a second.
        adoptable = gateway.find_adoptable(event)
        if len(adoptable) == 1:
            existing = adoptable[0]
            event_id = existing.get("id")
            if isinstance(event_id, str) and event_id:
                return SyncAction(
                    "adopt",
                    event,
                    payload,
                    event_id,
                    str(existing.get("summary", "")),
                )
        return SyncAction("create", event, payload)

    existing = matches[0]
    desired_hash = payload["extendedProperties"]["private"]["family_schedule_hash"]  # type: ignore[index]
    if _private_properties(existing).get("family_schedule_hash") == desired_hash:
        return SyncAction("skip", event, payload)

    event_id = existing.get("id")
    if not isinstance(event_id, str) or not event_id:
        raise RuntimeError(
            f"Existing event {event.uid!r} has no Google Calendar event ID"
        )
    return SyncAction("update", event, payload, event_id)


def plan_sync(
    events: list[CalendarEvent],
    gateway: CalendarGateway,
    *,
    reminder_minutes: int,
) -> list[SyncAction]:
    """Decide every change with reads only, before a single write happens."""
    return [
        _resolve(event, _managed_payload(event, reminder_minutes), gateway)
        for event in events
    ]


def summarize_plan(actions: list[SyncAction]) -> dict[str, int]:
    counts = {"created": 0, "adopted": 0, "updated": 0, "skipped": 0}
    names = {
        "create": "created",
        "adopt": "adopted",
        "update": "updated",
        "skip": "skipped",
    }
    for action in actions:
        counts[names[action.kind]] += 1
    return counts


def sync_events(
    events: list[CalendarEvent],
    gateway: CalendarGateway,
    *,
    reminder_minutes: int,
    max_new_events: int | None = None,
) -> dict[str, int]:
    actions = plan_sync(events, gateway, reminder_minutes=reminder_minutes)
    creations = [action for action in actions if action.kind == "create"]
    if max_new_events is not None and len(creations) > max_new_events:
        sample = ", ".join(f"{action.event.summary!r}" for action in creations[:5])
        raise RuntimeError(
            f"Refusing to add {len(creations)} new events in one run; the limit is "
            f"{max_new_events}. This usually means the calendar already holds these "
            "events under identities this repository does not recognise, and syncing "
            "would duplicate them. Review the calendar, then re-run with a higher "
            f"--max-new to proceed. First few: {sample}"
        )

    for action in actions:
        if action.kind == "create":
            gateway.import_event(action.payload)
        elif action.kind in {"adopt", "update"}:
            patch = dict(action.payload)
            patch.pop("iCalUID", None)
            gateway.patch_event(str(action.event_id), patch)
    return summarize_plan(actions)


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

    def _list(self, parameters: dict[str, object]) -> list[dict[str, object]]:
        query = urlencode({"showDeleted": "false", "maxResults": 10, **parameters})
        result = self._request_json("GET", f"{self._events_url}?{query}")
        items = result.get("items", [])
        if not isinstance(items, list):
            raise RuntimeError(  # noqa: TRY004 - malformed external API response
                "Google Calendar API returned an invalid events list"
            )
        return [item for item in items if isinstance(item, dict)]

    def find_adoptable(self, event: CalendarEvent) -> list[dict[str, object]]:
        """Find one unmanaged event this source clearly already describes.

        Only an exact match on summary and start counts, and only when nothing
        else in the window looks the same, so adoption can never silently attach
        this source to the wrong event.
        """
        google_event = to_google_event(event, reminder_minutes=0)
        start = google_event.get("start")
        if not isinstance(start, dict):
            return []
        moment = start.get("dateTime") or start.get("date")
        if not isinstance(moment, str) or not moment:
            return []
        candidates = self._list(
            {
                "q": event.summary,
                "timeMin": _window(moment, -1),
                "timeMax": _window(moment, 1),
                "singleEvents": "true",
            }
        )
        matches = [
            candidate
            for candidate in candidates
            if candidate.get("summary") == event.summary
            and _starts_at(candidate, start)
            and not is_managed(candidate)
            and not candidate.get("recurringEventId")
        ]
        # Ambiguity is not adoptable: two identical unmanaged events mean a real
        # duplicate that a person has to resolve.
        return matches if len(matches) == 1 else []

    def find_by_ical_uid(self, uid: str) -> list[dict[str, object]]:
        items = self._list({"iCalUID": uid})
        if not items:
            # An adopted event keeps the iCalUID it was created with, so it is
            # only findable by the identifier this repository wrote onto it.
            items = self._list(
                {"privateExtendedProperty": f"family_schedule_uid={uid}"}
            )
        # Editing a single occurrence of a recurring series makes Google store that
        # occurrence as its own event carrying the series iCalUID and a
        # recurringEventId. It is an instance of the event already managed here, not
        # a second event, so counting it as a duplicate would let one manual edit
        # block every future sync.
        return [item for item in items if not item.get("recurringEventId")]

    def import_event(self, payload: dict[str, object]) -> None:
        self._request_json("POST", f"{self._events_url}/import", payload)

    def patch_event(self, event_id: str, payload: dict[str, object]) -> None:
        safe_event_id = quote(event_id, safe="")
        self._request_json("PATCH", f"{self._events_url}/{safe_event_id}", payload)
