# Set up Family Calendar with a coding agent

Give this file and the private repository to Codex, Claude, Gemini, or another coding
agent. The person setting up the calendar should not need to edit code.

## Copy this prompt

> Set up this private Family Calendar repository. Ask me only for the Google Calendar
> account or Calendar ID, IANA time zone, reminder minutes, and whether I want the
> family email inbox and optional AI autopilot. Keep every credential out of chat and
> Git. Guide me through Google Cloud and consent in the browser, place secret values
> directly in GitHub Actions Secrets, configure `schedule.toml`, run all tests and a
> dry run, and explain the three ways my family can add schedules. Do not enable a
> calendar-writing workflow until its dry run passes.

## Definition of done for the agent

1. Confirm the deployment repository is private.
2. Configure the calendar ID, time zone, reminder, and optional intake address.
3. Enable Google Calendar API. Enable Gmail API only for email intake.
4. Run `family_schedule authorize`; use `--with-gmail` only for email intake.
5. Store the three Google values directly as GitHub Secrets.
6. Set `ENABLE_CALENDAR_SYNC=true` only after tests and a dry run pass.
7. For email intake, set `ENABLE_EMAIL_INTAKE=true` and test one `.ics` email.
8. For AI autopilot, store `AI_API_KEY` as a secret and set `AI_PROVIDER` to
   `openai`, `anthropic`, `gemini`, or `openrouter`; set `AI_MODEL` to a current
   model ID from that provider. Never assume a chat subscription includes API usage.
9. Show the family how to say “add this schedule,” forward to the intake alias, and
   add one-off events manually.

The system imports trusted batches without per-event approval. It reports failures
afterward and never deletes calendar events automatically.
