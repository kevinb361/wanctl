---
phase: 217-production-cycle-budget-baseline
plan: 02
subsystem: profiling
tags: [profiling, performance, production-capture, systemd, json]
requires:
  - phase: 217-production-cycle-budget-baseline
    provides: Plan 01 JSON profiling parser, gitignored capture directory, and production profiling runbook
provides:
  - Operator-gated Spectrum production capture window with >=1h JSON Cycle timing records
  - Committed `.planning/perf/217-capture-window.json` with capture timestamps, pilot status, revert proof, and validation counts
  - Gitignored raw capture artifacts under `.planning/perf/capture/` for Plan 03 analysis
affects: [phase-217, performance-profiling, production-evidence]
tech-stack:
  added: []
  patterns:
    - Operator-gated transient systemd drop-in for production profiling
    - Raw production DEBUG/Journald capture remains gitignored; only structured metadata is committed
key-files:
  created:
    - .planning/perf/217-capture-window.json
  modified: []
key-decisions:
  - "217-02 accepted the operator-gated pilot and full capture after revert proof showed no --profile/--debug/WANCTL_LOG_FORMAT residue."
  - "The final passing capture used live journalctl streaming because post-hoc debug-log/journal retention preserved only the tail of the first one-hour run."
patterns-established:
  - "Full-window cycle-budget validation is based on JSON `Cycle timing` records with numeric `cycle_total_ms`, not regex text DEBUG output."
  - "Router-write coverage is recorded in metadata so Plan 03 can distinguish driven-path evidence from organic steady-state."
requirements-completed: [PERF-01]
duration: 3h 40m
completed: 2026-05-30
---

# Phase 217 Plan 02: Production Cycle-Budget Capture Summary

**Operator-gated Spectrum profiling window captured 71,560 JSON Cycle timing records with router-write coverage and verified production revert.**

## Performance

- **Duration:** 3h 40m wall-clock including operator gates
- **Started:** 2026-05-29T21:07:44Z
- **Completed:** 2026-05-30T00:47:33Z
- **Tasks:** 3 completed
- **Files modified:** 1 committed metadata file; raw capture files remain gitignored

## Accomplishments

- Completed the 5-minute pilot gate: `cycle_total_ms` was present as a top-level JSON key, pilot recorded 5,959 `Cycle timing` records, no unit restarts, no overrun warnings, and the pilot drop-in was reverted.
- Completed the full Spectrum production capture window from `2026-05-29T23:43:16Z` to `2026-05-30T00:44:16Z` with `71,560` `Cycle timing` records.
- Landed the driven segment inside the window (`2026-05-30T00:13:16Z` → `2026-05-30T00:16:37Z`, `tcp_upload` + `rrul`, host `dallas`, exit code `0`).
- Verified router-write path coverage: `401` cycle records had non-zero `router_write_download_ms` or `router_write_upload_ms`.
- Collected adjacent observer-effect health windows before and during DEBUG capture.
- Verified mandatory revert: no drop-in/profile/debug/log-format residue, `wanctl@spectrum` active, `/health` healthy on version `1.45.0`.

## Task Commits

Each task was handled atomically where applicable:

1. **Task 1: Pre-capture safety check + run 5-min pilot** — operator checkpoint, no commit; raw pilot artifact is gitignored.
2. **Task 2: Full >=1h capture with driven segment, observer-effect windows, revert + verify** — `a5c3386` (chore; metadata captured with Task 3 validation)
3. **Task 3: Validate retrieved NDJSON spans the window with router-write coverage** — `a5c3386` (chore; validation block added to the capture metadata)

**Plan metadata:** recorded in the final docs commit for this summary/state update.

## Files Created/Modified

- `.planning/perf/217-capture-window.json` — committed structured capture metadata with pilot result, full-window timestamps, driven-segment timestamps, observer-effect window status, revert proof, and validation counts.
- `.planning/perf/capture/pilot-spectrum_debug.ndjson` — gitignored pilot raw capture, 5,959 `Cycle timing` records.
- `.planning/perf/capture/spectrum_debug.ndjson` — gitignored full-window JSON capture, 71,560 `Cycle timing` records after removing six non-JSON journal preamble lines from the live stream.
- `.planning/perf/capture/spectrum_journal.ndjson` — gitignored journal capture companion.
- `.planning/perf/capture/spectrum-health-on-window.ndjson` and `.planning/perf/capture/spectrum-health-off-window.ndjson` — gitignored observer-effect windows.

## Decisions Made

- Proceeded past Task 1 only after operator supplied explicit pilot PASS evidence: `cycle_total_ms` present, no restarts, no overruns, and drop-in reverted.
- Accepted the final full capture because it satisfied the sample floor (`71,560 >= 60,000`), had numeric-only `cycle_total_ms`, had router-write coverage present, and production revert was verified.
- Recorded the retention workaround as part of the durable metadata: final passing capture method was `live-journalctl-stream` because post-hoc retrieval preserved only the tail of the first one-hour attempt.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Switched effective capture source to live journal streaming**
- **Found during:** Task 2 (full capture retrieval)
- **Issue:** Post-hoc retrieval from debug-log/journal retention only preserved the tail of the first one-hour run, which would have failed the `>=60000` sample floor.
- **Fix:** Operator reran the passing long capture using live `journalctl -f -o cat` streaming into `.planning/perf/capture/spectrum_debug.ndjson`, preserving the full window for analysis.
- **Files modified:** `.planning/perf/capture/spectrum_debug.ndjson` (gitignored), `.planning/perf/217-capture-window.json`
- **Verification:** Parser counted `71,560` cycle-total samples; Task 3 jq validation passed after non-JSON preamble cleanup.
- **Committed in:** `a5c3386`

**2. [Rule 3 - Blocking] Removed non-JSON journal preamble lines from analysis NDJSON**
- **Found during:** Task 3 (canonical jq validation)
- **Issue:** The live journal stream included six non-JSON systemd/status lines before JSON log records, causing the plan's jq validation commands to stop with a parse error.
- **Fix:** Preserved a temporary backup under `/tmp/opencode/phase217-spectrum_debug-with-journal-preamble.ndjson`, then filtered `.planning/perf/capture/spectrum_debug.ndjson` to JSON lines only so it is valid NDJSON for Plan 03.
- **Files modified:** `.planning/perf/capture/spectrum_debug.ndjson` (gitignored)
- **Verification:** `jq -c 'select(.message=="Cycle timing") | .cycle_total_ms'` returned `71,560`; `cycle_total_ms` types were `"number"` only.
- **Committed in:** N/A for raw capture; metadata result committed in `a5c3386`

---

**Total deviations:** 2 auto-handled blocking issues.  
**Impact on plan:** The capture remains valid and more robust for Plan 03; no production control-path, threshold, service unit, or source-code changes were made.

## Issues Encountered

- The passing full capture recorded 2 isolated `Cycle overrun:` warnings. The plan allowed isolated rate-limited warnings; there was no sustained cluster and no unit restart.
- Task 2 and Task 3 share commit `a5c3386` because the operator-created metadata file was first committed after Task 3 added the required validation block.

## User Setup Required

None. Production operator actions are complete and the transient drop-in was reverted.

## Verification

- Pilot: `5,959` `Cycle timing` records; `cycle_total_ms` present; zero restarts; zero pilot overruns; pilot revert verified.
- Full capture: window spans 61 minutes; `71,560` `Cycle timing` records; first cycle `2026-05-29T23:43:19.365Z`; last cycle `2026-05-30T00:44:16.900Z`.
- Driven segment: `tcp_upload` and `rrul` ran inside the window with exit code `0`.
- Task 3 validation: `router_write_records=401`, `router_write_coverage=present`, `cycle_total_types=["number"]`.
- Revert: `systemctl cat` profile/debug/log-format grep count `0`; running Spectrum process had no profile/debug/log-format matches; service active; health status healthy; version `1.45.0`.
- Raw artifacts remain gitignored under `.planning/perf/capture/`; only `.planning/perf/217-capture-window.json` was committed.

## Known Stubs

None.

## Threat Flags

None.

## Next Phase Readiness

Ready for Plan 217-03. The raw full-window capture is analysis-ready in `.planning/perf/capture/spectrum_debug.ndjson`, and `.planning/perf/217-capture-window.json` provides explicit `--from` / `--to` bounds plus router-write coverage for downstream storage attribution and D-03 verdict computation.

## Self-Check: PASSED

- `.planning/perf/217-capture-window.json` exists, parses as JSON, includes `revert_verified: true`, and includes a populated `validation` block.
- Task commit `a5c3386` exists in git history.
- Required raw captures exist in the gitignored capture directory and are not staged or committed.
- Plan acceptance checks for sample count, numeric `cycle_total_ms`, router-write coverage, and revert proof passed.

---
*Phase: 217-production-cycle-budget-baseline*
*Completed: 2026-05-30*
