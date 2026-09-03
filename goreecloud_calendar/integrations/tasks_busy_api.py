"""Least-privilege Calendar busy-time API boundary for GoreeCloud Tasks.

This module is intentionally framework-neutral. A deployment may bind
``dispatch_tasks_busy_time`` to the documented HTTP route while retaining its own server,
TLS, observability, and rate-control stack.

The development credential maps one GoreeCloud Tasks service caller to one explicitly
configured Calendar subject and a fixed set of Calendar collections. The caller cannot select
another subject or calendar through request data. This is a bounded development integration
mechanism, not a replacement for the required GoreeCloud Identity production contract.
"""

from __future__ import annotations

import json
import os
import secrets
import stat
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping

from goreecloud_calendar.auth import CalendarAuthorizationError, CalendarPrincipal
from goreecloud_calendar.http import HTTPResponse
from goreecloud_calendar.service import CalendarService

SCHEMA = "goreecloud.calendar.tasks-busy.v1"
VERSION = 1
DEFAULT_MAX_WINDOW_MINUTES = 31 * 24 * 60
ABSOLUTE_MAX_WINDOW_MINUTES = 62 * 24 * 60
_ALLOWED_QUERY_FIELDS = frozenset({"starts_at", "ends_at"})


@dataclass(frozen=True, slots=True)
class TasksBusyAPIConfiguration:
    """Validated deployment mapping for the GoreeCloud Tasks busy-time caller."""

    enabled: bool
    token: str = ""
    subject: str = ""
    calendar_hrefs: tuple[str, ...] = ()
    max_window_minutes: int = DEFAULT_MAX_WINDOW_MINUTES
    error: str | None = None


def _env_bool(value: str | None) -> bool:
    return bool(value and value.strip().lower() in {"1", "true", "yes", "on"})


def _load_protected_secret(path_value: str) -> str:
    path = Path(path_value)
    try:
        info = path.stat()
    except OSError as exc:
        raise ValueError("configured token file is unavailable") from exc
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("configured token path is not a regular file")
    if info.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise ValueError("configured token file permissions are too broad")
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ValueError("configured token file is unreadable") from exc


def load_tasks_busy_api_configuration(
    environment: Mapping[str, str] | None = None,
) -> TasksBusyAPIConfiguration:
    """Load the development service mapping without exposing reusable credentials."""

    env = os.environ if environment is None else environment
    enabled = _env_bool(env.get("CALENDAR_TASKS_BUSY_API_ENABLED"))
    if not enabled:
        return TasksBusyAPIConfiguration(enabled=False)

    errors: list[str] = []
    direct_token = env.get("CALENDAR_TASKS_BUSY_API_TOKEN", "").strip()
    token_file = env.get("CALENDAR_TASKS_BUSY_API_TOKEN_FILE", "").strip()
    token = ""
    if direct_token and token_file:
        errors.append("set only one Tasks busy API token source")
    elif token_file:
        try:
            token = _load_protected_secret(token_file)
        except ValueError as exc:
            errors.append(str(exc))
    else:
        token = direct_token

    if len(token) < 32 or len(token) > 512:
        errors.append("Tasks busy API token must contain 32 to 512 characters")

    subject = env.get("CALENDAR_TASKS_BUSY_API_SUBJECT", "").strip()
    if not subject or len(subject) > 200:
        errors.append("Tasks busy API subject must contain 1 to 200 characters")

    raw_hrefs = env.get("CALENDAR_TASKS_BUSY_API_CALENDAR_HREFS", "")
    calendar_hrefs = tuple(
        item.strip() for item in raw_hrefs.split(",") if item.strip()
    )
    if not calendar_hrefs:
        errors.append("at least one Tasks busy API calendar collection is required")
    elif len(calendar_hrefs) > 32:
        errors.append("Tasks busy API may authorize at most 32 calendar collections")
    elif len(set(calendar_hrefs)) != len(calendar_hrefs):
        errors.append("Tasks busy API calendar collections must be unique")
    else:
        for href in calendar_hrefs:
            if not href.startswith("/") or ".." in href or len(href) > 1000:
                errors.append("Tasks busy API calendar collection scope is invalid")
                break

    raw_max_window = env.get(
        "CALENDAR_TASKS_BUSY_API_MAX_WINDOW_MINUTES",
        str(DEFAULT_MAX_WINDOW_MINUTES),
    )
    try:
        max_window_minutes = int(raw_max_window)
    except (TypeError, ValueError):
        max_window_minutes = DEFAULT_MAX_WINDOW_MINUTES
        errors.append("Tasks busy API maximum window must be an integer")
    if not 60 <= max_window_minutes <= ABSOLUTE_MAX_WINDOW_MINUTES:
        errors.append(
            f"Tasks busy API maximum window must be between 60 and {ABSOLUTE_MAX_WINDOW_MINUTES} minutes"
        )

    return TasksBusyAPIConfiguration(
        enabled=True,
        token=token,
        subject=subject,
        calendar_hrefs=calendar_hrefs,
        max_window_minutes=max_window_minutes,
        error="; ".join(errors) if errors else None,
    )


def _json(
    status: int,
    payload: dict[str, object],
    *,
    extra_headers: tuple[tuple[str, str], ...] = (),
) -> HTTPResponse:
    headers = (
        ("Content-Type", "application/json; charset=utf-8"),
        ("Cache-Control", "private, no-store"),
        ("Vary", "Authorization"),
        *extra_headers,
    )
    return HTTPResponse(
        status=status,
        body=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers=headers,
    )


def _header(headers: Mapping[str, str], name: str) -> str:
    target = name.casefold()
    for key, value in headers.items():
        if key.casefold() == target:
            return value
    return ""


def _authenticated(headers: Mapping[str, str], config: TasksBusyAPIConfiguration) -> bool:
    authorization = _header(headers, "Authorization")
    scheme, separator, supplied_token = authorization.partition(" ")
    if not separator or scheme.casefold() != "bearer" or not supplied_token.strip():
        return False
    return secrets.compare_digest(supplied_token.strip(), config.token)


def _parse_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include timezone information")
    return parsed


def dispatch_tasks_busy_time(
    *,
    service: CalendarService,
    config: TasksBusyAPIConfiguration,
    method: str,
    headers: Mapping[str, str] | None = None,
    query: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> HTTPResponse:
    """Serve the minimized read-only busy-time projection for GoreeCloud Tasks.

    Expected HTTP binding: ``GET /api/v1/tasks/busy-time``. Authentication is evaluated
    before request fields. The configured subject and collection scope are server-side values;
    request data may contain only ``starts_at`` and ``ends_at``.
    """

    headers = headers or {}
    query = query or {}

    if not config.enabled:
        return _json(404, {"error": "not_found"})
    if config.error:
        return _json(503, {"error": "integration_unavailable"})
    if method.upper() != "GET":
        return _json(
            405,
            {"error": "method_not_allowed"},
            extra_headers=(("Allow", "GET"),),
        )
    if not _authenticated(headers, config):
        return _json(
            401,
            {"error": "authentication_required"},
            extra_headers=(("WWW-Authenticate", "Bearer"),),
        )

    if set(query) != _ALLOWED_QUERY_FIELDS:
        return _json(400, {"error": "invalid_request"})

    try:
        starts_at = _parse_timestamp(query.get("starts_at"), "starts_at")
        ends_at = _parse_timestamp(query.get("ends_at"), "ends_at")
        if ends_at <= starts_at:
            raise ValueError("busy window must have positive duration")
        if ends_at - starts_at > timedelta(minutes=config.max_window_minutes):
            raise ValueError("busy window exceeds configured maximum")

        principal = CalendarPrincipal(
            subject=config.subject,
            calendar_hrefs=config.calendar_hrefs,
            can_write=False,
        )
        payload = service.busy_time_for_calendars(
            principal=principal,
            calendar_hrefs=config.calendar_hrefs,
            starts_at=starts_at,
            ends_at=ends_at,
        )
    except CalendarAuthorizationError:
        return _json(403, {"error": "forbidden"})
    except ValueError:
        return _json(400, {"error": "invalid_request"})

    generated_at = now or datetime.now(timezone.utc)
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("now must include timezone information")

    # Repackage the existing Calendar busy projection under the peer-API contract without
    # revealing Calendar collection identifiers, subjects, event titles, descriptions, or
    # locations. Busy intervals are the complete approved data surface for this endpoint.
    return _json(
        200,
        {
            "schema": SCHEMA,
            "version": VERSION,
            "generated_at": generated_at.isoformat(),
            "range": payload["range"],
            "returned": payload["returned"],
            "busy": payload["busy"],
        },
    )
