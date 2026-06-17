---
phase: 243-cycle-budget-benchmark-gate
plan: 04
subsystem: benchmarking
tags: [bench-01, bench-02, safe-17, systemd, production-evidence, input-error]

requires:
  - phase: 243-cycle-budget-benchmark-gate
    provides: Plans 01-03 frozen thresholds, preregistration provenance, rollup/hygiene sampler, and gate evaluator
provides:
  - Isolation-gated production benchmark harness for all 8 icmplib/fping idle/load WAN arms
  - Operator runbook and production evidence bundle for the live benchmark run
  - Recorded BENCH verdict with outcome input_error, preserving preregistration provenance
affects: [phase-243, phase-245-ab, bench-01, bench-02, safe-17]

tech-stack:
  added: []
  patterns:
    - Fail-closed live-shaper isolation preflight before transient benchmark units
    - Production-mirroring transient systemd units with invocation-scoped journal evidence
    - Committed benchmark verdict as a gate input, not as a pass claim

key-files:
  created:
    - configs/bench/README.md
    - configs/bench/gen-bench-configs.sh
    - scripts/phase243-bench-preflight.sh
    - scripts/phase243-bench-run.sh
    - tests/test_phase243_bench_configs.py
    - docs/PHASE243-BENCHMARK-RUNBOOK.md
    - .planning/phases/243-cycle-budget-benchmark-gate/evidence/243-BENCHMARK-VERDICT.json
    - .planning/phases/243-cycle-budget-benchmark-gate/evidence/production-run/
  modified:
    - scripts/phase243-gate-eval.py
    - scripts/phase243-hygiene-sampler.sh

key-decisions:
  - "Recorded the production benchmark verdict as input_error, not pass; Phase 245 remains blocked until the benchmark input validity gaps are resolved or explicitly replanned."
  - "Kept production-run evidence local and committed under phase evidence while preserving preregistration provenance from the frozen thresholds commit."
  - "Treated live-run harness fixes as Plan 04 deviations because they were required to complete the operator-gated evidence run safely without touching controller source."

patterns-established:
  - "Benchmark harness must prove qdisc/router writer isolation before any transient autorate unit starts."
  - "The final gate evaluator can run locally over copied production evidence when production temp staging is intentionally not a git repository."
  - "An input_error verdict is a completed benchmark artifact but not a satisfied no-regression gate."

requirements-completed: [BENCH-01, BENCH-02, SAFE-17]

duration: checkpointed; live continuation completed 2026-06-17
completed: 2026-06-17
---

# Phase 243 Plan 04: Bench Launcher and Production Verdict Summary

**Isolation-gated 8-arm production benchmark harness with committed evidence and an input_error BENCH verdict that blocks treating Phase 243 as passed.**

## Performance

- **Duration:** checkpointed; operator-gated production continuation completed 2026-06-17
- **Started:** 2026-06-17T19:43:55Z finalization window
- **Completed:** 2026-06-17
- **Tasks:** 4 completed, with Task 4 completed by operator-gated live run/resume
- **Files modified:** 10 key harness/test/docs/evidence surfaces plus production evidence directory

## Accomplishments

- Added the committed bench config generator and README for the 8-arm matrix, with throwaway interfaces, unique ports/paths, isolated state/locks/storage, and backend-specific configuration.
- Added a fail-closed preflight that proves bench interfaces/writers are isolated from live cake-autorate qdisc ownership before a transient benchmark arm starts.
- Added the preflight-gated systemd launcher with production-relevant capabilities, CPUAccounting, RuntimeMaxSec/trap bounded stop, invocation-scoped journal drain, hygiene capture, and residue checks.
- Added the operator runbook for the production benchmark procedure.
- Preserved production evidence under `.planning/phases/243-cycle-budget-benchmark-gate/evidence/production-run/` and recorded `.planning/phases/243-cycle-budget-benchmark-gate/evidence/243-BENCHMARK-VERDICT.json`.
- The live benchmark completed all 8 arms; Dallas netperf was initially wedged, `netperf.service` on Dallas was restarted, then the full run completed.
- The final gate evaluator ran locally over copied production evidence to preserve git preregistration provenance because the production temp staging directory was intentionally not a git repo.

## Verdict

- **Outcome:** `input_error` — this is not a pass.
- **Provenance:** prereg commit `96520db0c80cb01bbf6f738c95fc70c8341d7716`; thresholds blob `c39915330d4e77652ed48b981652a075b7835a71` from `scripts/phase243-thresholds.json`.
- **Primary validity failures:** every comparison failed the n-floor gate with minimum cycle counts far below the frozen 36,000 floor; `spectrum/load` failed the hard icmplib representativeness gate.
- **Regression/hygiene signals:** fping showed large avg/p99 regressions and p99 absolute ceiling failures across all comparisons; several comparisons also failed stall, task-bound, and zombie gates.
- **Production teardown:** production shaper services were restarted and verified active after the run.

## Task Commits

Each implementation/fix task was committed atomically before final metadata:

1. **Task 1: Committed bench config generator + isolation/schema tests** — `12844ae5` (`feat`)
2. **Task 2: Fail-closed bench preflight** — `7d9b759c` (`feat`)
3. **Task 3: Preflight-gated launcher and runbook** — `0f8df0da` (`feat`)
4. **Task 4 continuation/live-run fixes and evidence enablement:**
   - `e117423a` (`fix`) — satisfy bench config test lint
   - `01077f3d` (`fix`) — bind ATT bench arms to dev source IP
   - `76ed90c2` (`fix`) — derive bench preflight live route device
   - `bb943aa6` (`fix`) — keep bench interface names within Linux limits
   - `e26e8acf` (`fix`) — avoid pipe-heredoc loss in qdisc snapshots
   - `4dbf2b91` (`fix`) — bind bench configs to production source IPs
   - `aa99ddfa` (`fix`) — mirror production benchmark entrypoint
   - `e88167c3` (`fix`) — allow temp-staged benchmark code
   - `75eeb52d` (`fix`) — snapshot live config qdisc interfaces
   - `bde491f4` (`fix`) — read production live configs in preflight
   - `ef3cc5cc` (`fix`) — set system PATH for benchmark scripts
   - `5b4ab73f` (`fix`) — pass absolute bench config to transient unit
   - `f0a0563f` (`fix`) — satisfy bench router schema
   - `ea70b18a` (`fix`) — clean bench state after each arm
   - `ffd8e747` (`fix`) — clean wanctl-owned bench state
   - `7548ff05` (`fix`) — allow CPU capture after load window
   - `96520db0` (`fix`) — stop transient bench units with sudo

## Files Created/Modified

- `configs/bench/gen-bench-configs.sh` — Generates isolated bench configs for spectrum/att × icmplib/fping, reused by idle/load launch arms.
- `configs/bench/README.md` — Documents arm matrix, isolation contract, throwaway netdev setup, and bench-only usage warnings.
- `tests/test_phase243_bench_configs.py` — Proves bench config isolation, evidence-key schema contract, launcher capability grant, and live-run safety expectations.
- `scripts/phase243-bench-preflight.sh` — Read-only fail-closed isolation proof and qdisc stable-ownership snapshot producer.
- `scripts/phase243-bench-run.sh` — Systemd transient-unit launcher with preflight gate, capabilities, bounded stop, invocation-scoped evidence, CPU capture, hygiene sampler, and residue cleanup.
- `docs/PHASE243-BENCHMARK-RUNBOOK.md` — Operator procedure for isolation setup, 8-arm production launch, gate evaluation, teardown, and valid close semantics.
- `scripts/phase243-gate-eval.py` — Updated during Plan 04 to expose the CPU evidence key contract consumed by launcher/schema tests.
- `scripts/phase243-hygiene-sampler.sh` — Given explicit PATH setup for production script execution.
- `.planning/phases/243-cycle-budget-benchmark-gate/evidence/production-run/` — Copied production benchmark evidence for all 8 arms.
- `.planning/phases/243-cycle-budget-benchmark-gate/evidence/243-BENCHMARK-VERDICT.json` — Recorded gate verdict with `outcome: input_error`.
- `.planning/phases/243-cycle-budget-benchmark-gate/evidence/safe17-boundary-243.json` — Fresh SAFE-17 boundary evidence from finalization.

## Decisions Made

- The BENCH verdict is recorded as `input_error` and must not be interpreted as a no-regression pass.
- The final evaluator was run locally over copied production evidence to preserve preregistration provenance in git; the production staging directory stayed intentionally non-git.
- The Dallas netperf service restart is recorded as an operator-run prerequisite recovery, not a benchmark harness code path.
- Production shaper recovery/active verification is recorded as live-run teardown evidence, not rerun by finalization.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Verification] Fixed lint in bench config tests**
- **Found during:** Task 1 verification
- **Issue:** The new bench config tests tripped repository lint.
- **Fix:** Removed the lint violation while preserving the isolation assertions.
- **Files modified:** `tests/test_phase243_bench_configs.py`
- **Verification:** `.venv/bin/ruff check tests/test_phase243_bench_configs.py scripts/phase243-gate-eval.py` passed during finalization.
- **Committed in:** `e117423a`

**2. [Rule 2 - Production correctness] Corrected WAN source-IP and route/interface assumptions**
- **Found during:** Task 4 live-run preparation/execution
- **Issue:** Initial bench configs/preflight assumptions did not match production source-IP and route-device realities closely enough for valid source-bound runs.
- **Fix:** Bound ATT and production bench configs to the correct source IPs, derived live route devices, read production live configs in preflight, and snapshotted production qdisc interfaces.
- **Files modified:** `configs/bench/README.md`, `configs/bench/gen-bench-configs.sh`, `scripts/phase243-bench-preflight.sh`, `scripts/phase243-bench-run.sh`, `tests/test_phase243_bench_configs.py`
- **Verification:** Live 8-arm run completed and final local tests passed.
- **Committed in:** `01077f3d`, `76ed90c2`, `4dbf2b91`, `75eeb52d`, `bde491f4`

**3. [Rule 3 - Blocking] Made production shell execution robust**
- **Found during:** Task 4 live-run execution
- **Issue:** Production execution needed shorter Linux interface names, reliable qdisc snapshot emission, explicit PATH, absolute config paths, and the production benchmark entrypoint.
- **Fix:** Kept bench interface names under kernel limits, avoided pipe/heredoc snapshot loss, set system PATH for scripts, passed absolute bench config paths, mirrored the production benchmark entrypoint, and allowed temp-staged benchmark code.
- **Files modified:** `configs/bench/README.md`, `configs/bench/gen-bench-configs.sh`, `scripts/phase243-bench-preflight.sh`, `scripts/phase243-bench-run.sh`, `scripts/phase243-hygiene-sampler.sh`, `tests/test_phase243_bench_configs.py`, `docs/PHASE243-BENCHMARK-RUNBOOK.md`
- **Verification:** All 8 production arms completed and final shell syntax/test checks passed.
- **Committed in:** `bb943aa6`, `e26e8acf`, `aa99ddfa`, `e88167c3`, `ef3cc5cc`, `5b4ab73f`

**4. [Rule 3 - Blocking] Hardened per-arm teardown and evidence capture**
- **Found during:** Task 4 live-run execution
- **Issue:** The launcher needed production-safe cleanup of bench state, sudo-backed unit stop, and CPU capture after load windows.
- **Fix:** Cleaned bench state after each arm, cleaned wanctl-owned state, allowed CPU capture after the load window, and stopped transient units with sudo.
- **Files modified:** `scripts/phase243-bench-run.sh`, `tests/test_phase243_bench_configs.py`
- **Verification:** Production shaper services were restarted and verified active after the completed run; final local checks passed.
- **Committed in:** `f0a0563f`, `ea70b18a`, `ffd8e747`, `7548ff05`, `96520db0`

---

**Total deviations:** 4 grouped auto-fixed issue classes across 17 fix commits.
**Impact on plan:** The fixes were required to safely execute the planned production benchmark and preserve evidence validity. They did not introduce `src/wanctl/` controller-path drift.

## Issues Encountered

- Dallas netperf was wedged before the full run; the operator restarted `netperf.service` on Dallas, then all 8 benchmark arms completed.
- The production temp staging directory was intentionally not a git repo, so final gate evaluation ran locally over copied evidence to preserve preregistration provenance.
- The verdict outcome is `input_error`: min-cycle floors were far below the frozen floor across arms, `spectrum/load` icmplib representativeness failed, and multiple regression/hygiene gates failed.

## Verification

- `bash -n configs/bench/gen-bench-configs.sh scripts/phase243-bench-preflight.sh scripts/phase243-bench-run.sh` — passed.
- `.venv/bin/pytest tests/test_phase243_bench_configs.py -q` — `5 passed`.
- `.venv/bin/ruff check tests/test_phase243_bench_configs.py scripts/phase243-gate-eval.py` — passed.
- `bash scripts/phase243-safe17-boundary-check.sh --out .planning/phases/243-cycle-budget-benchmark-gate/evidence/safe17-boundary-243.json` — passed.
- `git diff --name-only HEAD -- src/wanctl/` — no output; no controller-source drift from Plan 04 finalization.
- Live benchmark work was not rerun during finalization.

## Known Stubs

None.

## Threat Flags

None — new trust surfaces are the declared Plan 04 surfaces: throwaway bench unit isolation, live qdisc/router writer isolation, transient unit capabilities, invocation-scoped evidence, and operator-run verdict validity.

## User Setup Required

None for finalization. The live operator benchmark has already been executed and verdict recorded.

## Next Phase Readiness

Phase 243 Plan 04 is complete as an execution artifact, but the benchmark gate did **not** pass. Phase 245 live A/B should remain blocked unless the team explicitly resolves or replans the input validity failures (`input_error`) and re-establishes BENCH-02 no-regression evidence.

## Self-Check: PASSED

- Found summary, verdict, production evidence index, and fresh SAFE-17 evidence on disk.
- Found Plan 04 implementation/fix commits: `12844ae5`, `7d9b759c`, `0f8df0da`, `e117423a`, `01077f3d`, `76ed90c2`, `bb943aa6`, `e26e8acf`, `4dbf2b91`, `aa99ddfa`, `e88167c3`, `75eeb52d`, `bde491f4`, `ef3cc5cc`, `5b4ab73f`, `f0a0563f`, `ea70b18a`, `ffd8e747`, `7548ff05`, `96520db0`.
- Finalization verification passed; live benchmark work was not rerun.

---
*Phase: 243-cycle-budget-benchmark-gate*
*Completed: 2026-06-17*
