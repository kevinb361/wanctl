---
phase: 237-hil-failure-injection-harness-closeout
plan: 02
subsystem: testing
tags: [silicom, hil, failure-injection, bash, safe-16]

requires:
  - phase: 237-hil-failure-injection-harness-closeout
    provides: Plan 01 RED pytest contract for silicom-test HARN-01..05 behavior
provides:
  - silicom-test HIL orchestrator for failover, ab-cake, and chaos scenarios
  - operator-invoked Spectrum seed scenarios for failover and A/B CAKE
  - restore-on-exit and restore-on-signal safety handlers over silicom-bypass verbs
affects: [phase-237, silicom-test, harn, safe-16]

tech-stack:
  added: []
  patterns:
    - bash orchestrator composes silicom-bypass verbs only
    - separate EXIT and INT/TERM restore handlers with poller cleanup before restore
    - strict allowlist chaos scenario sourcing

key-files:
  created:
    - scripts/silicom-test
    - scripts/silicom-test-scenarios/cake-ab-spectrum.sh
    - scripts/silicom-test-scenarios/failover-spectrum.sh
  modified:
    - .claude/context.md

key-decisions:
  - "Implemented the harness as bash composition over silicom-bypass only; no bpctl_util or src/wanctl surface was introduced."
  - "Kept Spectrum (spec-modem) as the shipped seed-scenario pair; ATT remains protected by the louder SILICOM_TEST_ATT_CONFIRM gate."
  - "Used a default documented netperf-placeholder probe behind SILICOM_TEST_PROBE rather than hardcoding iperf or a new probe tool."

patterns-established:
  - "Signal handling restores touched pairs and then terminates via the original signal path, with literal 130/143 fallback exits present."
  - "Scenario names must pass both explicit traversal rejection and ^[A-Za-z0-9][A-Za-z0-9_-]*$ before sourcing."

requirements-completed: [HARN-01, HARN-02, HARN-03, HARN-04, HARN-05]

duration: 5min
completed: 2026-06-13
---

# Phase 237 Plan 02: HIL Failure-Injection Harness Summary

**Bash silicom-test harness composing guarded Silicom bypass verbs with restore-on-exit/signal safety and Spectrum seed chaos scenarios.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-13T01:17:18Z
- **Completed:** 2026-06-13T01:23:04Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added `scripts/silicom-test` with `failover`, `ab-cake`, and `chaos` subcommands that compose `silicom-bypass` verbs only.
- Registered distinct restore handlers: EXIT preserves rc after stopping pollers/restoring pairs, while INT/TERM restores and terminates through signal-derived handling with 130/143 fallback exits.
- Added strict chaos scenario validation and two operator-invoked Spectrum seed scenarios under `scripts/silicom-test-scenarios/`.
- Wrote structured per-run `result.json` data under the configured result root, with best-effort journal extract and capture-script wrappers.

## Task Commits

Each task was committed atomically:

1. **Task 1: silicom-test orchestrator** - `fb154b31` (feat)
2. **Task 2: chaos dispatch + seed scenarios** - `9bb4fba0` (feat)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `scripts/silicom-test` - HIL orchestrator with live/ATT gating, failover, ab-cake, chaos dispatch, capture wrappers, poller lifecycle, restore handlers, and structured result output.
- `scripts/silicom-test-scenarios/cake-ab-spectrum.sh` - Sourced Spectrum A/B CAKE seed scenario.
- `scripts/silicom-test-scenarios/failover-spectrum.sh` - Sourced Spectrum failover seed scenario.
- `.claude/context.md` - Hook-required current validation note documenting the new security/safety-sensitive harness surface.

## Decisions Made

- Followed the Plan 02 constraint to compose `silicom-bypass` only; `grep -v '^#' scripts/silicom-test | grep -c 'BPCTL_UTIL\|bpctl_util'` returned `0`.
- Kept scenario seeds limited to `spec-modem`; neither scenario references `att-modem` nor `--both-wan-confirm`.
- Left the A/B probe as the planned `SILICOM_TEST_PROBE` seam with a documented netperf placeholder default, avoiding any approved-tool swap.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added commit-hook documentation note**
- **Found during:** Task 1 commit
- **Issue:** The repository pre-commit documentation hook requires documentation/context coverage for security-sensitive script changes.
- **Fix:** Updated `.claude/context.md` with a concise Phase 237 Plan 02 validation note and committed normally through hooks.
- **Files modified:** `.claude/context.md`
- **Verification:** Hook reported `Documentation updated - looking good!`.
- **Committed in:** `fb154b31`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Documentation/context note only; no controller path, config, or production service behavior changed.

## Issues Encountered

- Shellcheck caught a multi-assignment local expansion in `run_ab_probe`; it was split into separate locals before commit.
- The Plan-01 signal test asserts signal termination (`-15`) after restore; the handler restores, writes results, disables EXIT double-restore, and terminates through the signal path with literal 130/143 fallback exits retained.

## Known Stubs

- `scripts/silicom-test:7` contains the planned default `SILICOM_TEST_PROBE` netperf-placeholder command. This is intentional and operator-overridable; live A/B runs should set `SILICOM_TEST_PROBE` to the approved rig.

## User Setup Required

None - no external service configuration required.

## Verification

- `shellcheck scripts/silicom-test scripts/silicom-test-scenarios/*.sh` — PASS
- `.venv/bin/pytest tests/test_silicom_test_harness.py -q` — PASS (`8 passed`)
- `.venv/bin/pytest tests/ -k invariant -q` — PASS (`8 passed, 5472 deselected`)
- `grep -rE "OnCalendar|crontab|cron|systemctl.*timer|\bat now\b" scripts/silicom-test scripts/silicom-test-scenarios/` — PASS (no matches)
- `git diff --exit-code v1.51..HEAD -- src/wanctl configs/att.yaml` — PASS
- Forbidden surface scan: no non-comment `BPCTL_UTIL`/`bpctl_util`, no `src/wanctl`, no `import wanctl`, no `--both-wan-confirm` literal in `scripts/silicom-test` — PASS

## Threat Flags

None - the plan threat model already covered the new operator-to-live-WAN, chaos-name-to-file-path, signal-handler, and fake/live gate surfaces.

## Next Phase Readiness

Ready for Plan 03: wire deploy/documentation surfaces for the harness while preserving SAFE-16 zero controller-path drift.

## Self-Check: PASSED

- Created files exist: `scripts/silicom-test`, `scripts/silicom-test-scenarios/cake-ab-spectrum.sh`, `scripts/silicom-test-scenarios/failover-spectrum.sh`.
- Task commits exist: `fb154b31`, `9bb4fba0`.
- Verification claims above were run after task commits.

---
*Phase: 237-hil-failure-injection-harness-closeout*
*Completed: 2026-06-13*
