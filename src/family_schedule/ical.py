from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

PARK_DISTRICT_ICAL_URL = re.compile(
    r"https://anprod\.active\.com/([A-Za-z0-9_-]+)/servlet/"
    r"RegistrationScheduleiCalFile\.sdi\?cid=([A-Za-z0-9]+)&rh=\s*([A-Za-z0-9]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CalendarEvent:
    uid: str
    summary: str
    start: str
    end: str
    lines: tuple[str, ...]


def _unfold_lines(calendar: str) -> list[str]:
    unfolded: list[str] = []
    for line in calendar.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        elif line:
            unfolded.append(line)
    return unfolded


def _property_value(lines: tuple[str, ...], name: str) -> str:
    prefix = f"{name}:"
    parameterized_prefix = f"{name};"
    for line in lines:
        if line.startswith(prefix):
            return line[len(prefix) :]
        if line.startswith(parameterized_prefix):
            return line.split(":", 1)[1]
    raise ValueError(f"VEVENT is missing {name}")


def _property_line(lines: tuple[str, ...], name: str) -> str | None:
    for line in lines:
        if line.startswith((f"{name}:", f"{name};")):
            return line
    return None


def _unescape_text(value: str) -> str:
    return (
        value.replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )


def escape_ical_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def _google_time(line: str) -> dict[str, str]:
    declaration, value = line.split(":", 1)
    parameters: dict[str, str] = {}
    for parameter in declaration.split(";")[1:]:
        if "=" in parameter:
            key, parameter_value = parameter.split("=", 1)
            parameters[key.upper()] = parameter_value

    if parameters.get("VALUE") == "DATE" or len(value) == 8:
        return {"date": f"{value[0:4]}-{value[4:6]}-{value[6:8]}"}

    if value.endswith("Z"):
        normalized = value[:-1]
        suffix = "Z"
    else:
        normalized = value
        suffix = ""
    date_time = (
        f"{normalized[0:4]}-{normalized[4:6]}-{normalized[6:8]}"
        f"T{normalized[9:11]}:{normalized[11:13]}:{normalized[13:15]}{suffix}"
    )
    result = {"dateTime": date_time}
    if "TZID" in parameters:
        result["timeZone"] = parameters["TZID"]
    return result


def _components(lines: list[str], kind: str) -> list[tuple[str, ...]]:
    start = f"BEGIN:{kind}"
    end = f"END:{kind}"
    components: list[tuple[str, ...]] = []
    current: list[str] | None = None
    for line in lines:
        if line == start:
            current = [line]
        elif current is not None:
            current.append(line)
            if line == end:
                components.append(tuple(current))
                current = None
    return components


def parse_events(calendar: str) -> list[CalendarEvent]:
    events: list[CalendarEvent] = []
    for lines in _components(_unfold_lines(calendar), "VEVENT"):
        events.append(
            CalendarEvent(
                uid=_property_value(lines, "UID"),
                summary=_property_value(lines, "SUMMARY"),
                start=_property_value(lines, "DTSTART"),
                end=_property_value(lines, "DTEND"),
                lines=lines,
            )
        )
    return events


def discover_park_district_urls(text: str) -> list[str]:
    urls: list[str] = []
    for tenant, cid, receipt_hash in PARK_DISTRICT_ICAL_URL.findall(text):
        url = (
            f"https://anprod.active.com/{tenant}/servlet/"
            f"RegistrationScheduleiCalFile.sdi?cid={cid}&rh={receipt_hash}"
        )
        if url not in urls:
            urls.append(url)
    return urls


def validate_ical_url(url: str, allowed_hosts: set[str]) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in allowed_hosts:
        raise ValueError(
            f"Refusing iCalendar URL outside the allow-list: {parsed.hostname!r}"
        )


def _with_reminder(lines: tuple[str, ...], minutes: int) -> tuple[str, ...]:
    if "BEGIN:VALARM" in lines:
        return lines
    closing_index = lines.index("END:VEVENT")
    reminder = (
        "BEGIN:VALARM",
        "ACTION:DISPLAY",
        "DESCRIPTION:Reminder",
        f"TRIGGER:-PT{minutes}M",
        "END:VALARM",
    )
    return lines[:closing_index] + reminder + lines[closing_index:]


def build_calendar(
    calendars: list[str],
    *,
    calendar_name: str = "Family Calendar",
    reminder_minutes: int = 30,
) -> str:
    """Merge event feeds into a deterministic import file without duplicate UIDs."""
    events: dict[str, CalendarEvent] = {}
    time_zone_component: tuple[str, ...] | None = None
    for calendar in calendars:
        lines = _unfold_lines(calendar)
        if time_zone_component is None:
            zones = _components(lines, "VTIMEZONE")
            time_zone_component = zones[0] if zones else None
        for event in parse_events(calendar):
            events.setdefault(event.uid, event)

    output = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Family Calendar//Schedule Import//EN",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:" + escape_ical_text(calendar_name),
    ]
    if time_zone_component:
        output.extend(time_zone_component)
    for event in sorted(events.values(), key=lambda item: (item.start, item.uid)):
        output.extend(_with_reminder(event.lines, reminder_minutes))
    output.append("END:VCALENDAR")
    return "\r\n".join(output) + "\r\n"


def count_events(calendar: str) -> int:
    return len(parse_events(calendar))


def to_google_event(
    event: CalendarEvent, *, reminder_minutes: int
) -> dict[str, object]:
    """Convert a validated VEVENT into a Google Calendar Events resource."""
    start_line = _property_line(event.lines, "DTSTART")
    end_line = _property_line(event.lines, "DTEND")
    if start_line is None or end_line is None:
        raise ValueError(f"Event {event.uid!r} is missing a start or end")

    payload: dict[str, object] = {
        "iCalUID": event.uid,
        "summary": _unescape_text(event.summary),
        "start": _google_time(start_line),
        "end": _google_time(end_line),
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": reminder_minutes}],
        },
    }
    location = _property_line(event.lines, "LOCATION")
    if location is not None:
        payload["location"] = _unescape_text(location.split(":", 1)[1])
    description = _property_line(event.lines, "DESCRIPTION")
    if description is not None:
        payload["description"] = _unescape_text(description.split(":", 1)[1])
    recurrence = _property_line(event.lines, "RRULE")
    if recurrence is not None:
        payload["recurrence"] = [recurrence]
    return payload
