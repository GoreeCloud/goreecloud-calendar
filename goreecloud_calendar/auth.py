"""Authorization-scoped Calendar session primitives.

These types intentionally carry only the minimum runtime identity and collection scope needed
for Calendar request authorization. Reusable DAV credentials remain outside user-facing
session payloads and source control.
"""

from __future__ import annotations

from dataclasses import dataclass


class CalendarAuthorizationError(PermissionError):
    """Raised when a Calendar principal attempts an unauthorized operation."""


@dataclass(frozen=True, slots=True)
class CalendarPrincipal:
    subject: str
    calendar_hrefs: tuple[str, ...]
    can_write: bool = False

    def __post_init__(self) -> None:
        subject = self.subject.strip()
        if not subject:
            raise CalendarAuthorizationError("principal subject is required")
        if len(set(self.calendar_hrefs)) != len(self.calendar_hrefs):
            raise CalendarAuthorizationError("calendar scope contains duplicate hrefs")
        for href in self.calendar_hrefs:
            if not href.startswith("/") or ".." in href:
                raise CalendarAuthorizationError("calendar href scope is invalid")

    def require_calendar(self, href: str, *, write: bool = False) -> None:
        if href not in self.calendar_hrefs:
            raise CalendarAuthorizationError("calendar is outside the principal scope")
        if write and not self.can_write:
            raise CalendarAuthorizationError("principal does not have Calendar write access")
