import base64
import hashlib
import hmac
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from goreecloud_calendar.credentials import CalendarCredentialError
from goreecloud_calendar.observability import emit_audit_event, subject_reference
from goreecloud_calendar.runtime_adapters import FileDAVCredentialProvider, HMACSessionClaimsProvider
from goreecloud_calendar.session import CalendarSessionAuthenticator, CalendarSessionError

UTC = timezone.utc


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def token(payload: dict[str, object], key: bytes) -> str:
    body = b64url(json.dumps(payload, separators=(",", ":")).encode())
    signature = hmac.new(key, body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{b64url(signature)}"


class RuntimeAdapterTests(unittest.TestCase):
    def test_hmac_session_provider_authenticates_valid_token(self):
        key = b"k" * 32
        now = datetime(2026, 8, 21, 8, tzinfo=UTC)
        handle = token({
            "sub": "user:calendar",
            "aud": "goreecloud-calendar",
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "calendar_hrefs": ["/user/calendar/"],
            "can_write": True,
        }, key)
        principal = CalendarSessionAuthenticator(HMACSessionClaimsProvider(key)).authenticate(handle, now=now)
        self.assertEqual(principal.subject, "user:calendar")
        self.assertTrue(principal.can_write)

    def test_hmac_session_provider_rejects_tampering(self):
        key = b"k" * 32
        handle = token({"sub":"a","aud":"goreecloud-calendar","exp":4102444800,"calendar_hrefs":[]}, key)
        with self.assertRaises(CalendarSessionError):
            HMACSessionClaimsProvider(key).resolve(handle[:-1] + ("A" if handle[-1] != "A" else "B"))

    def test_file_credential_provider_requires_private_permissions_and_env_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dav.json"
            path.write_text(json.dumps({"user:calendar": {
                "base_url": "https://dav.goreecloud.com/",
                "username": "calendar-user",
                "password_env": "CALENDAR_DAV_PASSWORD",
            }}), encoding="utf-8")
            path.chmod(0o600)
            with patch.dict(os.environ, {"CALENDAR_DAV_PASSWORD": "secret-value"}, clear=False):
                access = FileDAVCredentialProvider(path).resolve("user:calendar")
            self.assertEqual(access.credential.username, "calendar-user")
            self.assertNotIn("secret-value", repr(access.credential))

    def test_file_credential_provider_rejects_broad_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dav.json"
            path.write_text("{}", encoding="utf-8")
            path.chmod(0o644)
            with self.assertRaises(CalendarCredentialError):
                FileDAVCredentialProvider(path).resolve("user:calendar")

    def test_observability_is_metadata_only_and_pseudonymous(self):
        records = []
        emit_audit_event(records.append, request_id="req-1", operation="events.list", outcome="success",
                         subject="user:calendar", subject_salt=b"s" * 16, status=200,
                         now=datetime(2026, 8, 21, 8, tzinfo=UTC))
        record = json.loads(records[0])
        self.assertEqual(record["operation"], "events.list")
        self.assertNotIn("user:calendar", records[0])
        self.assertEqual(record["subject_ref"], subject_reference("user:calendar", salt=b"s" * 16))
        self.assertNotIn("title", record)
        self.assertNotIn("calendar_href", record)


if __name__ == "__main__":
    unittest.main()
