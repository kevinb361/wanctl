---
phase: 94-owd-asymmetric-detection
verified: 2026-03-17T23:30:00Z
status: passed
score: 7/7 must-haves verified
re_verification: false
---

# Phase 94: OWD Asymmetric Detection Verification Report

**Phase Goal:** The controller can distinguish upstream-only from downstream-only congestion using IRTT burst-internal send_delay vs receive_delay
**Verified:** 2026-03-17T23:30:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria)

| #   | Truth                                                                                                                                           | Status     | Evidence                                                                              |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------- |
| 1   | IRTT burst results are analyzed for send_delay vs receive_delay divergence to detect directional congestion                                     | VERIFIED   | `IRTTResult.send_delay_median_ms` and `receive_delay_median_ms` parsed from IRTT JSON; `AsymmetryAnalyzer.analyze()` computes upstream/downstream/symmetric/unknown from ratio |
| 2   | Asymmetric congestion direction is exposed as a named attribute for downstream consumers                                                        | VERIFIED   | `_last_asymmetry_result: AsymmetryResult | None` on `WANController`; health endpoint exposes `asymmetry_direction` and `asymmetry_ratio` in IRTT section |
| 3   | Asymmetric congestion events are persisted in SQLite with direction and magnitude for trend analysis                                            | VERIFIED   | `wanctl_irtt_asymmetry_ratio` and `wanctl_irtt_asymmetry_direction` written to `metrics_batch` inside existing IRTT dedup guard; both entries in `STORED_METRICS` |

**Score:** 3/3 success criteria verified

### Plan-Level Must-Have Truths

#### Plan 01 Must-Haves

| #   | Truth                                                                               | Status   | Evidence                                                                   |
| --- | ----------------------------------------------------------------------------------- | -------- | -------------------------------------------------------------------------- |
| 1   | IRTTResult contains send_delay_median_ms and receive_delay_median_ms parsed from IRTT JSON | VERIFIED | `irtt_measurement.py` lines 41-42 (fields with 0.0 defaults); `_parse_json` lines 159-160, 174-175 extract `stats.send_delay` and `stats.receive_delay` |
| 2   | AsymmetryAnalyzer computes direction (upstream/downstream/symmetric/unknown) from send/receive delay ratio | VERIFIED | `asymmetry_analyzer.py` lines 66-122: ratio threshold logic with all four outcomes |
| 3   | Direction transitions are logged at INFO, per-measurement at DEBUG                  | VERIFIED | `_log_transition()` lines 124-131: INFO only when `new_direction != self._last_direction` |
| 4   | Config is loaded from owd_asymmetry YAML section with warn+default validation       | VERIFIED | `autorate_continuous.py` lines 874-903: `_load_owd_asymmetry_config()` with isinstance+bool exclusion guard; called at line 958 in `_load_specific_fields()` |

#### Plan 02 Must-Haves

| #   | Truth                                                                                                        | Status   | Evidence                                                                   |
| --- | ------------------------------------------------------------------------------------------------------------ | -------- | -------------------------------------------------------------------------- |
| 5   | Asymmetric congestion direction is available as a named attribute on WANController for downstream consumers  | VERIFIED | `_last_asymmetry_result: AsymmetryResult | None = None` at line 1476; updated every cycle via `analyze()` call at line 2163-2164 |
| 6   | Health endpoint IRTT section includes asymmetry_direction and asymmetry_ratio fields                         | VERIFIED | `health_check.py` lines 225-252: full-data case, awaiting case, and disabled case all handled correctly |
| 7   | Asymmetry direction and ratio are persisted to SQLite metrics with IRTT dedup guard                          | VERIFIED | `autorate_continuous.py` lines 2223-2231: inside `if irtt_result is not None and irtt_result.timestamp != self._last_irtt_write_ts:` guard |

**Score:** 7/7 must-have truths verified

---

## Required Artifacts

| Artifact                               | Expected                                               | Status     | Details                                                                       |
| -------------------------------------- | ------------------------------------------------------ | ---------- | ----------------------------------------------------------------------------- |
| `src/wanctl/asymmetry_analyzer.py`     | AsymmetryAnalyzer, AsymmetryResult, DIRECTION_ENCODING | VERIFIED   | 132 lines; all three exports present; `_MIN_DELAY_MS=0.1` noise guard present |
| `src/wanctl/irtt_measurement.py`       | IRTTResult with send_delay_median_ms, receive_delay_median_ms | VERIFIED | Fields at lines 41-42 with 0.0 defaults; `_parse_json` extracts at lines 159-160, 174-175 |
| `src/wanctl/autorate_continuous.py`    | owd_asymmetry config loading + WANController wiring    | VERIFIED   | `_load_owd_asymmetry_config` at line 874; `_asymmetry_analyzer` init at line 1471; `analyze()` call at line 2163; metrics write at lines 2224-2231 |
| `src/wanctl/health_check.py`           | asymmetry_direction and asymmetry_ratio in IRTT section | VERIFIED  | Lines 225-252: all three IRTT states (disabled, awaiting, full data) include asymmetry fields correctly |
| `src/wanctl/storage/schema.py`         | Two new STORED_METRICS entries                         | VERIFIED   | Lines 30-31: `wanctl_irtt_asymmetry_ratio` and `wanctl_irtt_asymmetry_direction` present |
| `tests/test_asymmetry_analyzer.py`     | Unit tests >= 100 lines; all test classes present      | VERIFIED   | 329 lines; `TestAsymmetryResult`, `TestAsymmetryAnalyzer`, `TestTransitionLogging`, `TestOWDAsymmetryConfig` all present |
| `tests/test_irtt_measurement.py`       | Updated SAMPLE_IRTT_JSON with send_delay; new OWD tests | VERIFIED  | `send_delay` at line 28; `test_send_delay_parsed`, `test_owd_fields_default_zero_when_absent` present |
| `tests/test_asymmetry_persistence.py`  | SQLite metrics write tests >= 50 lines                 | VERIFIED   | 246 lines; `TestStoredMetrics`, `TestDirectionEncoding`, `TestAsymmetryMetricsWrite`, `TestAsymmetryDedup`, `TestLastAsymmetryResult` all present |
| `tests/test_asymmetry_health.py`       | Health endpoint asymmetry field tests >= 50 lines      | VERIFIED   | 260 lines; `TestAsymmetryHealthIRTTAvailable`, `TestAsymmetryHealthNoResult`, `TestAsymmetryHealthIRTTDisabled`, `TestAsymmetryHealthAwaitingMeasurement` all present |

---

## Key Link Verification

| From                                  | To                                        | Via                                            | Status   | Details                                                  |
| ------------------------------------- | ----------------------------------------- | ---------------------------------------------- | -------- | -------------------------------------------------------- |
| `src/wanctl/asymmetry_analyzer.py`    | `src/wanctl/irtt_measurement.py`          | `AsymmetryAnalyzer.analyze(irtt_result: IRTTResult)` | WIRED | `irtt_result.send_delay_median_ms` accessed at line 75; import at line 22 |
| `src/wanctl/autorate_continuous.py`   | `src/wanctl/asymmetry_analyzer.py`        | `_load_owd_asymmetry_config` + `_asymmetry_analyzer` init | WIRED | Import at line 23; `_load_owd_asymmetry_config` at line 874; `AsymmetryAnalyzer(...)` at line 1471 |
| `src/wanctl/autorate_continuous.py`   | `src/wanctl/asymmetry_analyzer.py`        | `self._asymmetry_analyzer.analyze(irtt_result)` in `run_cycle` | WIRED | Call at line 2163; result stored at line 2164 |
| `src/wanctl/autorate_continuous.py`   | `src/wanctl/storage/schema.py`            | `metrics_batch.extend` with asymmetry metrics inside IRTT dedup guard | WIRED | Lines 2224-2231: `wanctl_irtt_asymmetry_ratio` and `wanctl_irtt_asymmetry_direction` written |
| `src/wanctl/health_check.py`          | `src/wanctl/autorate_continuous.py`       | `wan_controller._last_asymmetry_result`        | WIRED    | Lines 243-252: reads `._last_asymmetry_result.direction` and `.ratio` |

---

## Requirements Coverage

| Requirement | Source Plan | Description                                                                               | Status    | Evidence                                                      |
| ----------- | ----------- | ----------------------------------------------------------------------------------------- | --------- | ------------------------------------------------------------- |
| ASYM-01     | 94-01       | Upstream vs downstream congestion detected from IRTT send_delay vs receive_delay within same measurement burst | SATISFIED | `AsymmetryAnalyzer.analyze()` in `asymmetry_analyzer.py`; called in `run_cycle` on each fresh IRTT result |
| ASYM-02     | 94-02       | Asymmetric congestion direction is available as a named attribute for downstream consumers | SATISFIED | `WANController._last_asymmetry_result: AsymmetryResult | None`; exposed in health endpoint |
| ASYM-03     | 94-02       | Asymmetric congestion is persisted in SQLite for trend analysis                           | SATISFIED | `wanctl_irtt_asymmetry_ratio` and `wanctl_irtt_asymmetry_direction` in `STORED_METRICS` and written in `run_cycle` |

All 3 requirements satisfied. No orphaned requirements found (REQUIREMENTS.md and plan frontmatter agree).

---

## Anti-Patterns Found

None. Scan of all 9 phase-modified files returned no TODO/FIXME/PLACEHOLDER comments, no empty implementations, no stub returns.

---

## Human Verification Required

None. All behaviors are verifiable through code inspection:

- The ratio computation logic is deterministic and fully unit-tested (TestAsymmetryAnalyzer: 91 lines of test cases)
- SQLite persistence follows an established pattern identical to existing IRTT metrics
- Health endpoint output is tested by TestAsymmetryHealthIRTTAvailable with concrete field assertions

No visual, real-time, or external-service behaviors introduced in this phase.

---

## Gaps Summary

No gaps. All must-haves verified at all three levels (exists, substantive, wired).

### Notable Implementation Details

- OWD fields added as last fields on `IRTTResult` with `= 0.0` defaults, preserving backward compatibility with all existing constructors in tests
- Ratio capped at 100.0 (not infinity) for divide-by-zero cases, ensuring SQLite REAL column safety
- `_MIN_DELAY_MS = 0.1` noise floor: both delays below this threshold return "symmetric" (not "unknown"), because data is present but too small for meaningful ratios
- Asymmetry metrics reuse the existing `_last_irtt_write_ts` dedup guard — no separate timestamp needed since both are IRTT-derived
- IRTT unavailable section (`available: False`) stays minimal with no asymmetry fields, consistent with the established pattern
- MagicMock truthy trap prevented by explicit `_last_asymmetry_result = None` on all mock WANControllers across 3 test files

### Commit Trail

All 6 task commits verified in git log:
- `5641e56` feat(94-01): extend IRTTResult with OWD send/receive delay fields
- `8e79e24` feat(94-01): create AsymmetryAnalyzer module with config loading
- `9244894` test(94-02): add failing tests for asymmetry persistence and WANController wiring
- `a39248e` feat(94-02): wire AsymmetryAnalyzer into WANController with SQLite persistence
- `5f2b181` test(94-02): add failing tests for asymmetry fields in health endpoint
- `b429204` feat(94-02): add asymmetry fields to IRTT health endpoint section

---

_Verified: 2026-03-17T23:30:00Z_
_Verifier: Claude (gsd-verifier)_
