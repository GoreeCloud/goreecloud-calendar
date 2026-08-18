from datetime import date, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles

from .caldav import CalDAVClient, CalDAVError
from .config import settings

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
security = HTTPBasic(auto_error=False)

app = FastAPI(
    title="GoreeCloud Calendar",
    version="0.1.0-dev",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def caldav_client(
    credentials: HTTPBasicCredentials | None = Depends(security),
) -> CalDAVClient:
    if settings.passthrough_auth_enabled:
        if credentials is None or not credentials.username or not credentials.password:
            raise HTTPException(
                status_code=401,
                detail="Calendar authentication is required",
                headers={"WWW-Authenticate": 'Basic realm="GoreeCloud Calendar"'},
            )
        return CalDAVClient(settings, (credentials.username, credentials.password))
    return CalDAVClient(settings)


@app.get("/api/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "goreecloud-calendar",
        "caldavConfigured": settings.caldav_configured,
        "authMode": settings.caldav_auth_mode,
        "writeEnabled": settings.writes_available,
    }


@app.get("/api/calendars")
async def calendars(client: CalDAVClient = Depends(caldav_client)) -> dict[str, object]:
    try:
        collections = await client.list_calendars()
    except CalDAVError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "calendars": [
            {
                "id": item["href"],
                "name": item["name"],
                "color": item["color"],
            }
            for item in collections
        ],
        "readOnly": not settings.writes_available,
    }


@app.get("/api/events")
async def events(
    start: date = Query(...),
    end: date = Query(...),
    client: CalDAVClient = Depends(caldav_client),
) -> dict[str, object]:
    if end <= start:
        raise HTTPException(status_code=422, detail="end must be after start")
    if end - start > timedelta(days=93):
        raise HTTPException(status_code=422, detail="date range must not exceed 93 days")
    try:
        items = await client.list_events(start, end)
    except CalDAVError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"events": items, "readOnly": not settings.writes_available}


@app.get("/{path:path}")
async def spa(path: str) -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
