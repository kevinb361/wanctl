---
phase: 204
slug: d-14-successor-recalibration-calib
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-06
audited: 2026-05-09
---

# Phase 204 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `pyproject.toml [tool.pytest.ini_options]` |
| **Quick run command** | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` |
| **Phase-scoped slice** | `.venv/bin/pytest tests/test_phase_204_replay.py tests/test_phase_204_watchdog.py tests/test_phase_204_distribution.py tests/test_phase_203_replay.py tests/test_phase_203_capture_projection.py tests/test_phase_202_replay.py tests/test_phase_195_replay.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -q` |
| **Estimated runtime** | quick ~41s · phase-scoped ~12s · full ~224s |

---

## Sampling Rate

- **After every task commit:** Run the task-specific acceptance command plus SAFE-07 source diff; for closeout metadata, rerun the hot-path slice.
- **After every plan wave:** Run phase-scoped slice.
- **Before `/gsd-verify-work`:** SAFE-07 checklist green, phase-scoped slice green, and full suite green.
- **Max feedback latency:** ~45 seconds for hot-path slice; full closeout suite intentionally longer.

---

## Per-Task Verification Map

> Populated by gsd-planner. Each task references the plan + wave + REQ-ID + automated command.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 204-01 | 01 | 1 | CALIB-01, SAFE-07 | T-204-01 deploy gate | Deploy 1 changes only approved version surfaces; SAFE-07 helper permits exact planned version bump only | scripted diff + smoke + hot-path | `bash scripts/check-safe07-source-diff.sh` and hot-path slice | ✅ | ✅ green |
| 204-02 | 02 | 2 | CALIB-01 | T-204-02 soak evidence integrity | CALIB-01 capture quality documented; distribution generated from committed NDJSON; line-count proxy deviation operator-accepted with stronger quality checks | unit + replay + artifact checks | `.venv/bin/pytest tests/test_phase_204_distribution.py tests/test_phase_203_replay.py tests/test_phase_202_replay.py -v` | ✅ | ✅ green |
| 204-03 | 03 | 3 | CALIB-02 | T-204-03 approval tampering | Operator-readable approval artifact and JSON mirror agree on statistic, threshold, headroom, rounding, and gate column | artifact/JSON grep + SAFE-07 | JSON/artifact mirror check and `bash scripts/check-safe07-source-diff.sh` | ✅ | ✅ green |
| 204-04 | 04 | 4 | CALIB-03, SAFE-07 | T-204-04 watchdog regression | Dual-emission watchdog preserves legacy oracle while adding completed-window gate from operator-approved constants | unit + replay + diff | `.venv/bin/pytest tests/test_phase_204_watchdog.py tests/test_phase_204_replay.py ... -q` | ✅ | ✅ green |
| 204-05 | 05 | 5 | CALIB-04, SAFE-07 | T-204-05 production soak evidence | CALIB-04 verdict uses primary floor-hit delta plus completed-window secondary gate; legacy gate informational only | artifact + jq + hot-path | dual-gate jq, `bash scripts/check-safe07-source-diff.sh`, hot-path slice | ✅ | ✅ green |
| 204-06 | 06 | 6 | CALIB-05, SAFE-07 | T-204-06 closeout tampering/repudiation | Closeout artifacts record requirements, checklist results, RETRO lesson, and milestone state; no `src/wanctl/` files touched | scripted diff + pytest + artifact grep | SAFE-07 four-command checklist plus full suite | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

> Existing test infrastructure (`pytest`, `tests/test_phase_195_replay.py`, `scripts/soak_summary_aggregate.py` replay tests) covers the Phase 204 surface. New fixtures landed during execution:
- [x] Replay fixture/test coverage for `aggregate_watchdog()` legacy-vs-new dual emission (CALIB-03): `tests/test_phase_204_watchdog.py`, `tests/test_phase_204_replay.py`, and refreshed synthetic summary fixtures.
- [x] Distribution-analysis test against synthetic CALIB-01 NDJSON (CALIB-01): `tests/test_phase_204_distribution.py` plus `tests/fixtures/phase_204_synthetic_*`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 24h Spectrum baseline soak (CALIB-01) | CALIB-01 | Production wall-clock + operator acceptance of capture quality | Completed in Plan 204-02 at `20260507T131911Z`; top-level p99 `82.0`, dwell-hold p99 `70.25999999999999`; line-count proxy miss accepted with stronger quality checks. |
| Operator approval signature on threshold | CALIB-02 | Human judgment locks the number | Completed in Plan 204-03: `statistic=p99`, `threshold=125`, `headroom_factor=1.5`, `gate_column=by_cause.dwell_hold`. |
| Two-snapshot rollback drill / deploy boundary | SAFE-07 (cross-cutting) | Production deploy on cake-shaper | Deploy 1 completed with two-snapshot rollback evidence; Deploy 2 was harness-only by design; closeout SAFE-07 source diff returned clean. |
| 24h verification soak dual gate (CALIB-04) | CALIB-04 | Production wall-clock | Completed in Plan 204-05 at `20260508T161146Z`: `primary_gate.delta=0`, `secondary_gate_completed_window.value=68.0 <= 125`, verdict `pass`. |
| RETRO threshold-basis hygiene lesson | CALIB-05 | Durable lesson quality is a closeout/document judgment | Completed in Plan 204-06: `204-RETRO.md` Key Lesson #1 contains the literal phrase `threshold-basis hygiene`. |

---

## Validation Sign-Off

- [x] All tasks have automated verify, artifact checks, or documented manual-only production/operator evidence.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all MISSING references; Phase 204 distribution/watchdog/replay tests and fixtures exist.
- [x] No watch-mode flags.
- [x] Feedback latency < 60s for hot-path/task slices; full closeout suite intentionally longer.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** validated 2026-05-09 — Phase 204 is Nyquist-compliant. Manual-only production/operator items are explicitly carved out and backed by committed soak, approval, verdict, verification, and retrospective artifacts.

---

## Validation Audit 2026-05-09

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Already covered | 6 (CALIB-01..05 + SAFE-07) |

**Audit notes:**

- SAFE-07 closeout source diff passed: `SAFE-07 OK: only planned src/wanctl/__init__.py version bump vs b72b463`.
- SAFE-05 pin block passed: `1 passed, 24 deselected`.
- Hot-path slice passed: `667 passed in 41.21s`.
- Phase-scoped slice passed: `70 passed in 12.39s`.
- Full suite passed: `4976 passed, 6 skipped, 2 deselected in 223.81s`.
- CALIB-01 and CALIB-04 line-count proxy misses are operator-accepted manual evidence-quality carve-outs with stronger quality checks, matching the Phase 202/203 validation model for manual-only items.
