"""Minimal fail-closed CalDAV transport and iCalendar serialization foundation."""

from __future__ import annotations

import base64
from dataclasses import replace
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from goreecloud_calendar.events import CalendarEvent, CalendarEventError


class CalDAVError(RuntimeError):
    """Raised when DAV data cannot be trusted or a DAV operation fails."""


def _safe_base_url(base_url: str) -> str:
    parsed = urlparse(base_url.strip())
    if parsed.scheme != "https" or not parsed.netloc:
        raise CalDAVError("CalDAV base URL must be an absolute HTTPS URL.")
    if parsed.username or parsed.password:
        raise CalDAVError("Credentials must not be embedded in the CalDAV URL.")
    return base_url.rstrip("/") + "/"


def _escape_ical(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CalDAVError("iCalendar timestamps must be timezone-aware.")
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def serialize_event(event: CalendarEvent, *, sequence: int = 0) -> str:
    """Serialize the supported event subset to RFC-style VCALENDAR/VEVENT text."""
    if sequence < 0:
        raise CalDAVError("sequence cannot be negative.")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//GoreeCloud//Calendar//EN",
        "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:{_escape_ical(event.uid)}",
        f"DTSTAMP:{_format_utc(datetime.now(timezone.utc))}",
        f"DTSTART:{_format_utc(event.starts_at)}",
        f"DTEND:{_format_utc(event.ends_at)}",
        f"SEQUENCE:{sequence}",
        f"SUMMARY:{_escape_ical(event.title)}",
    ]
    if event.description:
        lines.append(f"DESCRIPTION:{_escape_ical(event.description)}")
    if event.location:
        lines.append(f"LOCATION:{_escape_ical(event.location)}")
    lines.extend(["END:VEVENT", "END:VCALENDAR", ""])
    return "\r\n".join(lines)


class CalDAVClient:
    """Small authenticated CalDAV client with explicit optimistic-concurrency support."""

    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        timeout_seconds: float = 8.0,
    ) -> None:
        self.base_url = _safe_base_url(base_url)
        if not username.strip() or not password:
            raise CalDAVError("CalDAV username and password are required.")
        if timeout_seconds <= 0:
            raise CalDAVError("timeout_seconds must be greater than zero.")
        self.username = username
        self.password = password
        self.timeout_seconds = timeout_seconds

    def _authorization(self) -> str:
        raw = f"{self.username}:{self.password}".encode("utf-8")
        return "Basic " + base64.b64encode(raw).decode("ascii")

    def _request(
        self,
        *,
        method: str,
        href: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ):
        target = urljoin(self.base_url, href.lstrip("/"))
        if urlparse(target).netloc != urlparse(self.base_url).netloc:
            raise CalDAVError("Refusing cross-origin DAV request.")
        request_headers = {
            "Authorization": self._authorization(),
            "User-Agent": "GoreeCloud-Calendar/0.1",
        }
        if headers:
            request_headers.update(headers)
        request = Request(target, data=body, method=method, headers=request_headers)
        try:
            return urlopen(request, timeout=self.timeout_seconds)
        except HTTPError as exc:
            raise CalDAVError(f"CalDAV request failed with HTTP {exc.code}.") from exc
        except URLError as exc:
            raise CalDAVError("CalDAV service is unreachable.") from exc

    def discover_calendars(self, *, principal_path: str) -> tuple[str, ...]:
        """Discover calendar collection hrefs under a known principal path."""
        body = b'''<?xml version="1.0" encoding="utf-8"?>
<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
  <d:prop><d:resourcetype/></d:prop>
</d:propfind>'''
        with self._request(
            method="PROPFIND",
            href=principal_path,
            body=body,
            headers={"Depth": "1", "Content-Type": "application/xml; charset=utf-8"},
        ) as response:
            payload = response.read()
        try:
            root = ElementTree.fromstring(payload)
        except ElementTree.ParseError as exc:
            raise CalDAVError("CalDAV discovery returned invalid XML.") from exc

        namespaces = {"d": "DAV:", "c": "urn:ietf:params:xml:ns:caldav"}
        found: list[str] = []
        for response in root.findall("d:response", namespaces):
            href = response.findtext("d:href", default="", namespaces=namespaces).strip()
            resource_type = response.find(".//d:resourcetype", namespaces)
            if not href or resource_type is None:
                continue
            if resource_type.find("c:calendar", namespaces) is not None:
                found.append(href)
        return tuple(dict.fromkeys(found))

    def put_event(self, *, calendar_href: str, event: CalendarEvent) -> CalendarEvent:
        """Create or update one VEVENT and return its latest ETag when provided."""
        event_href = f"{calendar_href.rstrip('/')}/{event.uid}.ics"
        headers = {"Content-Type": "text/calendar; charset=utf-8"}
        if event.etag:
            headers["If-Match"] = event.etag
        else:
            headers["If-None-Match"] = "*"
        body = serialize_event(event).encode("utf-8")
        with self._request(method="PUT", href=event_href, body=body, headers=headers) as response:
            etag = response.headers.get("ETag")
        return replace(event, calendar_href=calendar_href, etag=etag or event.etag)

    def delete_event(self, *, event_href: str, etag: str) -> None:
        if not etag.strip():
            raise CalDAVError("An ETag is required for destructive event deletion.")
        with self._request(method="DELETE", href=event_href, headers={"If-Match": etag}):
            return
