---
phase: 111-auto-tuning-production-hardening-config-bounds-sigp-01-rate-fix
verified: 2026-03-25T16:00:00Z
status: passed
score: 5/5 must-haves verified
re_verification: null
gaps: []
human_verification: []
---

# Phase 111: Auto-Tuning Production Hardening Verification Report

**Phase Goal:** Widen 4 tuning bounds stuck at limits and fix SIGP-01 outlier rate 60x underestimate from wrong denominator
**Verified:** 2026-03-25T16:00:00Z
**Status:** PASSED
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Spectrum tuning bounds allow target_bloat_ms down to 5, warn_bloat_ms down to 15, baseline_rtt_max down to 25 | VERIFIED | `configs/spectrum.yaml` lines 130, 133, 154: `min: 5.0`, `min: 15.0`, `min: 25.0` |
| 2 | ATT tuning bounds allow hampel_window_size up to 21 | VERIFIED | `configs/att.yaml` line 125: `max: 21` |
| 3 | MAX_WINDOW constant in signal_processing.py equals 21 | VERIFIED | `src/wanctl/tuning/strategies/signal_processing.py` line 51: `MAX_WINDOW = 21` |
| 4 | SIGP-01 outlier rate calculation uses actual time gap between consecutive timestamps, not fixed SAMPLES_PER_MINUTE | VERIFIED | Lines 114-128: `samples_per_sec = 1.0 / CYCLE_INTERVAL`, `time_gap = sorted_ts[i] - sorted_ts[i-1]`, `expected_samples = time_gap * samples_per_sec`; `SAMPLES_PER_MINUTE` absent from file (grep returns 0 matches) |
| 5 | Outlier rate is consistent regardless of recording interval (1s, 5s, 60s gaps) | VERIFIED | `TestHampelSigmaRecordingDensity::test_rate_consistent_across_recording_densities` parametrized at 1/5/60s all pass; 27/27 tests pass |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `configs/spectrum.yaml` | Widened Spectrum tuning bounds | VERIFIED | Contains `min: 5.0` (target_bloat_ms), `min: 15.0` (warn_bloat_ms), `min: 25.0` (baseline_rtt_max) |
| `configs/att.yaml` | Widened ATT hampel_window_size bound | VERIFIED | Contains `max: 21` at line 125 with correct comment |
| `src/wanctl/tuning/strategies/signal_processing.py` | Corrected SIGP-01 rate normalization and MAX_WINDOW=21 | VERIFIED | `MAX_WINDOW = 21` at line 51; time-gap-aware rate loop at lines 111-131; `SAMPLES_PER_MINUTE` fully removed |
| `tests/test_signal_processing_strategy.py` | Rate normalization tests at various recording densities plus MAX_WINDOW assertion | VERIFIED | `TestHampelSigmaRecordingDensity` (lines 125-196) and `TestMaxWindowAlignment` (lines 198-203) both present and passing |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `signal_processing.py` | `tune_hampel_sigma` rates computation | `time_gap * samples_per_sec` denominator using `CYCLE_INTERVAL` | WIRED | `samples_per_sec = 1.0 / CYCLE_INTERVAL` (line 114), `expected_samples = time_gap * samples_per_sec` (line 127), `rate = delta / max(expected_samples, 1.0)` (line 128). Plan pattern `time_gap.*CYCLE_INTERVAL` did not literal-match (intermediate variable used), but semantics are equivalent and correct. |
| `signal_processing.py` | `tune_hampel_window` interpolation ceiling | `MAX_WINDOW = 21` constant used at lines 217 and 225 | WIRED | `MAX_WINDOW = 21` defined at line 51; used in interpolation at lines 217 (`candidate = float(MAX_WINDOW)`) and 225 (`candidate = MAX_WINDOW - (MAX_WINDOW - MIN_WINDOW) * fraction`) |

### Data-Flow Trace (Level 4)

Not applicable. Changed artifacts are a config file and a strategy function -- neither renders dynamic data to UI. The "data flow" is the formula producing `TuningResult`, which is verified by passing unit tests at all three recording densities.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 27 tests pass (20 existing + 7 new) | `.venv/bin/pytest tests/test_signal_processing_strategy.py -v` | 27 passed in 0.14s | PASS |
| SAMPLES_PER_MINUTE fully removed | `grep -c "SAMPLES_PER_MINUTE" src/wanctl/tuning/strategies/signal_processing.py` | 0 | PASS |
| MAX_WINDOW = 21 in code | `grep "MAX_WINDOW = 21" src/wanctl/tuning/strategies/signal_processing.py` | 1 match (line 51) | PASS |
| mypy clean on changed file | `.venv/bin/mypy src/wanctl/tuning/strategies/signal_processing.py` | Success: no issues | PASS |
| Spectrum target_bloat_ms min=5.0 | `grep -A1 "target_bloat_ms:" configs/spectrum.yaml` | `min: 5.0` | PASS |
| Spectrum warn_bloat_ms min=15.0 | `grep -A1 "warn_bloat_ms:" configs/spectrum.yaml` | `min: 15.0` | PASS |
| Spectrum baseline_rtt_max min=25.0 | `grep -A1 "baseline_rtt_max:" configs/spectrum.yaml` | `min: 25.0` | PASS |
| ATT hampel_window_size max=21 | `grep -A1 "hampel_window_size:" configs/att.yaml` | `max: 21` | PASS |

### Requirements Coverage

Phase 111's requirements (SIGP-01-FIX, BOUNDS-SPECTRUM, BOUNDS-ATT) are defined only in `ROADMAP.md`. They are NOT listed in `.planning/REQUIREMENTS.md`, which exclusively tracks v1.21 CAKE Offload requirements (BACK-xx, CAKE-xx, CONF-xx, INFR-xx, CUTR-xx). This is expected: Phase 111 is a standalone production hardening fix outside the v1.21 CAKE Offload milestone scope. No orphaned requirements in REQUIREMENTS.md reference Phase 111.

| Requirement | Source | Description | Status | Evidence |
|-------------|--------|-------------|--------|----------|
| SIGP-01-FIX | ROADMAP.md only | Fix outlier rate 60x underestimate (wrong denominator) | SATISFIED | `SAMPLES_PER_MINUTE` removed; time-gap-aware formula in place; parametrized density tests pass at 1s/5s/60s intervals |
| BOUNDS-SPECTRUM | ROADMAP.md only | Widen 3 Spectrum tuning bounds pegged at floor | SATISFIED | `target_bloat_ms min=5.0`, `warn_bloat_ms min=15.0`, `baseline_rtt_max min=25.0` verified in `configs/spectrum.yaml` |
| BOUNDS-ATT | ROADMAP.md only | Widen ATT hampel_window_size bound pegged at ceiling | SATISFIED | `hampel_window_size max=21` in `configs/att.yaml`; `MAX_WINDOW=21` in code ensures interpolation reaches the new ceiling |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tests/test_signal_processing_strategy.py` | 14, 17 | ruff F401: `TuningResult` and `MIN_SAMPLES` imported but unused | Info | Pre-existing warnings present before Phase 111 (confirmed via git history). Documented in SUMMARY as out-of-scope per deviation rules. No functional impact; ruff F401 is fixable but not a blocker. |

No blocker anti-patterns. No TODO/FIXME/placeholder comments. No empty implementations. No hardcoded empty returns in changed code.

### Human Verification Required

None. All verifiable behaviors were confirmed programmatically:
- Config bound values are literal YAML numbers (inspectable by grep)
- Code constant `MAX_WINDOW = 21` is a literal (inspectable by grep)
- Rate normalization correctness proven by parametrized unit tests
- No UI rendering, no external services, no real-time behavior involved

### Gaps Summary

No gaps. All 5 observable truths verified. All 4 artifacts exist and are substantive. Both key links confirmed wired. Tests pass. mypy clean. Config changes applied to deployment files.

One minor note: the PLAN's `key_links[0].pattern` field specifies `time_gap.*CYCLE_INTERVAL` as a literal grep pattern, but the implementation uses an intermediate variable (`samples_per_sec = 1.0 / CYCLE_INTERVAL` then `expected_samples = time_gap * samples_per_sec`). The semantics are identical and the fix is correct -- the plan's pattern was an approximation of intent, not a literal grep requirement. This is not a gap.

---

_Verified: 2026-03-25T16:00:00Z_
_Verifier: Claude (gsd-verifier)_
