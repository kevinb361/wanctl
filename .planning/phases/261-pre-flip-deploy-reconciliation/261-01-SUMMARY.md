# Phase 261, Plan 01 — Summary

**One-liner:** Built proof tooling (sha256 audit + smoke-assertion scripts), probed cake-shaper read-only, witnessed deploy dry-run deletion set, captured rollback anchor with restore drill, and machine-checked full write-set rollback coverage.

## What Was Done

### Task 1: Proof Scripts (autonomous)
- `scripts/phase261-sha256-audit.py` (305 lines) — D-01 per-file sha256 manifest audit, emits PHASE261_AUDIT_SRC_TREE_EQUAL/_MISMATCH with exit-code coupling. Audits managed scripts subset separately, flags extras.
- `scripts/phase261-smoke-assertion.py` (307 lines) — :9102/health smoke gate (4 explicit checks including mode==dry_run). Bounded-poll readiness, --min-inspected-after freshness, --check-units. No wanctl import.
- Both pass ruff check/format, parse cleanly. pyproject.toml updated with N999 exemptions.

### Task 2: Host Probe + Dry-Run Witness (read-only)
- All required tools (tar, mktemp, xargs, sha256sum, curl, python3) present on cake-shaper.
- :9102 baseline captured: healthy, mode=dry_run, active_owner=netwatch, inspector_status=ok.
- 113 non-pyc files in /opt/wanctl src tree. 1 stale script (phase259-ownership-proof.py), 1 .phase259-backup-* dir.
- Pre-deploy ActiveEnterTimestampMonotonic baseline: spectrum=259295876567, att=84347000490, steering=710735873594.
- rsync --delete dry-run: 7 paths deleted, all allowlisted (extended allowlist covers phase259-ownership-proof.py + route_ownership_guard.py.bak-d07). PHASE261_DELETE_SET_ALLOWLISTED.
- Static deploy.sh restart witness: all restart refs are echo-only print_next_steps. PHASE261_DEPLOY_NO_INTERNAL_STEERING_RESTART.
- readonly-commands staged from Phase 260.

### Task 3: Rollback Anchor + Coverage Gate
- Tarball captured: /var/lib/wanctl/phase261-backups/20260628T225946Z/opt-wanctl.tgz
- Scratch-restore drill: PHASE261_RESTORE_DRILL_PASS (byte-matched, no service touched)
- 11 host-config files backed up with sha256 under host-config-pre-deploy/
- 11 helper script sha baselines recorded
- Full deploy.sh write-set enumerated (27 paths) and classified into 5 buckets
- PHASE261_FULL_WRITESET_ROLLBACK_COVERED (fail-closed gate, no unclassified paths)
- One-command code + host-config revert documented

## Requirements Satisfied
- RECON-02: Pre-deploy anchor captured and proven restorable; full write-set rollback coverage enforced.

## SAFE-22
No controller-path source touched. No ownership change. No production service bounced.
