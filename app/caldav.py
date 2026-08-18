from __future__ import annotations

from asyncio import sleep
from datetime import date, datetime
from posixpath import normpath
from urllib.parse import unquote, urljoin, urlsplit

import httpx
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from .config import Settings

DAV = "DAV:"
CALDAV = "urn:ietf:params:xml:ns:caldav"
ICAL = "http://apple.com/ns/ical/"
MAX_ICAL_BYTES = 256 * 1024
MAX_UPSTREAM_RESPONSE_BYTES = 8 * 1024 * 1024
READ_RETRY_METHODS = {"PROPFIND", "REPORT"}


class CalDAVError(RuntimeError):
    pass


class CalDAVConflict(CalDAVError):
    pass


class CalDAVPreconditionRequired(CalDAVError):
    pass


class CalDAVAuthenticationError(CalDAVError):
    pass


def _unfold_ical_lines(payload: str) -> list[str]:
    normalized = payload.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    unfolded: list[str] = []
    for line in normalized:
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return unfolded


def _unescape_ical_text(value: str) -> str:
    return (
        value.replace("\\N", "\n")
        .replace("\\n", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )


def _parse_property(raw_key: str) -> tuple[str, dict[str, str]]:
    parts = raw_key.split(";")
    name = parts[0].upper()
    params: dict[str, str] = {}
    for item in parts[1:]:
        if "=" in item:
            key, value = item.split("=", 1)
            params[key.upper()] = value.strip('"')
    return name, params


def _parse_ics_datetime(value: str) -> str:
    value = value.strip()
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S", "%Y%m%d"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.isoformat() + ("Z" if value.endswith("Z") else "")
        except ValueError:
            continue
    return value


def parse_vevents(payload: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for raw_line in _unfold_ical_lines(payload):
        line = raw_line.strip()
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT" and current is not None:
            if current.get("uid") and current.get("start"):
                current.setdefault("summary", "Untitled event")
                current["recurring"] = bool(current.get("rrule") or current.get("recurrenceId"))
                events.append(current)
            current = None
            continue
        if current is None or ":" not in line:
            continue

        raw_key, value = line.split(":", 1)
        key, params = _parse_property(raw_key)
        if key == "UID":
            current["uid"] = value
        elif key == "SUMMARY":
            current["summary"] = _unescape_ical_text(value) or "Untitled event"
        elif key == "DTSTART":
            current["start"] = _parse_ics_datetime(value)
            if params.get("TZID"):
                current["startTimezone"] = params["TZID"]
            if params.get("VALUE") == "DATE" or ("T" not in value):
                current["allDay"] = True
        elif key == "DTEND":
            current["end"] = _parse_ics_datetime(value)
            if params.get("TZID"):
                current["endTimezone"] = params["TZID"]
        elif key == "LOCATION":
            current["location"] = _unescape_ical_text(value)
        elif key == "DESCRIPTION":
            current["description"] = _unescape_ical_text(value)
        elif key == "RRULE":
            current["rrule"] = value
        elif key == "RECURRENCE-ID":
            current["recurrenceId"] = _parse_ics_datetime(value)
    return events


def _parse_xml(payload: str, error_message: str):
    try:
        return ET.fromstring(payload)
    except (ET.ParseError, DefusedXmlException) as exc:
        raise CalDAVError(error_message) from exc


def parse_calendar_collections(payload: str) -> list[dict[str, str]]:
    root = _parse_xml(payload, "CalDAV calendar discovery returned invalid XML")
    calendars: list[dict[str, str]] = []
    for response in root.findall(f".//{{{DAV}}}response"):
        href = response.find(f"{{{DAV}}}href")
        if href is None or not href.text:
            continue
        prop = response.find(f".//{{{DAV}}}prop")
        if prop is None:
            continue
        resource_type = prop.find(f"{{{DAV}}}resourcetype")
        if resource_type is None or resource_type.find(f"{{{CALDAV}}}calendar") is None:
            continue
        display_name = prop.find(f"{{{DAV}}}displayname")
        color = prop.find(f"{{{ICAL}}}calendar-color")
        calendars.append(
            {
                "href": href.text,
                "name": (display_name.text if display_name is not None and display_name.text else "Calendar"),
                "color": (color.text if color is not None and color.text else ""),
            }
        )
    return calendars


class CalDAVClient:
    def __init__(self, settings: Settings, credentials: tuple[str, str]):
        self.settings = settings
        username, password = credentials
        if not username or not password:
            raise CalDAVError("CalDAV user credentials are incomplete")
        self.credentials = credentials
        self._client: httpx.AsyncClient | None = None

    def _auth(self) -> tuple[str, str]:
        return self.credentials

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            timeout = httpx.Timeout(self.settings.upstream_timeout_seconds)
            limits = httpx.Limits(max_connections=8, max_keepalive_connections=4, keepalive_expiry=20)
            self._client = httpx.AsyncClient(
                timeout=timeout,
                limits=limits,
                follow_redirects=False,
                headers={"User-Agent": "GoreeCloud-Calendar/0.2"},
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _url(self, href: str) -> str:
        base = self.settings.caldav_base_url.rstrip("/") + "/"
        resolved = urljoin(base, href)
        base_parts = urlsplit(base)
        resolved_parts = urlsplit(resolved)
        if (resolved_parts.scheme, resolved_parts.netloc) != (base_parts.scheme, base_parts.netloc):
            raise CalDAVError("CalDAV returned a resource outside the configured DAV origin")
        if resolved_parts.query or resolved_parts.fragment:
            raise CalDAVError("CalDAV resource URLs must not contain query strings or fragments")
        return resolved

    def _validate_resource_boundary(self, calendar_href: str, resource_href: str) -> None:
        calendar_path = normpath(unquote(urlsplit(self._url(calendar_href)).path)).rstrip("/") + "/"
        resource_path = normpath(unquote(urlsplit(self._url(resource_href)).path))
        if not resource_path.startswith(calendar_path) or resource_path == calendar_path.rstrip("/"):
            raise CalDAVError("CalDAV resource is outside the selected calendar collection")

    @staticmethod
    def _validate_ical_payload(payload: str) -> None:
        encoded = payload.encode("utf-8")
        if len(encoded) > MAX_ICAL_BYTES:
            raise CalDAVError("iCalendar payload exceeds the 256 KiB safety limit")
        upper = payload.upper()
        required = ("BEGIN:VCALENDAR", "END:VCALENDAR", "BEGIN:VEVENT", "END:VEVENT", "UID:", "DTSTART")
        if not all(marker in upper for marker in required):
            raise CalDAVError("iCalendar payload is missing required VCALENDAR or VEVENT fields")

    @staticmethod
    def _validate_upstream_response(response: httpx.Response) -> None:
        content_length = response.headers.get("Content-Length")
        if content_length and content_length.isdigit() and int(content_length) > MAX_UPSTREAM_RESPONSE_BYTES:
            raise CalDAVError("CalDAV response exceeds the application safety limit")
        if len(response.content) > MAX_UPSTREAM_RESPONSE_BYTES:
            raise CalDAVError("CalDAV response exceeds the application safety limit")

    async def _request(
        self,
        method: str,
        url: str,
        body: str | None = None,
        *,
        depth: str | None = None,
        content_type: str | None = "application/xml; charset=utf-8",
        extra_headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        headers: dict[str, str] = {}
        if depth is not None:
            headers["Depth"] = depth
        if content_type is not None:
            headers["Content-Type"] = content_type
        if extra_headers:
            headers.update(extra_headers)

        attempts = 2 if method in READ_RETRY_METHODS else 1
        for attempt in range(attempts):
            try:
                response = await self._http().request(
                    method,
                    url,
                    content=body,
                    headers=headers,
                    auth=self._auth(),
                )
                self._validate_upstream_response(response)
                if response.status_code in {401, 403}:
                    raise CalDAVAuthenticationError("CalDAV authentication or authorization failed")
                return response
            except httpx.RequestError as exc:
                if attempt + 1 < attempts:
                    await sleep(0.15)
                    continue
                raise CalDAVError("CalDAV service is unreachable") from exc
        raise CalDAVError("CalDAV request failed")

    async def calendar_home(self) -> str:
        body = """<?xml version='1.0' encoding='utf-8'?>
<d:propfind xmlns:d='DAV:' xmlns:c='urn:ietf:params:xml:ns:caldav'>
  <d:prop><c:calendar-home-set/></d:prop>
</d:propfind>"""
        response = await self._request(
            "PROPFIND", self.settings.caldav_base_url.rstrip("/") + "/", body, depth="0"
        )
        if response.status_code != 207:
            raise CalDAVError(f"CalDAV discovery failed with HTTP {response.status_code}")
        root = _parse_xml(response.text, "CalDAV discovery returned invalid XML")
        href = root.find(f".//{{{CALDAV}}}calendar-home-set/{{{DAV}}}href")
        if href is None or not href.text:
            raise CalDAVError("CalDAV calendar-home-set was not returned")
        return href.text

    async def list_calendars(self) -> list[dict[str, str]]:
        home = await self.calendar_home()
        body = """<?xml version='1.0' encoding='utf-8'?>
<d:propfind xmlns:d='DAV:' xmlns:c='urn:ietf:params:xml:ns:caldav' xmlns:i='http://apple.com/ns/ical/'>
  <d:prop><d:resourcetype/><d:displayname/><i:calendar-color/></d:prop>
</d:propfind>"""
        response = await self._request("PROPFIND", self._url(home), body, depth="1")
        if response.status_code != 207:
            raise CalDAVError(f"CalDAV calendar listing failed with HTTP {response.status_code}")
        return parse_calendar_collections(response.text)

    async def _calendar_events(
        self, calendar: dict[str, str], start: date, end: date
    ) -> list[dict[str, object]]:
        start_utc = start.strftime("%Y%m%dT000000Z")
        end_utc = end.strftime("%Y%m%dT000000Z")
        body = f"""<?xml version='1.0' encoding='utf-8'?>
<c:calendar-query xmlns:d='DAV:' xmlns:c='urn:ietf:params:xml:ns:caldav'>
  <d:prop><d:getetag/><c:calendar-data/></d:prop>
  <c:filter><c:comp-filter name='VCALENDAR'><c:comp-filter name='VEVENT'><c:time-range start='{start_utc}' end='{end_utc}'/></c:comp-filter></c:comp-filter></c:filter>
</c:calendar-query>"""
        response = await self._request("REPORT", self._url(calendar["href"]), body, depth="1")
        if response.status_code != 207:
            raise CalDAVError(
                f"CalDAV event query for {calendar['name']} failed with HTTP {response.status_code}"
            )
        root = _parse_xml(response.text, "CalDAV event query returned invalid XML")

        events: list[dict[str, object]] = []
        for item in root.findall(f".//{{{DAV}}}response"):
            href = item.find(f"{{{DAV}}}href")
            etag = item.find(f".//{{{DAV}}}getetag")
            calendar_data = item.find(f".//{{{CALDAV}}}calendar-data")
            if calendar_data is None or not calendar_data.text:
                continue
            for event in parse_vevents(calendar_data.text):
                event["calendarName"] = calendar["name"]
                event["calendarColor"] = calendar["color"]
                event["calendarHref"] = calendar["href"]
                if href is not None and href.text:
                    self._validate_resource_boundary(calendar["href"], href.text)
                    event["resourceHref"] = href.text
                if etag is not None and etag.text:
                    event["etag"] = etag.text
                events.append(event)
        return events

    async def list_events(self, start: date, end: date) -> list[dict[str, object]]:
        calendars = await self.list_calendars()
        events: list[dict[str, object]] = []
        for calendar in calendars:
            events.extend(await self._calendar_events(calendar, start, end))
        events.sort(key=lambda event: str(event.get("start", "")))
        return events

    async def put_event(
        self,
        calendar_href: str,
        resource_href: str,
        payload: str,
        *,
        etag: str | None = None,
        create: bool = False,
    ) -> str | None:
        if not self.settings.writes_available:
            raise CalDAVError("CalDAV writes are disabled")
        self._validate_resource_boundary(calendar_href, resource_href)
        self._validate_ical_payload(payload)
        if create and etag is not None:
            raise CalDAVError("New resources must not include an existing ETag")
        if not create and not etag:
            raise CalDAVPreconditionRequired("An ETag is required to update an existing event")

        condition = {"If-None-Match": "*"} if create else {"If-Match": etag or ""}
        response = await self._request(
            "PUT",
            self._url(resource_href),
            payload,
            content_type="text/calendar; charset=utf-8",
            extra_headers=condition,
        )
        if response.status_code == 412:
            raise CalDAVConflict("The calendar resource changed before the write completed")
        if response.status_code not in {201, 204}:
            raise CalDAVError(f"CalDAV event write failed with HTTP {response.status_code}")
        return response.headers.get("ETag")

    async def delete_event(self, calendar_href: str, resource_href: str, *, etag: str | None) -> None:
        if not self.settings.writes_available:
            raise CalDAVError("CalDAV writes are disabled")
        self._validate_resource_boundary(calendar_href, resource_href)
        if not etag:
            raise CalDAVPreconditionRequired("An ETag is required to delete an existing event")
        response = await self._request(
            "DELETE",
            self._url(resource_href),
            content_type=None,
            extra_headers={"If-Match": etag},
        )
        if response.status_code == 412:
            raise CalDAVConflict("The calendar resource changed before the delete completed")
        if response.status_code not in {200, 204}:
            raise CalDAVError(f"CalDAV event delete failed with HTTP {response.status_code}")
