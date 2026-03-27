---
phase: 118-metrics-retention-strategy
verified: 2026-03-27T17:30:00Z
status: passed
score: 13/13 must-haves verified
re_verification: false
---

# Phase 118: Metrics Retention Strategy Verification Report

**Phase Goal:** Operators can configure metrics.db retention thresholds and the system enforces that tuner data availability is never silently broken
**Verified:** 2026-03-27T17:30:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `get_storage_config()` returns per-granularity retention thresholds with defaults | VERIFIED | `config_base.py` returns `retention` dict with `raw_age_seconds=3600`, `aggregate_1m_age_seconds=86400`, `aggregate_5m_age_seconds=604800`; 12 tests pass |
| 2 | Old `storage.retention_days` YAML is translated via `deprecate_param()` | VERIFIED | Lazy import `from wanctl.config_validation_utils import deprecate_param` inside `get_storage_config()` at line 185; test `test_deprecated_retention_days_translates` passes |
| 3 | Config is rejected when `aggregate_1m_age_seconds < lookback_hours * 3600` and tuning is enabled | VERIFIED | `validate_retention_tuner_compat()` raises `ConfigValidationError` with message containing both field names; test `test_rejects_insufficient_retention` passes |
| 4 | Config is accepted when tuning is disabled regardless of retention values | VERIFIED | Early return when `tuning_config is None or not tuning_config.get("enabled", False)`; tests `test_skips_when_tuning_disabled` and `test_skips_when_tuning_none` pass |
| 5 | `prometheus_compensated=true` sets aggressive defaults (5m: 48h) and downgrades validation error to warning | VERIFIED | `config_base.py` sets `default_5m=172800` when `prometheus_compensated`; `validate_retention_tuner_compat()` calls `logger.warning()` instead of raising; tests pass |
| 6 | `downsample_metrics()` accepts optional `thresholds` parameter and uses it | VERIFIED | Signature `thresholds: dict[str, dict[str, int \| str]] \| None = None`; `effective_thresholds = thresholds if thresholds is not None else DOWNSAMPLE_THRESHOLDS` at line 271; tests pass |
| 7 | Startup maintenance uses config-driven retention thresholds | VERIFIED | `_init_storage()` extracts `retention_config`, calls `run_startup_maintenance(conn, retention_config=maintenance_retention_config, ...)` |
| 8 | Periodic hourly maintenance uses config-driven thresholds for both cleanup and downsampling | VERIFIED | Periodic block calls `cleanup_old_metrics(maintenance_conn, retention_config=maintenance_retention_config, ...)` and `downsample_metrics(..., thresholds=custom_thresholds)` |
| 9 | SIGUSR1 reload refreshes retention config with validation guard | VERIFIED | SIGUSR1 block at line 4232: calls `get_storage_config()` + `validate_retention_tuner_compat()`, catches `ConfigValidationError` and keeps old config on failure |
| 10 | `cleanup_old_metrics()` deletes data per-granularity based on retention config | VERIFIED | `_cleanup_per_granularity()` builds `tier_cutoffs` dict with tier-specific ages, uses `WHERE granularity = ? AND timestamp < ?` per tier; 8 tests pass |
| 11 | Steering daemon passes retention config to `run_startup_maintenance()` identically to autorate | VERIFIED | `steering/daemon.py` extracts `retention_config = storage_config.get("retention")`, calls `validate_retention_tuner_compat()`, then `run_startup_maintenance(writer.connection, retention_config=retention_config, ...)` |
| 12 | Example configs document `storage.retention` section | VERIFIED | Both `configs/examples/spectrum-vm.yaml.example` and `configs/examples/att-vm.yaml.example` contain `aggregate_1m_age_seconds`, `aggregate_5m_age_seconds`, and commented `prometheus_compensated` |
| 13 | Cross-section validation fires at config load (blocks startup) and SIGUSR1 (logs error, keeps old config) | VERIFIED | Startup: raises `ConfigValidationError` (propagates up to block daemon start). SIGUSR1: catches `ConfigValidationError`, logs error, retains previous `maintenance_retention_config` |

**Score:** 13/13 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/wanctl/config_base.py` | Extended STORAGE_SCHEMA and `get_storage_config()` with retention section | VERIFIED | STORAGE_SCHEMA has 4 new entries (`storage.retention.raw_age_seconds`, `storage.retention.aggregate_1m_age_seconds`, `storage.retention.aggregate_5m_age_seconds`, `storage.retention.prometheus_compensated`); `get_storage_config()` returns `retention` dict |
| `src/wanctl/config_validation_utils.py` | `validate_retention_tuner_compat()` cross-section validation | VERIFIED | Function defined at line 61 with correct signature; raises `ConfigValidationError` with both field names in message; handles `prometheus_compensated` as warning |
| `src/wanctl/storage/downsampler.py` | `get_downsample_thresholds()` factory and config-driven `downsample_metrics()` | VERIFIED | Factory defined above `DOWNSAMPLE_THRESHOLDS` constant; `DOWNSAMPLE_THRESHOLDS = get_downsample_thresholds()` preserves backward compat; `downsample_metrics` accepts `thresholds` param |
| `src/wanctl/storage/retention.py` | Per-granularity cleanup via `retention_config` dict | VERIFIED | `cleanup_old_metrics()` has `retention_config: dict \| None = None` param; dispatches to `_cleanup_per_granularity()` when provided |
| `src/wanctl/storage/maintenance.py` | Config-driven maintenance accepting `retention_config` dict | VERIFIED | `run_startup_maintenance()` has `retention_config: dict \| None = None`; imports and uses `get_downsample_thresholds`; passes `thresholds=` to `downsample_metrics()` |
| `src/wanctl/autorate_continuous.py` | Daemon wiring for retention config, SIGUSR1 reload, periodic maintenance | VERIFIED | `validate_retention_tuner_compat` imported at top; `maintenance_retention_config` used throughout; SIGUSR1 block reloads and validates |
| `configs/examples/spectrum-vm.yaml.example` | Example config with `storage.retention` section | VERIFIED | Contains `aggregate_1m_age_seconds: 86400`, `aggregate_5m_age_seconds: 604800`, commented `prometheus_compensated` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `config_base.py` | `config_validation_utils.py` | `deprecate_param()` call in `get_storage_config()` | WIRED | Lazy import at line 185; `deprecate_param(storage, old_key="retention_days", new_key="retention", ...)` |
| `config_base.py` | `storage/downsampler.py` | `retention` config dict feeds `get_downsample_thresholds()` | WIRED | `maintenance.py` and daemon code call `get_downsample_thresholds(raw_age_seconds=retention_config["raw_age_seconds"], ...)` |
| `autorate_continuous.py` | `config_base.py` | `get_storage_config()` returning retention dict | WIRED | Imported at top (line 25); called in `_init_storage()` and SIGUSR1 block |
| `autorate_continuous.py` | `storage/downsampler.py` | `get_downsample_thresholds()` called with retention config values | WIRED | Local import at line 3997-4000; called at line 4010 with config values |
| `autorate_continuous.py` | `config_validation_utils.py` | `validate_retention_tuner_compat()` at startup and SIGUSR1 | WIRED | Imported at line 29; called at startup (line 3688) and SIGUSR1 block (line 4236) |
| `autorate_continuous.py` | `storage/retention.py` | `cleanup_old_metrics()` with `retention_config` dict | WIRED | Local import in periodic block; called with `retention_config=maintenance_retention_config` |
| `steering/daemon.py` | `storage/maintenance.py` | `run_startup_maintenance()` with `retention_config` | WIRED | Local import at line 2251; called with `retention_config=retention_config` at line 2257 |

### Data-Flow Trace (Level 4)

These artifacts are daemon wiring code, not UI/rendering components. Data flows through configuration at load time rather than rendering dynamic visual data. The critical data flow is: YAML file -> `get_storage_config()` -> `retention_config` dict -> cleanup/downsampler calls. All traced and verified above via grep.

### Behavioral Spot-Checks

Static analysis only — daemon code requires a running service. Key behavioral invariants verified via unit tests:

| Behavior | Verified Via | Status |
|----------|-------------|--------|
| Default retention thresholds returned from empty config | `TestGetStorageConfigRetention::test_empty_config_returns_default_retention` | PASS |
| Insufficient 1m retention raises `ConfigValidationError` | `TestValidateRetentionTunerCompat::test_rejects_insufficient_retention` | PASS |
| `prometheus_compensated` sets 48h 5m default | `TestGetStorageConfigRetention::test_prometheus_compensated_defaults` | PASS |
| Per-granularity cleanup only deletes correct tier | `TestCleanupPerGranularity::test_retention_config_only_deletes_correct_granularity` | PASS |
| `downsample_metrics` uses custom thresholds when provided | `TestDownsampleMetricsWithThresholds::test_custom_thresholds_used` | PASS |
| Maintenance passes retention_config to both cleanup and downsampler | `TestStartupMaintenanceRetentionConfig::test_retention_config_passed_to_cleanup` | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| RETN-01 | 118-01, 118-02 | Retention thresholds configurable via `storage.retention` YAML section | SATISFIED | STORAGE_SCHEMA extended; `get_storage_config()` returns per-granularity dict; both daemons wire thresholds into cleanup and downsampler at startup and periodic maintenance |
| RETN-02 | 118-01, 118-02 | Config validation enforces retention >= tuner lookback_hours data availability | SATISFIED | `validate_retention_tuner_compat()` raises `ConfigValidationError` at startup (blocks daemon start); SIGUSR1 reload catches error and keeps old config |
| RETN-03 | 118-01, 118-02 | Prometheus-compensated mode enables aggressive local retention (24-48h) | SATISFIED | `prometheus_compensated=True` sets 5m default to 172800 (48h); relaxes `validate_retention_tuner_compat()` to `logger.warning()` instead of raising |

No orphaned requirements — all three RETN-0x IDs appear in both plan `requirements` fields and REQUIREMENTS.md maps all three to Phase 118.

### Anti-Patterns Found

None detected. Scan of all 7 modified source files found:
- No TODO/FIXME/PLACEHOLDER comments
- No stub implementations (`return null`, `return []`, empty handlers)
- No hardcoded empty data in rendering paths
- Ruff linting passes clean on all modified files

### Human Verification Required

1. **SIGUSR1 reload behavior on live daemon**
   - **Test:** Edit `/etc/wanctl/spectrum.yaml` to set `storage.retention.aggregate_1m_age_seconds: 43200` (insufficient for 24h lookback), then send `kill -USR1 <wanctl-pid>`
   - **Expected:** Error logged: "Retention config reload failed, keeping previous config: ..." and old retention config remains active
   - **Why human:** Requires running production daemon and YAML edit

2. **Startup blocking on dangerous config**
   - **Test:** Set `storage.retention.aggregate_1m_age_seconds: 3600` with `tuning.enabled: true` and `tuning.lookback_hours: 24`, then start the daemon
   - **Expected:** Daemon fails to start with `ConfigValidationError` logged; systemd shows failed unit
   - **Why human:** Requires live systemd service restart

3. **`prometheus_compensated` end-to-end YAML effect**
   - **Test:** Set `storage.retention.prometheus_compensated: true` in YAML with `tuning.lookback_hours: 24` and `aggregate_1m_age_seconds: 43200`, then start daemon
   - **Expected:** Daemon starts successfully; warning logged about insufficient retention but operation continues
   - **Why human:** Requires live daemon start to confirm warning appears in journalctl

### Gaps Summary

No gaps found. All 13 observable truths verified, all 7 artifacts exist at full implementation depth (not stubs), all 7 key links are wired, all 3 requirements satisfied, and ruff is clean across all modified files.

---

_Verified: 2026-03-27T17:30:00Z_
_Verifier: Claude (gsd-verifier)_
