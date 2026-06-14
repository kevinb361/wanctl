---
phase: 236-watchdog-fail-open-two-mode-reconciliation
fixed_at: 2026-06-12T22:05:50Z
review_path: .planning/phases/236-watchdog-fail-open-two-mode-reconciliation/236-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 236: Code Review Fix Report

**Fixed at:** 2026-06-12T22:05:50Z
**Source review:** `.planning/phases/236-watchdog-fail-open-two-mode-reconciliation/236-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 3
- Fixed: 3
- Skipped: 0

## Fixed Issues

### WR-01: Stale docs still instruct raw watchdog stop/restart outside W-INV

**Files modified:** `docs/SILICOM-BYPASS.md`
**Commit:** `6cdea1c6`
**Applied fix:** Replaced raw Spectrum watchdog `systemctl stop/restart` runbook commands with the sanctioned `silicom-bypass disarm spec-modem` / `silicom-bypass arm spec-modem --yes` flow and added a warning against raw watchdog lifecycle operations.

### WR-02: `arm` can create a partial watchdog env on missing/invalid env file

**Files modified:** `scripts/silicom-bypass`, `tests/test_silicom_bypass_cli.py`, `.claude/context.md`
**Commit:** `e979a3a1`
**Status:** fixed: requires human verification
**Applied fix:** `cmd_arm` now validates the watchdog env before mutating `TIMEOUT_MS`, then revalidates after the atomic timeout write; regression tests cover missing and invalid env files to ensure no timeout-only partial env is created.

### WR-03: Retired-variant test does not model the ExecStop-masked retirement path

**Files modified:** `tests/test_silicom_bypass_cli.py`
**Commit:** `913a8592`
**Status:** fixed: requires human verification
**Applied fix:** Extended the fake `systemctl` with an ExecStop-mask simulation and updated the retirement test to prove the masked disable does not run the bypass script, the shared sentinel remains until post-disable cleanup, cleanup is load-bearing, and subsequent real `@att` ExecStop still fail-opens. Kept unmasked sentinel and non-vacuity coverage.

## Skipped Issues

None.

## Verification

- `docs/SILICOM-BYPASS.md` re-read around the raw bridge procedure after WR-01.
- `.venv/bin/pytest tests/test_silicom_bypass_cli.py -k manual_reapply -q` → 1 passed.
- `bash -n scripts/silicom-bypass && .venv/bin/pytest tests/test_silicom_bypass_cli.py -k 'arm and env' -q` → 3 passed.
- `python -c "import ast; ast.parse(open('tests/test_silicom_bypass_cli.py').read())" && .venv/bin/pytest tests/test_silicom_bypass_cli.py -k retire_nobypass -q` → 1 passed.
- `.venv/bin/pytest tests/test_silicom_bypass_cli.py -k 'manual_reapply or (arm and env) or retire_nobypass or invariant' -q` → 6 passed.

---

_Fixed: 2026-06-12T22:05:50Z_
_Fixer: the agent (gsd-code-fixer)_
_Iteration: 1_
