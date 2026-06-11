---
phase: 233-gated-repo-hygiene-sweep
reviewed: 2026-06-11T19:54:23Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - deploy/systemd/cake-autorate-spectrum-state-bridge.service
  - docs/PERFORMANCE.md
  - docs/PROFILING.md
  - docs/RUNBOOK.md
  - docs/STEERING.md
findings:
  critical: 0
  warning: 2
  info: 0
  total: 2
status: issues_found
---

# Phase 233: Code Review Report

**Reviewed:** 2026-06-11T19:54:23Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Reviewed the Spectrum state-bridge systemd unit and the documentation hygiene updates for production operational correctness. The explicit Spectrum health-host environment pin is consistent with the repository's matching tests and ATT unit pattern. Two documentation/runbook issues remain: an external cake-autorate validation recipe still targets native `wanctl@` service/state paths, and the profiling rollback gate hard-codes an older health version.

## Warnings

### WR-01: External-mode steering validation targets the wrong writer and state path

**File:** `docs/STEERING.md:325-356`
**Issue:** The degradation validation runbook stops `wanctl@spectrum` and renames `/run/wanctl/spectrum_state.json`. In the active external cake-autorate topology reviewed in this phase, the state writer is `cake-autorate-spectrum-state-bridge.service`, and the checked-in Spectrum bridge writes `WANCTL_EXTERNAL_STATE_PATH=/var/lib/wanctl/spectrum_state.json`. Following the current recipe on an external-mode host can fail to create the intended stale/missing-state condition, producing a false validation result or leaving operators modifying a non-authoritative file.
**Fix:** Split the recipe by deployment mode or update the Spectrum external-mode commands to operate on the state bridge and `/var/lib` state file, for example:

```bash
# External cake-autorate mode: create stale zone condition
ssh cake-spectrum 'sudo systemctl stop cake-autorate-spectrum-state-bridge.service'
sleep 10
ssh cake-spectrum 'curl -s http://127.0.0.1:9102/health | python3 -m json.tool | grep -A10 wan_awareness'
ssh cake-spectrum 'sudo systemctl start cake-autorate-spectrum-state-bridge.service'

# External cake-autorate mode: simulate missing state file
ssh cake-spectrum 'sudo mv /var/lib/wanctl/spectrum_state.json /var/lib/wanctl/spectrum_state.json.bak'
sleep 3
ssh cake-spectrum 'curl -s http://127.0.0.1:9102/health | python3 -m json.tool | grep -A10 wan_awareness'
ssh cake-spectrum 'sudo mv /var/lib/wanctl/spectrum_state.json.bak /var/lib/wanctl/spectrum_state.json'
```

### WR-02: Profiling rollback check hard-codes stale health version

**File:** `docs/PROFILING.md:120-125`
**Issue:** The mandatory profiling revert gate says `/health.version == 1.45.0`, while the project context identifies the current production version as 1.47.0. This stale hard-coded version can cause a successful rollback on a current deployment to appear failed, or train operators to ignore the version check when it disagrees with reality.
**Fix:** Avoid a fixed historical version in the active runbook. Prefer a placeholder tied to the deployed release, or update it with every release:

```markdown
Expected:

- `systemctl cat wanctl@spectrum` shows no override block / `override.conf`.
- The process command contains neither `--profile` nor `--debug` nor
  `WANCTL_LOG_FORMAT=json`.
- Service is active and `/health.version` matches the deployed wanctl version.
```

---

_Reviewed: 2026-06-11T19:54:23Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
