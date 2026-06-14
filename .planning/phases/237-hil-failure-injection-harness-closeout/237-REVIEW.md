---
phase: 237-hil-failure-injection-harness-closeout
reviewed: 2026-06-14T01:04:38Z
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
  critical: 1
  warning: 1
  info: 0
  total: 2
status: issues_found
---

# Phase 237: Code Review Report

**Reviewed:** 2026-06-14T01:04:38Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Re-reviewed the listed Phase 237 files after Plan 05 gap closure. The two requested prior findings are resolved: pair arguments are now allowlisted before result path creation or mutation, and bare `SILICOM_BYPASS=silicom-bypass` is resolved through `PATH` before live-gate comparison.

Two previously identified issues remain outside the Plan 05 closure scope: `deploy.sh` still uses `eval` around rsync options and operator-provided target text, and the Silicom runbook still contains a raw watchdog `systemctl restart` command that conflicts with W-INV guidance.

## Previous Findings Re-check

- **Previous CR-01:** Resolved. `scripts/silicom-test:329-355` now calls `validate_pair "$pair"` before `require_live_gate`, `init_run_dir`, `mark_touched`, and any Silicom mutation for both `failover` and `ab-cake`. Regression coverage in `tests/test_silicom_test_harness.py:164-194` verifies malformed and unknown pairs create no result directories and trigger no mutation calls.
- **Previous WR-01:** Resolved. `scripts/silicom-test:210-228` now resolves bare commands via `command -v -- "$cmd"` before canonical `realpath` comparison. Regression coverage in `tests/test_silicom_test_harness.py:197-231` verifies `SILICOM_BYPASS=silicom-bypass` refuses as live without `SILICOM_TEST_LIVE_CONFIRM` when it resolves to the canonical CLI.

## Critical Issues

### CR-02: `eval rsync` permits local shell injection through deploy arguments

**File:** `scripts/deploy.sh:224-233`
**Issue:** `deploy_code()` constructs `rsync_opts` as a shell string and executes it through `eval rsync ... "$TARGET_HOST:$TARGET_CODE_DIR/"`. `TARGET_HOST` comes from CLI input, so shell metacharacters in a malformed target can execute unintended local commands during deployment.
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

### WR-02: Runbook still recommends raw watchdog restart despite W-INV

**File:** `docs/SILICOM-BYPASS.md:741-746`
**Issue:** The Spectrum restore checklist still tells operators to run `sudo systemctl restart silicom-bypass-watchdog@spectrum.service`, while the same runbook’s W-INV section forbids raw watchdog stop/disable/restart/mask because ExecStop can fail-open without the operator-disarm sentinel. This is risky production operator guidance.
**Fix:** Replace the raw restart with sanctioned CLI lifecycle guidance, for example:

```bash
sudo systemctl restart wanctl-nic-tuning.service
sudo systemctl restart wanctl@spectrum.service
sleep 3
sudo silicom-bypass arm spec-modem --yes
systemctl is-active wanctl@spectrum.service silicom-bypass-watchdog@spectrum.service bpctl-silicom.service
```

---

_Reviewed: 2026-06-14T01:04:38Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
