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

    def find_adoptable(self, event: object) -> list[dict[str, object]]:
        return []

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

        self.assertEqual(
            first, {"created": 1, "adopted": 0, "updated": 0, "skipped": 0}
        )
        self.assertEqual(
            second, {"created": 0, "adopted": 0, "updated": 0, "skipped": 1}
        )
        self.assertEqual(gateway.created, 1)
        self.assertEqual(gateway.updated, 0)

    def test_unchanged_source_does_not_overwrite_a_manual_calendar_edit(self) -> None:
        gateway = FakeCalendarGateway()
        events = parse_events(SAMPLE_ICS)
        sync_events(events, gateway, reminder_minutes=30)
        uid = events[0].uid
        gateway.events[uid]["summary"] = "Family corrected title"

        result = sync_events(events, gateway, reminder_minutes=30)

        self.assertEqual(
            result, {"created": 0, "adopted": 0, "updated": 0, "skipped": 1}
        )
        self.assertEqual(gateway.events[uid]["summary"], "Family corrected title")


class DuplicateDetectionTests(unittest.TestCase):
    """A duplicate must be a real second event, and must be findable."""

    class _Gateway(FakeCalendarGateway):
        def __init__(self, matches: list[dict[str, object]]) -> None:
            super().__init__()
            self.matches = matches

        def find_by_ical_uid(self, uid: str) -> list[dict[str, object]]:
            return self.matches

    def test_duplicate_error_identifies_the_conflicting_events(self) -> None:
        events = parse_events(SAMPLE_ICS)
        gateway = self._Gateway(
            [
                {
                    "id": "aaa111",
                    "summary": "Piano",
                    "start": {"dateTime": "2026-09-04T16:30:00"},
                    "extendedProperties": {
                        "private": {"family_schedule_managed": "true"}
                    },
                },
                {
                    "id": "bbb222",
                    "summary": "Piano lesson",
                    "start": {"dateTime": "2026-09-04T16:30:00"},
                },
            ]
        )

        with self.assertRaises(RuntimeError) as caught:
            sync_events(events, gateway, reminder_minutes=30)

        message = str(caught.exception)
        # Without ids and titles the operator has nothing to search the calendar for.
        self.assertIn("aaa111", message)
        self.assertIn("bbb222", message)
        self.assertIn("Piano lesson", message)
        self.assertIn("managed_by_this_repo=yes", message)
        self.assertIn("managed_by_this_repo=no", message)


class RecurrenceExceptionTests(unittest.TestCase):
    def _items(self) -> list[dict[str, object]]:
        return [
            {"id": "series", "summary": "Piano"},
            # Google stores an edited occurrence as its own event under the same
            # iCalUID; it is not a second event.
            {
                "id": "series_20260911T213000Z",
                "summary": "Piano",
                "recurringEventId": "series",
            },
        ]

    def test_an_edited_occurrence_is_not_counted_as_a_duplicate(self) -> None:
        from family_schedule.google_calendar import (
            GoogleCalendarGateway,
            GoogleCredentials,
        )

        gateway = object.__new__(GoogleCalendarGateway)
        gateway.calendar_id = "family@example.com"
        items = self._items()
        gateway._request_json = lambda *a, **k: {"items": items}  # type: ignore[method-assign]

        matches = gateway.find_by_ical_uid("piano-2026-2027@example.local")

        self.assertEqual([match["id"] for match in matches], ["series"])
        self.assertIsInstance(GoogleCredentials, type)


class AdoptionTests(unittest.TestCase):
    """A hand-imported event must be adopted, never duplicated."""

    class _Gateway(FakeCalendarGateway):
        def __init__(self, adoptable: list[dict[str, object]]) -> None:
            super().__init__()
            self.adoptable = adoptable
            self.patched: list[tuple[str, dict[str, object]]] = []

        def find_by_ical_uid(self, uid: str) -> list[dict[str, object]]:
            return []

        def find_adoptable(self, event: object) -> list[dict[str, object]]:
            return self.adoptable

        def patch_event(self, event_id: str, payload: dict[str, object]) -> None:
            self.patched.append((event_id, payload))

    def _existing(self, identifier: str = "imported-1") -> dict[str, object]:
        return {"id": identifier, "summary": "Tennis"}

    def test_an_unmanaged_twin_is_adopted_instead_of_duplicated(self) -> None:
        gateway = self._Gateway([self._existing()])
        events = parse_events(SAMPLE_ICS)

        result = sync_events(events, gateway, reminder_minutes=30)

        self.assertEqual(result["adopted"], 1)
        self.assertEqual(result["created"], 0)
        self.assertEqual(gateway.created, 0)
        self.assertEqual(gateway.patched[0][0], "imported-1")

    def test_adoption_writes_the_source_uid_so_it_is_found_next_run(self) -> None:
        # iCalUID is immutable, so without this marker the adopted event would be
        # invisible again on the next sync and duplicated after all.
        gateway = self._Gateway([self._existing()])
        events = parse_events(SAMPLE_ICS)

        sync_events(events, gateway, reminder_minutes=30)

        _identifier, payload = gateway.patched[0]
        private = payload["extendedProperties"]["private"]
        self.assertEqual(private["family_schedule_uid"], events[0].uid)
        self.assertEqual(private["family_schedule_managed"], "true")
        self.assertNotIn("iCalUID", payload)

    def test_two_identical_unmanaged_events_are_not_adopted(self) -> None:
        gateway = self._Gateway([self._existing("a"), self._existing("b")])
        events = parse_events(SAMPLE_ICS)

        result = sync_events(events, gateway, reminder_minutes=30)

        # Ambiguous: pick neither, and do not silently attach to the wrong one.
        self.assertEqual(result["adopted"], 0)
        self.assertEqual(result["created"], 1)


class CreationGuardTests(unittest.TestCase):
    class _EmptyCalendar(FakeCalendarGateway):
        def find_by_ical_uid(self, uid: str) -> list[dict[str, object]]:
            return []

        def find_adoptable(self, event: object) -> list[dict[str, object]]:
            return []

    def test_a_bulk_creation_is_refused_before_anything_is_written(self) -> None:
        gateway = self._EmptyCalendar()
        events = parse_events(SAMPLE_ICS)

        with self.assertRaises(RuntimeError) as caught:
            sync_events(events, gateway, reminder_minutes=30, max_new_events=0)

        self.assertIn("Refusing to add 1 new events", str(caught.exception))
        # The guard runs on the plan, so nothing reached the calendar.
        self.assertEqual(gateway.created, 0)

    def test_a_run_within_the_limit_proceeds(self) -> None:
        gateway = self._EmptyCalendar()
        events = parse_events(SAMPLE_ICS)

        result = sync_events(events, gateway, reminder_minutes=30, max_new_events=5)

        self.assertEqual(result["created"], 1)

    def test_no_limit_keeps_the_previous_behaviour(self) -> None:
        gateway = self._EmptyCalendar()
        events = parse_events(SAMPLE_ICS)

        result = sync_events(events, gateway, reminder_minutes=30)

        self.assertEqual(result["created"], 1)


class AdoptionCandidateTests(unittest.TestCase):
    """What the live gateway will and will not offer up for adoption."""

    def _gateway(self, items: list[dict[str, object]]):
        from family_schedule.google_calendar import GoogleCalendarGateway

        gateway = object.__new__(GoogleCalendarGateway)
        gateway.calendar_id = "family@example.com"
        gateway._request_json = lambda *a, **k: {"items": items}  # type: ignore[method-assign]
        return gateway

    def _candidate(self, **overrides: object) -> dict[str, object]:
        event = parse_events(SAMPLE_ICS)[0]
        from family_schedule.ical import to_google_event

        start = to_google_event(event, reminder_minutes=0)["start"]
        candidate: dict[str, object] = {
            "id": "imported",
            "summary": event.summary,
            "start": start,
        }
        candidate.update(overrides)
        return candidate

    def test_an_identical_unmanaged_event_is_adoptable(self) -> None:
        gateway = self._gateway([self._candidate()])

        matches = gateway.find_adoptable(parse_events(SAMPLE_ICS)[0])

        self.assertEqual([match["id"] for match in matches], ["imported"])

    def test_an_event_this_repo_already_manages_is_not_adoptable(self) -> None:
        gateway = self._gateway(
            [
                self._candidate(
                    extendedProperties={"private": {"family_schedule_managed": "true"}}
                )
            ]
        )

        self.assertEqual(gateway.find_adoptable(parse_events(SAMPLE_ICS)[0]), [])

    def test_a_different_title_at_the_same_time_is_not_adoptable(self) -> None:
        gateway = self._gateway([self._candidate(summary="Something else")])

        self.assertEqual(gateway.find_adoptable(parse_events(SAMPLE_ICS)[0]), [])

    def test_a_recurring_instance_is_not_adoptable(self) -> None:
        gateway = self._gateway([self._candidate(recurringEventId="series")])

        self.assertEqual(gateway.find_adoptable(parse_events(SAMPLE_ICS)[0]), [])
