"""Calendar event domain primitives.

The application layer may cache or normalize events, but Radicale/CalDAV remains the
canonical calendar-data authority. These types intentionally contain no persistence logic.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from uuid import uuid4


class CalendarEventError(ValueError):
    """Raised when an event would violate Calendar domain invariants."""


def _require_aware(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CalendarEventError(f"{field} must include timezone information.")


@dataclass(frozen=True, slots=True)
class CalendarEvent:
    uid: str
    title: str
    starts_at: datetime
    ends_at: datetime
    description: str = ""
    location: str = ""
    all_day: bool = False
    calendar_href: str | None = None
    etag: str | None = None

    def __post_init__(self) -> None:
        if not self.uid.strip():
            raise CalendarEventError("uid is required.")
        if not self.title.strip():
            raise CalendarEventError("title is required.")
        _require_aware(self.starts_at, "starts_at")
        _require_aware(self.ends_at, "ends_at")
        if self.ends_at <= self.starts_at:
            raise CalendarEventError("ends_at must be later than starts_at.")

    @classmethod
    def new(
        cls,
        *,
        title: str,
        starts_at: datetime,
        ends_at: datetime,
        description: str = "",
        location: str = "",
        all_day: bool = False,
    ) -> "CalendarEvent":
        return cls(
            uid=f"{uuid4()}@calendar.goreecloud.com",
            title=title,
            starts_at=starts_at,
            ends_at=ends_at,
            description=description,
            location=location,
            all_day=all_day,
        )

    def overlaps(self, other: "CalendarEvent") -> bool:
        """Return True for half-open interval overlap: [start, end)."""
        return self.starts_at < other.ends_at and other.starts_at < self.ends_at

    def moved(self, *, starts_at: datetime, ends_at: datetime) -> "CalendarEvent":
        return replace(self, starts_at=starts_at, ends_at=ends_at)

    @property
    def starts_at_utc(self) -> datetime:
        return self.starts_at.astimezone(timezone.utc)

    @property
    def ends_at_utc(self) -> datetime:
        return self.ends_at.astimezone(timezone.utc)


def busy_intervals(events: tuple[CalendarEvent, ...]) -> tuple[tuple[datetime, datetime], ...]:
    """Return merged busy intervals in chronological order."""
    if not events:
        return ()
    ordered = sorted((event.starts_at, event.ends_at) for event in events)
    merged: list[list[datetime]] = []
    for start, end in ordered:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        elif end > merged[-1][1]:
            merged[-1][1] = end
    return tuple((start, end) for start, end in merged)
