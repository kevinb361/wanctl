---
phase: 231-migration-held-criteria-rollback-verification-doc-sweep
reviewed: 2026-06-10T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - .claude/context.md
  - README.md
  - docs/ARCHITECTURE.md
  - docs/CONFIGURATION.md
  - docs/DEPLOYMENT.md
  - scripts/phase231-migration-held.sh
  - scripts/phase231-rollback.sh
  - tests/test_phase231_migration_held.py
  - tests/test_phase231_rollback.py
findings:
  critical: 1
  warning: 2
  info: 0
  total: 3
status: issues_found
---

# Phase 231: Code Review Report

**Reviewed:** 2026-06-10T00:00:00Z
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Reviewed the Phase 231 documentation sweep, SOAK-01 migration-held evaluator, SOAK-02 rollback renderer/preflight/executor, and focused regression tests. The docs are broadly aligned with the current two-mode service model and the read-only evaluator/preflight paths avoid obvious RouterOS, systemd, and qdisc mutation. The main blocker is in the mutation-capable rollback confirm path: remote rollback execution can continue after earlier rollback commands fail, creating partial-rollback/dual-writer risk.

## Critical Issues

### CR-01: Rollback confirm path can continue after partial remote failure

**File:** `scripts/phase231-rollback.sh:277-280`

**Issue:** `run_confirm()` writes the generated rollback sequence to a temporary script and executes it with `ssh ... "bash -s"`, but the generated remote script does not start with `set -e`/`set -euo pipefail`. In bash, a non-interactive script without `set -e` continues after failed intermediate commands and returns the status of the last command. That means failures in critical earlier steps such as disabling `cake-autorate-*`, enabling `wanctl@*`, changing ATT bypass state, or the first `tc qdisc replace` can be masked if the final command succeeds. In production rollback this can leave partial state or dual rate-control writers while still proceeding to local verification.

**Fix:** Make the remote rollback script fail-fast before any mutation and verify the external writer is inactive after rollback. For example:

```bash
remote_script="${tmpdir}/rollback-remote.sh"
{
    printf '%s\n' 'set -euo pipefail'
    rollback_commands_for_wan "$WAN"
} >"$remote_script"
ssh -n "${SSH_OPTS[@]}" "$SSH_HOST" "bash -s" <"$remote_script"

external_active="$(ssh -n "${SSH_OPTS[@]}" "$SSH_HOST" "systemctl is-active cake-autorate-${WAN}.service || true")"
if [[ "$external_active" == "active" ]]; then
    echo "ROLLBACK VERIFY FAILED: cake-autorate-${WAN}.service is still active" >&2
    exit 1
fi
```

## Warnings

### WR-01: `metrics_check` relies on bash dynamic scoping for the metrics DB path

**File:** `scripts/phase231-migration-held.sh:136`

**Issue:** The `local` declaration assigns `wan="$2"` and `db="/var/lib/wanctl/metrics-${wan}.db"` in the same statement. ShellCheck reports SC2318 because `${wan}` is expanded before the `wan="$2"` assignment in that same `local` command takes effect. This currently works only because bash dynamic scoping exposes the caller's `wan` local from `evaluate_wan()`, but it is fragile and can compute the wrong DB path if this helper is reused or refactored.

**Fix:** Split the assignments so `db` is derived after the local `wan` is set:

```bash
metrics_check() {
    local ssh_target="$1" wan="$2"
    local db="/var/lib/wanctl/metrics-${wan}.db"
    local rows pass="false" query remote_cmd
    ...
}
```

### WR-02: Preflight regression test does not assert the remote command set is read-only

**File:** `tests/test_phase231_rollback.py:104-119`

**Issue:** `test_preflight_json_shape_att` validates the JSON shape and expected check names, but it does not inspect the shimmed SSH command log for mutation verbs. A future change could accidentally add `systemctl enable/disable/restart` or `tc qdisc replace` to `--preflight` and this test would still pass as long as the shim returned `ok` and the JSON shape remained intact. Since preflight is the safety proof path, this creates false confidence around the no-mutation guarantee.

**Fix:** After running preflight with the SSH shim, assert the recorded commands contain only read-only probes. For example:

```python
log_text = (tmp_path / "ssh.log").read_text(encoding="utf-8")
assert not re.search(r"systemctl\s+(enable|disable|restart|start|stop)", log_text)
assert not re.search(r"tc\s+qdisc\s+(replace|add|del)", log_text)
assert "systemctl is-active" in log_text
```

---

_Reviewed: 2026-06-10T00:00:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
