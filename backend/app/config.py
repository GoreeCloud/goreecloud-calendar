from __future__ import annotations

from dataclasses import dataclass
import os
from urllib.parse import urlparse


def _bool_env(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a number.") from exc


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str
    caldav_base_url: str
    caldav_timeout_seconds: float
    caldav_max_query_days: int
    session_ttl_seconds: int
    session_idle_seconds: int
    session_max_total: int
    session_max_per_user: int
    session_cookie_secure: bool
    write_enabled: bool
    trusted_hosts: tuple[str, ...]
    login_max_failures: int
    login_window_seconds: int
    login_lockout_seconds: int

    @classmethod
    def from_env(cls) -> "Settings":
        environment = os.getenv("GOREECLOUD_CALENDAR_ENVIRONMENT", "development").strip().lower()
        caldav_base_url = os.getenv(
            "GOREECLOUD_CALENDAR_CALDAV_BASE_URL", "https://dav.goreecloud.com"
        ).strip().rstrip("/")
        trusted_hosts = tuple(
            item.strip()
            for item in os.getenv(
                "GOREECLOUD_CALENDAR_TRUSTED_HOSTS",
                "localhost,127.0.0.1,calendar.goreecloud.com",
            ).split(",")
            if item.strip()
        )
        settings = cls(
            environment=environment,
            caldav_base_url=caldav_base_url,
            caldav_timeout_seconds=_float_env("GOREECLOUD_CALENDAR_CALDAV_TIMEOUT_SECONDS", 15.0),
            caldav_max_query_days=_int_env("GOREECLOUD_CALENDAR_CALDAV_MAX_QUERY_DAYS", 62),
            session_ttl_seconds=_int_env("GOREECLOUD_CALENDAR_SESSION_TTL_SECONDS", 28800),
            session_idle_seconds=_int_env("GOREECLOUD_CALENDAR_SESSION_IDLE_SECONDS", 3600),
            session_max_total=_int_env("GOREECLOUD_CALENDAR_SESSION_MAX_TOTAL", 200),
            session_max_per_user=_int_env("GOREECLOUD_CALENDAR_SESSION_MAX_PER_USER", 5),
            session_cookie_secure=_bool_env("GOREECLOUD_CALENDAR_SESSION_COOKIE_SECURE", "true"),
            write_enabled=_bool_env("GOREECLOUD_CALENDAR_CALDAV_WRITE_ENABLED", "false"),
            trusted_hosts=trusted_hosts,
            login_max_failures=_int_env("GOREECLOUD_CALENDAR_LOGIN_MAX_FAILURES", 8),
            login_window_seconds=_int_env("GOREECLOUD_CALENDAR_LOGIN_WINDOW_SECONDS", 300),
            login_lockout_seconds=_int_env("GOREECLOUD_CALENDAR_LOGIN_LOCKOUT_SECONDS", 900),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.environment not in {"development", "test", "production"}:
            raise RuntimeError("GOREECLOUD_CALENDAR_ENVIRONMENT must be development, test, or production.")

        parsed = urlparse(self.caldav_base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RuntimeError("CalDAV base URL must be an absolute HTTP(S) URL.")
        if parsed.username or parsed.password:
            raise RuntimeError("CalDAV base URL must not contain embedded credentials.")
        if parsed.query or parsed.fragment:
            raise RuntimeError("CalDAV base URL must not contain a query string or fragment.")

        numeric_positive = {
            "CalDAV timeout": self.caldav_timeout_seconds,
            "CalDAV max query days": self.caldav_max_query_days,
            "session TTL": self.session_ttl_seconds,
            "session idle timeout": self.session_idle_seconds,
            "session max total": self.session_max_total,
            "session max per user": self.session_max_per_user,
            "login max failures": self.login_max_failures,
            "login window": self.login_window_seconds,
            "login lockout": self.login_lockout_seconds,
        }
        for label, value in numeric_positive.items():
            if value <= 0:
                raise RuntimeError(f"{label} must be greater than zero.")

        if self.session_idle_seconds > self.session_ttl_seconds:
            raise RuntimeError("Session idle timeout cannot exceed the absolute session TTL.")
        if self.session_max_per_user > self.session_max_total:
            raise RuntimeError("Per-user session limit cannot exceed the global session limit.")
        if not self.trusted_hosts or "*" in self.trusted_hosts:
            raise RuntimeError("Trusted hosts must be explicit and cannot include '*'.")

        if self.environment == "production":
            if parsed.scheme != "https":
                raise RuntimeError("Production CalDAV must use HTTPS.")
            if not self.session_cookie_secure:
                raise RuntimeError("Production sessions require Secure cookies.")
            if "calendar.goreecloud.com" not in self.trusted_hosts:
                raise RuntimeError("Production trusted hosts must include calendar.goreecloud.com.")
