---
phase: 223-staging-proof-clean-restart-reproduction
reviewed: 2026-06-03T00:30:51Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - tests/integration/__init__.py
  - tests/integration/steering_replay/__init__.py
  - tests/integration/steering_replay/conftest.py
  - tests/integration/steering_replay/fake_router_transport.py
  - tests/integration/steering_replay/replay_harness.py
  - tests/integration/steering_replay/test_replay_corpus.py
  - tests/integration/steering_replay/test_clean_restart.py
findings:
  critical: 0
  warning: 2
  info: 0
  total: 2
status: issues_found
---

# Phase 223: Code Review Report

**Reviewed:** 2026-06-03T00:30:51Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Reviewed the requested offline steering replay integration tests and harness code for correctness, test reliability, I/O-seal behavior, and production-path safety. No critical security issues or live-router mutation paths were found in the reviewed files. Two warning-level reliability issues should be addressed so replay evidence remains trustworthy across harness modes and invocation contexts.

## Warnings

### WR-01: Confidence-mode fixtures can pass without checking expected decisions

**File:** `tests/integration/steering_replay/replay_harness.py:256-259`

**Issue:** `run_fixture()` only records decision mismatches when `fixture["harness_mode"] != "confidence"`. Confidence fixtures still carry per-cycle `expected_decision` entries, and `test_replay_fixture_matches()` treats `verdict == "matches"` as proof. With the current guard, a confidence-mode regression in `current_state` or `effective_mangle_state` can be missed as long as the I/O seal remains intact.

**Fix:** Compare expected decisions for confidence fixtures too, or make the skip explicit and cover confidence expectations elsewhere. The lowest-churn fix is to remove the mode guard:

```python
expected_decision = cycle.get("expected_decision")
if not _cycle_expected_matches(observed, expected_decision):
    mismatches.append(idx)
```

If confidence fixtures intentionally need partial observation, encode that with `expected_decision: observe` on the specific cycles rather than skipping the whole mode.

### WR-02: Operator-runnable harness depends on caller working directory

**File:** `tests/integration/steering_replay/conftest.py:121`

**Issue:** `build_replay_config()` reads `Path("configs/steering.yaml")`, which only works when pytest or the operator-runnable `replay_harness.py` is launched from the repository root. Direct script invocation from another directory can fail before replay starts, despite `replay_harness.py` explicitly setting `ROOT` and advertising operator-runnable behavior.

**Fix:** Resolve repository-relative paths from the file location instead of the process CWD. For example:

```python
ROOT = Path(__file__).resolve().parents[3]

def build_replay_config(workspace: Path, harness_mode: str = "hysteresis-only") -> SteeringConfig:
    source = yaml.safe_load((ROOT / "configs/steering.yaml").read_text())
    ...
```

Apply the same pattern to any other harness/test helper paths that are meant to work outside a repo-root pytest invocation.

---

_Reviewed: 2026-06-03T00:30:51Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
