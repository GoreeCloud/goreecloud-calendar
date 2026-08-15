# GoreeCloud Calendar

GoreeCloud Calendar is a native, privacy-first, multi-user calendar web application built for the GoreeCloud platform.

**Project status:** Active development — native Docker foundation. Not approved for production use.

## Architecture

- User-facing application: `https://calendar.goreecloud.com`
- Authoritative CardDAV/CalDAV service: `https://dav.goreecloud.com`
- DAV server: Radicale
- Application model: server-side CalDAV adapter; no competing calendar database
- Interface: GoreeCloud Glaze UI
- Deployment model: Docker / Docker Compose

GoreeCloud Calendar authenticates users against Radicale and performs CalDAV operations using the authenticated user's identity. Radicale remains authoritative for calendar collections and event resources.

## Foundation features

- Individual Radicale-backed login
- Opaque HttpOnly sessions
- Per-session CSRF token for state-changing operations
- Per-user CalDAV calendar discovery
- Month calendar view with selectable calendars
- Responsive Glaze UI with light/dark/system appearance
- Event reading over CalDAV
- Safe event creation, update, and deletion when the write gate is enabled
- `If-None-Match: *` on create and ETag `If-Match` protection on update/delete
- Recurring-event visibility with intentionally read-only recurring edits
- Liveness and readiness endpoints
- Docker hardening: non-root runtime, capability drop, no-new-privileges, read-only filesystem, loopback-only development port
- CI for Python tests, JavaScript syntax, frontend dependency isolation, and Docker build

## Local Docker development

```bash
cp .env.example .env
docker compose up --build
```

Open `http://127.0.0.1:8086`.

The example configuration keeps `GOREECLOUD_CALENDAR_CALDAV_WRITE_ENABLED=false`. Use synthetic/test calendars and explicitly enable the gate only when controlled write validation is intended.

## Security and data ownership

The browser does not receive the reusable Radicale password after authentication. The password is held only in backend process memory for the session lifetime. DAV URLs are constrained to the configured DAV origin, and the backend verifies calendar/event resource membership before writes.

Do not place real credentials in `.env`, documentation, source code, screenshots, issues, or commits.

## Production-readiness boundary

This repository is not production-approved. Before production use, validate at minimum:

- representative two-user isolation;
- shared/durable session strategy or an explicitly approved one-worker operating model;
- HTTPS `Secure` cookie behavior;
- CSRF behavior through the production Caddy path;
- Radicale `dav.goreecloud.com` runtime migration and client coexistence;
- backup, restore, rollback, and portability;
- dependency/container vulnerability evidence;
- monitoring and health checks;
- production Caddy, DNS, NetBird, firewall, and port boundaries;
- recurring-event behavior and desired editing semantics;
- Glaze UI accessibility and browser acceptance.

See `docs/architecture.md` and `SECURITY.md`.
