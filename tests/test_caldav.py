"""CalDAV foundation tests that require no network access."""

import unittest
from datetime import datetime, timezone

from goreecloud_calendar.events import CalendarEvent
from goreecloud_calendar.integrations.caldav import CalDAVClient, CalDAVError, serialize_event


class CalDAVFoundationTests(unittest.TestCase):
    def test_client_requires_https_and_separate_credentials(self):
        with self.assertRaises(CalDAVError):
            CalDAVClient(base_url="http://dav.goreecloud.com", username="u", password="p")
        with self.assertRaises(CalDAVError):
            CalDAVClient(base_url="https://u:p@dav.goreecloud.com", username="u", password="p")

    def test_event_serialization_is_utc_and_escapes_text(self):
        event = CalendarEvent(
            uid="example@goreecloud.com",
            title="Planning, family; work",
            starts_at=datetime(2026, 8, 21, 9, tzinfo=timezone.utc),
            ends_at=datetime(2026, 8, 21, 10, tzinfo=timezone.utc),
            description="Line one\nLine two",
            location="Home; Office",
        )
        payload = serialize_event(event)
        self.assertIn("DTSTART:20260821T090000Z", payload)
        self.assertIn("SUMMARY:Planning\\, family\\; work", payload)
        self.assertIn("DESCRIPTION:Line one\\nLine two", payload)
        self.assertIn("LOCATION:Home\\; Office", payload)
        self.assertTrue(payload.endswith("\r\n"))

    def test_negative_sequence_is_rejected(self):
        event = CalendarEvent.new(
            title="Meeting",
            starts_at=datetime(2026, 8, 21, 9, tzinfo=timezone.utc),
            ends_at=datetime(2026, 8, 21, 10, tzinfo=timezone.utc),
        )
        with self.assertRaises(CalDAVError):
            serialize_event(event, sequence=-1)


if __name__ == "__main__":
    unittest.main()
