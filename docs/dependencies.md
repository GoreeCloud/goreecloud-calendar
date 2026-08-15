# Direct Runtime Dependencies

GoreeCloud Calendar keeps its direct application dependency set intentionally small. Versions are explicitly pinned in `backend/pyproject.toml`; transitive dependency locking remains a Stable-release gate.

| Dependency | Pinned version | Role | License |
|---|---:|---|---|
| FastAPI | 0.139.2 | HTTP application/API framework | MIT |
| HTTPX | 0.28.1 | outbound CalDAV HTTP client | BSD-3-Clause |
| icalendar | 7.2.2 | RFC 5545 iCalendar parsing and generation | BSD-2-Clause |
| recurring-ical-events | 3.8.2 | recurrence, exclusion, and override expansion for the read path | LGPL-3.0-or-later |

## Dependency boundary

The browser frontend has no third-party runtime dependencies. It ships only GoreeCloud-owned HTML, CSS, and JavaScript.

`recurring-ical-events` is used only to interpret occurrence views returned from Radicale. GoreeCloud Calendar continues to store and write standards-based `.ics` resources through CalDAV rather than using a proprietary calendar representation.

Before Stable release, GoreeCloud Calendar must add a reproducible transitive dependency lock and collect dependency/container vulnerability evidence in accordance with GoreeCloud software supply-chain and Docker standards.
