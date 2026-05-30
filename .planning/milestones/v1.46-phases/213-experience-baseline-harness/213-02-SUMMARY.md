---
phase: 213-experience-baseline-harness
plan: 02
subsystem: testing
tags: [baseline, harness, poller, browse, ndjson, dev-vm]

requires:
  - phase: 213-experience-baseline-harness
    provides: [Wave 0 Phase 213 fixtures and contract tests]
provides:
  - Extended 1Hz autorate /health NDJSON poller with 52-key jq projection
  - Source-bound curl-browse CSV loop for D-02 normal browsing evidence
  - HRDN-02 bounded-failure sidecar behavior for per-WAN health polling
affects: [213-experience-baseline-harness, 214-measurement-collapse-investigation, 215-spectrum-upload-reclaim-canary, 216-recovery-refractory-decision]

tech-stack:
  added: []
  patterns: [bash long-flag scripts, jq explicit projection, curl source binding, HRDN-02 bounded failures]

key-files:
  created:
    - scripts/phase213-health-poller.sh
    - scripts/phase213-browse-loop.sh
  modified: []

key-decisions:
  - "Kept Phase 213 traffic/telemetry surfaces script-only and evidence-only; no controller code, production config, services, or RouterOS surfaces were touched."
  - "Browse-loop request failures are recorded as CSV data via exit_code instead of aborting, matching the D-02 evidence contract."

patterns-established:
  - "Phase 213 health poller inherits soak-capture.sh bounded curl/HTTP/empty-body/jq failure classification while projecting the BASE-02 52-key allow-list."
  - "Phase 213 browse loop uses fixed seven-site rotation with per-request cache-busting and curl --interface source binding."

requirements-completed: [BASE-01, BASE-02]

duration: 4min
completed: 2026-05-27
---

# Phase 213 Plan 02: Health Poller + Browse Loop Summary

**Extended autorate health NDJSON poller and source-bound curl-browse CSV loop for Phase 213 baseline evidence capture.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-27T21:36:30Z
- **Completed:** 2026-05-27T21:39:44Z
- **Tasks:** 2/2
- **Files modified:** 2

## Accomplishments

- Added `scripts/phase213-health-poller.sh` (259 lines), an executable sibling of `soak-capture.sh` that polls one `/health` endpoint at 1Hz and emits the 52-key BASE-02 NDJSON projection.
- Preserved HRDN-02 bounded-failure behavior in the poller: curl exit, HTTP non-200, empty body, and jq parse failures append to `poll-failures.tsv`; lifetime failure gate defaults to `SOAK_FAIL_RATE_THRESHOLD=0.30` and `MIN_SAMPLES_BEFORE_EVAL=30`.
- Added `scripts/phase213-browse-loop.sh` (122 lines), an executable curl-browse loop with exact 7-column CSV header, fixed seven-site default rotation, `--interface <local-bind>`, cache-busting query strings, and per-request exit-code capture.

## Task Commits

Each task was committed atomically:

1. **Task 1: Build scripts/phase213-health-poller.sh with extended jq projection (BASE-02)** - `d90313f` (feat)
2. **Task 2: Build scripts/phase213-browse-loop.sh curl-browse CSV emitter (D-02)** - `3b1c017` (feat)

**Plan metadata:** this SUMMARY commit (docs)

## Files Created/Modified

- `scripts/phase213-health-poller.sh` - 1Hz `/health` NDJSON poller with 52-key jq projection, bounded-failure sidecar, clean SIGTERM/SIGINT lifecycle, and long-flag CLI: `--endpoint`, `--wan`, `--output`, `--duration`.
- `scripts/phase213-browse-loop.sh` - Source-bound curl loop with CLI: `--output`, `--duration`, `--local-bind`, `--sites`; emits `ts_utc,site,http_code,time_starttransfer,time_total,size_download,exit_code` CSV rows.

## CLI Contracts

- Health poller: `bash scripts/phase213-health-poller.sh --endpoint <url> --wan <name> --output <ndjson-path> [--duration <sec-or-0>]`
- Browse loop: `bash scripts/phase213-browse-loop.sh --output <csv-path> [--duration <sec>] [--local-bind <ip>] [--sites <csv>]`

## Verification Results

- `bash -n scripts/phase213-health-poller.sh` → passed.
- `bash -n scripts/phase213-browse-loop.sh` → passed.
- `.venv/bin/pytest tests/test_phase213_mutation_boundary.py -q` → 4 passed, 4 skipped.
- `.venv/bin/pytest tests/test_phase213_ndjson_schema.py -q` → 1 passed.
- `bash scripts/phase213-browse-loop.sh --output /tmp/phase213-browse-smoke.csv --duration 4 --local-bind 127.0.0.1 --sites "https://example.com/"` plus CSV assertion → header matched exactly and at least one 7-column data row was written.
- `git diff --stat -- src/wanctl/` → empty (SAFE-05 invariant held).

## Decisions Made

- Kept both scripts strictly outside the controller path and production configuration surfaces, matching AGENTS.md and Phase 213 D-10 constraints.
- Used the Plan 01 `ndjson-row-expected-keys.json` fixture as the projection contract; the poller emits 52 keys exactly.
- Treated browse-loop curl failures as evidence rows instead of errors; the CSV `exit_code` column preserves failure data for downstream classification.

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope changes; implementation stayed within the planned script-only evidence surfaces.

## Issues Encountered

None.

## Known Stubs

None. Empty string grep hits are CLI parser defaults and per-iteration variables, not user-facing stubs or unwired data sources.

## Threat Flags

None. The new HTTP polling and outbound curl traffic are the exact trust-boundary surfaces already listed in the plan threat model.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 213-03. The Wave 3 orchestrator can invoke the health poller and browse loop directly via the CLI contracts above, and the Plan 01 mutation-boundary and NDJSON schema tests now turn GREEN for these two scripts.

## Self-Check: PASSED

- Created files exist: `scripts/phase213-health-poller.sh`, `scripts/phase213-browse-loop.sh`.
- Task commits exist in git history: `d90313f`, `3b1c017`.
- Projection key count verified as 52 from `tests/fixtures/phase213/ndjson-row-expected-keys.json`.

---
*Phase: 213-experience-baseline-harness*
*Completed: 2026-05-27*
