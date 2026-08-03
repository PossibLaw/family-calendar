from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from family_schedule.auth import (
    CALENDAR_EVENTS_SCOPE,
    GMAIL_MODIFY_SCOPE,
    oauth_scopes,
    write_env_file,
)
from family_schedule.google_calendar import GoogleCredentials


class AuthorizationTests(unittest.TestCase):
    def test_email_intake_authorization_adds_gmail_without_expanding_calendar_only(
        self,
    ) -> None:
        self.assertEqual(oauth_scopes(with_gmail=False), [CALENDAR_EVENTS_SCOPE])
        self.assertEqual(
            oauth_scopes(with_gmail=True),
            [CALENDAR_EVENTS_SCOPE, GMAIL_MODIFY_SCOPE],
        )

    def test_writes_only_required_oauth_values_to_private_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"

            write_env_file(
                path,
                client_id="client-id",
                client_secret="client-secret",
                refresh_token="refresh-token",
            )

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "GOOGLE_CLIENT_ID=client-id\n"
                "GOOGLE_CLIENT_SECRET=client-secret\n"
                "GOOGLE_REFRESH_TOKEN=refresh-token\n",
            )
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_google_credentials_can_load_the_local_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "GOOGLE_CLIENT_ID=client-id\n"
                "GOOGLE_CLIENT_SECRET=client-secret\n"
                "GOOGLE_REFRESH_TOKEN=refresh-token\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                credentials = GoogleCredentials.from_environment(path)

            self.assertEqual(credentials.client_id, "client-id")
            self.assertEqual(credentials.client_secret, "client-secret")
            self.assertEqual(credentials.refresh_token, "refresh-token")
