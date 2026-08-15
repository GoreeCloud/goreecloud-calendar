from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe
from threading import RLock


@dataclass(frozen=True, slots=True)
class SessionRecord:
    token: str = field(repr=False)
    csrf_token: str = field(repr=False)
    username: str
    password: str = field(repr=False)
    expires_at: datetime


class SessionStore:
    """Opaque, process-local sessions.

    The browser never receives the Radicale password. The password remains only
    in backend memory for the session lifetime. This deliberately uses one
    application worker and is not a production-grade shared session store.
    """

    def __init__(self, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            raise ValueError("Session TTL must be greater than zero.")
        self.ttl_seconds = ttl_seconds
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
            expires_at=now + timedelta(seconds=self.ttl_seconds),
        )
        with self._lock:
            self._prune_locked(now)
            self._sessions[record.token] = record
        return record

    def get(self, token: str | None) -> SessionRecord | None:
        if not token:
            return None
        now = datetime.now(timezone.utc)
        with self._lock:
            self._prune_locked(now)
            return self._sessions.get(token)

    def delete(self, token: str | None) -> None:
        if not token:
            return
        with self._lock:
            self._sessions.pop(token, None)

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()

    def _prune_locked(self, now: datetime) -> None:
        expired = [
            token
            for token, record in self._sessions.items()
            if record.expires_at <= now
        ]
        for token in expired:
            self._sessions.pop(token, None)
