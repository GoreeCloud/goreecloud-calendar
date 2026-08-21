"""Calendar event-domain tests."""

import unittest
from datetime import datetime, timedelta, timezone

from goreecloud_calendar.events import CalendarEvent, CalendarEventError, busy_intervals


class CalendarEventTests(unittest.TestCase):
    def event(self, hour: int, duration: int = 1) -> CalendarEvent:
        start = datetime(2026, 8, 21, hour, tzinfo=timezone.utc)
        return CalendarEvent.new(title=f"Event {hour}", starts_at=start, ends_at=start + timedelta(hours=duration))

    def test_requires_timezone_aware_ordered_range(self):
        with self.assertRaises(CalendarEventError):
            CalendarEvent.new(
                title="Bad",
                starts_at=datetime(2026, 8, 21, 9),
                ends_at=datetime(2026, 8, 21, 10),
            )
        start = datetime(2026, 8, 21, 10, tzinfo=timezone.utc)
        with self.assertRaises(CalendarEventError):
            CalendarEvent.new(title="Bad", starts_at=start, ends_at=start)

    def test_half_open_overlap_does_not_conflict_at_boundary(self):
        first = self.event(9)
        second = self.event(10)
        third = self.event(9, 2)
        self.assertFalse(first.overlaps(second))
        self.assertTrue(first.overlaps(third))

    def test_busy_intervals_merge_overlaps_and_adjacency(self):
        intervals = busy_intervals((self.event(9, 2), self.event(10, 2), self.event(13)))
        self.assertEqual(len(intervals), 2)
        self.assertEqual(intervals[0][0].hour, 9)
        self.assertEqual(intervals[0][1].hour, 12)


if __name__ == "__main__":
    unittest.main()
