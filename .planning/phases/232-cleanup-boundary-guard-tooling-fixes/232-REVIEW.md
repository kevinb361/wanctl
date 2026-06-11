---
phase: 232-cleanup-boundary-guard-tooling-fixes
reviewed: 2026-06-11T11:52:19Z
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
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 232: Code Review Report

**Reviewed:** 2026-06-11T11:52:19Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Reviewed the cleanup boundary guard, Phase 231 rollback tooling, migration-held evaluator, and their tests. The main concerns are guard bypass cases in the cleanup boundary script and incomplete fail-closed verification after a confirmed rollback. No critical security issues found.

## Warnings

### WR-01: Cleanup guard can pass protected files removed from git or replaced by directories

**File:** `scripts/check-cleanup-boundary.sh:184-197`
**Issue:** The guard records `tracked` but never enforces it, and uses `Path.exists()` instead of file-ness. A protected anchor-present path can be removed from the index while left in the worktree and still pass if its blob matches the anchor. For `must-exist` rows, replacing the protected file with a directory can also be reported as `allowlisted-modified` instead of a violation because `worktree_blob()` returns `None` and the status is not treated as failing. That weakens BOUND-01 as a commit/sweep gate.
**Fix:** Treat protected rows as real files and require tracked status for anchor-present manifest entries, while preserving the intentional anchor-absent living-doc exception.

```python
is_file = Path(path).is_file()
tracked = is_tracked(path)

if not is_file:
    status = "MISSING"
elif anchor_present and not tracked:
    status = "UNTRACKED"
elif policy == "must-match-anchor" and worktree_oid != anchor_oid:
    status = "MODIFIED"
elif policy == "must-exist" and anchor_present and worktree_oid != anchor_oid:
    status = "allowlisted-modified"
else:
    status = "ok"

if status in {"MISSING", "MODIFIED", "UNTRACKED"}:
    violations.append(row)
```

Add tests for `git rm --cached <protected-anchor-file>` and replacing a `must-exist` manifest file with a directory.

### WR-02: Confirmed rollback verification misses remaining external writer units

**File:** `scripts/phase231-rollback.sh:283-287`
**Issue:** `run_confirm()` fails closed only if `cake-autorate-${WAN}.service` remains active/activating. The rollback command disables both the cake service and `cake-autorate-${WAN}-state-bridge.service`, and ATT also switches watchdog units. If the bridge or ATT cake watchdog remains active after the remote payload, the script can continue to validate `wanctl@${WAN}` and health while stale external-mode components are still running.
**Fix:** Verify every external-mode unit disabled by the rollback sequence is inactive/failed/not-found before validating `wanctl@${WAN}` and health, and add shim tests for an active state bridge/watchdog.

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
**Issue:** Options that require values use `${2:-}` followed by `shift 2`. When a caller passes `--anchor`, `--out`, `--wan`, `--ssh-host`, or `--window-hours` without a value, `shift 2` can terminate under `set -e` with a shell error/exit 1 instead of the scripts' usage/validation path. The current tests cover unknown anchors and normal paths, but not missing option values.
**Fix:** Add a helper such as `require_option_value "$1" "${2:-}"` before each `shift 2`, print a script-owned error, and exit 2. Add focused tests for missing values on each public script.

---

_Reviewed: 2026-06-11T11:52:19Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
