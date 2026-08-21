"""Concrete production-pattern runtime adapters for GoreeCloud Calendar.

These adapters keep authentication and reusable DAV secrets server-side while remaining
framework-neutral and replaceable by GoreeCloud Identity or another approved runtime.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from goreecloud_calendar.credentials import DAVAccess, DAVCredential, CalendarCredentialError
from goreecloud_calendar.session import CalendarSessionError, TrustedSessionClaims


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except Exception as exc:
        raise CalendarSessionError("session token is malformed") from exc


@dataclass(slots=True)
class HMACSessionClaimsProvider:
    """Validate compact HMAC-SHA256 session tokens issued by trusted server code.

    Token form: ``base64url(payload-json).base64url(hmac)``. The signing key is supplied by
    runtime secret injection and is never stored in the token or source tree.
    """

    signing_key: bytes

    def __post_init__(self) -> None:
        if len(self.signing_key) < 32:
            raise CalendarSessionError("session signing key must be at least 32 bytes")

    def resolve(self, session_handle: str) -> TrustedSessionClaims:
        try:
            encoded_payload, encoded_signature = session_handle.split(".", 1)
        except ValueError as exc:
            raise CalendarSessionError("session token is malformed") from exc
        supplied = _b64url_decode(encoded_signature)
        expected = hmac.new(self.signing_key, encoded_payload.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(supplied, expected):
            raise CalendarSessionError("session token is invalid")
        try:
            payload = json.loads(_b64url_decode(encoded_payload))
            expires_at = datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc)
            hrefs = tuple(str(item) for item in payload["calendar_hrefs"])
            return TrustedSessionClaims(
                subject=str(payload["sub"]),
                audience=str(payload["aud"]),
                expires_at=expires_at,
                calendar_hrefs=hrefs,
                can_write=bool(payload.get("can_write", False)),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise CalendarSessionError("session claims are invalid") from exc


@dataclass(slots=True)
class FileDAVCredentialProvider:
    """Load DAV credentials from a root-readable runtime JSON file.

    The file must not grant group/other permissions. Production deployment can replace this
    adapter with Vaultwarden, an identity broker, or another approved secret manager without
    changing Calendar's DAVCredentialProvider contract.
    """

    path: Path

    def _load(self) -> Mapping[str, object]:
        try:
            info = self.path.stat()
        except OSError as exc:
            raise CalendarCredentialError("DAV credential file is unavailable") from exc
        if not stat.S_ISREG(info.st_mode):
            raise CalendarCredentialError("DAV credential path must be a regular file")
        if info.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            raise CalendarCredentialError("DAV credential file permissions are too broad")
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CalendarCredentialError("DAV credential file is invalid") from exc
        if not isinstance(data, dict):
            raise CalendarCredentialError("DAV credential file root must be an object")
        return data

    def resolve(self, subject: str) -> DAVAccess:
        if not subject.strip():
            raise CalendarCredentialError("credential subject is required")
        data = self._load()
        entry = data.get(subject)
        if not isinstance(entry, dict):
            raise CalendarCredentialError("DAV access is not available for this subject")
        try:
            base_url = str(entry["base_url"])
            username = str(entry["username"])
            password_env = str(entry["password_env"])
        except KeyError as exc:
            raise CalendarCredentialError("DAV credential entry is incomplete") from exc
        password = os.environ.get(password_env)
        if not password:
            raise CalendarCredentialError("DAV credential secret is unavailable")
        return DAVAccess(base_url=base_url, credential=DAVCredential(username=username, password=password))
