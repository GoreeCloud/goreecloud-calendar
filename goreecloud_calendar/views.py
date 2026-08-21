"""Pure calendar view projections for the first-party Calendar UI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from .events import CalendarEvent


class CalendarViewError(ValueError):
    """Raised when a calendar view request is invalid."""


class ViewMode(StrEnum):
    MONTH = "month"
    WEEK = "week"
    DAY = "day"
    AGENDA = "agenda"


@dataclass(frozen=True, slots=True)
class ViewWindow:
    mode: ViewMode
    starts_at: datetime
    ends_at: datetime
    timezone: str

    def __post_init__(self) -> None:
        if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None:
            raise CalendarViewError("view boundaries must be timezone-aware")
        if self.ends_at <= self.starts_at:
            raise CalendarViewError("view window must have positive duration")


def _midnight(day: date, zone: ZoneInfo) -> datetime:
    return datetime.combine(day, time.min, zone)


def build_view_window(*, mode: ViewMode | str, anchor: date, timezone_name: str) -> ViewWindow:
    """Build a deterministic local-time view window around ``anchor``."""

    try:
        view_mode = ViewMode(mode)
    except ValueError as exc:
        raise CalendarViewError(f"unsupported view mode: {mode}") from exc
    try:
        zone = ZoneInfo(timezone_name)
    except Exception as exc:
        raise CalendarViewError(f"unknown timezone: {timezone_name}") from exc

    if view_mode is ViewMode.DAY:
        start_day = anchor
        end_day = anchor + timedelta(days=1)
    elif view_mode is ViewMode.WEEK:
        start_day = anchor - timedelta(days=anchor.weekday())
        end_day = start_day + timedelta(days=7)
    elif view_mode is ViewMode.MONTH:
        first = anchor.replace(day=1)
        start_day = first - timedelta(days=first.weekday())
        next_month = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
        last = next_month - timedelta(days=1)
        end_day = last + timedelta(days=(6 - last.weekday()) + 1)
    else:
        start_day = anchor
        end_day = anchor + timedelta(days=30)

    return ViewWindow(
        mode=view_mode,
        starts_at=_midnight(start_day, zone),
        ends_at=_midnight(end_day, zone),
        timezone=timezone_name,
    )


def events_for_window(
    events: tuple[CalendarEvent, ...], window: ViewWindow
) -> tuple[CalendarEvent, ...]:
    """Return events intersecting the view window in stable chronological order."""

    selected = [
        event
        for event in events
        if event.starts_at < window.ends_at and window.starts_at < event.ends_at
    ]
    return tuple(sorted(selected, key=lambda item: (item.starts_at, item.ends_at, item.uid)))
