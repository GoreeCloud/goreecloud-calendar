"""Tests for the authenticated Calendar runtime boundary."""

import json
import unittest
from datetime import datetime, timedelta, timezone

from goreecloud_calendar.auth import CalendarPrincipal
from goreecloud_calendar.events import CalendarEvent
from goreecloud_calendar.http import dispatch
from goreecloud_calendar.service import CalendarService

UTC = timezone.utc


class FakeStore:
    def __init__(self):
        self.events = []
        self.deleted = []

    def query_events(self, *, calendar_href, starts_at, ends_at):
        return tuple(
            event for event in self.events
            if event.calendar_href == calendar_href
            and event.starts_at < ends_at and event.ends_at > starts_at
        )

    def put_event(self, *, calendar_href, event):
        saved = CalendarEvent(
            uid=event.uid,
            title=event.title,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
            description=event.description,
            location=event.location,
            all_day=event.all_day,
            calendar_href=calendar_href,
            etag='"v1"',
        )
        self.events.append(saved)
        return saved

    def delete_event(self, *, event_href, etag):
        self.deleted.append((event_href, etag))


class RuntimeServiceTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeStore()
        self.service = CalendarService(self.store)
        self.reader = CalendarPrincipal("user:reader", ("/u/reader/calendar/",), False)
        self.writer = CalendarPrincipal("user:writer", ("/u/writer/calendar/",), True)
        self.anchor = datetime(2026, 8, 20, 12, tzinfo=UTC)

    def test_unscoped_calendar_is_forbidden_without_leaking_detail(self):
        response = dispatch(
            service=self.service,
            principal=self.reader,
            method="GET",
            path="/api/v1/events",
            query={"calendar": "/other/calendar/", "view": "day", "anchor": self.anchor.isoformat()},
        )
        self.assertEqual(response.status, 403)
        self.assertEqual(json.loads(response.body), {"error": "forbidden"})

    def test_read_only_principal_cannot_write(self):
        response = dispatch(
            service=self.service,
            principal=self.reader,
            method="PUT",
            path="/api/v1/events",
            payload={
                "calendar": "/u/reader/calendar/",
                "uid": "blocked@example.test",
                "title": "Blocked write",
                "starts_at": self.anchor.isoformat(),
                "ends_at": (self.anchor + timedelta(hours=1)).isoformat(),
            },
        )
        self.assertEqual(response.status, 403)
        self.assertEqual(self.store.events, [])

    def test_write_returns_only_mutation_identity_and_concurrency_state(self):
        response = dispatch(
            service=self.service,
            principal=self.writer,
            method="PUT",
            path="/api/v1/events",
            payload={
                "calendar": "/u/writer/calendar/",
                "uid": "event@example.test",
                "title": "Private title",
                "description": "Private description",
                "location": "Private location",
                "starts_at": self.anchor.isoformat(),
                "ends_at": (self.anchor + timedelta(hours=1)).isoformat(),
            },
        )
        self.assertEqual(response.status, 200)
        payload = json.loads(response.body)
        self.assertEqual(payload["schema"], "goreecloud.calendar.event-mutation.v1")
        self.assertNotIn("title", json.dumps(payload))
        self.assertEqual(payload["event"]["etag"], '"v1"')

    def test_busy_time_redacts_event_content(self):
        self.store.events.append(CalendarEvent(
            uid="busy@example.test",
            title="Medical appointment",
            description="Sensitive",
            location="Sensitive place",
            starts_at=self.anchor,
            ends_at=self.anchor + timedelta(hours=1),
            calendar_href="/u/reader/calendar/",
        ))
        response = dispatch(
            service=self.service,
            principal=self.reader,
            method="GET",
            path="/api/v1/busy-time",
            query={
                "calendar": "/u/reader/calendar/",
                "starts_at": (self.anchor - timedelta(hours=1)).isoformat(),
                "ends_at": (self.anchor + timedelta(hours=2)).isoformat(),
            },
        )
        self.assertEqual(response.status, 200)
        text = response.body.decode()
        self.assertNotIn("Medical", text)
        self.assertNotIn("Sensitive", text)
        self.assertNotIn("calendar_href", text)

    def test_delete_cannot_escape_authorized_collection(self):
        response = dispatch(
            service=self.service,
            principal=self.writer,
            method="DELETE",
            path="/api/v1/events",
            payload={
                "calendar": "/u/writer/calendar/",
                "event_href": "/u/other/calendar/event.ics",
                "etag": '"v1"',
            },
        )
        self.assertEqual(response.status, 400)
        self.assertEqual(self.store.deleted, [])


if __name__ == "__main__":
    unittest.main()
