import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.auth import SessionStore
from app.caldav import (
    CalDAVClient,
    CalDAVConflict,
    CalDAVError,
    CalDAVPreconditionRequired,
    parse_calendar_collections,
    parse_vevents,
)
from app.config import Settings
from app.main import app


def test_health_is_minimized_and_hardened():
    response = TestClient(app).get('/api/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert response.headers['x-frame-options'] == 'DENY'
    assert response.headers['cross-origin-opener-policy'] == 'same-origin'
    assert response.headers['x-wardveil-security'] == 'Wardveil Security by GoreeCloud'
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-request-id']


def test_meta_is_secret_free_when_signed_out():
    body = TestClient(app).get('/api/meta').json()
    assert body['authenticated'] is False
    assert body['csrfToken'] is None
    assert body['glazeUi'] == '1.0'
    assert body['securityIdentity'] == 'Wardveil Security by GoreeCloud'
    assert 'caldav' not in str(body).lower()


def test_protected_calendar_api_requires_session():
    response = TestClient(app).get('/api/events?start=2026-08-20&end=2026-08-21')
    assert response.status_code == 401


def test_session_store_is_bounded_and_opaque():
    store = SessionStore(ttl_seconds=300, max_sessions=8)
    session_id, session = store.create('synthetic-user', 'synthetic-password')
    assert 'synthetic-user' not in session_id
    assert store.get(session_id) is session
    assert session.csrf_token
    store.delete(session_id)
    assert store.get(session_id) is None


def test_parse_vevents_normalizes_basic_event():
    payload = '''BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:abc-123\nSUMMARY:Family appointment\nDTSTART:20260820T150000Z\nDTEND:20260820T160000Z\nLOCATION:Clinic\nEND:VEVENT\nEND:VCALENDAR'''
    events = parse_vevents(payload)
    assert events == [{
        'uid': 'abc-123',
        'summary': 'Family appointment',
        'start': '2026-08-20T15:00:00Z',
        'end': '2026-08-20T16:00:00Z',
        'location': 'Clinic',
        'recurring': False,
    }]


def test_parse_vevents_unfolds_text_and_preserves_timezone_and_recurrence():
    payload = '''BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:weekly-1\nSUMMARY:Family planning \\n meeting\nDTSTART;TZID=America/Chicago:20260820T090000\nDTEND;TZID=America/Chicago:20260820T100000\nDESCRIPTION:Bring notes\\, calendar\\; and questions\nRRULE:FREQ=WEEKLY;COUNT=4\nEND:VEVENT\nEND:VCALENDAR'''
    event = parse_vevents(payload)[0]
    assert event['uid'] == 'weekly-1'
    assert event['startTimezone'] == 'America/Chicago'
    assert event['description'] == 'Bring notes, calendar; and questions'
    assert event['rrule'] == 'FREQ=WEEKLY;COUNT=4'
    assert event['recurring'] is True


def test_parse_vevents_marks_date_value_as_all_day():
    payload = '''BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:all-day-1\nSUMMARY:Birthday\nDTSTART;VALUE=DATE:20260820\nDTEND;VALUE=DATE:20260821\nEND:VEVENT\nEND:VCALENDAR'''
    event = parse_vevents(payload)[0]
    assert event['start'] == '2026-08-20T00:00:00'
    assert event['allDay'] is True


def test_parse_calendar_collections_filters_non_calendar_resources():
    payload = '''<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav" xmlns:i="http://apple.com/ns/ical/">
  <d:response><d:href>/user/</d:href><d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat></d:response>
  <d:response><d:href>/user/personal/</d:href><d:propstat><d:prop><d:resourcetype><d:collection/><c:calendar/></d:resourcetype><d:displayname>Personal</d:displayname><i:calendar-color>#5b7cff</i:calendar-color></d:prop></d:propstat></d:response>
</d:multistatus>'''
    assert parse_calendar_collections(payload) == [{'href': '/user/personal/', 'name': 'Personal', 'color': '#5b7cff'}]


def writable_client() -> CalDAVClient:
    return CalDAVClient(
        Settings(caldav_base_url='https://dav.goreecloud.com', caldav_auth_mode='passthrough', caldav_write_enabled=True),
        ('synthetic-user', 'synthetic-password'),
    )


def sample_ics() -> str:
    return '''BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:test-1\r\nDTSTART:20260820T150000Z\r\nSUMMARY:Test\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n'''


def test_passthrough_write_mode_requires_both_flags():
    assert Settings(caldav_auth_mode='passthrough', caldav_write_enabled=True).writes_available is True
    assert Settings(caldav_auth_mode='service', caldav_write_enabled=True).writes_available is False
    assert Settings(caldav_auth_mode='passthrough', caldav_write_enabled=False).writes_available is False


def test_config_rejects_non_https_dav():
    with pytest.raises(ValueError, match='HTTPS'):
        Settings(caldav_base_url='http://dav.example.test')


def test_caldav_url_rejects_cross_origin_href():
    with pytest.raises(CalDAVError, match='outside the configured DAV origin'):
        writable_client()._url('https://example.invalid/users/a/calendar.ics')


def test_write_rejects_resource_outside_selected_calendar():
    with pytest.raises(CalDAVError, match='outside the selected calendar collection'):
        asyncio.run(writable_client().put_event('/user/personal/', '/user/other/event.ics', sample_ics(), create=True))


def test_update_requires_etag_before_network_request():
    with pytest.raises(CalDAVPreconditionRequired, match='ETag'):
        asyncio.run(writable_client().put_event('/user/personal/', '/user/personal/event.ics', sample_ics()))


def test_create_uses_if_none_match_star(monkeypatch):
    client = writable_client()
    captured = {}
    async def fake_request(method, url, body=None, **kwargs):
        captured.update(method=method, url=url, body=body, kwargs=kwargs)
        return SimpleNamespace(status_code=201, headers={'ETag': '"new-etag"'})
    monkeypatch.setattr(client, '_request', fake_request)
    etag = asyncio.run(client.put_event('/user/personal/', '/user/personal/new.ics', sample_ics(), create=True))
    assert etag == '"new-etag"'
    assert captured['kwargs']['extra_headers'] == {'If-None-Match': '*'}


def test_update_uses_if_match(monkeypatch):
    client = writable_client()
    captured = {}
    async def fake_request(method, url, body=None, **kwargs):
        captured.update(method=method, url=url, body=body, kwargs=kwargs)
        return SimpleNamespace(status_code=204, headers={'ETag': '"next-etag"'})
    monkeypatch.setattr(client, '_request', fake_request)
    asyncio.run(client.put_event('/user/personal/', '/user/personal/event.ics', sample_ics(), etag='"old-etag"'))
    assert captured['kwargs']['extra_headers'] == {'If-Match': '"old-etag"'}


def test_delete_requires_etag():
    with pytest.raises(CalDAVPreconditionRequired, match='ETag'):
        asyncio.run(writable_client().delete_event('/user/personal/', '/user/personal/event.ics', etag=None))


def test_precondition_failure_becomes_conflict(monkeypatch):
    client = writable_client()
    async def fake_request(method, url, body=None, **kwargs):
        return SimpleNamespace(status_code=412, headers={})
    monkeypatch.setattr(client, '_request', fake_request)
    with pytest.raises(CalDAVConflict, match='changed before the write completed'):
        asyncio.run(client.put_event('/user/personal/', '/user/personal/event.ics', sample_ics(), etag='"stale-etag"'))
