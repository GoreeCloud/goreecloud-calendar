from __future__ import annotations

from datetime import date, datetime
from xml.etree import ElementTree as ET

import httpx

from .config import Settings

DAV = "DAV:"
CALDAV = "urn:ietf:params:xml:ns:caldav"


class CalDAVError(RuntimeError):
    pass


def _parse_ics_datetime(value: str) -> str:
    value = value.strip()
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S", "%Y%m%d"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.isoformat() + ("Z" if value.endswith("Z") else "")
        except ValueError:
            continue
    return value


def parse_vevents(payload: str) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw_line in payload.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT" and current is not None:
            if current.get("uid") and current.get("start"):
                events.append(current)
            current = None
        elif current is not None and ":" in line:
            key, value = line.split(":", 1)
            key = key.split(";", 1)[0].upper()
            if key == "UID":
                current["uid"] = value
            elif key == "SUMMARY":
                current["summary"] = value or "Untitled event"
            elif key == "DTSTART":
                current["start"] = _parse_ics_datetime(value)
            elif key == "DTEND":
                current["end"] = _parse_ics_datetime(value)
            elif key == "LOCATION":
                current["location"] = value
    return events


class CalDAVClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _auth(self) -> tuple[str, str]:
        if not self.settings.caldav_configured:
            raise CalDAVError("CalDAV credentials are not configured")
        return self.settings.caldav_username or "", self.settings.caldav_password or ""

    async def calendar_home(self) -> str:
        body = """<?xml version='1.0' encoding='utf-8'?>
<d:propfind xmlns:d='DAV:' xmlns:c='urn:ietf:params:xml:ns:caldav'>
  <d:prop><c:calendar-home-set/></d:prop>
</d:propfind>"""
        async with httpx.AsyncClient(timeout=self.settings.upstream_timeout_seconds, follow_redirects=False) as client:
            response = await client.request("PROPFIND", self.settings.caldav_base_url + "/", content=body, headers={"Depth": "0", "Content-Type": "application/xml"}, auth=self._auth())
        if response.status_code != 207:
            raise CalDAVError(f"CalDAV discovery failed with HTTP {response.status_code}")
        root = ET.fromstring(response.text)
        href = root.find(f".//{{{CALDAV}}}calendar-home-set/{{{DAV}}}href")
        if href is None or not href.text:
            raise CalDAVError("CalDAV calendar-home-set was not returned")
        return href.text

    async def list_events(self, start: date, end: date) -> list[dict[str, str]]:
        home = await self.calendar_home()
        target = self.settings.caldav_base_url + home if home.startswith("/") else home
        start_utc = start.strftime("%Y%m%dT000000Z")
        end_utc = end.strftime("%Y%m%dT000000Z")
        body = f"""<?xml version='1.0' encoding='utf-8'?>
<c:calendar-query xmlns:d='DAV:' xmlns:c='urn:ietf:params:xml:ns:caldav'>
  <d:prop><d:getetag/><c:calendar-data/></d:prop>
  <c:filter><c:comp-filter name='VCALENDAR'><c:comp-filter name='VEVENT'><c:time-range start='{start_utc}' end='{end_utc}'/></c:comp-filter></c:comp-filter></c:filter>
</c:calendar-query>"""
        async with httpx.AsyncClient(timeout=self.settings.upstream_timeout_seconds, follow_redirects=False) as client:
            response = await client.request("REPORT", target, content=body, headers={"Depth": "1", "Content-Type": "application/xml"}, auth=self._auth())
        if response.status_code != 207:
            raise CalDAVError(f"CalDAV event query failed with HTTP {response.status_code}")
        root = ET.fromstring(response.text)
        events: list[dict[str, str]] = []
        for item in root.findall(f".//{{{CALDAV}}}calendar-data"):
            if item.text:
                events.extend(parse_vevents(item.text))
        return events
