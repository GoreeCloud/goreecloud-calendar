import pytest

from app.caldav import CalDavAuthorizationError, CalDavClient, CalDavSettings


def client():
    return CalDavClient(
        CalDavSettings(base_url="https://dav.goreecloud.com", timeout_seconds=5),
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
