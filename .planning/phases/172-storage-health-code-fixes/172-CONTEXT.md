# Phase 172: Storage Health & Code Fixes - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Shrink the 925 MB metrics DB through retention tuning and VACUUM, split to per-WAN DB files to eliminate write contention, fix the periodic maintenance CPython error, and make analyze_baseline.py deployable as a CLI entry point. This is a bugfix/operations phase -- no new features.

</domain>

<decisions>
## Implementation Decisions

### DB Reduction Strategy
- **D-01:** Raw cycle data retention set to 24 hours (raw_age_seconds=86400). Downsampled 1m/5m/1h aggregates retain longer history.
- **D-02:** Update production YAML configs (spectrum.yaml, att.yaml) to enforce 24h raw retention permanently. deploy.sh syncs config.
- **D-03:** One-shot manual VACUUM after the retention purge to reclaim space immediately. Then periodic maintenance handles future VACUUMs.
- **D-04:** No explicit DB size target -- trust the v1.34 storage pressure monitoring thresholds. 24h retention determines steady-state size.

### Write Contention
- **D-05:** Split to per-WAN DB files (metrics-spectrum.db, metrics-att.db). Each wanctl@{wan} service writes to its own DB. Eliminates cross-service lock contention entirely.
- **D-06:** CLI tools (wanctl-history, wanctl-operator-summary) attach both DBs and present unified/merged output. User doesn't need to specify which WAN.
- **D-07:** Fresh start migration -- new per-WAN DBs start empty after deploy. Old shared metrics.db archived but not migrated. 24h retention means historical data would be purged anyway.

### Maintenance Error Fix
- **D-08:** Wrap maintenance operations in try/except SystemError, log the error, retry once. If it persists, skip that maintenance cycle gracefully.
- **D-09:** Per-WAN DB split + 24h retention may also eliminate the root cause (smaller DBs, no contention during VACUUM). Monitor during Phase 174 soak.

### analyze_baseline Fix
- **D-10:** Promote analyze_baseline to a `wanctl-analyze-baseline` CLI entry point via pyproject.toml console_scripts. Follows the pattern of all other wanctl-* tools.

### Folded Todos
- **Investigate shared metrics.db write contention (3 writers)** -- addressed by D-05/D-06/D-07 (per-WAN DB split). Originally from backlog todo 2026-04-10.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Storage & Maintenance
- `src/wanctl/storage/maintenance.py` -- Startup and periodic maintenance entry points, VACUUM deferral logic
- `src/wanctl/storage/retention.py` -- Batch deletion, DEFAULT_RETENTION_DAYS=7, per-granularity cleanup
- `src/wanctl/storage/downsampler.py` -- Downsample thresholds and aggregation logic
- `src/wanctl/storage/writer.py` -- MetricsWriter singleton, DB connection management
- `src/wanctl/storage/schema.py` -- DB schema definitions
- `src/wanctl/storage/__init__.py` -- Storage module exports

### Runtime Pressure & Health
- `src/wanctl/runtime_pressure.py` -- DB size thresholds, WAL monitoring, RSS classification
- `src/wanctl/health_check.py` -- Health endpoint integrating storage pressure

### Daemon Integration
- `src/wanctl/autorate_continuous.py` -- Periodic maintenance scheduling (DEFAULT_MAINTENANCE_INTERVAL=900), maintenance_conn setup
- `src/wanctl/config_base.py` -- Storage config loading

### Deployment & Scripts
- `scripts/deploy.sh` -- ANALYSIS_SCRIPTS array listing analyze_baseline.py
- `scripts/analyze_baseline.py` -- The script with broken import path (to be promoted to entry point)

### Configuration
- `docs/CONFIGURATION.md` -- Storage and retention config reference

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `storage/retention.py:cleanup_old_metrics()` -- Already supports per-granularity cleanup via retention_config dict. Just needs correct raw_age_seconds passed.
- `storage/maintenance.py:maintenance_lock()` -- Context manager for cross-process lock. Will need adaptation for per-WAN DB paths.
- `runtime_pressure.py:get_storage_file_snapshot()` -- Already reads DB/WAL/SHM sizes. Will need to handle multiple DB files.

### Established Patterns
- Per-WAN state files already exist: `{wan}_state.json` -- DB split follows this convention
- CLI entry points defined in pyproject.toml `[project.scripts]` -- analyze_baseline follows same pattern
- MetricsWriter is a singleton with `_reset_instance()` for test isolation
- `atomic_write_json()` pattern for safe state persistence

### Integration Points
- `autorate_continuous.py:_init_maintenance_storage()` -- Where db_path is resolved from config. Must use per-WAN path.
- `pyproject.toml [project.scripts]` -- Add wanctl-analyze-baseline entry point
- `deploy.sh ANALYSIS_SCRIPTS` -- May need update or removal after entry point promotion
- Health endpoint `/health` -- Storage pressure section needs to report per-WAN DB sizes

</code_context>

<specifics>
## Specific Ideas

No specific requirements -- standard approaches guided by the decisions above.

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope.

### Reviewed Todos (not folded)
- **Monitor Proxmox steal CPU on cake-shaper VM** -- out of scope for storage/code fixes phase, belongs in infrastructure monitoring work

</deferred>

---

*Phase: 172-storage-health-code-fixes*
*Context gathered: 2026-04-12*
