# GoreeCloud Calendar Security

GoreeCloud Calendar is a privacy-first self-hosted application. Security reports should use GitHub's private security-advisory workflow for this repository rather than a public issue when disclosure could expose an unpatched vulnerability, authentication weakness, credential-handling flaw, or data-protection issue.

## Security model

- Radicale remains authoritative for DAV authentication, collection authorization, and calendar data.
- Production uses individually attributable DAV identities through the Calendar session layer.
- DAV credentials remain only in bounded application memory for the active session and are not written to application storage, browser storage, logs, or source control.
- Mutations require a valid session, session-bound CSRF token, collection containment, and CalDAV conditional-write preconditions.
- `CALDAV_WRITE_ENABLED=false` is the default and must remain disabled until the documented target acceptance gates pass.
- Wardveil Security by GoreeCloud is the security and protection identity; it does not replace the technical controls documented above.

## Sensitive information

Do not submit production credentials, session cookies, CSRF values, calendar contents, private DAV hrefs, personal event information, private network details, backup secrets, or other reusable sensitive values in issues, pull requests, logs, screenshots, or test fixtures.

## Release security gates

A release candidate must pass the repository test, dependency-audit, container scan, Compose validation, non-root runtime, and SBOM gates. A source-valid candidate is not production-approved until the target-environment, backup/restore, manual Glaze UI/accessibility, and explicit cutover gates in `docs/PRODUCTION_READINESS.md` are complete.
