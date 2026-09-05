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
        self.assertGreater(settings["calendar"]["reminder_minutes"], 0)

    def test_shipped_intake_config_is_closed_to_untrusted_senders(self) -> None:
        # The sender list is the whole trust boundary once intake uses the plain
        # account address, so the template must not ship it open.
        with (ROOT / "schedule.toml").open("rb") as stream:
            intake = tomllib.load(stream)["intake"]

        self.assertFalse(intake["allow_any_sender"])
        self.assertTrue(intake["trusted_senders"])

    def test_repository_ships_no_household_schedules(self) -> None:
        # Real schedules name children, teachers and home addresses. The
        # template carries an example instead, and inbox/ starts empty.
        self.assertEqual(
            sorted(p.name for p in (ROOT / "inbox").iterdir()), [".gitkeep"]
        )

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


class ChangedSinceTests(unittest.TestCase):
    def test_sync_workflow_fetches_history_changed_since_can_diff(self) -> None:
        workflow = (ROOT / ".github/workflows/sync-calendar.yml").read_text(
            encoding="utf-8"
        )

        # fetch-depth 2 does not contain github.event.before after a rebase merge,
        # which silently escalated an ordinary push to a full reconciliation.
        self.assertIn("fetch-depth: 0", workflow)
        self.assertNotIn("fetch-depth: 2", workflow)

    def test_unresolvable_revision_refuses_instead_of_reconciling_everything(
        self,
    ) -> None:
        import sys

        sys.path.insert(0, str(ROOT / "src"))
        from family_schedule.cli import _changed_source_paths

        with self.assertRaises(RuntimeError) as caught:
            _changed_source_paths("0" * 40, ROOT / "inbox")

        self.assertIn("full reconciliation", str(caught.exception))


class ReconcileGuardTests(unittest.TestCase):
    def test_manual_reconciliation_caps_how_many_events_it_may_add(self) -> None:
        workflow = (ROOT / ".github/workflows/sync-calendar.yml").read_text(
            encoding="utf-8"
        )

        # A first full reconcile against a populated calendar once added 69 events
        # with no warning; it must refuse rather than bulk-create silently.
        self.assertIn("sync --max-new", workflow)
