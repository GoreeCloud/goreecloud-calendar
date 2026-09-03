# GoreeCloud Calendar ↔ Tasks API v1 Client Candidate

## Status

**Development Candidate / source implementation. Not production accepted.**

This document records Calendar-side source support for the GoreeCloud Tasks Calendar API v1 implemented as the counterpart to the GoreeCloud Tasks development candidate in `GoreeCloud/goreecloud-tasks` PR #54. It supplements, and does not replace, `docs/tasks-integration-contract.md`.

GoreeCloud Tasks remains authoritative for task content, task authorization, task workflow, assignment, completion, recurrence, project membership, and due scheduling. GoreeCloud Calendar remains authoritative for native calendar events, event authorization, calendar membership, Calendar metadata, and busy-time context.

## Client capabilities in this candidate

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

## Privacy and security behavior

The bearer credential remains runtime input and is never placed in the URL or returned from client objects. The client sends only the fields allowed by the Tasks API:

- create: title, due time, optional priority, optional project ID;
- reschedule: due time and expected Tasks revision.

The client does not send descriptions, labels, comments, assignees, recurrence mutations, completion state, operational metadata, or unrelated account information.

Transport and schema failures fail closed as `TasksProjectionError`. HTTP rejection messages remain deliberately low-detail and do not expose raw upstream response bodies. A 409 mutation conflict becomes `TasksConflictError`; only the minimized current source revision is exposed when it can be validated.

Calendar native event workflows must continue to operate when Tasks is unavailable. A Tasks integration failure is not permission to invent stale task state or convert a projection into a Calendar-owned event.

## Compatibility boundary

The v1 projection schema identifier remains:

`goreecloud.tasks.calendar-projections.v1`

The existing list parser continues to accept the original v1 field set. When the extended source metadata is present it is validated. New single-projection and mutation responses require:

- source application `goreecloud-tasks`;
- source API version `1`;
- authoritative HTTP(S) task URL;
- `revision`;
- `updated_at` matching the same revision.

This allows a controlled transition without making an older read-only Tasks v1 list endpoint unreadable.

## Explicitly not implemented

- Calendar UI controls for create/reschedule;
- automatic drag-and-drop task rescheduling in calendar grids;
- task duration or time-block length;
- Tasks completion/deletion from Calendar;
- recurrence editing from Calendar;
- arbitrary task editing;
- production GoreeCloud Identity service identity/delegation;
- production Wardveil Security acceptance;
- production Privacy Shield adapter acceptance;
- production Everkeep continuity acceptance;
- production deployment or end-to-end Tasks/Calendar runtime acceptance.

The client source is therefore an integration building block, not evidence that the bidirectional workflow is production-ready.

## Validation boundary

The exact Calendar candidate revision must compile and pass the repository unit/integration-contract test workflow. That validation covers request construction, bounded windows, strict parsing, supported mutation bodies, low-detail HTTP failures, and optimistic conflict handling. Production acceptance still requires an environment-specific end-to-end test against an accepted Tasks candidate plus current identity, privacy, security, continuity, deployment, failure-mode, accessibility, and application acceptance evidence.