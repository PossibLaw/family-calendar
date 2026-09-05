from __future__ import annotations

import argparse
import json
import subprocess
import tomllib
from collections import Counter
from pathlib import Path

from .ai import HostedAIExtractor
from .auth import authorize_google
from .google_calendar import (
    GoogleCalendarGateway,
    GoogleCredentials,
    plan_sync,
    summarize_plan,
    sync_events,
)
from .ical import CalendarEvent, build_calendar, parse_events
from .inbox import GmailGateway, intake_search_query, process_inbox
from .sources import calendars_from_source


def _load_settings(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def _source_paths(explicit: list[Path], inbox: Path) -> list[Path]:
    candidates = explicit or _inbox_sources(inbox)
    paths = sorted({path.resolve() for path in candidates})
    if not paths:
        raise RuntimeError(f"No .ics or .pdf schedule sources found in {inbox}")
    for path in paths:
        if not path.is_file():
            raise RuntimeError(f"Schedule source does not exist: {path}")
    return paths


def _inbox_sources(inbox: Path) -> list[Path]:
    return [path for path in inbox.iterdir() if path.suffix.lower() in {".ics", ".pdf"}]


def _changed_source_paths(revision: str, inbox: Path) -> list[Path]:
    revision = revision.strip()
    if not revision:
        raise ValueError("changed source revision cannot be empty")
    verified = subprocess.run(
        ["git", "rev-parse", "--verify", f"{revision}^{{commit}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if verified.returncode != 0:
        # Falling back to every source here would reconcile the whole calendar on an
        # ordinary push and revert the family's manual edits, which is exactly what
        # this flag exists to avoid. A shallow checkout is the usual cause: the
        # workflow must fetch enough history for this revision to resolve.
        raise RuntimeError(
            f"Cannot resolve --changed-since revision {revision!r} in this checkout. "
            "Fetch enough git history (fetch-depth: 0) and re-run; refusing to fall "
            "back to a full reconciliation."
        )
    changed = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=AM",
            revision,
            "HEAD",
            "--",
            str(inbox),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    inbox_root = inbox.resolve()
    paths: list[Path] = []
    for raw_path in changed.stdout.splitlines():
        path = Path(raw_path)
        resolved = path.resolve()
        if (
            resolved.is_relative_to(inbox_root)
            and path.suffix.lower() in {".ics", ".pdf"}
            and path.is_file()
        ):
            paths.append(resolved)
    return sorted(set(paths))


def _calendar_for_paths(
    paths: list[Path], settings: dict[str, object]
) -> tuple[str, list[CalendarEvent]]:
    calendar_settings = settings["calendar"]  # type: ignore[index]
    provider_settings = settings["providers"]  # type: ignore[index]
    if not isinstance(calendar_settings, dict) or not isinstance(
        provider_settings, dict
    ):
        raise TypeError("schedule.toml has invalid calendar or provider settings")
    allowed_hosts = set(provider_settings["allowed_ical_hosts"])
    calendars: list[str] = []
    for path in paths:
        calendars.extend(calendars_from_source(path, allowed_hosts))
    merged = build_calendar(
        calendars,
        calendar_name=str(calendar_settings.get("name", "Family Calendar")),
        reminder_minutes=int(calendar_settings["reminder_minutes"]),
    )
    return merged, parse_events(merged)


def _build(args: argparse.Namespace) -> int:
    settings = _load_settings(args.config)
    calendar_settings = settings["calendar"]
    paths = _source_paths(args.source, args.inbox)
    merged, events = _calendar_for_paths(paths, settings)
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


def _sync(args: argparse.Namespace) -> int:
    settings = _load_settings(args.config)
    calendar_settings = settings["calendar"]
    if args.source:
        paths = _source_paths(args.source, args.inbox)
    elif args.changed_since:
        paths = _changed_source_paths(args.changed_since, args.inbox)
    else:
        paths = sorted(path.resolve() for path in _inbox_sources(args.inbox))
    if not paths:
        print(
            json.dumps(
                {
                    "sources": [],
                    "event_records": 0,
                    "created": 0,
                    "updated": 0,
                    "skipped": 0,
                },
                indent=2,
            )
        )
        return 0
    _merged, events = _calendar_for_paths(paths, settings)
    gateway = GoogleCalendarGateway(
        str(calendar_settings["id"]), GoogleCredentials.from_environment()
    )
    reminder_minutes = int(calendar_settings["reminder_minutes"])
    if args.dry_run:
        # Report the decided plan, not just a record count, so a run that would
        # add dozens of events says so before anyone approves it.
        actions = plan_sync(events, gateway, reminder_minutes=reminder_minutes)
        print(
            json.dumps(
                {
                    "sources": [path.name for path in paths],
                    "event_records": len(events),
                    "dry_run": True,
                    **summarize_plan(actions),
                    "would_create": [
                        action.event.summary
                        for action in actions
                        if action.kind == "create"
                    ][:20],
                },
                indent=2,
            )
        )
        return 0
    result = sync_events(
        events,
        gateway,
        reminder_minutes=reminder_minutes,
        max_new_events=args.max_new,
    )
    print(
        json.dumps(
            {
                "sources": [path.name for path in paths],
                "event_records": len(events),
                **result,
            },
            indent=2,
        )
    )
    return 0


def _authorize(args: argparse.Namespace) -> int:
    output = authorize_google(args.credentials, args.output, with_gmail=args.with_gmail)
    service = "Google Calendar and Gmail" if args.with_gmail else "Google Calendar"
    print(f"{service} authorization saved securely to {output}")
    print("Do not commit or share this file.")
    return 0


def _process_inbox(args: argparse.Namespace) -> int:
    settings = _load_settings(args.config)
    calendar_settings = settings["calendar"]
    provider_settings = settings["providers"]
    intake_settings = settings["intake"]
    address = str(intake_settings.get("address", "")).strip()
    if not address:
        raise RuntimeError(
            "Set intake.address in schedule.toml before processing email"
        )
    senders = intake_settings.get("trusted_senders", [])
    if not isinstance(senders, list):
        raise TypeError("intake.trusted_senders must be a list")
    allow_any_sender = bool(intake_settings.get("allow_any_sender", False))
    trusted = {str(sender) for sender in senders}
    sender_allowlist = None if allow_any_sender else trusted
    credentials = GoogleCredentials.from_environment()
    extractor = HostedAIExtractor.from_environment()
    result = process_inbox(
        GmailGateway(credentials),
        GoogleCalendarGateway(str(calendar_settings["id"]), credentials),
        intake_address=address,
        trusted_senders=trusted,
        allow_any_sender=allow_any_sender,
        allowed_ical_hosts=set(provider_settings["allowed_ical_hosts"]),
        calendar_name=str(calendar_settings.get("name", "Family Calendar")),
        default_timezone=str(calendar_settings.get("timezone", "UTC")),
        reminder_minutes=int(calendar_settings["reminder_minutes"]),
        extractor=extractor,
    )
    # A run that sees nothing is the hardest failure to diagnose from a log, so
    # always report which mailbox query ran and whether autopilot was available.
    print(
        json.dumps(
            {
                "intake_address": address,
                "search_query": intake_search_query(address, sender_allowlist),
                "ai_autopilot": "enabled" if extractor else "disabled",
                **result,
            },
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="family-calendar")
    parser.add_argument("--config", type=Path, default=Path("schedule.toml"))
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="Build a validated iCalendar import")
    build.add_argument("--source", type=Path, action="append", default=[])
    build.add_argument("--inbox", type=Path, default=Path("inbox"))
    build.add_argument("--output", type=Path, default=Path("build/family-schedule.ics"))
    build.add_argument("--manifest", type=Path, default=Path("build/manifest.json"))
    build.set_defaults(handler=_build)

    apply = commands.add_parser("apply", help="Idempotently sync the validated import")
    apply.add_argument("--input", type=Path, default=Path("build/family-schedule.ics"))
    apply.add_argument("--dry-run", action="store_true")
    apply.set_defaults(handler=_apply)

    sync = commands.add_parser(
        "sync", help="Build and sync a trusted schedule batch immediately"
    )
    sync.add_argument("--source", type=Path, action="append", default=[])
    sync.add_argument("--inbox", type=Path, default=Path("inbox"))
    sync.add_argument(
        "--changed-since",
        help="Only sync inbox files added or modified after this Git revision",
    )
    sync.add_argument("--dry-run", action="store_true")
    sync.add_argument(
        "--max-new",
        type=int,
        default=None,
        help="Refuse the run if it would add more than this many new events",
    )
    sync.set_defaults(handler=_sync)

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
    authorize.add_argument(
        "--with-gmail",
        action="store_true",
        help="Also authorize the scheduled family email inbox",
    )
    authorize.set_defaults(handler=_authorize)

    inbox = commands.add_parser(
        "process-inbox",
        help="Add trusted email schedule batches to Google Calendar",
    )
    inbox.set_defaults(handler=_process_inbox)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.handler(args)
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
        parser.error(str(error))
    return 2
