# Security

## Reporting a vulnerability

Please do not open a public issue for a vulnerability that could expose Google OAuth
tokens, calendar contents, addresses, or family schedule data. Use GitHub's private
security-advisory reporting feature for the repository instead.

Do not include real credentials or family schedule documents in screenshots, logs,
reproduction repositories, or sample files.

## Supported version

Security fixes are applied to the latest version on the default branch.

## Credential safety

The repository-only workflow needs the narrow Google Calendar `calendar.events`
permission. The optional family email inbox additionally needs Gmail `gmail.modify`
so it can read trusted intake messages and label them after processing. Do not enable
the Gmail scope if you do not use email intake.

Store OAuth and optional AI values only in GitHub Actions Secrets or the ignored local
`.env` file. If a credential is exposed, revoke it with the provider and replace the
affected GitHub secret immediately.

## Email and AI intake

- Keep the family deployment private.
- Prefer an explicit `trusted_senders` list. `allow_any_sender = true` accepts anyone
  who discovers the intake alias and is a convenience-versus-spam choice.
- Email bodies are untrusted data. They are never executed, links are not followed,
  attachment sizes are bounded, and provider output is checked locally.
- Only event titles, dates, time zones, recurrence, and useful locations can enter an
  AI-generated event. Arbitrary response fields are discarded.
- A failed message is labeled for attention and does not block later messages.
