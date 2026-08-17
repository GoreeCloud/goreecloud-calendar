from fastapi.testclient import TestClient

from app.caldav import parse_calendar_collections, parse_vevents
from app.main import app


def test_health_reports_read_only():
    response = TestClient(app).get('/api/health')
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'ok'
    assert body['writeEnabled'] is False


def test_events_rejects_invalid_range():
    response = TestClient(app).get('/api/events?start=2026-08-20&end=2026-08-19')
    assert response.status_code == 422


def test_events_rejects_oversized_range():
    response = TestClient(app).get('/api/events?start=2026-01-01&end=2026-06-01')
    assert response.status_code == 422


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
    events = parse_vevents(payload)
    event = events[0]
    assert event['uid'] == 'weekly-1'
    assert event['start'] == '2026-08-20T09:00:00'
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
  <d:response>
    <d:href>/user/</d:href>
    <d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype><d:displayname>User</d:displayname></d:prop></d:propstat>
  </d:response>
  <d:response>
    <d:href>/user/personal/</d:href>
    <d:propstat><d:prop><d:resourcetype><d:collection/><c:calendar/></d:resourcetype><d:displayname>Personal</d:displayname><i:calendar-color>#5b7cff</i:calendar-color></d:prop></d:propstat>
  </d:response>
</d:multistatus>'''
    assert parse_calendar_collections(payload) == [
        {'href': '/user/personal/', 'name': 'Personal', 'color': '#5b7cff'}
    ]
