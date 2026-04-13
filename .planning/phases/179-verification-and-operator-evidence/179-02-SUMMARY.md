---
phase: 179-verification-and-operator-evidence
plan: 02
subsystem: testing
tags: [production, history, sqlite, operators, topology]
requires:
  - phase: 178-retention-tightening-and-legacy-db-cleanup
    provides: operator verification commands and the intended per-WAN history-reader topology
provides:
  - live reader-topology evidence for the supported CLI and HTTP history readers
  - direct SQLite separation evidence for per-WAN autorate DBs versus the shared steering DB
  - operator-facing retention-shape proof for short raw retention plus longer aggregate coverage
affects: [OPER-04, milestone-audit, operator-evidence]
tech-stack:
  added: []
  patterns: [read-only production verification, live reader-versus-db topology comparison]
key-files:
  created:
    - .planning/phases/179-verification-and-operator-evidence/179-live-reader-topology-report.md
  modified: []
key-decisions:
  - "Use sudo -u wanctl with PYTHONPATH=/opt for live CLI evidence because the deployed host does not expose a wanctl-history wrapper on the SSH user's PATH."
  - "Use the service-bound 10.10.110.223:9101 and 10.10.110.227:9101 listeners instead of localhost because 127.0.0.1:9101 is not the live autorate history bind on production."
  - "Document the live /metrics/history ATT mismatch as evidence rather than infer parity from repo code."
patterns-established:
  - "Production-evidence plans can adapt command form as long as the replacement stays read-only and proves the same surface."
  - "Reader-topology claims must separate CLI behavior, HTTP behavior, and direct DB evidence when the live outputs diverge."
requirements-completed: [OPER-04]
duration: 13min
completed: 2026-04-13
---

# Phase 179 Plan 02: Live Reader Topology Summary

**Production proof that `wanctl-history` follows the per-WAN autorate DB set, while live `/metrics/history` keeps its response envelope but does not currently show equivalent ATT evidence**

## Performance

- **Duration:** 13 min
- **Started:** 2026-04-13T23:28:00Z
- **Completed:** 2026-04-13T23:40:54Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `.planning/phases/179-verification-and-operator-evidence/179-live-reader-topology-report.md` with live CLI, HTTP, and SQLite production evidence.
- Proved under the deployed `wanctl` user that `discover_wan_dbs()` resolves `metrics-att.db` and `metrics-spectrum.db`, and that `wanctl.history` returns both WANs over the same 1-hour window.
- Recorded direct SQLite spot checks showing the per-WAN autorate DBs retain a short raw window plus longer `5m` aggregate coverage while the shared `metrics.db` remains separate steering evidence.

## Task Commits

Each task was committed atomically:

1. **Task 1: Capture live CLI and HTTP history-reader behavior** - `2fa4ae5` (`docs`)
2. **Task 2: Spot-check retained-window shape and steering separation directly** - `2b30dbf` (`docs`)

## Files Created/Modified

- `.planning/phases/179-verification-and-operator-evidence/179-live-reader-topology-report.md` - live production evidence for reader behavior, DB topology, and retention shape
- `.planning/phases/179-verification-and-operator-evidence/179-02-SUMMARY.md` - execution summary for plan 179-02

## Decisions Made

- Used the deployed module path and `wanctl` service account for CLI evidence because the SSH user could not read `/var/lib/wanctl/*.db` directly and no `wanctl-history` wrapper was on the remote `PATH`.
- Treated `10.10.110.223:9101` and `10.10.110.227:9101` as the authoritative live HTTP surfaces after verifying that `127.0.0.1:9101` refused connections and `127.0.0.1:9102` belonged to the separate steering health server.
- Preserved the actual production finding that `/metrics/history` did not return ATT rows during capture instead of claiming parity with the CLI based only on repo code.

## Deviations from Plan

None in scope, but the live environment required equivalent read-only command forms instead of the plan's example invocations:

- `wanctl-history` had to be executed as `sudo -u wanctl env PYTHONPATH=/opt python3 -m wanctl.history ...`
- `/metrics/history` had to be queried on `10.10.110.223:9101` and `10.10.110.227:9101` instead of `127.0.0.1:9101`

These adjustments did not change scope or mutate production state.

## Issues Encountered

- Live `/metrics/history` preserved its `{data, metadata}` envelope but did not return ATT rows during the capture window. Both tested listeners returned Spectrum rows for `wanctl_rtt_ms`, and `wan=att` returned zero rows even though `metrics-att.db` contained current ATT RTT samples.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The operator evidence artifact now captures the live topology and retention story with direct citations.
- Plan `179-03` can use this report to synthesize OPER-04 closeout, but it should carry forward the HTTP reader mismatch as a production finding rather than assume full reader parity.

## Self-Check: PASSED

- Found `.planning/phases/179-verification-and-operator-evidence/179-live-reader-topology-report.md`
- Found task commits `2fa4ae5` and `2b30dbf`
- Summary reflects the actual live evidence gathered during execution
