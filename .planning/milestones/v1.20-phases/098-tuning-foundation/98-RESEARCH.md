# Phase 98: Tuning Foundation - Research

**Researched:** 2026-03-18
**Domain:** Adaptive parameter tuning framework for production dual-WAN CAKE controller
**Confidence:** HIGH

## Summary

Phase 98 builds the tuning engine framework that all subsequent v1.20 phases depend on. The scope is infrastructure only: data models, config parsing, SIGUSR1 toggle, SQLite persistence, health endpoint integration, and the maintenance-window wiring. No actual tuning strategies (parameter derivation logic) are included -- those belong to Phases 99-102.

Every integration point for this phase follows a pattern already proven in the codebase at least twice: `_load_alerting_config()` for config parsing with warn+disable, `_reload_fusion_config()` for SIGUSR1 toggle, AlertEngine's `_persist_alert()` for SQLite insert via MetricsWriter, and the health endpoint's fusion/alerting sections for observability. Zero new Python dependencies are needed -- the framework uses frozen dataclasses, `statistics.quantiles()` from stdlib, and existing `storage/reader.py` for metric queries.

The primary risk is getting the framework boundaries wrong, leading to rework when strategy phases (99-102) discover missing abstractions. The architecture research already defines TuningResult as the interface contract: a frozen dataclass with parameter, old_value, new_value, confidence, rationale, and data_points. Strategy functions are pure functions from `(metrics_data, current_value, bounds) -> TuningResult | None`. This contract is simple enough to survive strategy implementation.

**Primary recommendation:** Build models, config, SIGUSR1, SQLite schema, health endpoint, and maintenance-window wiring. Ship disabled. Include one stub strategy (no-op) to prove the end-to-end pipeline works under test.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TUNE-01 | Tuning engine ships disabled by default (`tuning.enabled: false`) | Config parsing follows `_load_alerting_config()` warn+disable pattern; `tuning.enabled: false` default |
| TUNE-02 | Tuning can be enabled/disabled via SIGUSR1 without restart | `_reload_fusion_config()` pattern: re-read YAML, log old->new, update state; extends SIGUSR1 chain at line 3543 |
| TUNE-03 | Each tunable parameter has configurable min/max safety bounds in YAML | `tuning.bounds` dict with `{min, max}` per parameter; validated at config load |
| TUNE-04 | Tuning analyzes per-WAN metrics independently | Existing per-WAN `query_metrics(wan=wc.wan_name)` pattern; iterate `controller.wan_controllers` |
| TUNE-05 | Tuning decisions logged with old/new/rationale | TuningResult.rationale string; WARNING-level log matching SIGUSR1 transition pattern |
| TUNE-06 | Health endpoint exposes tuning section | Follows fusion/alerting health section pattern; per-WAN `tuning` key in health JSON |
| TUNE-07 | Tuning skips analysis when < 1h of metrics data | `warmup_hours` config; query earliest timestamp, compare to lookback requirement |
| TUNE-08 | Tuning adjustments persisted to SQLite | New `tuning_params` table following alerts table pattern; INSERT via MetricsWriter.connection |
| TUNE-09 | Tuning runs during hourly maintenance window | Piggyback on existing MAINTENANCE_INTERVAL block (line 3508); separate `last_tuning` timer |
| TUNE-10 | Max 10% parameter change per tuning cycle enforced | `max_step_pct` config (default 10); clamping logic in applier before WANController mutation |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `statistics` | 3.12 | `quantiles()`, `median()`, `stdev()` | Already used in storage/reader.py `compute_summary()`; zero deps |
| Python stdlib `dataclasses` | 3.12 | `@dataclass(frozen=True, slots=True)` for TuningResult/TuningConfig | Proven pattern: SignalResult, IRTTResult, AsymmetryResult |
| Python stdlib `collections.deque` | 3.12 | Bounded history for adjustment tracking | Already used in SignalProcessor |
| SQLite (via MetricsWriter) | bundled | Persist tuning decisions to `tuning_params` table | Existing persistence pattern (alerts, benchmarks, reflector_events) |
| PyYAML | 6.0.2 | Config reload on SIGUSR1 | Already a project dependency |

### Supporting
No new supporting libraries needed.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| statistics.quantiles | numpy percentile | numpy is not a project dependency and adds 30MB for 6-8 scalar params |
| Frozen dataclasses | TypedDict | Dataclasses are the established pattern (SignalResult, IRTTResult) |
| SQLite tuning_params | JSON file | SQLite is already the persistence backend; adds querying capability |

**Installation:**
```bash
# No new packages needed
```

**Version verification:** All stdlib modules verified available in Python 3.12 (project runtime).

## Architecture Patterns

### Recommended Project Structure
```
src/wanctl/
  tuning/
    __init__.py          # Package init (export public API)
    models.py            # TuningResult, TuningConfig, TuningState, SafetyBounds
    analyzer.py          # Per-WAN metric query + strategy orchestration
    applier.py           # Bounds check, max_step clamp, apply to WANController, persist
    strategies/
      __init__.py        # Strategy registry / interface
      base.py            # Strategy protocol/base (for Phase 99+ to implement)
```

### Pattern 1: Config Parsing with Warn+Disable
**What:** Load `tuning:` YAML section with field-by-field validation. Invalid config logs WARNING and disables tuning. Never crashes the daemon.
**When to use:** For all optional feature config sections.
**Source:** `_load_alerting_config()` at autorate_continuous.py:505

```python
def _load_tuning_config(self) -> None:
    """Load tuning configuration. Warns and disables on invalid config."""
    logger = logging.getLogger(__name__)
    tuning = self.data.get("tuning", {})

    if not tuning:
        self.tuning_config = None
        logger.info("Tuning: disabled (enable via tuning.enabled)")
        return

    enabled = tuning.get("enabled", False)
    if not isinstance(enabled, bool):
        logger.warning(
            f"tuning.enabled must be bool, got {type(enabled).__name__}; "
            "disabling tuning"
        )
        self.tuning_config = None
        return

    if not enabled:
        self.tuning_config = None
        logger.info("Tuning: disabled (enable via tuning.enabled)")
        return

    # Validate safety bounds, cadence, warmup, etc.
    # ... (each field validated individually, warn+disable on error)

    self.tuning_config = {
        "enabled": True,
        "cadence_sec": cadence_sec,
        "lookback_hours": lookback_hours,
        "warmup_hours": warmup_hours,
        "max_step_pct": max_step_pct,
        "bounds": bounds,
    }
```

### Pattern 2: SIGUSR1 Reload Chain Extension
**What:** Add `_reload_tuning_config()` to WANController, called from existing SIGUSR1 handler.
**When to use:** For any feature that needs zero-downtime enable/disable.
**Source:** `_reload_fusion_config()` at autorate_continuous.py:2138

```python
# In main loop SIGUSR1 block (line 3543):
if is_reload_requested():
    for wan_info in controller.wan_controllers:
        wan_info["logger"].info("SIGUSR1 received, reloading config")
        wan_info["controller"]._reload_fusion_config()
        wan_info["controller"]._reload_tuning_config()  # NEW
    reset_reload_state()
```

The `_reload_tuning_config()` method:
- Re-reads `tuning:` from YAML
- If enabled->disabled: clear tuning state, log transition
- If disabled->enabled: set ready flag for next maintenance window, log transition
- If bounds changed: validate new bounds, log changes
- YAML is always the reset escape hatch

### Pattern 3: Maintenance Window Piggyback
**What:** Run tuning analysis in the hourly maintenance window, after cleanup/downsampling.
**When to use:** For periodic analysis that is fast (<100ms) and doesn't need its own thread.
**Source:** Maintenance block at autorate_continuous.py:3505-3540

```python
# After existing cleanup/downsample/vacuum:
if tuning_enabled:
    now_mono = time.monotonic()
    if now_mono - last_tuning >= tuning_cadence:
        for wan_info in controller.wan_controllers:
            wc = wan_info["controller"]
            results = run_tuning_analysis(wc, db_path, tuning_config)
            if results:
                apply_tuning_results(wc, results, metrics_writer)
        last_tuning = now_mono
```

### Pattern 4: Frozen Dataclass Results
**What:** TuningResult as `@dataclass(frozen=True, slots=True)` -- immutable, hashable, efficient.
**Source:** SignalResult (signal_processing.py:39), IRTTResult, AsymmetryResult

```python
@dataclass(frozen=True, slots=True)
class TuningResult:
    parameter: str        # e.g., "target_bloat_ms"
    old_value: float
    new_value: float
    confidence: float     # 0.0-1.0 based on data quantity
    rationale: str        # Human-readable for logs and health endpoint
    data_points: int      # Number of data points used in derivation
    wan_name: str         # WAN this result applies to
```

### Pattern 5: Per-WAN Health Endpoint Section
**What:** Add `tuning` key to each WAN's health JSON, with always-present structure.
**Source:** Fusion section (health_check.py:277-319), IRTT section (health_check.py:204-253)

When disabled:
```json
{"tuning": {"enabled": false, "reason": "disabled"}}
```

When enabled but no data yet:
```json
{"tuning": {"enabled": true, "last_run": null, "parameters": {}, "reason": "awaiting_data"}}
```

When active:
```json
{
  "tuning": {
    "enabled": true,
    "last_run_ago_sec": 1847,
    "next_run_in_sec": 1753,
    "parameters": {
      "target_bloat_ms": {"yaml_value": 15.0, "current_value": 15.0, "bounds": {"min": 3, "max": 30}},
      "warn_bloat_ms": {"yaml_value": 45.0, "current_value": 45.0, "bounds": {"min": 10, "max": 100}}
    },
    "recent_adjustments": []
  }
}
```

### Anti-Patterns to Avoid
- **YAML file mutation:** Never write tuned values to config files. YAML is operator truth; tuning is runtime-only.
- **Per-cycle analysis:** Tuning MUST be hourly. Per-cycle would cause feedback oscillation.
- **Cross-WAN contamination:** Each WAN queried and tuned independently via `wan=wc.wan_name` filter.
- **Background thread for analysis:** Analysis is <100ms CPU work -- no thread needed.
- **Simultaneous multi-parameter changes:** Phase 98 builds the framework; later phases add one category at a time.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Metric history queries | Custom SQLite queries | `storage/reader.py query_metrics()` | Read-only conn, WAL-safe, granularity-aware |
| Persistence writes | Direct SQLite in tuning | `MetricsWriter.connection` | Thread-safe singleton, WAL mode, integrity checks |
| Config validation | Ad-hoc YAML parsing | `_load_alerting_config()` pattern | Proven warn+disable, never crashes |
| SIGUSR1 toggle | Custom signal handling | `signal_utils.py` + reload chain | Thread-safe, single-threaded reload check |
| Health endpoint section | Custom HTTP handler | Extend existing `HealthCheckHandler._get_health_status()` | Consistent JSON structure, same port |
| Table creation | Manual CREATE TABLE | Add to `storage/schema.py create_tables()` | Idempotent IF NOT EXISTS, consistent |

**Key insight:** Every component of Phase 98 has a direct precedent in the codebase. The risk is in novel integration, not novel implementation.

## Common Pitfalls

### Pitfall 1: MagicMock Truthy Trap on Tuning State
**What goes wrong:** Test uses `MagicMock()` for WANController. Code checks `if controller._tuning_enabled:` and MagicMock is truthy. Tuning logic runs against mock data, crashes or produces nonsense.
**Why it happens:** MagicMock() evaluates as truthy. Every v1.18/v1.19 feature hit this.
**How to avoid:** Explicit `_tuning_enabled = False`, `_tuning_state = None`, `_last_tuning_ts = None` on mock WANController objects. Add to `mock_autorate_config` fixture.
**Warning signs:** Tests pass in isolation but fail in CI; AttributeError on mock objects.

### Pitfall 2: Config Validation Crash on Malformed Bounds
**What goes wrong:** Operator writes `bounds: target_bloat_ms: 15` (scalar, not dict). Config loader does `bounds["target_bloat_ms"]["min"]` and gets TypeError. Daemon won't start.
**Why it happens:** YAML allows nested dict or scalar for the same key.
**How to avoid:** Validate each bounds entry is a dict with "min" and "max" keys. Warn+disable on invalid structure.
**Warning signs:** Daemon fails to start with TypeError in config loading.

### Pitfall 3: Maintenance Window Timing Interaction
**What goes wrong:** Tuning runs BEFORE downsampling completes. It queries stale 1m aggregates (previous hour's data). First tuning cycle after startup has stale data.
**Why it happens:** Downsampling creates 1m aggregates from raw data. If tuning runs before downsampling, the most recent hour's data isn't aggregated yet.
**How to avoid:** Run tuning AFTER existing maintenance (cleanup + downsample + vacuum). The existing code structure naturally supports this -- add tuning call after the existing maintenance block.
**Warning signs:** Tuning "last_data_ts" is always 1 hour behind wall clock.

### Pitfall 4: SIGUSR1 During Tuning Analysis
**What goes wrong:** Operator sends SIGUSR1 while tuning analysis is running (unlikely in <100ms window, but possible). Config changes mid-analysis. Results computed with old config, applied with new bounds.
**Why it happens:** SIGUSR1 check and tuning run in the same main loop iteration, but SIGUSR1 check comes AFTER maintenance.
**How to avoid:** Check for reload flag at the START of tuning. If reload happened, skip this cycle's results. Alternatively, check SIGUSR1 before maintenance (existing location) and tuning reads post-reload config naturally.
**Warning signs:** Tuning log shows bounds that don't match current YAML.

### Pitfall 5: SQLite Schema Not Created on Fresh Database
**What goes wrong:** Daemon starts with no existing metrics.db. MetricsWriter creates tables via `create_tables()`. But tuning_params table isn't included. First tuning persistence fails with "no such table: tuning_params".
**Why it happens:** New table added to schema.py but not added to `create_tables()` function.
**How to avoid:** Add `TUNING_PARAMS_SCHEMA` to the `create_tables()` function in `storage/schema.py`. Test with fresh database.
**Warning signs:** First tuning cycle after fresh install logs error.

### Pitfall 6: Bounds Tighter Than Config SCHEMA Ranges
**What goes wrong:** Config SCHEMA says `target_bloat_ms` range is [1, 100]. Tuning bounds say [3, 30]. Operator configures `target_bloat_ms: 2` in continuous_monitoring (valid per SCHEMA). Tuning tries to clamp to [3, 30] but actual value is 2 (below tuning min). Tuning would "adjust" to 3, which is a 50% increase -- exceeding max_step_pct.
**How to avoid:** Tuning bounds clamp the DERIVED value, not the operator's configured value. If operator sets 2 and tuning derives 5, clamp to 3 (bounds min) but still enforce max_step_pct from operator's value (2).
**Warning signs:** Tuning adjusts to bounds min/max on first run regardless of current value.

## Code Examples

### TuningResult Model
```python
# Source: architecture research + SignalResult pattern (signal_processing.py:39)
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class TuningResult:
    """Result of a single parameter tuning analysis."""
    parameter: str        # e.g., "target_bloat_ms"
    old_value: float
    new_value: float
    confidence: float     # 0.0-1.0 based on data quantity
    rationale: str        # Human-readable for logs and health
    data_points: int      # Number of data points analyzed
    wan_name: str         # WAN this result applies to
```

### TuningConfig Model
```python
@dataclass(frozen=True, slots=True)
class SafetyBounds:
    """Min/max bounds for a tunable parameter."""
    min_value: float
    max_value: float

@dataclass(frozen=True, slots=True)
class TuningConfig:
    """Parsed and validated tuning configuration."""
    enabled: bool
    cadence_sec: int          # Default 3600
    lookback_hours: int       # Default 24
    warmup_hours: int         # Default 1
    max_step_pct: float       # Default 10.0
    bounds: dict[str, SafetyBounds]
```

### SQLite Schema for tuning_params
```sql
-- Source: architecture research; follows alerts table pattern (schema.py:61-80)
CREATE TABLE IF NOT EXISTS tuning_params (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    wan_name TEXT NOT NULL,
    parameter TEXT NOT NULL,
    old_value REAL NOT NULL,
    new_value REAL NOT NULL,
    confidence REAL NOT NULL,
    rationale TEXT,
    data_points INTEGER NOT NULL,
    reverted INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_tuning_timestamp
    ON tuning_params(timestamp);

CREATE INDEX IF NOT EXISTS idx_tuning_wan_param
    ON tuning_params(wan_name, parameter, timestamp);
```

### Persist Tuning Result
```python
# Source: alert_engine.py:188-201 INSERT INTO alerts pattern
def persist_tuning_result(
    result: TuningResult,
    writer: MetricsWriter | None,
) -> int | None:
    """Persist a tuning adjustment to SQLite for historical review."""
    if writer is None:
        return None
    try:
        ts = int(time.time())
        cursor = writer.connection.execute(
            "INSERT INTO tuning_params "
            "(timestamp, wan_name, parameter, old_value, new_value, "
            "confidence, rationale, data_points) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (ts, result.wan_name, result.parameter, result.old_value,
             result.new_value, result.confidence, result.rationale,
             result.data_points),
        )
        return cursor.lastrowid
    except Exception:
        logger.warning(
            "Failed to persist tuning result %s on %s",
            result.parameter, result.wan_name, exc_info=True,
        )
        return None
```

### Max Step Clamping
```python
# Source: architecture research ARCHITECTURE.md strategy pattern
def clamp_to_step(
    current: float,
    candidate: float,
    max_step_pct: float,
    bounds: SafetyBounds,
) -> float:
    """Clamp candidate to max step size and safety bounds."""
    # Clamp to safety bounds first
    clamped = max(bounds.min_value, min(bounds.max_value, candidate))

    # Enforce max step size from current value
    max_delta = current * (max_step_pct / 100.0)
    if max_delta < 0.001:
        max_delta = 0.001  # Prevent zero-delta for small values
    if abs(clamped - current) > max_delta:
        direction = 1 if clamped > current else -1
        clamped = current + max_delta * direction

    return round(clamped, 1)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual threshold tuning | Percentile-based derivation | v1.20 (this milestone) | Replaces guesswork with data-driven parameters |
| Static Hampel sigma 3.0 | Per-WAN sigma optimization | v1.20 Phase 101 | Different noise profiles per WAN get different filters |
| Fixed EWMA alpha | Settling-time-based alpha | v1.20 Phase 101 | Alpha adapts to each WAN's latency variance |

**Deprecated/outdated:**
- ML/scipy/numpy approaches: Explicitly out of scope. 6-8 scalar parameters don't justify ML complexity.
- Per-cycle adjustment: Explicitly excluded. Hourly cadence is a safety requirement.

## Open Questions

1. **Tuning state on WANController or separate object?**
   - What we know: WANController already has 20+ instance attributes. Adding tuning state (enabled, last_run, recent_adjustments) adds 3-5 more.
   - What's unclear: Whether to add directly to WANController or create a TuningState object held as `self._tuning_state`.
   - Recommendation: Use a TuningState frozen dataclass stored as `self._tuning_state` on WANController. Health endpoint reads it. Analyzer replaces it atomically. Keeps WANController attribute count manageable and follows the pattern of `_last_signal_result`, `_last_asymmetry_result`.

2. **Should stub strategy be included in Phase 98?**
   - What we know: Phase 98 is framework only. Strategies are Phases 99-102.
   - What's unclear: Whether to include a no-op stub strategy to prove end-to-end pipeline.
   - Recommendation: Include a simple "pass-through" strategy in tests only (not shipped code). Use it to verify the analyze->apply->persist->health pipeline works end-to-end.

3. **Tuning retention cleanup integration**
   - What we know: alerts have no explicit retention cleanup yet (they rely on the general metrics retention). The tuning_params table will be small (~8 rows/day per WAN).
   - What's unclear: Whether to add tuning_params cleanup now or defer.
   - Recommendation: Defer cleanup to a later phase. At ~16 rows/day (2 WANs), 30 days is only 480 rows. Not a concern until v1.21+.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `.venv/bin/pytest tests/test_tuning*.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TUNE-01 | Ships disabled, tuning_config=None when absent | unit | `.venv/bin/pytest tests/test_tuning_config.py -x` | Wave 0 |
| TUNE-02 | SIGUSR1 toggle enables/disables | unit | `.venv/bin/pytest tests/test_tuning_reload.py -x` | Wave 0 |
| TUNE-03 | Bounds parsed, validated, clamped | unit | `.venv/bin/pytest tests/test_tuning_models.py -x` | Wave 0 |
| TUNE-04 | Per-WAN independent analysis | unit | `.venv/bin/pytest tests/test_tuning_analyzer.py -x` | Wave 0 |
| TUNE-05 | Logging with old/new/rationale | unit | `.venv/bin/pytest tests/test_tuning_applier.py -x` | Wave 0 |
| TUNE-06 | Health endpoint tuning section | unit | `.venv/bin/pytest tests/test_tuning_health.py -x` | Wave 0 |
| TUNE-07 | Skip when < warmup_hours data | unit | `.venv/bin/pytest tests/test_tuning_analyzer.py -x` | Wave 0 |
| TUNE-08 | SQLite persistence | unit | `.venv/bin/pytest tests/test_tuning_persistence.py -x` | Wave 0 |
| TUNE-09 | Runs in maintenance window | unit | `.venv/bin/pytest tests/test_tuning_wiring.py -x` | Wave 0 |
| TUNE-10 | Max 10% step enforced | unit | `.venv/bin/pytest tests/test_tuning_applier.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_tuning*.py -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_tuning_config.py` -- covers TUNE-01, TUNE-03 (config parsing, bounds validation, warn+disable)
- [ ] `tests/test_tuning_models.py` -- covers TUNE-03, TUNE-10 (TuningResult, TuningConfig, SafetyBounds, clamp_to_step)
- [ ] `tests/test_tuning_analyzer.py` -- covers TUNE-04, TUNE-07 (per-WAN query, warmup check, strategy orchestration)
- [ ] `tests/test_tuning_applier.py` -- covers TUNE-05, TUNE-10 (bounds enforcement, max step, logging)
- [ ] `tests/test_tuning_persistence.py` -- covers TUNE-08 (SQLite insert, schema creation, query)
- [ ] `tests/test_tuning_health.py` -- covers TUNE-06 (health endpoint tuning section, enabled/disabled/active states)
- [ ] `tests/test_tuning_reload.py` -- covers TUNE-02 (SIGUSR1 enable/disable, old->new transition logging)
- [ ] `tests/test_tuning_wiring.py` -- covers TUNE-09 (maintenance window integration, cadence tracking)
- [ ] `conftest.py` update -- add `tuning_config` to `mock_autorate_config` fixture (explicit `None`)

## Sources

### Primary (HIGH confidence)
- Direct source: `autorate_continuous.py` -- Config class (line 127), WANController (line 1306), maintenance window (line 3505), SIGUSR1 handler (line 3543)
- Direct source: `health_check.py` -- HealthCheckHandler._get_health_status() fusion/alerting patterns
- Direct source: `storage/schema.py` -- ALERTS_SCHEMA, BENCHMARKS_SCHEMA, REFLECTOR_EVENTS_SCHEMA, create_tables()
- Direct source: `storage/reader.py` -- query_metrics(), select_granularity(), compute_summary()
- Direct source: `storage/writer.py` -- MetricsWriter singleton, write_metrics_batch()
- Direct source: `alert_engine.py` -- _persist_alert() INSERT INTO pattern
- Direct source: `signal_processing.py` -- SignalResult frozen dataclass, SignalProcessor config dict
- Direct source: `config_base.py` -- BaseConfig, validate_schema(), _load_specific_fields()
- Direct source: `tests/conftest.py` -- mock_autorate_config fixture pattern

### Secondary (MEDIUM confidence)
- `.planning/research/ARCHITECTURE.md` -- Tuning architecture, component boundaries, data flow
- `.planning/research/FEATURES.md` -- Feature landscape, MVP recommendation
- `.planning/research/PITFALLS.md` -- Domain pitfalls, phase-specific warnings
- `.planning/research/SUMMARY.md` -- Executive summary, stack decisions

### Tertiary (LOW confidence)
None -- all findings verified against source code.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- zero new dependencies, all patterns exist in codebase
- Architecture: HIGH -- every integration point verified against source code line numbers
- Pitfalls: HIGH -- grounded in 20 milestones of project experience, MagicMock trap well-documented
- Test infrastructure: HIGH -- pytest infrastructure established, conftest pattern clear

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (stable -- no external dependency version risk)
