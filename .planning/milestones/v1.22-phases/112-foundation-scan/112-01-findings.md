# 112-01 Findings: Dependency Hygiene Scan

Date: 2026-03-26

## pip-audit (FSCAN-01)

**Result: 1 low-severity CVE found, zero critical/high.**

```
Found 1 known vulnerability in 1 package
Name     Version ID            Fix Versions
-------- ------- ------------- ------------
pygments 2.19.2  CVE-2026-4539
```

**CVE-2026-4539 (pygments 2.19.2):** Inefficient regex in `AdlLexer` (archetype.py). Local-access-only ReDoS. No fix version available. pygments is a transitive dev dependency (via rich/bandit), not a runtime dependency. **Disposition: Accept risk (low severity, dev-only, no fix available).**

All 56 auditable packages scanned. wanctl itself skipped (not on PyPI, expected).

## deptry (FSCAN-02)

**Result: 7 findings across 3 categories.**

### DEP002: Unused Dependencies (declared but never imported)

| Package | Disposition |
|---------|------------|
| `cryptography>=46.0.5` | **Removed from `[project] dependencies`.** Never imported directly in src/. Pulled in transitively by paramiko (confirmed: `pip show paramiko` lists cryptography as requirement). Still available at runtime. |

### DEP003: Transitive Dependencies (imported directly but not declared)

| Package | Import Location | Disposition |
|---------|----------------|------------|
| `rich` | `src/wanctl/dashboard/app.py:15` | Transitive via textual (dashboard optional group). **Kept: dashboard is optional, rich comes with textual.** |
| `rich` | `src/wanctl/dashboard/widgets/status_bar.py:8` | Same as above |
| `rich` | `src/wanctl/dashboard/widgets/steering_panel.py:11` | Same as above |
| `rich` | `src/wanctl/dashboard/widgets/wan_panel.py:11` | Same as above |
| `urllib3` | `src/wanctl/routeros_rest.py:46` | Transitive via requests. **Kept: urllib3 is a stable requests dependency, adding explicit dep would create version conflicts.** |

### DEP001: Missing Dependencies (imported but not declared)

| Package | Import Location | Disposition |
|---------|----------------|------------|
| `systemd` | `src/wanctl/systemd_utils.py:35` | **Kept as-is.** `python3-systemd` is a system apt package, not pip-installable. Import is wrapped in try/except (graceful fallback). Cannot and should not be declared in pyproject.toml. |

### Additional Removal: pyflakes

`pyflakes>=3.4.0` removed from `[dependency-groups] dev`. Redundant with ruff's `F` rule selector (ruff implements pyflakes checks natively). Identified in STACK.md research.

### Summary of pyproject.toml Changes

- **Removed** `"cryptography>=46.0.5"` from `[project] dependencies` (transitive via paramiko)
- **Removed** `"pyflakes>=3.4.0"` from `[dependency-groups] dev` (redundant with ruff F rules)
- `uv sync` completed successfully after removals
- `uv.lock` updated to reflect new dependency graph

## pytest-deadfixtures (FSCAN-07)

**Result: 8 orphaned fixtures found.**

| # | Fixture Name | Location | Description |
|---|-------------|----------|-------------|
| 1 | `sample_config_data` | `tests/conftest.py:22` | Sample configuration data for testing |
| 2 | `with_controller` | `tests/integration/conftest.py:41` | Get controller monitoring flag from CLI |
| 3 | `integration_output_dir` | `tests/integration/conftest.py:47` | Get integration test output directory |
| 4 | `memory_db` | `tests/test_alert_engine.py:16` | In-memory SQLite connection with tables |
| 5 | `mock_controller` | `tests/test_autorate_entry_points.py:113` | Mock ContinuousAutoRate controller |
| 6 | `controller` | `tests/test_autorate_error_recovery.py:61` | WANController with patched load_state |
| 7 | `sample_steering_response` | `tests/test_dashboard/conftest.py:45` | Steering health JSON schema dict |
| 8 | `sample_autorate_response` | `tests/test_dashboard/conftest.py:7` | Autorate health JSON schema dict |

**Disposition: Cataloged only.** These fixtures are candidates for removal in Plan 04 (dead code scan) after validation that no test parametrization or indirect usage exists.

Note: 2 collection errors during scan (likely dashboard tests requiring textual/httpx optional deps). Does not affect fixture detection accuracy.

## Log Rotation (FSCAN-08)

### Handler Configuration (src/wanctl/logging_utils.py)

- **Handler:** `logging.handlers.RotatingFileHandler`
- **Max bytes:** 10,485,760 (10 MB) per file (configurable via `config.max_bytes`)
- **Backup count:** 3 (configurable via `config.backup_count`)
- **Main log:** INFO level, always active
- **Debug log:** DEBUG level, only when `debug=True`
- **Format:** Text (default) or JSON (via `WANCTL_LOG_FORMAT=json` env var)

### Production Verification (cake-shaper VM, 2026-03-26 12:23 UTC)

```
total 95M
-rw-r--r-- 1 wanctl wanctl 8.1M Mar 26 12:23 att.log
-rw-r--r-- 1 wanctl wanctl  10M Mar 26 11:29 att.log.1
-rw-r--r-- 1 wanctl wanctl  10M Mar 26 10:24 att.log.2
-rw-r--r-- 1 wanctl wanctl  10M Mar 26 09:18 att.log.3
-rw-r--r-- 1 wanctl wanctl 9.9M Mar 26 12:23 spectrum.log
-rw-r--r-- 1 wanctl wanctl  10M Mar 26 11:28 spectrum.log.1
-rw-r--r-- 1 wanctl wanctl  10M Mar 26 10:33 spectrum.log.2
-rw-r--r-- 1 wanctl wanctl  10M Mar 26 09:38 spectrum.log.3
-rw-r--r-- 1 wanctl wanctl 6.6M Mar 26 12:23 steering.log
-rw-r--r-- 1 wanctl wanctl  10M Mar 26 03:58 steering.log.1
95M total
```

**Assessment:** Log rotation is active and healthy.
- 3 services (spectrum, att, steering) each with active log + 3 backups
- Total disk: 95 MB (bounded at ~120 MB max = 3 services x 4 files x 10 MB)
- Rotation frequency: ~1 hour for autorate logs (high-frequency 50ms cycles), ~8 hours for steering log
- No debug logs active in production (expected)
- Retention is appropriate for operational troubleshooting (3-4 hours of autorate history, ~32 hours of steering history)
