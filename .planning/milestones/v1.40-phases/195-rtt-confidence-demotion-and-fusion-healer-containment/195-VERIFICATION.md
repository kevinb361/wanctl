---
phase: 195-rtt-confidence-demotion-and-fusion-healer-containment
verified: 2026-04-24T18:47:14Z
status: passed
score: 13/13 must-haves verified
overrides_applied: 0
production_verification:
  window_start: 2026-04-24T17:45:49Z
  window_end: 2026-04-24T18:45:44Z
  health_samples_per_wan: 360
  health_sample_errors: 0
  raw_health_sample_path: /tmp/wanctl-phase195/phase195-health-samples.jsonl
  canary: passed
---

# Phase 195: RTT Confidence Demotion and Fusion-Healer Containment Verification Report

**Phase Goal:** Introduce `rtt_confidence`, gate DL RTT override behind confidence plus direction agreement, contain fusion-healer bypass behind 6 aligned distress cycles, prevent single-path bypasses, and avoid magnitude-ratio/state-machine/timing/threshold/rate-compute changes.
**Verified:** 2026-04-24T18:47:14Z
**Status:** passed
**Re-verification:** Yes - production UAT completed after the initial `human_needed` result.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | SC-1 production `rtt_confidence` is observed in `/health` and SQLite over a 1-hour cake-signal window | VERIFIED | cake-shaper health collection from `2026-04-24T17:45:49Z` to `2026-04-24T18:45:44Z`: 360 samples per WAN, zero errors, all healthy, health confidence range `0.0..1.0`; SQLite rows over the same window: spectrum 70,344 and ATT 70,387 `wanctl_rtt_confidence` rows, each min `0.0`, max `1.0`. |
| 2 | SC-2 production low-confidence queue-GREEN RTT spike does not emit `rtt_veto` | VERIFIED | SQLite cycle reconstruction found queue-GREEN, low-confidence RTT spikes where `active_primary=1.0` queue: spectrum `2026-04-24T18:09:03Z` with confidence `0.0`, queue `2us`, RTT delta `210.74ms`; ATT `2026-04-24T18:39:33Z` with confidence `0.0`, queue `194us`, RTT delta `10.84ms`. |
| 3 | SC-3 production single-path flip does not enter `healer_bypass` | VERIFIED | Journal recorded protocol-deprioritization events after restart, including spectrum ratio `0.62` and ATT ratio flips `0.23..1.52`; health samples showed `fusion_bypass_active=false` and reason `None` for all 720 samples; SQLite `wanctl_fusion_bypass_active` max was `0.0` for both WANs. |
| 4 | SC-4 Spectrum 2026-04-23 replay avoids phantom RTT bloat and healer bypass | VERIFIED | `tests/test_phase_195_replay.py:537` and `:566`; replay lineage passed `48 passed, 6 skipped`. |
| 5 | Controller derives `rtt_confidence` in `[0.0, 1.0]` from ICMP/UDP agreement and queue/RTT direction | VERIFIED | `_derive_rtt_confidence` at `src/wanctl/wan_controller.py:2642`; tests at `tests/test_wan_controller.py:3249`. |
| 6 | `rtt_confidence` is `None` when no valid queue snapshot exists | VERIFIED | `_run_congestion_assessment` sets `None` at `src/wanctl/wan_controller.py:2747`; focused tests passed. |
| 7 | `/health` and SQLite metric paths surface live confidence without sentinel rows | VERIFIED | `get_health_data` at `src/wanctl/wan_controller.py:4155`, metric append at `:3079`, renderer pass-through at `src/wanctl/health_check.py:781`. |
| 8 | Queue-primary distress remains authoritative | VERIFIED | Selector returns queue distress before veto at `src/wanctl/wan_controller.py:2694`; tests cover queue-distress authority. |
| 9 | RTT veto fires only for queue-GREEN, confidence `>= 0.6`, agreeing non-unknown directions, and RTT YELLOW+ | VERIFIED | Gate at `src/wanctl/wan_controller.py:2697-2706`; `TestPhase195RttVetoGate` passed. |
| 10 | Fusion bypass enters only after 6 aligned queue+RTT distress cycles | VERIFIED | Streak/gate at `src/wanctl/wan_controller.py:2772-2799`; `TestPhase195HealerBypass` and replay tests passed. |
| 11 | Single-path flips never bypass | VERIFIED | `tests/test_phase_195_replay.py:537`; `tests/test_wan_controller.py:3060`; replay and focused slices passed. |
| 12 | No queue-us/RTT-ms magnitude ratio, and UL/state-machine/timing/threshold/rate-compute contracts hold | VERIFIED | Source guards found no `absolute_disagreement` or queue/RTT ratio; no diff in `queue_controller.py`, `cake_signal.py`, or `fusion_healer.py`; full slice passed. |
| 13 | Post-review WR-01 stale fusion fallback expectation is fixed | VERIFIED | Commit `14b0343`; `tests/test_fusion_healer.py:831` asserts filtered RTT without bypass; `109 passed`. |

**Score:** 13/13 truths verified.

### Production UAT Evidence

Phase 195 was deployed code-only to cake-shaper by syncing `src/wanctl/` to
`/opt/wanctl`, preserving production YAML and systemd units. The deployed files
contained Phase 195 markers (`ARBITRATION_REASON_HEALER_BYPASS`,
`_derive_rtt_confidence`, `queue_rtt_aligned_distress`,
`wanctl_rtt_confidence`). `wanctl@spectrum.service` and `wanctl@att.service`
were restarted at 2026-04-24 12:44:27 CDT.

Post-restart canary:

```text
spectrum autorate: pass
att autorate: pass
steering: pass
```

One-hour health collection:

```text
path: /tmp/wanctl-phase195/phase195-health-samples.jsonl
window: 2026-04-24T17:45:49Z to 2026-04-24T18:45:44Z
spectrum: 360 samples, 0 errors, all healthy
att: 360 samples, 0 errors, all healthy
```

SQLite confidence rows over the same window:

| WAN | Rows | Min | Max | Avg |
|---|---:|---:|---:|---:|
| spectrum | 70,344 | 0.0 | 1.0 | 0.0410 |
| att | 70,387 | 0.0 | 1.0 | 0.0316 |

Low-confidence RTT spike trace examples:

| WAN | UTC Time | rtt_confidence | queue_delta_us | rtt_delta_ms | active_primary | fusion_active |
|---|---|---:|---:|---:|---:|---:|
| spectrum | 2026-04-24T18:09:03Z | 0.0 | 2.0 | 210.74 | 1.0 queue | 0.0 |
| att | 2026-04-24T18:39:33Z | 0.0 | 194.0 | 10.84 | 1.0 queue | 0.0 |

Single-path flip / bypass evidence:

- Journal after restart contained protocol-deprioritization events, including
  spectrum ICMP/UDP ratio `0.62` and ATT ratio flips from `0.23` to `1.52`.
- Filtered journal had no `healer_bypass`, `queue_rtt_aligned`, or `rtt_veto`
  entries.
- Health samples reported `fusion_bypass_active=false`,
  `fusion_bypass_reason=None` for all 720 samples.
- SQLite `wanctl_fusion_bypass_active` max was `0.0` for both WANs.
- `journalctl -p err` for both WAN services since the Phase 195 restart
  returned 0 entries.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/wanctl/wan_controller.py` | Confidence helpers, RTT veto, healer streak gate, health/metric wiring | VERIFIED | Constants/helpers/stashes, selector, gate, and metrics are present and wired. |
| `src/wanctl/health_check.py` | `signal_arbitration.rtt_confidence` pass-through renderer | VERIFIED | Renderer returns `arb.get("rtt_confidence")`; docstring reflects live Phase 195 source. |
| `tests/test_wan_controller.py` | Unit coverage for confidence, veto, healer bypass, UL guards | VERIFIED | Focused slice passed `64 passed, 306 deselected`. |
| `tests/test_health_check.py` | Renderer pass-through for `0.0`, `0.5`, `1.0`, `None` | VERIFIED | `test_phase195_renderer_passes_rtt_confidence_through` at line 4488. |
| `tests/test_phase_195_replay.py` | Replay harness for ARB-02, ARB-03, SAFE-05, Spectrum event | VERIFIED | Manual check verified `SPECTRUM_2026_04_23_TRACE`; gsd-tools' mixed-case pattern check was a false negative. |
| `tests/test_phase_194_replay.py` | Superseded Phase 194 negative `rtt_veto` assertion | VERIFIED | Test is retained and skipped with explicit Phase 195 pointer at line 516. |
| `tests/test_fusion_healer.py` | Updated WR-01 fallback expectation | VERIFIED | Large ICMP/IRTT disagreement now asserts no bypass activation. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `_run_congestion_assessment` | `_last_rtt_confidence`, directions, and previous raw deltas | Raw queue/RTT deltas captured before selector | VERIFIED | Lines `2728-2756` compute and stash current-cycle confidence before arbitration. |
| `_select_dl_primary_scalar_ms` | `ARBITRATION_REASON_RTT_VETO` | Confidence, direction agreement, RTT YELLOW+ gate | VERIFIED | Lines `2697-2706`; queue distress returns first. |
| `_run_congestion_assessment` | Fusion bypass state | `_healer_aligned_streak >= 6` | VERIFIED | Lines `2772-2799`; sets `queue_rtt_aligned_distress` and `healer_bypass`. |
| `_compute_fused_rtt` | Phase 195 bypass driver | Fusion math records offset only | VERIFIED | Lines `1718-1720`; source has no `absolute_disagreement` literal. |
| `WANController.get_health_data` | `/health.signal_arbitration.rtt_confidence` | `getattr(self, "_last_rtt_confidence", None)` | VERIFIED | Line `4155`; `health_check.py` passes it through unchanged. |
| `_run_logging_metrics` | `wanctl_rtt_confidence` row | `_append_rtt_confidence_metric` only when non-None | VERIFIED | Lines `3028`, `3079-3088`; tests cover emit and skip. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `wan_controller.py` | `_last_rtt_confidence` | Raw queue delta, raw RTT delta, `_irtt_correlation`, `_derive_rtt_confidence` | Yes | FLOWING |
| `health_check.py` | `signal_arbitration.rtt_confidence` | `WANController.get_health_data()` | Yes | FLOWING |
| SQLite metrics path | `wanctl_rtt_confidence` | `_append_rtt_confidence_metric` gated on non-None confidence | Yes | FLOWING |
| Fusion bypass fields | `_fusion_bypass_active`, `_fusion_bypass_reason` | 6-cycle aligned distress gate | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Phase 195 focused controller/health behavior | `.venv/bin/pytest -o addopts='' tests/test_wan_controller.py tests/test_health_check.py -q -k "rtt_confidence or arbitration or signal_arbitration or healer_bypass or phase195"` | `64 passed, 306 deselected` | PASS |
| Replay lineage | `.venv/bin/pytest -o addopts='' tests/test_phase_193_replay.py tests/test_phase_194_replay.py tests/test_phase_195_replay.py -q` | `48 passed, 6 skipped` | PASS |
| Post-review fusion fallback test | `.venv/bin/pytest -o addopts='' tests/test_fusion_healer.py -q` | `109 passed` | PASS |
| Full hot-path plus fusion slice | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py tests/test_phase_193_replay.py tests/test_phase_194_replay.py tests/test_phase_195_replay.py tests/test_fusion_healer.py -q` | `719 passed, 6 skipped` | PASS |
| Lint | `.venv/bin/ruff check ...` | `All checks passed!` | PASS |
| Type check | `.venv/bin/mypy src/wanctl/wan_controller.py src/wanctl/health_check.py` | `Success: no issues found in 2 source files` | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| ARB-02 | `195-02`, `195-03` | RTT only overrides queue-GREEN through confidence and direction agreement | SATISFIED | Selector gate, automated tests, replay coverage, and production SQLite traces verify low-confidence RTT spikes stayed queue-primary. |
| ARB-03 | `195-02`, `195-03` | Healer bypass only after 6 aligned queue+RTT distress cycles; single-path flips never bypass; no magnitude ratio | SATISFIED | Streak gate, no literal `absolute_disagreement`, no ratio matches, replay coverage, and production protocol-deprioritization traces with no bypass. |
| SAFE-05 | `195-01`, `195-02`, `195-03` | No state-machine, EWMA, dwell, deadband, burst, threshold, or rate-compute changes | SATISFIED | Source guards clean; no changes in `queue_controller.py`, `cake_signal.py`, or `fusion_healer.py`; full tests pass. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| `src/wanctl/wan_controller.py` | 3097 | `return {}` | Info | Existing fallback for unavailable Linux CAKE write timings; not a Phase 195 stub and not user-visible. |

### Human Verification Completed

### 1. SC-1 Production Confidence Observation

**Test:** Run a cake-signal-supported WAN for at least 1 hour and capture `/health` plus SQLite metric rows for `wanctl_rtt_confidence`.
**Expected:** `rtt_confidence` is a non-null float in `[0.0, 1.0]` on valid queue-snapshot cycles and tracks protocol/direction agreement.
**Result:** Passed. cake-shaper health collection produced 360 samples per WAN with zero errors; SQLite contained non-null `wanctl_rtt_confidence` rows for the same window with values in `[0.0, 1.0]`.

### 2. SC-2 Low-Confidence RTT Spike Trace

**Test:** Capture or replay against production telemetry where queue remains GREEN while RTT spikes and `rtt_confidence < 0.6`.
**Expected:** `control_decision_reason != "rtt_veto"` and DL zone transitions do not escalate due to RTT in that window.
**Result:** Passed. Production SQLite traces show queue-GREEN, low-confidence RTT spikes on both WANs with `active_primary=1.0` queue.

### 3. SC-3 Single-Path Flip Trace

**Test:** Capture a single-path ICMP/IRTT flip with queue GREEN for at least 6 cycles.
**Expected:** `control_decision_reason` never shows `healer_bypass`; fusion bypass remains inactive.
**Result:** Passed. Production journal recorded protocol-deprioritization events; health and SQLite evidence show fusion bypass stayed inactive.

### Gaps Summary

No implementation or production verification gaps remain. The phase goal is achieved in the codebase, covered by automated tests, and backed by the one-hour production evidence recorded in this report and `195-HUMAN-UAT.md`.

---

_Verified: 2026-04-24T18:47:14Z_
_Verifier: Codex (gsd-verifier)_
