# GoreeCloud Tasks Integration Contract

## Purpose

GoreeCloud Calendar and GoreeCloud Tasks are separate first-party applications with complementary responsibilities. They must integrate in both directions while preserving independent authorization, data ownership, failure isolation, backup, recovery, and release lifecycles.

## Authority boundaries

### GoreeCloud Tasks is authoritative for

- task title and description;
- task creator and assignee;
- project membership and task authorization;
- task priority and workflow status;
- task completion and reopening;
- task due date/time;
- task recurrence;
- subtasks, labels, comments, and task activity;
- GoreeCloud operational task metadata.

### GoreeCloud Calendar is authoritative for

- native calendar events;
- calendar ownership and membership;
- calendar-specific event metadata;
- calendar visibility and event authorization;
- event scheduling semantics that are not task properties;
- calendar display and busy-time context.

A scheduled task shown in Calendar is a projection of a Tasks record, not an independently authoritative Calendar event.

## Required user experience

Calendar should display authorized Tasks items alongside native calendar events when those tasks have schedulable date/time information. Task projections must be visually distinguishable from native calendar events and should deep-link to the authoritative task.

Tasks planning surfaces should be able to display authorized Calendar event/busy context so a user can plan work around meetings and other commitments. Calendar event details shown in Tasks must respect Calendar authorization and should remain read-only unless a separately authorized Calendar mutation workflow is introduced.

Users should be able to create a new task from Calendar context. Calendar should call Tasks through a versioned task-creation API and should not create a duplicate calendar-owned shadow record as the task authority.

Users with Tasks edit permission should be able to drag or otherwise reschedule a task projection in Calendar. Calendar should submit the requested schedule change to Tasks, and Tasks should perform normal authorization and validation before accepting it.

## Projection identity

Every Calendar representation of a task must carry stable origin information sufficient to distinguish it from a native calendar event. At minimum the projection should identify:

- source application: `goreecloud-tasks`;
- stable Tasks task identifier;
- source API version;
- authoritative deep link when available;
- current scheduling revision or timestamp when required for conflict detection.

Calendar must not silently convert a projection into a detached native event.

## Mutation semantics

### Reschedule

Calendar may request a due-date/time change only for a task the mapped user or application identity is authorized to edit. Tasks performs the mutation and returns the authoritative result.

### Complete

Calendar may eventually offer task completion as a convenience action, but completion must be executed by the Tasks API so recurrence, activity, reminders, and authorization remain correct. The first integration increment may keep completion read-only if that reduces risk.

### Delete

Deleting or hiding a task projection from a Calendar view must not delete the authoritative task. Task deletion remains a Tasks operation.

If a task is deleted in Tasks, Calendar should stop rendering its projection after the next synchronization/read. If a task is completed, Calendar should follow the display behavior defined by the user's Calendar/Tasks integration preferences rather than inventing an independent completion state.

### Recurrence

Tasks remains authoritative for recurring task generation and recurrence rules. Calendar may display recurring task occurrences supplied by Tasks but must not independently expand or mutate the recurrence series in a way that conflicts with Tasks.

## Initial versioned API responsibilities

### Tasks API consumed by Calendar

The first implementation should support versioned endpoints or equivalent service methods for:

- listing task projections visible to one mapped user within a requested time window;
- reading one visible task projection;
- creating a task from Calendar context;
- rescheduling an editable task;
- returning stable task deep links and projection metadata.

Responses should be data-minimized for calendar presentation. Calendar does not need access to private comments, full activity history, unrelated project metadata, reminder credentials, or administrative information merely to render a task projection.

### Calendar API consumed by Tasks

The first implementation should support versioned endpoints or equivalent service methods for:

- listing authorized event/busy context for one mapped user within a requested time window;
- returning enough display metadata for Today, Upcoming, agenda, and planning views;
- returning stable Calendar deep links for date/event context where appropriate.

Tasks should not receive unrelated private calendars, attendees, notes, or event fields unless they are required for the approved planning experience and authorized for the user.

## Identity and authorization

Cross-application calls must use dedicated service credentials or another approved first-party identity mechanism. Service identities must be least-privilege and mapped to explicit user authorization context rather than operating as an unrestricted administrator.

Both applications must independently validate authorization for each protected object. A valid service credential is not sufficient by itself to access arbitrary user data.

Application-administrator status must not be treated as automatic permission to read another user's private task or calendar content through normal integration APIs.

## Failure isolation

GoreeCloud Calendar must continue to work for native events when Tasks is unavailable. Task projections may show a temporary unavailable/stale state, but Calendar must not fail as a whole.

GoreeCloud Tasks must continue to work when Calendar is unavailable. Today, Upcoming, task editing, recurrence, reminders, and task completion must not depend on Calendar availability. Calendar context should degrade gracefully.

## Synchronization model

Prefer API-backed read-through projection for the first version rather than duplicating authoritative task records into Calendar storage. If caching is later required for responsiveness, cached data must be explicitly non-authoritative, time-bounded, revocable, and recoverable from the source service.

Conflict handling for rescheduling should use source revisions or timestamps where appropriate so Calendar does not overwrite a newer Tasks edit without detection.

## Privacy and logging

Integration logs should record operational metadata needed for troubleshooting without logging task descriptions, private calendar notes, bearer credentials, session identifiers, tokens, or unnecessary personal content.

No third-party telemetry or commercial cloud is required for this integration.

## Recovery and portability

Each application remains independently backed up and restorable. Restoring Calendar without Tasks must not create authoritative task copies, and restoring Tasks without Calendar must not lose task scheduling data merely because projections are unavailable.

Cross-application identifiers and integration settings should be documented and portable where practical, while credentials remain outside user data exports unless an approved secure recovery process explicitly covers them.

## Initial delivery sequence

1. Define and test the shared projection schema and authorization model.
2. Add read-only task projections to Calendar.
3. Add authorized Calendar busy/event context to Tasks planning views.
4. Add Calendar-to-Tasks task creation.
5. Add Calendar-to-Tasks task rescheduling with conflict checks.
6. Add deep links and polished first-party navigation in both directions.
7. Evaluate task completion from Calendar after recurrence and activity semantics are fully covered by cross-application tests.
8. Add broader DAV/standards interoperability without weakening the richer first-party contract.

## Non-negotiable constraints

- No shared database between Tasks and Calendar.
- No direct cross-application ORM/database coupling.
- No privilege expansion through service credentials.
- No duplicate authoritative task event created solely for display.
- No commercial SaaS dependency for the core integration.
- No silent deletion of Tasks data from Calendar actions.
- No independent Calendar recurrence engine for Tasks-owned recurrence.
- Every mutation must execute through the authoritative application's validated API boundary.
