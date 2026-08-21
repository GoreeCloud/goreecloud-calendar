"""Server-side DAV credential retrieval contracts for GoreeCloud Calendar.

Reusable DAV credentials are resolved from a trusted provider at runtime and are never accepted
from browser payloads, query parameters, ordinary logs, or source-controlled configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol
from urllib.parse import urlsplit


class CalendarCredentialError(PermissionError):
    """Raised when Calendar cannot safely resolve DAV credentials."""


@dataclass(frozen=True, slots=True)
class DAVCredential:
    username: str
    password: str = field(repr=False)

    def __post_init__(self) -> None:
        if not self.username.strip() or not self.password:
            raise CalendarCredentialError("DAV username and password are required")


@dataclass(frozen=True, slots=True)
class DAVAccess:
    """Runtime-only DAV access material for one authenticated subject."""

    base_url: str
    credential: DAVCredential

    def __post_init__(self) -> None:
        parsed = urlsplit(self.base_url)
        if parsed.scheme.lower() != "https" or not parsed.netloc:
            raise CalendarCredentialError("DAV base URL must use HTTPS")
        if parsed.username is not None or parsed.password is not None:
            raise CalendarCredentialError("DAV credentials must not be embedded in URLs")
        if parsed.query or parsed.fragment:
            raise CalendarCredentialError("DAV base URL must not contain query or fragment data")


class DAVCredentialProvider(Protocol):
    """Production secret-manager or identity-broker contract."""

    def resolve(self, subject: str) -> DAVAccess: ...


@dataclass(slots=True)
class StaticDAVCredentialProvider:
    """Synthetic test/development provider; never use it for production reusable secrets."""

    access_by_subject: Mapping[str, DAVAccess]

    def resolve(self, subject: str) -> DAVAccess:
        if not isinstance(subject, str) or not subject.strip():
            raise CalendarCredentialError("credential subject is required")
        try:
            return self.access_by_subject[subject]
        except KeyError as exc:
            raise CalendarCredentialError("DAV access is not available for this subject") from exc
