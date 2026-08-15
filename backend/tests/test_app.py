from fastapi.testclient import TestClient

from app.main import app


def test_liveness_has_restrictive_browser_headers():
    with TestClient(app) as client:
        response = client.get("/api/health/live")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cross-origin-opener-policy"] == "same-origin"
    assert response.headers["cross-origin-resource-policy"] == "same-origin"
    assert "default-src 'self'" in response.headers["content-security-policy"]


def test_unknown_host_is_rejected():
    with TestClient(app) as client:
        response = client.get(
            "/api/health/live",
            headers={"host": "not-approved.example"},
        )

    assert response.status_code == 400
