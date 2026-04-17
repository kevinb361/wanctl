---
phase: 179-verification-and-operator-evidence
plan: 02
subsystem: operators
tags: [production, history, topology, evidence]
requires:
  - phase: 178-retention-tightening-and-legacy-db-cleanup
    provides: intended per-WAN reader topology and operator verification path
provides:
  - live proof of which history-reader paths work on the deployed host
  - explicit record of current HTTP reader drift versus intended merged topology
affects: [179-03, OPER-04]
tech-stack:
  added: []
  patterns: [read-only production reader verification, evidence-first operator closeout]
key-files:
  created:
    - .planning/phases/179-verification-and-operator-evidence/179-live-reader-topology-report.md
    - .planning/phases/179-verification-and-operator-evidence/179-02-SUMMARY.md
key-decisions:
  - "Treat the deployed module invocation as the authoritative CLI proof path because the bare wanctl-history wrapper is absent on host."
  - "Record the live /metrics/history envelope as working while stating clearly that its current production behavior does not match the intended merged multi-WAN topology."
  - "Use direct DB inventory and retained-window spot checks to separate active per-WAN DBs from the shared steering DB."
patterns-established:
  - "Phase closeout artifacts distinguish working operator proof paths from documented-but-missing wrappers."
  - "Live evidence takes precedence over repo intent when documenting operator procedures."
requirements-completed: [OPER-04]
duration: 20 min
completed: 2026-04-13
---

# Phase 179 Plan 02: Live Reader Topology Summary

**Read-only production evidence showing the CLI reader sees both WAN DBs while the live HTTP reader keeps its response envelope but does not currently prove merged cross-WAN history**

## Accomplishments

- Captured a live production report for CLI, HTTP, and direct DB reader behavior in `179-live-reader-topology-report.md`.
- Proved the underlying CLI reader works on the host through `sudo -n env PYTHONPATH=/opt python3 -m wanctl.history ...` and returns both `att` and `spectrum`.
- Confirmed the live HTTP endpoint is bound to the WAN IPs, not `127.0.0.1`, and still returns the documented `{data, metadata}` envelope.
- Recorded the key deployment drift: live `/metrics/history` returned only `spectrum` rows and `wan=att` returned zero rows on both endpoints.
- Reconfirmed the active DB set and retained-window shape with read-only inventory and spot checks.

## Deviations from Plan

- The documented bare `wanctl-history` command was not available on the host, so the evidence path used the deployed module form instead.
- The HTTP reader did not match the intended merged topology, so the report records that mismatch instead of claiming success.

## Operator Outcome

- Cross-WAN history can still be verified repeatably in production today.
- The authoritative proof path is currently the module-based CLI plus direct DB inventory, not the bare CLI wrapper and not the live HTTP endpoint by itself.

## Self-Check: PASSED

- Verified `.planning/phases/179-verification-and-operator-evidence/179-live-reader-topology-report.md` exists.
- Verified the report includes `wanctl.history`, `/metrics/history`, `metrics-spectrum.db`, `metrics-att.db`, and `metrics.db`.
