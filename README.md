# GoreeCloud Calendar

GoreeCloud Calendar is the native GoreeCloud calendar application: a privacy-first, self-hosted Glaze UI web experience over the authoritative GoreeCloud CalDAV service.

## Architecture

- User-facing application: `https://calendar.goreecloud.com`
- Authoritative CalDAV service: `https://dav.goreecloud.com`
- Radicale remains authoritative for calendar data, DAV identity, and collection authorization.
- GoreeCloud Calendar does not maintain a competing calendar database or account database.
- Production multi-user access uses individually attributable Radicale identities through a bounded application-session layer.
- DAV hrefs are same-origin validated and event resources must remain descendants of their selected calendar collection before mutation.

## Security model

Wardveil Security by GoreeCloud is Calendar's security/protection identity and presentation layer. The technical controls remain explicit and independently testable:

- opaque HttpOnly/Secure/SameSite session cookies
- server-memory-only DAV credentials with bounded session lifetime and capacity
- session-bound CSRF verification for create/update/delete
- `If-None-Match: *` create protection
- mandatory current `If-Match` ETags for update/delete
- explicit stale-resource conflict handling
- HTTPS-only configured DAV origin
- selected-calendar resource containment
- 256 KiB iCalendar mutation limit and structural validation
- CSP, frame denial, MIME-sniffing prevention, no-referrer policy, browser isolation, restrictive Permissions Policy, no-store responses, and no-index metadata
- privacy-minimized structured request/security events with bounded request correlation

Broad observability deliberately excludes credentials, usernames, cookies, session/CSRF values, request bodies, calendar content, client IP addresses, user-agent strings, and raw upstream exception details.

## Glaze UI 1.0

The complete controlled experience uses Glaze UI 1.0, including:

- authentication, navigation, calendar filters, month view, agenda, event dialogs, notices, toasts, loading, empty, error, disabled, success, warning, and destructive states
- semantic design tokens and the Canvas/Solid/Raised/Glaze/Overlay hierarchy
- System, Light, and Dark appearance stored locally in the browser
- Compact, Medium, Expanded, and Wide adaptive ranges
- keyboard focus, practical targets, reduced motion, reduced transparency, increased contrast, forced colors, and solid translucency fallbacks
- no remote fonts, icons, UI frameworks, analytics, or tracking dependencies

See `docs/GLAZE_UI_CONFORMANCE.md`.

## Authentication and writes

Production defaults to `CALDAV_AUTH_MODE=passthrough`. A successful sign-in validates the individual's Radicale identity and creates an opaque application session. DAV credentials remain only in bounded server memory for the session lifetime.

`CALDAV_WRITE_ENABLED=false` remains the secure default. When explicitly enabled after the required acceptance gates, Calendar exposes guarded create/update/delete workflows. Recurring events remain protected from the simplified editor because recurrence-series and exception semantics must not be silently rewritten; users may view recurring events normally and use an approved CalDAV client for recurrence changes until a recurrence-native editor is separately validated.

## Runtime

The container runs as UID/GID `65532:65532`, drops Linux capabilities, enables `no-new-privileges`, uses a read-only root filesystem with bounded `/tmp`, and publishes no host port through the repository Compose topology. Network egress remains available because Calendar must reach `https://dav.goreecloud.com`; deployment-time Caddy/private-network attachment remains a separate controlled infrastructure action.

The production image currently targets the supported Python `3.12.13-slim-bookworm` line. CI performs dependency auditing, tests/coverage, compilation, non-root runtime verification, Compose validation, HIGH/CRITICAL container vulnerability and secret/misconfiguration scanning, and CycloneDX SBOM generation.

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
# For local HTTP only, set SECURE_COOKIES=false in the untracked .env file.
uvicorn app.main:app --reload
```

Then open `http://127.0.0.1:8000`.

## Production readiness

Source hardening does not authorize production cutover. `docs/PRODUCTION_READINESS.md` defines the fail-closed release gates for isolated synthetic Radicale write testing, collection isolation, recurrence compatibility, backup/restore, Caddy/TLS/private DNS/NetBird behavior, monitoring, rollback, manual Glaze/accessibility acceptance, and explicit cutover approval.

No source-development step should modify production DNS, Caddy, NetBird, firewall policy, Radicale accounts, production calendar data, backup state, or monitoring configuration without a separate controlled deployment and validation process.

## License

AGPL-3.0-only.
