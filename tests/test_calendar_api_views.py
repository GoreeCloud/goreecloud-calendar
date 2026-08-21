"""Tests for Calendar view windows and privacy-preserving API payloads."""

import unittest
from datetime import date, datetime, timezone

from goreecloud_calendar.api import BUSY_SCHEMA, EVENT_SCHEMA, busy_payload, view_payload
from goreecloud_calendar.events import CalendarEvent
from goreecloud_calendar.views import ViewMode, build_view_window


class CalendarViewTests(unittest.TestCase):
    def test_week_starts_on_monday(self):
        window = build_view_window(
            mode=ViewMode.WEEK,
            anchor=date(2026, 8, 20),
            timezone_name="America/Chicago",
        )
        self.assertEqual(window.starts_at.date(), date(2026, 8, 17))
        self.assertEqual(window.ends_at.date(), date(2026, 8, 24))

    def test_month_includes_complete_calendar_weeks(self):
        window = build_view_window(
            mode="month", anchor=date(2026, 8, 20), timezone_name="UTC"
        )
        self.assertEqual(window.starts_at.weekday(), 0)
        self.assertEqual((window.ends_at.date()).weekday(), 0)
        self.assertLessEqual(window.starts_at.date(), date(2026, 8, 1))
        self.assertGreater(window.ends_at.date(), date(2026, 8, 31))


class CalendarApiTests(unittest.TestCase):
    def events(self):
        return (
            CalendarEvent(
                uid="a@example",
                title="Private appointment",
                starts_at=datetime(2026, 8, 20, 14, tzinfo=timezone.utc),
                ends_at=datetime(2026, 8, 20, 15, tzinfo=timezone.utc),
                description="private details",
                location="private location",
                etag='"one"',
            ),
            CalendarEvent(
                uid="b@example",
                title="Second appointment",
                starts_at=datetime(2026, 8, 20, 14, 30, tzinfo=timezone.utc),
                ends_at=datetime(2026, 8, 20, 16, tzinfo=timezone.utc),
            ),
        )

    def test_view_payload_is_versioned(self):
        payload = view_payload(
            events=self.events(), mode="day", anchor=date(2026, 8, 20), timezone_name="UTC"
        )
        self.assertEqual(payload["schema"], EVENT_SCHEMA)
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["returned"], 2)
        self.assertEqual(payload["events"][0]["title"], "Private appointment")

    def test_busy_payload_merges_and_redacts_event_content(self):
        payload = busy_payload(
            events=self.events(),
            starts_at=datetime(2026, 8, 20, 13, tzinfo=timezone.utc),
            ends_at=datetime(2026, 8, 20, 17, tzinfo=timezone.utc),
        )
        self.assertEqual(payload["schema"], BUSY_SCHEMA)
        self.assertEqual(payload["returned"], 1)
        self.assertEqual(
            payload["busy"][0],
            {
                "starts_at": "2026-08-20T14:00:00+00:00",
                "ends_at": "2026-08-20T16:00:00+00:00",
            },
        )
        serialized = repr(payload)
        self.assertNotIn("Private appointment", serialized)
        self.assertNotIn("private details", serialized)
        self.assertNotIn("private location", serialized)


if __name__ == "__main__":
    unittest.main()
