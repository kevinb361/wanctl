---
phase: 232-cleanup-boundary-guard-tooling-fixes
reviewed: 2026-06-11T12:32:55Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - scripts/check-cleanup-boundary.sh
  - tests/test_cleanup_boundary_guard.py
  - scripts/phase231-rollback.sh
  - tests/test_phase231_rollback.py
  - scripts/phase231-migration-held.sh
findings:
  critical: 0
  warning: 1
  info: 1
  total: 2
status: issues_found
---

# Phase 232: Code Review Report

**Reviewed:** 2026-06-11T12:32:55Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Re-reviewed the cleanup boundary guard, Phase 231 rollback tooling, migration-held evaluator, and related tests after gap-closure work. The previous BOUND-01 cleanup guard bypass finding is resolved: protected paths now distinguish missing files, non-file replacements, untracked anchor-present files, immutable modifications, and allowlisted drift; tests cover removed files, untracked anchor-present files, immutable modifications, must-exist directory replacement, and the anchor-absent living-doc exception.

One rollback verification gap remains: confirmed rollback still checks only the primary cake-autorate service and can miss an active external state bridge or ATT cake watchdog. One low-severity CLI usability issue also remains around missing option values.

## Warnings

### WR-01: Confirmed rollback verification misses remaining external writer units

**File:** `scripts/phase231-rollback.sh:283-287`
**Issue:** `run_confirm()` fails closed only if `cake-autorate-${WAN}.service` remains `active` or `activating`. The rollback sequence disables both the cake service and `cake-autorate-${WAN}-state-bridge.service`, and ATT also disables `silicom-bypass-watchdog-cake-autorate-att.service`. If the bridge or ATT cake watchdog remains active after the remote rollback payload, the script can proceed to validate `wanctl@${WAN}` and health while stale external-mode components are still running.
**Fix:** Verify every external-mode unit disabled by the rollback sequence before validating the native unit and health, and add shim tests for active bridge/watchdog states.

```bash
external_units=(
  "cake-autorate-${WAN}.service"
  "cake-autorate-${WAN}-state-bridge.service"
)
if [[ "$WAN" == "att" ]]; then
  external_units+=("silicom-bypass-watchdog-cake-autorate-att.service")
fi

for unit in "${external_units[@]}"; do
  state="$(ssh -n "${SSH_OPTS[@]}" "$SSH_HOST" "systemctl is-active ${unit} || true")"
  if [[ "$state" == "active" || "$state" == "activating" ]]; then
    echo "ROLLBACK VERIFY FAILED: ${unit} is still ${state}" >&2
    exit 1
  fi
done
```

## Info

### IN-01: Missing-value CLI options fall through to shell `shift` failures

**File:** `scripts/check-cleanup-boundary.sh:49-55`, `scripts/phase231-rollback.sh:318-320`, `scripts/phase231-migration-held.sh:403-404`
**Issue:** Options that require values use `${2:-}` followed by `shift 2`. When a caller passes `--anchor`, `--out`, `--wan`, `--ssh-host`, or `--window-hours` without a value, `shift 2` can terminate under `set -e` with a shell-level error/exit instead of the scripts' usage/validation path.
**Fix:** Add a helper such as `require_option_value "$1" "${2:-}"` before each `shift 2`, print a script-owned error, and exit 2. Add focused tests for missing values on each public script.

---

_Reviewed: 2026-06-11T12:32:55Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
