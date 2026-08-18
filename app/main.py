from collections.abc import AsyncIterator
from datetime import date, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth import (
    SESSION_COOKIE,
    Session,
    SessionStore,
    authenticate,
    clear_session_cookie,
    require_csrf,
    require_session,
    set_session_cookie,
)
from .caldav import (
    CalDAVAuthenticationError,
    CalDAVClient,
    CalDAVConflict,
    CalDAVError,
    CalDAVPreconditionRequired,
)
from .config import settings
from .observability import WardveilMiddleware, configure_logging, emit_event

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
configure_logging(settings.log_level)
sessions = SessionStore(settings.session_ttl_seconds, settings.max_sessions)

app = FastAPI(
    title="GoreeCloud Calendar",
    version="0.2.0-rc1",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.add_middleware(WardveilMiddleware)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class EventWriteRequest(BaseModel):
    calendarHref: str = Field(min_length=1, max_length=2048)
    resourceHref: str = Field(min_length=1, max_length=2048)
    ical: str = Field(min_length=1, max_length=262144)
    etag: str | None = Field(default=None, max_length=512)


def current_session(request: Request) -> Session:
    return require_session(request, sessions)


async def current_client(session: Session = Depends(current_session)) -> AsyncIterator[CalDAVClient]:
    client = CalDAVClient(settings, (session.username, session.password))
    try:
        yield client
    finally:
        await client.aclose()


def invalidate_session(request: Request) -> None:
    sessions.delete(request.cookies.get(SESSION_COOKIE))


def upstream_error(exc: CalDAVError, request: Request) -> HTTPException:
    if isinstance(exc, CalDAVAuthenticationError):
        invalidate_session(request)
        return HTTPException(status_code=401, detail="Your calendar credentials are no longer accepted. Sign in again.")
    return HTTPException(status_code=502, detail="Calendar service is temporarily unavailable")


def mutation_error(exc: CalDAVError, request: Request) -> HTTPException:
    if isinstance(exc, CalDAVAuthenticationError):
        invalidate_session(request)
        return HTTPException(status_code=401, detail="Your calendar credentials are no longer accepted. Sign in again.")
    if isinstance(exc, CalDAVConflict):
        return HTTPException(status_code=409, detail="The event changed elsewhere. Reload before trying again.")
    if isinstance(exc, CalDAVPreconditionRequired):
        return HTTPException(status_code=428, detail=str(exc))
    return HTTPException(status_code=502, detail="The calendar service could not complete the change")


@app.get("/api/health")
async def health() -> dict[str, object]:
    return {"status": "ok"}


@app.get("/api/meta")
async def meta(request: Request) -> dict[str, object]:
    session = sessions.get(request.cookies.get(SESSION_COOKIE))
    return {
        "service": "goreecloud-calendar",
        "version": app.version,
        "authenticated": session is not None,
        "writeEnabled": settings.writes_available,
        "glazeUi": "1.0",
        "securityIdentity": "Wardveil Security by GoreeCloud",
        "csrfToken": session.csrf_token if session else None,
    }


@app.post("/api/session")
async def login(payload: LoginRequest, response: Response, request: Request) -> dict[str, object]:
    try:
        session_id, session = await authenticate(settings, sessions, payload.username, payload.password)
    except HTTPException:
        emit_event("auth.login.failed", request_id=request.state.request_id)
        raise
    set_session_cookie(response, settings, session_id)
    emit_event("auth.login.success", request_id=request.state.request_id)
    return {"authenticated": True, "csrfToken": session.csrf_token}


@app.delete("/api/session", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, session: Session = Depends(current_session)) -> Response:
    require_csrf(request, session)
    invalidate_session(request)
    clear_session_cookie(response, settings)
    emit_event("auth.logout", request_id=request.state.request_id)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@app.get("/api/calendars")
async def calendars(request: Request, client: CalDAVClient = Depends(current_client)) -> dict[str, object]:
    try:
        collections = await client.list_calendars()
    except CalDAVError as exc:
        raise upstream_error(exc, request) from exc
    return {
        "calendars": [{"id": item["href"], "name": item["name"], "color": item["color"]} for item in collections],
        "readOnly": not settings.writes_available,
    }


@app.get("/api/events")
async def events(
    request: Request,
    start: date = Query(...),
    end: date = Query(...),
    client: CalDAVClient = Depends(current_client),
) -> dict[str, object]:
    if end <= start:
        raise HTTPException(status_code=422, detail="end must be after start")
    if end - start > timedelta(days=93):
        raise HTTPException(status_code=422, detail="date range must not exceed 93 days")
    try:
        items = await client.list_events(start, end)
    except CalDAVError as exc:
        raise upstream_error(exc, request) from exc
    return {"events": items, "readOnly": not settings.writes_available}


@app.post("/api/events", status_code=status.HTTP_201_CREATED)
async def create_event(payload: EventWriteRequest, request: Request, session: Session = Depends(current_session)) -> dict[str, object]:
    if not settings.writes_available:
        raise HTTPException(status_code=403, detail="Calendar writes are disabled")
    require_csrf(request, session)
    client = CalDAVClient(settings, (session.username, session.password))
    try:
        etag = await client.put_event(payload.calendarHref, payload.resourceHref, payload.ical, create=True)
    except CalDAVError as exc:
        raise mutation_error(exc, request) from exc
    finally:
        await client.aclose()
    emit_event("calendar.event.create", request_id=request.state.request_id)
    return {"etag": etag}


@app.put("/api/events")
async def update_event(payload: EventWriteRequest, request: Request, session: Session = Depends(current_session)) -> dict[str, object]:
    if not settings.writes_available:
        raise HTTPException(status_code=403, detail="Calendar writes are disabled")
    require_csrf(request, session)
    client = CalDAVClient(settings, (session.username, session.password))
    try:
        etag = await client.put_event(payload.calendarHref, payload.resourceHref, payload.ical, etag=payload.etag)
    except CalDAVError as exc:
        raise mutation_error(exc, request) from exc
    finally:
        await client.aclose()
    emit_event("calendar.event.update", request_id=request.state.request_id)
    return {"etag": etag}


@app.delete("/api/events", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    request: Request,
    calendar_href: str = Query(..., alias="calendarHref", max_length=2048),
    resource_href: str = Query(..., alias="resourceHref", max_length=2048),
    etag: str = Query(..., max_length=512),
    session: Session = Depends(current_session),
) -> Response:
    if not settings.writes_available:
        raise HTTPException(status_code=403, detail="Calendar writes are disabled")
    require_csrf(request, session)
    client = CalDAVClient(settings, (session.username, session.password))
    try:
        await client.delete_event(calendar_href, resource_href, etag=etag)
    except CalDAVError as exc:
        raise mutation_error(exc, request) from exc
    finally:
        await client.aclose()
    emit_event("calendar.event.delete", request_id=request.state.request_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/{path:path}")
async def spa(path: str) -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
