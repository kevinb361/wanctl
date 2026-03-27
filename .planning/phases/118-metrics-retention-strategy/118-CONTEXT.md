# Phase 118: Metrics Retention Strategy - Context

**Gathered:** 2026-03-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Make all metrics.db retention and downsampling thresholds operator-configurable via YAML, with cross-section config validation that prevents tuner data availability from being silently broken. Add a Prometheus-compensated retention mode for aggressive local retention when long-term TSDB is available. Three requirements: configurable thresholds (RETN-01), tuner data availability validation (RETN-02), prometheus-compensated mode (RETN-03).

</domain>

<decisions>
## Implementation Decisions

### Retention Config Structure
- **D-01:** Claude's discretion on whether per-granularity thresholds control both downsampling AND deletion (unified) or are separate knobs. Choose based on operator simplicity and code complexity.
- **D-02:** Claude's discretion on backward compatibility for existing `storage.retention_days` field. Options: deprecate-and-translate (using existing `deprecate_param()` pattern), or clean break with clear error. Choose based on production safety and migration friction.
- **D-03:** Claude's discretion on YAML key naming. Roadmap suggests `raw_age_seconds`, `aggregate_1m_age_seconds`, `aggregate_5m_age_seconds` but Claude may adjust to fit codebase conventions as long as the same granularities are configurable.

### Validation Behavior
- **D-04:** Claude's discretion on when cross-section validation fires (config load only, config load + SIGUSR1 reload, or config load + runtime warning). Hard constraint: RETN-02 requires that retention configs where 1m data lifetime < `tuning.lookback_hours * 3600` are rejected with a clear error message.
- **D-05:** Claude's discretion on whether validation checks YAML-declared `lookback_hours` only, or also reads persisted `tuning_params` from metrics.db to validate against the effective lookback value.

### Prometheus-Compensated Mode
- **D-06:** Claude's discretion on which tiers get shortened in `prometheus_compensated` mode (all tiers compressed, or only final retention horizon). Choose based on actual disk usage breakdown and tuner data safety.
- **D-07:** Claude's discretion on whether `prometheus_compensated` is a curated preset profile or a boolean modifier that relaxes validation constraints so operators can set shorter thresholds. Choose based on operator UX.

### Claude's Discretion
- Unified vs separate downsample/delete thresholds (D-01)
- Migration strategy for `storage.retention_days` (D-02)
- YAML key naming conventions (D-03)
- Validation timing and scope (D-04, D-05)
- Prometheus-compensated mode design (D-06, D-07)
- Internal refactoring of `DOWNSAMPLE_THRESHOLDS` constants in `downsampler.py`
- Test structure and fixture design
- Error message wording for validation failures

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Storage Module (primary modification target)
- `src/wanctl/storage/retention.py` -- `cleanup_old_metrics()` with DEFAULT_RETENTION_DAYS=7, batch delete, VACUUM threshold
- `src/wanctl/storage/downsampler.py` -- `DOWNSAMPLE_THRESHOLDS` dict (hardcoded: raw 1h, 1m 1d, 5m 7d), `downsample_metrics()` orchestrator
- `src/wanctl/storage/maintenance.py` -- `run_startup_maintenance()` orchestrating cleanup + downsample with watchdog/time budget
- `src/wanctl/storage/writer.py` -- `MetricsWriter` singleton, `DEFAULT_DB_PATH`, WAL mode

### Config Infrastructure
- `src/wanctl/config_base.py` -- `STORAGE_SCHEMA` (lines 120-135), `get_storage_config()` (lines 138-153), `validate_schema()` pattern
- `src/wanctl/config_validation_utils.py` -- `deprecate_param()` (lines 22-58), cross-field validation patterns

### Tuner Data Access (must not break)
- `src/wanctl/tuning/analyzer.py` -- `_query_wan_metrics()` reads 1m granularity with `lookback_hours * 3600` window; `_check_warmup()` for data sufficiency

### Daemon Integration Points
- `src/wanctl/autorate_continuous.py` -- Startup maintenance call (line 3684), `MAINTENANCE_INTERVAL` hourly (line 103), `maintenance_retention_days` variable
- `src/wanctl/steering/daemon.py` -- Startup maintenance call (line 2238)

### Database Schema
- `src/wanctl/storage/schema.py` -- Metrics table with `granularity` column, indexes for time + granularity queries
- `src/wanctl/storage/reader.py` -- Read-only `query_metrics()` with granularity filter

### Existing Tests
- `tests/test_storage_retention.py` -- Cleanup tests
- `tests/test_storage_downsampler.py` -- Downsampling tests
- `tests/test_storage_maintenance.py` -- Startup maintenance tests
- `tests/test_config_validation_utils.py` -- Validation function tests

### Config Examples
- `configs/examples/spectrum-vm.yaml.example` -- Production-like config with `lookback_hours: 24`
- `configs/examples/att-vm.yaml.example` -- Secondary WAN config with tuning section

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `deprecate_param()` in `config_validation_utils.py` -- Warn+translate helper for config migrations (if deprecation approach chosen)
- `validate_schema()` in `config_base.py` -- Schema-driven validation with type/range/required checks
- `DOWNSAMPLE_THRESHOLDS` dict in `downsampler.py` -- Already structured as parameterizable dict, easy to make config-driven
- `get_storage_config()` in `config_base.py` -- Extraction point for storage config, needs expansion for new fields

### Established Patterns
- Config schemas defined as list-of-dicts in `config_base.py` with `path`, `type`, `required`, `default`, `min`, `max`
- Cross-section config access via `data.get("section", {})` pattern
- SIGUSR1 reload already reloads `dry_run`, `wan_state.enabled`, `webhook_url`, `fusion` config -- can extend to retention
- Hardcoded constants as module-level dicts (`DOWNSAMPLE_THRESHOLDS`) -- refactoring to config-driven is straightforward

### Integration Points
- `autorate_continuous.py` passes `maintenance_retention_days` to startup maintenance -- needs to pass new retention config structure
- `steering/daemon.py` has identical maintenance integration -- must stay in sync
- `STORAGE_SCHEMA` in `config_base.py` -- add new retention fields here
- `get_storage_config()` return dict -- expand to include per-granularity thresholds

### Key Constraint: 500MB/day Growth
- metrics.db hit 521MB after 25 hours at 50ms cycle interval
- Disk fills in ~50 days with current 7-day retention
- This phase is the fix -- aggressive downsampling and configurable retention are the path to sustainable disk usage

</code_context>

<specifics>
## Specific Ideas

- The tuning engine ONLY reads 1m granularity -- this is the critical tier for RETN-02 validation
- `tuning_params` table in metrics.db persists tuner overrides including potentially `lookback_hours` -- may need to factor into validation
- Production uses system Python (no venv) -- any new dependencies would need system-level install (but this phase needs zero new deps)
- The `DOWNSAMPLE_THRESHOLDS` dict is already structured for parameterization -- keys map cleanly to config hierarchy

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 118-metrics-retention-strategy*
*Context gathered: 2026-03-27*
