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


class LoginRateLimiter:
    """Process-local bounded login abuse control.

    Keys are hashed before storage so usernames are not retained in the limiter.
    This matches the current single-worker deployment model; a shared limiter is
    required before a multi-worker production model is approved.
    """

    def __init__(self, *, max_failures: int, window_seconds: int, lockout_seconds: int) -> None:
        if min(max_failures, window_seconds, lockout_seconds) <= 0:
            raise ValueError("Login limiter values must be greater than zero.")
        self.max_failures = max_failures
        self.window = timedelta(seconds=window_seconds)
        self.lockout = timedelta(seconds=lockout_seconds)
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
            state = self._states.setdefault(key, _AttemptState())
            self._prune_state(state, now)
            state.failures.append(now)
            if len(state.failures) >= self.max_failures:
                state.blocked_until = now + self.lockout
                state.failures.clear()

    def success(self, username: str) -> None:
        with self._lock:
            self._states.pop(self._key(username), None)

    def _prune_state(self, state: _AttemptState, now: datetime) -> None:
        cutoff = now - self.window
        while state.failures and state.failures[0] < cutoff:
            state.failures.popleft()
        if state.blocked_until and state.blocked_until <= now:
            state.blocked_until = None
