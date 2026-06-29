# Phase 261, Plan 02 — Deploy Reconcile Evidence (RECON-03)

**Timestamp:** 2026-06-28T23:10 UTC
**Host:** cake-shaper

## Deploy Output

- spectrum deploy: exit 0, 109 Python files deployed
- att deploy: exit 0, 109 Python files deployed
- Predeploy gate (spectrum): PASS — continuous_monitoring.upload clean

## Deletion Set (actual deploy rsync)

### Spectrum deploy:
- scripts/phase259-ownership-proof.py (ALLOWED)
- .phase259-backup-20260625T014037Z/* (ALLOWED - backup dir)
- steering/route_ownership_guard.py.bak-d07 (ALLOWED)
- "cannot delete non-empty directory: scripts" (harmless, scripts dir has new files)

### ATT deploy:
- scripts/wanctl-operator-summary, validate-deployment.sh, compact-metrics-dbs.sh, analyze_baseline.py (ALLOWED - these are reinstalled after rsync by deploy.sh non-rsync steps)

All deletions within expected allowlist.

## steering.yaml Preserve/Restore

Pre-deploy sha: b8cc6244d5e617ef11a081cf654e30a6d5ae5708d9da965b5d2f48403ab01bcd
Post-deploy sha (before restore): f9e57bbe8d20a92b6d13ae0b322a474620d18461ea530720c314d3475359e6e1 (CHANGED - deploy.sh overwrote)
Post-restore sha: b8cc6244d5e617ef11a081cf654e30a6d5ae5708d9da965b5d2f48403ab01bcd (MATCHES pre-deploy)

route_management.mode: dry_run (verified preserved after restore)

**PHASE261_STEERING_YAML_RESTORED**

## ActiveEnterTimestampMonotonic (no-restart gate)

| Unit | Pre-deploy | Post-deploy | Match |
|------|-----------|-------------|-------|
| cake-autorate-spectrum | 259295876567 | 259295876567 | YES |
| cake-autorate-att | 84347000490 | 84347000490 | YES |
| steering | 710735873594 | 710735873594 | YES |

**PHASE261_NO_RESTART_GATE_PASS**

## SHA256 Audit (repo vs prod)

- Repo manifest: 110 files
- Prod manifest: 110 files
- Sorted diff: 0 differences
- All 110 files byte-identical between repo HEAD and /opt/wanctl on cake-shaper

**PHASE261_AUDIT_SRC_TREE_EQUAL**
