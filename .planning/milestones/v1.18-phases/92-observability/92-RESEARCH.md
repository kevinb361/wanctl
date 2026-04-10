# Phase 92: Observability - Research

**Researched:** 2026-03-17
**Domain:** Health endpoint extension + SQLite metrics persistence for signal quality and IRTT data
**Confidence:** HIGH

## Summary

Phase 92 wires two existing data sources (signal quality from Phase 88 and IRTT from Phase 90) into the autorate health endpoint and SQLite metrics storage. All data structures, persistence patterns, and endpoint patterns already exist in the codebase -- this phase is pure integration with no new libraries, algorithms, or infrastructure.

The health endpoint follows the established per-WAN section pattern (like `cycle_budget`, `router_connectivity`). The SQLite persistence follows the existing `metrics_batch.extend()` pattern in `run_cycle()`. The only design nuance is IRTT write deduplication: since IRTT measures every 10s but `run_cycle()` executes every 50ms, the implementation must track the last-written IRTT timestamp to avoid 200x row duplication.

**Primary recommendation:** Follow the exact patterns in health_check.py lines 166-189 (per-WAN section construction) and autorate_continuous.py lines 1971-1988 (metrics batch construction). Add 8 entries to STORED_METRICS. Use isinstance guards for MagicMock safety per established convention.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Health endpoint signal_quality section: per-WAN, fields jitter_ms/variance_ms2/confidence/outlier_rate/total_outliers/warming_up
- Health endpoint irtt section: per-WAN, fields rtt_mean_ms/ipdv_ms/loss_up_pct/loss_down_pct/server/staleness_sec/protocol_correlation/available, always present with available flag
- Signal quality SQLite metrics: wanctl_signal_jitter_ms, wanctl_signal_variance_ms2, wanctl_signal_confidence, wanctl_signal_outlier_count
- IRTT SQLite metrics: wanctl_irtt_rtt_ms, wanctl_irtt_ipdv_ms, wanctl_irtt_loss_up_pct, wanctl_irtt_loss_down_pct
- Write cadence: signal quality EVERY cycle (50ms), IRTT ONLY on new measurement (track last-written timestamp)
- IRTT health always-present design: available: false with reason when disabled; available: true with null values awaiting first measurement; full data when working
- Signal quality warming_up flag during first 7 cycles (window_size)
- Staleness computed from irtt_result.timestamp via time.monotonic()
- protocol_correlation from WANController._irtt_correlation (may be None)
- reason field: "disabled" | "binary_not_found" | "awaiting_first_measurement" | omitted when working
- All metrics added to STORED_METRICS dict in storage/schema.py
- No schema migration needed -- generic metrics table (metric_name TEXT, value REAL)

### Claude's Discretion
- Exact health endpoint dict construction (follow cycle_budget pattern)
- isinstance guards for MagicMock safety in health endpoint
- Test fixture design for health endpoint tests
- Whether to round metric values in SQLite (or store full precision)
- Exact placement of metrics batch extension in run_cycle()

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| OBSV-01 | Health endpoint exposes signal quality section (jitter, confidence, variance, outlier count) | Per-WAN section pattern from health_check.py:166-189, SignalResult dataclass fields from signal_processing.py:39-65, _last_signal_result cached on WANController at line 1896 |
| OBSV-02 | Health endpoint exposes IRTT measurement section (RTT, loss direction, IPDV, server status) | IRTTResult dataclass from irtt_measurement.py:22-40, _irtt_thread/get_latest() from irtt_thread.py:46-48, _irtt_correlation from WANController, staleness via time.monotonic() |
| OBSV-03 | Signal quality metrics persisted in SQLite for trend analysis | STORED_METRICS dict in storage/schema.py:11-22, write_metrics_batch() in writer.py:193-228, metrics_batch construction in autorate_continuous.py:1971-2008 |
| OBSV-04 | IRTT metrics persisted in SQLite for trend analysis | Same persistence infrastructure as OBSV-03, plus timestamp-based deduplication to avoid 200x row duplication at 20Hz cycle rate |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.12 | All implementation | Zero new dependencies -- project policy |
| sqlite3 | stdlib | Metrics persistence | Existing MetricsWriter infrastructure |
| time | stdlib | monotonic() for staleness | Already used for IRTT timestamp tracking |
| json | stdlib | Health endpoint response | Already used by health_check.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.2 | Testing | All test files |
| unittest.mock | stdlib | MagicMock, patch | Health endpoint test fixtures |

### Alternatives Considered
None -- this phase uses only existing infrastructure with zero new dependencies.

**Installation:**
```bash
# No new packages needed
```

## Architecture Patterns

### Recommended Project Structure
```
src/wanctl/
  health_check.py           # ADD: signal_quality + irtt sections per WAN
  storage/schema.py         # ADD: 8 new STORED_METRICS entries
  autorate_continuous.py    # ADD: signal quality + IRTT metrics batch extension
tests/
  test_health_check.py      # ADD: signal_quality + irtt health section tests
  test_metrics_observability.py  # NEW: SQLite persistence tests for new metrics
```

### Pattern 1: Per-WAN Health Section (Existing)
**What:** Optional dict sections added to each WAN's health object
**When to use:** Always -- both signal_quality and irtt sections go here
**Example:**
```python
# Source: health_check.py lines 181-189 (cycle_budget pattern)
# After wan_health base dict is constructed:

# Signal quality section (always present -- signal processing always active)
signal_result = wan_controller._last_signal_result
if signal_result is not None:
    wan_health["signal_quality"] = {
        "jitter_ms": round(signal_result.jitter_ms, 3),
        "variance_ms2": round(signal_result.variance_ms2, 3),
        "confidence": round(signal_result.confidence, 3),
        "outlier_rate": round(signal_result.outlier_rate, 3),
        "total_outliers": signal_result.total_outliers,
        "warming_up": signal_result.warming_up,
    }
```

### Pattern 2: Always-Present Section with Available Flag
**What:** Section always present (never omitted), with available: true/false and reason field
**When to use:** IRTT section -- operators need to know if IRTT is configured, not wonder if it's missing
**Example:**
```python
# IRTT section -- always present with available flag
irtt_thread = wan_controller._irtt_thread
if irtt_thread is None:
    # Determine reason: disabled or binary not found
    # Need to check if IRTT was configured but binary missing vs not configured
    wan_health["irtt"] = {
        "available": False,
        "reason": "disabled",  # or "binary_not_found"
    }
else:
    irtt_result = irtt_thread.get_latest()
    if irtt_result is None:
        wan_health["irtt"] = {
            "available": True,
            "reason": "awaiting_first_measurement",
            "rtt_mean_ms": None,
            "ipdv_ms": None,
            "loss_up_pct": None,
            "loss_down_pct": None,
            "server": None,
            "staleness_sec": None,
            "protocol_correlation": None,
        }
    else:
        staleness = round(time.monotonic() - irtt_result.timestamp, 1)
        wan_health["irtt"] = {
            "available": True,
            "rtt_mean_ms": round(irtt_result.rtt_mean_ms, 2),
            "ipdv_ms": round(irtt_result.ipdv_mean_ms, 2),
            "loss_up_pct": round(irtt_result.send_loss, 1),
            "loss_down_pct": round(irtt_result.receive_loss, 1),
            "server": f"{irtt_result.server}:{irtt_result.port}",
            "staleness_sec": staleness,
            "protocol_correlation": (
                round(wan_controller._irtt_correlation, 2)
                if wan_controller._irtt_correlation is not None
                else None
            ),
        }
```

### Pattern 3: Metrics Batch Extension (Existing)
**What:** Append new metric tuples to existing metrics_batch list
**When to use:** Signal quality metrics (every cycle) and IRTT metrics (on new measurement only)
**Example:**
```python
# Source: autorate_continuous.py lines 1971-1988
# Inside the existing "if self._metrics_writer is not None:" block:

# Signal quality metrics -- every cycle (4 metrics)
if self._last_signal_result is not None:
    sr = self._last_signal_result
    metrics_batch.extend([
        (ts, self.wan_name, "wanctl_signal_jitter_ms", sr.jitter_ms, None, "raw"),
        (ts, self.wan_name, "wanctl_signal_variance_ms2", sr.variance_ms2, None, "raw"),
        (ts, self.wan_name, "wanctl_signal_confidence", sr.confidence, None, "raw"),
        (ts, self.wan_name, "wanctl_signal_outlier_count", float(sr.total_outliers), None, "raw"),
    ])

# IRTT metrics -- only on new measurement (4 metrics)
if irtt_result is not None and irtt_result.timestamp != self._last_irtt_write_ts:
    metrics_batch.extend([
        (ts, self.wan_name, "wanctl_irtt_rtt_ms", irtt_result.rtt_mean_ms, None, "raw"),
        (ts, self.wan_name, "wanctl_irtt_ipdv_ms", irtt_result.ipdv_mean_ms, None, "raw"),
        (ts, self.wan_name, "wanctl_irtt_loss_up_pct", irtt_result.send_loss, None, "raw"),
        (ts, self.wan_name, "wanctl_irtt_loss_down_pct", irtt_result.receive_loss, None, "raw"),
    ])
    self._last_irtt_write_ts = irtt_result.timestamp
```

### Pattern 4: IRTT Write Deduplication
**What:** Track last-written IRTT timestamp to avoid duplicate SQLite rows
**When to use:** IRTT metrics persistence -- IRTT measures every ~10s, run_cycle executes every 50ms
**Implementation:** Add `self._last_irtt_write_ts: float | None = None` to WANController.__init__ alongside other IRTT state. Compare `irtt_result.timestamp != self._last_irtt_write_ts` before writing.

### Anti-Patterns to Avoid
- **Omitting IRTT section when disabled:** Always include with available: false + reason. Operators need to see it's configured off, not wonder if it's missing.
- **Writing IRTT metrics every cycle:** Would create 200x duplicate rows (10s/50ms = 200 cycles per measurement). MUST track last-written timestamp.
- **isinstance check on signal_result:** Not needed -- `_last_signal_result` is always `SignalResult | None`, set by internal code, not from config/mocks. Only check `is not None`.
- **isinstance check on irtt_thread:** Needed in health endpoint tests where wan_controller is MagicMock -- `_irtt_thread` attribute on MagicMock returns another MagicMock (truthy), not None. Use isinstance guard or explicit None assignment in test fixtures.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Metrics persistence | Custom SQLite writes | MetricsWriter.write_metrics_batch() | Thread-safe, transactional, existing infrastructure |
| Health endpoint HTTP | Custom server | Existing HealthCheckHandler._get_health_status() | Add sections to existing method |
| IRTT staleness calculation | Complex age tracking | `time.monotonic() - irtt_result.timestamp` | IRTTResult.timestamp is already monotonic |
| Metric naming | Custom scheme | STORED_METRICS dict entries | Prometheus-compatible naming convention exists |

**Key insight:** Every building block exists. This phase is wiring, not building.

## Common Pitfalls

### Pitfall 1: MagicMock Truthy on _irtt_thread
**What goes wrong:** In tests, `mock_wan_controller._irtt_thread` returns a MagicMock (truthy) instead of None, causing the health endpoint to try calling `.get_latest()` on a MagicMock.
**Why it happens:** MagicMock auto-creates attributes as MagicMock instances.
**How to avoid:** In test fixtures, explicitly set `mock_wan_controller._irtt_thread = None` when IRTT is not being tested. For IRTT tests, create a real or explicit mock with controlled return values.
**Warning signs:** Tests passing but returning unexpected MagicMock objects in health JSON instead of None/dicts.

### Pitfall 2: IRTT Write Duplication at 20Hz
**What goes wrong:** 80 IRTT rows per second instead of 0.4, database bloat, downsampling overhead.
**Why it happens:** `irtt_result` reference doesn't change between measurements (pointer swap only on new result), so every 50ms cycle sees the same result and re-writes it.
**How to avoid:** Compare `irtt_result.timestamp` with `self._last_irtt_write_ts` before writing. Only write when timestamp differs.
**Warning signs:** `wanctl_irtt_*` metrics growing 200x faster than expected in SQLite.

### Pitfall 3: Signal Result None During First Cycle
**What goes wrong:** Health endpoint crashes or returns incomplete data on very first cycle before any RTT measurement.
**Why it happens:** `_last_signal_result` starts as None, set to SignalResult on first `run_cycle()` call.
**How to avoid:** Check `signal_result is not None` before constructing section. When None, omit section (same as cycle_budget pattern -- section only appears when data exists).
**Warning signs:** KeyError or TypeError in health endpoint on startup.

### Pitfall 4: IRTT "disabled" vs "binary_not_found" Reason
**What goes wrong:** Health endpoint shows wrong reason for IRTT unavailability.
**Why it happens:** When `_irtt_thread` is None, it could be because IRTT is disabled in config OR because the binary wasn't found. Need to distinguish.
**How to avoid:** Check the WANController's IRTT config state. If `irtt_config.get("enabled")` is False, reason is "disabled". If enabled but `_irtt_thread` is None, reason is "binary_not_found". The `_irtt_thread` is set in `main()` after `_start_irtt_thread()` which returns None for either case.
**Warning signs:** Operators seeing "disabled" when IRTT is configured but irtt binary is missing.

### Pitfall 5: irtt_result Scope in Metrics Block
**What goes wrong:** `irtt_result` variable referenced in metrics block but defined in a different scope within `run_cycle()`.
**Why it happens:** `irtt_result` is assigned inside the state management PerfTimer block (line 1940), and metrics are written at line 1971+ inside the same block. Both are in scope. However, the variable is inside a `with` statement -- ensure the metrics extension happens INSIDE the same `with state_timer:` block.
**How to avoid:** Place signal quality and IRTT metrics batch extension INSIDE the existing metrics writing block (lines 1971-2008), which is already inside the state_timer context.
**Warning signs:** NameError on `irtt_result` or `signal_result`.

### Pitfall 6: Accessing Config from Health Endpoint
**What goes wrong:** Health endpoint code in health_check.py needs to determine IRTT reason ("disabled" vs "binary_not_found") but doesn't have direct access to WAN config.
**Why it happens:** Health endpoint only has access to `wan_controller` (WANController instance), not the config dict.
**How to avoid:** Access `wan_controller._irtt_thread` for None check. For reason differentiation, can check `wan_info["config"].irtt_config.get("enabled", False)` since health_check.py already iterates `wan_info` dicts which contain both controller and config.
**Warning signs:** Unable to distinguish IRTT unavailability reasons.

## Code Examples

### STORED_METRICS Additions
```python
# Source: storage/schema.py STORED_METRICS dict
# Add these 8 entries:
"wanctl_signal_jitter_ms": "EWMA jitter from consecutive RTT deltas in milliseconds",
"wanctl_signal_variance_ms2": "EWMA variance of RTT around load_rtt in ms^2",
"wanctl_signal_confidence": "Measurement confidence score (0-1, higher is better)",
"wanctl_signal_outlier_count": "Lifetime count of Hampel-detected outlier RTT samples",
"wanctl_irtt_rtt_ms": "IRTT measured mean RTT in milliseconds",
"wanctl_irtt_ipdv_ms": "IRTT measured mean IPDV (jitter) in milliseconds",
"wanctl_irtt_loss_up_pct": "IRTT upstream packet loss percentage",
"wanctl_irtt_loss_down_pct": "IRTT downstream packet loss percentage",
```

### WANController Init for IRTT Deduplication
```python
# Add alongside existing IRTT state (after line 1350):
self._last_irtt_write_ts: float | None = None
```

### Health Endpoint Test Fixture Pattern
```python
# Follow existing test_health_check.py mock pattern:
mock_wan_controller = MagicMock()
# ... existing setup ...

# Signal quality: set to None for base tests, SignalResult for signal tests
mock_wan_controller._last_signal_result = None

# IRTT: explicitly set to None (prevents MagicMock truthy issue)
mock_wan_controller._irtt_thread = None
mock_wan_controller._irtt_correlation = None
```

### IRTT Reason Detection in Health Endpoint
```python
# Inside health_check.py per-WAN loop (has access to wan_info dict):
irtt_thread = wan_controller._irtt_thread
if irtt_thread is None:
    irtt_enabled = config.irtt_config.get("enabled", False)
    if not irtt_enabled:
        reason = "disabled"
    else:
        reason = "binary_not_found"
    wan_health["irtt"] = {"available": False, "reason": reason}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No signal quality in health | Phase 92 adds signal_quality section | v1.18 | Operators see jitter/confidence/variance live |
| No IRTT in health | Phase 92 adds irtt section | v1.18 | Operators see IRTT measurements + staleness |
| 10 STORED_METRICS entries | 18 after Phase 92 | v1.18 | Historical trend analysis for signal quality + IRTT |
| Signal data only in logs | Signal data in health + SQLite | v1.18 | Queryable via /metrics/history API |

**No deprecated or outdated patterns** -- this phase extends existing infrastructure.

## Open Questions

1. **Rounding precision in SQLite**
   - What we know: Health endpoint uses round() for display. Existing metrics (RTT, rates) are stored at full precision in SQLite.
   - What's unclear: Whether signal quality metrics should round in SQLite too.
   - Recommendation: Store full precision in SQLite (consistent with existing metrics). Round only in health endpoint display. Full precision preserves data for future analysis.

2. **IRTT disabled vs binary_not_found detection**
   - What we know: `_irtt_thread` is None for both cases. Config has `irtt_config.enabled` flag. `_start_irtt_thread()` checks `measurement.is_available()` which requires enabled + server + binary.
   - What's unclear: Whether health endpoint can reliably distinguish these without storing the reason on the controller.
   - Recommendation: Access `config.irtt_config` from the `wan_info` dict in health_check.py. If `enabled` is False, reason is "disabled". If `enabled` is True but `_irtt_thread` is None, reason is "binary_not_found". If `server` is None, reason is "disabled" (effectively same -- enabled without server means not actually configured).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `.venv/bin/pytest tests/test_health_check.py tests/test_metrics_observability.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OBSV-01 | Health endpoint signal_quality section with jitter/confidence/variance/outlier_count/warming_up | unit | `.venv/bin/pytest tests/test_health_check.py -x -k signal_quality` | No -- Wave 0 |
| OBSV-02 | Health endpoint irtt section with available/reason/rtt/ipdv/loss/server/staleness/correlation | unit | `.venv/bin/pytest tests/test_health_check.py -x -k irtt` | No -- Wave 0 |
| OBSV-03 | Signal quality metrics written to SQLite every cycle (4 metrics) | unit | `.venv/bin/pytest tests/test_metrics_observability.py -x -k signal` | No -- Wave 0 |
| OBSV-04 | IRTT metrics written to SQLite only on new measurement + deduplication | unit | `.venv/bin/pytest tests/test_metrics_observability.py -x -k irtt` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_health_check.py tests/test_metrics_observability.py -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_health_check.py` -- add signal_quality and irtt section test classes (OBSV-01, OBSV-02)
- [ ] `tests/test_metrics_observability.py` -- new file for SQLite persistence tests (OBSV-03, OBSV-04)
- [ ] No framework install needed -- pytest 9.0.2 already configured

## Sources

### Primary (HIGH confidence)
- `src/wanctl/health_check.py` lines 166-209 -- Per-WAN health section construction + AlertEngine isinstance guard
- `src/wanctl/signal_processing.py` lines 39-65 -- SignalResult frozen dataclass (10 fields)
- `src/wanctl/irtt_measurement.py` lines 22-40 -- IRTTResult frozen dataclass (11 fields)
- `src/wanctl/irtt_thread.py` lines 46-48 -- get_latest() lock-free cached result API
- `src/wanctl/storage/schema.py` lines 11-22 -- STORED_METRICS dict (10 current entries)
- `src/wanctl/storage/writer.py` lines 193-228 -- write_metrics_batch() interface
- `src/wanctl/autorate_continuous.py` lines 1339-1351 -- WANController signal/IRTT state init
- `src/wanctl/autorate_continuous.py` lines 1890-2008 -- Signal processing + IRTT observation + metrics batch in run_cycle()
- `src/wanctl/steering/health.py` lines 226-272 -- wan_awareness always-present section pattern
- `tests/test_health_check.py` -- Existing test patterns for mock WAN controllers

### Secondary (MEDIUM confidence)
- `.planning/phases/92-observability/92-CONTEXT.md` -- All locked decisions and field specifications

### Tertiary (LOW confidence)
None -- all findings verified from source code.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- zero new dependencies, all existing infrastructure
- Architecture: HIGH -- all patterns verified from source code, exact line numbers documented
- Pitfalls: HIGH -- MagicMock truthy issue and IRTT deduplication identified from code review of existing patterns
- Code examples: HIGH -- derived directly from existing code patterns in the codebase

**Research date:** 2026-03-17
**Valid until:** 2026-04-17 (stable -- internal codebase patterns, no external dependencies)
