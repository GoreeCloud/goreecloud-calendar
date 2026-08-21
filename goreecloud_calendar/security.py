"""Framework-neutral runtime security controls for GoreeCloud Calendar.

This module validates trusted browser request context before requests reach the Calendar API
adapter. Production session validation and secret retrieval remain deployment responsibilities;
request payloads never define identity, authorization scope, or CSRF policy.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from time import monotonic
from urllib.parse import urlsplit


class CalendarRequestSecurityError(PermissionError):
    """Raised when browser request trust cannot be established."""


@dataclass(frozen=True, slots=True)
class TrustedRequestContext:
    """Server-derived request metadata used for origin and CSRF enforcement."""

    scheme: str
    host: str
    origin: str | None
    csrf_cookie: str | None = None
    csrf_header: str | None = None

    @property
    def canonical_origin(self) -> str:
        scheme = self.scheme.lower()
        host = self.host.lower().rstrip(".")
        if scheme != "https" or not host:
            raise CalendarRequestSecurityError("Calendar requires trusted HTTPS request context")
        return f"https://{host}"

    def require_same_origin(self) -> None:
        """Reject cross-origin browser requests when an Origin header is present."""

        if self.origin is None:
            return
        parsed = urlsplit(self.origin)
        supplied = f"{parsed.scheme.lower()}://{parsed.netloc.lower().rstrip('.')}"
        if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            raise CalendarRequestSecurityError("request origin is malformed")
        if supplied != self.canonical_origin:
            raise CalendarRequestSecurityError("cross-origin Calendar request refused")

    def require_csrf(self) -> None:
        """Require an exact double-submit CSRF token match for browser mutations."""

        if not self.csrf_cookie or not self.csrf_header:
            raise CalendarRequestSecurityError("CSRF evidence is required")
        if self.csrf_cookie != self.csrf_header:
            raise CalendarRequestSecurityError("CSRF evidence does not match")


class InMemoryRateLimiter:
    """Small injectable sliding-window limiter for source/runtime acceptance tests.

    Production deployments may replace this with a distributed limiter while preserving the
    same ``allow`` contract. Keys should be server-derived pseudonymous subjects rather than
    raw event content, tokens, or credentials.
    """

    def __init__(self, *, limit: int = 120, window_seconds: float = 60.0) -> None:
        if limit < 1 or window_seconds <= 0:
            raise ValueError("rate-limit configuration must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, *, now: float | None = None) -> bool:
        if not key:
            raise ValueError("rate-limit key is required")
        timestamp = monotonic() if now is None else now
        bucket = self._events[key]
        cutoff = timestamp - self.window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= self.limit:
            return False
        bucket.append(timestamp)
        return True


def enforce_browser_request(
    *,
    context: TrustedRequestContext,
    method: str,
    rate_limiter: InMemoryRateLimiter | None = None,
    rate_key: str | None = None,
) -> None:
    """Apply browser-origin, CSRF, and optional abuse controls before API dispatch."""

    context.require_same_origin()
    unsafe = method.upper() not in {"GET", "HEAD", "OPTIONS"}
    if unsafe:
        context.require_csrf()
    if rate_limiter is not None:
        if rate_key is None or not rate_limiter.allow(rate_key):
            raise CalendarRequestSecurityError("request rate exceeded")
