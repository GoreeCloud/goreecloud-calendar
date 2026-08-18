from __future__ import annotations

import json
import logging
import re
import time
from secrets import token_hex

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{8,64}$")
logger = logging.getLogger("goreecloud.calendar")


def configure_logging(level: str) -> None:
    logging.basicConfig(level=getattr(logging, level), format="%(message)s")


def emit_event(event: str, **fields: object) -> None:
    record = {"event": event, "service": "goreecloud-calendar", **fields}
    logger.info(json.dumps(record, separators=(",", ":"), sort_keys=True))


class WardveilMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        supplied = request.headers.get("X-Request-ID", "")
        request_id = supplied if REQUEST_ID_RE.fullmatch(supplied) else token_hex(16)
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            emit_event("http.error", request_id=request_id, method=request.method, path=request.url.path)
            response = JSONResponse(
                status_code=500,
                content={"detail": "Unexpected server error", "requestId": request_id},
            )
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        if request.url.path != "/api/health" or response.status_code >= 400:
            emit_event(
                "http.request",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=duration_ms,
            )
        self._headers(response, request_id)
        return response

    @staticmethod
    def _headers(response: Response, request_id: str) -> None:
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Wardveil-Security"] = "Wardveil Security by GoreeCloud"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Origin-Agent-Cluster"] = "?1"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'; "
            "object-src 'none'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'"
        )
        response.headers["Cache-Control"] = "no-store"
