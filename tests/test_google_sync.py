from __future__ import annotations

import unittest

from test_calendar_import import SAMPLE_ICS

from family_schedule.google_calendar import sync_events
from family_schedule.ical import parse_events


class FakeCalendarGateway:
    def __init__(self) -> None:
        self.events: dict[str, dict[str, object]] = {}
        self.created = 0
        self.updated = 0

    def find_by_ical_uid(self, uid: str) -> list[dict[str, object]]:
        event = self.events.get(uid)
        return [event] if event else []

    def import_event(self, payload: dict[str, object]) -> None:
        self.created += 1
        stored = dict(payload)
        stored["id"] = f"event-{self.created}"
        self.events[str(payload["iCalUID"])] = stored

    def patch_event(self, event_id: str, payload: dict[str, object]) -> None:
        self.updated += 1
        for uid, event in self.events.items():
            if event.get("id") == event_id:
                event.update(payload)
                self.events[uid] = event
                return
        raise AssertionError(f"Unknown event ID: {event_id}")


class GoogleCalendarSyncTests(unittest.TestCase):
    def test_second_sync_skips_existing_unchanged_event(self) -> None:
        gateway = FakeCalendarGateway()
        events = parse_events(SAMPLE_ICS)

        first = sync_events(events, gateway, reminder_minutes=30)
        second = sync_events(events, gateway, reminder_minutes=30)

        self.assertEqual(first, {"created": 1, "updated": 0, "skipped": 0})
        self.assertEqual(second, {"created": 0, "updated": 0, "skipped": 1})
        self.assertEqual(gateway.created, 1)
        self.assertEqual(gateway.updated, 0)
