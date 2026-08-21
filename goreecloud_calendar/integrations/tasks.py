"""Strict consumer for the GoreeCloud Tasks Calendar projection contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SCHEMA = "goreecloud.tasks.calendar-projections.v1"
VERSION = 1


class TasksProjectionError(RuntimeError):
    """Raised when the Tasks integration cannot provide a trustworthy projection."""


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


def parse_projection_payload(payload: Any) -> tuple[TaskProjection, ...]:
    """Validate and normalize one complete Tasks projection response."""

    root = _require_dict(payload, "payload")
    if root.get("schema") != SCHEMA:
        raise TasksProjectionError("Unsupported GoreeCloud Tasks projection schema.")
    if root.get("version") != VERSION:
        raise TasksProjectionError("Unsupported GoreeCloud Tasks projection version.")

    tasks = root.get("tasks")
    if not isinstance(tasks, list):
        raise TasksProjectionError("tasks must be an array.")
    if root.get("returned") != len(tasks):
        raise TasksProjectionError("returned does not match the task projection count.")

    parsed: list[TaskProjection] = []
    seen_ids: set[int] = set()
    for index, raw_task in enumerate(tasks):
        task = _require_dict(raw_task, f"tasks[{index}]")
        task_id = task.get("id")
        if not isinstance(task_id, int) or isinstance(task_id, bool) or task_id <= 0:
            raise TasksProjectionError(f"tasks[{index}].id must be a positive integer.")
        if task_id in seen_ids:
            raise TasksProjectionError("Duplicate task projection ID received.")
        seen_ids.add(task_id)

        title = task.get("title")
        if not isinstance(title, str) or not title.strip():
            raise TasksProjectionError(f"tasks[{index}].title must be non-empty.")

        priority = _require_dict(task.get("priority"), f"tasks[{index}].priority")
        status = _require_dict(task.get("status"), f"tasks[{index}].status")
        recurrence = _require_dict(
            task.get("recurrence"), f"tasks[{index}].recurrence"
        )

        priority_value = priority.get("value")
        if not isinstance(priority_value, int) or isinstance(priority_value, bool):
            raise TasksProjectionError(
                f"tasks[{index}].priority.value must be an integer."
            )

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
                raise TasksProjectionError(
                    f"tasks[{index}].{field_name} must be non-empty."
                )

        project = task.get("project")
        project_id: int | None = None
        project_name: str | None = None
        if project is not None:
            project_obj = _require_dict(project, f"tasks[{index}].project")
            project_id = project_obj.get("id")
            project_name = project_obj.get("name")
            if not isinstance(project_id, int) or isinstance(project_id, bool) or project_id <= 0:
                raise TasksProjectionError(
                    f"tasks[{index}].project.id must be a positive integer."
                )
            if not isinstance(project_name, str) or not project_name.strip():
                raise TasksProjectionError(
                    f"tasks[{index}].project.name must be non-empty."
                )

        parsed.append(
            TaskProjection(
                id=task_id,
                title=title,
                due_at=_parse_datetime(task.get("due_at"), f"tasks[{index}].due_at"),
                priority_value=priority_value,
                priority_label=priority_label,
                status_value=status_value,
                status_label=status_label,
                recurrence_value=recurrence_value,
                recurrence_label=recurrence_label,
                project_id=project_id,
                project_name=project_name,
                updated_at=_parse_datetime(
                    task.get("updated_at"), f"tasks[{index}].updated_at"
                ),
            )
        )

    return tuple(parsed)


def fetch_task_projections(
    *, base_url: str, token: str, timeout_seconds: float = 5.0
) -> tuple[TaskProjection, ...]:
    """Fetch scheduled task projections from GoreeCloud Tasks.

    The Calendar consumer fails closed on transport, HTTP, JSON, schema, version, or field
    validation errors. Callers may choose to degrade the Calendar UI gracefully, but must not
    render unvalidated upstream data as trusted Tasks projections.
    """

    if not base_url.strip():
        raise TasksProjectionError("Tasks base URL is required.")
    if len(token.strip()) < 32:
        raise TasksProjectionError("Tasks integration token is invalid.")
    if timeout_seconds <= 0:
        raise TasksProjectionError("timeout_seconds must be greater than zero.")

    endpoint = base_url.rstrip("/") + "/api/v1/calendar/task-projections/"
    request = Request(
        endpoint,
        method="GET",
        headers={
            "Authorization": f"Bearer {token.strip()}",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read()
    except HTTPError as exc:
        raise TasksProjectionError(
            f"GoreeCloud Tasks rejected the projection request with HTTP {exc.code}."
        ) from exc
    except URLError as exc:
        raise TasksProjectionError("GoreeCloud Tasks is unreachable.") from exc

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TasksProjectionError("GoreeCloud Tasks returned invalid JSON.") from exc

    return parse_projection_payload(payload)
