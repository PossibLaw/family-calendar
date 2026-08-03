# Contributing

Thank you for helping improve Family Calendar.

## Privacy first

Never commit a real family schedule, calendar ID, address, email address, OAuth file,
or token. Use fictional data in tests and examples.

## Development

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

For changed behavior, add or update a test first. Pull requests should explain the
happy path, an edge case, and the failure or security case that was checked.

Provider integrations must validate remote hosts before downloading, use HTTPS,
limit response sizes, and fail before calendar writes when input is ambiguous.
