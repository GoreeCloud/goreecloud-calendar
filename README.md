# GoreeCloud Calendar

Native GoreeCloud calendar application. Active development is performed through reviewed feature branches and pull requests.

## First-party integration

GoreeCloud Calendar and GoreeCloud Tasks are peer first-party applications and are designed to integrate in both directions.

Calendar remains authoritative for native calendar events, calendar membership, event scheduling semantics, and calendar-specific metadata. Tasks remains authoritative for task content, task workflow, assignment, project membership, completion, recurrence, and task-specific authorization.

The integration must use versioned application APIs. Neither application may read or write the other's database directly, and neither service may broaden a user's permissions through integration.

See `docs/tasks-integration-contract.md` for the initial cross-application contract and implementation boundary.
