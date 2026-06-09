---
phase: 226-baseline-capture-threshold-lock-snapshot-a
plan: "01"
subsystem: validation
tags: [baseline, spectrum, cake, flent, rrul, qdisc, health, evidence]

requires:
  - phase: 226-baseline-capture-threshold-lock-snapshot-a
    provides: [Snapshot A rollback anchor captured before baseline load]
provides:
  - Read-only 3-run Spectrum baseline capture wrapper
  - Parser-tested per-tin DELTA summary helper with continuous-health window rates
  - Retained redacted baseline evidence set for 920/18 besteffort wash
affects: [phase-227-candidate-capture, phase-228-verdict, GATE-01, AB-02, SAFE-13]

tech-stack:
  added: []
  patterns: [read-only live capture, per-run tc counter deltas, continuous health NDJSON, retained baseline manifest]

key-files:
  created:
    - scripts/phase226-baseline-capture.sh
    - scripts/phase226-baseline-summary.py
    - tests/phase226/test_tc_qdisc_parser.py
    - tests/phase226/fixtures/tc-qdisc.before.txt
    - tests/phase226/fixtures/tc-qdisc.during.txt
    - tests/phase226/fixtures/tc-qdisc.after.txt
    - tests/phase226/fixtures/health.window.ndjson
    - .planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/baseline/baseline-20260604T113435Z/MANIFEST.md
    - .planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/baseline/baseline-20260604T113435Z/baseline-summary.json
    - .planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/baseline/baseline-20260604T113435Z/BASELINE-SUMMARY.md
  modified:
    - .claude/context.md

key-decisions:
  - "Task 4 used the operator-approved forced-window reason exactly: operator approved forced run now at checkpoint."
  - "The retained baseline run used ref_host=vultr-chicago after objective invalid dallas run-sets were discarded for netperf errors and recorded in the retained MANIFEST."

patterns-established:
  - "Flent's timestamped RRUL raw output is normalized into stable per-run flent-rrul.NN.flent.gz artifacts for downstream scripts."
  - "Baseline validity records discarded-run names but only the retained redacted valid baseline evidence is committed."

requirements-completed: [AB-02, SAFE-13]

duration: 19min
completed: 2026-06-04
---

# Phase 226 Plan 01: Baseline evidence capture Summary

**Read-only forced-window Spectrum baseline capture with 3-run RRUL/reference-flow evidence, per-tin DELTA summaries, and continuous health-window GATE inputs.**

## Performance

- **Duration:** 19 min resumed execution (checkpoint continuation)
- **Started:** 2026-06-04T11:21:36Z
- **Completed:** 2026-06-04T11:40:21Z
- **Tasks:** 4 total; Task 4 completed in this continuation
- **Files modified:** 55 in the Task 4 commit; 4 primary implementation/test/context files across the plan plus baseline evidence tree

## Accomplishments

- Added `scripts/phase226-baseline-capture.sh`, a read-only wrapper for 3x60s Spectrum baseline capture with before/during/after `tc -s qdisc`, continuous `/health` NDJSON, RRUL flent output, unmarked UDP/TCP reference summaries, DSCP-neutrality proof, validity gating, and manifest/hashing.
- Added `scripts/phase226-baseline-summary.py`, which computes per-run CAKE tin DELTAS (`during - before`) and emits `tin_queue_delay_spread_ms`, `baseline_window`, and RRUL p99 headline fields.
- Added pytest fixture coverage proving the parser does not treat cumulative `tc` counters as per-run values and derives restart/transition/floor/SOFT_RED figures from windowed health samples.
- Captured and committed the retained baseline evidence set at `.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/baseline/baseline-20260604T113435Z/`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Write read-only 3-run baseline capture wrapper** - `e061e52` (feat)
2. **Task 2: Compute mean + per-tin queue-delay summary helper** - `d305160` (feat)
3. **Task 3: Parser fixture tests** - `3b003e7` (test)
4. **Task 4: Run the baseline capture and commit redacted evidence** - `0523133` (feat)

**Plan metadata:** pending final metadata commit

## Files Created/Modified

- `scripts/phase226-baseline-capture.sh` - Read-only live baseline wrapper with forced-window recording, stable flent artifact normalization, health poller cleanup, validity gate, and manifest generation.
- `scripts/phase226-baseline-summary.py` - Parser and summarizer for per-tin `tc` deltas, health-window rates, RRUL p99, JSON output, and Markdown table output.
- `tests/phase226/test_tc_qdisc_parser.py` - Regression tests for cumulative-counter delta semantics and continuous health-window rate derivation.
- `tests/phase226/fixtures/*` - Representative `tc -s qdisc` and health NDJSON fixtures.
- `.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/baseline/baseline-20260604T113435Z/` - Retained redacted baseline evidence set.
- `.claude/context.md` - Updated local technical context for the new capture/summary tooling and retained live evidence.

## Decisions Made

- Forced the off-peak gate only with the explicit operator-approved reason: `operator approved forced run now at checkpoint`.
- Switched the retained run's `ref_host` from `dallas` to `vultr-chicago` only after objective invalid dallas run-sets hit netperf errors/resets; the retained manifest records the discarded run-set names.
- Committed only the retained public-safe baseline evidence tree; discarded invalid run directories were not committed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Normalized Flent timestamped raw output to expected artifact names**
- **Found during:** Task 4 (Run the baseline capture and commit redacted evidence)
- **Issue:** Flent writes raw RRUL data as timestamped `rrul-*.flent.gz` files under `-D`, while the wrapper initially asserted stable `flent-rrul.NN.flent.gz` names directly.
- **Fix:** Added `normalize_flent_artifacts` to copy the newest timestamped RRUL raw file to the stable per-run name and capture console output for validity review.
- **Files modified:** `scripts/phase226-baseline-capture.sh`
- **Verification:** `bash -n`, `shellcheck`, dry-run, and final retained capture all passed.
- **Committed in:** `0523133` (Task 4 commit)

**2. [Rule 1 - Bug] Fixed manifest artifact listing after live capture**
- **Found during:** Task 4 (Run the baseline capture and commit redacted evidence)
- **Issue:** The manifest's `find -printf` invocation used an invalid argument order and failed after the live runs completed.
- **Fix:** Corrected the `find -printf` invocation and removed transient `.health-stop` markers before artifact assertion/commit.
- **Files modified:** `scripts/phase226-baseline-capture.sh`, retained baseline `MANIFEST.md`, retained baseline `artifact-sha256.txt`
- **Verification:** Final retained manifest exists, lists required artifacts, and records `validity: valid` / `retained: true`.
- **Committed in:** `0523133` (Task 4 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug).
**Impact on plan:** Both fixes were capture-artifact correctness fixes. No production deployment, restart, CAKE-mode change, `/etc/wanctl` write, `tc`/`nft` mutation, controller-path source change, or ATT change occurred.

## Issues Encountered

- Two dallas run-sets were objectively invalid because netperf returned connection errors/resets during RRUL. Per the anti-cherry-pick rule, these were treated as invalid-run failures and rerun provenance was recorded in the retained manifest. The final retained run-set used `vultr-chicago`, passed validity, and was committed.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None. Empty-string defaults in the capture wrapper are CLI argument sentinels and do not flow to UI rendering or committed evidence as placeholders.

## Next Phase Readiness

Plan 226-03 can consume `baseline-20260604T113435Z/baseline-summary.json` for the D-06 tin queue-delay spread / noise-band input and `baseline_window` values. Phase 227 can rerun the same capture shape against the candidate `diffserv4 wash` state.

## Self-Check: PASSED

- FOUND: `scripts/phase226-baseline-capture.sh`
- FOUND: `scripts/phase226-baseline-summary.py`
- FOUND: `tests/phase226/test_tc_qdisc_parser.py`
- FOUND: retained baseline `MANIFEST.md`, `baseline-summary.json`, and `BASELINE-SUMMARY.md`
- FOUND commit: `e061e52`
- FOUND commit: `d305160`
- FOUND commit: `3b003e7`
- FOUND commit: `0523133`

---
*Phase: 226-baseline-capture-threshold-lock-snapshot-a*
*Completed: 2026-06-04*
