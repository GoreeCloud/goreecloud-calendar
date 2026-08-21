"""Runtime service boundary between authenticated Calendar requests and CalDAV."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from goreecloud_calendar.api import busy_time_payload, event_view_payload
from goreecloud_calendar.auth import CalendarPrincipal
from goreecloud_calendar.events import CalendarEvent


class CalendarStore(Protocol):
    def query_events(
        self, *, calendar_href: str, starts_at: datetime, ends_at: datetime
    ) -> tuple[CalendarEvent, ...]: ...

    def put_event(self, *, calendar_href: str, event: CalendarEvent) -> CalendarEvent: ...

    def delete_event(self, *, event_href: str, etag: str) -> None: ...


@dataclass(slots=True)
class CalendarService:
    """Authorized application service over an injected CalDAV-compatible store."""

    store: CalendarStore

    def list_events(
        self,
        *,
        principal: CalendarPrincipal,
        calendar_href: str,
        view: str,
        anchor: datetime,
    ) -> dict[str, object]:
        principal.require_calendar(calendar_href)
        # event_view_payload owns deterministic view-window calculation and filtering.
        return event_view_payload(
            view=view,
            anchor=anchor,
            events_provider=lambda start, end: self.store.query_events(
                calendar_href=calendar_href, starts_at=start, ends_at=end
            ),
        )

    def busy_time(
        self,
        *,
        principal: CalendarPrincipal,
        calendar_href: str,
        starts_at: datetime,
        ends_at: datetime,
    ) -> dict[str, object]:
        principal.require_calendar(calendar_href)
        events = self.store.query_events(
            calendar_href=calendar_href, starts_at=starts_at, ends_at=ends_at
        )
        return busy_time_payload(starts_at=starts_at, ends_at=ends_at, events=events)

    def save_event(
        self,
        *,
        principal: CalendarPrincipal,
        calendar_href: str,
        event: CalendarEvent,
    ) -> CalendarEvent:
        principal.require_calendar(calendar_href, write=True)
        if event.calendar_href not in (None, calendar_href):
            raise ValueError("event calendar_href does not match the authorized target")
        return self.store.put_event(calendar_href=calendar_href, event=event)

    def delete_event(
        self,
        *,
        principal: CalendarPrincipal,
        calendar_href: str,
        event_href: str,
        etag: str,
    ) -> None:
        principal.require_calendar(calendar_href, write=True)
        prefix = calendar_href.rstrip("/") + "/"
        if not event_href.startswith(prefix) or ".." in event_href:
            raise ValueError("event href is outside the authorized calendar collection")
        self.store.delete_event(event_href=event_href, etag=etag)
