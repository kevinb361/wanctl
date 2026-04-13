---
phase: 179-verification-and-operator-evidence
plan: 03
subsystem: operators
tags: [closeout, evidence, docs]
requires:
  - phase: 179-verification-and-operator-evidence
    provides: live footprint and reader-topology evidence
provides:
  - final OPER-04 closeout artifact
  - docs aligned to the executed production proof path
affects: [OPER-04]
tech-stack:
  added: []
  patterns: [evidence-backed closeout, exact operator guidance]
key-files:
  created:
    - .planning/phases/179-verification-and-operator-evidence/179-operator-evidence-closeout.md
    - .planning/phases/179-verification-and-operator-evidence/179-03-SUMMARY.md
  modified:
    - docs/DEPLOYMENT.md
    - docs/RUNBOOK.md
key-decisions:
  - "Close OPER-04 based on the repeatable proof path, not on a successful size reduction claim."
  - "Document the actual deployed CLI and HTTP invocation paths instead of preserving stale 127.0.0.1 and bare-wrapper guidance."
  - "State the live HTTP reader drift explicitly instead of folding it into vague success language."
patterns-established:
  - "Operator docs must prefer the command that works on production today over the command that was expected to exist."
requirements-completed: [OPER-04]
duration: 10 min
completed: 2026-04-13
---

# Phase 179 Plan 03: Operator Evidence Closeout Summary

**Closed OPER-04 with an evidence-backed operator proof path while documenting that production footprint stayed flat and the live HTTP reader still drifts from the intended merged topology**

## Accomplishments

- Wrote the final operator closeout artifact in `179-operator-evidence-closeout.md`.
- Updated deployment and runbook guidance to match the commands that actually worked on the live host.
- Kept the final wording precise:
  - storage is healthy
  - the per-WAN footprint did not materially shrink
  - the CLI reader is the authoritative cross-WAN proof path today
  - `/metrics/history` still needs follow-up if it is expected to prove merged cross-WAN history

## Self-Check: PASSED

- Verified the closeout artifact includes `OPER-04`, `baseline`, `wanctl.history`, `/metrics/history`, and `storage.status`.
- Verified the operator docs no longer direct Phase 179 checks to `127.0.0.1:9101` or the missing bare `wanctl-history` wrapper.
