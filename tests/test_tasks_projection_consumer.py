"""Contract tests for the GoreeCloud Tasks projection consumer."""

import unittest

from goreecloud_calendar.integrations.tasks import (
    TasksProjectionError,
    parse_projection_payload,
)


class TasksProjectionConsumerTests(unittest.TestCase):
    def valid_payload(self):
        return {
            "schema": "goreecloud.tasks.calendar-projections.v1",
            "version": 1,
            "generated_at": "2026-08-20T18:00:00-05:00",
            "authorization": {
                "identity": "calendar-user",
                "scope": "scheduled tasks visible to the configured Tasks principal",
            },
            "returned": 2,
            "tasks": [
                {
                    "id": 10,
                    "title": "Personal task",
                    "due_at": "2026-08-21T09:00:00-05:00",
                    "priority": {"value": 2, "label": "P2 — High"},
                    "status": {"value": "ready", "label": "Ready"},
                    "recurrence": {"value": "daily", "label": "Daily"},
                    "project": None,
                    "updated_at": "2026-08-20T17:00:00-05:00",
                },
                {
                    "id": 11,
                    "title": "Project task",
                    "due_at": "2026-08-21T10:00:00-05:00",
                    "priority": {"value": 1, "label": "P1 — Urgent"},
                    "status": {"value": "blocked", "label": "Blocked"},
                    "recurrence": {"value": "none", "label": "Does not repeat"},
                    "project": {"id": 7, "name": "Shared Schedule"},
                    "updated_at": "2026-08-20T17:10:00-05:00",
                },
            ],
        }

    def test_valid_payload_is_normalized(self):
        tasks = parse_projection_payload(self.valid_payload())
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0].id, 10)
        self.assertEqual(tasks[0].project_id, None)
        self.assertEqual(tasks[0].recurrence_value, "daily")
        self.assertEqual(tasks[1].project_id, 7)
        self.assertEqual(tasks[1].project_name, "Shared Schedule")
        self.assertIsNotNone(tasks[0].due_at.tzinfo)

    def test_unknown_schema_or_version_fails_closed(self):
        payload = self.valid_payload()
        payload["schema"] = "unexpected.schema"
        with self.assertRaises(TasksProjectionError):
            parse_projection_payload(payload)

        payload = self.valid_payload()
        payload["version"] = 2
        with self.assertRaises(TasksProjectionError):
            parse_projection_payload(payload)

    def test_returned_count_mismatch_is_rejected(self):
        payload = self.valid_payload()
        payload["returned"] = 99
        with self.assertRaises(TasksProjectionError):
            parse_projection_payload(payload)

    def test_duplicate_task_ids_are_rejected(self):
        payload = self.valid_payload()
        payload["tasks"][1]["id"] = 10
        with self.assertRaises(TasksProjectionError):
            parse_projection_payload(payload)

    def test_naive_timestamps_are_rejected(self):
        payload = self.valid_payload()
        payload["tasks"][0]["due_at"] = "2026-08-21T09:00:00"
        with self.assertRaises(TasksProjectionError):
            parse_projection_payload(payload)

    def test_invalid_project_shape_is_rejected(self):
        payload = self.valid_payload()
        payload["tasks"][1]["project"] = {"id": 7, "name": ""}
        with self.assertRaises(TasksProjectionError):
            parse_projection_payload(payload)


if __name__ == "__main__":
    unittest.main()
