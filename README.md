# GoreeCloud Calendar

GoreeCloud Calendar is a native, privacy-first, multi-user calendar web application built for the GoreeCloud platform with the Glaze UI Design Language.

**Project status:** Active development — hardened native Docker foundation. Not approved for production use.

## Architecture

- User-facing application: `https://calendar.goreecloud.com`
- Authoritative CardDAV/CalDAV service: `https://dav.goreecloud.com`
- DAV server: Radicale
- Application model: server-side CalDAV adapter; no competing calendar database
- Interface: GoreeCloud Glaze UI
- Deployment model: Docker / Docker Compose

GoreeCloud Calendar authenticates each user against Radicale and performs CalDAV operations using that individual identity. Radicale remains authoritative for calendar collections and `.ics` event resources.

## Current capabilities

- Individual Radicale-backed login
- Opaque HttpOnly SameSite sessions
- Absolute and idle session expiry with per-user/global session caps
- Bounded login-abuse throttling without retaining plaintext usernames in the limiter
- Per-session CSRF token for state-changing operations
- Per-user CalDAV calendar discovery and authorization checks
- Bounded date-range queries
- Month calendar with selectable calendars, Today/month navigation, keyboard shortcuts, and Radicale calendar colors when available
- Recurring-series expansion for read-only occurrence display
- Controlled event creation, update, and deletion when the write gate is enabled
- `If-None-Match: *` on create and ETag `If-Match` protection on update/delete
- Recurring-series and occurrence writes intentionally blocked pending interoperability validation
- Responsive, dependency-free Glaze UI with light/dark/system appearance
- Liveness and readiness endpoints
- Production configuration validation that fails closed for unsafe DAV/cookie/trusted-host settings
- Docker hardening: non-root runtime, capability drop, `no-new-privileges`, read-only filesystem, loopback-only development port
- CI for dependency consistency, Python tests, JavaScript syntax, frontend dependency isolation, Docker build, non-root image validation, and hardened runtime smoke testing

## Local Docker development

```bash
cp .env.example .env
docker compose up --build
```

Open `http://127.0.0.1:8086`.

The example configuration keeps `GOREECLOUD_CALENDAR_CALDAV_WRITE_ENABLED=false`. Use synthetic/test calendars and explicitly enable the gate only for controlled write validation.

## Security and data ownership

The browser does not receive the reusable Radicale password after authentication. The password remains only in backend process memory for the bounded session lifetime. DAV URLs are constrained to the configured DAV origin, redirects are revalidated, and the backend verifies calendar/event membership before writes.

Do not place real credentials in `.env`, documentation, source code, screenshots, issues, or commits.

## Current operating model

The session store and login limiter are process-local by design, so the approved development runtime uses exactly one application worker. Do not increase the worker count without first implementing and validating a shared session/throttling design.

## Production-readiness boundary

This repository is not production-approved. Before production use, validate at minimum:

- representative two-user isolation against the target Radicale instance;
- HTTPS and `Secure` cookie behavior through the production Caddy path;
- Radicale `dav.goreecloud.com` runtime migration and client coexistence;
- backup, restore, rollback, and portable `.ics` recovery;
- dependency and container vulnerability evidence;
- monitoring and health-check integration;
- production Caddy, DNS, NetBird, firewall, and port boundaries;
- recurring-series/occurrence write semantics if those features are enabled later;
- Glaze UI accessibility and supported-browser acceptance;
- reproducible transitive dependency locking before Stable release.

See `docs/architecture.md`, `docs/dependencies.md`, and `SECURITY.md`.
