"""Dependency-free JSON HTTP adapter for the Calendar runtime service.

This module is intentionally framework-neutral. It converts already-authenticated request
context into typed service calls. ``secure_dispatch`` additionally applies trusted browser
origin, CSRF, and optional rate-limit controls before requests reach the application service.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from goreecloud_calendar.auth import CalendarAuthorizationError, CalendarPrincipal
from goreecloud_calendar.events import CalendarEvent, CalendarEventError
from goreecloud_calendar.security import (
    CalendarRequestSecurityError,
    InMemoryRateLimiter,
    TrustedRequestContext,
    enforce_browser_request,
)
from goreecloud_calendar.service import CalendarService


@dataclass(frozen=True, slots=True)
class HTTPResponse:
    status: int
    body: bytes
    headers: tuple[tuple[str, str], ...] = (("Content-Type", "application/json; charset=utf-8"),)


def _json(status: int, payload: dict[str, Any]) -> HTTPResponse:
    return HTTPResponse(status=status, body=json.dumps(payload, separators=(",", ":")).encode("utf-8"))


def _parse_dt(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} is required")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include timezone information")
    return parsed


def _parse_date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"{field} is required")
    return date.fromisoformat(value)


def dispatch(
    *,
    service: CalendarService,
    principal: CalendarPrincipal,
    method: str,
    path: str,
    query: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
) -> HTTPResponse:
    """Dispatch the versioned Calendar API for an already-authorized principal."""

    query = query or {}
    payload = payload or {}
    try:
        calendar_href = query.get("calendar") or payload.get("calendar")
        if not isinstance(calendar_href, str):
            raise ValueError("calendar is required")

        if method == "GET" and path == "/api/v1/events":
            anchor = _parse_date(query.get("anchor"), "anchor")
            view = query.get("view", "month")
            timezone_name = query.get("timezone", "UTC")
            return _json(200, service.list_events(
                principal=principal,
                calendar_href=calendar_href,
                view=view,
                anchor=anchor,
                timezone_name=timezone_name,
            ))

        if method == "GET" and path == "/api/v1/busy-time":
            starts_at = _parse_dt(query.get("starts_at"), "starts_at")
            ends_at = _parse_dt(query.get("ends_at"), "ends_at")
            return _json(200, service.busy_time(
                principal=principal,
                calendar_href=calendar_href,
                starts_at=starts_at,
                ends_at=ends_at,
            ))

        if method == "PUT" and path == "/api/v1/events":
            event = CalendarEvent(
                uid=str(payload.get("uid", "")),
                title=str(payload.get("title", "")),
                starts_at=_parse_dt(payload.get("starts_at"), "starts_at"),
                ends_at=_parse_dt(payload.get("ends_at"), "ends_at"),
                description=str(payload.get("description", "")),
                location=str(payload.get("location", "")),
                all_day=bool(payload.get("all_day", False)),
                calendar_href=calendar_href,
                etag=payload.get("etag") if isinstance(payload.get("etag"), str) else None,
            )
            saved = service.save_event(
                principal=principal, calendar_href=calendar_href, event=event
            )
            return _json(200, {
                "schema": "goreecloud.calendar.event-mutation.v1",
                "version": 1,
                "event": {
                    "uid": saved.uid,
                    "calendar_href": saved.calendar_href,
                    "etag": saved.etag,
                },
            })

        if method == "DELETE" and path == "/api/v1/events":
            event_href = payload.get("event_href")
            etag = payload.get("etag")
            if not isinstance(event_href, str) or not isinstance(etag, str):
                raise ValueError("event_href and etag are required")
            service.delete_event(
                principal=principal,
                calendar_href=calendar_href,
                event_href=event_href,
                etag=etag,
            )
            return _json(200, {"schema": "goreecloud.calendar.event-mutation.v1", "version": 1, "deleted": True})

        return _json(404, {"error": "not_found"})
    except CalendarAuthorizationError:
        return _json(403, {"error": "forbidden"})
    except (CalendarEventError, ValueError):
        return _json(400, {"error": "invalid_request"})


def secure_dispatch(
    *,
    service: CalendarService,
    principal: CalendarPrincipal,
    request_context: TrustedRequestContext,
    method: str,
    path: str,
    query: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    rate_limiter: InMemoryRateLimiter | None = None,
) -> HTTPResponse:
    """Apply server-derived browser security controls, then dispatch the Calendar API.

    Rate limiting uses the authenticated principal subject rather than request content. Security
    failures return a deliberately low-detail response so rejected requests do not reveal which
    trust check failed.
    """

    try:
        enforce_browser_request(
            context=request_context,
            method=method,
            rate_limiter=rate_limiter,
            rate_key=principal.subject if rate_limiter is not None else None,
        )
    except CalendarRequestSecurityError:
        return _json(403, {"error": "request_rejected"})
    return dispatch(
        service=service,
        principal=principal,
        method=method,
        path=path,
        query=query,
        payload=payload,
    )
