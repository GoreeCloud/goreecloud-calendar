"""Security regression tests for the Calendar-to-Tasks busy API token file."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from goreecloud_calendar.integrations.tasks_busy_api import (
    MAX_TOKEN_FILE_BYTES,
    load_tasks_busy_api_configuration,
)


TOKEN = "calendar-tasks-busy-test-token-0123456789abcdef0123456789abcdef"


class TasksBusyTokenFileHardeningTests(unittest.TestCase):
    def base_environment(self, token_path: Path) -> dict[str, str]:
        return {
            "CALENDAR_TASKS_BUSY_API_ENABLED": "true",
            "CALENDAR_TASKS_BUSY_API_TOKEN": "",
            "CALENDAR_TASKS_BUSY_API_TOKEN_FILE": str(token_path),
            "CALENDAR_TASKS_BUSY_API_SUBJECT": "alice",
            "CALENDAR_TASKS_BUSY_API_CALENDAR_HREFS": "/calendars/alice/personal/",
            "CALENDAR_TASKS_BUSY_API_MAX_WINDOW_MINUTES": str(31 * 24 * 60),
        }

    def test_protected_regular_token_file_remains_supported(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            token_path = Path(temporary_directory) / "token"
            token_path.write_text(TOKEN + "\n", encoding="utf-8")
            os.chmod(token_path, 0o600)

            config = load_tasks_busy_api_configuration(self.base_environment(token_path))

        self.assertIsNone(config.error)
        self.assertEqual(config.token, TOKEN)

    def test_symbolic_link_token_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            target_path = Path(temporary_directory) / "target"
            target_path.write_text(TOKEN, encoding="utf-8")
            os.chmod(target_path, 0o600)
            token_path = Path(temporary_directory) / "token-link"
            token_path.symlink_to(target_path)

            config = load_tasks_busy_api_configuration(self.base_environment(token_path))

        self.assertIsNotNone(config.error)
        self.assertIn("symbolic link", config.error)
        self.assertEqual(config.token, "")

    def test_replaced_token_file_between_lstat_and_open_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            token_path = Path(temporary_directory) / "token"
            token_path.write_text(TOKEN, encoding="utf-8")
            os.chmod(token_path, 0o600)
            replacement_path = Path(temporary_directory) / "replacement"
            replacement_path.write_text("r" * len(TOKEN), encoding="utf-8")
            os.chmod(replacement_path, 0o600)
            real_open = os.open

            def replace_then_open(path, flags):
                os.replace(replacement_path, token_path)
                return real_open(path, flags)

            with mock.patch(
                "goreecloud_calendar.integrations.tasks_busy_api.os.open",
                side_effect=replace_then_open,
            ):
                config = load_tasks_busy_api_configuration(self.base_environment(token_path))

        self.assertIsNotNone(config.error)
        self.assertIn("changed while being opened", config.error)
        self.assertEqual(config.token, "")

    def test_oversized_token_file_fails_closed_before_token_use(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            token_path = Path(temporary_directory) / "token"
            token_path.write_bytes(b"x" * (MAX_TOKEN_FILE_BYTES + 1))
            os.chmod(token_path, 0o600)

            config = load_tasks_busy_api_configuration(self.base_environment(token_path))

        self.assertIsNotNone(config.error)
        self.assertIn("too large", config.error)
        self.assertEqual(config.token, "")

    def test_non_utf8_token_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            token_path = Path(temporary_directory) / "token"
            token_path.write_bytes(b"\xff" * 64)
            os.chmod(token_path, 0o600)

            config = load_tasks_busy_api_configuration(self.base_environment(token_path))

        self.assertIsNotNone(config.error)
        self.assertIn("UTF-8", config.error)
        self.assertEqual(config.token, "")


if __name__ == "__main__":
    unittest.main()
