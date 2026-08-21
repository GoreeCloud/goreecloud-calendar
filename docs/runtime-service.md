# Calendar runtime service boundary

GoreeCloud Calendar treats the authenticated application principal as a capability scope, not as a client-controlled field. Production authentication middleware must resolve the user identity and permitted CalDAV collections before invoking the Calendar runtime service.

The runtime service enforces collection membership for every read and write, applies an explicit write capability for mutations, and rejects destructive event hrefs that escape the authorized calendar collection. The HTTP adapter never accepts a subject or permission set from request JSON.

Radicale at `https://dav.goreecloud.com` remains authoritative. The Calendar runtime service may query and mutate authorized CalDAV resources but does not introduce an authoritative application database.

Busy-time responses are deliberately privacy-minimized. They expose only the requested window and merged occupied intervals. Titles, descriptions, locations, event identifiers, and calendar membership must not be included in the Tasks-facing projection.

Production work still requires identity-provider/session integration, secret retrieval, CSRF and browser-origin controls where applicable, rate and abuse controls, hardened error handling and observability, real Radicale acceptance, and deployment-specific security review.