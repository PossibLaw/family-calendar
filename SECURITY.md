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

Family Calendar needs the narrow Google Calendar `calendar.events` permission. Store
OAuth values only in GitHub Actions Secrets or the ignored local `.env` file. If a
credential is exposed, revoke the application's access in the Google Account and
replace the affected GitHub secrets immediately.
