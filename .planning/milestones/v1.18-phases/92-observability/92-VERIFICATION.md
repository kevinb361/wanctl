---
phase: 92-observability
verified: 2026-03-17T12:06:10Z
status: gaps_found
score: 4/5 truths verified
gaps:
  - truth: "Full test suite passes with zero regressions"
    status: failed
    reason: "test_health_alerting.py::TestAutorateHealthAlerting has 3 failing tests due to missing MagicMock safety attributes on mock WAN controllers in that file"
    artifacts:
      - path: "tests/test_health_alerting.py"
        issue: "_make_wan_controller_mock() does not set _last_signal_result=None, _irtt_thread=None, _irtt_correlation=None, or irtt_config on mock controllers. New health_check.py code accesses these attributes, gets truthy MagicMock objects, and json.dumps() fails with TypeError: Object of type MagicMock is not JSON serializable"
    missing:
      - "Add these 4 lines to _make_wan_controller_mock() in tests/test_health_alerting.py: wan_controller._last_signal_result = None; wan_controller._irtt_thread = None; wan_controller._irtt_correlation = None; config.irtt_config = {'enabled': False}"
---

# Phase 92: Observability Verification Report

**Phase Goal:** Signal quality and IRTT data are visible in health endpoints and persisted in SQLite for trend analysis
**Verified:** 2026-03-17T12:06:10Z
**Status:** gaps_found
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | Health endpoint /health response contains signal_quality section per WAN with jitter_ms, variance_ms2, confidence, outlier_rate, total_outliers, warming_up | VERIFIED | health_check.py lines 191-201: `wan_health["signal_quality"]` dict with all 6 fields, rounded to 3dp |
| 2  | Health endpoint /health response contains irtt section per WAN with available flag and reason when disabled | VERIFIED | health_check.py lines 203-241: irtt section always present, `{"available": False, "reason": reason}` for disabled/binary_not_found |
| 3  | IRTT section shows full data fields when available | VERIFIED | health_check.py lines 227-241: rtt_mean_ms, ipdv_ms, loss_up_pct, loss_down_pct, server (host:port), staleness_sec, protocol_correlation |
| 4  | Signal quality and IRTT metrics are persisted to SQLite with correct deduplication | VERIFIED | autorate_continuous.py lines 1990-2008: metrics_batch.extend() for signal quality every cycle; IRTT only when timestamp != _last_irtt_write_ts |
| 5  | Full test suite passes with zero regressions | FAILED | tests/test_health_alerting.py::TestAutorateHealthAlerting - 3 tests fail with MagicMock JSON serialization error (1 failed, 1376 passed) |

**Score:** 4/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/wanctl/health_check.py` | signal_quality and irtt per-WAN health sections | VERIFIED | Lines 191-241: both sections implemented, 5-state IRTT model, conditional signal_quality pattern |
| `tests/test_health_check.py` | Tests for signal_quality and irtt health sections | VERIFIED | class TestSignalQualityHealth (line 836, 5 tests) + class TestIRTTHealth (line 1027, 7 tests), 42 total tests pass |
| `src/wanctl/storage/schema.py` | 8 new STORED_METRICS entries | VERIFIED | Lines 22-29: all 8 entries present; len(STORED_METRICS) == 18 confirmed by runtime check |
| `src/wanctl/autorate_continuous.py` | Signal quality and IRTT metrics batch extension in run_cycle() | VERIFIED | Lines 1352 (_last_irtt_write_ts init), 1990-2008 (metrics_batch.extend with dedup) |
| `tests/test_metrics_observability.py` | Tests for signal quality and IRTT SQLite persistence | VERIFIED | class TestSignalQualityMetrics (line 22) + class TestIRTTMetricsPersistence (line 193), 17 tests pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/wanctl/health_check.py` | `wan_controller._last_signal_result` | direct attribute access | WIRED | Line 192: `signal_result = wan_controller._last_signal_result`; None-guarded at line 193 |
| `src/wanctl/health_check.py` | `wan_controller._irtt_thread` | `get_latest()` call | WIRED | Line 204: `irtt_thread = wan_controller._irtt_thread`; line 213: `irtt_thread.get_latest()` |
| `src/wanctl/health_check.py` | `config.irtt_config` | dict `.get()` for enabled flag | WIRED | Line 206: `config.irtt_config.get("enabled", False)` |
| `src/wanctl/autorate_continuous.py` | `src/wanctl/storage/writer.py` | `write_metrics_batch()` call | WIRED | Line 2010: single `self._metrics_writer.write_metrics_batch(metrics_batch)` call after all extensions |
| `src/wanctl/autorate_continuous.py` | `_last_signal_result` | attribute access for metric values | WIRED | Line 1992: `sr = self._last_signal_result`; line 1994: `sr.jitter_ms` etc. |
| `src/wanctl/autorate_continuous.py` | `irtt_result.timestamp` | deduplication comparison | WIRED | Line 2001: `irtt_result.timestamp != self._last_irtt_write_ts`; line 2008: update after write |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| OBSV-01 | 92-01-PLAN.md | Health endpoint exposes signal quality section (jitter, confidence, variance, outlier count) | SATISFIED | health_check.py lines 194-201: all 6 signal_quality fields present and rounded |
| OBSV-02 | 92-01-PLAN.md | Health endpoint exposes IRTT measurement section (RTT, loss direction, IPDV, server status) | SATISFIED | health_check.py lines 203-241: 5-state model (disabled, binary_not_found, awaiting, full data, null correlation) |
| OBSV-03 | 92-02-PLAN.md | Signal quality metrics are persisted in SQLite for trend analysis | SATISFIED | autorate_continuous.py lines 1990-1998: 4 signal metrics in batch every cycle when _last_signal_result not None |
| OBSV-04 | 92-02-PLAN.md | IRTT metrics are persisted in SQLite for trend analysis | SATISFIED | autorate_continuous.py lines 2000-2008: 4 IRTT metrics with timestamp dedup, _last_irtt_write_ts tracks last write |

All 4 requirement IDs from both plans are accounted for. No orphaned requirements in REQUIREMENTS.md for Phase 92.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tests/test_health_alerting.py` | 108-135 | `_make_wan_controller_mock()` creates MagicMock without setting `_last_signal_result=None`, `_irtt_thread=None`, `_irtt_correlation=None`, or `irtt_config` on mock config | Blocker | `json.dumps()` in health endpoint fails with `TypeError: Object of type MagicMock is not JSON serializable` when MagicMock auto-creates these as truthy MagicMock attributes |

### Human Verification Required

None - all observable truths are programmatically verifiable.

### Gaps Summary

The phase goal is substantively achieved: signal_quality and irtt sections are correctly implemented in the health endpoint (OBSV-01, OBSV-02), and both signal quality and IRTT metrics are correctly persisted to SQLite with proper deduplication (OBSV-03, OBSV-04). All 4 requirements are satisfied.

The single blocking gap is a test regression: `tests/test_health_alerting.py` was not updated when `health_check.py` gained the new signal_quality/irtt sections. The PLAN (92-01-PLAN.md lines 254-258) explicitly identified the need to update ALL mock WAN controllers to set explicit None values on `_last_signal_result`, `_irtt_thread`, and `_irtt_correlation`, and named `test_health_check.py` fixtures specifically. However, `test_health_alerting.py` was not in the named list and was missed.

**Fix required (3 lines in one file):** Add to `_make_wan_controller_mock()` in `tests/test_health_alerting.py`:
```python
wan_controller._last_signal_result = None
wan_controller._irtt_thread = None
wan_controller._irtt_correlation = None
```
And add to `config = MagicMock()` lines in each affected test method:
```python
config.irtt_config = {"enabled": False}
```

Three tests in `TestAutorateHealthAlerting` call the live HTTP health endpoint and then `json.dumps()` the response, triggering the failure on the MagicMock auto-created attributes.

---

_Verified: 2026-03-17T12:06:10Z_
_Verifier: Claude (gsd-verifier)_
