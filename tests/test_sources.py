from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from family_schedule.sources import (
    MAX_SOURCE_BYTES,
    calendars_from_source,
    decode_ical_bytes,
)


class SourceTests(unittest.TestCase):
    def test_decodes_legacy_latin1_calendar_feeds(self) -> None:
        data = "SUMMARY:Renée".encode("latin-1")

        self.assertEqual(decode_ical_bytes(data, None), "SUMMARY:Renée")

    def test_rejects_oversized_local_sources_before_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oversized.ics"
            with path.open("wb") as stream:
                stream.seek(MAX_SOURCE_BYTES)
                stream.write(b"x")

            with self.assertRaisesRegex(RuntimeError, "size limit"):
                calendars_from_source(path, {"anprod.active.com"})
