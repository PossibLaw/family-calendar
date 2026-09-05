from __future__ import annotations

import unittest

from family_schedule.ical import (
    build_calendar,
    count_events,
    discover_park_district_urls,
    parse_events,
    to_google_event,
    validate_ical_url,
)

SAMPLE_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//EN
BEGIN:VTIMEZONE
TZID:America/Chicago
END:VTIMEZONE
BEGIN:VEVENT
UID:tennis-1@example.test
DTSTART;TZID=America/Chicago:20260819T153000
DTEND;TZID=America/Chicago:20260819T163000
SUMMARY:Tennis Youth Red 2: Fall I
LOCATION:1 Example Court\\, Exampletown\\, IL 60000
END:VEVENT
END:VCALENDAR
"""


class CalendarImportTests(unittest.TestCase):
    def test_build_calendar_deduplicates_events_and_adds_reminders(self) -> None:
        result = build_calendar([SAMPLE_ICS, SAMPLE_ICS], reminder_minutes=30)

        self.assertEqual(count_events(result), 1)
        self.assertEqual(result.count("UID:tennis-1@example.test"), 1)
        self.assertNotIn("SUMMARY:Piano", result)
        self.assertEqual(result.count("TRIGGER:-PT30M"), 1)

    def test_build_calendar_preserves_recurring_rules_from_input(self) -> None:
        recurring = SAMPLE_ICS.replace(
            "SUMMARY:Tennis Youth Red 2: Fall I",
            "RRULE:FREQ=WEEKLY;COUNT=4;BYDAY=WE\nSUMMARY:Weekly activity",
        ).replace("UID:tennis-1@example.test", "UID:weekly@example.test")

        result = build_calendar([recurring], reminder_minutes=15)

        self.assertIn("RRULE:FREQ=WEEKLY;COUNT=4;BYDAY=WE", result)
        self.assertIn("SUMMARY:Weekly activity", result)
        self.assertIn("TRIGGER:-PT15M", result)

    def test_discovers_line_wrapped_park_district_calendar_urls(self) -> None:
        text = (
            "Download: https://anprod.active.com/exampleparks/servlet/"
            "RegistrationScheduleiCalFile.sdi?cid=F4B20E870A37AC&rh=\n"
            "FA8D0B8F0835A5FD"
        )

        self.assertEqual(
            discover_park_district_urls(text),
            [
                (
                    "https://anprod.active.com/exampleparks/servlet/"
                    "RegistrationScheduleiCalFile.sdi?cid=F4B20E870A37AC"
                    "&rh=FA8D0B8F0835A5FD"
                )
            ],
        )

    def test_discovers_other_active_communities_tenants(self) -> None:
        text = (
            "https://anprod.active.com/springfieldparks/servlet/"
            "RegistrationScheduleiCalFile.sdi?cid=ABC123&rh=DEF456"
        )

        self.assertEqual(
            discover_park_district_urls(text),
            [
                (
                    "https://anprod.active.com/springfieldparks/servlet/"
                    "RegistrationScheduleiCalFile.sdi?cid=ABC123&rh=DEF456"
                )
            ],
        )

    def test_parse_events_keeps_stable_source_identifiers(self) -> None:
        event = parse_events(SAMPLE_ICS)[0]

        self.assertEqual(event.uid, "tennis-1@example.test")
        self.assertEqual(event.summary, "Tennis Youth Red 2: Fall I")
        self.assertEqual(event.start, "20260819T153000")

    def test_maps_ical_event_to_google_calendar_payload(self) -> None:
        event = parse_events(SAMPLE_ICS)[0]

        payload = to_google_event(event, reminder_minutes=30)

        self.assertEqual(payload["iCalUID"], "tennis-1@example.test")
        self.assertEqual(
            payload["start"],
            {
                "dateTime": "2026-08-19T15:30:00",
                "timeZone": "America/Chicago",
            },
        )
        self.assertEqual(payload["reminders"]["overrides"][0]["minutes"], 30)

    def test_rejects_untrusted_calendar_feed_hosts(self) -> None:
        with self.assertRaises(ValueError):
            validate_ical_url(
                "https://evil.example/calendar.ics", {"anprod.active.com"}
            )
