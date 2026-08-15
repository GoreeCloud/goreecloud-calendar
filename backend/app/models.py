from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=2048)


class SessionResponse(BaseModel):
    username: str
    csrf_token: str
    write_enabled: bool


class CalendarSummary(BaseModel):
    href: str
    display_name: str
    description: str = ""
    color: str | None = None


class EventSummary(BaseModel):
    href: str
    etag: str | None = None
    calendar_href: str
    uid: str
    summary: str
    description: str = ""
    location: str = ""
    start: str
    end: str | None = None
    all_day: bool = False
    recurring: bool = False


class EventWriteRequest(BaseModel):
    calendar_href: str
    summary: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=20000)
    location: str = Field(default="", max_length=2000)
    start: str
    end: str | None = None
    all_day: bool = False
    etag: str | None = None

    @field_validator("summary")
    @classmethod
    def normalize_summary(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Summary is required.")
        return value

    @model_validator(mode="after")
    def validate_times(self) -> "EventWriteRequest":
        if self.all_day:
            start_date = date.fromisoformat(self.start)
            if self.end:
                end_date = date.fromisoformat(self.end)
                if end_date <= start_date:
                    raise ValueError("All-day end date must be after the start date.")
        else:
            start_dt = datetime.fromisoformat(self.start.replace("Z", "+00:00"))
            if start_dt.tzinfo is None:
                raise ValueError("Timed event start must include a timezone offset.")
            if self.end:
                end_dt = datetime.fromisoformat(self.end.replace("Z", "+00:00"))
                if end_dt.tzinfo is None:
                    raise ValueError("Timed event end must include a timezone offset.")
                if end_dt <= start_dt:
                    raise ValueError("Event end must be after the start.")
        return self


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    environment: str
