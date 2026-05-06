---
phase: 202-ul-suppression-metric-semantics-metric
verified: 2026-05-06T21:31:58Z
status: passed
score: 11/11 must-haves verified
overrides_applied: 0
---

# Phase 202: UL Suppression Metric Semantics (METRIC) Verification Report

**Phase Goal:** Operators can read completed-window UL suppression counts decomposed by cause from `/health.wans[].upload`, and the new metric matches codex re-aggregation values from the v1.42 reference soak — without changing controller behavior.
**Verified:** 2026-05-06T21:31:58Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator can read `suppressions_completed_window_count` from `/health.wans[].upload` with values that emit only at 60s window boundaries; live `suppressions_per_min` is preserved untouched. | ✓ VERIFIED | `QueueController.reset_window()` snapshots `_last_completed_window_total` before zeroing live cause counters and returns the legacy int count (`src/wanctl/queue_controller.py:690-706`). `/health` copies `suppressions_completed_window_count` and preserves `suppressions_per_min` (`health_check.py:309-331`). Tests cover initial shape, round-trip, and backlog-recovery not affecting `suppressions_per_min` (`tests/test_health_check.py:3114-3171`). |
| 2 | Each suppression increment is classified at source as `dwell_hold`, `backlog_recovery`, or `other` and surfaced as additive per-cause `/health` count fields. | ✓ VERIFIED | `_record_suppression(cause)` allowlists/falls back to `other` (`queue_controller.py:354-371`). Dwell-hold callsite records `dwell_hold` after the legacy counter (`queue_controller.py:388-390`); 3-state and 4-state backlog recovery callsites record `backlog_recovery` (`queue_controller.py:274-276`, `639-641`). Per-cause completed-window and lifetime dicts are emitted by `get_health_data()` and `_build_rate_hysteresis_section()` (`queue_controller.py:722-727`, `health_check.py:320-331`). |
| 3 | Replay test against `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/soak-capture.ndjson` confirms completed-window counts match the codex oracle: peak mean ~13.9/min, p95=41, max=124. | ✓ VERIFIED | `tests/test_phase_202_replay.py` reads the canonical fixture path and uses strict reset-boundary detection (`snapshots[i] < snapshots[i-1]`). Independent spot-check computed `84117` samples, `1331` observable completed windows, mean `13.890308039068369`, p95 `41.0`, max `124`. |
| 4 | SAFE-05 v1.43 occurrence pins are re-established for new metric keys; existing v1.42 control-path pins remain unchanged/valid for SAFE-07. | ✓ VERIFIED | `tests/test_phase_195_replay.py:642-714` contains the existing v1.40/v1.41 pins, corrected v1.42 pins, and new `phase202_expected_counts`. Empirical source counts match: `_record_suppression=4`, `_window_suppressions_by_cause=6`, `_lifetime_suppressions_by_cause=3`, `_last_completed_window_total=3`, `_last_completed_window_by_cause=3`, and each new public key count `=3`. |
| 5 | `CHANGELOG.md` and `docs/CONFIGURATION.md` document the additive `/health` fields and live-counter vs completed-window metric framing. | ✓ VERIFIED | `CHANGELOG.md:8-25` documents the v1.43-dev additive field set, symmetry, backward compatibility, watchdog warning, and per-cycle backlog note. `docs/CONFIGURATION.md:294-317` documents the field comparison, cause taxonomy, per-cycle accounting, warning not to use `suppressions_per_min` as a rate, backward compatibility, and fixture pointer. |
| 6 | `QueueController` exposes a per-cause window counter fed by all three suppression callsites at source. | ✓ VERIFIED | Per-cause dict initialized at `queue_controller.py:95-99`; all three source callsites invoke `_record_suppression` with correct cause tags (`274-276`, `388-390`, `639-641`). Tests verify helper and 3-state/4-state callsite tagging (`tests/test_queue_controller.py:2702-2775`). |
| 7 | `QueueController` exposes a per-cause lifetime monotonic counter alongside the window counter. | ✓ VERIFIED | `_lifetime_suppressions_by_cause` initialized at `queue_controller.py:100-104`, incremented in `_record_suppression()` (`370-371`), emitted via `get_health_data()` (`727`) and `/health` (`health_check.py:328-331`). Tests verify monotonic persistence across reset (`tests/test_health_check.py:3148-3161`). |
| 8 | `reset_window()` publishes a completed-window snapshot before zeroing live state, preserves pre-existing zeroing semantics, and keeps its int return type. | ✓ VERIFIED | `reset_window()` stores `count = self._window_suppressions`, snapshots sum and by-cause dict, zeros legacy and per-cause live counters, updates timestamp/congestion flag, and returns `count` (`queue_controller.py:690-706`). Tests assert return is int and snapshot values survive (`tests/test_queue_controller.py:2777-2811`). |
| 9 | `/health.wans[].upload.hysteresis` and `/health.wans[].download.hysteresis` each contain `suppressions_completed_window_count`, `suppressions_completed_window_by_cause`, and `suppressions_lifetime_by_cause`. | ✓ VERIFIED | Common hysteresis builder copies all three keys before direction-specific additions (`health_check.py:309-331`), so upload/download are symmetric. Exact key-set test verifies upload and download (`tests/test_health_check.py:2870-2891`). |
| 10 | Active v1.43 docs/planning references use the canonical archived fixture path. | ✓ VERIFIED | `.planning/REQUIREMENTS.md:17` and `.planning/ROADMAP.md:47` both point to `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/soak-capture.ndjson`. |
| 11 | SAFE-07 cross-cutting invariant: Phase 202 is additive metric/schema/test/docs work only; no controller tuning. | ✓ VERIFIED | `git diff -- src/wanctl/wan_controller.py` returned empty. Code changes in `queue_controller.py` are additive counter/schema instrumentation; no threshold/rate tuning values changed. Full test suite passed: `4940 passed, 6 skipped, 2 deselected`. |

**Score:** 11/11 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/wanctl/queue_controller.py` | Counter attributes, `_record_suppression(cause)`, callsite tagging, reset snapshot publish, health-data emission | ✓ VERIFIED | Exists and substantive. Wired internally by all three source callsites and `get_health_data()`; no hollow data path. |
| `src/wanctl/health_check.py` | `_build_rate_hysteresis_section` copies new keys through to `/health` for upload/download | ✓ VERIFIED | Exists and substantive. Common builder copies new keys from `qc.get_health_data()` with fallbacks; upload/download routes call same builder. |
| `tests/test_queue_controller.py` | Unit tests for helper, callsite tagging, reset semantics, legacy counter preservation | ✓ VERIFIED | Phase 202 test class covers helper, unknown cause, dwell-hold, 3-state/4-state backlog recovery, reset snapshot, initial state. |
| `tests/test_health_check.py` | Exact key sets and `/health` symmetry tests | ✓ VERIFIED | Exact upload/download key tests and Phase 202 schema tests present. |
| `tests/test_phase_202_replay.py` | METRIC-03 oracle test + synthetic reset snapshot tests | ✓ VERIFIED | Exists with helper, oracle, synthetic trace classes; canonical fixture wired. |
| `tests/test_phase_195_replay.py` | SAFE-05 v1.43 pin extension | ✓ VERIFIED | `phase202_expected_counts` present and passing. |
| `CHANGELOG.md` | v1.43-dev additive field documentation | ✓ VERIFIED | Top-level v1.43-dev entry documents fields and warning. |
| `docs/CONFIGURATION.md` | Suppression metric semantics section | ✓ VERIFIED | Contains required field table, cause taxonomy, per-cycle note, watchdog warning, fixture pointer. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| Dwell-hold callsite | `_record_suppression("dwell_hold")` | Additive call after legacy `_window_suppressions += 1` | ✓ WIRED | `queue_controller.py:388-390`; preserves legacy `suppressions_per_min`. |
| 3-state backlog-recovery callsite | `_record_suppression("backlog_recovery")` | Additive call after `_backlog_suppressed_this_cycle = True` | ✓ WIRED | `queue_controller.py:274-276`; does not increment legacy `_window_suppressions`. |
| 4-state backlog-recovery callsite | `_record_suppression("backlog_recovery")` | Additive call after `_backlog_suppressed_this_cycle = True` | ✓ WIRED | `queue_controller.py:639-641`; does not increment legacy `_window_suppressions`. |
| `reset_window()` | `_last_completed_window_total` / `_last_completed_window_by_cause` | Snapshot before zeroing live state | ✓ WIRED | `queue_controller.py:696-704`; tests assert snapshot and zeroing behavior. |
| `QueueController.get_health_data()` | `HealthCheckHandler._build_rate_hysteresis_section()` | `qc.get_health_data()["hysteresis"]` copied into `/health` | ✓ WIRED | `health_check.py:300-331`; both upload and download sections call this builder (`250-255`). |
| `tests/test_phase_202_replay.py::SOAK_CAPTURE_NDJSON` | Archived v1.42 soak fixture | Path constant under `.planning/milestones/v1.42-phases/...` | ✓ WIRED | `tests/test_phase_202_replay.py:22-32`; oracle test opens this path. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `queue_controller.py` | `_window_suppressions_by_cause` | `_record_suppression()` calls from actual dwell/backlog suppression branches | Yes | ✓ FLOWING |
| `queue_controller.py` | `_last_completed_window_total`, `_last_completed_window_by_cause` | `reset_window()` at the existing 60s boundary | Yes | ✓ FLOWING |
| `queue_controller.py` | `_lifetime_suppressions_by_cause` | Monotonic increments in `_record_suppression()` | Yes | ✓ FLOWING |
| `health_check.py` | `/health.wans[].{upload,download}.hysteresis.*` | `qc.get_health_data()` from live QueueController instances | Yes | ✓ FLOWING |
| `tests/test_phase_202_replay.py` | `window_counts` | Real archived `soak-capture.ndjson` `suppressions_per_min` column | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase 202 replay oracle and SAFE-05 pins pass | `.venv/bin/pytest tests/test_phase_202_replay.py tests/test_phase_195_replay.py -q` | `34 passed in 1.92s` | ✓ PASS |
| Hot-path regression slice passes | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` | `667 passed in 42.97s` | ✓ PASS |
| Full regression suite passes | `.venv/bin/pytest tests/ -q` | `4940 passed, 6 skipped, 2 deselected in 188.73s` | ✓ PASS |
| Replay oracle computes codex values from fixture | Python spot-check using `aggregate_completed_windows()` | `84117 1331 13.890308039068369 41.0 124` | ✓ PASS |
| `wan_controller.py` remains untouched for SAFE-07 | `git diff -- src/wanctl/wan_controller.py` | no output | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| METRIC-01 | 202-01 | Operator can read completed-window UL suppression counts alongside preserved `suppressions_per_min`. | ✓ SATISFIED | New completed-window key emitted through `QueueController.get_health_data()` and `/health`; legacy live counter remains separate. |
| METRIC-02 | 202-01 | Suppressions decomposed by cause: `dwell_hold`, `backlog_recovery`, `other`; surfaced as additive `/health` fields. | ✓ SATISFIED | `_record_suppression()` and all three source callsites verified; per-cause completed-window and lifetime dicts emitted. |
| METRIC-03 | 202-02 | Replay test confirms completed-window counts match codex re-aggregation values from v1.42 fixture. | ✓ SATISFIED | Test file and spot-check verify mean `13.8903`, p95 `41`, max `124`. |
| METRIC-04 | 202-03 | SAFE-05 v1.43 occurrence pins established; existing pins unchanged. | ✓ SATISFIED | `phase202_expected_counts` present with empirical counts; replay pin test passes. |
| METRIC-05 | 202-04 | Changelog and configuration docs document additive `/health` fields and metric semantics. | ✓ SATISFIED | `CHANGELOG.md:8-25`, `docs/CONFIGURATION.md:294-317`. |
| SAFE-07 | Cross-cutting | No controller tuning in v1.43; no control-path knob changes. | ✓ SATISFIED | No `wan_controller.py` diff; Phase 202 code changes are additive counters/schema; full test suite passed. |

No orphaned Phase 202 requirements found: REQUIREMENTS.md maps METRIC-01..05 to Phase 202 and SAFE-07 cross-cutting; OBSV/CALIB requirements are assigned to later phases.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/wanctl/**` | various | Broad scan found existing `return []` / fallback/no-op patterns in unrelated modules | ℹ️ Info | Not Phase 202 stubs. Phase-touched source files contain substantive counter/schema logic, tests, and no placeholder implementation blocking the goal. |

### Human Verification Required

None. Phase 202 is additive code/schema/test/docs work; production canary is explicitly not required by the roadmap. Automated tests and code/data-flow inspection are sufficient for this phase goal.

### Gaps Summary

No blocking gaps found. Phase 202 achieved the roadmap goal: completed-window suppression counters and per-cause decomposition are implemented, wired into `/health`, mechanically pinned against the v1.42 oracle, protected by SAFE-05 occurrence pins, documented for operators, and shipped without controller tuning.

---

_Verified: 2026-05-06T21:31:58Z_
_Verifier: the agent (gsd-verifier)_
