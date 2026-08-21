# GoreeCloud Calendar product foundation

## Role and authority

GoreeCloud Calendar is the user-facing GoreeCloud application for calendars, events, scheduling, agenda views, availability, and first-party productivity integration. The canonical application identity is `https://calendar.goreecloud.com`.

Radicale remains the authoritative standards-based DAV service at `https://dav.goreecloud.com`. Calendar must not create a competing authoritative event store merely to provide richer user experiences. Application caches, indexes, derived busy-time data, and Tasks projections must remain replaceable and rebuildable.

## Product capabilities

The target application provides day, week, month, agenda, and schedule views; event creation and editing; all-day and timed events; recurrence and exceptions; calendar membership and sharing; invitations where the underlying architecture supports them; search; reminders; availability and conflict visibility; import/export; timezone-aware scheduling; offline-tolerant client behavior where justified; and accessible responsive Glaze UI experiences.

## Tasks integration

Calendar renders Tasks work as projections, never detached duplicate events. Tasks remains authoritative for task state and recurrence. Calendar may request task creation or rescheduling only through versioned Tasks APIs, and Tasks may consume authorized Calendar busy/event context through versioned Calendar APIs. Peer failure must not make either application's native data unusable.

## Security and privacy

Every DAV or first-party integration request must be attributable to an approved identity and constrained to the user's authorized collections/objects. Reusable credentials remain outside source and ordinary documentation. Logs must not contain passwords, bearer tokens, private descriptions, or unnecessary event content. Destructive DAV writes require optimistic-concurrency evidence such as an ETag.

## Glaze UI 1.3

The Calendar interface uses the shared Canvas, Solid, Raised, Glaze, and Overlay hierarchy. Solid/Raised are default content surfaces; Glaze is reserved for navigation and interactive chrome where translucency improves hierarchy. Keyboard navigation, visible focus, reduced motion, reduced transparency, forced colors, practical touch targets, system/light/dark appearance support, and clear loading/empty/error/offline states are required.

## Production-readiness gates

Before production acceptance, validate isolated multi-user CalDAV authorization; create/update/delete with ETag conflict behavior; recurrence and timezone correctness; import/export round trips; Tasks integration authorization and peer-failure behavior; private DNS/Caddy/NetBird publication; Wardveil Security review; Privacy Shield data-flow review; monitoring; backup and restoration; upgrade/rollback behavior; accessibility; responsive visual acceptance; and real-browser/client acceptance against the exact candidate revision.
