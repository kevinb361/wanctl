# Phase 112 Plan 02: Production VM Security Audit Findings

**Audited:** 2026-03-26
**Target:** cake-shaper VM (10.10.110.223)
**Method:** SSH inline commands (per D-08)

## File Permissions (FSCAN-04)

### /etc/wanctl/ (Configuration Directory)

| Path | Actual | Expected | Owner | Status |
|------|--------|----------|-------|--------|
| `/etc/wanctl/` | 0750 | 0750 | root:wanctl | PASS |
| `/etc/wanctl/secrets` | 0640 | 0600 | root:wanctl | NOTE |
| `/etc/wanctl/att.yaml` | 0640 | 0640 | root:wanctl | PASS |
| `/etc/wanctl/spectrum.yaml` | 0640 | 0640 | root:wanctl | PASS |
| `/etc/wanctl/steering.yaml` | 0640 | 0640 | root:wanctl | PASS |
| `/etc/wanctl/cable.yaml.example` | 0640 | 0640 | root:wanctl | PASS |
| `/etc/wanctl/dsl.yaml.example` | 0640 | 0640 | root:wanctl | PASS |
| `/etc/wanctl/fiber.yaml.example` | 0640 | 0640 | root:wanctl | PASS |
| `/etc/wanctl/ssh/` | 0750 | 0750 | root:wanctl | PASS |

**NOTE on `/etc/wanctl/secrets` (0640 vs expected 0600):**
The file is 0640 with owner root:wanctl. This means the `wanctl` group can read it, which is required for the wanctl service (running as `wanctl` user) to read the router password. Changing to 0600 would break the service. The plan's expectation of 0600 is incorrect -- 0640 with group=wanctl is the correct production permission for this file. No world-readable access exists.

**Additional finding:** Two `.bak` files exist with owner `root:root` (not `root:wanctl`):
- `/etc/wanctl/spectrum.yaml.bak.20260325-195530` (0640, root:root)
- `/etc/wanctl/spectrum.yaml.bak.20260326-064031` (0640, root:root)

These backup files are not readable by the wanctl group. This is acceptable since they are not used at runtime, but cleanup could be considered.

### /var/lib/wanctl/ (State Directory)

| Path | Actual | Expected | Owner | Status |
|------|--------|----------|-------|--------|
| `/var/lib/wanctl/` | 0750 | 0750 | wanctl:wanctl | PASS |
| `att_state.json` | 0600 | 0600 | wanctl:wanctl | PASS |
| `spectrum_state.json` | 0600 | 0600 | wanctl:wanctl | PASS |
| `steering_state.json` | 0600 | 0600 | wanctl:wanctl | PASS |
| `steering_state.json.backup` | 0600 | 0600 | wanctl:wanctl | PASS |
| `steering_state.json.lock` | 0644 | - | wanctl:wanctl | NOTE |
| `metrics.db` | 0644 | 0640 | wanctl:wanctl | NOTE |
| `metrics.db-shm` | 0644 | 0640 | wanctl:wanctl | NOTE |
| `metrics.db-wal` | 0644 | 0640 | wanctl:wanctl | NOTE |
| `metrics.db.corrupt` | 0644 | - | wanctl:wanctl | NOTE |
| `.ssh/` | 0700 | 0700 | wanctl:wanctl | PASS |

**NOTE on metrics.db (0644):** The SQLite database and its journal files (shm, wal) are world-readable (0644). While these contain only performance metrics (not secrets), restricting to 0640 would be slightly better practice. Low priority -- no sensitive data exposed.

**NOTE on metrics.db.corrupt:** A 284MB corrupt database file exists. This is dead weight on disk. Consider cleanup.

**NOTE on steering_state.json.lock:** Lock file is 0644 (world-readable, empty). Standard for lock files.

### /var/log/wanctl/ (Log Directory)

| Path | Actual | Expected | Owner | Status |
|------|--------|----------|-------|--------|
| `/var/log/wanctl/` | 0750 | 0750 | wanctl:wanctl | PASS |
| `spectrum.log` | 0644 | 0640 | wanctl:wanctl | NOTE |
| `att.log` | 0644 | 0640 | wanctl:wanctl | NOTE |
| `steering.log` | 0644 | 0640 | wanctl:wanctl | NOTE |
| `*.log.N` (rotated) | 0644 | 0640 | wanctl:wanctl | NOTE |

**NOTE on log files (0644):** All log files are world-readable. The directory itself restricts access (0750), so users outside the wanctl group cannot traverse to these files. However, the files themselves could be tightened to 0640. Low priority since directory permissions provide adequate access control.

### /opt/wanctl/ (Application Code)

| Path | Actual | Expected | Owner | Status |
|------|--------|----------|-------|--------|
| `/opt/wanctl/` | 0755 | 0755 | root:root | PASS |
| All `.py` files | 0644 | 0644 | root:root | PASS |
| Subdirectories | 0755 | 0755 | root:root | PASS |

**NOTE:** Application code is deployed as a flat directory of `.py` files (no `src/` subdirectory). Code is root-owned and world-readable, which is standard for application code that contains no secrets.

**Additional finding:** An `autorate_continuous.py.bak` (178KB) file exists in `/opt/wanctl/`. This is dead weight and should be cleaned up.

### Permissions Summary

| Category | Items Checked | PASS | NOTE | FAIL |
|----------|--------------|------|------|------|
| Config (/etc/wanctl/) | 9 | 8 | 1 | 0 |
| State (/var/lib/wanctl/) | 11 | 6 | 5 | 0 |
| Logs (/var/log/wanctl/) | 8 | 1 | 7 | 0 |
| Application (/opt/wanctl/) | 3 | 3 | 0 | 0 |
| **Total** | **31** | **18** | **13** | **0** |

**No FAIL findings.** All critical security permissions are correct. Notes are low-priority improvements for defense-in-depth.
