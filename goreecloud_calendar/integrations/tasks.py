"""Strict first-party consumer for the GoreeCloud Tasks Calendar API."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

SCHEMA = "goreecloud.tasks.calendar-projections.v1"
VERSION = 1
SOURCE_APPLICATION = "goreecloud-tasks"
MAX_WINDOW = timedelta(days=93)
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class TasksProjectionError(RuntimeError):
    """Raised when Tasks cannot provide a trustworthy Calendar projection."""


class TasksConflictError(TasksProjectionError):
    """Raised when a Tasks mutation conflicts with a newer authoritative revision."""

    def __init__(
        self,
        message: str,
        *,
        current_revision: datetime | None = None,
    ):
        super().__init__(message)
        self.current_revision = current_revision


@dataclass(frozen=True)
class TaskProjection:
    id: int
    title: str
    due_at: datetime
    priority_value: int
    priority_label: str
    status_value: str
    status_label: str
    recurrence_value: str
    recurrence_label: str
    project_id: int | None
    project_name: str | None
    updated_at: datetime
    revision: datetime
    source_application: str | None
    source_api_version: int | None
    authoritative_url: str | None


def _parse_datetime(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise TasksProjectionError(f"{field} must be a non-empty timestamp string.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise TasksProjectionError(f"{field} is not a valid ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None:
        raise TasksProjectionError(f"{field} must include timezone information.")
    return parsed


def _require_dict(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TasksProjectionError(f"{field} must be an object.")
    return value


def _require_positive_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise TasksProjectionError(f"{field} must be a positive integer.")
    return value


def _validate_endpoint_inputs(
    *,
    base_url: str,
    token: str,
    timeout_seconds: float,
) -> tuple[str, str]:
    base = base_url.strip()
    if not base:
        raise TasksProjectionError("Tasks base URL is required.")
    parsed = urlparse(base)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise TasksProjectionError("Tasks base URL must be an absolute HTTP(S) URL.")
    if len(token.strip()) < 32:
        raise TasksProjectionError("Tasks integration token is invalid.")
    if timeout_seconds <= 0:
        raise TasksProjectionError("timeout_seconds must be greater than zero.")
    return base.rstrip("/"), token.strip()


def _require_aware_datetime(value: Any, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise TasksProjectionError(f"{field} must be a datetime.")
    if value.tzinfo is None:
        raise TasksProjectionError(f"{field} must include timezone information.")
    return value


def _validate_window(
    start: datetime | None,
    end: datetime | None,
) -> tuple[datetime | None, datetime | None]:
    if start is None and end is None:
        return None, None
    if start is None or end is None:
        raise TasksProjectionError("start and end must be provided together.")
    start = _require_aware_datetime(start, "start")
    end = _require_aware_datetime(end, "end")
    if end <= start:
        raise TasksProjectionError("end must be later than start.")
    if end - start > MAX_WINDOW:
        raise TasksProjectionError("The Tasks projection window cannot exceed 93 days.")
    return start, end


def _validate_task_id(task_id: int) -> int:
    return _require_positive_int(task_id, "task_id")


def _validate_authoritative_url(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise TasksProjectionError(f"{field} must be a non-empty absolute URL.")
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise TasksProjectionError(f"{field} must be a non-empty absolute URL.")
    return value.strip()


def _parse_projection_task(
    raw_task: Any,
    field: str,
    *,
    require_extended: bool,
) -> TaskProjection:
    task = _require_dict(raw_task, field)
    task_id = _require_positive_int(task.get("id"), f"{field}.id")

    title = task.get("title")
    if not isinstance(title, str) or not title.strip():
        raise TasksProjectionError(f"{field}.title must be non-empty.")

    priority = _require_dict(task.get("priority"), f"{field}.priority")
    status = _require_dict(task.get("status"), f"{field}.status")
    recurrence = _require_dict(task.get("recurrence"), f"{field}.recurrence")

    priority_value = priority.get("value")
    if not isinstance(priority_value, int) or isinstance(priority_value, bool):
        raise TasksProjectionError(f"{field}.priority.value must be an integer.")

    priority_label = priority.get("label")
    status_value = status.get("value")
    status_label = status.get("label")
    recurrence_value = recurrence.get("value")
    recurrence_label = recurrence.get("label")
    string_fields = {
        "priority.label": priority_label,
        "status.value": status_value,
        "status.label": status_label,
        "recurrence.value": recurrence_value,
        "recurrence.label": recurrence_label,
    }
    for field_name, value in string_fields.items():
        if not isinstance(value, str) or not value.strip():
            raise TasksProjectionError(f"{field}.{field_name} must be non-empty.")

    project = task.get("project")
    project_id: int | None = None
    project_name: str | None = None
    if project is not None:
        project_obj = _require_dict(project, f"{field}.project")
        project_id = _require_positive_int(
            project_obj.get("id"),
            f"{field}.project.id",
        )
        project_name = project_obj.get("name")
        if not isinstance(project_name, str) or not project_name.strip():
            raise TasksProjectionError(f"{field}.project.name must be non-empty.")

    updated_at = _parse_datetime(task.get("updated_at"), f"{field}.updated_at")

    source_application: str | None = None
    source_api_version: int | None = None
    source = task.get("source")
    if source is not None:
        source_obj = _require_dict(source, f"{field}.source")
        source_application = source_obj.get("application")
        source_api_version = source_obj.get("api_version")
        if source_application != SOURCE_APPLICATION:
            raise TasksProjectionError(f"{field}.source.application is unsupported.")
        if source_api_version != VERSION:
            raise TasksProjectionError(f"{field}.source.api_version is unsupported.")
    elif require_extended:
        raise TasksProjectionError(f"{field}.source is required.")

    authoritative_url = _validate_authoritative_url(
        task.get("authoritative_url"),
        f"{field}.authoritative_url",
    )
    if require_extended and authoritative_url is None:
        raise TasksProjectionError(f"{field}.authoritative_url is required.")

    revision_raw = task.get("revision")
    if revision_raw is None:
        if require_extended:
            raise TasksProjectionError(f"{field}.revision is required.")
        revision = updated_at
    else:
        revision = _parse_datetime(revision_raw, f"{field}.revision")
        if revision != updated_at:
            raise TasksProjectionError(
                f"{field}.revision and updated_at must identify the same source revision."
            )

    return TaskProjection(
        id=task_id,
        title=title,
        due_at=_parse_datetime(task.get("due_at"), f"{field}.due_at"),
        priority_value=priority_value,
        priority_label=priority_label,
        status_value=status_value,
        status_label=status_label,
        recurrence_value=recurrence_value,
        recurrence_label=recurrence_label,
        project_id=project_id,
        project_name=project_name,
        updated_at=updated_at,
        revision=revision,
        source_application=source_application,
        source_api_version=source_api_version,
        authoritative_url=authoritative_url,
    )


def _validate_schema(root: dict[str, Any]) -> None:
    if root.get("schema") != SCHEMA:
        raise TasksProjectionError("Unsupported GoreeCloud Tasks projection schema.")
    if root.get("version") != VERSION:
        raise TasksProjectionError("Unsupported GoreeCloud Tasks projection version.")


def parse_projection_payload(payload: Any) -> tuple[TaskProjection, ...]:
    """Validate and normalize one complete Tasks projection-list response.

    Legacy v1 list payloads without the new source/deep-link/revision fields remain
    readable. When present, the extended fields are validated strictly.
    """
    root = _require_dict(payload, "payload")
    _validate_schema(root)

    tasks = root.get("tasks")
    if not isinstance(tasks, list):
        raise TasksProjectionError("tasks must be an array.")
    if root.get("returned") != len(tasks):
        raise TasksProjectionError("returned does not match the task projection count.")

    parsed: list[TaskProjection] = []
    seen_ids: set[int] = set()
    for index, raw_task in enumerate(tasks):
        projection = _parse_projection_task(
            raw_task,
            f"tasks[{index}]",
            require_extended=False,
        )
        if projection.id in seen_ids:
            raise TasksProjectionError("Duplicate task projection ID received.")
        seen_ids.add(projection.id)
        parsed.append(projection)

    return tuple(parsed)


def parse_single_projection_payload(payload: Any) -> TaskProjection:
    """Validate the new v1 single-task/mutation response contract."""
    root = _require_dict(payload, "payload")
    _validate_schema(root)
    return _parse_projection_task(
        root.get("task"),
        "task",
        require_extended=True,
    )


def _decode_json_body(body: bytes) -> Any:
    if len(body) > MAX_RESPONSE_BYTES:
        raise TasksProjectionError("GoreeCloud Tasks returned an oversized response.")
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TasksProjectionError("GoreeCloud Tasks returned invalid JSON.") from exc


def _request_json(
    *,
    endpoint: str,
    token: str,
    timeout_seconds: float,
    method: str,
    payload: dict[str, Any] | None = None,
) -> Any:
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if payload is not None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(endpoint, method=method, headers=headers, data=data)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        if exc.code == 409:
            current_revision = None
            try:
                conflict_payload = _decode_json_body(exc.read(MAX_RESPONSE_BYTES + 1))
                if isinstance(conflict_payload, dict) and conflict_payload.get(
                    "current_revision"
                ):
                    current_revision = _parse_datetime(
                        conflict_payload["current_revision"],
                        "current_revision",
                    )
            except TasksProjectionError:
                current_revision = None
            raise TasksConflictError(
                "GoreeCloud Tasks rejected the mutation because the task changed.",
                current_revision=current_revision,
            ) from exc
        raise TasksProjectionError(
            f"GoreeCloud Tasks rejected the request with HTTP {exc.code}."
        ) from exc
    except URLError as exc:
        raise TasksProjectionError("GoreeCloud Tasks is unreachable.") from exc

    return _decode_json_body(body)


def fetch_task_projections(
    *,
    base_url: str,
    token: str,
    start: datetime | None = None,
    end: datetime | None = None,
    timeout_seconds: float = 5.0,
) -> tuple[TaskProjection, ...]:
    """Fetch scheduled task projections, optionally for one bounded time window."""
    base, normalized_token = _validate_endpoint_inputs(
        base_url=base_url,
        token=token,
        timeout_seconds=timeout_seconds,
    )
    start, end = _validate_window(start, end)

    endpoint = base + "/api/v1/calendar/task-projections/"
    if start is not None:
        endpoint += "?" + urlencode(
            {"start": start.isoformat(), "end": end.isoformat()}
        )

    payload = _request_json(
        endpoint=endpoint,
        token=normalized_token,
        timeout_seconds=timeout_seconds,
        method="GET",
    )
    return parse_projection_payload(payload)


def fetch_task_projection(
    *,
    base_url: str,
    token: str,
    task_id: int,
    timeout_seconds: float = 5.0,
) -> TaskProjection:
    """Fetch one currently authorized Tasks projection."""
    base, normalized_token = _validate_endpoint_inputs(
        base_url=base_url,
        token=token,
        timeout_seconds=timeout_seconds,
    )
    task_id = _validate_task_id(task_id)
    payload = _request_json(
        endpoint=f"{base}/api/v1/calendar/task-projections/{task_id}/",
        token=normalized_token,
        timeout_seconds=timeout_seconds,
        method="GET",
    )
    return parse_single_projection_payload(payload)


def create_task(
    *,
    base_url: str,
    token: str,
    title: str,
    due_at: datetime,
    priority: int | None = None,
    project_id: int | None = None,
    timeout_seconds: float = 5.0,
) -> TaskProjection:
    """Create one limited native Tasks item through the Calendar service contract."""
    base, normalized_token = _validate_endpoint_inputs(
        base_url=base_url,
        token=token,
        timeout_seconds=timeout_seconds,
    )
    if not isinstance(title, str) or not title.strip():
        raise TasksProjectionError("title is required.")
    if len(title.strip()) > 500:
        raise TasksProjectionError("title cannot exceed 500 characters.")
    due_at = _require_aware_datetime(due_at, "due_at")
    if priority is not None:
        if (
            not isinstance(priority, int)
            or isinstance(priority, bool)
            or priority not in {0, 1, 2, 3, 4}
        ):
            raise TasksProjectionError("priority must be a GoreeCloud P0-P4 integer.")
    if project_id is not None:
        _validate_task_id(project_id)

    body: dict[str, Any] = {
        "title": title.strip(),
        "due_at": due_at.isoformat(),
        "project_id": project_id,
    }
    if priority is not None:
        body["priority"] = priority

    payload = _request_json(
        endpoint=base + "/api/v1/calendar/tasks/",
        token=normalized_token,
        timeout_seconds=timeout_seconds,
        method="POST",
        payload=body,
    )
    return parse_single_projection_payload(payload)


def reschedule_task(
    *,
    base_url: str,
    token: str,
    task_id: int,
    due_at: datetime,
    expected_updated_at: datetime,
    timeout_seconds: float = 5.0,
) -> TaskProjection:
    """Reschedule one editable task using the source revision as a conflict guard."""
    base, normalized_token = _validate_endpoint_inputs(
        base_url=base_url,
        token=token,
        timeout_seconds=timeout_seconds,
    )
    task_id = _validate_task_id(task_id)
    due_at = _require_aware_datetime(due_at, "due_at")
    expected_updated_at = _require_aware_datetime(
        expected_updated_at,
        "expected_updated_at",
    )

    payload = _request_json(
        endpoint=f"{base}/api/v1/calendar/tasks/{task_id}/reschedule/",
        token=normalized_token,
        timeout_seconds=timeout_seconds,
        method="POST",
        payload={
            "due_at": due_at.isoformat(),
            "expected_updated_at": expected_updated_at.isoformat(),
        },
    )
    return parse_single_projection_payload(payload)
