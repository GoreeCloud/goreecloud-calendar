"""Least-privilege delegated peer authorization for Tasks→Calendar busy context.

This module consumes only claims that an approved GoreeCloud Identity boundary has already
validated. It does not parse or verify raw bearer tokens, sessions, cookies, or DAV credentials.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .auth import CalendarAuthorizationError, CalendarPrincipal

TASKS_BUSY_AUDIENCE = "goreecloud-calendar-busy"
TASKS_BUSY_SCOPE = "calendar.busy.read"
MAX_DELEGATED_SCOPES = 16
MAX_DELEGATED_CALENDARS = 32


@dataclass(frozen=True, slots=True)
class DelegatedCalendarClaims:
    """Already-validated Identity claims permitted to reach the Calendar peer boundary."""

    subject: str
    audience: str
    scopes: frozenset[str]
    calendar_hrefs: tuple[str, ...]
    expires_at: datetime

    def __post_init__(self) -> None:
        subject = self.subject.strip()
        audience = self.audience.strip()
        if not subject or not audience:
            raise CalendarAuthorizationError("delegated Calendar subject and audience are required")
        if not self.scopes or len(self.scopes) > MAX_DELEGATED_SCOPES:
            raise CalendarAuthorizationError("delegated Calendar scopes are outside the reviewed bound")
        normalized_scopes = frozenset(scope.strip() for scope in self.scopes if isinstance(scope, str))
        if len(normalized_scopes) != len(self.scopes) or any(not scope for scope in normalized_scopes):
            raise CalendarAuthorizationError("delegated Calendar scopes are invalid")
        if not self.calendar_hrefs or len(self.calendar_hrefs) > MAX_DELEGATED_CALENDARS:
            raise CalendarAuthorizationError("delegated Calendar collection scope is outside the reviewed bound")
        if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
            raise CalendarAuthorizationError("delegated Calendar expiry must include timezone information")

        object.__setattr__(self, "subject", subject)
        object.__setattr__(self, "audience", audience)
        object.__setattr__(self, "scopes", normalized_scopes)
        object.__setattr__(self, "expires_at", self.expires_at.astimezone(timezone.utc))


def principal_for_tasks_busy_context(
    claims: DelegatedCalendarClaims | None,
    *,
    now: datetime,
) -> CalendarPrincipal:
    """Map approved Tasks busy-time claims to a read-only Calendar principal.

    The returned principal retains only the delegated subject and explicit Calendar collection
    hrefs. Passing this boundary grants no Calendar mutation authority and does not itself perform
    transport, token validation, backend access, or a busy-time query.
    """

    if now.tzinfo is None or now.utcoffset() is None:
        raise CalendarAuthorizationError("delegated Calendar check time must include timezone information")
    checked_at = now.astimezone(timezone.utc)
    if (
        claims is None
        or claims.audience != TASKS_BUSY_AUDIENCE
        or TASKS_BUSY_SCOPE not in claims.scopes
        or claims.expires_at <= checked_at
    ):
        raise CalendarAuthorizationError("delegated Calendar busy authorization unavailable")

    return CalendarPrincipal(
        subject=claims.subject,
        calendar_hrefs=claims.calendar_hrefs,
        can_write=False,
    )
