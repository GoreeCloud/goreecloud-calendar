from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class Settings:
    caldav_base_url: str = getenv("CALDAV_BASE_URL", "https://dav.goreecloud.com").rstrip("/")
    caldav_username: str | None = getenv("CALDAV_USERNAME")
    caldav_password: str | None = getenv("CALDAV_PASSWORD")
    upstream_timeout_seconds: float = float(getenv("UPSTREAM_TIMEOUT_SECONDS", "10"))

    @property
    def caldav_configured(self) -> bool:
        return bool(self.caldav_username and self.caldav_password)


settings = Settings()
