# Family Calendar agent instructions

These instructions apply to any coding agent working in this repository.

## When someone asks to add a schedule

- Treat “add this schedule” as approval for the complete batch. Do not request approval
  for each event.
- Work only in a private family deployment when the input contains real people,
  addresses, routines, travel, or school information. Never add private schedule data
  to the public template.
- Prefer an official `.ics` source. Otherwise create a standards-compliant `.ics` file
  under `inbox/` with stable unique UIDs, correct IANA time zones, recurrence rules,
  locations, and the configured reminder.
- Add every event with enough date and time information. Skip only unusable items and
  report them after processing; one bad item must not block a valid batch.
- Omit confirmation codes, ticket numbers, loyalty numbers, payment details, barcodes,
  passport data, and unrelated email text.
- Use a distinct source filename so concurrent family submissions normally merge
  without conflict.
- Run the unit tests, Ruff checks, and a dry run before completing the repository
  workflow. The user's request authorizes normal in-scope commit, push, merge, and
  configured calendar-sync steps.
- A full reconciliation (`sync` with no `--changed-since`) refuses to add more than
  `--max-new` events in one run. Hitting that limit means the calendar already holds
  those events under identities this repository does not recognise; check the calendar
  before raising the limit, rather than raising it reflexively.
- Do not run a full reconciliation merely because a new source was added. Normal push
  automation syncs only new or changed sources so manual Google Calendar edits and
  deletions are not continuously reversed.

## Accepting event details in any form

Anyone with access to this repository may hand an agent a schedule as a screenshot, a
PDF, a photo of a letter, a forwarded email, a pasted itinerary, a link to an official
`.ics`, or a plain typed sentence such as "I'm on UA 123 to San Francisco on October
12". All of these are valid input. Read the attachment or the text directly and build
the event from it. No AI API key is involved on this path: the agent is the extractor.

The email intake's two filters do not apply here. Its trusted sender list is enforced
by Gmail, and its category allowlist lives in `build_extracted_calendar`, which a
hand-written `.ics` never reaches. On this path the agent is the only filter, so apply
the same category rule by hand: add an event only when it commits the family to being
somewhere at a specific time — travel, lodging, school, activity, appointment, or an
explicit invitation. A date alone is not enough. Marketing and promotional mail, sale
deadlines, order confirmations, shipping and delivery notices, and billing or account
alerts are never events, even when they state a clear date.

## What to put in the calendar

- **Summary** — recognisable at a glance: `Flight UA 123 ORD to SFO`, `Marriott Union
  Square`, `Piano`. Name the child when the household has more than one and the event
  belongs to one of them.
- **Start and end with an IANA time zone** — `DTSTART;TZID=` and `DTEND;TZID=`. Travel
  legs routinely begin and end in different zones, so use each end's own local zone
  rather than forcing a single one. Chicago to San Francisco is
  `DTSTART;TZID=America/Chicago` with `DTEND;TZID=America/Los_Angeles`; collapsing both
  to one zone silently misstates the duration.
- **All-day events** — `VALUE=DATE`, with an exclusive end date.
- **Location** — whatever helps someone arrive: airport and terminal, street address,
  venue name.
- **UID** — stable and derived from the item itself, such as flight number plus date,
  so resubmitting the same thing updates its event instead of creating a second one.
- **RRULE** — for anything repeating, with an `UNTIL` where the season ends.
- **Reminder** — do not hand-write a `VALARM`. `build_calendar` adds it from
  `calendar.reminder_minutes` in `schedule.toml`.

Omit confirmation codes and record locators, ticket numbers, loyalty and frequent
flyer numbers, payment details, barcodes, passport data, and prices.

## Confirm the ambiguous, invent nothing

Ask a short question when the source is genuinely ambiguous, then write the file:

- The year, which screenshots and confirmations often omit.
- The time zone, when only a city or airport appears and the choice changes the time.
- Whether a multi-leg itinerary should be one event per leg or a single span.

Never guess a missing date or time. Skip an unusable item, add the rest, and report
what was skipped and why.

## Completing the work without further approval

Dropping in the details is the request. Carry it through to a synced calendar event
without asking whether to proceed:

1. Write one new `.ics` under `inbox/` per submission, using a distinct filename.
2. Run the validation commands below. Never push a source that fails them.
3. Commit and push to `main`. `sync-calendar.yml` runs only on pushes to `main`, and
   syncs only the `inbox/` files that push changed, so an event left on a branch never
   reaches the calendar.
4. Confirm the `Sync family calendar` run succeeded, then report what was added and
   anything skipped.

Ask first only when the content is ambiguous per the section above, or when it carries
someone outside the household's private information.

## Validation commands

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m family_schedule build
.venv/bin/python -m family_schedule sync --dry-run
```

Never expose values from `.env`, `credentials.json`, GitHub Secrets, or AI API keys.
