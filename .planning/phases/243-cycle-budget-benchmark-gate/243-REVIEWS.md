---
phase: 243
reviewers: [codex]
reviewed_at: 2026-06-16T22:35:23Z
plans_reviewed: [243-01-PLAN.md, 243-02-PLAN.md, 243-03-PLAN.md, 243-04-PLAN.md]
---

# Cross-AI Plan Review — Phase 243 (Cycle-Budget Benchmark Gate)

> Reviewer: Codex (codex-cli 0.135.0, default model). Claude self-skipped (review ran inside Claude Code; `--codex` requested).

## Codex Review

**Summary**
The plans are strong on measurement discipline, SAFE-17 containment, and fail-closed gate thinking. Plans 01-03 are mostly execution-ready with a few tightening changes. Plan 04 is not safe enough yet: launching the real `autorate_continuous` loop can still write live CAKE/router limits, and the plan does not provide committed bench configs proving isolation from active cake-autorate/steering state. I would not run the live 8-arm benchmark until that is fixed.

**Plan 01 — Prereg + SAFE-17**
**Strengths**
- Good BENCH-02 posture: frozen thresholds JSON plus human prereg before data.
- Correct SAFE-17 direction for this phase: empty `src/wanctl` diff against Phase 242.
- Good reuse of path confinement and dirty-tree fail-closed checks.

**Concerns**
- **MEDIUM:** “Committed before data” is stated but not mechanically proven. Presence tests cannot prove threshold/evidence ordering.
- **MEDIUM:** The mirror test anchor workflow is fuzzy before the real Phase 243 close SHA exists. A temporary HEAD-like anchor can become a rot hazard if not repinned as a blocking close step.
- **LOW:** `TASKS_BOUND` needs exact semantics: absolute max, baseline+delta, or windowed max. Plan 03 assumes baseline+bound.

**Suggestions**
- Record threshold file blob SHA and prereg commit SHA in the final verdict.
- Add a closeout check that evidence/verdict commits are descendants of the prereg commit and that the threshold blob did not change.
- Make repinning `PHASE_CLOSE_ANCHOR` to the actual Phase 243 close commit an explicit blocking finalization task.

**Risk Assessment: MEDIUM**
Good structure, but prereg integrity needs git-level proof, not just file presence.

**Plan 02 — Rollup + Hygiene Sampler**
**Strengths**
- Correctly reuses existing `Cycle timing` JSON instrumentation from [perf_profiler.py](/home/kevin/projects/wanctl/src/wanctl/perf_profiler.py:286) and parser guard behavior from [profiling_collector_json.py](/home/kevin/projects/wanctl/scripts/profiling_collector_json.py:120).
- Adds the right missing signal: inter-cycle gap detection for STALL.
- CPUUsageNSec and fd/zombie/Tasks sampling are the right evidence shape.

**Concerns**
- **HIGH:** Journal rollup must isolate a single invocation. `journalctl -u <unit>` after repeated arm names can include old logs unless bounded by cursor, timestamp, boot ID, or `_SYSTEMD_INVOCATION_ID`.
- **MEDIUM:** `CPUUsageNSec` can be unavailable or nonnumeric unless CPU accounting is enabled. The sampler and launcher should fail closed on that.
- **MEDIUM:** Malformed journal JSON is silently ignored if the wrapper just reuses parser behavior. For benchmark evidence, a malformed-line count should be surfaced.
- **LOW:** Zombie scan by direct `PPID == MainPID` may miss cgroup descendants. Probably okay for fping, but document the limitation or scan the unit cgroup.

**Suggestions**
- Capture the unit invocation ID and pass it to journal collection.
- Emit parse counters: lines seen, JSON decode failures, cycle records, timestamped records.
- Add `CPUAccounting=yes` to the transient unit properties and assert numeric `CPUUsageNSec`.

**Risk Assessment: MEDIUM**
The measurement tools are conceptually right, but log scoping must be fixed or the p99/stall evidence can be contaminated.

**Plan 03 — Gate Evaluator**
**Strengths**
- Correct primary comparison: same-run fping vs same-run icmplib, not historical baseline.
- Good fail-closed matrix: missing cycle stats, missing CPU evidence, n-floor, zombie, fd, Tasks, stall.
- Good separation of frozen thresholds from evaluator logic.

**Concerns**
- **HIGH:** The historical representativeness anchor is only advisory in the plan, but D-02 says a wildly off icmplib arm makes the run suspect. That should abort/block, not merely warn.
- **MEDIUM:** CPU% normalization is not settled. Dividing by `n_cores` makes the threshold “percent of whole machine,” which can mask single-core contention. If the intended metric is top/systemd-style CPU, do not divide by core count.
- **MEDIUM:** `20Hz` is an implicit threshold for the 30-minute cycle floor. Put `CYCLE_HZ` or `CYCLE_INTERVAL_MS` in the frozen JSON.
- **MEDIUM:** Sequential same-run arms can still be confounded by WAN/load drift. The runbook should pair/randomize order and require rerun near threshold boundaries.

**Suggestions**
- Make representativeness a validity gate with a pre-registered tolerance band and `outcome: input_error` / `abort`, not `pass`.
- Pre-register CPU normalization explicitly.
- Define a concrete input schema for all 8 arms so Plan 04 can call the evaluator without inventing glue.

**Risk Assessment: MEDIUM**
Gate logic is mostly right, but the representativeness and CPU definitions need tightening before it can be a hard A/B blocker.

**Plan 04 — Launcher + Runbook**
**Strengths**
- Correctly insists on a real systemd unit with journal-pipe stdout and no TTY.
- Good intent around unique unit names, CPUUsageNSec capture, residue checks, and no iperf substitution.
- Operator-gated live run is appropriate.

**Concerns**
- **HIGH:** This can mutate live shaping. `WANController.apply_rate_changes_if_needed()` calls `router.set_limits(...)` on rate changes [wan_controller.py](/home/kevin/projects/wanctl/src/wanctl/wan_controller.py:1607), [wan_controller.py](/home/kevin/projects/wanctl/src/wanctl/wan_controller.py:1676). The Linux CAKE adapter also initializes qdiscs with `tc qdisc replace` on construction [linux_cake_adapter.py](/home/kevin/projects/wanctl/src/wanctl/backends/linux_cake_adapter.py:10). The plan only checks ports/locks/state, not live qdisc/router writer collision with cake-autorate.
- **HIGH:** No committed bench YAML/templates are planned. BENCH-01 needs reproducible configs proving backend selection, source IP, unique health/metrics ports, lock/state/log/storage paths, and writer isolation.
- **MEDIUM:** `systemd-run` properties are under-specified. Running as root without `User=wanctl`, `WorkingDirectory`, `PYTHONPATH`, capabilities, CPU affinity, and CPUAccounting differs materially from the production service.
- **MEDIUM:** The exact flent source-binding syntax and ATT target are still unresolved.
- **LOW:** `ruff check` on a shell script is not meaningful; use `bash -n` and shellcheck if available.

**Suggestions**
- Add committed bench config templates or a generator, plus tests that assert all paths/ports differ from live configs.
- Add a hard preflight proving the bench unit cannot write the active CAKE qdiscs/RouterOS queues, or explicitly require an operator-approved isolated host/qdisc/maintenance window. Current “throwaway unit” is not enough.
- Make the transient unit mirror production-relevant properties: `--uid=wanctl`, working dir, env file/env vars, capabilities, CPU affinity, `CPUAccounting=yes`, `StandardOutput=journal`.
- Use unique per-run unit names and journal invocation IDs.

**Risk Assessment: HIGH**
This is the blocking plan. Without qdisc/router-write isolation, the benchmark can become a second live shaper and collide with cake-autorate.

**Overall Risk**
**HIGH until Plan 04 is revised.** SAFE-17 is well covered for source drift, and the statistical gate is close, but live-state collision is not solved. The phase should not proceed to the operator 8-arm run until the launcher/config story proves it cannot mutate active cake-autorate/steering state unintentionally.

---

## Consensus Summary

Single external reviewer (Codex); "consensus" here is Codex's verdict plus orchestrator
verification of the load-bearing claims against live code.

### Agreed Strengths
- Strong measurement discipline: frozen-thresholds-before-data (BENCH-02), same-run
  fping-vs-icmplib primary basis (D-02), fail-closed gate matrix.
- SAFE-17 containment is correct for a measurement-only phase: empty `src/wanctl` diff
  vs the Phase 242 close anchor, with path-confinement + dirty-tree fail-closed checks.
- Good reuse of existing instrumentation (`perf_profiler.py` cycle timing,
  `profiling_collector_json.py` parser guard) rather than reinventing stats.

### Agreed Concerns (HIGH — priority for replan)
1. **[Plan 04 — HIGH, verified] Live-shaping collision risk.** Launching the real
   `autorate_continuous.py` loop runs `WANController.apply_rate_changes_if_needed()`
   → `router.set_limits()` (`wan_controller.py:1607/1676`), and the Linux CAKE adapter
   does `tc qdisc replace` at construction (`linux_cake_adapter.py:12/288`). The plan's
   preflight only checks port/lock/state — NOT qdisc/router-writer isolation from the
   live cake-autorate shapers on .226/.233. **Verified against live code by the
   orchestrator.** This is the blocking concern: the bench unit could become a second
   live shaper.
2. **[Plan 04 — HIGH] No committed bench configs.** BENCH-01 reproducibility needs
   committed bench YAML/templates proving backend selection, source-IP binding, unique
   health/metrics ports, and lock/state/log/storage path isolation + writer isolation.
   The plan references `/etc/wanctl/bench/<WAN>-bench-<BACKEND>.yaml` but does not create
   or test them.
3. **[Plan 02 — HIGH] Journal scoping.** `journalctl -u <unit>` can pick up logs from a
   prior arm reusing the same unit name unless bounded by `_SYSTEMD_INVOCATION_ID`
   (or cursor/boot-id/timestamp). Contaminated logs corrupt p99/stall evidence.
4. **[Plan 03 — HIGH] Representativeness is advisory, not a gate.** D-02 says a wildly
   off dev icmplib arm makes the whole run suspect, but the plan only `warn`s. It should
   be a pre-registered validity gate that aborts/blocks (`input_error`), not a soft warn.

### Notable MEDIUM concerns
- CPU% normalization unsettled (dividing by `n_cores` masks single-core contention;
  pre-register the definition).
- `CPUUsageNSec` requires `CPUAccounting=yes` on the transient unit; sampler/launcher
  should fail closed on missing/nonnumeric values.
- Prereg "committed before data" is asserted but not git-mechanically proven (record
  threshold-blob SHA + prereg commit SHA in the verdict; assert evidence commits descend
  from the prereg commit).
- `20Hz` cycle cadence is an implicit constant in the n-floor math; move `CYCLE_HZ` /
  `CYCLE_INTERVAL_MS` into the frozen JSON.
- Sequential same-run arms can still be confounded by WAN/load drift; pair/randomize
  order and rerun near threshold boundaries.
- `systemd-run` properties under-specified vs the production service (User=wanctl,
  WorkingDirectory, env, CPUAccounting, affinity).

### Divergent Views
None — single reviewer.

### Orchestrator note
Codex's central Plan-04 HIGH was independently verified against live source
(`wan_controller.py`, `linux_cake_adapter.py`): the real controller loop does issue
router/qdisc writes, so the live-collision risk is real, not hypothetical. Recommend
addressing the 4 HIGHs (especially qdisc/router-writer isolation + committed bench
configs) via `/gsd:plan-phase 243 --reviews` before the operator 8-arm run. The
unit-test scaffolding (Plans 01-03) is largely execution-ready; the blocking risk is
concentrated in Plan 04's live-run safety story.
