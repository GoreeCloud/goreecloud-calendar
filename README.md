# GoreeCloud Calendar

GoreeCloud Calendar is a native, privacy-first, multi-user calendar web application built for the GoreeCloud platform with the **Glaze UI Design Language**.

**Project status:** Active development — hardened native Docker and Glaze UI web foundation. Not approved for production use.

## Architecture

- User-facing application: `https://calendar.goreecloud.com`
- Authoritative CardDAV/CalDAV service: `https://dav.goreecloud.com`
- DAV server: Radicale
- Application model: server-side CalDAV adapter; no competing calendar database
- Interface: GoreeCloud Glaze UI
- Deployment model: Docker / Docker Compose

GoreeCloud Calendar authenticates each user against Radicale and performs CalDAV operations using that individual identity. Radicale remains authoritative for calendar collections and `.ics` event resources.

## Web experience

The browser application is intentionally built as a GoreeCloud product rather than a default framework interface. The frontend separates shared Glaze UI foundations from Calendar-specific composition:

- `frontend/glaze.css` — shared Glaze design tokens, surfaces, controls, fields, theme architecture, focus behavior, motion, and accessibility fallbacks.
- `frontend/styles.css` — Calendar-specific shell, navigation, month grid, schedule view, event presentation, context rail, dialogs, and responsive behavior.
- `frontend/app.js` — dependency-free same-origin browser behavior and Calendar interactions.

Current web capabilities include:

- Month view with selectable calendars, Today/month navigation, current-day emphasis, keyboard-accessible events, and Radicale calendar colors when available.
- Schedule view with date-grouped events, time, calendar, location, and recurrence context.
- Local search across the events already loaded into the current view; search text is not sent to a third-party service.
- Wide-screen Today and Coming Up context rail.
- Explicit Select All/Clear calendar controls and per-calendar loaded-view counts.
- Responsive desktop, tablet, and mobile interaction models rather than a desktop layout that merely shrinks.
- Mobile calendar-navigation overlay and dedicated Today/Calendars/New quick-action bar.
- Glaze UI loading, empty, error, confirmation, connection-status, and toast feedback.
- System, light, and dark appearance modes.
- Reduced-motion and reduced-transparency operating-system preference support.
- Keyboard shortcuts: `/` search, `N` new event, `T` Today, and left/right arrows for month navigation.
- No external browser scripts, stylesheets, fonts, analytics, trackers, advertising SDKs, or CDN dependencies.

See `docs/glaze-ui.md` for the web design-system implementation boundary.

## Application and security capabilities

- Individual Radicale-backed login.
- Opaque HttpOnly SameSite sessions.
- Absolute and idle session expiry with per-user/global session caps.
- Bounded login-abuse throttling without retaining plaintext usernames in the limiter.
- Per-session CSRF token for state-changing operations.
- Per-user CalDAV calendar discovery and authorization checks.
- Bounded date-range queries.
- Recurring-series expansion for read-only occurrence display.
- Controlled event creation, update, and deletion when the write gate is enabled.
- `If-None-Match: *` on create and ETag `If-Match` protection on update/delete.
- Recurring-series and occurrence writes intentionally blocked pending interoperability validation.
- Liveness and readiness endpoints.
- Production configuration validation that fails closed for unsafe DAV/cookie/trusted-host settings.
- Docker hardening: non-root runtime, capability drop, `no-new-privileges`, read-only filesystem, loopback-only development port.

## Validation

CI validates all three major boundaries:

- **Backend:** dependency installation, dependency consistency, Python compilation, and pytest.
- **Frontend:** JavaScript syntax and `scripts/validate_frontend.py` Glaze UI structural validation.
- **Docker:** image build, non-root image user, and hardened read-only/capability-dropped/no-new-privileges runtime smoke test.

The Glaze UI validator checks required shared layers and controls, unique IDs, explicit button types, browser dependency isolation, theme architecture, reduced motion/transparency, adaptive mobile structure, Schedule/search behavior, safe DOM-construction rules, and consistency between JavaScript element references and HTML IDs.

Structural validation complements rather than replaces visual acceptance in representative browsers, themes, viewports, keyboard-only use, assistive technology, and touch devices.

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
- representative Glaze UI visual, accessibility, touch, and supported-browser acceptance;
- reproducible transitive dependency locking before Stable release.

See `docs/architecture.md`, `docs/dependencies.md`, `docs/glaze-ui.md`, and `SECURITY.md`.
