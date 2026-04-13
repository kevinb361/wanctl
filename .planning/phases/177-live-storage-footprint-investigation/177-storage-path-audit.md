# Phase 177 Storage Path Audit

**Captured:** 2026-04-13
**Scope:** Repo DB-path authority and live production file-role inventory

## Repo-Side DB Path Authority

### Configured active per-WAN DBs

The shipped autorate configs explicitly point each WAN at its own DB:

- `configs/spectrum.yaml` -> `/var/lib/wanctl/metrics-spectrum.db`
- `configs/att.yaml` -> `/var/lib/wanctl/metrics-att.db`

### Legacy default path still present in shared storage code

The shared storage/config helpers still carry a default:

- `src/wanctl/config_base.py`
  - `DEFAULT_STORAGE_DB_PATH = "/var/lib/wanctl/metrics.db"`
  - `get_storage_config()` returns `storage.db_path` or that default

### Discovery/fallback behavior for multi-DB readers

`src/wanctl/storage/db_utils.py` documents and implements:

- use per-WAN files matching `metrics-*.db` when they exist
- fall back to legacy `metrics.db` only when no per-WAN files exist

## Live Production File Inventory

### Observed DB files

From `cake-shaper` on 2026-04-13:

| File | Size | Last modified | Classification |
|------|------|---------------|----------------|
| `/var/lib/wanctl/metrics-spectrum.db` | `5,441,712,128` bytes (`~5.44 GB`) | `2026-04-13 17:39:18 -0500` | active runtime DB |
| `/var/lib/wanctl/metrics-spectrum.db-wal` | `4,268,352` bytes (`~4.27 MB`) | `2026-04-13 17:39:18 -0500` | active WAL |
| `/var/lib/wanctl/metrics-att.db` | `5,082,914,816` bytes (`~5.08 GB`) | `2026-04-13 17:39:17 -0500` | active runtime DB |
| `/var/lib/wanctl/metrics-att.db-wal` | `4,243,632` bytes (`~4.24 MB`) | `2026-04-13 17:39:18 -0500` | active WAL |
| `/var/lib/wanctl/metrics.db` | `750,997,504` bytes (`~751 MB`) | `2026-04-13 17:39:03 -0500` | active legacy/shared DB |
| `/var/lib/wanctl/metrics.db-wal` | `4,523,792` bytes (`~4.52 MB`) | `2026-04-13 17:39:18 -0500` | active legacy/shared WAL |
| `/var/lib/wanctl/spectrum_metrics.db` | `0` bytes | `2026-04-07 19:40:59 -0500` | stale/empty artifact |
| `/var/lib/wanctl/att_metrics.db` | `0` bytes | `2026-04-08 18:22:03 -0500` | stale/empty artifact |

### File-role conclusions

- `metrics-spectrum.db`: active runtime DB
  - matches shipped Spectrum config
  - is current in both file mtime and health `storage.files` output
- `metrics-att.db`: active runtime DB
  - matches shipped ATT config
  - is current in both file mtime and health `storage.files` output
- `metrics.db`: active legacy/shared DB
  - still being updated on disk
  - still has a live WAL
  - still receives fresh `metrics` rows (see composition report)
- `spectrum_metrics.db` / `att_metrics.db`: stale/empty artifacts
  - zero bytes
  - old mtimes
  - not referenced by repo config or DB discovery helpers

## Why `metrics.db` is classified as active, not residue

This file is not inert residue because all three of the following are true:

1. it had a fresh mtime on 2026-04-13
2. it had a live `.db-wal` companion with a fresh mtime
3. its `metrics` table still contained fresh rows through `2026-04-13T22:39:18Z`

The most likely runtime explanation is:

- autorate services use the explicit per-WAN `storage.db_path` values
- steering still falls back to the shared default `/var/lib/wanctl/metrics.db`

That steering inference is consistent with:

- `src/wanctl/steering/daemon.py` using `get_storage_config(config.data)`
- `get_storage_config()` defaulting missing `storage.db_path` to `/var/lib/wanctl/metrics.db`
- the legacy DB still being actively written even though the autorate DBs are split per-WAN

## Unresolved Points

None at Phase 177 closeout. The active-vs-legacy-vs-stale file roles are now evidence-backed well enough to drive Phase 178.

## Evidence Commands

```bash
rg -n 'db_path|metrics\.db|metrics-' configs/spectrum.yaml configs/att.yaml src/wanctl/config_base.py src/wanctl/storage/db_utils.py
ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n stat -c "%n %s %y" /var/lib/wanctl/metrics.db /var/lib/wanctl/metrics.db-wal /var/lib/wanctl/metrics-spectrum.db /var/lib/wanctl/metrics-spectrum.db-wal /var/lib/wanctl/metrics-att.db /var/lib/wanctl/metrics-att.db-wal /var/lib/wanctl/spectrum_metrics.db /var/lib/wanctl/att_metrics.db 2>/dev/null'
```

