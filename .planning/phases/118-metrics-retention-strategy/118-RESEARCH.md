# Phase 118: Metrics Retention Strategy - Research

**Researched:** 2026-03-27
**Domain:** SQLite metrics retention, config schema expansion, cross-section validation
**Confidence:** HIGH

## Summary

Phase 118 makes the currently-hardcoded downsampling thresholds and retention period operator-configurable via YAML, adds cross-section validation to prevent the tuner from losing data it needs (RETN-02), and introduces a prometheus_compensated mode for aggressive local retention when a long-term TSDB is available (RETN-03).

The codebase is well-structured for this change. The `DOWNSAMPLE_THRESHOLDS` dict in `downsampler.py` is already a parameterizable data structure -- converting it from module-level constants to config-driven values is straightforward. The `STORAGE_SCHEMA` in `config_base.py` follows the established list-of-dicts pattern and can be extended with new fields. The `deprecate_param()` utility in `config_validation_utils.py` exists specifically for migrating old config keys. Cross-section validation (reading both `storage.retention` and `tuning.lookback_hours` during config load) has no existing precedent in this codebase but follows naturally from the `validate_schema()` / `validate_field()` patterns.

**Primary recommendation:** Unified thresholds (each tier has one age_seconds that controls both "when to downsample" and "when to delete the source tier"), deprecate `storage.retention_days` via `deprecate_param()`, validate at config load and SIGUSR1 reload, and implement prometheus_compensated as a boolean modifier that pre-sets aggressive defaults with relaxed validation.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
None -- all implementation decisions are Claude's discretion.

### Claude's Discretion
- D-01: Unified vs separate downsample/delete thresholds
- D-02: Migration strategy for `storage.retention_days`
- D-03: YAML key naming conventions
- D-04: Validation timing and scope
- D-05: Whether validation checks YAML-declared `lookback_hours` only, or also reads persisted `tuning_params`
- D-06: Which tiers get shortened in `prometheus_compensated` mode
- D-07: Whether `prometheus_compensated` is a curated preset profile or a boolean modifier
- Internal refactoring of `DOWNSAMPLE_THRESHOLDS` constants in `downsampler.py`
- Test structure and fixture design
- Error message wording for validation failures

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RETN-01 | Retention thresholds configurable via `storage.retention` YAML section | Extend `STORAGE_SCHEMA` in `config_base.py`, make `DOWNSAMPLE_THRESHOLDS` config-driven, pass thresholds through `get_storage_config()` to both daemons |
| RETN-02 | Config validation enforces retention >= tuner lookback_hours data availability | Cross-section validation function in `config_validation_utils.py`, fires at config load + SIGUSR1; only checks YAML `lookback_hours` (not persisted tuning_params) |
| RETN-03 | Prometheus-compensated mode enables aggressive local retention (24-48h) when long-term TSDB is available | Boolean `prometheus_compensated` field relaxes validation constraints and provides aggressive defaults; does NOT shorten 1m tier below lookback_hours |

</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Production network control system -- change conservatively
- Priority: stability > safety > clarity > elegance
- Never refactor core logic, algorithms, thresholds, or timing without approval
- Portable Controller Architecture: all variability via config parameters (YAML)
- Zero new Python dependencies for this phase
- Tests: `.venv/bin/pytest tests/ -v`
- Linting: `.venv/bin/ruff check src/ tests/` and `.venv/bin/mypy src/wanctl/`
- Format: `.venv/bin/ruff format src/ tests/`

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12 | Runtime | Production deployment |
| sqlite3 | stdlib | Metrics database | Already in use, WAL mode |
| PyYAML | (existing) | Config loading | Already in use via config_base.py |
| pytest | 9.0.2 | Test framework | Already in venv |

### Supporting
No new libraries needed. All work uses existing stdlib and project infrastructure.

**Installation:** None required. Zero new dependencies.

## Architecture Patterns

### Recommended Project Structure (changes only)
```
src/wanctl/
  config_base.py              # Extend STORAGE_SCHEMA, expand get_storage_config()
  config_validation_utils.py  # Add validate_retention_tuner_compat()
  storage/
    downsampler.py            # Make DOWNSAMPLE_THRESHOLDS config-driven
    retention.py              # Accept per-granularity cutoffs (not just retention_days)
    maintenance.py            # Accept retention config dict (not just retention_days int)
  autorate_continuous.py      # Pass retention config, reload on SIGUSR1
  steering/daemon.py          # Pass retention config (must stay in sync)
tests/
  test_storage_retention.py   # Extend for per-granularity retention
  test_storage_downsampler.py # Extend for config-driven thresholds
  test_storage_maintenance.py # Extend for retention config dict
  test_config_validation_utils.py  # Add retention-tuner cross-validation tests
```

### Pattern 1: Config-Driven Thresholds (replacing hardcoded DOWNSAMPLE_THRESHOLDS)

**What:** Replace module-level `DOWNSAMPLE_THRESHOLDS` dict with a function that accepts config values and returns the same dict structure, falling back to current defaults when no config is provided.

**When to use:** Any function that currently imports `DOWNSAMPLE_THRESHOLDS` directly.

**Example:**
```python
# In downsampler.py -- new function
def get_downsample_thresholds(
    raw_age_seconds: int = 3600,
    aggregate_1m_age_seconds: int = 86400,
    aggregate_5m_age_seconds: int = 604800,
) -> dict[str, dict[str, int | str]]:
    """Build downsample thresholds from config or defaults."""
    return {
        "raw_to_1m": {
            "from_granularity": "raw",
            "to_granularity": "1m",
            "bucket_seconds": 60,
            "age_seconds": raw_age_seconds,
        },
        "1m_to_5m": {
            "from_granularity": "1m",
            "to_granularity": "5m",
            "bucket_seconds": 300,
            "age_seconds": aggregate_1m_age_seconds,
        },
        "5m_to_1h": {
            "from_granularity": "5m",
            "to_granularity": "1h",
            "bucket_seconds": 3600,
            "age_seconds": aggregate_5m_age_seconds,
        },
    }

# Keep DOWNSAMPLE_THRESHOLDS as default for backward compat
DOWNSAMPLE_THRESHOLDS = get_downsample_thresholds()
```

### Pattern 2: Cross-Section Config Validation

**What:** A validation function that reads two YAML sections (`storage.retention` and `tuning.lookback_hours`) and rejects configs where 1m aggregate lifetime is shorter than the tuner's lookback window.

**When to use:** At config load time and on SIGUSR1 reload.

**Example:**
```python
# In config_validation_utils.py
def validate_retention_tuner_compat(
    retention_config: dict,
    tuning_config: dict | None,
    logger: logging.Logger | None = None,
) -> None:
    """Validate retention config doesn't break tuner data availability.

    The tuner reads 1m-granularity data for lookback_hours * 3600 seconds.
    If aggregate_1m_age_seconds < lookback_hours * 3600, the tuner will
    silently get incomplete data and make bad decisions.
    """
    if tuning_config is None or not tuning_config.get("enabled", False):
        return  # No tuner, no constraint

    lookback_hours = tuning_config.get("lookback_hours", 24)
    lookback_seconds = lookback_hours * 3600

    agg_1m_age = retention_config.get("aggregate_1m_age_seconds", 86400)

    if agg_1m_age < lookback_seconds:
        raise ConfigValidationError(
            f"storage.retention.aggregate_1m_age_seconds ({agg_1m_age}s = "
            f"{agg_1m_age / 3600:.0f}h) is less than tuning.lookback_hours "
            f"({lookback_hours}h = {lookback_seconds}s). The tuner needs 1m "
            f"data for at least {lookback_hours} hours. Either increase "
            f"aggregate_1m_age_seconds or decrease lookback_hours."
        )
```

### Pattern 3: deprecate_param() for Backward Compatibility

**What:** Use the existing `deprecate_param()` helper to translate `storage.retention_days` to the new `storage.retention.aggregate_5m_age_seconds` (or nearest equivalent).

**When to use:** During config loading in `get_storage_config()`.

**Example:**
```python
# In config_base.py get_storage_config()
from wanctl.config_validation_utils import deprecate_param

storage = data.get("storage", {})
translated = deprecate_param(
    storage,
    old_key="retention_days",
    new_key="retention",
    logger=logger,
    transform_fn=lambda days: {
        "raw_age_seconds": 3600,       # 1 hour (unchanged default)
        "aggregate_1m_age_seconds": 86400,   # 1 day (unchanged default)
        "aggregate_5m_age_seconds": days * 86400,  # Convert days to seconds
    },
)
if translated is not None:
    storage["retention"] = translated
```

### Pattern 4: Prometheus-Compensated Mode

**What:** A boolean `prometheus_compensated` field under `storage.retention` that signals "Prometheus/TSDB handles long-term, keep local storage minimal." When enabled: raw=1h (unchanged), 1m=24h (shortened from default 1d), 5m=48h (shortened from default 7d). The RETN-02 validation is relaxed -- prometheus_compensated allows 1m age below lookback_hours (with a warning log instead of an error) because the operator is accepting that the tuner will rely on available data.

**When to use:** Operators who have deployed Phase 121 (Prometheus) and want to minimize local disk usage.

**Rationale for boolean modifier (not curated preset):** A preset implies operator cannot tweak individual values. A boolean modifier changes defaults and relaxes validation, but operators can still override individual thresholds. This gives maximum flexibility.

### Anti-Patterns to Avoid
- **Separate downsample and delete thresholds:** Doubles the config surface for no practical benefit. Downsampling already deletes the source data after aggregation. The age_seconds value controls when data transitions to the next tier -- there is no separate "keep the raw data but also have the aggregate" use case.
- **Reading tuning_params from metrics.db during config validation:** `lookback_hours` is NOT a tunable parameter in the tuning_params table (confirmed by grep). Only YAML values matter. Reading the DB during config load adds complexity and a potential failure mode for zero benefit.
- **Making SIGUSR1 reload retention a separate code path from config load:** Use the same validation function for both. The only difference is the trigger.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Config migration (retention_days -> retention section) | Custom migration logic | `deprecate_param()` in config_validation_utils.py | Already handles old->new key translation with warning logs |
| Config field validation | Custom type/range checks | `STORAGE_SCHEMA` + `validate_schema()` in config_base.py | Established pattern used by all other config sections |
| Watchdog-safe maintenance | Custom time tracking | Existing `max_seconds` + `watchdog_fn` params in retention.py/maintenance.py | Already battle-tested in production |

**Key insight:** Every infrastructure pattern needed for this phase already exists in the codebase. The phase is about wiring config values into existing machinery, not building new machinery.

## Common Pitfalls

### Pitfall 1: Breaking the Steering Daemon
**What goes wrong:** `autorate_continuous.py` and `steering/daemon.py` both call `run_startup_maintenance()` and the periodic maintenance loop. Changing the function signature in one but not the other causes the steering daemon to crash.
**Why it happens:** They have independent integration points with identical patterns.
**How to avoid:** Change `run_startup_maintenance()` to accept an optional retention config dict with a default fallback, preserving the existing `retention_days` parameter as deprecated. Both callers must be updated in the same plan.
**Warning signs:** Steering daemon tests fail or `grep` for `run_startup_maintenance` misses a call site.

### Pitfall 2: SIGUSR1 Reload Missing Retention
**What goes wrong:** Operator changes retention config in YAML and sends SIGUSR1, but the daemon keeps using the old retention values because the reload handler doesn't refresh the maintenance config.
**Why it happens:** The SIGUSR1 handler currently only reloads `dry_run`, `wan_state.enabled`, `webhook_url`, `fusion`, and `tuning` configs -- not storage/retention.
**How to avoid:** Add retention config reload to the SIGUSR1 handler. The `maintenance_retention_days` variable in the main loop must be updated.
**Warning signs:** Changing retention in YAML requires a full daemon restart to take effect.

### Pitfall 3: Config Validation Blocking Startup When Tuning is Disabled
**What goes wrong:** Cross-section validation rejects a config where 1m age < lookback_hours, even though tuning is disabled (so lookback_hours is irrelevant).
**Why it happens:** Validation doesn't check whether tuning is enabled before comparing thresholds.
**How to avoid:** Guard the cross-section check: skip when `tuning.enabled` is false or `tuning` section is absent.
**Warning signs:** Operators who don't use tuning get unexpected config validation errors.

### Pitfall 4: Downsampler Still Using Hardcoded DOWNSAMPLE_THRESHOLDS
**What goes wrong:** The periodic maintenance loop in `autorate_continuous.py` (line 3987) calls `downsample_metrics()` without passing config, so it uses the module-level default `DOWNSAMPLE_THRESHOLDS` instead of the operator's config.
**Why it happens:** `downsample_metrics()` currently takes no config argument -- it reads `DOWNSAMPLE_THRESHOLDS` at module scope.
**How to avoid:** Add an optional `thresholds` parameter to `downsample_metrics()` that falls back to the default. Pass the config-driven thresholds from both startup and periodic maintenance.
**Warning signs:** Operator configures custom thresholds but data still downsamples at default intervals.

### Pitfall 5: Prometheus-Compensated Mode Silently Breaking Tuner
**What goes wrong:** Operator enables prometheus_compensated with 24h 1m retention, but tuning.lookback_hours is 24h. The tuner gets exactly zero margin for timing drift, sometimes seeing 23.9h of data instead of 24h, causing intermittent warmup failures.
**Why it happens:** 1m age == lookback_hours has no safety margin.
**How to avoid:** When prometheus_compensated is true and 1m age < lookback_hours, log a WARNING but don't reject. When 1m age == lookback_hours (no prometheus_compensated), that's fine -- the check is strictly less-than.
**Warning signs:** Tuner sporadically logs "skipping, only X minutes of data" despite enough data existing.

## Code Examples

### Current YAML Config (before this phase)
```yaml
storage:
  retention_days: 7
  db_path: /var/lib/wanctl/metrics.db
```

### New YAML Config (after this phase)
```yaml
storage:
  db_path: /var/lib/wanctl/metrics.db
  retention:
    raw_age_seconds: 3600          # 1 hour (default)
    aggregate_1m_age_seconds: 86400   # 1 day (default)
    aggregate_5m_age_seconds: 604800  # 7 days (default)
    prometheus_compensated: false      # default
```

### Prometheus-Compensated Mode
```yaml
storage:
  db_path: /var/lib/wanctl/metrics.db
  retention:
    prometheus_compensated: true
    # Defaults when prometheus_compensated is true:
    #   raw_age_seconds: 3600        (1h, unchanged)
    #   aggregate_1m_age_seconds: 86400  (24h)
    #   aggregate_5m_age_seconds: 172800 (48h)
    # Operator can still override individual values
```

### Backward-Compatible Config (deprecated but works)
```yaml
storage:
  retention_days: 14  # Deprecated: translated to aggregate_5m_age_seconds: 1209600
  db_path: /var/lib/wanctl/metrics.db
```

### Error Message for RETN-02 Violation
```
Config validation failed: storage.retention.aggregate_1m_age_seconds (43200s = 12h)
is less than tuning.lookback_hours (24h = 86400s). The tuner needs 1m data for at
least 24 hours. Either increase aggregate_1m_age_seconds or decrease lookback_hours.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single `retention_days` int | Per-granularity age thresholds | This phase | Operators control each tier independently |
| Hardcoded `DOWNSAMPLE_THRESHOLDS` | Config-driven thresholds with defaults | This phase | Downsampling intervals match retention policy |
| No cross-section validation | storage vs tuning validation | This phase | Tuner data availability guaranteed |

## Open Questions

1. **Should the 1h granularity tier have a configurable age?**
   - What we know: Currently 1h data lives until final `retention_days` cleanup deletes it. There's no separate age threshold for 1h data.
   - What's unclear: Whether operators need to control 1h tier independently from the final retention horizon.
   - Recommendation: Omit for now. The 5m->1h threshold already controls when 5m data gets downsampled. The 1h data lifetime is implicitly "forever until something deletes it." If needed later, it's a one-line schema addition. Keep the config surface minimal.

2. **Should SIGUSR1 reload also update the periodic maintenance thresholds?**
   - What we know: The periodic maintenance loop in autorate_continuous.py uses `maintenance_retention_days` captured at startup.
   - What's unclear: Whether the variable is reassigned during SIGUSR1 handling.
   - Recommendation: Yes -- extend SIGUSR1 to reload retention config. The `maintenance_retention_days` variable (or its replacement) must be refreshed. This matches the principle that SIGUSR1 reloads all mutable config.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `.venv/bin/pytest tests/test_storage_retention.py tests/test_storage_downsampler.py tests/test_storage_maintenance.py tests/test_config_validation_utils.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RETN-01 | Per-granularity thresholds from YAML flow through to downsampler and retention cleanup | unit | `.venv/bin/pytest tests/test_storage_downsampler.py tests/test_storage_retention.py -x` | Exists (extend) |
| RETN-01 | `get_storage_config()` parses new retention section with defaults | unit | `.venv/bin/pytest tests/test_config_base.py -x -k retention` | Exists (extend) |
| RETN-01 | `deprecate_param()` translates `retention_days` to new structure | unit | `.venv/bin/pytest tests/test_config_validation_utils.py -x -k deprecate` | Exists (extend) |
| RETN-01 | Startup and periodic maintenance pass config-driven thresholds | unit | `.venv/bin/pytest tests/test_storage_maintenance.py -x` | Exists (extend) |
| RETN-02 | Config rejected when 1m age < lookback_hours * 3600 | unit | `.venv/bin/pytest tests/test_config_validation_utils.py -x -k retention_tuner` | Wave 0 |
| RETN-02 | Config accepted when 1m age >= lookback_hours * 3600 | unit | `.venv/bin/pytest tests/test_config_validation_utils.py -x -k retention_tuner` | Wave 0 |
| RETN-02 | Validation skipped when tuning disabled | unit | `.venv/bin/pytest tests/test_config_validation_utils.py -x -k retention_tuner` | Wave 0 |
| RETN-03 | prometheus_compensated=true sets aggressive defaults | unit | `.venv/bin/pytest tests/test_config_base.py -x -k prometheus` | Wave 0 |
| RETN-03 | prometheus_compensated relaxes validation (warning not error) | unit | `.venv/bin/pytest tests/test_config_validation_utils.py -x -k prometheus` | Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_storage_retention.py tests/test_storage_downsampler.py tests/test_storage_maintenance.py tests/test_config_validation_utils.py tests/test_config_base.py -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_config_validation_utils.py` -- add `TestValidateRetentionTunerCompat` class (covers RETN-02)
- [ ] `tests/test_config_base.py` -- add retention config parsing tests (covers RETN-01 schema expansion)
- [ ] `tests/test_config_validation_utils.py` -- add prometheus_compensated validation tests (covers RETN-03)

## Discretion Recommendations

Based on codebase analysis, here are the recommended decisions for Claude's discretion areas:

### D-01: Unified thresholds (recommended)
Each tier has one `age_seconds` value. When data is older than this age, it gets downsampled to the next tier AND the source data is deleted. This is already how the code works -- `downsample_to_granularity()` deletes originals after aggregation. Separate knobs would add config complexity with no behavioral difference.

### D-02: deprecate_param() migration (recommended)
Use the existing `deprecate_param()` pattern to translate `storage.retention_days` to `storage.retention`. This matches how `load_time_constant_sec` was migrated from `alpha`. The old field continues to work with a warning log. No breaking change.

### D-03: YAML key naming (use roadmap names)
Keep `raw_age_seconds`, `aggregate_1m_age_seconds`, `aggregate_5m_age_seconds` as specified in the roadmap. They match the `DOWNSAMPLE_THRESHOLDS` dict structure and are self-documenting. Add `prometheus_compensated` as a boolean.

### D-04: Validation at config load + SIGUSR1 (recommended)
Fire cross-section validation at config load (startup) and SIGUSR1 reload. At startup, a failure raises `ConfigValidationError` and blocks daemon start (safe -- operator must fix config). At SIGUSR1, a failure logs ERROR and keeps old config (safe -- daemon continues with previous good config).

### D-05: YAML-only validation (recommended)
`lookback_hours` is NOT stored in the `tuning_params` table (confirmed by code analysis). The tuning_params table only stores parameter adjustments like `target_bloat_ms`, `hampel_sigma`, etc. Validation only needs to read the YAML-declared `lookback_hours`.

### D-06: Shorten final tiers only in prometheus_compensated (recommended)
When `prometheus_compensated=true`: raw stays at 1h (ICMP and signal processing need recent data), 1m stays at 24h (tuner lookback default), 5m shortens to 48h (from 7d). This is the biggest disk savings with the least risk. The 1m tier must NOT go below `lookback_hours` unless operator explicitly overrides.

### D-07: Boolean modifier (recommended)
`prometheus_compensated: true` changes defaults and relaxes validation. Operators can still override individual age_seconds values. This is simpler than a curated preset and gives operators maximum control.

## Sources

### Primary (HIGH confidence)
- `src/wanctl/storage/downsampler.py` -- DOWNSAMPLE_THRESHOLDS structure, downsample_metrics() API
- `src/wanctl/storage/retention.py` -- cleanup_old_metrics() API, DEFAULT_RETENTION_DAYS
- `src/wanctl/storage/maintenance.py` -- run_startup_maintenance() API, integration pattern
- `src/wanctl/config_base.py` -- STORAGE_SCHEMA, get_storage_config(), validate_schema()
- `src/wanctl/config_validation_utils.py` -- deprecate_param(), cross-field validation patterns
- `src/wanctl/tuning/analyzer.py` -- _query_wan_metrics() reads 1m granularity with lookback_hours
- `src/wanctl/tuning/models.py` -- TuningConfig.lookback_hours (1-168, default 24)
- `src/wanctl/autorate_continuous.py` -- daemon integration: _init_storage(), SIGUSR1 handler, periodic maintenance

### Secondary (MEDIUM confidence)
- `configs/examples/spectrum-vm.yaml.example` -- production config structure with `lookback_hours: 24`

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all existing patterns
- Architecture: HIGH -- code read in full, all integration points mapped
- Pitfalls: HIGH -- each pitfall derives from specific code paths verified by grep

**Research date:** 2026-03-27
**Valid until:** indefinite (internal codebase patterns, no external dependency drift)
