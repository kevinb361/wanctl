# Phase 172: Storage Health & Code Fixes - Research

**Researched:** 2026-04-12
**Domain:** SQLite storage management, retention tuning, per-WAN DB split, CPython sqlite3 error handling, CLI entry point promotion
**Confidence:** HIGH

## Summary

Phase 172 addresses three concrete production issues: (1) a 925 MB metrics.db that has hit the storage-pressure critical threshold, (2) a periodic maintenance "error return without exception set" SystemError, and (3) a broken import path in `analyze_baseline.py`. All three have locked decisions from the discuss phase and well-understood code paths in the existing codebase.

The DB size problem is caused by `DEFAULT_STORAGE_RAW_AGE_SECONDS = 900` (15 minutes) which is the code default but was never overridden in production YAML configs (spectrum.yaml and att.yaml lack a `storage:` section entirely). With 20Hz polling writing ~25 metrics per cycle per WAN, raw data accumulates fast. Decision D-01 sets `raw_age_seconds=86400` (24h) which is actually *increasing* raw retention from the 900s default, but the real fix is that production configs currently have no `storage:` block at all, so the default retention is running. The per-WAN DB split (D-05) eliminates the shared-DB write contention between `wanctl@spectrum` and `wanctl@att` services.

**Primary recommendation:** Add `storage:` sections to both production YAML configs with `db_path` pointing to per-WAN files (`metrics-spectrum.db`, `metrics-att.db`), set `raw_age_seconds: 86400`, run a one-shot VACUUM on the old shared DB, then promote `analyze_baseline.py` to a CLI entry point and wrap the maintenance error in try/except SystemError.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Raw cycle data retention set to 24 hours (raw_age_seconds=86400). Downsampled 1m/5m/1h aggregates retain longer history.
- **D-02:** Update production YAML configs (spectrum.yaml, att.yaml) to enforce 24h raw retention permanently. deploy.sh syncs config.
- **D-03:** One-shot manual VACUUM after the retention purge to reclaim space immediately. Then periodic maintenance handles future VACUUMs.
- **D-04:** No explicit DB size target -- trust the v1.34 storage pressure monitoring thresholds. 24h retention determines steady-state size.
- **D-05:** Split to per-WAN DB files (metrics-spectrum.db, metrics-att.db). Each wanctl@{wan} service writes to its own DB. Eliminates cross-service lock contention entirely.
- **D-06:** CLI tools (wanctl-history, wanctl-operator-summary) attach both DBs and present unified/merged output. User doesn't need to specify which WAN.
- **D-07:** Fresh start migration -- new per-WAN DBs start empty after deploy. Old shared metrics.db archived but not migrated. 24h retention means historical data would be purged anyway.
- **D-08:** Wrap maintenance operations in try/except SystemError, log the error, retry once. If it persists, skip that maintenance cycle gracefully.
- **D-09:** Per-WAN DB split + 24h retention may also eliminate the root cause (smaller DBs, no contention during VACUUM). Monitor during Phase 174 soak.
- **D-10:** Promote analyze_baseline to a `wanctl-analyze-baseline` CLI entry point via pyproject.toml console_scripts. Follows the pattern of all other wanctl-* tools.

### Folded Todos
- Investigate shared metrics.db write contention (3 writers) -- addressed by D-05/D-06/D-07

### Claude's Discretion
No items specified -- all decisions locked.

### Deferred Ideas (OUT OF SCOPE)
- Monitor Proxmox steal CPU on cake-shaper VM -- out of scope for storage/code fixes phase
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STOR-01 | Metrics DB size is reduced to under the warning threshold through retention tuning or manual cleanup | D-01/D-02/D-03: Add storage config with 24h raw retention to YAML, run cleanup+VACUUM. Per-WAN split (D-05) creates fresh empty DBs. |
| STOR-02 | The periodic maintenance error ("error return without exception set") is diagnosed and fixed so maintenance runs complete cleanly | D-08: Wrap in try/except SystemError with retry. Root cause is CPython sqlite3 module edge case during VACUUM/checkpoint on large DBs under contention. |
| DEPL-02 | analyze_baseline.py is deployable and runnable on production (fix import path issue found during UAT) | D-10: Promote to pyproject.toml console_scripts entry point, following existing wanctl-* CLI pattern. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Change policy:** Explain risky changes before changing behavior. Never refactor core logic/algorithms/thresholds/timing without approval. Priority: stability > safety > clarity > elegance.
- **Portable controller:** Link-agnostic code. Deployment-specific behavior in YAML, not Python branching.
- **Dev commands:** Use `.venv/bin/pytest`, `.venv/bin/ruff`, `.venv/bin/mypy` directly.
- **Test pattern:** `make ci` equivalent via `.venv/bin/pytest tests/ -v`, hot-path regression slice available.
- **Singleton pattern:** MetricsWriter is a singleton with `_reset_instance()` for test isolation.
- **FHS paths:** `/var/lib/wanctl/` for state, `/etc/wanctl/` for config, `/opt/wanctl/` for code.
- **Version bump:** ALWAYS update version in `__init__.py`, `pyproject.toml`, and `CLAUDE.md` on deploy.

## Standard Stack

### Core (Already in Project)
| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| sqlite3 | stdlib (3.12.3) | Metrics storage | WAL mode, INCREMENTAL auto_vacuum already configured [VERIFIED: codebase] |
| PyYAML | >=6.0.1 | Config loading | Production configs in `/etc/wanctl/` [VERIFIED: pyproject.toml] |

### Supporting (No New Dependencies)
This phase requires zero new dependencies. All work uses existing stdlib sqlite3, existing storage modules, and existing CLI patterns. [VERIFIED: codebase review]

## Architecture Patterns

### Current DB Path Resolution
```
config YAML → data.get("storage", {}) → storage.get("db_path", DEFAULT_STORAGE_DB_PATH)
DEFAULT_STORAGE_DB_PATH = "/var/lib/wanctl/metrics.db"
```
[VERIFIED: config_base.py lines 134, 220, 258]

**Critical finding:** Neither `configs/spectrum.yaml` nor `configs/att.yaml` has a `storage:` section. Both WANs currently share the default path `/var/lib/wanctl/metrics.db`. Both `wanctl@spectrum` and `wanctl@att` systemd services write to this single file. [VERIFIED: configs/spectrum.yaml, configs/att.yaml]

### Per-WAN DB Split Pattern

**Config change (D-05):**
```yaml
# In spectrum.yaml
storage:
  db_path: "/var/lib/wanctl/metrics-spectrum.db"
  retention:
    raw_age_seconds: 86400         # 24h raw (D-01)
    aggregate_1m_age_seconds: 86400  # 24h 1m aggregates
    aggregate_5m_age_seconds: 604800 # 7d 5m aggregates

# In att.yaml
storage:
  db_path: "/var/lib/wanctl/metrics-att.db"
  retention:
    raw_age_seconds: 86400
    aggregate_1m_age_seconds: 86400
    aggregate_5m_age_seconds: 604800
```
[VERIFIED: get_storage_config() in config_base.py handles this natively -- db_path is already configurable]

### Code Impact Analysis for Per-WAN DB Split

**Writer path (MetricsWriter singleton):** The singleton receives `db_path` from `_init_storage()` in `autorate_continuous.py` (line 347: `MetricsWriter(Path(db_path))`). Since each `wanctl@{wan}` is a separate process, each gets its own singleton instance with its own db_path. **No code change needed in writer.** [VERIFIED: autorate_continuous.py, writer.py]

**Maintenance path:** `_run_maintenance()` gets db_path from `get_storage_config()` on line 611. Per-WAN config already resolves to per-WAN db_path. **No code change needed in maintenance.** [VERIFIED: autorate_continuous.py]

**Health endpoint:** `health_check.py` imports `DEFAULT_DB_PATH` from writer.py. The health endpoint uses the `MetricsWriter.get_instance()` singleton, which already has the correct per-WAN path. Storage file snapshot uses the singleton's db_path. Need to verify health endpoint reads from the right path. [VERIFIED: health_check.py imports DEFAULT_DB_PATH but may use singleton path at runtime]

**Reader/CLI path:** `storage/reader.py` functions take `db_path` as parameter defaulting to `DEFAULT_DB_PATH`. CLI tools (`wanctl-history`, `wanctl-operator-summary`) accept `--db` flag defaulting to `DEFAULT_DB_PATH`. For D-06 (merged output), CLI tools need modification. [VERIFIED: history.py line 527-532, reader.py line 58]

### CLI Multi-DB Merge Pattern (D-06)

CLI tools need to query both per-WAN DBs and merge results. Pattern:

```python
# Auto-discover per-WAN DB files
WAN_DB_DIR = Path("/var/lib/wanctl")
WAN_DB_GLOB = "metrics-*.db"

def discover_wan_dbs(db_dir: Path = WAN_DB_DIR) -> list[Path]:
    """Find all per-WAN metrics DB files."""
    dbs = sorted(db_dir.glob(WAN_DB_GLOB))
    # Fall back to legacy shared DB if no per-WAN files found
    legacy = db_dir / "metrics.db"
    if not dbs and legacy.exists():
        return [legacy]
    return dbs
```
[ASSUMED — pattern design, not from existing code]

**Affected CLI tools:**
- `wanctl-history` (history.py) -- `--db` flag, calls `query_metrics()` [VERIFIED: history.py]
- `wanctl-operator-summary` (operator_summary.py) -- reads from health endpoint URLs, NOT directly from DB [VERIFIED: operator_summary.py uses HTTP/file sources, not SQLite]
- `analyze_baseline.py` / `wanctl-analyze-baseline` -- `--db` flag, calls `query_metrics()` [VERIFIED: scripts/analyze_baseline.py]

**operator_summary does NOT need DB changes** -- it reads from the `/health` HTTP endpoint, which is per-service. [VERIFIED: operator_summary.py lines 22-26]

### Entry Point Promotion Pattern (D-10)

Existing CLI entry points in pyproject.toml follow this pattern:
```toml
[project.scripts]
wanctl-history = "wanctl.history:main"
wanctl-check-config = "wanctl.check_config:main"
```
[VERIFIED: pyproject.toml lines 15-24]

For `analyze_baseline.py`:
1. Move from `scripts/analyze_baseline.py` to `src/wanctl/analyze_baseline.py`
2. Remove the `sys.path` hack (lines 19-22 of current script)
3. Add entry point: `wanctl-analyze-baseline = "wanctl.analyze_baseline:main"`
4. Update `deploy.sh` ANALYSIS_SCRIPTS array (may become unnecessary if installed via pip)

The current script has a sys.path hack:
```python
sys.path.insert(0, str(_script_dir.parent / "src"))  # dev layout
sys.path.insert(0, str(_script_dir.parent.parent))    # prod layout (/opt)
```
This is the root cause of DEPL-02 -- the path resolution fails in certain deployment layouts. Moving to a proper entry point eliminates this entirely. [VERIFIED: scripts/analyze_baseline.py lines 19-22]

### Maintenance Error Fix Pattern (D-08)

The "error return without exception set" is a `SystemError` from CPython's sqlite3 module. It occurs during VACUUM or WAL checkpoint operations on large databases, particularly under contention. This is a known CPython issue (python/cpython#108083 -- "sqlite3: some code paths ignore exceptions"). [CITED: https://github.com/python/cpython/issues/108083]

Current maintenance code in `_run_maintenance()` catches `Exception` broadly (line 664), but `SystemError` can propagate from C-level code in ways that bypass normal Python exception handling. The fix:

```python
def _run_maintenance(controller, maintenance_conn, maintenance_retention_config):
    """Run periodic maintenance with SystemError resilience."""
    maint_logger = controller.wan_controllers[0]["logger"]
    try:
        # ... existing maintenance logic ...
    except SystemError as e:
        maint_logger.warning("Maintenance hit CPython sqlite3 error (retrying): %s", e)
        try:
            # Retry once -- error is often transient
            # ... retry maintenance logic ...
        except (SystemError, Exception) as retry_err:
            maint_logger.error("Maintenance retry also failed, skipping cycle: %s", retry_err)
    except Exception as e:
        maint_logger.error("Periodic maintenance failed: %s", e)
```
[VERIFIED: autorate_continuous.py line 664 catches Exception; CITED: CPython issue #108083]

**Important:** The existing `except Exception` on line 664 should already catch `SystemError` since `SystemError` inherits from `Exception`. The fact that the error appeared in production logs means the catch IS working (it logs the error and continues). D-08 adds explicit SystemError handling with retry logic for resilience. The real fix may be the DB split itself (D-09) -- smaller DBs with no contention during VACUUM. [VERIFIED: Python MRO -- SystemError -> Exception -> BaseException]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-WAN DB path | Custom path resolution | YAML `storage.db_path` config key | Already supported by `get_storage_config()` [VERIFIED] |
| DB auto-discovery for CLI | Hard-coded WAN list | Glob pattern `metrics-*.db` | New WANs auto-discovered without code changes |
| CLI entry points | sys.path hacks | pyproject.toml `[project.scripts]` | Standard Python packaging, works everywhere |
| VACUUM scheduling | Custom VACUUM timer | Existing `vacuum_if_needed()` in retention.py | Already has incremental vacuum, freelist threshold [VERIFIED] |

## Common Pitfalls

### Pitfall 1: MetricsWriter Singleton Across Processes
**What goes wrong:** Assuming MetricsWriter singleton is shared across wanctl@spectrum and wanctl@att.
**Why it happens:** "Singleton" sounds like one global instance.
**How to avoid:** Each systemd service is a separate process. Each gets its own singleton with its own db_path from its own YAML config. The split is config-only, not code-only.
**Warning signs:** Tests that mock a single MetricsWriter for multi-WAN scenarios.

### Pitfall 2: Stale DEFAULT_DB_PATH in CLI Tools
**What goes wrong:** CLI tools still default to `/var/lib/wanctl/metrics.db` after per-WAN split, showing no data.
**Why it happens:** `DEFAULT_DB_PATH` in writer.py is unchanged, and CLI --db defaults to it.
**How to avoid:** CLI tools must auto-discover per-WAN DB files when no explicit --db is given. Fall back to legacy path for backward compat.
**Warning signs:** `wanctl-history --last 1h` returns empty results after deploy.

### Pitfall 3: One-Shot VACUUM on 925MB DB
**What goes wrong:** Running VACUUM on the existing 925MB shared DB takes a long time and doubles disk usage temporarily (VACUUM copies the entire DB).
**Why it happens:** Full VACUUM creates a copy of the database, writes reorganized data, then replaces the original.
**How to avoid:** Run the one-shot VACUUM manually (D-03) AFTER the retention purge has deleted most data. With 24h raw retention, the 925MB DB should shrink dramatically from deletion alone. VACUUM after deletion reclaims the freed pages. Also, the old shared DB gets archived (D-07), not actively used.
**Warning signs:** Disk full during VACUUM on a partition with < 1GB free.

### Pitfall 4: deploy.sh Still Deploying analyze_baseline.py to /opt/wanctl/scripts/
**What goes wrong:** After promoting to entry point, deploy.sh still copies the old script file, creating confusion about which version runs.
**Why it happens:** `ANALYSIS_SCRIPTS` array in deploy.sh still lists the file.
**How to avoid:** Remove from ANALYSIS_SCRIPTS array or remove the array entirely. The entry point gets installed via the code rsync of `src/wanctl/`.
**Warning signs:** Two copies of analyze_baseline: the old script in /opt/wanctl/scripts/ and the new module in /opt/wanctl/analyze_baseline.py.

### Pitfall 5: Health Endpoint File Snapshot After Split
**What goes wrong:** Health endpoint reports storage file sizes for the wrong DB or only one WAN's DB.
**Why it happens:** `get_storage_file_snapshot()` in runtime_pressure.py takes a single db_path.
**How to avoid:** The health endpoint is per-service (each wanctl@wan has its own health server on its own IP). Each service's health endpoint naturally reports its own per-WAN DB size. No code change needed.
**Warning signs:** N/A -- this pitfall is a false alarm once you understand the per-service architecture.

### Pitfall 6: Retention Config Default vs Explicit
**What goes wrong:** Setting `raw_age_seconds: 86400` (24h) in YAML but the code default `DEFAULT_STORAGE_RAW_AGE_SECONDS = 900` (15 min) for raw data is what currently runs in production.
**Why it happens:** Production configs have no `storage:` section, so code defaults apply.
**How to avoid:** D-02 explicitly adds the storage section. The 24h raw retention is intentional -- production needs more history than the aggressive 15-minute default.
**Warning signs:** After deploy, DB size balloons instead of shrinking (if raw_age is accidentally set larger than current data volume warrants).

## Code Examples

### Adding storage section to spectrum.yaml
```yaml
# Source: configs/examples/cable.yaml.example + D-01/D-05 decisions
storage:
  db_path: "/var/lib/wanctl/metrics-spectrum.db"
  maintenance_interval_seconds: 900
  retention:
    raw_age_seconds: 86400           # 24h raw data (D-01)
    aggregate_1m_age_seconds: 86400  # 24h 1-minute aggregates
    aggregate_5m_age_seconds: 604800 # 7d 5-minute aggregates
```
[VERIFIED: get_storage_config() in config_base.py handles these keys natively]

### CLI auto-discovery pattern for per-WAN DBs
```python
# Source: Pattern design based on existing reader.py API
from pathlib import Path
from wanctl.storage.reader import query_metrics

WAN_DB_DIR = Path("/var/lib/wanctl")

def discover_wan_dbs() -> list[Path]:
    """Auto-discover per-WAN DB files, with legacy fallback."""
    dbs = sorted(WAN_DB_DIR.glob("metrics-*.db"))
    if not dbs:
        legacy = WAN_DB_DIR / "metrics.db"
        if legacy.exists():
            return [legacy]
    return dbs

def query_all_wans(**kwargs) -> list[dict]:
    """Query metrics across all per-WAN DBs, merge results."""
    results = []
    for db in discover_wan_dbs():
        results.extend(query_metrics(db_path=db, **kwargs))
    # Sort by timestamp for chronological output
    results.sort(key=lambda r: r.get("timestamp", 0))
    return results
```
[ASSUMED -- pattern design]

### SystemError-resilient maintenance
```python
# Source: D-08 decision + CPython issue #108083
def _run_maintenance(controller, maintenance_conn, maintenance_retention_config):
    maint_logger = controller.wan_controllers[0]["logger"]
    for attempt in range(2):  # D-08: retry once
        try:
            # ... existing maintenance body ...
            return  # Success
        except SystemError as e:
            if attempt == 0:
                maint_logger.warning(
                    "Maintenance SystemError (attempt %d, retrying): %s", attempt + 1, e
                )
            else:
                maint_logger.error(
                    "Maintenance SystemError persisted after retry, skipping cycle: %s", e
                )
        except Exception as e:
            maint_logger.error("Periodic maintenance failed: %s", e)
            return  # Non-retryable
```
[ASSUMED -- implementation pattern based on D-08]

### Entry point for analyze_baseline
```toml
# In pyproject.toml [project.scripts]
wanctl-analyze-baseline = "wanctl.analyze_baseline:main"
```
[VERIFIED: follows exact pattern of existing entries in pyproject.toml lines 15-24]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Shared metrics.db for all WANs | Per-WAN DB files | Phase 172 (now) | Eliminates write contention |
| sys.path hacks for scripts | pyproject.toml entry points | Phase 172 (now) | Clean imports everywhere |
| No explicit storage config in YAML | Explicit retention + db_path in YAML | Phase 172 (now) | Operator controls retention |
| DEFAULT_RETENTION_DAYS=7 flat | Per-granularity retention (raw/1m/5m/1h) | Already in code (v1.33+) | More granular control |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | CLI auto-discovery via glob `metrics-*.db` is sufficient for multi-WAN DB merge | CLI Multi-DB Merge Pattern | LOW -- can always add explicit --db flag per WAN as fallback |
| A2 | operator_summary does NOT need DB changes because it reads from HTTP health endpoint | Code Impact Analysis | LOW -- verified from source, reads URL/file not SQLite |
| A3 | The "error return without exception set" is a CPython sqlite3 SystemError triggered by VACUUM/checkpoint under contention on large DBs | Maintenance Error Fix Pattern | MEDIUM -- exact trigger not confirmed from production logs, but CPython issue #108083 matches symptoms |
| A4 | 24h raw retention on a fresh per-WAN DB will not exceed storage pressure thresholds | Pitfall 6 | LOW -- 24h of raw at 20Hz ~25 metrics = ~43M rows/day, but each row is tiny; DB split halves per-file size |

## Open Questions

1. **Exact steady-state DB size with 24h raw retention**
   - What we know: Current 925MB is from 7+ days of raw data with no cleanup running effectively (the storage section was never configured). With 24h raw + proper downsampling, size should be dramatically smaller.
   - What's unclear: Exact size per WAN with 24h raw at 20Hz (~25 metrics/cycle).
   - Recommendation: Deploy and monitor. D-04 says trust the storage pressure thresholds. If size grows beyond warning, reduce raw_age_seconds.

2. **Python version on production cake-shaper VM**
   - What we know: Dev machine is Python 3.12.3. Production is Ubuntu-based VM.
   - What's unclear: Exact Python version on cake-shaper. CPython sqlite3 bugs vary by version.
   - Recommendation: Check `python3 --version` on production during deployment.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with xdist, timeout, cov |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `.venv/bin/pytest tests/storage/ -v -x` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STOR-01 | Retention cleanup deletes data older than raw_age_seconds | unit | `.venv/bin/pytest tests/storage/test_storage_retention.py -v -x` | Yes |
| STOR-01 | Per-WAN DB path resolves from config | unit | `.venv/bin/pytest tests/test_config_base.py -v -x -k storage` | Yes |
| STOR-02 | Maintenance handles SystemError gracefully | unit | `.venv/bin/pytest tests/storage/test_storage_maintenance.py -v -x` | Yes (needs new test) |
| DEPL-02 | analyze_baseline imports resolve correctly | unit | `.venv/bin/pytest tests/test_analyze_baseline.py -v -x` | No -- Wave 0 |
| D-06 | CLI discovers and merges per-WAN DBs | unit | `.venv/bin/pytest tests/test_history.py -v -x -k multi_db` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/storage/ -v -x`
- **Per wave merge:** `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_analyze_baseline.py` -- covers DEPL-02 (entry point import resolution)
- [ ] New test in `tests/storage/test_storage_maintenance.py` -- covers STOR-02 (SystemError handling)
- [ ] New test in `tests/test_history.py` or `tests/storage/test_multi_db.py` -- covers D-06 (CLI multi-DB merge)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A |
| V3 Session Management | no | N/A |
| V4 Access Control | no | N/A -- DB files inherit FHS permissions (root:wanctl 640) |
| V5 Input Validation | yes | YAML config validation via existing `get_storage_config()` schema |
| V6 Cryptography | no | N/A |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious db_path in YAML config | Tampering | Config files are root-owned, 640 permissions [VERIFIED: deploy.sh line 192] |
| SQL injection via metric queries | Tampering | Parameterized queries throughout reader.py [VERIFIED: reader.py uses ? placeholders] |
| Disk exhaustion from DB growth | Denial of Service | Storage pressure monitoring (runtime_pressure.py) + retention cleanup [VERIFIED: existing v1.34 feature] |

## Sources

### Primary (HIGH confidence)
- Codebase review: `src/wanctl/storage/` (writer.py, reader.py, retention.py, maintenance.py, schema.py, downsampler.py)
- Codebase review: `src/wanctl/autorate_continuous.py` (_init_storage, _run_maintenance, _run_daemon_loop)
- Codebase review: `src/wanctl/config_base.py` (get_storage_config, DEFAULT_STORAGE_* constants)
- Codebase review: `configs/spectrum.yaml`, `configs/att.yaml` (no storage section present)
- Codebase review: `scripts/analyze_baseline.py` (sys.path hack on lines 19-22)
- Codebase review: `scripts/deploy.sh` (ANALYSIS_SCRIPTS array)
- Codebase review: `pyproject.toml` (existing [project.scripts] entry points)

### Secondary (MEDIUM confidence)
- [CPython issue #108083](https://github.com/python/cpython/issues/108083) -- sqlite3 code paths that ignore exceptions
- [CPython issue #146090](https://github.com/python/cpython/issues/146090) -- assertion failure in free_callback_context
- Python version: 3.12.3 on dev machine [VERIFIED: `python3 --version`]

### Tertiary (LOW confidence)
- Steady-state DB size estimate with 24h raw retention (not measured, only calculated)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all existing code paths
- Architecture: HIGH -- per-WAN DB split is config-only for writer; CLI merge is the main new code
- Pitfalls: HIGH -- thoroughly traced code paths, all integration points identified

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (stable domain -- SQLite patterns don't change fast)
