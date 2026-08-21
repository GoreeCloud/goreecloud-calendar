"""Tests for fail-closed CalDAV query parsing."""

import unittest
from datetime import datetime, timezone

from goreecloud_calendar.events import CalendarEvent
from goreecloud_calendar.integrations.caldav import CalDAVError, parse_event, serialize_event


class CalDAVParserTests(unittest.TestCase):
    def event(self):
        return CalendarEvent(
            uid="event-1@calendar.goreecloud.com",
            title="Family, planning; session",
            starts_at=datetime(2026, 8, 21, 1, tzinfo=timezone.utc),
            ends_at=datetime(2026, 8, 21, 2, tzinfo=timezone.utc),
            description="Line one\nLine two",
            location="Home; Office",
        )

    def test_calendar_serialization_round_trips_supported_fields(self):
        original = self.event()
        parsed = parse_event(serialize_event(original), calendar_href="/calendar/", etag='"abc"')
        self.assertEqual(parsed.uid, original.uid)
        self.assertEqual(parsed.title, original.title)
        self.assertEqual(parsed.starts_at, original.starts_at)
        self.assertEqual(parsed.ends_at, original.ends_at)
        self.assertEqual(parsed.description, original.description)
        self.assertEqual(parsed.location, original.location)
        self.assertEqual(parsed.calendar_href, "/calendar/")
        self.assertEqual(parsed.etag, '"abc"')

    def test_non_utc_initial_parser_input_fails_closed(self):
        payload = serialize_event(self.event()).replace("DTSTART:20260821T010000Z", "DTSTART:20260821T010000")
        with self.assertRaises(CalDAVError):
            parse_event(payload)

    def test_missing_uid_fails_closed(self):
        payload = serialize_event(self.event()).replace("UID:event-1@calendar.goreecloud.com\r\n", "")
        with self.assertRaises(CalDAVError):
            parse_event(payload)


if __name__ == "__main__":
    unittest.main()
