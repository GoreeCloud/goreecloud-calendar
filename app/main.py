from datetime import date, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .caldav import CalDAVClient, CalDAVError
from .config import settings

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="GoreeCloud Calendar",
    version="0.1.0-dev",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/api/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "goreecloud-calendar",
        "caldavConfigured": settings.caldav_configured,
        "writeEnabled": False,
    }


@app.get("/api/events")
async def events(
    start: date = Query(...),
    end: date = Query(...),
) -> dict[str, object]:
    if end <= start:
        raise HTTPException(status_code=422, detail="end must be after start")
    if end - start > timedelta(days=93):
        raise HTTPException(status_code=422, detail="date range must not exceed 93 days")
    try:
        items = await CalDAVClient(settings).list_events(start, end)
    except CalDAVError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"events": items, "readOnly": True}


@app.get("/{path:path}")
async def spa(path: str) -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
