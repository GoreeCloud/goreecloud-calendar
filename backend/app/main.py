from __future__ import annotations

from datetime import datetime
from pathlib import Path
import os

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Response, status
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .caldav import (
    CalDavAuthenticationError,
    CalDavAuthorizationError,
    CalDavClient,
    CalDavConflict,
    CalDavError,
    CalDavNotFound,
    CalDavSettings,
)
from .models import (
    CalendarSummary,
    EventSummary,
    EventWriteRequest,
    HealthResponse,
    LoginRequest,
    SessionResponse,
)
from .session import SessionRecord, SessionStore


SERVICE = "goreecloud-calendar"
ENVIRONMENT = os.getenv("GOREECLOUD_CALENDAR_ENVIRONMENT", "development").strip()
CALDAV_BASE_URL = os.getenv(
    "GOREECLOUD_CALENDAR_CALDAV_BASE_URL", "https://dav.goreecloud.com"
).strip()
CALDAV_TIMEOUT_SECONDS = float(
    os.getenv("GOREECLOUD_CALENDAR_CALDAV_TIMEOUT_SECONDS", "15")
)
SESSION_TTL_SECONDS = int(
    os.getenv("GOREECLOUD_CALENDAR_SESSION_TTL_SECONDS", "28800")
)
SESSION_COOKIE_SECURE = os.getenv(
    "GOREECLOUD_CALENDAR_SESSION_COOKIE_SECURE", "true"
).strip().lower() in {"1", "true", "yes", "on"}
WRITE_ENABLED = os.getenv(
    "GOREECLOUD_CALENDAR_CALDAV_WRITE_ENABLED", "false"
).strip().lower() in {"1", "true", "yes", "on"}
TRUSTED_HOSTS = [
    item.strip()
    for item in os.getenv(
        "GOREECLOUD_CALENDAR_TRUSTED_HOSTS",
        "localhost,127.0.0.1,calendar.goreecloud.com",
    ).split(",")
    if item.strip()
]
COOKIE_NAME = "goreecloud_calendar_session"

STATIC_ROOT = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(
    title="GoreeCloud Calendar",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=TRUSTED_HOSTS)
sessions = SessionStore(SESSION_TTL_SECONDS)
dav_settings = CalDavSettings(
    base_url=CALDAV_BASE_URL,
    timeout_seconds=CALDAV_TIMEOUT_SECONDS,
)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
    )
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "object-src 'none'; "
        "base-uri 'none'; "
        "frame-ancestors 'none'; "
        "form-action 'self'"
    )
    return response


def client_for(record: SessionRecord) -> CalDavClient:
    return CalDavClient(
        dav_settings,
        username=record.username,
        password=record.password,
    )


def current_session(
    session_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> SessionRecord:
    record = sessions.get(session_token)
    if record is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return record


def require_csrf(
    record: SessionRecord = Depends(current_session),
    csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> SessionRecord:
    if not csrf_token or csrf_token != record.csrf_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed.",
        )
    return record


def require_write_enabled() -> None:
    if not WRITE_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CalDAV writes are disabled by the GoreeCloud Calendar safety gate.",
        )


def map_dav_error(exc: CalDavError) -> HTTPException:
    if isinstance(exc, CalDavAuthenticationError):
        return HTTPException(status_code=401, detail=str(exc))
    if isinstance(exc, CalDavAuthorizationError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, CalDavNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, CalDavConflict):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=502, detail=str(exc))


@app.get("/api/health/live", response_model=HealthResponse)
async def health_live() -> HealthResponse:
    return HealthResponse(status="ok", service=SERVICE, environment=ENVIRONMENT)


@app.get("/api/health/ready", response_model=HealthResponse)
async def health_ready() -> HealthResponse:
    if not CALDAV_BASE_URL:
        raise HTTPException(status_code=503, detail="CalDAV base URL is not configured.")
    return HealthResponse(status="ok", service=SERVICE, environment=ENVIRONMENT)


@app.post("/api/auth/login", response_model=SessionResponse)
async def login(payload: LoginRequest, response: Response) -> SessionResponse:
    client = CalDavClient(
        dav_settings,
        username=payload.username,
        password=payload.password,
    )
    try:
        await client.validate_credentials()
    except CalDavError as exc:
        raise map_dav_error(exc) from exc

    record = sessions.create(username=payload.username, password=payload.password)
    response.set_cookie(
        COOKIE_NAME,
        record.token,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="strict",
        max_age=SESSION_TTL_SECONDS,
        path="/",
    )
    return SessionResponse(
        username=record.username,
        csrf_token=record.csrf_token,
        write_enabled=WRITE_ENABLED,
    )


@app.get("/api/auth/me", response_model=SessionResponse)
async def auth_me(record: SessionRecord = Depends(current_session)) -> SessionResponse:
    return SessionResponse(
        username=record.username,
        csrf_token=record.csrf_token,
        write_enabled=WRITE_ENABLED,
    )


@app.post("/api/auth/logout", status_code=204)
async def logout(
    response: Response,
    record: SessionRecord = Depends(require_csrf),
    session_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> Response:
    sessions.delete(session_token)
    response.delete_cookie(COOKIE_NAME, path="/")
    response.status_code = 204
    return response


@app.get("/api/calendars", response_model=list[CalendarSummary])
async def list_calendars(
    record: SessionRecord = Depends(current_session),
) -> list[CalendarSummary]:
    try:
        return await client_for(record).discover_calendars()
    except CalDavError as exc:
        raise map_dav_error(exc) from exc


@app.get("/api/events", response_model=list[EventSummary])
async def list_events(
    calendar_href: str,
    start: datetime,
    end: datetime,
    record: SessionRecord = Depends(current_session),
) -> list[EventSummary]:
    try:
        return await client_for(record).list_events(
            calendar_href, start=start, end=end
        )
    except (CalDavError, ValueError) as exc:
        if isinstance(exc, CalDavError):
            raise map_dav_error(exc) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/events", response_model=EventSummary, status_code=201)
async def create_event(
    payload: EventWriteRequest,
    record: SessionRecord = Depends(require_csrf),
) -> EventSummary:
    require_write_enabled()
    try:
        return await client_for(record).create_event(payload)
    except CalDavError as exc:
        raise map_dav_error(exc) from exc


@app.put("/api/events", response_model=EventSummary)
async def update_event(
    event_href: str,
    payload: EventWriteRequest,
    record: SessionRecord = Depends(require_csrf),
) -> EventSummary:
    require_write_enabled()
    try:
        return await client_for(record).update_event(event_href, payload)
    except CalDavError as exc:
        raise map_dav_error(exc) from exc


@app.delete("/api/events", status_code=204)
async def delete_event(
    event_href: str,
    etag: str,
    record: SessionRecord = Depends(require_csrf),
) -> Response:
    require_write_enabled()
    try:
        await client_for(record).delete_event(event_href, etag=etag)
    except CalDavError as exc:
        raise map_dav_error(exc) from exc
    return Response(status_code=204)


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_ROOT / "index.html")


app.mount("/assets", StaticFiles(directory=STATIC_ROOT), name="assets")
