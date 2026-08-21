"""Dependency-free API response contracts for GoreeCloud Calendar."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from typing import Any

from .events import CalendarEvent, busy_intervals
from .views import ViewMode, build_view_window, events_for_window

EVENT_SCHEMA = "goreecloud.calendar.events.v1"
BUSY_SCHEMA = "goreecloud.calendar.busy.v1"


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


def busy_payload(
    *, events: tuple[CalendarEvent, ...], starts_at: datetime, ends_at: datetime
) -> dict[str, Any]:
    """Build a least-privilege busy-time projection for peer applications such as Tasks."""

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
    intervals = busy_intervals(clipped)
    return {
        "schema": BUSY_SCHEMA,
        "version": 1,
        "range": {"starts_at": _iso(starts_at), "ends_at": _iso(ends_at)},
        "returned": len(intervals),
        "busy": [{"starts_at": _iso(start), "ends_at": _iso(end)} for start, end in intervals],
    }
