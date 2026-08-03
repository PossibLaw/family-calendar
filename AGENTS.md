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
- Do not run a full reconciliation merely because a new source was added. Normal push
  automation syncs only new or changed sources so manual Google Calendar edits and
  deletions are not continuously reversed.

## Validation commands

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m family_schedule build
.venv/bin/python -m family_schedule sync --dry-run
```

Never expose values from `.env`, `credentials.json`, GitHub Secrets, or AI API keys.
