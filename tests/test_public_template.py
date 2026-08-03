from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PublicTemplateTests(unittest.TestCase):
    def test_default_config_targets_the_authorized_accounts_primary_calendar(
        self,
    ) -> None:
        with (ROOT / "schedule.toml").open("rb") as stream:
            settings = tomllib.load(stream)

        self.assertEqual(settings["calendar"]["id"], "primary")
        self.assertEqual(settings["calendar"]["name"], "Family Calendar")

    def test_calendar_writes_require_an_explicit_repository_variable(self) -> None:
        workflow = (ROOT / ".github/workflows/sync-calendar.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("vars.ENABLE_CALENDAR_SYNC == 'true'", workflow)
        self.assertIn(
            "GOOGLE_REFRESH_TOKEN: ${{ secrets.GOOGLE_REFRESH_TOKEN }}", workflow
        )

    def test_sensitive_local_files_are_ignored(self) -> None:
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

        self.assertIn("credentials.json", ignored)
        self.assertIn(".env", ignored)
        self.assertIn(".private/", ignored)
