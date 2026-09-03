# GoreeCloud Calendar ↔ Tasks API v1 Candidate

## Status

**Development Candidate / source implementation. Not production accepted.**

This document records Calendar-side source support for the GoreeCloud Tasks Calendar API v1 implemented as the counterpart to the GoreeCloud Tasks development candidate in `GoreeCloud/goreecloud-tasks` PR #54, plus the first read-only Calendar busy-time provider boundary intended for GoreeCloud Tasks planning. It supplements, and does not replace, `docs/tasks-integration-contract.md`.

GoreeCloud Tasks remains authoritative for task content, task authorization, task workflow, assignment, completion, recurrence, project membership, and due scheduling. GoreeCloud Calendar remains authoritative for native calendar events, event authorization, calendar membership, Calendar metadata, and busy-time context.

## Calendar client capabilities in this candidate

The Calendar Tasks client can:

- consume the existing `goreecloud.tasks.calendar-projections.v1` list response;
- optionally request a bounded `start` / `end` projection window;
- read one Tasks projection by stable task ID;
- create one native Tasks item through the restricted Calendar create endpoint;
- reschedule one editable Tasks item with an optimistic source-revision guard;
- surface a typed conflict when Tasks returns HTTP 409;
- retain compatibility with legacy v1 projection-list payloads that predate the new source/deep-link/revision fields;
- strictly validate the new source application, API version, authoritative deep link, timestamps, and revision when using the new single-task and mutation responses.

The client does not directly access Tasks storage and does not cache a second authoritative task record.

## Calendar busy-time provider capability

The Calendar source candidate also defines a framework-neutral, read-only service boundary for GoreeCloud Tasks planning:

`GET /api/v1/tasks/busy-time`

The request accepts exactly two query fields:

- `starts_at` — timezone-aware ISO-8601 lower window bound;
- `ends_at` — timezone-aware ISO-8601 exclusive upper window bound.

The request does **not** accept a Calendar subject, username, calendar collection, or arbitrary authorization scope. The deployment mapping fixes the Calendar subject and authorized collection set server-side. Unknown query fields are rejected.

The response schema is:

`goreecloud.calendar.tasks-busy.v1`

A successful response contains only:

- schema and version;
- response generation time;
- requested time range;
- number of merged busy intervals; and
- merged `starts_at` / `ends_at` busy intervals.

It does not expose event UIDs, titles, descriptions, locations, attendees, calendar collection identifiers, Calendar subjects, reusable credentials, or other event content. Busy intervals from multiple authorized collections are combined before serialization so the response does not reveal which collection produced a busy period.

### Authorization model

The development provider uses one deployment-configured bearer credential for the GoreeCloud Tasks service caller. That credential maps to one configured Calendar subject and an explicit set of Calendar collection hrefs. The caller cannot supply or override those values.

The supported non-secret configuration keys are:

- `CALENDAR_TASKS_BUSY_API_ENABLED`;
- `CALENDAR_TASKS_BUSY_API_SUBJECT`;
- `CALENDAR_TASKS_BUSY_API_CALENDAR_HREFS`;
- `CALENDAR_TASKS_BUSY_API_MAX_WINDOW_MINUTES`.

The reusable credential is provided through exactly one runtime secret source:

- `CALENDAR_TASKS_BUSY_API_TOKEN`; or
- `CALENDAR_TASKS_BUSY_API_TOKEN_FILE`.

When a token file is used, the source adapter rejects non-regular files and files granting group or other permissions. The endpoint is hidden when disabled, fails closed when enabled configuration is invalid, authenticates before validating request fields, accepts GET only, emits private/no-store responses, and uses `Vary: Authorization`.

The default maximum query window is 31 days. Deployment configuration may reduce or increase the value only within the implementation's absolute 62-day ceiling. This bound prevents unbounded calendar enumeration through the peer API.

This service mapping is a transitional development mechanism. It does not satisfy the required long-term GoreeCloud Identity service-identity/delegation contract and must not be represented as production identity acceptance.

### Calendar authorization behavior

`CalendarService.busy_time_for_calendars` authorizes every configured collection before querying any of them. Only after all collection checks succeed does the service read event data, combine the event sets, and produce the existing privacy-minimized Calendar busy projection. The single-calendar browser/session busy-time operation continues to use the same service path through a one-collection call.

This preserves Calendar as the sole authority for event visibility and busy-time derivation. GoreeCloud Tasks does not gain direct CalDAV access or a path to the Calendar database/backend.

## Privacy and security behavior

The Tasks client bearer credential remains runtime input and is never placed in a URL or returned from client objects. The client sends only the fields allowed by the Tasks API:

- create: title, due time, optional priority, optional project ID;
- reschedule: due time and expected Tasks revision.

The client does not send descriptions, labels, comments, assignees, recurrence mutations, completion state, operational metadata, or unrelated account information.

The Calendar busy provider returns only merged busy intervals and similarly keeps its bearer credential out of URLs and response bodies. Service-side request data cannot select another Calendar identity or collection.

Transport and schema failures in the Tasks client fail closed as `TasksProjectionError`. HTTP rejection messages remain deliberately low-detail and do not expose raw upstream response bodies. A 409 mutation conflict becomes `TasksConflictError`; only the minimized current source revision is exposed when it can be validated.

Calendar native event workflows must continue to operate when Tasks is unavailable. A Tasks integration failure is not permission to invent stale task state or convert a projection into a Calendar-owned event. Likewise, Tasks planning must remain usable without Calendar busy context when Calendar is unavailable; the future Tasks consumer must treat busy context as additive planning information rather than authoritative task state.

## Compatibility boundary

The Tasks v1 projection schema identifier remains:

`goreecloud.tasks.calendar-projections.v1`

The existing list parser continues to accept the original v1 field set. When the extended source metadata is present it is validated. New single-projection and mutation responses require:

- source application `goreecloud-tasks`;
- source API version `1`;
- authoritative HTTP(S) task URL;
- `revision`;
- `updated_at` matching the same revision.

The Calendar busy-time peer schema is separately versioned as `goreecloud.calendar.tasks-busy.v1`, allowing Calendar's general browser-facing busy API and its least-privilege Tasks integration contract to evolve independently.

## Explicitly not implemented

- Tasks-side consumption or UI presentation of Calendar busy intervals;
- Calendar UI controls for create/reschedule;
- automatic drag-and-drop task rescheduling in calendar grids;
- task duration or time-block length;
- Tasks completion/deletion from Calendar;
- recurrence editing from Calendar;
- arbitrary task editing;
- production GoreeCloud Identity service identity/delegation;
- production network exposure or TLS/reverse-proxy binding for the busy-time peer route;
- production rate-limiter integration for the peer route;
- production Wardveil Security acceptance;
- production Privacy Shield adapter acceptance;
- production Everkeep continuity acceptance;
- production deployment or full end-to-end Tasks/Calendar runtime acceptance.

The source is therefore an integration building block, not evidence that the bidirectional workflow is production-ready.

## Validation boundary

The exact Calendar candidate revision must compile and pass the repository unit/integration-contract test workflow. Provider tests cover disabled and invalid configuration, bearer authentication, GET-only behavior, bounded timezone-aware windows, fixed subject/collection scope, multi-calendar merging, response minimization, protected token-file handling, and cache/security headers.

The existing cross-repository Tasks Candidate Integration workflow continues to validate the opposite Calendar → Tasks direction against the exact pinned Tasks API candidate. A separate Tasks-side consumer and live Calendar → Tasks planning-path validation remain required before busy context may be described as integrated into the Tasks product.

Production acceptance still requires current GoreeCloud Identity, Privacy Shield, Wardveil Security, Everkeep, Mesh, Manager, deployment, monitoring, failure-mode, accessibility, application, and representative target-environment evidence.