from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from threading import RLock


class LoginBlocked(RuntimeError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Too many failed sign-in attempts.")
        self.retry_after_seconds = max(1, retry_after_seconds)


@dataclass(slots=True)
class _AttemptState:
    failures: deque[datetime] = field(default_factory=deque)
    blocked_until: datetime | None = None
    last_seen_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class LoginRateLimiter:
    """Bounded process-local login abuse control for the single-worker model."""

    def __init__(
        self,
        *,
        max_failures: int,
        window_seconds: int,
        lockout_seconds: int,
        max_identities: int = 1000,
    ) -> None:
        if min(max_failures, window_seconds, lockout_seconds, max_identities) <= 0:
            raise ValueError("Login limiter values must be greater than zero.")
        self.max_failures = max_failures
        self.window = timedelta(seconds=window_seconds)
        self.lockout = timedelta(seconds=lockout_seconds)
        self.max_identities = max_identities
        self._states: dict[str, _AttemptState] = {}
        self._lock = RLock()

    @staticmethod
    def _key(username: str) -> str:
        normalized = username.strip().casefold().encode("utf-8")
        return sha256(normalized).hexdigest()

    def check(self, username: str) -> None:
        now = datetime.now(timezone.utc)
        key = self._key(username)
        with self._lock:
            state = self._states.get(key)
            if state is None:
                return
            state.last_seen_at = now
            self._prune_state(state, now)
            if state.blocked_until and state.blocked_until > now:
                retry = int((state.blocked_until - now).total_seconds()) + 1
                raise LoginBlocked(retry)
            if not state.failures:
                self._states.pop(key, None)

    def failure(self, username: str) -> None:
        now = datetime.now(timezone.utc)
        key = self._key(username)
        with self._lock:
            state = self._states.get(key)
            if state is None:
                self._prune_all_locked(now)
                self._ensure_capacity_locked()
                state = _AttemptState(last_seen_at=now)
                self._states[key] = state
            state.last_seen_at = now
            self._prune_state(state, now)
            state.failures.append(now)
            if len(state.failures) >= self.max_failures:
                state.blocked_until = now + self.lockout
                state.failures.clear()

    def success(self, username: str) -> None:
        with self._lock:
            self._states.pop(self._key(username), None)

    def count(self) -> int:
        now = datetime.now(timezone.utc)
        with self._lock:
            self._prune_all_locked(now)
            return len(self._states)

    def _prune_state(self, state: _AttemptState, now: datetime) -> None:
        cutoff = now - self.window
        while state.failures and state.failures[0] < cutoff:
            state.failures.popleft()
        if state.blocked_until and state.blocked_until <= now:
            state.blocked_until = None

    def _prune_all_locked(self, now: datetime) -> None:
        stale: list[str] = []
        for key, state in self._states.items():
            self._prune_state(state, now)
            if not state.failures and state.blocked_until is None:
                stale.append(key)
        for key in stale:
            self._states.pop(key, None)

    def _ensure_capacity_locked(self) -> None:
        if len(self._states) < self.max_identities:
            return
        oldest_key = min(
            self._states,
            key=lambda key: self._states[key].last_seen_at,
        )
        self._states.pop(oldest_key, None)
