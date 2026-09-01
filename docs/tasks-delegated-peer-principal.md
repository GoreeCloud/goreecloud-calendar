# Tasks delegated peer Calendar principal

Status: Development

GoreeCloud Calendar now has a least-privilege mapping boundary for future Tasks busy-time requests that arrive with already-validated GoreeCloud Identity claims.

`goreecloud_calendar.peer_authorization` requires the dedicated `goreecloud-calendar-busy` audience, the narrow `calendar.busy.read` scope, an unexpired timezone-aware claim set, and an explicit bounded list of authorized Calendar collection hrefs. Successful claims are reduced to the existing `CalendarPrincipal` with `can_write=False`.

Calendar therefore continues to enforce its own collection scope through `CalendarPrincipal.require_calendar(...)`; a valid peer claim does not authorize arbitrary calendars and cannot be used for Calendar mutations.

## Credential and transport boundary

This module does not parse, verify, mint, store, log, or transmit bearer tokens, cookies, sessions, static service credentials, Radicale credentials, or cross-user secrets. Raw credential validation remains the responsibility of an approved GoreeCloud Identity/transport boundary before claims reach this code.

The module performs no network I/O and does not query Calendar data. Producing a principal does not mean a busy-time request was made or accepted.

## Acceptance boundary

Live delegated Identity transport, production rate/security integration for peer calls, Privacy Shield/Wardveil acceptance, Tasks user-facing planning composition, deployment, and Stable qualification remain separate gates.
