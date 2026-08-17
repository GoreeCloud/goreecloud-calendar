from __future__ import annotations

from datetime import date, datetime
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

import httpx

from .config import Settings

DAV = "DAV:"
CALDAV = "urn:ietf:params:xml:ns:caldav"
ICAL = "http://apple.com/ns/ical/"


class CalDAVError(RuntimeError):
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


def parse_calendar_collections(payload: str) -> list[dict[str, str]]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise CalDAVError("CalDAV calendar discovery returned invalid XML") from exc

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
    def __init__(self, settings: Settings):
        self.settings = settings

    def _auth(self) -> tuple[str, str]:
        if not self.settings.caldav_configured:
            raise CalDAVError("CalDAV credentials are not configured")
        return self.settings.caldav_username or "", self.settings.caldav_password or ""

    def _url(self, href: str) -> str:
        return urljoin(self.settings.caldav_base_url.rstrip("/") + "/", href)

    async def _request(self, method: str, url: str, body: str, depth: str) -> httpx.Response:
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.upstream_timeout_seconds,
                follow_redirects=False,
            ) as client:
                return await client.request(
                    method,
                    url,
                    content=body,
                    headers={"Depth": depth, "Content-Type": "application/xml; charset=utf-8"},
                    auth=self._auth(),
                )
        except httpx.RequestError as exc:
            raise CalDAVError("CalDAV service is unreachable") from exc

    async def calendar_home(self) -> str:
        body = """<?xml version='1.0' encoding='utf-8'?>
<d:propfind xmlns:d='DAV:' xmlns:c='urn:ietf:params:xml:ns:caldav'>
  <d:prop><c:calendar-home-set/></d:prop>
</d:propfind>"""
        response = await self._request(
            "PROPFIND", self.settings.caldav_base_url.rstrip("/") + "/", body, "0"
        )
        if response.status_code != 207:
            raise CalDAVError(f"CalDAV discovery failed with HTTP {response.status_code}")
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            raise CalDAVError("CalDAV discovery returned invalid XML") from exc
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
        response = await self._request("PROPFIND", self._url(home), body, "1")
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
        response = await self._request("REPORT", self._url(calendar["href"]), body, "1")
        if response.status_code != 207:
            raise CalDAVError(
                f"CalDAV event query for {calendar['name']} failed with HTTP {response.status_code}"
            )
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            raise CalDAVError("CalDAV event query returned invalid XML") from exc

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
