# GoreeCloud Calendar Architecture

## Role and purpose

GoreeCloud Calendar is the user-facing GoreeCloud calendar application. It provides a Glaze UI web experience for calendar discovery, event viewing, and controlled event management.

The application does not replace Radicale and does not create a competing authoritative calendar database.

## Service identities

- `calendar.goreecloud.com` — GoreeCloud Calendar application
- `dav.goreecloud.com` — shared Radicale DAV service

Calendar uses CalDAV through the authenticated user's Radicale identity. Contacts and Calendar therefore remain separate user-facing applications while sharing the standards-based DAV service.

## Application layers

```text
Browser
  │ HTTPS / same-origin API
  ▼
GoreeCloud Calendar
  ├── Glaze UI frontend
  ├── FastAPI application/API boundary
  ├── bounded opaque session store
  ├── login-abuse guard
  └── CalDAV adapter
        │ authenticated per-user CalDAV
        ▼
Radicale at dav.goreecloud.com
        │
        └── authoritative calendars and .ics resources
```

## Multi-user boundary

Each user signs in with an individual Radicale identity. The backend holds that user's reusable DAV credential only in process memory for the bounded session lifetime. The browser receives an opaque session cookie and a separate CSRF token. Calendar discovery is performed under that user's DAV authorization and all requested calendar/event resources are revalidated against discovered authorized collections.

The current session and login-abuse stores are intentionally process-local. The approved runtime therefore remains one backend worker. Multi-worker operation requires a separately approved shared session and throttling design.

## Calendar and recurrence behavior

Radicale is queried with CalDAV calendar-query REPORT requests over a bounded date window. Returned iCalendar resources are parsed with `icalendar`. Recurrence expansion is performed in the application read path so recurring series, exclusions, and overrides can be represented as occurrences within the requested view window.

Recurring resources remain read-only in this stage. GoreeCloud Calendar does not yet modify a series or individual occurrence because recurrence writes require explicit sequence, recurrence-ID, exception, and interoperability validation.

## Write safety

CalDAV writes are controlled by `GOREECLOUD_CALENDAR_CALDAV_WRITE_ENABLED`, which defaults to false. When enabled:

- new resources use `If-None-Match: *`;
- updates and deletes require the current ETag through `If-Match`;
- event paths must resolve to `.ics` resources;
- cross-origin DAV URLs are rejected;
- redirects are followed only after same-origin validation;
- calendar and event membership are checked against the authenticated user's discoverable calendars;
- recurring writes remain blocked.

## Security controls

The application includes explicit trusted-host validation, HttpOnly/SameSite session cookies, Secure-cookie enforcement in production, per-session CSRF tokens, constant-time CSRF comparison, restrictive CSP and browser security headers, HSTS in production, bounded session counts, absolute and idle session expiry, login throttling, bounded calendar query ranges, non-root Docker execution, capability dropping, `no-new-privileges`, and a read-only runtime filesystem.

## Production boundary

Source validation does not authorize production. Before production deployment I must separately validate representative multi-user isolation against Radicale, the final Caddy/HTTPS path, Secure cookies, Radicale migration/coexistence, monitoring, backup/restore and rollback, image/dependency vulnerability evidence, production network boundaries, and Glaze UI browser/accessibility acceptance.
