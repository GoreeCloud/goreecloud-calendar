import pytest

from app.config import Settings


def test_production_requires_https_and_secure_cookie(monkeypatch):
    monkeypatch.setenv("GOREECLOUD_CALENDAR_ENVIRONMENT", "production")
    monkeypatch.setenv("GOREECLOUD_CALENDAR_CALDAV_BASE_URL", "http://dav.goreecloud.com")
    monkeypatch.setenv("GOREECLOUD_CALENDAR_SESSION_COOKIE_SECURE", "true")

    with pytest.raises(RuntimeError, match="HTTPS"):
        Settings.from_env()


def test_trusted_hosts_reject_wildcard(monkeypatch):
    monkeypatch.setenv("GOREECLOUD_CALENDAR_TRUSTED_HOSTS", "*")

    with pytest.raises(RuntimeError, match="Trusted hosts"):
        Settings.from_env()


def test_session_idle_timeout_cannot_exceed_ttl(monkeypatch):
    monkeypatch.setenv("GOREECLOUD_CALENDAR_SESSION_TTL_SECONDS", "60")
    monkeypatch.setenv("GOREECLOUD_CALENDAR_SESSION_IDLE_SECONDS", "61")

    with pytest.raises(RuntimeError, match="idle timeout"):
        Settings.from_env()


def test_login_identity_limit_must_be_positive(monkeypatch):
    monkeypatch.setenv("GOREECLOUD_CALENDAR_LOGIN_MAX_IDENTITIES", "0")
    with pytest.raises(RuntimeError, match="login max identities"):
        Settings.from_env()
