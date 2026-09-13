# GoreeCloud Calendar Android Client

This directory is the dedicated native Android application line for GoreeCloud Calendar.

## Architecture authority

The shared GoreeCloud Radicale/CalDAV service remains the authoritative calendar store. The Android application must not create a second authoritative event database. Any future local persistence is a bounded offline/cache representation with explicit synchronization, ETag/precondition handling, and deterministic conflict behavior.

Android's Calendar Provider is an optional device-integration bridge, not the GoreeCloud source of truth. Provider access must be separately permissioned, purpose-bound, user-controlled, and independently accepted before enablement.

## Current Development foundation

- Kotlin/Jetpack Compose application module targeting SDK 36 with minimum SDK 29 and Java 17.
- Launchable native Calendar Development surface.
- Repository-local GLAZE UI V1.4 / `1.4.0` adoption boundary pinned to the current Stable source authority while downstream conformance remains `ADOPTION_IN_PROGRESS`.
- Explicit runtime capability state for Identity, CalDAV read/write, offline cache, background synchronization, and the Android Calendar Provider bridge.
- A pure Kotlin read-contract model for the existing session-authorized `/api/v1/events` and `/api/v1/busy-time` endpoints.
- Fail-closed request construction: calendar hrefs must be bounded, canonical server-relative identifiers; view modes are restricted to the server contract; busy-time windows use timezone-aware values with positive duration.
- Native Identity/session exchange and network transport remain blocked. The manifest still requests neither `INTERNET` nor Calendar Provider permissions.
- Android backup disabled.
- Unit coverage proving unavailable runtime capability is not advertised as accepted and the source-ready read contract cannot broaden origin/identity authority.
- Gradle caching, parallel execution, and incremental Kotlin compilation.

A source-ready endpoint contract is not a live CalDAV connection. The Android client does not copy browser cookies, embed reusable service credentials, invent bearer tokens, or contact Radicale directly.

## Next milestones

1. Define and accept first-party GoreeCloud Identity/session exchange for native Calendar without reusable application-wide credentials.
2. Add a bounded same-origin transport adapter and exercise read-only event listing/busy-time retrieval against non-production Development data.
3. Add calendar discovery if/when a native-safe scoped discovery contract is exposed by the Calendar service; do not bypass the service with direct Radicale discovery.
4. Add ETag/precondition-safe event create/edit/delete and visible conflict resolution.
5. Complete recurrence, exceptions, VTIMEZONE/TZID, all-day events, attendees/scheduling, alarms, and extension-preserving interoperability.
6. Add protected bounded offline cache and deterministic reconciliation.
7. Add WorkManager/background synchronization with power/network constraints.
8. Add the optional Android Calendar Provider bridge with explicit permissions and user controls.
9. Complete repository-local GLAZE UI V1.4 application acceptance, accessibility, form-factor, and representative-device gates; human/manual V1.4.1 checks remain separate.
10. Complete independent Privacy Shield, Wardveil Security, Everkeep, Manager, Mesh, Identity, signing/provenance, recovery, Release Candidate, production, and Stable gates.

A successful source build or CI run is Development evidence only and does not grant production or platform-system acceptance.
