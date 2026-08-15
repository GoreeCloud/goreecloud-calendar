from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from posixpath import normpath
from urllib.parse import unquote, urljoin, urlparse
from uuid import uuid4
import xml.etree.ElementTree as ET

import httpx
import recurring_ical_events
from icalendar import Calendar as ICalendar
from icalendar import Event as IEvent

from .models import CalendarSummary, EventSummary, EventWriteRequest


DAV = "DAV:"
CALDAV = "urn:ietf:params:xml:ns:caldav"
APPLE = "http://apple.com/ns/ical/"
NS = {"d": DAV, "c": CALDAV, "a": APPLE}


class CalDavError(RuntimeError):
    pass


class CalDavAuthenticationError(CalDavError):
    pass


class CalDavAuthorizationError(CalDavError):
    pass


class CalDavConflict(CalDavError):
    pass


class CalDavNotFound(CalDavError):
    pass


@dataclass(frozen=True, slots=True)
class CalDavSettings:
    base_url: str
    timeout_seconds: float
    max_query_days: int = 62


class CalDavClient:
    def __init__(
        self,
        settings: CalDavSettings,
        *,
        username: str,
        password: str,
    ) -> None:
        self.settings = settings
        self.username = username
        self.password = password

    def _auth(self) -> httpx.BasicAuth:
        return httpx.BasicAuth(self.username, self.password)

    def _resolve_safe_url(self, href: str) -> str:
        base = self.settings.base_url.rstrip("/") + "/"
        target = urljoin(base, href)
        base_parts = urlparse(base)
        target_parts = urlparse(target)
        if (
            target_parts.scheme != base_parts.scheme
            or target_parts.netloc != base_parts.netloc
        ):
            raise CalDavAuthorizationError(
                "CalDAV resource resolved outside the configured DAV server."
            )
        return target

    def _canonical_path(self, href: str) -> str:
        target = self._resolve_safe_url(href)
        path = unquote(urlparse(target).path)
        normalized = normpath("/" + path.lstrip("/"))
        return normalized.rstrip("/") or "/"

    @staticmethod
    def _validate_event_href(href: str) -> None:
        path = unquote(urlparse(href).path)
        if not path.lower().endswith(".ics"):
            raise CalDavAuthorizationError(
                "CalDAV event resources must use an .ics path."
            )

    async def _request(
        self,
        method: str,
        url: str,
        *,
        depth: str | None = None,
        body: str | bytes | None = None,
        headers: dict[str, str] | None = None,
        content_type: str | None = None,
    ) -> httpx.Response:
        current_url = self._resolve_safe_url(url)
        request_headers = {
            "Accept": "application/xml, text/xml, text/calendar",
        }
        if depth is not None:
            request_headers["Depth"] = depth
        if content_type is not None:
            request_headers["Content-Type"] = content_type
        elif body is not None:
            request_headers["Content-Type"] = "application/xml; charset=utf-8"
        if headers:
            request_headers.update(headers)

        try:
            async with httpx.AsyncClient(
                auth=self._auth(),
                timeout=self.settings.timeout_seconds,
                follow_redirects=False,
            ) as client:
                for _ in range(4):
                    response = await client.request(
                        method,
                        current_url,
                        headers=request_headers,
                        content=body,
                    )
                    if response.status_code not in {301, 302, 307, 308}:
                        break
                    location = response.headers.get("location")
                    if not location:
                        raise CalDavError("CalDAV redirect omitted a Location header.")
                    current_url = self._resolve_safe_url(urljoin(current_url, location))
                else:
                    raise CalDavError("CalDAV returned too many redirects.")
        except httpx.HTTPError as exc:
            raise CalDavError("Unable to reach the configured CalDAV server.") from exc

        if response.status_code == 401:
            raise CalDavAuthenticationError("CalDAV authentication failed.")
        if response.status_code == 403:
            raise CalDavAuthorizationError("CalDAV server denied access.")
        if response.status_code == 404:
            raise CalDavNotFound("CalDAV resource was not found.")
        if response.status_code == 412:
            raise CalDavConflict(
                "CalDAV precondition failed because the resource changed or already exists."
            )
        if response.status_code >= 400:
            raise CalDavError(f"CalDAV server returned HTTP {response.status_code}.")
        return response

    @staticmethod
    def _xml(response: httpx.Response) -> ET.Element:
        try:
            return ET.fromstring(response.content)
        except ET.ParseError as exc:
            raise CalDavError("CalDAV server returned invalid XML.") from exc

    @staticmethod
    def _response_prop(response_node: ET.Element, tag: str) -> ET.Element | None:
        for propstat in response_node.findall("d:propstat", NS):
            status = propstat.findtext("d:status", default="", namespaces=NS)
            if " 200 " not in f" {status} ":
                continue
            prop = propstat.find("d:prop", NS)
            if prop is None:
                continue
            value = prop.find(tag, NS)
            if value is not None:
                return value
        return None

    async def _discover_home_url(self) -> str:
        base_url = self.settings.base_url
        principal_body = """<?xml version="1.0" encoding="utf-8" ?>
<d:propfind xmlns:d="DAV:">
  <d:prop><d:current-user-principal /></d:prop>
</d:propfind>"""
        principal_response = await self._request(
            "PROPFIND", base_url, depth="0", body=principal_body
        )
        principal_root = self._xml(principal_response)
        principal_href = principal_root.findtext(
            ".//d:current-user-principal/d:href",
            default="",
            namespaces=NS,
        )
        if not principal_href:
            raise CalDavError("CalDAV principal discovery returned no principal URL.")

        principal_url = self._resolve_safe_url(principal_href)
        home_body = """<?xml version="1.0" encoding="utf-8" ?>
<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
  <d:prop><c:calendar-home-set /></d:prop>
</d:propfind>"""
        home_response = await self._request(
            "PROPFIND", principal_url, depth="0", body=home_body
        )
        home_root = self._xml(home_response)
        home_href = home_root.findtext(
            ".//c:calendar-home-set/d:href",
            default="",
            namespaces=NS,
        )
        if not home_href:
            raise CalDavError("CalDAV principal did not expose a calendar home set.")
        return self._resolve_safe_url(home_href)

    async def validate_credentials(self) -> None:
        await self._discover_home_url()

    async def discover_calendars(self) -> list[CalendarSummary]:
        home_url = await self._discover_home_url()
        body = """<?xml version="1.0" encoding="utf-8" ?>
<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"
            xmlns:a="http://apple.com/ns/ical/">
  <d:prop>
    <d:displayname />
    <d:resourcetype />
    <c:calendar-description />
    <a:calendar-color />
  </d:prop>
</d:propfind>"""
        response = await self._request("PROPFIND", home_url, depth="1", body=body)
        root = self._xml(response)
        calendars: list[CalendarSummary] = []

        for response_node in root.findall("d:response", NS):
            href = response_node.findtext("d:href", default="", namespaces=NS)
            if not href:
                continue
            resource_type = self._response_prop(response_node, "d:resourcetype")
            if resource_type is None or resource_type.find("c:calendar", NS) is None:
                continue

            display_node = self._response_prop(response_node, "d:displayname")
            description_node = self._response_prop(
                response_node, "c:calendar-description"
            )
            color_node = self._response_prop(response_node, "a:calendar-color")
            display_name = (
                (display_node.text or "").strip() if display_node is not None else ""
            )
            calendars.append(
                CalendarSummary(
                    href=self._canonical_path(href),
                    display_name=display_name or "Calendar",
                    description=(
                        (description_node.text or "").strip()
                        if description_node is not None
                        else ""
                    ),
                    color=(
                        (color_node.text or "").strip() or None
                        if color_node is not None
                        else None
                    ),
                )
            )
        return calendars

    async def _assert_calendar_access(self, calendar_href: str) -> str:
        requested = self._canonical_path(calendar_href)
        calendars = await self.discover_calendars()
        allowed = {self._canonical_path(calendar.href) for calendar in calendars}
        if requested not in allowed:
            raise CalDavAuthorizationError(
                "Requested calendar is not available to the authenticated user."
            )
        return self._resolve_safe_url(requested.rstrip("/") + "/")

    async def _assert_event_access(self, event_href: str) -> str:
        self._validate_event_href(event_href)
        event_path = self._canonical_path(event_href)
        calendars = await self.discover_calendars()
        for calendar in calendars:
            calendar_path = self._canonical_path(calendar.href).rstrip("/") + "/"
            if event_path.startswith(calendar_path):
                return self._resolve_safe_url(event_path)
        raise CalDavAuthorizationError(
            "Requested event is outside the authenticated user's calendars."
        )

    async def list_events(
        self,
        calendar_href: str,
        *,
        start: datetime,
        end: datetime,
    ) -> list[EventSummary]:
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("Calendar query range must be timezone-aware.")
        if end <= start:
            raise ValueError("Calendar query end must be after start.")
        if end - start > timedelta(days=self.settings.max_query_days):
            raise ValueError(
                f"Calendar query range cannot exceed {self.settings.max_query_days} days."
            )

        calendar_url = await self._assert_calendar_access(calendar_href)
        start_utc = start.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        end_utc = end.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        body = f"""<?xml version="1.0" encoding="utf-8" ?>
<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
  <d:prop>
    <d:getetag />
    <c:calendar-data />
  </d:prop>
  <c:filter>
    <c:comp-filter name="VCALENDAR">
      <c:comp-filter name="VEVENT">
        <c:time-range start="{start_utc}" end="{end_utc}" />
      </c:comp-filter>
    </c:comp-filter>
  </c:filter>
</c:calendar-query>"""
        response = await self._request(
            "REPORT", calendar_url, depth="1", body=body
        )
        root = self._xml(response)
        events: list[EventSummary] = []

        for response_node in root.findall("d:response", NS):
            href = response_node.findtext("d:href", default="", namespaces=NS)
            if not href:
                continue
            etag_node = self._response_prop(response_node, "d:getetag")
            data_node = self._response_prop(response_node, "c:calendar-data")
            if data_node is None or not data_node.text:
                continue
            try:
                parsed = ICalendar.from_ical(data_node.text)
            except Exception as exc:
                raise CalDavError("CalDAV returned invalid iCalendar data.") from exc

            components, series_recurring = self._expand_components(
                parsed, start=start, end=end
            )

            for component in components:
                events.append(
                    self._event_summary(
                        component,
                        href=self._canonical_path(href),
                        etag=(
                            (etag_node.text or "").strip()
                            if etag_node is not None
                            else None
                        ),
                        calendar_href=self._canonical_path(calendar_href),
                        recurring=series_recurring,
                    )
                )
        return events

    @staticmethod
    def _expand_components(
        parsed: ICalendar,
        *,
        start: datetime,
        end: datetime,
    ) -> tuple[list[IEvent], bool]:
        source_events = parsed.walk("VEVENT")
        series_recurring = any(
            component.get("RRULE") is not None
            or component.get("RDATE") is not None
            or component.get("RECURRENCE-ID") is not None
            for component in source_events
        )
        try:
            components = list(recurring_ical_events.of(parsed).between(start, end))
        except Exception as exc:
            raise CalDavError("Unable to expand recurring iCalendar data safely.") from exc
        return components, series_recurring

    @staticmethod
    def _serialize_dt(value: object) -> tuple[str, bool]:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.isoformat(), False
        if isinstance(value, date):
            return value.isoformat(), True
        raise CalDavError("Event contains an unsupported date/time value.")

    def _event_summary(
        self,
        component: IEvent,
        *,
        href: str,
        etag: str | None,
        calendar_href: str,
        recurring: bool | None = None,
    ) -> EventSummary:
        dtstart = component.decoded("DTSTART", None)
        if dtstart is None:
            raise CalDavError("VEVENT is missing DTSTART.")
        start, all_day = self._serialize_dt(dtstart)

        dtend = component.decoded("DTEND", None)
        if dtend is None:
            if all_day:
                dtend = dtstart + timedelta(days=1)
            else:
                dtend = dtstart
        end, _ = self._serialize_dt(dtend)

        uid = str(component.get("UID", "")).strip()
        if not uid:
            raise CalDavError("VEVENT is missing UID.")

        return EventSummary(
            href=href,
            etag=etag,
            calendar_href=calendar_href,
            uid=uid,
            summary=str(component.get("SUMMARY", "(Untitled event)")),
            description=str(component.get("DESCRIPTION", "")),
            location=str(component.get("LOCATION", "")),
            start=start,
            end=end,
            all_day=all_day,
            recurring=(
                recurring
                if recurring is not None
                else component.get("RRULE") is not None
                or component.get("RDATE") is not None
                or component.get("RECURRENCE-ID") is not None
            ),
        )

    async def create_event(self, payload: EventWriteRequest) -> EventSummary:
        calendar_url = await self._assert_calendar_access(payload.calendar_href)
        uid = f"{uuid4()}@goreecloud.com"
        resource_url = self._resolve_safe_url(urljoin(calendar_url, f"{uid}.ics"))
        calendar = ICalendar()
        calendar.add("prodid", "-//GoreeCloud//GoreeCloud Calendar//EN")
        calendar.add("version", "2.0")
        event = IEvent()
        event.add("uid", uid)
        event.add("dtstamp", datetime.now(timezone.utc))
        self._apply_write_fields(event, payload)
        calendar.add_component(event)
        response = await self._request(
            "PUT",
            resource_url,
            body=calendar.to_ical(),
            headers={"If-None-Match": "*"},
            content_type="text/calendar; charset=utf-8",
        )
        etag = response.headers.get("etag")
        return self._event_summary(
            event,
            href=self._canonical_path(resource_url),
            etag=etag,
            calendar_href=self._canonical_path(payload.calendar_href),
        )

    @staticmethod
    def _assert_nonrecurring_resource(calendar: ICalendar) -> IEvent:
        components = calendar.walk("VEVENT")
        if len(components) != 1:
            raise CalDavConflict(
                "Multi-component calendar resources are read-only in this release."
            )
        event = components[0]
        if (
            event.get("RRULE") is not None
            or event.get("RDATE") is not None
            or event.get("RECURRENCE-ID") is not None
            or event.get("EXDATE") is not None
        ):
            raise CalDavConflict(
                "Recurring-event writes are not enabled in this release."
            )
        return event

    async def update_event(
        self,
        event_href: str,
        payload: EventWriteRequest,
    ) -> EventSummary:
        if not payload.etag or not payload.etag.strip():
            raise CalDavConflict("An ETag is required to update an event.")
        resource_url = await self._assert_event_access(event_href)
        calendar_url = await self._assert_calendar_access(payload.calendar_href)
        event_path = self._canonical_path(event_href)
        calendar_path = self._canonical_path(calendar_url).rstrip("/") + "/"
        if not event_path.startswith(calendar_path):
            raise CalDavAuthorizationError(
                "Event does not belong to the requested calendar."
            )
        existing = await self._request("GET", resource_url)
        try:
            calendar = ICalendar.from_ical(existing.content)
        except Exception as exc:
            raise CalDavError("Stored event contains invalid iCalendar data.") from exc

        event = self._assert_nonrecurring_resource(calendar)
        self._apply_write_fields(event, payload)
        response = await self._request(
            "PUT",
            resource_url,
            body=calendar.to_ical(),
            headers={"If-Match": payload.etag.strip()},
            content_type="text/calendar; charset=utf-8",
        )
        return self._event_summary(
            event,
            href=self._canonical_path(event_href),
            etag=response.headers.get("etag") or payload.etag.strip(),
            calendar_href=self._canonical_path(payload.calendar_href),
        )

    async def delete_event(self, event_href: str, *, etag: str) -> None:
        if not etag.strip():
            raise CalDavConflict("An ETag is required to delete an event.")
        resource_url = await self._assert_event_access(event_href)
        existing = await self._request("GET", resource_url)
        try:
            calendar = ICalendar.from_ical(existing.content)
        except Exception as exc:
            raise CalDavError("Stored event contains invalid iCalendar data.") from exc
        self._assert_nonrecurring_resource(calendar)
        await self._request(
            "DELETE",
            resource_url,
            headers={"If-Match": etag.strip()},
        )

    @staticmethod
    def _apply_write_fields(event: IEvent, payload: EventWriteRequest) -> None:
        event["SUMMARY"] = payload.summary
        if payload.description:
            event["DESCRIPTION"] = payload.description
        elif "DESCRIPTION" in event:
            del event["DESCRIPTION"]
        if payload.location:
            event["LOCATION"] = payload.location
        elif "LOCATION" in event:
            del event["LOCATION"]

        for key in ("DTSTART", "DTEND"):
            if key in event:
                del event[key]

        if payload.all_day:
            start = date.fromisoformat(payload.start)
            end = date.fromisoformat(payload.end) if payload.end else start + timedelta(days=1)
            event.add("dtstart", start)
            event.add("dtend", end)
        else:
            start = datetime.fromisoformat(payload.start.replace("Z", "+00:00"))
            end = (
                datetime.fromisoformat(payload.end.replace("Z", "+00:00"))
                if payload.end
                else start + timedelta(hours=1)
            )
            event.add("dtstart", start)
            event.add("dtend", end)
