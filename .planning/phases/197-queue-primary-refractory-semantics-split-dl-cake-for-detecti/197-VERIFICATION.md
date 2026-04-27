---
phase: 197-queue-primary-refractory-semantics-split-dl-cake-for-detecti
verified: 2026-04-27T00:00:00Z
status: passed
score: 11/11 must-haves verified
overrides_applied: 0
---

# Phase 197: Queue-Primary Refractory Semantics Verification Report

**Phase Goal:** Split DL CAKE snapshot consumption into detection-side refractory-masked `dl_cake_for_detection` and arbitration-side live `dl_cake_for_arbitration`, preserving Phase 160 no-cascade safety and Phase 194 selector ordering while keeping queue-primary classification active during valid refractory snapshots.
**Verified:** 2026-04-27T00:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | During refractory with a valid CAKE snapshot, active primary is queue with `queue_during_refractory`. | ✓ VERIFIED | `wan_controller.py:2700-2712` returns queue/refractory reason for valid snapshots when refractory is active; `tests/test_phase_197_replay.py:208-230` verifies all 40 cycles. |
| 2 | During refractory with missing or cold-start CAKE snapshot, RTT fallback still works and is distinguishable. | ✓ VERIFIED | `wan_controller.py:2731-2739` returns `rtt_fallback_during_refractory`; tests cover `None` and `cold_start` at `tests/test_phase_197_replay.py:238-263`. |
| 3 | No repeated CAKE detection cascade during refractory. | ✓ VERIFIED | Detection path is masked at `wan_controller.py:2750-2757` and passed to `adjust_4state` at `wan_controller.py:2794-2801`; spy test asserts `cake_snapshot is None` at `tests/test_phase_197_replay.py:271-289`. |
| 4 | Phase 160 invariant is preserved: QueueController detection sees no DL CAKE snapshot during refractory. | ✓ VERIFIED | Same split wiring proves `dl_cake_for_detection=None` during refractory; protected files `queue_controller.py` and `cake_signal.py` have no diff. |
| 5 | Phase 194 invariant is preserved: selector runs after refractory masking and consumes arbitration-side snapshot. | ✓ VERIFIED | `_run_congestion_assessment` captures both locals then calls `_select_dl_primary_scalar_ms(dl_cake_for_arbitration)` at `wan_controller.py:2791-2793`, while detection receives `dl_cake_for_detection`. |
| 6 | Outside refractory behavior remains byte-identical to Phase 193/194 expected zones/rates. | ✓ VERIFIED | Integrated replay test `TestPhase197IntegratedNonRefractoryByteIdentity` at `tests/test_phase_197_replay.py:163-200`; targeted run passed: `12 passed in 0.41s`. |
| 7 | RTT-veto branch is unreachable during refractory. | ✓ VERIFIED | Selector checks refractory before the RTT-veto branch (`wan_controller.py:2693-2712` before `2722-2728`); forced setup test at `tests/test_phase_197_replay.py:349-361`. |
| 8 | `/health` includes `signal_arbitration.refractory_active` defaulting false and reflecting the per-cycle stash. | ✓ VERIFIED | Controller emits at `wan_controller.py:4230-4232`; renderer defaults at `health_check.py:779-786`; health tests passed in `tests/test_health_check.py` as part of 380-test run. |
| 9 | Metrics emit numeric `wanctl_arbitration_refractory_active` from the stash. | ✓ VERIFIED | DL metric emitted as `1.0 if refractory_active else 0.0` at `wan_controller.py:3081-3090`; tests exist in `tests/test_wan_controller.py` and controller/health run passed. |
| 10 | Healer-bypass alignment state resets on refractory entry and cannot increment during refractory. | ✓ VERIFIED | Entry reset at `wan_controller.py:2871-2879`; refractory guard at `2823-2832`; interaction tests at `tests/test_phase_197_replay.py:297-347`. |
| 11 | Phase 196 audit/capture tooling accounts for Phase 197 refractory regimes. | ✓ VERIFIED | Capture script exports `refractory_active` and metric names (`scripts/phase196-soak-capture.sh:116,148,219,267`); predicate doc accepts `queue_during_refractory` and buckets `rtt_fallback_during_refractory + refractory_active=true` with raw-only filtering. |

**Score:** 11/11 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/wanctl/wan_controller.py` | Split locals, new reason constants, stash, health/metric emission, healer guard | ✓ VERIFIED | Constants at lines 94-95; split locals at 2750-2757; selector at 2677-2739; metric at 3081-3090. |
| `src/wanctl/health_check.py` | Renderer relays `refractory_active` with default false | ✓ VERIFIED | `_build_signal_arbitration_section` returns `refractory_active` at line 786. |
| `tests/test_phase_197_replay.py` | Replay, refractory queue/fallback/no-cascade/healer tests | ✓ VERIFIED | 361 substantive lines; targeted test run: 12 passed. |
| `tests/test_wan_controller.py` | Selector, health-shape, metric-emission coverage | ✓ VERIFIED | Included in controller/health test run: 380 passed. |
| `tests/test_health_check.py` | Renderer shape/default/reason relay coverage | ✓ VERIFIED | Included in controller/health test run: 380 passed. |
| `scripts/phase196-soak-capture.sh` | Captures refractory health and metric fields | ✓ VERIFIED | `refractory_active` extraction and summary wiring found. |
| `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/primary-signal-audit-phase197.md` | Phase 197 audit predicate contract | ✓ VERIFIED | Documents accept-list, regime buckets, and raw-only metric filter. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `_run_congestion_assessment` | `_select_dl_primary_scalar_ms` | `dl_cake_for_arbitration` | ✓ WIRED | `wan_controller.py:2791-2793`. |
| `_run_congestion_assessment` | `download.adjust_4state` | `cake_snapshot=dl_cake_for_detection` | ✓ WIRED | `wan_controller.py:2794-2801`. |
| Pre-decrement refractory state | `/health` + metrics | `_dl_arbitration_used_refractory_snapshot` | ✓ WIRED | Stashed at `2754`, health at `4230-4232`, metric at `3081-3090`. |
| Controller health data | HTTP health renderer | `refractory_active` relay | ✓ WIRED | `health_check.py:779-786`. |
| Phase 197 reason vocabulary | Phase 196 audit predicate | accept-list / separate fallback bucket | ✓ WIRED | Predicate doc and capture script contain the new fields/reasons. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `src/wanctl/wan_controller.py` | `dl_cake_for_arbitration` | `self._dl_cake_snapshot` before refractory detection mask | Yes | ✓ FLOWING |
| `src/wanctl/wan_controller.py` | `dl_cake_for_detection` | `self._dl_cake_snapshot`, then `None` during refractory | Yes, intentionally masked for detection only | ✓ FLOWING |
| `src/wanctl/wan_controller.py` | `_dl_arbitration_used_refractory_snapshot` | Pre-decrement `_dl_refractory_remaining > 0` | Yes | ✓ FLOWING |
| `src/wanctl/health_check.py` | `refractory_active` | Controller `signal_arbitration` dict, default false when omitted | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Phase 197 replay and invariants | `.venv/bin/pytest -o addopts='' tests/test_phase_197_replay.py -q` | `12 passed in 0.41s` | ✓ PASS |
| Controller + health regressions | `.venv/bin/pytest -o addopts='' tests/test_wan_controller.py tests/test_health_check.py -q` | `380 passed in 38.31s` | ✓ PASS |
| Protected no-touch surfaces | `git diff -- src/wanctl/queue_controller.py src/wanctl/cake_signal.py` | no output | ✓ PASS |
| Orchestrator regression/replay gate | Provided context | `607 passed, 6 skipped` | ✓ PASS |
| Schema drift gate | Provided context | `drift_detected=false` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| N/A | `197-01-PLAN.md`, `197-02-PLAN.md` | Plan frontmatter `requirements: []`; ROADMAP states requirements TBD/no mandated REQ-IDs. | ✓ VERIFIED | No Phase 197 REQ IDs in `REQUIREMENTS.md`; implicit roadmap tests and invariants are verified above. |
| Implicit gate | ROADMAP Phase 197 | No repeated CAKE detection cascade during refractory. | ✓ SATISFIED | Truths 3-4. |
| Implicit gate | ROADMAP Phase 197 | RTT fallback still works when queue snapshot genuinely unavailable. | ✓ SATISFIED | Truth 2. |
| Implicit gate | ROADMAP Phase 197 | `active_primary_signal=queue` during refractory when valid queue snapshot exists. | ✓ SATISFIED | Truth 1. |
| Implicit gate | ROADMAP Phase 197 | Preserve Phase 160 no-cascade invariant. | ✓ SATISFIED | Truths 3-4. |
| Implicit gate | ROADMAP Phase 197 | Preserve Phase 194 selector-after-masking invariant. | ✓ SATISFIED | Truth 5. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `scripts/phase196-soak-capture.sh` | 221-222 (from review) | Burst counters read from absent health paths | ⚠️ Warning | Advisory only per orchestrator context; can under-report burst summary counters but does not block Phase 197 refractory semantics. |
| `src/wanctl/wan_controller.py` | 3160 | `return {}` | ℹ️ Info | Legitimate non-LinuxCakeAdapter empty timing payload, not introduced as a Phase 197 stub and not user-visible placeholder behavior. |

### Human Verification Required

None. The phase goal is control-path semantics and audit predicate readiness; all roadmap-mandated tests/invariants are covered by automated replay/static checks. Production throughput rerun remains a Phase 196 validation activity, not a Phase 197 implementation gate.

### Gaps Summary

No blocking gaps found. Phase 197 achieves the requested goal: detection masking remains cascade-safe, arbitration remains queue-primary during valid refractory snapshots, invalid snapshots fall back to RTT with a distinct reason, RTT-veto/healer bypass are suppressed during refractory, and health/metrics/audit surfaces expose the regime.

---

_Verified: 2026-04-27T00:00:00Z_
_Verifier: the agent (gsd-verifier)_
