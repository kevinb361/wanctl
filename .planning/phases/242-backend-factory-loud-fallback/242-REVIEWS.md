---
phase: 242
reviewers: [codex]
reviewed_at: 2026-06-16T02:47:57Z
plans_reviewed: [242-01-PLAN.md, 242-02-PLAN.md, 242-03-PLAN.md, 242-04-PLAN.md]
cycle: 3
prior_cycle_high: 1
current_cycle_high: 1
---

# Cross-AI Plan Review — Phase 242 (Cycle 3 / re-review of revised plans)

This is the third review cycle. The plans below are the REPLANNED versions authored to
close the Cycle-2 load-bearing HIGH (`WANController.rtt_measurement` bound to a
`FpingMeasurement` → `AttributeError` on `ping_host`/`ping_hosts_with_results`/`maybe_probe`).
Codex was asked to (1) confirm closure of the Cycle-2 HIGH, (2) confirm the Cycle-1 HIGH
stays closed, and (3) surface any newly-introduced gap. The orchestrator independently
verified the new finding against live source.

## Prior-Finding Closure (Cycle 2 → Cycle 3)

| Cycle-2 finding | Status | Evidence |
|---|---|---|
| **HIGH** — Incomplete `rtt_measurement` substitution (`FpingMeasurement` on the positional slot → `AttributeError` at `:1269`/`:1474`/`:3127`) | **FULLY RESOLVED** | Plan 02 adds `RttBackendHandle.controller_measurement` (ALWAYS an icmplib `RTTMeasurement`, never a `FpingMeasurement`); Plan 03 binds `handle.controller_measurement` into the positional `rtt_measurement` slot and explicitly states it is NEVER `handle.backend`; Plan 01 adds `test_controller_measurement_is_rttmeasurement` exercising all three live helper paths under a fping-selected config without `AttributeError`. Codex + orchestrator verified the live-code shape; the `backend`/`controller_measurement` split is the right fix. |
| **MEDIUM** — fping scorer/loss semantics unspecified for live fping mode | **PARTIALLY RESOLVED** | Plans 02/03 document (in prose/comments) that the reflector scorer always runs on the icmplib `controller_measurement` and fping does not drive the scorer in 242. But no test or factory-construction assertion pins that `FpingMeasurement` is built WITHOUT a shared `scorer` — and live `FpingMeasurement.probe()` calls `_scorer.record_results(...)` when a scorer is supplied. Scope is decided but not enforced. |
| **MEDIUM** — steering backend source-of-truth ambiguity | **MOSTLY RESOLVED** | Plan 03 now resolves BOTH `source_ip` AND `measurement.backend` from the PRIMARY WAN config (the file `_derive_primary_health_url` opens), not `steering.yaml`, made explicit in a comment + a test. Residual: `build_rtt_backend` expects a Config-like object; passing raw YAML vs `Config` needs an explicit adapter/helper or executors may still drift. |
| **MEDIUM** — Plan 03 `files_modified` omits test files | **FULLY RESOLVED** | Plan 03 frontmatter `files_modified` now lists `tests/test_wan_controller.py` and `tests/test_health_check.py`. |
| **MEDIUM** — verifier self-test / Plan 04 reproduction must commit edits in detached worktrees; dirty-tree precheck covers tests/+scripts/ | **FULLY RESOLVED** | Plan 01 self-test commits the synthetic out-of-allowlist edit inside `git worktree add --detach` (proving allowlist, not dirty-tree, fails closed); Plan 04 requires a clean tree across `src/wanctl/`, `tests/`, `scripts/` before evidence and detached-worktree reproduction for failure classification. |

Both prior load-bearing HIGHs (Cycle-1 thread protocol, Cycle-2 measurement object) are
closed in the revised plans. **However, this cycle surfaces one NEW load-bearing HIGH** —
a fping-cadence wiring defect that would make fping permanently dead in the live path.

## Codex Review

**Resolution Status**

- **Cycle-2 HIGH (rtt_measurement substitution): FULLY RESOLVED in the revised plan design**, pending execution.
  - `242-01`: `test_controller_measurement_is_rttmeasurement` asserts under a fping-selected config that `handle.controller_measurement` is `RTTMeasurement` (not `FpingMeasurement`) and runs `ping_host`, `ping_hosts_with_results`, and `maybe_probe(...)` without `AttributeError`.
  - `242-02`: requires `RttBackendHandle.controller_measurement` is ALWAYS an icmplib `RTTMeasurement` (never a `FpingMeasurement`).
  - `242-03`: requires autorate to construct `WANController(..., handle.controller_measurement, ..., rtt_thread_factory=handle, rtt_backend_status=handle)` and says the positional `rtt_measurement` slot is NEVER `handle.backend`.
- **Cycle-1 HIGH (thread protocol): stays closed.** `242-02` requires an fping adapter (`get_cycle_status()->None`, `get_latest()->RttSample.to_snapshot()`) and `242-03` assigns `_rtt_thread` from `handle.make_thread(...)`, never a raw `FpingThread`.
- Live code shape verified: `WANController.rtt_measurement` is still consumed at the three helper paths, and `FpingThread` still lacks `get_cycle_status()`. The split is correct.

### 242-01-PLAN.md

**Summary:** Strong TDD scaffold. Pins fallback behavior, thread protocol, controller-measurement safety, `/health` subset preservation, and SAFE-17 verifier behavior before implementation.

**Strengths**
- Directly tests both historical HIGHs.
- Tests the produced thread protocol, not just the handle metadata.
- Explicitly exercises all three Cycle-2 helper paths.
- Health byte-preservation is a subset assertion, so additive keys remain allowed.
- Detached-worktree committed negative self-test is the right shape for fail-closed verifier proof.

**Concerns**
- **HIGH:** Missing a test that fping-selected LIVE startup uses `measurement.fping.cadence_sec`. The plans test `make_thread(... cadence_sec > timeout)` manually, but Plan 03 passes `WANController._background_rtt_cadence_sec()` in live wiring. That value is min-capped at `0.25s`, while the default-ish fping timeout is ~`3s` (`count=5 * period_ms=200/1000 + grace=2.0`), so fping would loudly fall back to icmplib every time despite a valid fping config.
- **MEDIUM:** The plan says fping does not drive the reflector scorer in 242, but no test pins that `FpingMeasurement` is constructed without a shared scorer. Current `FpingMeasurement.probe()` calls `_scorer.record_results(...)` if a scorer is supplied.
- **LOW:** The controller-helper-path test should call the actual controller paths, not only monkeypatch method presence on `RTTMeasurement`; acceptance should be strict.

**Suggestions**
- Add a test using the real `start_background_rtt()` path with fping selected and a valid `measurement.fping.cadence_sec`, asserting `backend_active == "fping"` after thread construction.
- Add a test/assertion that 242 fping construction does not pass a live scorer into `FpingMeasurement`.

### 242-02-PLAN.md

**Summary:** The factory/handle design correctly separates background backend selection from controller helper measurement. This is the core fix.

**Strengths**
- `controller_measurement` always icmplib closes the Cycle-2 failure class.
- In-module fping adapter closes the Cycle-1 thread-protocol failure class.
- Deferred `make_thread()` matches existing lifecycle constraints.
- Per-WAN WARN-once and per-handle fallback state are good.
- Timeout-vs-cadence fallback keeps the daemon from crashing.

**Concerns**
- **HIGH:** The fping cadence model is wrong/underspecified. Phase 241 (D-06) established an INDEPENDENT fping `cadence_sec` knob (default ~10s; validator key `measurement.fping.cadence_sec`), but this plan's `make_thread(... cadence_sec)` uses the caller-supplied cadence for fping. In Plan 03 the caller-supplied cadence is the controller background-RTT cadence (`_background_rtt_cadence_sec()`, min `0.25s`), not `measurement.fping.cadence_sec`. Result: valid fping configs silently degrade to icmplib at thread construction (`FpingThread` raises `ValueError` when `timeout >= cadence`, fping_measurement.py:299).
- **MEDIUM:** "Factory owns a SINGLE `shutil.which("fping")` probe" conflicts with the frozen `FpingMeasurement.__init__`, which calls `shutil.which("fping")` internally and accepts no binary path. Either allow changing `FpingMeasurement` or weaken the claim to "factory probe authoritative; internal probe tolerated and patched in tests."
- **MEDIUM:** Plan does not explicitly say to OMIT `scorer` from the `FpingMeasurement` config. Given the live scorer feed, that ambiguity could introduce duplicate/concurrent reflector scoring.
- **LOW:** Factory hardcodes autorate's `AVERAGE/log_sample_stats=True` shape, while steering uses `MEDIAN/log_sample_stats=False`. Steering is dead in 242, but this should be a deliberate API decision before Phase 245.

**Suggestions**
- Store the resolved fping thread cadence in the handle from `config.data["measurement"]["fping"]["cadence_sec"]` with a safe default, and use that for `FpingThread`.
- Add factory tests asserting fping-present + valid fping cadence returns an adapter and stays `backend_active == "fping"` after `make_thread()`.
- Resolve the `shutil.which` contradiction explicitly.

### 242-03-PLAN.md

**Summary:** Correctly wires the factory into autorate and steering, and correctly binds `handle.controller_measurement` into `WANController`.

**Strengths**
- The live autorate binding is now explicitly safe: `handle.controller_measurement`, never `handle.backend`.
- Optional constructor args avoid broad test/call-site churn.
- `measure_rtt()` remains protected and untouched.
- `/health` status is per-controller, not module-global.
- Steering source-of-truth corrected to the primary WAN config instead of `steering.yaml`.

**Concerns**
- **HIGH:** Live fping startup likely falls back because `start_background_rtt()` passes `_background_rtt_cadence_sec()` into `handle.make_thread(...)`. This does not honor the independent fping cadence validated in Phase 241. (Same root cause as the 242-02 HIGH; this is the live-wiring manifestation.)
- **MEDIUM:** Steering says it resolves both backend and source IP from the primary WAN config, but the factory signature expects a Config-like object. Passing raw YAML vs `Config` needs an explicit adapter/helper, otherwise executors may accidentally read backend from `steering.yaml` or lose timeout/fping params.
- **MEDIUM:** The "fping does not drive scorer" scope is only comments/prose unless the factory construction prevents `scorer` from entering `FpingMeasurement`.
- **LOW:** Steering now constructs and may warn/fall back for a dead pinger. Consistent with "route construction only," but operators may see new warnings for something not yet consumed.

**Suggestions**
- Change `make_thread()` so fping ignores the controller cadence and uses the resolved fping cadence, or pass a backend-specific cadence from the handle.
- Add a Plan 03 test proving the real `WANController.start_background_rtt()` path stays fping-active with valid fping config.
- Add a helper like `_load_primary_wan_config_for_rtt_backend()` returning a clear Config-like object or explicit factory inputs.

### 242-04-PLAN.md

**Summary:** Good boundary gate. Fixes earlier review problems around committed evidence, full-allowlist scope, the explicit 241 guard, and detached-worktree failure classification.

**Strengths**
- Correctly expects changed paths to be a subset of the full v1.53 allowlist, not only Phase 242 files.
- Requires tests/scripts/source committed before evidence.
- Requires the explicit 241 frozen-file no-drift field.
- Requires named full-suite failure classification, not a broad "legacy" bucket.

**Concerns**
- **MEDIUM:** SAFE-17 will NOT catch the fping-cadence semantic failure. All affected edits are allowlisted and protected bodies can stay byte-identical while live fping mode always falls back to icmplib — the gate is a path/byte gate, not a functional one.
- **LOW:** The evidence gate depends on Plan 01's self-test quality. Keep the self-test path separate from real evidence output so it cannot pollute phase evidence.

**Suggestions**
- Add a phase-local functional assertion to the gate set: fping selected, binary present, valid `measurement.fping.cadence_sec`, real `start_background_rtt()` path, `backend_active == "fping"`.

**Overall Risk Assessment: MEDIUM.** The `AttributeError` failure class is resolved by the
revised design. The remaining load-bearing problem is not "will fping crash the live path,"
but "will fping ever actually run in the live path after wiring." The independent fping
cadence gap is a HIGH plan defect for phase correctness and A/B readiness, but the loud
fallback makes it unlikely to break the live controller outright. Fix cadence handling and
pin scorer non-use, and the plans become much lower risk.

---

## Consensus Summary

Single reviewer (Codex) this cycle; no cross-reviewer consensus to compute. The orchestrator
independently verified the new HIGH against live source (see below).

### Agreed Strengths

- The Cycle-2 load-bearing HIGH (`rtt_measurement` substitution) is genuinely closed: the
  `backend` vs `controller_measurement` split + a controller-helper-paths regression test
  exercising `:1269`/`:1474`/`:3127` under fping mode.
- The Cycle-1 HIGH (raw `FpingThread` in `measure_rtt()`) stays closed.
- Plan 04 evidence discipline (full-allowlist subset, explicit 241-close-guard field,
  per-failure classification, detached-worktree reproduction) is sound.

### Agreed Concerns (highest priority)

- **HIGH (NEW, verified) — fping cadence wiring makes fping permanently dead in the live
  path.** Phase 241 (D-06) gave fping an INDEPENDENT `measurement.fping.cadence_sec` knob
  (default ~10s) precisely so bursts never pile; the validator already recognizes
  `measurement.fping.cadence_sec`. But Plans 02/03 wire
  `make_thread(... cadence_sec=self._background_rtt_cadence_sec())` — the ICMP background
  cadence (`max(cycle_interval, 0.25s)` ≈ `0.25s` on the 50ms loop). `FpingThread.__init__`
  raises `ValueError` when `measurement._timeout >= cadence_sec` (fping_measurement.py:299),
  and the default fping timeout is `count(5)*period_ms(200)/1000 + grace(2.0) = 3.0s`. So
  `3.0 >= 0.25` → `ValueError` → the plans' "loud timeout-vs-cadence fallback" disposition
  fires EVERY time → `backend_active` is permanently `icmplib`. The phase would ship a
  "working, all-green" factory in which fping never actually runs, defeating FALL-01/FALL-02
  intent for the live path and leaving Phase 245's A/B with nothing to A/B against. The
  manual `make_thread(cadence_sec > timeout)` tests pass while live wiring degrades.
  **Remediation:** resolve the fping thread cadence from `measurement.fping.cadence_sec`
  (with a safe default) on the handle and use THAT for `FpingThread` — do not pass the
  controller background-RTT cadence to the fping branch. Add a test on the real
  `start_background_rtt()` path asserting `backend_active == "fping"` with a valid fping
  cadence.
- **MEDIUM** — fping scorer non-use is decided in prose only; no construction assertion/test
  prevents a shared `scorer` from entering `FpingMeasurement` (live `probe()` would then
  `_scorer.record_results(...)`, risking duplicate/concurrent reflector scoring).
- **MEDIUM** — steering passes a Config-like object to `build_rtt_backend`; raw-YAML vs
  `Config` needs an explicit adapter/helper or executors may still read backend from
  `steering.yaml` / drop fping params.
- **MEDIUM** — single `shutil.which` claim conflicts with the frozen
  `FpingMeasurement.__init__` internal probe; resolve explicitly (factory-authoritative +
  patch both sites in tests).
- **MEDIUM** — SAFE-17 (Plan 04) is a path/byte gate and will not catch the cadence
  functional defect; add a phase-local functional assertion to the gate set.

### Divergent Views

None — single reviewer.

### Orchestrator Note (verification)

The new HIGH was independently confirmed against live source:
- `src/wanctl/wan_controller.py:1105` — `_background_rtt_cadence_sec()` returns
  `max(self._cycle_interval_ms/1000, BACKGROUND_RTT_MIN_CADENCE_SECONDS)`;
  `BACKGROUND_RTT_MIN_CADENCE_SECONDS = 0.25` (`wan_controller.py:90`).
- `src/wanctl/fping_measurement.py:57` — `_timeout = count*period_ms/1000 + grace`; with the
  defaults (`count=5`, `period_ms=200`, `timeout_grace_sec=2.0`) → `3.0s`.
- `src/wanctl/fping_measurement.py:299-301` — `FpingThread.__init__` raises `ValueError` when
  `measurement._timeout >= cadence_sec`.
- `src/wanctl/check_config_validators.py:258` — `measurement.fping.cadence_sec` is a
  recognized config key (the independent fping cadence from Phase 241 D-06), but neither
  Plan 02 nor Plan 03 reads it for the `make_thread`/`FpingThread` cadence.
- Plans 02 (interface block / make_thread) and 03 (start_background_rtt edit, line
  "cadence_sec=self._background_rtt_cadence_sec()") confirm the controller cadence is what
  flows into the fping branch.

Net: `3.0 >= 0.25` is always true with the validated defaults, so the live fping path would
deterministically fall back to icmplib at startup. This is a plan defect, not a code bug —
it should be fixed in Plans 02/03 (resolve and thread the fping-specific cadence) plus a
real-path test in Plan 01 before execution.

**Recommendation:** Replan 02 and 03 to thread `measurement.fping.cadence_sec` into the
fping `make_thread`/`FpingThread` construction (with a safe default and the existing
`timeout < cadence` invariant honored), pin fping scorer non-use with a construction
assertion, and add a real-`start_background_rtt()` functional test asserting
`backend_active == "fping"`. After that, residual risk drops to MEDIUM (execution hygiene
+ steering Config-shape + scorer-scope enforcement).
