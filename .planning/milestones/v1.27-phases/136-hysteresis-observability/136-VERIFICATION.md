---
phase: 136-hysteresis-observability
verified: 2026-04-03T19:40:37Z
status: passed
score: 7/7 must-haves verified
re_verification: false
---

# Phase 136: Hysteresis Observability Verification Report

**Phase Goal:** Operator can monitor dwell/deadband suppression rates during real congestion to detect potential false negatives
**Verified:** 2026-04-03T19:40:37Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Health endpoint exposes per-minute suppression count with windowed counters per direction | VERIFIED | `health_check.py:220,233` — `suppressions_per_min`, `window_start_epoch`, `alert_threshold_per_min` in both download/upload hysteresis dicts |
| 2 | Controller logs periodic suppression rate at INFO level at each 60s window boundary during congestion | VERIFIED | `autorate_continuous.py:3267-3269` — `[HYSTERESIS] %s window: %d suppressions in 60s (DL: %d, UL: %d)` at INFO, gated by `had_congestion` |
| 3 | Window resets every 60s and reports the previous window's count | VERIFIED | `autorate_continuous.py:3246-3286` — `_check_hysteresis_window()` checks elapsed >= 60s, reads congestion flags before reset, calls `reset_window()` which returns-then-clears |
| 4 | Discord alert fires when suppression rate exceeds configurable threshold in a 60s window | VERIFIED | `autorate_continuous.py:3272-3284` — `alert_engine.fire(alert_type="hysteresis_suppression", severity="warning", ...)` inside `had_congestion` guard when `total > _suppression_alert_threshold` |
| 5 | Suppression alert threshold is YAML-configurable under continuous_monitoring.thresholds | VERIFIED | `autorate_continuous.py:2145-2147` — init reads `cm_config.get("thresholds", {}).get("suppression_alert_threshold", 20)` |
| 6 | Suppression alert threshold is hot-reloadable via SIGUSR1 | VERIFIED | `autorate_continuous.py:3129` def `_reload_suppression_alert_config()`, wired into SIGUSR1 chain at line 5025 |
| 7 | AlertEngine cooldown prevents suppression alert spam | VERIFIED | AlertEngine.fire() at `alert_engine.py:112,116` applies cooldown per `(alert_type, wan_name)` key — no allowlist needed, generic mechanism covers `hysteresis_suppression` |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/wanctl/autorate_continuous.py` | QueueController windowed counter + WANController window check + alert + SIGUSR1 reload | VERIFIED | `_window_suppressions` at 5 sites in source (plus 2 more in health_check.py); `_check_hysteresis_window` at 3 sites (def + call in `_record_profiling` + docstring); `_reload_suppression_alert_config` at 2 sites (def + SIGUSR1 chain) |
| `src/wanctl/health_check.py` | Windowed hysteresis fields in health endpoint | VERIFIED | `suppressions_per_min`, `window_start_epoch`, `alert_threshold_per_min` in both DL/UL hysteresis dicts (lines 220-222, 233-235) |
| `tests/test_hysteresis_observability.py` | TDD tests for windowed counter, window reset, health endpoint, periodic logging | VERIFIED | 572 lines, 24 tests across 4 classes, all passing |
| `tests/test_hysteresis_alert.py` | TDD tests for alert firing, threshold check, SIGUSR1 reload | VERIFIED | 418 lines, 16 tests across 3 classes, all passing |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `QueueController.adjust()` | `_window_suppressions` counter | increment alongside `_transitions_suppressed` | WIRED | `autorate_continuous.py:1452` — `self._window_suppressions += 1` after `_transitions_suppressed += 1` |
| `QueueController.adjust_4state()` | `_window_suppressions` counter | increment alongside `_transitions_suppressed` | WIRED | `autorate_continuous.py:1594` — `self._window_suppressions += 1` after `_transitions_suppressed += 1` |
| `WANController._record_profiling()` | `_check_hysteresis_window()` | call every cycle | WIRED | `autorate_continuous.py:3220` — `self._check_hysteresis_window()` called after `_check_cycle_budget_alert()` |
| `health_check.py` | `QueueController._window_suppressions` | direct attribute access | WIRED | `health_check.py:220,233` — `wan_controller.download._window_suppressions` and `wan_controller.upload._window_suppressions` |
| `WANController._check_hysteresis_window()` | `AlertEngine.fire()` | threshold comparison after window reset | WIRED | `autorate_continuous.py:3273-3284` — `self.alert_engine.fire(alert_type="hysteresis_suppression", ...)` |
| `WANController._reload_suppression_alert_config()` | `_suppression_alert_threshold` | SIGUSR1 handler chain | WIRED | `autorate_continuous.py:5025` — `wan_info["controller"]._reload_suppression_alert_config()` in SIGUSR1 block |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `health_check.py` suppressions_per_min | `QueueController._window_suppressions` | Incremented in `adjust()`/`adjust_4state()` on each dwell suppression event | Yes — live counter, not hardcoded | FLOWING |
| `health_check.py` window_start_epoch | `QueueController._window_start_time` | Set to `time.time()` on init and after each `reset_window()` | Yes — real timestamp | FLOWING |
| `health_check.py` alert_threshold_per_min | `WANController._suppression_alert_threshold` | Parsed from YAML at init and reloaded on SIGUSR1 | Yes — from config, not hardcoded | FLOWING |
| `_check_hysteresis_window()` alert | `dl_count + ul_count` from `reset_window()` | Accumulated from real dwell suppressions in `adjust()`/`adjust_4state()` | Yes — real suppression events | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Test suite: windowed counter + health + logging (Plan 01) | `.venv/bin/pytest tests/test_hysteresis_observability.py -v` | 24 passed | PASS |
| Test suite: alert firing + SIGUSR1 reload (Plan 02) | `.venv/bin/pytest tests/test_hysteresis_alert.py -v` | 16 passed | PASS |
| Regression: queue controller | `.venv/bin/pytest tests/test_queue_controller.py -v` | 79 passed | PASS |
| Regression: health check | `.venv/bin/pytest tests/test_health_check.py -v` | 77 passed | PASS |
| Combined targeted suite | `.venv/bin/pytest tests/test_hysteresis_observability.py tests/test_hysteresis_alert.py tests/test_queue_controller.py tests/test_health_check.py -q` | 196 passed in 20.78s | PASS |
| Lint: modified files | `.venv/bin/ruff check src/wanctl/autorate_continuous.py src/wanctl/health_check.py` | All checks passed | PASS |
| Type check: modified files | `.venv/bin/mypy src/wanctl/autorate_continuous.py src/wanctl/health_check.py` | 16 errors (all pre-existing, confirmed same count before phase 136) | PASS (no regression) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|------------|------------|-------------|--------|---------|
| HYST-01 | 136-01-PLAN | Health endpoint exposes per-minute suppression rate with windowed counters | SATISFIED | `health_check.py:220,233` — `suppressions_per_min` per direction; tests `TestHysteresisHealthEndpoint` pass |
| HYST-02 | 136-01-PLAN | Controller logs periodic suppression rate at INFO level during active congestion events | SATISFIED | `autorate_continuous.py:3266-3270` — INFO log only when `had_congestion` is True; tests `TestPeriodicHysteresisLogging` pass |
| HYST-03 | 136-02-PLAN | AlertEngine fires Discord alert when suppression rate exceeds configurable threshold | SATISFIED | `autorate_continuous.py:3272-3284` — `alert_engine.fire(alert_type="hysteresis_suppression")` gated by threshold and congestion; `_reload_suppression_alert_config()` in SIGUSR1 chain; tests `TestHysteresisSuppressionAlert` and `TestSIGUSR1ChainIncludesSuppressionReload` pass |

All 3 requirements marked Complete in REQUIREMENTS.md traceability table. No orphaned requirements.

### Anti-Patterns Found

None. No TODOs, placeholder returns, or stub implementations found in phase 136 additions.

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `src/wanctl/autorate_continuous.py` | 7 pre-existing mypy errors (ReflectorScorer, FusionHealer, LinuxCakeAdapter, validate_retention) | Info | Not introduced by phase 136 — verified by comparing pre-136 snapshot (same errors present) |

### Human Verification Required

### 1. Live Discord Alert Delivery

**Test:** Temporarily lower `suppression_alert_threshold` to 0 in YAML, send SIGUSR1, then introduce enough load to trigger dwell suppressions. Observe Discord webhook.
**Expected:** Discord message arrives with `hysteresis_suppression` alert type, showing DL/UL breakdown and threshold.
**Why human:** Requires live Discord webhook, production YAML edit, and real congestion load. Cannot test without running services.

### 2. Real-Congestion INFO Log Visibility

**Test:** Monitor `journalctl -u wanctl@spectrum -f` during a bufferbloat event (e.g., netperf download). After ~60s, verify `[HYSTERESIS] spectrum window: N suppressions` appears in logs.
**Expected:** INFO log line appears only during congested windows, silent during idle.
**Why human:** Requires real network congestion; cannot simulate deterministically without production environment.

### Gaps Summary

No gaps. All 7 observable truths verified. All 4 artifacts exist, are substantive, and are wired. All 3 requirement IDs (HYST-01, HYST-02, HYST-03) are satisfied with implementation evidence. No blocker anti-patterns. Human verification items are optional confirmation of live behavior, not blocking items.

---

_Verified: 2026-04-03T19:40:37Z_
_Verifier: Claude (gsd-verifier)_
