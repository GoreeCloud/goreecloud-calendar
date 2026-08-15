from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe
from threading import RLock


@dataclass(frozen=True, slots=True)
class SessionRecord:
    token: str = field(repr=False)
    csrf_token: str = field(repr=False)
    username: str
    password: str = field(repr=False)
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    idle_expires_at: datetime


class SessionStore:
    """Bounded opaque, process-local sessions for the single-worker model."""

    def __init__(
        self,
        ttl_seconds: int,
        *,
        idle_seconds: int | None = None,
        max_total: int = 200,
        max_per_user: int = 5,
    ) -> None:
        idle_seconds = idle_seconds or ttl_seconds
        if min(ttl_seconds, idle_seconds, max_total, max_per_user) <= 0:
            raise ValueError("Session limits must be greater than zero.")
        if idle_seconds > ttl_seconds:
            raise ValueError("Idle timeout cannot exceed absolute TTL.")
        if max_per_user > max_total:
            raise ValueError("Per-user session limit cannot exceed global limit.")
        self.ttl_seconds = ttl_seconds
        self.idle_seconds = idle_seconds
        self.max_total = max_total
        self.max_per_user = max_per_user
        self._sessions: dict[str, SessionRecord] = {}
        self._lock = RLock()

    def create(self, *, username: str, password: str) -> SessionRecord:
        username = username.strip()
        if not username or not password:
            raise ValueError("Username and password are required.")
        now = datetime.now(timezone.utc)
        record = SessionRecord(
            token=token_urlsafe(48),
            csrf_token=token_urlsafe(32),
            username=username,
            password=password,
            created_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(seconds=self.ttl_seconds),
            idle_expires_at=now + timedelta(seconds=self.idle_seconds),
        )
        with self._lock:
            self._prune_locked(now)
            self._trim_user_locked(username, keep=self.max_per_user - 1)
            self._trim_total_locked(keep=self.max_total - 1)
            self._sessions[record.token] = record
        return record

    def get(self, token: str | None, *, touch: bool = True) -> SessionRecord | None:
        if not token:
            return None
        now = datetime.now(timezone.utc)
        with self._lock:
            self._prune_locked(now)
            record = self._sessions.get(token)
            if record is None:
                return None
            if not touch:
                return record
            refreshed = replace(
                record,
                last_seen_at=now,
                idle_expires_at=min(
                    record.expires_at,
                    now + timedelta(seconds=self.idle_seconds),
                ),
            )
            self._sessions[token] = refreshed
            return refreshed

    def delete(self, token: str | None) -> None:
        if not token:
            return
        with self._lock:
            self._sessions.pop(token, None)

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()

    def count(self) -> int:
        now = datetime.now(timezone.utc)
        with self._lock:
            self._prune_locked(now)
            return len(self._sessions)

    def _prune_locked(self, now: datetime) -> None:
        expired = [
            token
            for token, record in self._sessions.items()
            if record.expires_at <= now or record.idle_expires_at <= now
        ]
        for token in expired:
            self._sessions.pop(token, None)

    def _trim_user_locked(self, username: str, *, keep: int) -> None:
        matches = sorted(
            (record for record in self._sessions.values() if record.username == username),
            key=lambda record: record.last_seen_at,
            reverse=True,
        )
        for record in matches[max(keep, 0):]:
            self._sessions.pop(record.token, None)

    def _trim_total_locked(self, *, keep: int) -> None:
        records = sorted(
            self._sessions.values(),
            key=lambda record: record.last_seen_at,
            reverse=True,
        )
        for record in records[max(keep, 0):]:
            self._sessions.pop(record.token, None)
