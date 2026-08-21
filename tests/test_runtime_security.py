"""Tests for Calendar browser request trust and abuse controls."""

import json
import unittest
from datetime import datetime, timedelta, timezone

from goreecloud_calendar.auth import CalendarPrincipal
from goreecloud_calendar.events import CalendarEvent
from goreecloud_calendar.http import secure_dispatch
from goreecloud_calendar.security import InMemoryRateLimiter, TrustedRequestContext
from goreecloud_calendar.service import CalendarService

UTC = timezone.utc


class FakeStore:
    def __init__(self):
        self.events = []

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
        return None


class RuntimeSecurityTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeStore()
        self.service = CalendarService(self.store)
        self.principal = CalendarPrincipal("user:writer", ("/u/writer/calendar/",), True)
        self.anchor = datetime(2026, 8, 21, 12, tzinfo=UTC)
        self.good = TrustedRequestContext(
            scheme="https",
            host="calendar.goreecloud.com",
            origin="https://calendar.goreecloud.com",
            csrf_cookie="csrf-value",
            csrf_header="csrf-value",
        )

    def _put(self, context=None, limiter=None):
        return secure_dispatch(
            service=self.service,
            principal=self.principal,
            request_context=context or self.good,
            method="PUT",
            path="/api/v1/events",
            payload={
                "calendar": "/u/writer/calendar/",
                "uid": "event@example.test",
                "title": "Private event",
                "starts_at": self.anchor.isoformat(),
                "ends_at": (self.anchor + timedelta(hours=1)).isoformat(),
            },
            rate_limiter=limiter,
        )

    def test_cross_origin_mutation_is_rejected_before_store_write(self):
        bad = TrustedRequestContext(
            scheme="https",
            host="calendar.goreecloud.com",
            origin="https://attacker.example",
            csrf_cookie="same",
            csrf_header="same",
        )
        response = self._put(context=bad)
        self.assertEqual(response.status, 403)
        self.assertEqual(json.loads(response.body), {"error": "request_rejected"})
        self.assertEqual(self.store.events, [])

    def test_mutation_requires_matching_csrf_evidence(self):
        bad = TrustedRequestContext(
            scheme="https",
            host="calendar.goreecloud.com",
            origin="https://calendar.goreecloud.com",
            csrf_cookie="cookie-token",
            csrf_header="different-token",
        )
        response = self._put(context=bad)
        self.assertEqual(response.status, 403)
        self.assertEqual(self.store.events, [])

    def test_non_https_request_context_is_rejected(self):
        bad = TrustedRequestContext(
            scheme="http",
            host="calendar.goreecloud.com",
            origin="http://calendar.goreecloud.com",
            csrf_cookie="same",
            csrf_header="same",
        )
        response = self._put(context=bad)
        self.assertEqual(response.status, 403)
        self.assertEqual(self.store.events, [])

    def test_same_origin_mutation_with_csrf_succeeds(self):
        response = self._put()
        self.assertEqual(response.status, 200)
        self.assertEqual(len(self.store.events), 1)

    def test_get_does_not_require_csrf_but_still_requires_same_origin(self):
        context = TrustedRequestContext(
            scheme="https",
            host="calendar.goreecloud.com",
            origin="https://calendar.goreecloud.com",
        )
        response = secure_dispatch(
            service=self.service,
            principal=self.principal,
            request_context=context,
            method="GET",
            path="/api/v1/events",
            query={
                "calendar": "/u/writer/calendar/",
                "anchor": "2026-08-21",
                "view": "day",
                "timezone": "UTC",
            },
        )
        self.assertEqual(response.status, 200)

    def test_rate_limiter_rejects_excess_requests_without_event_content_keying(self):
        limiter = InMemoryRateLimiter(limit=1, window_seconds=60)
        first = self._put(limiter=limiter)
        second = self._put(limiter=limiter)
        self.assertEqual(first.status, 200)
        self.assertEqual(second.status, 403)
        self.assertEqual(json.loads(second.body), {"error": "request_rejected"})
        self.assertEqual(len(self.store.events), 1)


if __name__ == "__main__":
    unittest.main()
