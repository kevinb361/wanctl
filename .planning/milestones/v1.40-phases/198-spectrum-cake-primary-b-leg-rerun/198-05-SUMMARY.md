---
phase: 198-spectrum-cake-primary-b-leg-rerun
plan: 05
subsystem: validation-tooling
tags: [spectrum, cake-primary, rerun, flent, loaded-window-audit, safe-05]

requires:
  - phase: 198-spectrum-cake-primary-b-leg-rerun
    plan: 04
    provides: Blocked closeout with identified loaded-window, throughput, and A/B gaps
provides:
  - Off-peak gated attempt-isolated Spectrum rerun harness
  - Per-run loaded-window health-primary queue coverage audit script
  - Locked VALN-05a throughput verdict script over three flent medians
affects: [phase-198, valn-04, valn-05a, safe-05]

tech-stack:
  added: []
  patterns: [attempt-isolated-evidence, health-ndjson-primary-audit, canonical-sqlite-psv, locked-throughput-verdict]

key-files:
  created:
    - scripts/phase198-rerun-flent-3run.sh
    - scripts/phase198-loaded-window-audit.py
    - scripts/phase198-throughput-verdict.py
  modified: []

key-decisions:
  - "Use /health 1Hz NDJSON as the primary per-run loaded-window evidence source because persisted SQLite raw rows are too sparse for a 500-row 30s gate."
  - "Treat throughput/audit FAIL verdicts as completed attempt facts rather than harness crashes so Plan 198-06/07 can make operator decisions from contracted summaries."

review-concerns-addressed:
  - HIGH-1 canonical SQLite schema
  - HIGH-2 health 1Hz primary evidence
  - HIGH-3 dwell-bypass per-run capture
  - MEDIUM-5 --test-hour gated by --dry-run
  - MEDIUM-6 joint IP+org egress assertion
  - MEDIUM-7 trap-on-failure summary contract
  - MEDIUM-9 hard-abort threshold enforced
  - LOW-11 simplified pass|fail audit verdict

requirements-addressed: [VALN-04, VALN-05a, SAFE-05]
requirements-completed: []

duration: ~16m
completed: 2026-04-29T12:12:00Z
---

# Phase 198 Plan 05: Off-Peak Rerun Harness and Audit Tooling Summary

**Off-peak Spectrum rerun tooling now captures attempt-isolated flent, /health, SQLite, per-run audit, throughput verdict, and partial-failure summary evidence without touching controller source.**

## Performance

- **Started:** 2026-04-29T11:56:28Z
- **Completed:** 2026-04-29T12:12:00Z
- **Tasks:** 2/2 complete
- **Files created:** 3 scripts
- **Regression slice:** 572 tests passed

## Accomplishments

- Added `scripts/phase198-rerun-flent-3run.sh`, an executable harness that refuses production runs outside the standard 02..04 local off-peak window unless extended or forced, accepts `--test-hour` only with `--dry-run`, hard-locks `--local-bind` to `10.10.110.226`, and enforces SAFE-05 against Phase 197 ship SHA `068b804`.
- The harness auto-detects the next `rerun-attempt-N` directory, enforces the N>=4 hard-abort threshold from `198-06-ATTEMPT-LOG.md`, asserts both exact Spectrum egress IP `70.123.224.169` and org `Charter|AS11427` before each flent run, samples `/health` at 1Hz in parallel, captures canonical SQLite PSV rows with `wan_name` and `metric_name`, and writes `attempt-summary.json` on failures via an ERR trap.
- Added `scripts/phase198-loaded-window-audit.py`, which reads per-run `/health` NDJSON as primary evidence, reads SQLite PSV as cross-correlation evidence, reports dwell-bypass samples in the same loaded window, and emits a simple `pass` or `fail` verdict.
- Added `scripts/phase198-throughput-verdict.py`, which reads the attempt flent manifest and applies the locked VALN-05a rule: `PASS` iff `medians_above_532 >= 2 AND median_of_medians_mbps >= 532`.

## Task Commits

1. **Task 1: Write off-peak gated rerun harness** — `975104b`
2. **Task 2: Write loaded-window audit and throughput verdict scripts** — `e8a0a8c`

## Verification

- `bash -n scripts/phase198-rerun-flent-3run.sh` — PASS
- `shellcheck scripts/phase198-rerun-flent-3run.sh` if available — PASS/no findings
- Harness token and behavior checks, including `--dry-run --test-hour 12` exits 2, `--dry-run --test-hour 03` exits 0, and `--test-hour 03` without `--dry-run` exits 7 — PASS
- `.venv/bin/python3 -m py_compile scripts/phase198-loaded-window-audit.py scripts/phase198-throughput-verdict.py` — PASS
- Script content checks for `queue_primary_health_pct`, `health_dwell_bypass_samples`, `medians_above_532`, canonical metric names, and absence of `pass_with_documented_exceptions` — PASS
- `git diff --quiet 068b804..HEAD -- src/wanctl/queue_controller.py src/wanctl/cake_signal.py src/wanctl/fusion_healer.py src/wanctl/wan_controller.py src/wanctl/health_check.py` — PASS
- `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` — PASS (`572 passed in 39.96s`)

## Decisions Made

- Used `/health` 1Hz NDJSON as primary evidence and SQLite PSV as secondary/cross-correlation evidence, matching Codex HIGH-2 feasibility math.
- Included actual Phase 197 `/health` key resolution (`signal_arbitration.active_primary_signal` and `signal_arbitration.refractory_active`) in the audit script while retaining the planned fallback paths.
- Allowed audit and throughput scripts to exit non-zero on `fail` when run directly, but the harness treats written FAIL artifacts as factual attempt outcomes and still writes a final summary for Plan 198-06/07 consumption.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Preserved failed verdicts as completed attempt facts**
- **Found during:** Task 1 harness implementation
- **Issue:** With `set -e`, a throughput or audit `FAIL` exit would have triggered the partial-failure trap and prevented a complete `attempt-summary.json`, even though a FAIL verdict is a valid evidence outcome rather than a harness crash.
- **Fix:** The harness now accepts non-zero audit/verdict exits when their JSON artifact was written, then records `throughput_verdict`, `per_run_audit_verdicts`, and `all_per_run_audits_pass` in the final attempt summary.
- **Files modified:** `scripts/phase198-rerun-flent-3run.sh`
- **Commit:** `975104b`

**2. [Rule 2 - Critical functionality] Added actual Phase 197 health field fallback**
- **Found during:** Task 2 audit implementation
- **Issue:** The plan listed generic `state.*` and `arbitration.*` paths, but current `/health` exposes the relevant fields under `signal_arbitration`.
- **Fix:** The audit script resolves `signal_arbitration.active_primary_signal == "queue"` and `signal_arbitration.refractory_active` first, then falls back to the planned paths.
- **Files modified:** `scripts/phase198-loaded-window-audit.py`
- **Commit:** `e8a0a8c`

**3. [Rule 3 - Blocking] Used documented non-interactive doc-check bypass for script commits**
- **Found during:** Task commits
- **Issue:** The repository pre-commit documentation hook opened an interactive prompt for security/network-related script changes.
- **Fix:** Used the repository-documented `SKIP_DOC_CHECK=1` environment variable while keeping normal git hooks enabled and never using `--no-verify`.
- **Files modified:** none
- **Commit:** `975104b`, `e8a0a8c`

## Issues Encountered

- Existing untracked `graphify-out/` remained unrelated and was left untouched.
- `.planning/STATE.md` and `.planning/ROADMAP.md` already contained gap-closure planning updates at execution start; they are carried into the final metadata update rather than treated as task code changes.

## Known Stubs

None. Grep matched intentional empty shell defaults and Python `newline=""` usage; none are UI/data-source stubs.

## Threat Flags

None. The new network, SSH, health, and SAFE-05 surfaces are the planned trust boundaries in `198-05-PLAN.md`.

## Next Phase Readiness

Ready for `198-06`: an operator can schedule the harness during the 02:00-05:00 local off-peak window. The harness will produce attempt-isolated evidence for Plan 198-06/07 to evaluate.

---
*Phase: 198-spectrum-cake-primary-b-leg-rerun*
*Completed: 2026-04-29T12:12:00Z*

## Self-Check: PASSED

- Found `scripts/phase198-rerun-flent-3run.sh`, `scripts/phase198-loaded-window-audit.py`, and `scripts/phase198-throughput-verdict.py` on disk.
- Found task commits `975104b` and `e8a0a8c` in git history.
- Verified no `src/wanctl/` protected files differ from Phase 197 ship SHA `068b804`.
