from dataclasses import dataclass
from os import getenv


def _env_bool(name: str, default: bool = False) -> bool:
    value = getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = getenv(name)
    value = default if raw is None else int(raw)
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    raw = getenv(name)
    value = default if raw is None else float(raw)
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


@dataclass(frozen=True)
class Settings:
    caldav_base_url: str = getenv("CALDAV_BASE_URL", "https://dav.goreecloud.com").rstrip("/")
    caldav_username: str | None = getenv("CALDAV_USERNAME")
    caldav_password: str | None = getenv("CALDAV_PASSWORD")
    caldav_auth_mode: str = getenv("CALDAV_AUTH_MODE", "passthrough").strip().lower()
    caldav_write_enabled: bool = _env_bool("CALDAV_WRITE_ENABLED", False)
    upstream_timeout_seconds: float = _env_float("UPSTREAM_TIMEOUT_SECONDS", 10.0, minimum=1.0, maximum=30.0)
    session_ttl_seconds: int = _env_int("SESSION_TTL_SECONDS", 28800, minimum=300, maximum=86400)
    max_sessions: int = _env_int("MAX_SESSIONS", 256, minimum=8, maximum=4096)
    secure_cookies: bool = _env_bool("SECURE_COOKIES", True)
    trust_proxy_headers: bool = _env_bool("TRUST_PROXY_HEADERS", False)
    log_level: str = getenv("LOG_LEVEL", "INFO").strip().upper()

    def __post_init__(self) -> None:
        if self.caldav_auth_mode not in {"passthrough", "service"}:
            raise ValueError("CALDAV_AUTH_MODE must be passthrough or service")
        if not self.caldav_base_url.startswith("https://"):
            raise ValueError("CALDAV_BASE_URL must use HTTPS")
        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL is invalid")

    @property
    def caldav_configured(self) -> bool:
        if self.caldav_auth_mode == "passthrough":
            return True
        return bool(self.caldav_username and self.caldav_password)

    @property
    def passthrough_auth_enabled(self) -> bool:
        return self.caldav_auth_mode == "passthrough"

    @property
    def writes_available(self) -> bool:
        return self.caldav_write_enabled and self.passthrough_auth_enabled


settings = Settings()
