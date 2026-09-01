# Free-Time Planning Boundary

GoreeCloud Calendar can derive candidate free intervals from an authenticated user's authorized calendar without exposing event content.

## Contract

`GET /api/v1/free-time` accepts:

- an authorized `calendar` collection href;
- timezone-aware `starts_at` and `ends_at` boundaries; and
- optional `minimum_minutes` from 1 through 1440, defaulting to 30.

The response uses `goreecloud.calendar.free.v1` and contains only:

- schema and version;
- requested time range;
- minimum qualifying duration;
- returned interval count; and
- free interval start/end timestamps.

## Privacy boundary

Free time is derived from the same merged busy intervals used by `goreecloud.calendar.busy.v1`. The free-time projection does not return event UID, title, description, location, attendee data, calendar name, ETag, resource href, CalDAV backend information, or credentials.

The calculation remains collection-scoped through `CalendarPrincipal.require_calendar`. Read access is sufficient; the endpoint performs no event mutation.

## Authority boundary

Radicale/CalDAV remains authoritative for calendar data. This feature queries events through the existing `CalendarStore` boundary and derives transient availability in memory. It introduces no second calendar database or synchronization authority.

## Integration boundary

This is a Calendar-native planning primitive. Peer applications such as GoreeCloud Tasks may consume privacy-minimized availability only through separately authorized GoreeCloud application contracts. They must not bypass Calendar authorization with direct Radicale access or shared cross-user credentials.

## Acceptance boundary

This source increment does not by itself establish Glaze UI 2.1 conformance, delegated peer-application authorization, production deployment, target-environment acceptance, or Stable qualification. Those remain separate evidence-bearing gates.
