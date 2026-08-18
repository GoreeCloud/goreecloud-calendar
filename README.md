# GoreeCloud Calendar

GoreeCloud Calendar is the native GoreeCloud calendar application. It provides a privacy-first, self-hosted web interface over the authoritative GoreeCloud CalDAV service.

## Architecture

- User-facing application: `https://calendar.goreecloud.com`
- Authoritative CalDAV service: `https://dav.goreecloud.com`
- Calendar data remains authoritative in Radicale/CalDAV. GoreeCloud Calendar does not maintain a competing calendar database.
- The backend validates every CalDAV href against the configured DAV origin before following it.
- Calendar event resources must remain descendants of their selected calendar collection before any mutation primitive can operate on them.

## Authentication modes

The foundation supports two backend authentication modes:

- `service` — the current read-only compatibility mode. CalDAV credentials are supplied through server-side environment configuration and are never embedded in browser assets.
- `passthrough` — request-scoped identity mode. Each Calendar API request must authenticate with that user's own Radicale credentials, and only that identity is forwarded to CalDAV.

Passthrough authentication is the required identity model for future multi-user write support. It prevents one shared application credential from becoming the authorization boundary for multiple users.

## Current foundation

The application currently provides:

- FastAPI backend and health endpoint
- server-side CalDAV home and calendar-collection discovery
- multiple-calendar event retrieval with calendar identity and color metadata
- resource href and ETag preservation
- bounded upstream timeouts and fail-closed configuration
- iCalendar line unfolding, text unescaping, all-day detection, timezone metadata, and recurrence metadata preservation
- normalized event API for the browser
- responsive Glaze UI month/agenda experience
- System, Light, and Dark appearance modes stored locally in the browser
- accessible keyboard/focus treatment and reduced-motion support
- Docker/Compose development packaging
- automated backend tests and GitHub Actions CI

## Conditional-write foundation

Internal CalDAV mutation primitives are implemented but are **not exposed as Calendar HTTP CRUD endpoints**.

The write foundation enforces:

- `CALDAV_WRITE_ENABLED=false` by default
- passthrough authentication as a prerequisite for write availability
- `If-None-Match: *` when creating a new event resource
- mandatory `If-Match` with the current ETag when updating or deleting an existing event
- HTTP `412 Precondition Failed` conversion to an explicit conflict condition
- same-origin DAV href validation
- selected-calendar resource containment checks
- a 256 KiB iCalendar payload safety limit
- minimum VCALENDAR/VEVENT structural validation

These primitives exist so isolated synthetic Radicale testing can validate conflict semantics before any browser mutation path is enabled.

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
uvicorn app.main:app --reload
```

Then open `http://127.0.0.1:8000`.

## Safety and remaining gates

The user-facing Calendar application remains read-only. Event create/update/delete API routes must not be added until request-scoped identity behavior, isolated Radicale conditional writes, recurrence compatibility, backup/recovery, and production acceptance are validated.

No development step should change production DNS, Caddy, NetBird, Radicale accounts, existing calendar data, or production publication without a separate controlled deployment and validation process.

## License

AGPL-3.0-only.
