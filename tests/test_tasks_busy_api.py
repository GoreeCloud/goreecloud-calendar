"""Contract tests for the read-only Calendar busy-time API exposed to Tasks."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from goreecloud_calendar.events import CalendarEvent
from goreecloud_calendar.integrations.tasks_busy_api import (
    SCHEMA,
    TasksBusyAPIConfiguration,
    dispatch_tasks_busy_time,
    load_tasks_busy_api_configuration,
)
from goreecloud_calendar.service import CalendarService


TOKEN = "calendar-tasks-busy-test-token-0123456789abcdef0123456789abcdef"


class InMemoryCalendarStore:
    def __init__(self) -> None:
        self.queries: list[tuple[str, datetime, datetime]] = []
        self.events = {
            "/calendars/alice/personal/": (
                CalendarEvent(
                    uid="personal-private",
                    title="Private medical appointment",
                    starts_at=datetime(2026, 9, 4, 14, 0, tzinfo=timezone.utc),
                    ends_at=datetime(2026, 9, 4, 15, 0, tzinfo=timezone.utc),
                    description="private diagnosis detail",
                    location="private clinic",
                ),
            ),
            "/calendars/alice/work/": (
                CalendarEvent(
                    uid="work-private",
                    title="Private work meeting",
                    starts_at=datetime(2026, 9, 4, 14, 30, tzinfo=timezone.utc),
                    ends_at=datetime(2026, 9, 4, 16, 0, tzinfo=timezone.utc),
                    description="private work detail",
                    location="private office",
                ),
            ),
            "/calendars/bob/private/": (
                CalendarEvent(
                    uid="bob-private",
                    title="Bob secret event",
                    starts_at=datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc),
                    ends_at=datetime(2026, 9, 4, 13, 0, tzinfo=timezone.utc),
                ),
            ),
        }

    def query_events(self, *, calendar_href, starts_at, ends_at):
        self.queries.append((calendar_href, starts_at, ends_at))
        return tuple(
            event
            for event in self.events.get(calendar_href, ())
            if event.starts_at < ends_at and starts_at < event.ends_at
        )

    def put_event(self, *, calendar_href, event):  # pragma: no cover - read-only test store
        raise AssertionError("busy API must not write events")

    def delete_event(self, *, event_href, etag):  # pragma: no cover - read-only test store
        raise AssertionError("busy API must not delete events")


class TasksBusyAPIContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = InMemoryCalendarStore()
        self.service = CalendarService(self.store)
        self.config = TasksBusyAPIConfiguration(
            enabled=True,
            token=TOKEN,
            subject="alice",
            calendar_hrefs=(
                "/calendars/alice/personal/",
                "/calendars/alice/work/",
            ),
            max_window_minutes=31 * 24 * 60,
        )
        self.query = {
            "starts_at": "2026-09-04T10:00:00+00:00",
            "ends_at": "2026-09-04T18:00:00+00:00",
        }
        self.headers = {"Authorization": f"Bearer {TOKEN}"}

    @staticmethod
    def payload(response):
        return json.loads(response.body.decode("utf-8"))

    @staticmethod
    def headers_dict(response):
        return dict(response.headers)

    def test_disabled_api_is_hidden(self):
        response = dispatch_tasks_busy_time(
            service=self.service,
            config=TasksBusyAPIConfiguration(enabled=False),
            method="GET",
            headers=self.headers,
            query=self.query,
        )
        self.assertEqual(response.status, 404)
        self.assertEqual(self.payload(response), {"error": "not_found"})
        self.assertEqual(self.store.queries, [])

    def test_invalid_enabled_configuration_fails_closed(self):
        response = dispatch_tasks_busy_time(
            service=self.service,
            config=TasksBusyAPIConfiguration(
                enabled=True,
                error="test configuration error that must not be exposed",
            ),
            method="GET",
            headers=self.headers,
            query=self.query,
        )
        self.assertEqual(response.status, 503)
        self.assertEqual(self.payload(response), {"error": "integration_unavailable"})
        self.assertNotIn("test configuration", response.body.decode("utf-8"))
        self.assertEqual(self.store.queries, [])

    def test_missing_or_wrong_bearer_token_is_rejected_before_query_validation(self):
        missing = dispatch_tasks_busy_time(
            service=self.service,
            config=self.config,
            method="GET",
            headers={},
            query={"calendar": "/calendars/bob/private/"},
        )
        wrong = dispatch_tasks_busy_time(
            service=self.service,
            config=self.config,
            method="GET",
            headers={"authorization": "Bearer not-the-token"},
            query=self.query,
        )
        self.assertEqual(missing.status, 401)
        self.assertEqual(wrong.status, 401)
        self.assertEqual(
            self.headers_dict(missing)["WWW-Authenticate"],
            "Bearer",
        )
        self.assertEqual(self.store.queries, [])

    def test_busy_projection_merges_authorized_collections_and_redacts_content(self):
        response = dispatch_tasks_busy_time(
            service=self.service,
            config=self.config,
            method="GET",
            headers=self.headers,
            query=self.query,
            now=datetime(2026, 9, 3, 4, 55, tzinfo=timezone.utc),
        )
        self.assertEqual(response.status, 200)
        payload = self.payload(response)
        self.assertEqual(payload["schema"], SCHEMA)
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["generated_at"], "2026-09-03T04:55:00+00:00")
        self.assertEqual(payload["returned"], 1)
        self.assertEqual(
            payload["busy"],
            [
                {
                    "starts_at": "2026-09-04T14:00:00+00:00",
                    "ends_at": "2026-09-04T16:00:00+00:00",
                }
            ],
        )
        serialized = json.dumps(payload)
        for forbidden in (
            "alice",
            "personal",
            "work",
            "Private medical appointment",
            "private diagnosis detail",
            "private clinic",
            "Private work meeting",
            "private work detail",
            "private office",
            "Bob secret event",
            "uid",
            "title",
            "description",
            "location",
        ):
            self.assertNotIn(forbidden, serialized)

        self.assertEqual(
            [query[0] for query in self.store.queries],
            [
                "/calendars/alice/personal/",
                "/calendars/alice/work/",
            ],
        )
        response_headers = self.headers_dict(response)
        self.assertEqual(response_headers["Cache-Control"], "private, no-store")
        self.assertEqual(response_headers["Vary"], "Authorization")

    def test_request_cannot_select_another_subject_or_calendar(self):
        for extra_field, value in (
            ("calendar", "/calendars/bob/private/"),
            ("calendar_href", "/calendars/bob/private/"),
            ("subject", "bob"),
            ("user", "bob"),
        ):
            with self.subTest(extra_field=extra_field):
                query = dict(self.query)
                query[extra_field] = value
                response = dispatch_tasks_busy_time(
                    service=self.service,
                    config=self.config,
                    method="GET",
                    headers=self.headers,
                    query=query,
                )
                self.assertEqual(response.status, 400)
        self.assertEqual(self.store.queries, [])

    def test_window_must_be_timezone_aware_positive_and_bounded(self):
        invalid_queries = (
            {
                "starts_at": "2026-09-04T10:00:00",
                "ends_at": "2026-09-04T18:00:00+00:00",
            },
            {
                "starts_at": "2026-09-04T18:00:00+00:00",
                "ends_at": "2026-09-04T10:00:00+00:00",
            },
            {
                "starts_at": "2026-09-04T10:00:00+00:00",
                "ends_at": "2026-10-06T10:00:01+00:00",
            },
            {"starts_at": "not-a-time", "ends_at": "still-not-a-time"},
            {"starts_at": "2026-09-04T10:00:00+00:00"},
        )
        for query in invalid_queries:
            with self.subTest(query=query):
                response = dispatch_tasks_busy_time(
                    service=self.service,
                    config=self.config,
                    method="GET",
                    headers=self.headers,
                    query=query,
                )
                self.assertEqual(response.status, 400)
        self.assertEqual(self.store.queries, [])

    def test_api_is_get_only(self):
        response = dispatch_tasks_busy_time(
            service=self.service,
            config=self.config,
            method="POST",
            headers=self.headers,
            query=self.query,
        )
        self.assertEqual(response.status, 405)
        self.assertEqual(self.headers_dict(response)["Allow"], "GET")
        self.assertEqual(self.store.queries, [])

    def test_now_must_be_timezone_aware(self):
        with self.assertRaises(ValueError):
            dispatch_tasks_busy_time(
                service=self.service,
                config=self.config,
                method="GET",
                headers=self.headers,
                query=self.query,
                now=datetime(2026, 9, 3, 4, 55),
            )


class TasksBusyAPIConfigurationTests(unittest.TestCase):
    def base_environment(self):
        return {
            "CALENDAR_TASKS_BUSY_API_ENABLED": "true",
            "CALENDAR_TASKS_BUSY_API_TOKEN": TOKEN,
            "CALENDAR_TASKS_BUSY_API_TOKEN_FILE": "",
            "CALENDAR_TASKS_BUSY_API_SUBJECT": "alice",
            "CALENDAR_TASKS_BUSY_API_CALENDAR_HREFS": (
                "/calendars/alice/personal/,/calendars/alice/work/"
            ),
            "CALENDAR_TASKS_BUSY_API_MAX_WINDOW_MINUTES": str(31 * 24 * 60),
        }

    def test_disabled_configuration_requires_no_secret_or_scope(self):
        config = load_tasks_busy_api_configuration(
            {"CALENDAR_TASKS_BUSY_API_ENABLED": "false"}
        )
        self.assertFalse(config.enabled)
        self.assertIsNone(config.error)

    def test_valid_direct_configuration_is_normalized(self):
        config = load_tasks_busy_api_configuration(self.base_environment())
        self.assertTrue(config.enabled)
        self.assertIsNone(config.error)
        self.assertEqual(config.subject, "alice")
        self.assertEqual(
            config.calendar_hrefs,
            ("/calendars/alice/personal/", "/calendars/alice/work/"),
        )
        self.assertEqual(config.max_window_minutes, 31 * 24 * 60)

    def test_invalid_scope_and_secret_configuration_fails_closed(self):
        environment = self.base_environment()
        environment.update(
            {
                "CALENDAR_TASKS_BUSY_API_TOKEN": "short",
                "CALENDAR_TASKS_BUSY_API_SUBJECT": "",
                "CALENDAR_TASKS_BUSY_API_CALENDAR_HREFS": (
                    "/calendars/alice/personal/,../escape"
                ),
                "CALENDAR_TASKS_BUSY_API_MAX_WINDOW_MINUTES": "999999",
            }
        )
        config = load_tasks_busy_api_configuration(environment)
        self.assertTrue(config.enabled)
        self.assertIsNotNone(config.error)
        self.assertNotIn("short", config.error)

    def test_token_sources_are_mutually_exclusive(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            token_path = Path(temporary_directory) / "token"
            token_path.write_text(TOKEN, encoding="utf-8")
            os.chmod(token_path, 0o600)
            environment = self.base_environment()
            environment["CALENDAR_TASKS_BUSY_API_TOKEN_FILE"] = str(token_path)
            config = load_tasks_busy_api_configuration(environment)
        self.assertIsNotNone(config.error)
        self.assertIn("only one", config.error)

    def test_protected_token_file_is_supported(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            token_path = Path(temporary_directory) / "token"
            token_path.write_text(TOKEN + "\n", encoding="utf-8")
            os.chmod(token_path, 0o600)
            environment = self.base_environment()
            environment["CALENDAR_TASKS_BUSY_API_TOKEN"] = ""
            environment["CALENDAR_TASKS_BUSY_API_TOKEN_FILE"] = str(token_path)
            config = load_tasks_busy_api_configuration(environment)
        self.assertIsNone(config.error)
        self.assertEqual(config.token, TOKEN)

    def test_overbroad_token_file_permissions_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            token_path = Path(temporary_directory) / "token"
            token_path.write_text(TOKEN, encoding="utf-8")
            os.chmod(token_path, 0o640)
            environment = self.base_environment()
            environment["CALENDAR_TASKS_BUSY_API_TOKEN"] = ""
            environment["CALENDAR_TASKS_BUSY_API_TOKEN_FILE"] = str(token_path)
            config = load_tasks_busy_api_configuration(environment)
        self.assertIsNotNone(config.error)
        self.assertIn("permissions", config.error)


if __name__ == "__main__":
    unittest.main()
