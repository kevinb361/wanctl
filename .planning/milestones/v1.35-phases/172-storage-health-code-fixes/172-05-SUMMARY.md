---
phase: 172-storage-health-code-fixes
plan: 05
subsystem: deployment
tags: [gap-closure, deployment, wrapper-script, testing]
dependency_graph:
  requires: []
  provides: [deployable-analyze-baseline, subprocess-regression-test]
  affects: [scripts/analyze_baseline.py, scripts/deploy.sh, tests/test_analyze_baseline.py]
tech_stack:
  added: []
  patterns: [sys.path-bootstrap, subprocess-wrapper-test]
key_files:
  created: []
  modified:
    - scripts/analyze_baseline.py
    - scripts/deploy.sh
    - tests/test_analyze_baseline.py
decisions:
  - Used existing compare_ab.py sys.path bootstrap pattern for consistency
metrics:
  duration_seconds: 94
  completed: "2026-04-12T16:31:21Z"
  tasks_completed: 2
  tasks_total: 2
  test_count: 4
  test_pass: 4
---

# Phase 172 Plan 05: Fix analyze_baseline Deployment Gap Summary

**One-liner:** sys.path bootstrap + deploy array population + subprocess test closes DEPL-02 verification gap for analyze_baseline.py

## What Was Done

### Task 1: Fix wrapper bootstrap and populate deploy array (1e94c3b)
- Rewrote `scripts/analyze_baseline.py` with sys.path bootstrap matching the established `compare_ab.py` pattern (dev layout via `_script_dir.parent / "src"`, prod layout via `_script_dir.parent.parent`)
- Populated `ANALYSIS_SCRIPTS` array in `scripts/deploy.sh` with `scripts/analyze_baseline.py` so `deploy_analysis_scripts()` deploys the wrapper to `/opt/wanctl/scripts/` on target hosts
- Verified `python3 scripts/analyze_baseline.py --help` exits 0 from repo root

### Task 2: Add subprocess wrapper execution test (e3e0f4b)
- Added `test_wrapper_script_runs_as_subprocess()` to `tests/test_analyze_baseline.py`
- Test invokes `scripts/analyze_baseline.py` as a child process via `subprocess.run()`, asserting exit code 0 and expected help text
- Catches ModuleNotFoundError regressions that in-process import tests cannot detect
- All 4 tests in file pass, regression slice (analyze_baseline + history_multi_db) passes 15/15

## Deviations from Plan

None - plan executed exactly as written.

## Verification

1. `python3 scripts/analyze_baseline.py --help` -- exits 0, prints usage
2. `grep -c "analyze_baseline.py" scripts/deploy.sh` -- returns match in ANALYSIS_SCRIPTS
3. `pytest tests/test_analyze_baseline.py -x` -- 4/4 pass
4. `pytest tests/test_analyze_baseline.py tests/test_history_multi_db.py -q` -- 15/15 pass

## Commits

| Task | Hash | Message |
|------|------|---------|
| 1 | 1e94c3b | fix(172-05): add sys.path bootstrap to analyze_baseline wrapper and populate deploy array |
| 2 | e3e0f4b | test(172-05): add subprocess wrapper execution test for analyze_baseline |

## Self-Check: PASSED

All files exist, all commits verified.
