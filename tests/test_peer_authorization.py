from datetime import datetime, timedelta, timezone
import unittest

from goreecloud_calendar.auth import CalendarAuthorizationError
from goreecloud_calendar.peer_authorization import (
    TASKS_BUSY_AUDIENCE,
    TASKS_BUSY_SCOPE,
    DelegatedCalendarClaims,
    principal_for_tasks_busy_context,
)


class DelegatedTasksCalendarAuthorizationTests(unittest.TestCase):
    now = datetime(2026, 9, 1, 17, 0, tzinfo=timezone.utc)

    def claims(self, **overrides):
        values = {
            "subject": "owner-a",
            "audience": TASKS_BUSY_AUDIENCE,
            "scopes": frozenset({TASKS_BUSY_SCOPE}),
            "calendar_hrefs": ("/calendars/owner-a/work/",),
            "expires_at": self.now + timedelta(minutes=5),
        }
        values.update(overrides)
        return DelegatedCalendarClaims(**values)

    def test_maps_reviewed_busy_claims_to_read_only_scoped_principal(self):
        principal = principal_for_tasks_busy_context(self.claims(), now=self.now)

        self.assertEqual(principal.subject, "owner-a")
        self.assertEqual(principal.calendar_hrefs, ("/calendars/owner-a/work/",))
        self.assertFalse(principal.can_write)
        principal.require_calendar("/calendars/owner-a/work/")
        with self.assertRaises(CalendarAuthorizationError):
            principal.require_calendar("/calendars/owner-a/work/", write=True)

    def test_rejects_wrong_audience_missing_scope_and_expiry(self):
        for claims in (
            self.claims(audience="goreecloud-calendar-full"),
            self.claims(scopes=frozenset({"calendar.events.read"})),
            self.claims(expires_at=self.now),
        ):
            with self.subTest(claims=claims):
                with self.assertRaises(CalendarAuthorizationError):
                    principal_for_tasks_busy_context(claims, now=self.now)

    def test_calendar_collection_scope_remains_explicit_and_bounded(self):
        principal = principal_for_tasks_busy_context(
            self.claims(calendar_hrefs=("/calendars/owner-a/work/", "/calendars/owner-a/personal/")),
            now=self.now,
        )
        with self.assertRaises(CalendarAuthorizationError):
            principal.require_calendar("/calendars/owner-a/other/")

        with self.assertRaises(CalendarAuthorizationError):
            self.claims(calendar_hrefs=())
        with self.assertRaises(CalendarAuthorizationError):
            self.claims(calendar_hrefs=tuple(f"/calendars/owner-a/{index}/" for index in range(33)))

    def test_rejects_naive_times_and_unreviewed_scope_volume(self):
        with self.assertRaises(CalendarAuthorizationError):
            self.claims(expires_at=datetime(2026, 9, 1, 17, 5))
        with self.assertRaises(CalendarAuthorizationError):
            principal_for_tasks_busy_context(
                self.claims(),
                now=datetime(2026, 9, 1, 17, 0),
            )
        with self.assertRaises(CalendarAuthorizationError):
            self.claims(scopes=frozenset(f"scope-{index}" for index in range(17)))


if __name__ == "__main__":
    unittest.main()
