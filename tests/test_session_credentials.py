"""Tests for trusted Calendar sessions and runtime-only DAV credentials."""

import json
import unittest
from datetime import datetime, timedelta, timezone

from goreecloud_calendar.credentials import (
    CalendarCredentialError,
    DAVAccess,
    DAVCredential,
    StaticDAVCredentialProvider,
)
from goreecloud_calendar.events import CalendarEvent
from goreecloud_calendar.http import authenticated_dispatch
from goreecloud_calendar.security import TrustedRequestContext
from goreecloud_calendar.service import CalendarService
from goreecloud_calendar.session import (
    CalendarSessionAuthenticator,
    CalendarSessionError,
    StaticSessionClaimsProvider,
    TrustedSessionClaims,
)

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


class SessionBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 21, 8, tzinfo=UTC)
        self.claims = TrustedSessionClaims(
            subject="user:calendar-writer",
            audience="goreecloud-calendar",
            expires_at=self.now + timedelta(hours=1),
            calendar_hrefs=("/u/writer/calendar/",),
            can_write=True,
        )
        self.authenticator = CalendarSessionAuthenticator(
            StaticSessionClaimsProvider({"opaque-session": self.claims})
        )

    def test_session_maps_to_minimal_principal(self):
        principal = self.authenticator.authenticate("opaque-session", now=self.now)
        self.assertEqual(principal.subject, "user:calendar-writer")
        self.assertEqual(principal.calendar_hrefs, ("/u/writer/calendar/",))
        self.assertTrue(principal.can_write)

    def test_expired_session_is_rejected(self):
        expired = TrustedSessionClaims(
            subject="user:expired",
            audience="goreecloud-calendar",
            expires_at=self.now - timedelta(seconds=1),
            calendar_hrefs=("/u/expired/calendar/",),
        )
        auth = CalendarSessionAuthenticator(StaticSessionClaimsProvider({"expired": expired}))
        with self.assertRaises(CalendarSessionError):
            auth.authenticate("expired", now=self.now)

    def test_wrong_audience_is_rejected(self):
        wrong = TrustedSessionClaims(
            subject="user:wrong",
            audience="another-service",
            expires_at=self.now + timedelta(hours=1),
            calendar_hrefs=("/u/wrong/calendar/",),
        )
        auth = CalendarSessionAuthenticator(StaticSessionClaimsProvider({"wrong": wrong}))
        with self.assertRaises(CalendarSessionError):
            auth.authenticate("wrong", now=self.now)

    def test_authenticated_dispatch_does_not_trust_payload_identity(self):
        service = CalendarService(FakeStore())
        context = TrustedRequestContext(
            scheme="https",
            host="calendar.goreecloud.com",
            origin="https://calendar.goreecloud.com",
        )
        response = authenticated_dispatch(
            service=service,
            authenticator=self.authenticator,
            session_handle="opaque-session",
            request_context=context,
            method="GET",
            path="/api/v1/events",
            query={
                "calendar": "/u/writer/calendar/",
                "anchor": "2026-08-21",
                "view": "day",
                "timezone": "UTC",
            },
            payload={"subject": "user:attacker", "can_write": False},
            now=self.now,
        )
        self.assertEqual(response.status, 200)
        self.assertNotIn("attacker", response.body.decode("utf-8"))

    def test_unrecognized_session_returns_low_detail_401(self):
        service = CalendarService(FakeStore())
        response = authenticated_dispatch(
            service=service,
            authenticator=self.authenticator,
            session_handle="missing",
            request_context=TrustedRequestContext(
                scheme="https",
                host="calendar.goreecloud.com",
                origin="https://calendar.goreecloud.com",
            ),
            method="GET",
            path="/api/v1/events",
            query={"calendar": "/u/writer/calendar/", "anchor": "2026-08-21"},
            now=self.now,
        )
        self.assertEqual(response.status, 401)
        self.assertEqual(json.loads(response.body), {"error": "authentication_required"})


class DAVCredentialBoundaryTests(unittest.TestCase):
    def test_password_is_not_exposed_in_repr(self):
        credential = DAVCredential(username="calendar-runtime", password="synthetic-secret")
        self.assertNotIn("synthetic-secret", repr(credential))

    def test_https_and_no_embedded_credentials_are_required(self):
        credential = DAVCredential(username="calendar-runtime", password="synthetic-secret")
        with self.assertRaises(CalendarCredentialError):
            DAVAccess(base_url="http://dav.goreecloud.com", credential=credential)
        with self.assertRaises(CalendarCredentialError):
            DAVAccess(
                base_url="https://user:pass@dav.goreecloud.com",
                credential=credential,
            )

    def test_provider_resolves_by_authenticated_subject(self):
        access = DAVAccess(
            base_url="https://dav.goreecloud.com",
            credential=DAVCredential(username="calendar-runtime", password="synthetic-secret"),
        )
        provider = StaticDAVCredentialProvider({"user:calendar-writer": access})
        self.assertIs(provider.resolve("user:calendar-writer"), access)
        with self.assertRaises(CalendarCredentialError):
            provider.resolve("user:not-authorized")


if __name__ == "__main__":
    unittest.main()
