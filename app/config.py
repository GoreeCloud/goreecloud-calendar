from dataclasses import dataclass
from os import getenv


def _env_bool(name: str, default: bool = False) -> bool:
    value = getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    caldav_base_url: str = getenv("CALDAV_BASE_URL", "https://dav.goreecloud.com").rstrip("/")
    caldav_username: str | None = getenv("CALDAV_USERNAME")
    caldav_password: str | None = getenv("CALDAV_PASSWORD")
    caldav_auth_mode: str = getenv("CALDAV_AUTH_MODE", "service").strip().lower()
    caldav_write_enabled: bool = _env_bool("CALDAV_WRITE_ENABLED", False)
    upstream_timeout_seconds: float = float(getenv("UPSTREAM_TIMEOUT_SECONDS", "10"))

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
