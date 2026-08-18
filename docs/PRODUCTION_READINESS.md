# GoreeCloud Calendar Production Readiness

GoreeCloud Calendar uses a fail-closed production-readiness model. Source validation is necessary but does not by itself authorize production publication or enable CalDAV writes.

## Source and repository gates

- Automated tests and minimum coverage pass.
- Python dependency consistency and vulnerability audit pass.
- Hardened container builds and runs as the non-root runtime identity.
- HIGH/CRITICAL container vulnerability scan passes or has a documented GoreeCloud exception.
- CycloneDX SBOM evidence is generated and retained.
- Compose renders successfully with no directly published application port.
- No reusable credential, DAV password, session identifier, CSRF token, private key, or production data is committed.
- Docker build context explicitly excludes local secrets, Git metadata, virtual environments, caches, and test artifacts.

## Authentication, authorization, and privacy gates

- Every Calendar user authenticates with an individually attributable Radicale identity; shared DAV service credentials are unsupported.
- The browser receives only an opaque HttpOnly/Secure/SameSite session cookie. DAV credentials remain in bounded server memory for the session lifetime.
- Mutations require a valid session and session-bound CSRF token.
- Radicale remains authoritative for collection authorization; Calendar does not create a second user or permission database.
- Authentication or authorization revocation from Radicale invalidates the application session on the next DAV operation.
- Logs and broad HTTP observability exclude usernames, passwords, cookies, authorization data, DAV hrefs, request bodies, client IP addresses, user-agent strings, calendar content, and raw upstream exception detail.

## Wardveil Security gates

- Wardveil Security by GoreeCloud is the security/protection identity and presentation layer.
- Underlying technical authorities remain application session controls, Radicale authentication/authorization, Caddy, NetBird, firewall policy, secrets management, vulnerability management, backup, recovery, and rollback.
- Security-facing responses include the Wardveil identity metadata without using branding as evidence that an individual control succeeded.
- CSP, clickjacking denial, MIME sniffing prevention, HSTS, no-referrer, browser isolation, permissions policy, no-store caching, and no-index behavior are validated.

## Glaze UI 1.0 gates

- Semantic design tokens and the Canvas/Solid/Raised/Glaze/Overlay hierarchy are present.
- Authentication, calendar navigation, filters, event detail/editing, dialogs, notices, loading, empty, error, success, disabled, and destructive states use Glaze patterns.
- System, Light, and Dark appearance are supported locally without analytics, trackers, remote fonts, or remote icon/UI dependencies.
- Compact, Medium, Expanded, and Wide layout ranges are implemented.
- Visible focus, keyboard access, practical targets, reduced motion, reduced transparency, increased contrast, forced colors, and solid translucency fallbacks are present.
- Complex event types that cannot yet be safely round-tripped by the simplified editor are viewable but mutation-protected with an explicit Glaze explanation and approved CalDAV-client fallback.
- Manual visual acceptance remains required on representative desktop and mobile-width browsers before Stable classification.

## Target-environment gates

Before `CALDAV_WRITE_ENABLED=true` or production Stable classification:

1. Create a dedicated synthetic Radicale Calendar acceptance identity and synthetic calendar; never use family production data for first-write validation.
2. Validate login, logout, session expiration, expected denied access, collection isolation, create, update, delete, stale-ETag conflict, and CSRF rejection against that isolated identity.
3. Validate calendar discovery, event retrieval, timezone handling, all-day behavior, recurrence read compatibility, and mutation-protection behavior with representative fixtures.
4. Validate Caddy routing, TLS, private DNS, NetBird access, expected public denial, and absence of direct host-port publication.
5. Validate monitoring, privacy-minimized structured operational logs, request correlation, and actionable degraded/error states.
6. Verify backup/recovery coverage for authoritative Radicale calendar data and perform a representative restoration according to GoreeCloud backup standards.
7. Validate rollback with writes disabled and confirm no application-owned authoritative calendar state is required for recovery.
8. Perform manual Glaze UI and accessibility acceptance across representative System/Light/Dark, Compact/Medium/Expanded/Wide, keyboard-only, zoom/reflow, increased-contrast, forced-colors, reduced-motion, and reduced-transparency conditions.
9. Obtain explicit production cutover approval.

Unknown, skipped, unavailable, or unverified required gates do not count as passing.
