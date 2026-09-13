# GoreeCloud Calendar Android — GLAZE UI V1.4 Adoption

**Lifecycle:** Development / adoption in progress  
**Required Stable version:** `1.4.0`  
**Reference repository:** `GoreeCloud/goreecloud-glaze-ui`  
**Reference revision:** `84cb3db4884042f0fa25ed6d475a127fb110f596`

## Current mapping

GoreeCloud Calendar Android now routes its Development shell through a repository-local GLAZE UI V1.4 boundary. Calendar/event reading, identity, attendee/consent, scheduling decisions, and explicit mutation decisions remain solid. No camera, telemetry, environmental sensing, event-content sampling, remote optical context, or decorative color-memory source is introduced.

Radicale/CalDAV remains the sole authoritative calendar service. Android Calendar Provider remains an optional future device-integration bridge and is not promoted into a source of truth by this visual migration.

The application records V1.4 as `ADOPTION_IN_PROGRESS`, not accepted downstream conformance.

## Not yet accepted

Native Optical Engine behavior, Reduced Transparency, Increased Contrast, accessibility semantics, representative form factors, physical-device review, V1.4.1 human visual verification, and exact-revision consumer conformance evidence remain open.

## Release boundary

This source migration does not establish CalDAV transport, Identity/session acceptance, Calendar Provider permission/bridge acceptance, recurrence/timezone/attendee/alarm interoperability, offline cache, background sync, Wardveil, Privacy Shield, Everkeep, production signing/distribution, Release Candidate, or Stable status.
