"""Live disposable contract check against an exact GoreeCloud Tasks candidate."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from goreecloud_calendar.integrations.tasks import (
    TasksConflictError,
    create_task,
    fetch_task_projection,
    fetch_task_projections,
    reschedule_task,
)


def main() -> None:
    base_url = os.environ.get("TASKS_LIVE_BASE_URL", "http://127.0.0.1:8765")
    token = os.environ["TASKS_CALENDAR_API_TOKEN"]

    now = datetime.now(timezone.utc)
    projections = fetch_task_projections(
        base_url=base_url,
        token=token,
        start=now - timedelta(days=1),
        end=now + timedelta(days=30),
    )
    if not any(item.title == "Calendar contract seed" for item in projections):
        raise RuntimeError("The seeded Tasks projection was not returned.")

    created_due = now + timedelta(days=2)
    created = create_task(
        base_url=base_url,
        token=token,
        title="Calendar live contract task",
        due_at=created_due,
        priority=1,
    )
    if created.source_application != "goreecloud-tasks":
        raise RuntimeError("Created task did not retain Tasks source identity.")
    if created.authoritative_url is None:
        raise RuntimeError("Created task did not provide an authoritative Tasks deep link.")

    fetched = fetch_task_projection(
        base_url=base_url,
        token=token,
        task_id=created.id,
    )
    if fetched.id != created.id or fetched.revision != created.revision:
        raise RuntimeError("Single-projection read did not match the created Tasks revision.")

    moved_due = created_due + timedelta(hours=3)
    moved = reschedule_task(
        base_url=base_url,
        token=token,
        task_id=created.id,
        due_at=moved_due,
        expected_updated_at=created.revision,
    )
    if moved.due_at != moved_due:
        raise RuntimeError("Tasks did not persist the Calendar reschedule.")
    if moved.revision == created.revision:
        raise RuntimeError("Tasks did not advance the authoritative revision after reschedule.")

    try:
        reschedule_task(
            base_url=base_url,
            token=token,
            task_id=created.id,
            due_at=moved_due + timedelta(hours=1),
            expected_updated_at=created.revision,
        )
    except TasksConflictError as exc:
        if exc.current_revision != moved.revision:
            raise RuntimeError(
                "The Tasks conflict response did not expose the current minimized revision."
            ) from exc
    else:
        raise RuntimeError("A stale Calendar revision unexpectedly overwrote Tasks state.")


if __name__ == "__main__":
    main()
