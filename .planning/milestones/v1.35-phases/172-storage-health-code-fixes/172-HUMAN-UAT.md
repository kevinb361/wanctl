---
status: partial
phase: 172-storage-health-code-fixes
source: [172-VERIFICATION.md]
started: 2026-04-12T14:47:07Z
updated: 2026-04-12T15:34:30Z
---

## Current Test

production validation completed on cake-shaper; one operational issue remains

## Tests

### 1. Production Storage Migration
expected: scripts/migrate-storage.sh archives /var/lib/wanctl/metrics.db after purge+VACUUM, restarts can proceed, and per-WAN DB files are present or ready to be created on service start
result: passed

notes:
- Ran the migration on `cake-shaper`.
- Legacy shared DB archived to `/var/lib/wanctl/metrics.db.pre-v135-archive`.
- A residual shared DB created by a pre-deploy restart was moved aside to `/var/lib/wanctl/metrics.db.post-phase172-residual`.
- After deploying current config/code and restarting services, live writes moved to `/var/lib/wanctl/metrics-spectrum.db` and `/var/lib/wanctl/metrics-att.db`.

### 2. Post-Deploy Storage Canary
expected: scripts/canary-check.sh reports storage file sizes, storage.status is not critical, and the canary exits 0
result: issue

notes:
- `./scripts/canary-check.sh --ssh cake-shaper --skip-steering` exited successfully with `0` errors and `0` warnings.
- `/health` now reports healthy runtime and `storage_status: ok` in summary rows for both WANs.
- The top-level `/health` `storage` field is still `null`, so the canary cannot display live DB/WAL sizes and currently prints `storage status=unknown, db=0B, wal=0B, shm=0B, total=0B`.
- On-disk files confirm the real sizes are non-zero:
- `metrics-spectrum.db` / `metrics-spectrum.db-wal`
- `metrics-att.db` / `metrics-att.db-wal`

## Summary

total: 2
passed: 1
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

- Health endpoint contract gap: top-level `storage` is `null` on production, so Phase 172's canary storage-size observability is not yet satisfied even though per-WAN DB routing and runtime health are working.
