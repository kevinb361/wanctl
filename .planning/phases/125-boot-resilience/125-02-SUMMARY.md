---
phase: 125-boot-resilience
plan: "02"
status: complete
started: 2026-04-02
completed: 2026-04-02
---

# Plan 125-02: Dependency Wiring + Deploy + Dry-Run

## What Was Built

Wired systemd dependencies so wanctl services wait for NIC tuning, reconciled diverged systemd unit directories, updated deploy.sh to include NIC tuning artifacts, and validated the full boot chain via dry-run on production.

## Key Changes

### Task 1: Systemd Dependency Wiring + Directory Reconciliation
- Added `After=wanctl-nic-tuning.service` and `Wants=wanctl-nic-tuning.service` to `deploy/systemd/wanctl@.service`
- Removed old `systemd/wanctl@.service` and `systemd/steering.service` (pre-hardening versions)
- `deploy/systemd/` is now the single canonical location for all systemd units

### Task 2: deploy.sh Update
- Updated `SYSTEMD_FILES` array to reference `deploy/systemd/` paths
- Added `wanctl-nic-tuning.service` to SYSTEMD_FILES
- Added NIC tuning script deployment block (scp to /usr/local/bin/)

### Task 3: Dry-Run Validation (Human Checkpoint)
- Deployed script and updated units to production (10.10.110.223) without restart
- Script ran idempotently: 4 NICs tuned, 0 errors, exit 0
- Journal logging confirmed: 10 log lines covering all actions
- `systemd-analyze verify wanctl@spectrum.service` passed
- `systemctl show After=` and `Wants=` both include `wanctl-nic-tuning.service`
- All 3 services (wanctl@spectrum, wanctl@att, wanctl-nic-tuning) remained active

## Deviations

None -- plan executed as written.

## Key Files

### Modified
- `deploy/systemd/wanctl@.service` -- Added NIC tuning dependency (After= and Wants=)
- `scripts/deploy.sh` -- Updated paths to deploy/systemd/, added NIC tuning artifacts

### Removed
- `systemd/wanctl@.service` -- Old unhardened version (replaced by deploy/systemd/)
- `systemd/steering.service` -- Old unhardened version (replaced by deploy/systemd/)

## Self-Check

- [x] `grep -q 'wanctl-nic-tuning.service' deploy/systemd/wanctl@.service` -- After= and Wants= present
- [x] `test ! -d systemd/` -- Old directory removed
- [x] `grep -q 'wanctl-nic-tuning' scripts/deploy.sh` -- NIC tuning in deploy script
- [x] `bash -n scripts/deploy.sh` -- Valid syntax
- [x] Production dry-run: script runs, logging works, dependency graph correct, services unaffected

## Self-Check: PASSED
