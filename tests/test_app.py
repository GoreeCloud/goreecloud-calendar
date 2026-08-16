from datetime import date

from fastapi.testclient import TestClient

from app.caldav import parse_vevents
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
    }]
