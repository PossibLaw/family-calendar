from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PublicTemplateTests(unittest.TestCase):
    def test_calendar_config_contains_required_values(self) -> None:
        with (ROOT / "schedule.toml").open("rb") as stream:
            settings = tomllib.load(stream)

        self.assertTrue(settings["calendar"]["id"])
        self.assertTrue(settings["calendar"]["name"])
        self.assertGreater(settings["calendar"]["reminder_minutes"], 0)

    def test_calendar_writes_require_an_explicit_repository_variable(self) -> None:
        workflow = (ROOT / ".github/workflows/sync-calendar.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("vars.ENABLE_CALENDAR_SYNC == 'true'", workflow)
        self.assertIn(
            "GOOGLE_REFRESH_TOKEN: ${{ secrets.GOOGLE_REFRESH_TOKEN }}", workflow
        )
        self.assertIn("--changed-since", workflow)
        self.assertIn("github.event.before", workflow)
        self.assertIn("queue: max", workflow)

    def test_email_intake_is_scheduled_but_requires_explicit_enablement(self) -> None:
        workflow = (ROOT / ".github/workflows/process-inbox.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("schedule:", workflow)
        self.assertIn("vars.ENABLE_EMAIL_INTAKE == 'true'", workflow)
        self.assertIn("secrets.AI_API_KEY", workflow)
        self.assertIn("queue: max", workflow)

    def test_sensitive_local_files_are_ignored(self) -> None:
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

        self.assertIn("credentials.json", ignored)
        self.assertIn(".env", ignored)
        self.assertIn(".private/", ignored)
