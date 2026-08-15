# GoreeCloud Calendar Architecture

## Role

GoreeCloud Calendar is the user-facing calendar application at `https://calendar.goreecloud.com`.

Radicale remains the authoritative CardDAV/CalDAV service at `https://dav.goreecloud.com`. GoreeCloud Calendar is an application and presentation layer over CalDAV and must not create a competing authoritative event database.

## Data flow

```text
Browser
  -> GoreeCloud Calendar
  -> server-side CalDAV adapter
  -> https://dav.goreecloud.com
  -> Radicale
  -> calendars and VEVENT resources
```

The browser never receives reusable Radicale credentials after login. The backend holds the credential only inside the opaque in-memory session record for its lifetime.

## Multi-user boundary

Each user signs in with an individually attributable Radicale identity. Calendar discovery and every event read/write are performed with that user's credentials. The backend additionally constrains calendar and event hrefs to resources discovered for the authenticated identity.

## Foundation limitations

This milestone deliberately uses a process-local session store and one backend worker. It is suitable for development and controlled validation, not production approval. Recurring events are displayed and identified, but recurring-series editing is read-only in the foundation release. Recurrence instances are not yet expanded into a full series-aware editing model. The application does not create or manage Radicale user accounts.

## Docker boundary

The image runs as a non-root user, uses a read-only root filesystem through Compose, drops all Linux capabilities, and binds the development host port only to `127.0.0.1`. Production publication belongs behind the approved GoreeCloud Caddy/private-service path rather than a directly exposed application port.
