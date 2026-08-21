"""Trusted session integration boundary for GoreeCloud Calendar.

The application never constructs Calendar authorization from browser request JSON. A trusted
identity/session adapter validates server-derived session claims and then maps those claims to a
minimal CalendarPrincipal used by the existing authorization layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping, Protocol

from goreecloud_calendar.auth import CalendarPrincipal


class CalendarSessionError(PermissionError):
    """Raised when a trusted application session cannot be accepted."""


@dataclass(frozen=True, slots=True)
class TrustedSessionClaims:
    """Minimal validated claims supplied by trusted authentication middleware."""

    subject: str
    audience: str
    expires_at: datetime
    calendar_hrefs: tuple[str, ...]
    can_write: bool = False

    def validate(self, *, expected_audience: str, now: datetime | None = None) -> None:
        if not self.subject.strip():
            raise CalendarSessionError("session subject is required")
        if self.audience != expected_audience:
            raise CalendarSessionError("session audience is invalid")
        if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
            raise CalendarSessionError("session expiry must include timezone information")
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or current.utcoffset() is None:
            raise CalendarSessionError("validation time must include timezone information")
        if self.expires_at <= current:
            raise CalendarSessionError("session is expired")
        if len(set(self.calendar_hrefs)) != len(self.calendar_hrefs):
            raise CalendarSessionError("session calendar scope contains duplicates")

    def to_principal(self, *, expected_audience: str, now: datetime | None = None) -> CalendarPrincipal:
        self.validate(expected_audience=expected_audience, now=now)
        return CalendarPrincipal(
            subject=self.subject,
            calendar_hrefs=self.calendar_hrefs,
            can_write=self.can_write,
        )


class SessionClaimsProvider(Protocol):
    """Provider contract implemented by production authentication/session middleware."""

    def resolve(self, session_handle: str) -> TrustedSessionClaims: ...


@dataclass(slots=True)
class CalendarSessionAuthenticator:
    """Resolve an opaque session handle into a validated Calendar principal."""

    provider: SessionClaimsProvider
    audience: str = "goreecloud-calendar"

    def authenticate(
        self, session_handle: str, *, now: datetime | None = None
    ) -> CalendarPrincipal:
        if not isinstance(session_handle, str) or not session_handle.strip():
            raise CalendarSessionError("session handle is required")
        claims = self.provider.resolve(session_handle)
        if not isinstance(claims, TrustedSessionClaims):
            raise CalendarSessionError("session provider returned invalid claims")
        return claims.to_principal(expected_audience=self.audience, now=now)


@dataclass(slots=True)
class StaticSessionClaimsProvider:
    """Small test/development provider that stores only opaque handles and synthetic claims."""

    sessions: Mapping[str, TrustedSessionClaims]

    def resolve(self, session_handle: str) -> TrustedSessionClaims:
        try:
            return self.sessions[session_handle]
        except KeyError as exc:
            raise CalendarSessionError("session is not recognized") from exc
