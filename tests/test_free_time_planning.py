"""Tests for privacy-safe Calendar free-time planning."""

import json
import unittest
from datetime import datetime, timedelta, timezone

from goreecloud_calendar.api import FREE_SCHEMA, free_payload
from goreecloud_calendar.auth import CalendarPrincipal
from goreecloud_calendar.events import CalendarEvent
from goreecloud_calendar.http import dispatch
from goreecloud_calendar.service import CalendarService

UTC = timezone.utc


class FreeTimeApiTests(unittest.TestCase):
    def events(self):
        return (
            CalendarEvent(
                uid="private-a@example.test",
                title="Medical appointment",
                description="Sensitive details",
                location="Sensitive place",
                starts_at=datetime(2026, 8, 31, 9, 0, tzinfo=UTC),
                ends_at=datetime(2026, 8, 31, 10, 0, tzinfo=UTC),
            ),
            CalendarEvent(
                uid="private-b@example.test",
                title="Private meeting",
                starts_at=datetime(2026, 8, 31, 12, 0, tzinfo=UTC),
                ends_at=datetime(2026, 8, 31, 13, 30, tzinfo=UTC),
            ),
        )

    def test_free_payload_returns_only_qualifying_gaps(self):
        payload = free_payload(
            events=self.events(),
            starts_at=datetime(2026, 8, 31, 8, 0, tzinfo=UTC),
            ends_at=datetime(2026, 8, 31, 15, 0, tzinfo=UTC),
            minimum_minutes=90,
        )

        self.assertEqual(payload["schema"], FREE_SCHEMA)
        self.assertEqual(payload["minimum_minutes"], 90)
        self.assertEqual(payload["returned"], 2)
        self.assertEqual(
            payload["free"],
            [
                {
                    "starts_at": "2026-08-31T10:00:00+00:00",
                    "ends_at": "2026-08-31T12:00:00+00:00",
                },
                {
                    "starts_at": "2026-08-31T13:30:00+00:00",
                    "ends_at": "2026-08-31T15:00:00+00:00",
                },
            ],
        )

    def test_free_payload_redacts_event_content_and_identity(self):
        payload = free_payload(
            events=self.events(),
            starts_at=datetime(2026, 8, 31, 8, 0, tzinfo=UTC),
            ends_at=datetime(2026, 8, 31, 15, 0, tzinfo=UTC),
        )
        serialized = repr(payload)

        for private_value in (
            "Medical appointment",
            "Sensitive details",
            "Sensitive place",
            "private-a@example.test",
            "Private meeting",
        ):
            self.assertNotIn(private_value, serialized)

    def test_free_payload_uses_merged_busy_intervals(self):
        overlapping = (
            CalendarEvent(
                uid="a@example.test",
                title="A",
                starts_at=datetime(2026, 8, 31, 9, tzinfo=UTC),
                ends_at=datetime(2026, 8, 31, 11, tzinfo=UTC),
            ),
            CalendarEvent(
                uid="b@example.test",
                title="B",
                starts_at=datetime(2026, 8, 31, 10, tzinfo=UTC),
                ends_at=datetime(2026, 8, 31, 12, tzinfo=UTC),
            ),
        )
        payload = free_payload(
            events=overlapping,
            starts_at=datetime(2026, 8, 31, 8, tzinfo=UTC),
            ends_at=datetime(2026, 8, 31, 13, tzinfo=UTC),
            minimum_minutes=60,
        )

        self.assertEqual(payload["returned"], 2)
        self.assertEqual(payload["free"][0]["ends_at"], "2026-08-31T09:00:00+00:00")
        self.assertEqual(payload["free"][1]["starts_at"], "2026-08-31T12:00:00+00:00")

    def test_free_payload_rejects_invalid_minimum(self):
        for invalid in (0, 1441, True):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    free_payload(
                        events=(),
                        starts_at=datetime(2026, 8, 31, 8, tzinfo=UTC),
                        ends_at=datetime(2026, 8, 31, 9, tzinfo=UTC),
                        minimum_minutes=invalid,
                    )


class FakeStore:
    def __init__(self, events):
        self.events = list(events)

    def query_events(self, *, calendar_href, starts_at, ends_at):
        return tuple(
            event
            for event in self.events
            if event.calendar_href == calendar_href
            and event.starts_at < ends_at
            and event.ends_at > starts_at
        )

    def put_event(self, *, calendar_href, event):
        raise AssertionError("free-time planning must not write events")

    def delete_event(self, *, event_href, etag):
        raise AssertionError("free-time planning must not delete events")


class FreeTimeRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.calendar_href = "/u/reader/calendar/"
        self.anchor = datetime(2026, 8, 31, 12, tzinfo=UTC)
        self.event = CalendarEvent(
            uid="private@example.test",
            title="Private appointment",
            description="Sensitive",
            location="Sensitive location",
            starts_at=self.anchor,
            ends_at=self.anchor + timedelta(hours=1),
            calendar_href=self.calendar_href,
        )
        self.service = CalendarService(FakeStore((self.event,)))
        self.reader = CalendarPrincipal("user:reader", (self.calendar_href,), False)

    def test_dispatch_exposes_authorized_free_time_without_event_content(self):
        response = dispatch(
            service=self.service,
            principal=self.reader,
            method="GET",
            path="/api/v1/free-time",
            query={
                "calendar": self.calendar_href,
                "starts_at": (self.anchor - timedelta(hours=2)).isoformat(),
                "ends_at": (self.anchor + timedelta(hours=3)).isoformat(),
                "minimum_minutes": "60",
            },
        )

        self.assertEqual(response.status, 200)
        payload = json.loads(response.body)
        self.assertEqual(payload["schema"], FREE_SCHEMA)
        text = response.body.decode()
        self.assertNotIn("Private appointment", text)
        self.assertNotIn("Sensitive", text)
        self.assertNotIn("private@example.test", text)
        self.assertNotIn("calendar_href", text)

    def test_dispatch_defaults_minimum_to_thirty_minutes(self):
        response = dispatch(
            service=self.service,
            principal=self.reader,
            method="GET",
            path="/api/v1/free-time",
            query={
                "calendar": self.calendar_href,
                "starts_at": (self.anchor - timedelta(hours=1)).isoformat(),
                "ends_at": (self.anchor + timedelta(hours=2)).isoformat(),
            },
        )

        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.body)["minimum_minutes"], 30)

    def test_dispatch_rejects_invalid_minimum(self):
        response = dispatch(
            service=self.service,
            principal=self.reader,
            method="GET",
            path="/api/v1/free-time",
            query={
                "calendar": self.calendar_href,
                "starts_at": (self.anchor - timedelta(hours=1)).isoformat(),
                "ends_at": (self.anchor + timedelta(hours=2)).isoformat(),
                "minimum_minutes": "0",
            },
        )

        self.assertEqual(response.status, 400)
        self.assertEqual(json.loads(response.body), {"error": "invalid_request"})

    def test_dispatch_rejects_unscoped_calendar(self):
        response = dispatch(
            service=self.service,
            principal=self.reader,
            method="GET",
            path="/api/v1/free-time",
            query={
                "calendar": "/other/calendar/",
                "starts_at": (self.anchor - timedelta(hours=1)).isoformat(),
                "ends_at": (self.anchor + timedelta(hours=2)).isoformat(),
            },
        )

        self.assertEqual(response.status, 403)
        self.assertEqual(json.loads(response.body), {"error": "forbidden"})


if __name__ == "__main__":
    unittest.main()
