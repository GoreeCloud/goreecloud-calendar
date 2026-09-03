"""Runtime service boundary between authenticated Calendar requests and CalDAV."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Protocol

from goreecloud_calendar.api import busy_payload, view_payload
from goreecloud_calendar.auth import CalendarPrincipal
from goreecloud_calendar.events import CalendarEvent
from goreecloud_calendar.views import build_view_window


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
        anchor: date,
        timezone_name: str,
    ) -> dict[str, object]:
        principal.require_calendar(calendar_href)
        window = build_view_window(mode=view, anchor=anchor, timezone_name=timezone_name)
        events = self.store.query_events(
            calendar_href=calendar_href,
            starts_at=window.starts_at,
            ends_at=window.ends_at,
        )
        return view_payload(
            events=events,
            mode=window.mode,
            anchor=anchor,
            timezone_name=timezone_name,
        )

    def busy_time_for_calendars(
        self,
        *,
        principal: CalendarPrincipal,
        calendar_hrefs: Iterable[str],
        starts_at: datetime,
        ends_at: datetime,
    ) -> dict[str, object]:
        """Return one minimized busy projection across authorized collections.

        Every collection is authorized independently before it is queried. The returned
        projection is produced only after events from all authorized collections have been
        combined, so overlapping busy periods are merged without exposing which calendar or
        event produced an interval.
        """

        hrefs = tuple(calendar_hrefs)
        if not hrefs:
            raise ValueError("at least one calendar collection is required")
        if len(set(hrefs)) != len(hrefs):
            raise ValueError("calendar collections must be unique")

        for calendar_href in hrefs:
            principal.require_calendar(calendar_href)

        events: list[CalendarEvent] = []
        for calendar_href in hrefs:
            events.extend(
                self.store.query_events(
                    calendar_href=calendar_href,
                    starts_at=starts_at,
                    ends_at=ends_at,
                )
            )
        return busy_payload(
            events=tuple(events),
            starts_at=starts_at,
            ends_at=ends_at,
        )

    def busy_time(
        self,
        *,
        principal: CalendarPrincipal,
        calendar_href: str,
        starts_at: datetime,
        ends_at: datetime,
    ) -> dict[str, object]:
        return self.busy_time_for_calendars(
            principal=principal,
            calendar_hrefs=(calendar_href,),
            starts_at=starts_at,
            ends_at=ends_at,
        )

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
