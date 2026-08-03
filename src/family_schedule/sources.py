from __future__ import annotations

from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .ical import discover_park_district_urls, validate_ical_url

MAX_ICAL_BYTES = 5 * 1024 * 1024
MAX_SOURCE_BYTES = 20 * 1024 * 1024


def decode_ical_bytes(data: bytes, charset: str | None) -> str:
    if charset:
        return data.decode(charset)
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise RuntimeError(
            "PDF input requires pypdf; install the project dependencies"
        ) from error
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def fetch_ical(url: str, allowed_hosts: set[str]) -> str:
    validate_ical_url(url, allowed_hosts)
    request = Request(
        url,
        method="GET",
        headers={"Accept": "text/calendar", "User-Agent": "family-schedule/0.1"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            data = response.read(MAX_ICAL_BYTES + 1)
            charset = response.headers.get_content_charset()
    except (HTTPError, URLError) as error:
        raise RuntimeError("Unable to download an approved iCalendar feed") from error
    if len(data) > MAX_ICAL_BYTES:
        raise RuntimeError("iCalendar feed exceeds the 5 MB safety limit")
    calendar = decode_ical_bytes(data, charset)
    if "BEGIN:VCALENDAR" not in calendar or "BEGIN:VEVENT" not in calendar:
        raise RuntimeError("Approved URL did not return an iCalendar event feed")
    return calendar


def calendars_from_source(path: Path, allowed_hosts: set[str]) -> list[str]:
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise RuntimeError(f"Schedule source exceeds the 20 MB size limit: {path}")
    suffix = path.suffix.lower()
    if suffix == ".ics":
        calendar = path.read_text(encoding="utf-8-sig")
        if "BEGIN:VCALENDAR" not in calendar:
            raise RuntimeError(f"Invalid iCalendar file: {path}")
        return [calendar]
    if suffix == ".pdf":
        text = extract_pdf_text(path)
        urls = discover_park_district_urls(text)
        if not urls:
            raise RuntimeError(
                f"PDF has no trusted Park District calendar feed and requires review: {path}"
            )
        return [fetch_ical(url, allowed_hosts) for url in urls]
    raise RuntimeError(f"Unsupported schedule source type: {path}")
