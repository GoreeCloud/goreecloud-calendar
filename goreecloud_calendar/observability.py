"""Privacy-safe structured observability primitives for GoreeCloud Calendar."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Callable


@dataclass(frozen=True, slots=True)
class CalendarAuditEvent:
    timestamp: str
    request_id: str
    operation: str
    outcome: str
    subject_ref: str | None = None
    status: int | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"), sort_keys=True)


def subject_reference(subject: str, *, salt: bytes) -> str:
    """Return a stable pseudonymous subject reference without logging raw identity."""
    if len(salt) < 16:
        raise ValueError("observability salt must be at least 16 bytes")
    digest = hashlib.sha256(salt + subject.encode("utf-8")).hexdigest()
    return digest[:24]


def emit_audit_event(
    sink: Callable[[str], None],
    *,
    request_id: str,
    operation: str,
    outcome: str,
    subject: str | None = None,
    subject_salt: bytes | None = None,
    status: int | None = None,
    now: datetime | None = None,
) -> None:
    """Emit metadata-only JSON; event content, credentials, tokens, and calendar hrefs are excluded."""
    if not request_id.strip() or not operation.strip() or not outcome.strip():
        raise ValueError("request_id, operation, and outcome are required")
    ref = None
    if subject is not None:
        if subject_salt is None:
            raise ValueError("subject_salt is required when subject is provided")
        ref = subject_reference(subject, salt=subject_salt)
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    sink(CalendarAuditEvent(timestamp, request_id, operation, outcome, ref, status).to_json())
