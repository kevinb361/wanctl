---
phase: 242
reviewers: [codex]
reviewed_at: 2026-06-15T00:00:00Z
plans_reviewed: [242-01-PLAN.md, 242-02-PLAN.md, 242-03-PLAN.md, 242-04-PLAN.md]
---

# Cross-AI Plan Review — Phase 242

## Codex Review

## Overall

The plans are directionally right, but not yet executable-safe. The biggest unresolved issue is the factory/thread contract: current `WANController.start_background_rtt()` always builds `BackgroundRTTThread` later, and `WANController.measure_rtt()` unconditionally calls `get_cycle_status()` on the thread. `FpingThread` does not provide that method. See `wan_controller.py:1080`, `wan_controller.py:1152`, and `fping_measurement.py:281`. That must be resolved explicitly before execution.

## 242-01-PLAN.md

**Summary**

Good TDD/scaffolding plan, but it risks freezing the wrong public contract before the factory design is settled. The verifier work is useful, but grep-only validation is weak for a hard SAFE-17 gate.

**Strengths**

- Establishes fallback behavior before implementation.
- Correctly adds a standing `/health` subset-preservation regression.
- Creates the Phase 242 boundary verifier early enough for later plans to use.

**Concerns**

- **MEDIUM:** The factory tests may force an invalid return shape if they assert concrete `BackgroundRTTThread` / `FpingThread` instances too early. Autorate cannot build either real thread at `_create_wan_components()` time because host selection, shutdown event, and pool are later.
- **MEDIUM:** The SAFE-17 verifier acceptance relies mostly on `grep` and `bash -n`; this catches syntax and strings, not whether the allowlist fails closed.
- **LOW:** "Byte-preserved" is slightly misleading for JSON with additive keys. The test should assert exact values and rounding for the three fields, not object bytes or full dict equality.

**Suggestions**

- Define the stable factory public contract in the test as a small handle/bundle shape, not a raw tuple unless that shape is already decided.
- Add a verifier negative self-test or detached-worktree test that proves an out-of-allowlist `src/wanctl` edit fails.
- Make the `/health` preservation test explicitly subset-based: `available`, `raw_rtt_ms`, `staleness_sec`.

**Risk Assessment**

MEDIUM. It only adds tests/scripts, but bad tests here can drive Plans 02/03 toward an unsafe implementation.

## 242-02-PLAN.md

**Summary**

This is the weakest plan. It says "factory returns backend and thread," but the current runtime lifecycle makes that impossible as written. The plan needs a precise backend handle and thread-factory protocol before implementation.

**Strengths**

- Correctly keeps factory out of `rtt_backend.py`.
- Correctly uses construction-time `shutil.which("fping")`.
- Keeps fallback loud and observable as a first-class contract.

**Concerns**

- **HIGH:** `build_rtt_backend(config, source_ip, shutdown_event, logger)` is not a viable autorate construction signature. `shutdown_event`, `hosts_fn`, pool, and reflector scorer context are not all available at `_create_wan_components()`.
- **HIGH:** `FpingThread` is not interchangeable with `BackgroundRTTThread`; `measure_rtt()` requires `get_cycle_status()`. Returning raw `FpingThread` will break the live path.
- **HIGH:** `BackgroundRTTThread` cannot wrap `FpingMeasurement`; it is built around the legacy RTT measurement path, not the `RttBackend.probe()` protocol.
- **MEDIUM:** Fping timeout-vs-cadence is currently validator `WARN`, but `FpingThread` raises `ValueError`. If Phase 242 constructs fping live, a warned config can become a startup crash.
- **MEDIUM:** Fallback counter semantics are vague. Global process counter vs per-WAN counter affects `/health` attribution in multi-WAN operation.
- **MEDIUM:** WARN-once should be scoped at least per WAN/requested backend. Process-global once can hide fallback on the second WAN.

**Suggestions**

- Introduce an explicit dataclass, e.g. `RttBackendHandle`, with `backend`, `backend_active`, `fell_back`, `fallback_count`, and `make_thread(...)`.
- Introduce a common thread protocol: `start`, `stop`, `get_latest`, `get_cycle_status`, `get_profile_stats`, `cadence_sec`.
- Add an adapter in the factory module for fping, or explicitly expand scope to make `FpingThread` satisfy the protocol. Given the 241 freeze, an adapter inside `rtt_backend_factory.py` is safer.
- Add tests for fping selected with valid binary but invalid timeout/cadence behavior. Decide whether that is loud fallback or startup failure.

**Risk Assessment**

HIGH. Without a concrete handle/thread protocol, this can pass unit tests while still breaking the live autorate path.

## 242-03-PLAN.md

**Summary**

The intended wiring is right, but the plan understates the live-path implications. It says "construction only," but for autorate, `measurement.backend: fping` would become live consumption once wired. That is acceptable only if the thread protocol and tests are made explicit.

**Strengths**

- Correctly preserves steering consumption as autorate `/health` based. Current steering still uses autorate health in `measure_current_rtt()` at `daemon.py:1757`.
- Correctly treats `/health` keys as additive and preserves the three steering-consumed fields in `health_check.py:493`.
- Correctly identifies `source_ip` binding as worth fixing before Phase 245.

**Concerns**

- **HIGH:** Autorate fping selection is a live behavior change, not construction-only. The default remains icmplib, but selected fping must be treated as live controller-path behavior.
- **HIGH:** `WANController` needs a thread factory/status handle, probably as optional constructor state. Making it required would churn many tests and call sites.
- **HIGH:** Assigning a raw `FpingThread` to `_rtt_thread` breaks `measure_rtt()` because `get_cycle_status()` is missing.
- **MEDIUM:** Steering `source_ip` loading via raw YAML and swallowed exceptions can silently pass `None`, defeating D-01a. This should be loud in logs and covered by a test.
- **MEDIUM:** It is unclear whether steering factory construction should use steering config's backend default or the primary WAN autorate config's `measurement.backend`. For Phase 245 readiness, this should be explicit.
- **MEDIUM:** `/health` fallback metadata must be per controller/WAN, not just read from a module-level global accessor.
- **LOW:** Mock health tests need updating carefully; otherwise they may prove `health_check.py` reflection but not real `WANController.get_health_data()` production.

**Suggestions**

- Add `WANController(..., rtt_thread_factory=None, rtt_backend_status=None)` defaults to avoid broad test churn.
- Add a real `tests/test_wan_controller.py` assertion that `get_health_data()["measurement"]` includes `backend_active`, `fell_back`, `fallback_count`.
- Add a fping-selected integration/unit test that starts background RTT with the factory-produced thread handle and calls `measure_rtt()` without AttributeError.
- Add a steering test that `_create_steering_components()` passes non-`None` `source_ip` from the primary WAN config and does not consume the constructed pinger.

**Risk Assessment**

HIGH. This is the actual controller-path wiring. The plan is sound in intent but underspecified at the exact compatibility point most likely to fail.

## 242-04-PLAN.md

**Summary**

Good hard-gate concept. The verifier-first posture fits SAFE-17, but the plan overstates what the evidence should look like and leaves too much room to wave off full-suite failures.

**Strengths**

- Requires clean committed `src/wanctl` before running the boundary verifier.
- Keeps protected-body verification in place.
- Correctly says not to widen the allowlist to pass.

**Concerns**

- **MEDIUM:** The expected `changed_paths` wording is wrong if diffing against `v1.52`: prior Phase 239-241 allowlisted files will also appear, not only the five Phase 242 files.
- **MEDIUM:** "Legacy full-suite failures" is too broad. Any full-suite failure should be classified with evidence, ideally by reproducing on the pre-242 anchor or citing prior phase evidence.
- **MEDIUM:** The verifier script itself and Plan 01 test changes should be committed before evidence generation, or the evidence is not fully reproducible.
- **LOW:** The 241-close guard is good, but it should emit explicit fields for the new no-drift result so Plan 04 can assert it directly, not infer from pass/fail.

**Suggestions**

- Change Plan 04 expected evidence to: `changed_paths` is a subset of the full SAFE-17 allowlist, with Phase 242 source files present as expected.
- Require phase-local tests, hot-path tests, and full suite classification with concrete failure names if not green.
- Assert the new 241-close guard field directly in the JSON.
- Commit verifier/test/source changes before the final evidence run, then commit evidence immediately after.

**Risk Assessment**

MEDIUM. The gate is the right control, but inaccurate evidence expectations can either create false failures or normalize weak signoff.

## Final Risk

Overall risk is **HIGH until the thread-factory contract is fixed**, then likely **MEDIUM**. The phase can satisfy FALL-01/FALL-02/SAFE-17, but only if Plans 02/03 explicitly define a common thread handle compatible with `WANController.measure_rtt()` and keep fallback metadata per-WAN.

---

## Consensus Summary

Single reviewer (Codex) this cycle; no cross-reviewer consensus to compute. The orchestrator independently verified the central HIGH finding against live source (see below).

### Agreed Strengths

- Verifier-first / TDD posture: fallback contract and SAFE-17 boundary verifier authored before implementation (Plans 01, 04).
- Factory correctly kept out of the byte-frozen `rtt_backend.py`; construction-time `shutil.which("fping")` is the right fallback trigger (Plan 02).
- `/health` keys are additive and the three steering-consumed fields are preserved; steering consumption correctly stays dead until Phase 245 (Plan 03).

### Agreed Concerns (highest priority)

- **HIGH — Thread/backend contract mismatch (Plans 02 + 03).** `WANController.measure_rtt()` (`wan_controller.py:1152`) unconditionally calls `self._rtt_thread.get_cycle_status()`. `FpingThread` (`fping_measurement.py:281-340`) does **not** implement `get_cycle_status()` (it has only `cadence_sec`/`get_latest`/`get_profile_stats`/`start`/`stop`). `BackgroundRTTThread` (`rtt_measurement.py:472`) does. Additionally `get_latest()` returns `RttSample` on `FpingThread` vs `RTTSnapshot` on `BackgroundRTTThread`. So a factory that hands a raw `FpingThread` to `_rtt_thread` will `AttributeError` on the live autorate path the moment `measurement.backend: fping` is selected — while unit tests asserting only on the fallback signal stay green. **Verified by orchestrator against live code.** The plans say "thread or builder" but never define the common thread protocol `measure_rtt()` requires. This is the load-bearing gap.
- **MEDIUM — Per-WAN vs process-global fallback state.** WARN-once and `fallback_count` scoped process-globally can hide a fallback on the second WAN and corrupt `/health` attribution in the dual-WAN deployment.
- **MEDIUM — fping timeout-vs-cadence is validator WARN but FpingThread raises ValueError.** A "warned" config can become a startup crash once 242 constructs fping live; the plans don't decide whether that is loud fallback or hard failure.
- **MEDIUM — Steering source_ip via raw YAML with swallowed exceptions can silently pass None,** defeating D-01a; should be loud + test-covered.
- **MEDIUM — Plan 04 evidence expectation ("changed_paths contains only the five 242 files") is wrong against the v1.52 anchor;** prior 239–241 allowlisted files will also appear. Should be "subset of the full allowlist, with the 242 files present."

### Divergent Views

None — single reviewer.

### Orchestrator Note (verification)

The central HIGH finding was independently confirmed against live source: `get_cycle_status` is called at `wan_controller.py:1152` and is absent from `FpingThread`. The recommended remediation (a `RttBackendHandle` dataclass exposing a `make_thread(...)` builder plus a common thread protocol — `start/stop/get_latest/get_cycle_status/get_profile_stats/cadence_sec` — with an fping adapter living in `rtt_backend_factory.py` so the 241-frozen `fping_measurement.py` is not touched) is consistent with the SAFE-17 allowlist and the Pitfall-1 thread-timing note already in the plans. Replanning Plans 02 and 03 to pin this contract before execution is warranted.
