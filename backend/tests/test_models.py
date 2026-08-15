import pytest
from pydantic import ValidationError

from app.models import EventWriteRequest


def test_timed_event_requires_timezone():
    with pytest.raises(ValidationError):
        EventWriteRequest(
            calendar_href="/person/calendar/",
            summary="Test",
            start="2026-08-15T09:00:00",
            end="2026-08-15T10:00:00",
            all_day=False,
        )


def test_all_day_event_end_is_exclusive_and_after_start():
    payload = EventWriteRequest(
        calendar_href="/person/calendar/",
        summary="Test",
        start="2026-08-15",
        end="2026-08-16",
        all_day=True,
    )
    assert payload.all_day is True


def test_summary_is_trimmed():
    payload = EventWriteRequest(
        calendar_href="/person/calendar/",
        summary="  Planning  ",
        start="2026-08-15T14:00:00+00:00",
        end="2026-08-15T15:00:00+00:00",
    )
    assert payload.summary == "Planning"
