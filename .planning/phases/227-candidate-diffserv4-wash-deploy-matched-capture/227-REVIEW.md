---
phase: 227-candidate-diffserv4-wash-deploy-matched-capture
reviewed: 2026-06-04T16:53:33Z
depth: quick
files_reviewed: 4
files_reviewed_list:
  - scripts/phase226-baseline-capture.sh
  - scripts/phase227-qdisc-verify.sh
  - tests/test_phase227_marked_ef.py
  - tests/test_phase227_qdisc_verify.py
findings:
  critical: 0
  warning: 3
  info: 0
  total: 3
status: issues_found
---

# Phase 227: Code Review Report

**Reviewed:** 2026-06-04T16:53:33Z
**Depth:** quick
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Re-reviewed the interface-name validation fix for prior CR-01 in the Phase 226 baseline capture and Phase 227 qdisc verification scripts. Both scripts now validate operator-supplied interface names with a conservative allowlist before any SSH/qdisc command path, and focused tests cover unsafe names failing closed before SSH. Quick-pattern checks found no new critical issues in the reviewed scope.

Three prior warnings from the earlier full standard review remain recorded below as still-open phase review items.

## Resolved / Closed Issues

### CR-01: Interface values are interpolated into remote root shell commands — RESOLVED

**File:** `scripts/phase226-baseline-capture.sh:66-72,261-262` and `scripts/phase227-qdisc-verify.sh:45-51,175-176`

**Issue:** Operator-supplied interface names were previously embedded inside remote shell command strings that run under `sudo -n`, allowing a single quote in an interface value to break remote shell quoting.

**Resolution:** Both scripts now reject unsafe interface names using `^[A-Za-z0-9_.:-]+$` before command execution, and tests assert malicious names such as `spec-router';id` return exit code 2 before SSH.

## Warnings

### WR-01: Evidence completeness can pass without proving candidate qdisc mode is diffserv4 wash

**File:** `scripts/phase227-evidence-completeness.py:163-170` and `scripts/phase227-evidence-completeness.py:204-208`

**Issue:** `qdisc_files_are_complete()` only requires a CAKE qdisc line with any recognized mode token. It does not require `diffserv4` or `wash` for the candidate run tree. Also, `require_tin_separation()` returns early when summary tin fields look complete, so a candidate summary with diffserv4-like tins can be marked `verdict-ready` even if the raw run-tree qdisc files are besteffort/no-wash. That is a false-positive verification risk for Phase 228.

**Fix:** Add an expected mode/wash contract to the checker and enforce it for every before/during/after qdisc file in candidate evidence, for example:

```python
def qdisc_files_are_complete(run_dir: Path, *, expected_mode: str = "diffserv4", require_wash: bool = True) -> None:
    ...
    require(f" {expected_mode} " in f" {text} ", f"run {run_dir.name} qdisc not {expected_mode}: {path.name}")
    if require_wash:
        require(" wash" in text, f"run {run_dir.name} qdisc missing wash: {path.name}")
```

Then ensure `require_run_tree()` always calls this candidate-mode check before any summary-based early return.

### WR-02: Baseline summary ignores capture harness interface options

**File:** `scripts/phase226-baseline-summary.py:379-383`

**Issue:** The capture harness exposes `--router-iface` and `--modem-iface`, but the summary generator always reads `spec-router` and `spec-modem`. If an operator uses the documented options, capture can succeed but summary generation will read the wrong filenames and fail or silently omit the intended interface evidence. That undermines portability and evidence integrity.

**Fix:** Persist interface names into the manifest or pass them to the summary helper, then iterate those values instead of hardcoding Spectrum defaults:

```python
parser.add_argument("--router-iface", default="spec-router")
parser.add_argument("--modem-iface", default="spec-modem")
...
for iface in (args.router_iface, args.modem_iface):
    ...
```

Update `phase226-baseline-capture.sh` to call the summary helper with the selected interface names.

### WR-03: SAFE-13 regression test depends on live repository boundary state

**File:** `tests/test_phase227_safe13_boundary.py:20-33`

**Issue:** The test invokes the real boundary script against `v1.48` and expects the current worktree/HEAD to satisfy the SAFE-13 zero-diff boundary. That makes a regression test depend on unrelated repository state; future legitimate controller/config work can fail this test even if `wan_controller_state.py` remains protected. This is a test reliability issue, not just a style concern.

**Fix:** Split the unit assertion from the live boundary proof. Keep the source assertion that `wan_controller_state.py` is in the protected list, and move the full boundary script invocation to a phase evidence command or mark it as an explicit integration test requiring a clean phase-close tree.

---

_Reviewed: 2026-06-04T16:53:33Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: quick_
