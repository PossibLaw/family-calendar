from __future__ import annotations

import argparse
import json
import tomllib
from collections import Counter
from pathlib import Path

from .auth import authorize_google
from .google_calendar import GoogleCalendarGateway, GoogleCredentials, sync_events
from .ical import build_calendar, parse_events
from .sources import calendars_from_source


def _load_settings(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def _source_paths(explicit: list[Path], inbox: Path) -> list[Path]:
    candidates = explicit or [
        path for path in inbox.iterdir() if path.suffix.lower() in {".ics", ".pdf"}
    ]
    paths = sorted({path.resolve() for path in candidates})
    if not paths:
        raise RuntimeError(f"No .ics or .pdf schedule sources found in {inbox}")
    for path in paths:
        if not path.is_file():
            raise RuntimeError(f"Schedule source does not exist: {path}")
    return paths


def _build(args: argparse.Namespace) -> int:
    settings = _load_settings(args.config)
    calendar_settings = settings["calendar"]
    provider_settings = settings["providers"]
    allowed_hosts = set(provider_settings["allowed_ical_hosts"])
    paths = _source_paths(args.source, args.inbox)

    calendars: list[str] = []
    for path in paths:
        calendars.extend(calendars_from_source(path, allowed_hosts))
    merged = build_calendar(
        calendars,
        calendar_name=str(calendar_settings.get("name", "Family Calendar")),
        reminder_minutes=calendar_settings["reminder_minutes"],
    )
    events = parse_events(merged)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(merged, encoding="utf-8", newline="")
    manifest = {
        "calendar_id": calendar_settings["id"],
        "event_records": len(events),
        "sources": [path.name for path in paths],
        "summaries": dict(sorted(Counter(event.summary for event in events).items())),
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


def _apply(args: argparse.Namespace) -> int:
    settings = _load_settings(args.config)
    calendar_settings = settings["calendar"]
    events = parse_events(args.input.read_text(encoding="utf-8-sig"))
    if args.dry_run:
        print(json.dumps({"event_records": len(events), "dry_run": True}, indent=2))
        return 0
    gateway = GoogleCalendarGateway(
        str(calendar_settings["id"]), GoogleCredentials.from_environment()
    )
    result = sync_events(
        events,
        gateway,
        reminder_minutes=int(calendar_settings["reminder_minutes"]),
    )
    print(json.dumps(result, indent=2))
    return 0


def _authorize(args: argparse.Namespace) -> int:
    output = authorize_google(args.credentials, args.output)
    print(f"Google Calendar authorization saved securely to {output}")
    print("Do not commit or share this file.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="family-calendar")
    parser.add_argument("--config", type=Path, default=Path("schedule.toml"))
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="Build a reviewed iCalendar import")
    build.add_argument("--source", type=Path, action="append", default=[])
    build.add_argument("--inbox", type=Path, default=Path("inbox"))
    build.add_argument("--output", type=Path, default=Path("build/family-schedule.ics"))
    build.add_argument("--manifest", type=Path, default=Path("build/manifest.json"))
    build.set_defaults(handler=_build)

    apply = commands.add_parser("apply", help="Idempotently sync the reviewed import")
    apply.add_argument("--input", type=Path, default=Path("build/family-schedule.ics"))
    apply.add_argument("--dry-run", action="store_true")
    apply.set_defaults(handler=_apply)

    authorize = commands.add_parser(
        "authorize",
        help="Connect Google Calendar in a browser and save a private local token",
    )
    authorize.add_argument(
        "--credentials",
        type=Path,
        default=Path("credentials.json"),
        help="OAuth desktop client JSON downloaded from Google Cloud",
    )
    authorize.add_argument("--output", type=Path, default=Path(".env"))
    authorize.set_defaults(handler=_authorize)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.handler(args)
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))
    return 2
