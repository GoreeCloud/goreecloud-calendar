# Security Policy

GoreeCloud Calendar is under active development and is not yet approved for production use.

## Implemented security boundary

- Radicale remains authoritative for calendar data.
- Browser sessions are opaque, HttpOnly, SameSite=Strict, and required to be Secure in production.
- Radicale passwords remain only in backend process memory for the bounded session lifetime.
- Sessions have absolute expiry, idle expiry, a global cap, and a per-user cap.
- State-changing requests require a separate per-session CSRF token compared in constant time.
- Failed sign-ins are rate-limited using a process-local limiter keyed by a hash of the normalized username.
- Production configuration fails closed if CalDAV is not HTTPS, Secure cookies are disabled, trusted hosts are wildcarded, or other security limits are invalid.
- Calendar query windows are bounded to limit accidental or abusive expansion work.
- CalDAV resource URLs are constrained to the configured DAV origin, including redirects.
- Event resources must use `.ics` paths and writes must remain inside an authorized discovered calendar.
- Event updates and deletes require ETags; creates use `If-None-Match: *`.
- The CalDAV write gate defaults to disabled.
- Recurring resources are displayable as expanded occurrences but recurring writes remain blocked.
- The container runs as a non-root user; Compose drops all Linux capabilities, applies `no-new-privileges`, and uses a read-only filesystem.
- The frontend has no external scripts, styles, fonts, analytics, trackers, or CDN dependencies.

## Current production blockers

The session store and login limiter are process-local and require the documented single-worker runtime. Production approval still requires representative two-user isolation against Radicale, final Caddy/HTTPS and Secure-cookie verification, backup/restore and rollback evidence, monitoring, dependency and container vulnerability evidence, production DNS/NetBird/firewall review, recurrence-write decisions, and Glaze UI accessibility/browser acceptance.

## Reporting

Do not place credentials, private calendar data, session tokens, or other secrets in public issues. Use a private GoreeCloud security reporting channel.
