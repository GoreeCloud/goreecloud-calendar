"""Dependency-free API response contracts for GoreeCloud Calendar."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from .events import CalendarEvent, busy_intervals
from .views import ViewMode, build_view_window, events_for_window

EVENT_SCHEMA = "goreecloud.calendar.events.v1"
BUSY_SCHEMA = "goreecloud.calendar.busy.v1"
FREE_SCHEMA = "goreecloud.calendar.free.v1"
MAX_FREE_MINIMUM_MINUTES = 24 * 60


def _iso(value: datetime) -> str:
    return value.isoformat()


def serialize_event(event: CalendarEvent) -> dict[str, Any]:
    """Serialize one validated event without exposing credentials or backend details."""

    return {
        "uid": event.uid,
        "title": event.title,
        "starts_at": _iso(event.starts_at),
        "ends_at": _iso(event.ends_at),
        "description": event.description,
        "location": event.location,
        "all_day": event.all_day,
        "etag": event.etag,
    }


def view_payload(
    *,
    events: tuple[CalendarEvent, ...],
    mode: ViewMode | str,
    anchor: date,
    timezone_name: str,
) -> dict[str, Any]:
    """Build the stable Calendar view API payload consumed by the Glaze UI shell."""

    window = build_view_window(mode=mode, anchor=anchor, timezone_name=timezone_name)
    selected = events_for_window(events, window)
    return {
        "schema": EVENT_SCHEMA,
        "version": 1,
        "view": window.mode.value,
        "timezone": timezone_name,
        "range": {"starts_at": _iso(window.starts_at), "ends_at": _iso(window.ends_at)},
        "returned": len(selected),
        "events": [serialize_event(event) for event in selected],
    }


def _busy_for_window(
    *, events: tuple[CalendarEvent, ...], starts_at: datetime, ends_at: datetime
) -> tuple[tuple[datetime, datetime], ...]:
    if starts_at.tzinfo is None or ends_at.tzinfo is None:
        raise ValueError("busy window boundaries must be timezone-aware")
    if ends_at <= starts_at:
        raise ValueError("busy window must have positive duration")

    visible = tuple(
        event
        for event in events
        if event.starts_at < ends_at and starts_at < event.ends_at
    )
    clipped = tuple(
        CalendarEvent(
            uid=event.uid,
            title=event.title,
            starts_at=max(event.starts_at, starts_at),
            ends_at=min(event.ends_at, ends_at),
            all_day=event.all_day,
        )
        for event in visible
    )
    return busy_intervals(clipped)


def busy_payload(
    *, events: tuple[CalendarEvent, ...], starts_at: datetime, ends_at: datetime
) -> dict[str, Any]:
    """Build a least-privilege busy-time projection for peer applications such as Tasks."""

    intervals = _busy_for_window(events=events, starts_at=starts_at, ends_at=ends_at)
    return {
        "schema": BUSY_SCHEMA,
        "version": 1,
        "range": {"starts_at": _iso(starts_at), "ends_at": _iso(ends_at)},
        "returned": len(intervals),
        "busy": [{"starts_at": _iso(start), "ends_at": _iso(end)} for start, end in intervals],
    }


def free_payload(
    *,
    events: tuple[CalendarEvent, ...],
    starts_at: datetime,
    ends_at: datetime,
    minimum_minutes: int = 30,
) -> dict[str, Any]:
    """Build privacy-safe free intervals without returning event content.

    Free time is derived only from the same merged busy intervals already used by
    the peer-facing busy contract. The payload contains no event identity, title,
    description, location, attendee, calendar name, or backend metadata.
    """

    if isinstance(minimum_minutes, bool) or not isinstance(minimum_minutes, int):
        raise ValueError("minimum_minutes must be an integer")
    if minimum_minutes < 1 or minimum_minutes > MAX_FREE_MINIMUM_MINUTES:
        raise ValueError("minimum_minutes must be between 1 and 1440")

    intervals = _busy_for_window(events=events, starts_at=starts_at, ends_at=ends_at)
    minimum = timedelta(minutes=minimum_minutes)
    free: list[tuple[datetime, datetime]] = []
    cursor = starts_at

    for busy_start, busy_end in intervals:
        if busy_start > cursor and busy_start - cursor >= minimum:
            free.append((cursor, busy_start))
        if busy_end > cursor:
            cursor = busy_end

    if ends_at > cursor and ends_at - cursor >= minimum:
        free.append((cursor, ends_at))

    return {
        "schema": FREE_SCHEMA,
        "version": 1,
        "range": {"starts_at": _iso(starts_at), "ends_at": _iso(ends_at)},
        "minimum_minutes": minimum_minutes,
        "returned": len(free),
        "free": [{"starts_at": _iso(start), "ends_at": _iso(end)} for start, end in free],
    }
