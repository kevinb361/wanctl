---
phase: 197
slug: queue-primary-refractory-semantics-split-dl-cake-for-detecti
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-27
reconstructed_from: SUMMARY.md (State B — VALIDATION.md not produced during execution)
---

# Phase 197 — Validation Strategy

> Per-phase validation contract reconstructed from completed-phase artifacts (197-01-PLAN.md, 197-02-PLAN.md, 197-VERIFICATION.md, and the live test tree). Every plan-frontmatter `must_haves.truth` is mapped to at least one green automated test that would fail if the truth regressed.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (declared in `pyproject.toml`) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `.venv/bin/pytest -o addopts='' tests/test_phase_197_replay.py -q` |
| **Hot-path slice** | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` |
| **Phase-197 + dependents** | `.venv/bin/pytest -o addopts='' tests/test_phase_197_replay.py tests/test_wan_controller.py tests/test_health_check.py -q` |
| **Static-script gate** | `bash -n scripts/phase196-soak-capture.sh` |
| **Lint / type** | `.venv/bin/ruff check src/ tests/` · `.venv/bin/mypy src/wanctl/` |
| **Estimated runtime (phase slice)** | ~40s (392 tests, observed 39.30s on 2026-04-27) |

---

## Sampling Rate

- **After every task commit:** quick run command above (replay file alone, ~0.5s).
- **After every plan wave:** Phase-197 + dependents command (392 tests, ~40s).
- **Before `/gsd-verify-work`:** hot-path regression slice green + replay battery green (`tests/test_phase_193_replay.py tests/test_phase_194_replay.py tests/test_phase_197_replay.py`).
- **Max feedback latency:** ~40s.

---

## Per-Task Verification Map

Plan frontmatter declared no REQ-IDs (`requirements: []` in both 197-01 and 197-02). The contract is the `must_haves.truths` block. Each truth is mapped below.

### Plan 197-01 — Split-locals refractory semantics

| Task ID | Wave | Truth / Behavior | Threat Ref | Test Type | Test Function(s) | File Exists | Status |
|---------|------|------------------|------------|-----------|------------------|-------------|--------|
| 197-01-T1 | 1 | Reason constants + stash + split locals + selector branches in `wan_controller.py` | T-197-01 (control-flow integrity) | unit (selector + state) | `tests/test_wan_controller.py::test_get_health_data_signal_arbitration_shape`, `..._relays_queue_primary` | ✅ | ✅ green |
| 197-01-T2 | 2 | `health_check.py` renderer surfaces `refractory_active` (default False, verbatim relay) | T-197-04 (health-shape contract) | unit (renderer) | `tests/test_health_check.py::test_refractory_active_relayed_when_controller_sets_true`, `test_refractory_active_defaults_false_when_controller_omits` | ✅ | ✅ green |
| 197-01-T3 | 3 | Replay harness: byte-identity outside refractory, queue-primary during refractory with valid snapshot, RTT fallback with invalid snapshot, no detection cascade, RTT-veto unreachable | T-197-02, T-197-03, T-197-05 | replay + integrated | `tests/test_phase_197_replay.py::TestPhase197NonRefractoryByteIdentity`, `TestPhase197IntegratedNonRefractoryByteIdentity`, `TestPhase197RefractoryQueueArbitration`, `TestPhase197RTTFallbackDuringRefractory`, `TestPhase197NoCascadeOnDetection` | ✅ | ✅ green (12 passed in 0.41s) |

### Plan 197-02 — Metric, healer-bypass guard, audit predicate

| Task ID | Wave | Truth / Behavior | Threat Ref | Test Type | Test Function(s) | File Exists | Status |
|---------|------|------------------|------------|-----------|------------------|-------------|--------|
| 197-02-T1 | 1 | `wanctl_arbitration_refractory_active` emitted DL-only as 1.0/0.0 sourced from `_dl_arbitration_used_refractory_snapshot`; UL block byte-identical | T-197-08, T-197-13 | unit (metric emission) | `tests/test_wan_controller.py::test_dl_metrics_emit_refractory_active_one_when_stash_true`, `..._zero_when_stash_false`, `test_ul_metrics_byte_identical_after_phase_197_metric_addition` | ✅ | ✅ green |
| 197-02-T2 | 2 | Refractory entry atomically resets `_healer_aligned_streak`; refractory window suppresses streak increment; RTT-veto branch unreachable during refractory | T-197-09 (cascading control elevation) | integrated | `tests/test_phase_197_replay.py::TestPhase197HealerBypassInteractions::test_streak_resets_on_refractory_entry`, `..._streak_does_not_increment_during_refractory`, `..._rtt_veto_unreachable_during_refractory` | ✅ | ✅ green |
| 197-02-T3 | 3 | Capture script extracts `refractory_active` and emits it in summary JSON; Phase 196 audit predicate document accepts Phase 197 reason vocabulary as queue-primary with regime-aware bucketing | T-197-10, T-197-11, T-197-12 | static + manual | `bash -n scripts/phase196-soak-capture.sh` (script syntax) + artifact-existence grep gates from plan `<verify>` block | ✅ | ✅ green (script) / 🟡 manual (predicate executes during next Spectrum cake-primary B-leg rerun) |

### Truths-to-Test crosswalk (12 must-have truths across both plans)

| # | Truth (paraphrased) | Test ID | Status |
|---|---------------------|---------|--------|
| 1 | Refractory + valid snapshot → `queue` / `queue_during_refractory` | `TestPhase197RefractoryQueueArbitration::test_refractory_window_keeps_queue_primary_with_valid_snapshot` | ✅ |
| 2 | Refractory + None/cold_start → `rtt` / `rtt_fallback_during_refractory` | `TestPhase197RTTFallbackDuringRefractory::test_rtt_fallback_during_refractory_when_snapshot_none` + `..._when_snapshot_cold_start` | ✅ |
| 3 | Outside refractory: integrated seam byte-identical to Phase 193/194 | `TestPhase197IntegratedNonRefractoryByteIdentity::test_integrated_seam_replay_byte_identical_to_phase_195` | ✅ |
| 4 | `download.adjust_4state` receives `cake_snapshot=None` for every refractory cycle | `TestPhase197NoCascadeOnDetection::test_detection_path_does_not_recascade_during_refractory` | ✅ |
| 5 | `/health` exposes `refractory_active` boolean defaulting False | `tests/test_wan_controller.py::test_get_health_data_signal_arbitration_shape` + `tests/test_health_check.py::test_refractory_active_defaults_false_when_controller_omits` | ✅ |
| 6 | RTT-veto branch unreachable during refractory | `TestPhase197HealerBypassInteractions::test_rtt_veto_unreachable_during_refractory` | ✅ |
| 7 | `wanctl_arbitration_refractory_active` = 1.0 when stash True | `test_dl_metrics_emit_refractory_active_one_when_stash_true` | ✅ |
| 8 | `wanctl_arbitration_refractory_active` = 0.0 when stash False | `test_dl_metrics_emit_refractory_active_zero_when_stash_false` | ✅ |
| 9 | Healer-streak resets on refractory entry (atomic with `_dl_refractory_remaining` set) | `test_streak_resets_on_refractory_entry` | ✅ |
| 10 | Streak does not increment during refractory window | `test_streak_does_not_increment_during_refractory` | ✅ |
| 11 | UL metric block byte-identical (no UL emission of new metric) | `test_ul_metrics_byte_identical_after_phase_197_metric_addition` | ✅ |
| 12 | Phase 196 audit predicate accepts `queue_during_refractory` and buckets `rtt_fallback_during_refractory + refractory_active=true` separately, with raw-only granularity filter | `bash -n` on capture script (automated) + Manual-Only entry below for the predicate's runtime application | 🟡 partial (static contract automated; runtime application manual) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky · 🟡 partial-automated*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements — pytest is already installed in `.venv`, `tests/test_phase_193_replay.py` (Phase 193) and `tests/test_phase_194_replay.py` (Phase 194) provided the reusable `integrated_controller` fixture, `_queue_snapshot`, `_prepare_queue_primary_controller`, `EXPECTED_ZONES`, and TRACE primitives that Phase 197 reused verbatim.

---

## Manual-Only Verifications

| Behavior | Truth Ref | Why Manual | Test Instructions |
|----------|-----------|------------|-------------------|
| Phase 196 cake-primary audit predicate correctly classifies a Phase-197-aware soak run | Truth #12 (audit predicate document `primary-signal-audit-phase197.md`) | The predicate is a markdown contract executed by jq during the Spectrum B-leg rerun on the same deployment token. Static existence + content tokens are auto-checked, but the predicate's correctness against live `/health` and SQLite metric rows can only be observed during a real soak. | 1. Deploy controller to `cake-shaper:wanctl@spectrum.service:/etc/wanctl/spectrum.yaml`. 2. Run `scripts/phase196-soak-capture.sh` for ≥24h with source-bind `10.10.110.226`. 3. Apply the jq predicate from `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/primary-signal-audit-phase197.md`. 4. Confirm: `non_queue` health samples ≤ documented threshold; `metric_queue_samples_via_refractory_rtt_fallback` is bucketed separately; `granularity = 'raw'` filter applied. 5. Compare to Phase 196 rtt-blend A-leg comparator. Throughput threshold: `tcp_12down >= 532 Mbps`. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify blocks (recorded in 197-01-PLAN.md and 197-02-PLAN.md `<verify>` sections)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (every task has either pytest, ruff, mypy, grep gates, or `bash -n`)
- [x] Wave 0 covers all MISSING references (none — phase reused Phase 193/194 fixtures verbatim)
- [x] No watch-mode flags (all commands are one-shot `pytest -q`)
- [x] Feedback latency < 60s (392-test phase slice runs in ~40s)
- [x] `nyquist_compliant: true` set in frontmatter
- [x] Independently re-verified by 197-VERIFICATION.md (11/11 truths) and 197-REVIEW.md / 197-SECURITY.md

**Approval:** approved 2026-04-27 (reconstructed from artifacts; no missing tests required)

---

## Validation Audit 2026-04-27

| Metric | Count |
|--------|-------|
| Truths in plan frontmatter | 12 |
| COVERED (green automated) | 11 |
| PARTIAL (static-automated, runtime-manual) | 1 (Truth #12) |
| MISSING | 0 |
| Tests generated this audit | 0 |
| Manual-only escalations | 1 (Phase 196 B-leg soak predicate execution) |

**Reconstruction note:** Phase 197 was executed without a VALIDATION.md being produced in-flight. This document was reconstructed in State B by mapping the `must_haves.truths` blocks of both plans to the test functions named in their `<verify>` and `<acceptance_criteria>` blocks, then re-running the live test tree (`392 passed in 39.30s`) on 2026-04-27 to confirm green status. No new tests were generated — full coverage existed at completion.
