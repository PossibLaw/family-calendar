from __future__ import annotations

import base64
import html
import json
import re
import tempfile
from dataclasses import dataclass
from email.utils import parseaddr
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .ai import EventExtractor, build_extracted_calendar
from .google_calendar import (
    CalendarGateway,
    GoogleCredentials,
    refresh_google_access_token,
    sync_events,
)
from .ical import build_calendar, parse_events
from .sources import MAX_SOURCE_BYTES, calendars_from_source, extract_pdf_text

MAX_GMAIL_RESPONSE_BYTES = 30 * 1024 * 1024
MAX_MESSAGES_PER_RUN = 500
PROCESSED_LABEL = "Family Calendar Processed"
NEEDS_ATTENTION_LABEL = "Family Calendar Needs Attention"


@dataclass(frozen=True)
class InboxAttachment:
    filename: str
    content_type: str
    data: bytes


@dataclass(frozen=True)
class InboxMessage:
    message_id: str
    sender: str
    subject: str
    text: str
    attachments: tuple[InboxAttachment, ...]


class MailGateway(Protocol):
    def list_messages(self, intake_address: str) -> list[InboxMessage]: ...

    def mark_processed(self, message_id: str) -> None: ...

    def mark_needs_attention(self, message_id: str) -> None: ...


def _decode_base64url(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except (ValueError, TypeError) as error:
        raise RuntimeError("Gmail returned an invalid attachment") from error


def _plain_html(value: str) -> str:
    without_scripts = re.sub(
        r"<(script|style)\b[^>]*>.*?</\1>", " ", value, flags=re.DOTALL | re.IGNORECASE
    )
    without_tags = re.sub(r"<[^>]+>", " ", without_scripts)
    return re.sub(r"\s+", " ", html.unescape(without_tags)).strip()


class GmailGateway:
    def __init__(self, credentials: GoogleCredentials) -> None:
        self.access_token = refresh_google_access_token(credentials)
        self._label_ids: dict[str, str] = {}
        self._ensure_labels()

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
                "User-Agent": "family-calendar/0.2",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read(MAX_GMAIL_RESPONSE_BYTES + 1)
        except HTTPError as error:
            raise RuntimeError(
                f"Gmail API request failed with HTTP {error.code}"
            ) from error
        if len(raw) > MAX_GMAIL_RESPONSE_BYTES:
            raise RuntimeError("Gmail API response exceeded the 30 MB limit")
        if not raw:
            return {}
        try:
            result = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RuntimeError("Gmail API returned an invalid response") from error
        if not isinstance(result, dict):
            raise RuntimeError(  # noqa: TRY004 - malformed external API response
                "Gmail API returned an invalid response"
            )
        return result

    @property
    def _base_url(self) -> str:
        return "https://gmail.googleapis.com/gmail/v1/users/me"

    def _ensure_labels(self) -> None:
        result = self._request_json("GET", f"{self._base_url}/labels")
        labels = result.get("labels", [])
        if not isinstance(labels, list):
            raise RuntimeError(  # noqa: TRY004 - malformed external API response
                "Gmail API returned an invalid label list"
            )
        for label in labels:
            if isinstance(label, dict) and isinstance(label.get("name"), str):
                label_id = label.get("id")
                if isinstance(label_id, str):
                    self._label_ids[label["name"]] = label_id
        for name in (PROCESSED_LABEL, NEEDS_ATTENTION_LABEL):
            if name in self._label_ids:
                continue
            created = self._request_json(
                "POST",
                f"{self._base_url}/labels",
                {
                    "name": name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                },
            )
            label_id = created.get("id")
            if not isinstance(label_id, str) or not label_id:
                raise RuntimeError("Gmail did not return the created label ID")
            self._label_ids[name] = label_id

    def _attachment_data(self, message_id: str, attachment_id: str) -> bytes:
        safe_message = quote(message_id, safe="")
        safe_attachment = quote(attachment_id, safe="")
        result = self._request_json(
            "GET",
            f"{self._base_url}/messages/{safe_message}/attachments/{safe_attachment}",
        )
        value = result.get("data")
        if not isinstance(value, str):
            raise RuntimeError(  # noqa: TRY004 - malformed external API response
                "Gmail attachment has no data"
            )
        data = _decode_base64url(value)
        if len(data) > MAX_SOURCE_BYTES:
            raise RuntimeError("Gmail attachment exceeds the 20 MB source limit")
        return data

    def _message_from_payload(
        self, message_id: str, result: dict[str, object]
    ) -> InboxMessage:
        payload = result.get("payload")
        if not isinstance(payload, dict):
            raise RuntimeError(  # noqa: TRY004 - malformed external API response
                "Gmail message has no MIME payload"
            )
        headers = payload.get("headers", [])
        header_values: dict[str, str] = {}
        if isinstance(headers, list):
            for item in headers:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                value = item.get("value")
                if isinstance(name, str) and isinstance(value, str):
                    header_values[name.lower()] = value
        sender = parseaddr(header_values.get("from", ""))[1].strip().lower()
        if not sender:
            raise RuntimeError("Gmail message has no sender address")

        plain_parts: list[str] = []
        html_parts: list[str] = []
        attachments: list[InboxAttachment] = []

        def visit(part: dict[str, object]) -> None:
            parts = part.get("parts", [])
            if isinstance(parts, list):
                for child in parts:
                    if isinstance(child, dict):
                        visit(child)
            mime_type = str(part.get("mimeType", "application/octet-stream"))
            filename = str(part.get("filename", "")).strip()
            body = part.get("body", {})
            if not isinstance(body, dict):
                return
            raw_data: bytes | None = None
            inline = body.get("data")
            attachment_id = body.get("attachmentId")
            if isinstance(inline, str):
                raw_data = _decode_base64url(inline)
            elif isinstance(attachment_id, str):
                raw_data = self._attachment_data(message_id, attachment_id)
            if raw_data is None:
                return
            if len(raw_data) > MAX_SOURCE_BYTES:
                raise RuntimeError("Gmail message part exceeds the 20 MB source limit")
            if filename or mime_type in {"text/calendar", "application/pdf"}:
                if not filename:
                    filename = (
                        "calendar.ics"
                        if mime_type == "text/calendar"
                        else "schedule.pdf"
                    )
                attachments.append(InboxAttachment(filename, mime_type, raw_data))
            elif mime_type == "text/plain":
                plain_parts.append(raw_data.decode("utf-8", errors="replace"))
            elif mime_type == "text/html":
                html_parts.append(raw_data.decode("utf-8", errors="replace"))

        visit(payload)
        text = "\n".join(part.strip() for part in plain_parts if part.strip())
        if not text:
            text = "\n".join(_plain_html(part) for part in html_parts if part.strip())
        return InboxMessage(
            message_id=message_id,
            sender=sender,
            subject=header_values.get("subject", "").strip(),
            text=text,
            attachments=tuple(attachments),
        )

    def list_messages(self, intake_address: str) -> list[InboxMessage]:
        if (
            not intake_address
            or "@" not in intake_address
            or any(character.isspace() for character in intake_address)
        ):
            raise ValueError("Email intake address is invalid")
        query = (
            f"deliveredto:{intake_address} "
            f'-label:"{PROCESSED_LABEL}" -label:"{NEEDS_ATTENTION_LABEL}"'
        )
        message_ids: list[str] = []
        page_token: str | None = None
        while len(message_ids) < MAX_MESSAGES_PER_RUN:
            parameters = {"q": query, "maxResults": 100}
            if page_token:
                parameters["pageToken"] = page_token
            result = self._request_json(
                "GET", f"{self._base_url}/messages?{urlencode(parameters)}"
            )
            messages = result.get("messages", [])
            if not isinstance(messages, list):
                raise RuntimeError(  # noqa: TRY004 - malformed external API response
                    "Gmail API returned an invalid message list"
                )
            for item in messages:
                if isinstance(item, dict) and isinstance(item.get("id"), str):
                    message_ids.append(item["id"])
                    if len(message_ids) >= MAX_MESSAGES_PER_RUN:
                        break
            next_token = result.get("nextPageToken")
            page_token = next_token if isinstance(next_token, str) else None
            if not page_token:
                break

        output: list[InboxMessage] = []
        for message_id in message_ids:
            safe_id = quote(message_id, safe="")
            result = self._request_json(
                "GET", f"{self._base_url}/messages/{safe_id}?format=full"
            )
            output.append(self._message_from_payload(message_id, result))
        return output

    def _mark(self, message_id: str, label_name: str) -> None:
        safe_id = quote(message_id, safe="")
        self._request_json(
            "POST",
            f"{self._base_url}/messages/{safe_id}/modify",
            {"addLabelIds": [self._label_ids[label_name]]},
        )

    def mark_processed(self, message_id: str) -> None:
        self._mark(message_id, PROCESSED_LABEL)

    def mark_needs_attention(self, message_id: str) -> None:
        self._mark(message_id, NEEDS_ATTENTION_LABEL)


def _attachment_calendars(
    attachment: InboxAttachment,
    allowed_ical_hosts: set[str],
    extractor: EventExtractor | None,
    *,
    source_id: str,
    calendar_name: str,
    default_timezone: str,
    reminder_minutes: int,
) -> tuple[list[str], int]:
    suffix = Path(attachment.filename).suffix.lower()
    if attachment.content_type == "text/calendar" and suffix != ".ics":
        suffix = ".ics"
    if attachment.content_type == "application/pdf" and suffix != ".pdf":
        suffix = ".pdf"
    if suffix not in {".ics", ".pdf"}:
        return [], 0
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / f"source{suffix}"
        path.write_bytes(attachment.data)
        try:
            return calendars_from_source(path, allowed_ical_hosts), 0
        except RuntimeError:
            if suffix != ".pdf" or extractor is None:
                raise
            payload = extractor.extract(
                extract_pdf_text(path), default_timezone=default_timezone
            )
            extraction = build_extracted_calendar(
                payload,
                source_id=source_id,
                calendar_name=calendar_name,
                reminder_minutes=reminder_minutes,
            )
            if extraction.accepted == 0:
                raise RuntimeError("AI could not extract any dated events from the PDF")
            return [extraction.calendar], len(extraction.rejected)


def process_inbox(
    mail_gateway: MailGateway,
    calendar_gateway: CalendarGateway,
    *,
    intake_address: str,
    trusted_senders: set[str],
    allow_any_sender: bool,
    allowed_ical_hosts: set[str],
    calendar_name: str,
    default_timezone: str,
    reminder_minutes: int,
    extractor: EventExtractor | None = None,
) -> dict[str, int]:
    messages = mail_gateway.list_messages(intake_address)
    trusted = {sender.strip().lower() for sender in trusted_senders if sender.strip()}
    totals = {
        "messages_seen": len(messages),
        "messages_processed": 0,
        "messages_needing_attention": 0,
        "events_created": 0,
        "events_updated": 0,
        "events_skipped": 0,
        "items_rejected": 0,
    }
    for message in messages:
        if not allow_any_sender and message.sender.lower() not in trusted:
            mail_gateway.mark_needs_attention(message.message_id)
            totals["messages_needing_attention"] += 1
            continue
        try:
            calendars: list[str] = []
            rejected = 0
            for index, attachment in enumerate(message.attachments):
                try:
                    extracted, rejected_items = _attachment_calendars(
                        attachment,
                        allowed_ical_hosts,
                        extractor,
                        source_id=f"{message.message_id}-attachment-{index}",
                        calendar_name=calendar_name,
                        default_timezone=default_timezone,
                        reminder_minutes=reminder_minutes,
                    )
                except (OSError, RuntimeError, TypeError, ValueError):
                    rejected += 1
                    continue
                calendars.extend(extracted)
                rejected += rejected_items
            if not calendars and extractor is not None and message.text.strip():
                payload = extractor.extract(
                    f"Subject: {message.subject}\n\n{message.text}",
                    default_timezone=default_timezone,
                )
                extraction = build_extracted_calendar(
                    payload,
                    source_id=message.message_id,
                    calendar_name=calendar_name,
                    reminder_minutes=reminder_minutes,
                )
                if extraction.accepted:
                    calendars.append(extraction.calendar)
                rejected += len(extraction.rejected)
            if not calendars:
                raise RuntimeError("Message has no supported schedule data")
            merged = build_calendar(
                calendars,
                calendar_name=calendar_name,
                reminder_minutes=reminder_minutes,
            )
            events = parse_events(merged)
            if not events:
                raise RuntimeError("Message produced no valid calendar events")
            result = sync_events(
                events,
                calendar_gateway,
                reminder_minutes=reminder_minutes,
            )
            mail_gateway.mark_processed(message.message_id)
            totals["messages_processed"] += 1
            totals["events_created"] += result["created"]
            totals["events_updated"] += result["updated"]
            totals["events_skipped"] += result["skipped"]
            totals["items_rejected"] += rejected
        except (OSError, RuntimeError, TypeError, ValueError):
            mail_gateway.mark_needs_attention(message.message_id)
            totals["messages_needing_attention"] += 1
    return totals
