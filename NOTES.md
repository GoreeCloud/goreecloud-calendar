# GoreeCloud Calendar — Notes

**Lifecycle:** Development  
**Last reconciled:** September 10, 2026

This file records implementation notes subordinate to Calendar specifications, feature roadmap, governing GoreeCloud instructions, Tasks Management, and verified runtime evidence.

## Current verified development state

- The active Calendar Development stack includes a transitional GoreeCloud Tasks busy-state integration candidate.
- The current token-file read path is hardened against symbolic-link substitution, uses no-follow/open-and-verify behavior, validates the opened file, enforces owner expectations, bounds token bytes, and requires valid UTF-8 before the credential is consumed.
- This hardening reduces risk in the current Development mechanism but does not make the token-file mechanism a production Identity design or a Stable authorization model.
- A stacked Platform Contract v0.2 adoption candidate now adds the previously missing root `goreecloud.platform.yaml` and reusable exact-revision validation workflow. The manifest deliberately records Calendar as `development`, `development-unversioned`, and globally `nonconformant`; it does not turn repository-local Glaze UI 1.3 source into application acceptance or manufacture Manager, Privacy Shield, Wardveil Security, Everkeep, Mesh, or Identity conformance.
- Existing exact-head parent CI and Tasks candidate-integration checks are Development evidence only. The new Platform Contract workflow is a separate exact-head declaration/conformance validation gate for the adoption candidate.

## Open acceptance work

A governed Calendar application version, production GoreeCloud Identity/session authority, service/backend integration, TLS and endpoint acceptance, recovery and revocation behavior, current Stable Glaze UI application acceptance, accessibility/device coverage, and the applicable Wardveil, Privacy Shield, Everkeep, Mesh, Manager, production, and release gates remain open.

## Documentation rule

Do not use this notes file to promote Calendar lifecycle, credential mechanism, Tasks integration, or Platform Contract state beyond verified evidence. Material changes must be reconciled through the applicable roadmap, conformance evidence, Drive records, and Tasks Management.
