---
phase: 237-hil-failure-injection-harness-closeout
reviewed: 2026-06-14T00:28:43Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - .claude/context.md
  - .gitignore
  - docs/SILICOM-BYPASS.md
  - scripts/deploy.sh
  - scripts/phase237-safe16-boundary-check.sh
  - scripts/silicom-test
  - scripts/silicom-test-scenarios/cake-ab-spectrum.sh
  - scripts/silicom-test-scenarios/failover-spectrum.sh
  - tests/test_silicom_bypass_cli.py
  - tests/test_silicom_test_harness.py
findings:
  critical: 2
  warning: 2
  info: 0
  total: 4
status: issues_found
---

# Phase 237: Code Review Report

**Reviewed:** 2026-06-14T00:28:43Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Reviewed the Phase 237 HIL harness, standalone deploy path, Silicom runbook updates, SAFE-16 evidence script, and regression tests. The harness has the right broad safety shape (restore traps, live gates, installed scenarios, ignored ephemeral results), but there are two security/safety issues that should be fixed before relying on it as an operator-facing production tool: unsanitized pair names can escape the intended result directory, and `deploy.sh` still uses `eval` around operator-supplied deployment arguments. Two additional warning-level issues affect fail-open safety guidance/gating.

## Critical Issues

### CR-01: Pair name is used in result paths before validation

**File:** `scripts/silicom-test:233-240`
**Issue:** `init_run_dir()` builds `RUN_DIR` directly from `PAIR`, and `cmd_failover()` / `cmd_ab_cake()` accept arbitrary pair strings before any local validation. A pair containing `/` or `..` can make the harness create/write artifacts outside `SILICOM_TEST_RESULT_ROOT`; malformed pair/scenario values are also interpolated into the generated Python in `write_result_json()`.
**Fix:** Validate pair tokens before `require_live_gate` and before `init_run_dir`, ideally restricting to the supported Silicom control pairs.

```bash
validate_pair() {
    case "$1" in
        att-modem|spec-modem) return 0 ;;
        *) die "unknown bypass pair: $1" 2 ;;
    esac
}

cmd_failover() {
    local pair="${1:-spec-modem}"
    [[ $# -le 1 ]] || die "failover accepts zero or one pair" 2
    validate_pair "$pair"
    require_live_gate "$pair"
    init_run_dir failover "$pair"
    ...
}
```

Also add regression coverage for rejecting `../escape`, `spec-modem/evil`, and unknown pair names without creating a result directory.

### CR-02: `eval rsync` permits local shell injection through deploy arguments

**File:** `scripts/deploy.sh:224-233`
**Issue:** `deploy_code()` constructs an option string and executes it through `eval rsync ... "$TARGET_HOST:$TARGET_CODE_DIR/"`. Because `TARGET_HOST` comes from CLI input, a malformed host containing shell metacharacters can execute unintended local commands. This is especially risky in a production deployment script that operators run from the repo.
**Fix:** Replace string+`eval` construction with a Bash array.

```bash
local rsync_opts=(-av --delete)
rsync_opts+=(--exclude=__pycache__ --exclude='*.pyc')
rsync_opts+=(--rsync-path='sudo rsync')
rsync_opts+=(--chmod=F644,D755 --chown=root:root)
if [[ "$DRY_RUN" == "true" ]]; then
    rsync_opts+=(-n)
fi

rsync "${rsync_opts[@]}" "src/wanctl/" "$TARGET_HOST:$TARGET_CODE_DIR/"
```

## Warnings

### WR-01: Live gate can be bypassed accidentally by using command-name `SILICOM_BYPASS`

**File:** `scripts/silicom-test:214-219`
**Issue:** `require_live_gate()` only enforces `SILICOM_TEST_LIVE_CONFIRM` when `realpath_or_literal "$SILICOM_BYPASS"` matches `/usr/local/sbin/silicom-bypass`. If an operator sets `SILICOM_BYPASS=silicom-bypass` and that resolves through `PATH` to the real installed CLI, `realpath` fails on the bare command name, returns the literal, and the live gate is skipped.
**Fix:** Resolve command names through `command -v` before comparing to the canonical path, while preserving test seams that point at temp-path fakes.

```bash
resolve_command_path() {
    case "$1" in
        */*) realpath "$1" 2>/dev/null || printf '%s\n' "$1" ;;
        *) command -v -- "$1" 2>/dev/null | xargs -r realpath 2>/dev/null || printf '%s\n' "$1" ;;
    esac
}
```

Add a test with `SILICOM_BYPASS=silicom-bypass` and `PATH` pointing at a symlink to `/usr/local/sbin/silicom-bypass` to prove the gate still refuses without `SILICOM_TEST_LIVE_CONFIRM`.

### WR-02: Runbook still recommends raw watchdog restart despite W-INV

**File:** `docs/SILICOM-BYPASS.md:741-746`
**Issue:** The Spectrum restore checklist tells operators to run `sudo systemctl restart silicom-bypass-watchdog@spectrum.service`, but the same runbook’s W-INV section forbids raw watchdog stop/disable/restart/mask because ExecStop can fail-open without the disarm sentinel. This is a production safety regression in operator guidance.
**Fix:** Replace the raw restart with the sanctioned CLI lifecycle sequence, e.g. `sudo silicom-bypass arm spec-modem --yes` after `wanctl@spectrum.service` is active, or explicitly document `silicom-bypass disarm spec-modem` before any raw service lifecycle operation if a special maintenance flow truly needs it.

---

_Reviewed: 2026-06-14T00:28:43Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
