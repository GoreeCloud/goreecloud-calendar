# Wardveil Security by GoreeCloud — Calendar

Wardveil Security is GoreeCloud Calendar's platform-wide security and protection identity and presentation layer. It does not replace the technical controls that enforce Calendar security.

## Technical authorities

- Radicale authenticates DAV identities and authorizes calendar collections.
- GoreeCloud Calendar creates bounded opaque application sessions after validating the supplied individual Radicale identity.
- Mutation requests require both the opaque session cookie and a session-bound CSRF token.
- CalDAV updates and deletes require current ETags; creates use `If-None-Match: *`.
- DAV hrefs are restricted to the configured HTTPS origin and event resources are restricted to the selected calendar collection.
- Caddy, NetBird, DNS, firewall policy, backup/recovery, secrets management, and vulnerability management remain separate authoritative controls.

## Privacy-minimized observability

Broad structured HTTP events contain only the service, event family, request identifier, HTTP method, path, response status, and duration. Authentication and mutation security events record event type and request identifier.

The logging contract excludes usernames, passwords, session/CSRF values, cookies, Authorization headers, DAV resource paths in security events, query strings, request/response bodies, event content, client IP addresses, user-agent strings, and raw upstream exception details.

## Browser and response policy

Dynamic responses receive request correlation, Wardveil identity metadata, CSP, frame denial, MIME sniffing prevention, no-referrer, same-origin opener/resource isolation, Origin-Agent-Cluster, cross-domain policy denial, a restrictive Permissions Policy, and no-store caching.

## Secure-default boundary

Production configuration defaults to individual passthrough authentication and disabled writes. Enabling writes is an explicit deployment decision after isolated synthetic CalDAV acceptance, backup/recovery validation, manual Glaze/accessibility acceptance, and production approval.
