---
phase: 187
slug: rtt-cache-and-fallback-safety
status: final
nyquist_compliant: true
wave_0_complete: true
finalized: 2026-04-15
created: 2026-04-15
---

# Phase 187 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/pytest -o addopts='' tests/test_rtt_measurement.py tests/test_wan_controller.py tests/test_health_check.py tests/test_autorate_error_recovery.py -q` |
| **Full suite command** | `.venv/bin/pytest -q` |
| **Estimated runtime** | ~30s quick / ~90s full |

---

## Sampling Rate

- **After every task commit:** Run quick run command (targeted hot-path slice)
- **After every plan wave:** Run quick run command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

> Planner will populate exact task IDs during step 8. Skeleton mapped to roadmap's 3 pre-defined plans.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 187-01-* | 01 | 1 | RTT-CACHE-01 | — | Zero-success cycle publishes explicit degraded status; `_last_raw_rtt_ts` not overwritten | unit | `.venv/bin/pytest tests/test_rtt_measurement.py::TestBackgroundRTTThread -q` | ✅ | ✅ green |
| 187-02-* | 02 | 2 | RTT-CACHE-02 | — | `measure_rtt()` overrides host lists on zero-success; SAFE-02 fallback path unchanged | unit | `.venv/bin/pytest tests/test_wan_controller.py::TestMeasureRTTNonBlocking tests/test_autorate_error_recovery.py -q` | ✅ | ✅ green |
| 187-03-* | 03 | 2 | RTT-CACHE-03 | — | Regression witnesses for zero-success, reduced quorum, and SAFE-02 non-regression | unit | `.venv/bin/pytest tests/test_health_check.py::TestMeasurementContract tests/test_rtt_measurement.py -q` | ✅ | ✅ green |

*Status: ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.* All target test files already exist (confirmed in RESEARCH.md): `tests/test_rtt_measurement.py`, `tests/test_wan_controller.py`, `tests/test_health_check.py`, `tests/test_autorate_error_recovery.py`. No new fixtures or framework installs needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Zero-success cycle during live DOCSIS upstream congestion does not drive phantom GREEN state | RTT-CACHE-02 | Requires real reflector collapse on production hardware | Soak on cake-shaper VM 206, induce reflector outage (iptables DROP egress to reflector hosts), confirm health endpoint reports `state="collapsed"` and controller does not raise rate |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** final — 2026-04-15 (aligned with 187-VERIFICATION.md passed/5-of-5)
