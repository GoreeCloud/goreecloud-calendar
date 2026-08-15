# Security Policy

GoreeCloud Calendar is under active development and is not yet approved for production use.

## Security model

- Radicale remains authoritative for calendar data.
- Browser sessions are opaque and HttpOnly.
- Radicale passwords remain server-side in process memory for the session lifetime.
- State-changing requests require a per-session CSRF token.
- CalDAV resource URLs are constrained to the configured DAV origin.
- Event resources must use `.ics` paths and updates must remain within the requested authorized calendar.
- Event updates and deletes require ETags.
- Event creation uses `If-None-Match: *`.
- The CalDAV write gate defaults to disabled.
- The container drops Linux capabilities, uses `no-new-privileges`, runs as a non-root user, and is read-only at runtime through Compose.

## Current production blockers

The process-local session store is intentionally a foundation implementation and does not support multiple backend workers or durable session revocation. Recurring-event editing is also intentionally read-only. Production deployment requires representative multi-user isolation testing, login-abuse controls appropriate to the final access path, backup/recovery validation, exact runtime configuration review, dependency and container vulnerability review, Caddy/DNS/NetBird validation, secure-cookie validation under HTTPS, monitoring, and rollback evidence.

## Reporting

Do not place credentials, private calendar data, session tokens, or other secrets in public issues. Use a private GoreeCloud security reporting channel.
