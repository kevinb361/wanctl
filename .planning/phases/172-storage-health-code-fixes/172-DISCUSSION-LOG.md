# Phase 172: Storage Health & Code Fixes - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-12
**Phase:** 172-storage-health-code-fixes
**Areas discussed:** DB reduction strategy, Write contention, Maintenance error fix, analyze_baseline fix

---

## DB Reduction Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| 24 hours raw | Keep raw 50ms cycle data for 1 day only. Downsampled aggregates cover longer history. | :heavy_check_mark: |
| 48 hours raw | Two days of raw data for next-day investigation. | |
| Keep 7 days raw | Don't change raw retention, focus on VACUUM only. | |

**User's choice:** 24 hours raw
**Notes:** Matches the fact that raw data is only useful for recent debugging.

| Option | Description | Selected |
|--------|-------------|----------|
| One-shot manual VACUUM | Run once after big purge, periodic handles future. | :heavy_check_mark: |
| VACUUM INTO new DB | Fresh compacted copy, swap files. | |
| Let periodic handle it | Just tune retention, VACUUM reclaims over time. | |

**User's choice:** One-shot manual VACUUM
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Update YAML config | Set raw_age_seconds=86400 in production configs. | :heavy_check_mark: |
| One-time script only | Manual cleanup, leave defaults. | |

**User's choice:** Update YAML config
**Notes:** Makes retention explicit and prevents re-growth.

| Option | Description | Selected |
|--------|-------------|----------|
| Under 100 MB | Strict target for pressure threshold. | |
| Under 200 MB | Relaxed target. | |
| Whatever 24h lands at | Trust pressure monitoring, no explicit target. | :heavy_check_mark: |

**User's choice:** Whatever 24h lands at
**Notes:** Trust v1.34 storage pressure monitoring thresholds.

---

## Write Contention

| Option | Description | Selected |
|--------|-------------|----------|
| Per-WAN DB files | Each wanctl@{wan} writes to own DB. Eliminates contention. | :heavy_check_mark: |
| WAL tuning only | Increase busy_timeout, tune wal_autocheckpoint. | |
| Investigate first | Diagnose if contention is actually causing problems. | |

**User's choice:** Per-WAN DB files
**Notes:** Follows existing per-WAN state file pattern.

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, merge results | CLI tools attach both DBs, unified output. | :heavy_check_mark: |
| Separate queries | User passes --wan flag to query each. | |

**User's choice:** Yes, merge results
**Notes:** User doesn't need to think about which DB.

| Option | Description | Selected |
|--------|-------------|----------|
| Fresh start | New per-WAN DBs start empty. Old DB archived. | :heavy_check_mark: |
| Split and migrate | Extract each WAN's rows into per-WAN DB. | |
| Keep old as read-only | Old DB for history, new DBs for writes. | |

**User's choice:** Fresh start
**Notes:** 24h retention means historical data would be purged anyway.

---

## Maintenance Error Fix

| Option | Description | Selected |
|--------|-------------|----------|
| Catch and retry | Wrap in try/except SystemError, log, retry once. | :heavy_check_mark: |
| Root-cause diagnose first | Reproduce error, identify exact cause. | |
| Ignore -- DB split may fix it | Monitor during soak, fix only if recurs. | |

**User's choice:** Catch and retry
**Notes:** Pragmatic approach. Per-WAN DB split may also fix the root cause.

---

## analyze_baseline Fix

| Option | Description | Selected |
|--------|-------------|----------|
| CLI entry point | Promote to wanctl-analyze-baseline via pyproject.toml. | :heavy_check_mark: |
| Fix script import path | Add sys.path manipulation to find wanctl modules. | |
| Move to src/wanctl/cli/ | Move logic into CLI module, expose via entry point. | |

**User's choice:** CLI entry point
**Notes:** Follows the pattern of all other wanctl-* tools.

---

## Claude's Discretion

No areas deferred to Claude's discretion -- all decisions were user-specified.

## Deferred Ideas

- Monitor Proxmox steal CPU on cake-shaper VM -- reviewed but out of scope for this phase
