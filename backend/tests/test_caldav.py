from datetime import datetime, timezone

import pytest
from icalendar import Calendar as ICalendar

from app.caldav import CalDavAuthorizationError, CalDavClient, CalDavSettings


def client():
    return CalDavClient(
        CalDavSettings(
            base_url="https://dav.goreecloud.com",
            timeout_seconds=5,
            max_query_days=62,
        ),
        username="person",
        password="secret",
    )


def test_safe_url_accepts_same_origin_path():
    assert client()._resolve_safe_url("/person/calendar/event.ics") == (
        "https://dav.goreecloud.com/person/calendar/event.ics"
    )


def test_safe_url_rejects_cross_origin_resource():
    with pytest.raises(CalDavAuthorizationError):
        client()._resolve_safe_url("https://example.com/event.ics")


def test_event_href_requires_ics_resource():
    with pytest.raises(CalDavAuthorizationError):
        client()._validate_event_href("/person/calendar/")


def test_recurring_events_expand_inside_requested_window():
    parsed = ICalendar.from_ical(
        b"""BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//GoreeCloud//Test//EN\r\nBEGIN:VEVENT\r\nUID:test-series@goreecloud.com\r\nDTSTART:20260801T140000Z\r\nDTEND:20260801T150000Z\r\nRRULE:FREQ=WEEKLY;COUNT=4\r\nSUMMARY:Weekly review\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"""
    )
    events, recurring = client()._expand_components(
        parsed,
        start=datetime(2026, 8, 1, tzinfo=timezone.utc),
        end=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )

    assert recurring is True
    assert len(events) == 4
    assert [event.decoded("DTSTART") for event in events] == [
        datetime(2026, 8, 1, 14, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 8, 14, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 15, 14, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 22, 14, 0, tzinfo=timezone.utc),
    ]


def test_calendar_query_range_is_bounded():
    settings = client().settings
    assert settings.max_query_days == 62


def test_calendar_access_is_scoped_to_discovered_user_collections(monkeypatch):
    from app.models import CalendarSummary
    import asyncio

    dav = client()

    async def discovered():
        return [CalendarSummary(href="/person-a/calendar/", display_name="A")]

    monkeypatch.setattr(dav, "discover_calendars", discovered)

    assert asyncio.run(dav._assert_calendar_access("/person-a/calendar/")) == (
        "https://dav.goreecloud.com/person-a/calendar/"
    )
    with pytest.raises(CalDavAuthorizationError):
        asyncio.run(dav._assert_calendar_access("/person-b/calendar/"))


def test_event_access_is_scoped_to_discovered_user_collections(monkeypatch):
    from app.models import CalendarSummary
    import asyncio

    dav = client()

    async def discovered():
        return [CalendarSummary(href="/person-a/calendar/", display_name="A")]

    monkeypatch.setattr(dav, "discover_calendars", discovered)

    with pytest.raises(CalDavAuthorizationError):
        asyncio.run(dav._assert_event_access("/person-b/calendar/event.ics"))


def test_calendar_query_range_rejects_oversized_window():
    import asyncio

    dav = client()
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 4, 1, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="cannot exceed"):
        asyncio.run(dav.list_events("/person/calendar/", start=start, end=end))


def test_recurring_resource_is_blocked_for_writes():
    from app.caldav import CalDavConflict

    calendar = ICalendar.from_ical(
        b"""BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:series\r\nDTSTART:20260801T140000Z\r\nRRULE:FREQ=DAILY;COUNT=2\r\nSUMMARY:Series\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"""
    )
    with pytest.raises(CalDavConflict, match="Recurring-event writes"):
        client()._assert_nonrecurring_resource(calendar)
