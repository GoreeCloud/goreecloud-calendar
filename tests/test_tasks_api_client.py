"""HTTP-contract tests for Calendar's first-party GoreeCloud Tasks client."""

import json
import unittest
from datetime import datetime, timedelta, timezone
from io import BytesIO
from urllib.error import HTTPError
from unittest.mock import patch

from goreecloud_calendar.integrations.tasks import (
    TasksConflictError,
    TasksProjectionError,
    create_task,
    fetch_task_projection,
    fetch_task_projections,
    parse_single_projection_payload,
    reschedule_task,
)


TOKEN = "calendar-client-test-token-0123456789abcdef0123456789abcdef"
BASE_URL = "https://tasks.example.test"


class FakeResponse:
    def __init__(self, payload):
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self, amount=-1):
        if amount is None or amount < 0:
            return self.body
        return self.body[:amount]


def task_payload(task_id=10, *, title="Scheduled task"):
    return {
        "source": {
            "application": "goreecloud-tasks",
            "api_version": 1,
        },
        "id": task_id,
        "authoritative_url": f"https://tasks.example.test/tasks/{task_id}/",
        "title": title,
        "due_at": "2026-09-04T09:00:00+00:00",
        "priority": {"value": 2, "label": "P2 — High"},
        "status": {"value": "ready", "label": "Ready"},
        "recurrence": {"value": "none", "label": "Does not repeat"},
        "project": {"id": 7, "name": "Shared Schedule"},
        "revision": "2026-09-03T02:30:00+00:00",
        "updated_at": "2026-09-03T02:30:00+00:00",
    }


def single_payload(task_id=10, *, title="Scheduled task"):
    return {
        "schema": "goreecloud.tasks.calendar-projections.v1",
        "version": 1,
        "task": task_payload(task_id, title=title),
    }


class TasksAPIClientTests(unittest.TestCase):
    def test_extended_single_projection_is_strictly_normalized(self):
        task = parse_single_projection_payload(single_payload())
        self.assertEqual(task.id, 10)
        self.assertEqual(task.source_application, "goreecloud-tasks")
        self.assertEqual(task.source_api_version, 1)
        self.assertEqual(
            task.authoritative_url,
            "https://tasks.example.test/tasks/10/",
        )
        self.assertEqual(task.revision, task.updated_at)

    def test_single_projection_rejects_missing_source_metadata(self):
        payload = single_payload()
        del payload["task"]["source"]
        with self.assertRaises(TasksProjectionError):
            parse_single_projection_payload(payload)

    def test_single_projection_rejects_revision_mismatch(self):
        payload = single_payload()
        payload["task"]["revision"] = "2026-09-03T02:31:00+00:00"
        with self.assertRaises(TasksProjectionError):
            parse_single_projection_payload(payload)

    @patch("goreecloud_calendar.integrations.tasks.urlopen")
    def test_projection_list_sends_bounded_window_and_bearer_header(self, mocked_urlopen):
        start = datetime(2026, 9, 4, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(days=7)
        mocked_urlopen.return_value = FakeResponse(
            {
                "schema": "goreecloud.tasks.calendar-projections.v1",
                "version": 1,
                "returned": 1,
                "tasks": [task_payload()],
            }
        )

        tasks = fetch_task_projections(
            base_url=BASE_URL,
            token=TOKEN,
            start=start,
            end=end,
        )
        self.assertEqual(len(tasks), 1)

        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertIn("/api/v1/calendar/task-projections/?", request.full_url)
        self.assertIn("start=", request.full_url)
        self.assertIn("end=", request.full_url)
        self.assertEqual(request.get_header("Authorization"), f"Bearer {TOKEN}")

    def test_projection_list_rejects_unbounded_or_naive_windows_before_network(self):
        start = datetime(2026, 9, 4, 0, 0, tzinfo=timezone.utc)
        with self.assertRaises(TasksProjectionError):
            fetch_task_projections(
                base_url=BASE_URL,
                token=TOKEN,
                start=start,
            )
        with self.assertRaises(TasksProjectionError):
            fetch_task_projections(
                base_url=BASE_URL,
                token=TOKEN,
                start=start.replace(tzinfo=None),
                end=(start + timedelta(days=1)).replace(tzinfo=None),
            )
        with self.assertRaises(TasksProjectionError):
            fetch_task_projections(
                base_url=BASE_URL,
                token=TOKEN,
                start=start,
                end=start + timedelta(days=94),
            )

    @patch("goreecloud_calendar.integrations.tasks.urlopen")
    def test_fetch_one_uses_stable_projection_path(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeResponse(single_payload(22))
        task = fetch_task_projection(
            base_url=BASE_URL,
            token=TOKEN,
            task_id=22,
        )
        self.assertEqual(task.id, 22)
        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            BASE_URL + "/api/v1/calendar/task-projections/22/",
        )

    @patch("goreecloud_calendar.integrations.tasks.urlopen")
    def test_create_task_sends_only_supported_fields(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeResponse(
            single_payload(30, title="Created from Calendar")
        )
        due_at = datetime(2026, 9, 5, 11, 30, tzinfo=timezone.utc)
        task = create_task(
            base_url=BASE_URL,
            token=TOKEN,
            title=" Created from Calendar ",
            due_at=due_at,
            priority=1,
            project_id=7,
        )
        self.assertEqual(task.id, 30)

        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(
            request.full_url,
            BASE_URL + "/api/v1/calendar/tasks/",
        )
        self.assertEqual(request.get_header("Content-type"), "application/json")
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(
            body,
            {
                "title": "Created from Calendar",
                "due_at": due_at.isoformat(),
                "project_id": 7,
                "priority": 1,
            },
        )
        self.assertNotIn("description", body)
        self.assertNotIn("assignee", body)
        self.assertNotIn("recurrence", body)

    def test_create_task_rejects_invalid_client_input_before_network(self):
        due_at = datetime(2026, 9, 5, 11, 30, tzinfo=timezone.utc)
        invalid_cases = [
            {"title": "", "due_at": due_at},
            {"title": "x" * 501, "due_at": due_at},
            {"title": "Task", "due_at": due_at.replace(tzinfo=None)},
            {"title": "Task", "due_at": due_at, "priority": 9},
            {"title": "Task", "due_at": due_at, "project_id": 0},
        ]
        for kwargs in invalid_cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(TasksProjectionError):
                    create_task(base_url=BASE_URL, token=TOKEN, **kwargs)

    @patch("goreecloud_calendar.integrations.tasks.urlopen")
    def test_reschedule_sends_due_time_and_expected_revision(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeResponse(single_payload())
        due_at = datetime(2026, 9, 6, 14, 0, tzinfo=timezone.utc)
        revision = datetime(2026, 9, 3, 2, 30, tzinfo=timezone.utc)

        reschedule_task(
            base_url=BASE_URL,
            token=TOKEN,
            task_id=10,
            due_at=due_at,
            expected_updated_at=revision,
        )
        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            BASE_URL + "/api/v1/calendar/tasks/10/reschedule/",
        )
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(
            body,
            {
                "due_at": due_at.isoformat(),
                "expected_updated_at": revision.isoformat(),
            },
        )

    @patch("goreecloud_calendar.integrations.tasks.urlopen")
    def test_reschedule_exposes_409_as_typed_conflict_without_raw_body(self, mocked_urlopen):
        body = json.dumps(
            {
                "detail": "Task revision conflict.",
                "current_revision": "2026-09-03T02:45:00+00:00",
            }
        ).encode("utf-8")
        mocked_urlopen.side_effect = HTTPError(
            BASE_URL + "/api/v1/calendar/tasks/10/reschedule/",
            409,
            "Conflict",
            hdrs=None,
            fp=BytesIO(body),
        )

        with self.assertRaises(TasksConflictError) as captured:
            reschedule_task(
                base_url=BASE_URL,
                token=TOKEN,
                task_id=10,
                due_at=datetime(2026, 9, 6, 14, 0, tzinfo=timezone.utc),
                expected_updated_at=datetime(
                    2026, 9, 3, 2, 30, tzinfo=timezone.utc
                ),
            )

        self.assertEqual(
            captured.exception.current_revision,
            datetime(2026, 9, 3, 2, 45, tzinfo=timezone.utc),
        )
        self.assertNotIn("Task revision conflict", str(captured.exception))

    @patch("goreecloud_calendar.integrations.tasks.urlopen")
    def test_non_conflict_http_failures_remain_low_detail(self, mocked_urlopen):
        mocked_urlopen.side_effect = HTTPError(
            BASE_URL + "/api/v1/calendar/task-projections/",
            403,
            "Forbidden with upstream detail",
            hdrs=None,
            fp=BytesIO(b'{"detail":"private upstream detail"}'),
        )
        with self.assertRaises(TasksProjectionError) as captured:
            fetch_task_projections(base_url=BASE_URL, token=TOKEN)
        self.assertIn("HTTP 403", str(captured.exception))
        self.assertNotIn("private upstream detail", str(captured.exception))


if __name__ == "__main__":
    unittest.main()
