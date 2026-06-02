---
phase: 223-staging-proof-clean-restart-reproduction
reviewed: 2026-06-02T18:13:51Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - .claude/context.md
  - tests/integration/__init__.py
  - tests/integration/steering_replay/fake_cake_reader.py
  - tests/integration/steering_replay/fake_live_rtt_source.py
  - tests/integration/steering_replay/fake_router_transport.py
  - tests/integration/steering_replay/fixtures/clean-restart-degraded.yaml
  - tests/integration/steering_replay/replay_harness.py
  - tests/integration/steering_replay/test_clean_restart.py
  - tests/integration/steering_replay/test_io_seal.py
  - tests/integration/steering_replay/test_replay_corpus.py
findings:
  critical: 0
  warning: 2
  info: 0
  total: 2
status: issues_found
---

# Phase 223: Code Review Report

**Reviewed:** 2026-06-02T18:13:51Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Reviewed the requested Phase 223 replay harness, fakes, clean-restart fixture, and integration tests for correctness, test reliability, I/O-seal coverage, and production WAN safety assumptions. No critical security or production-mutation issues were found in the reviewed files. Two warning-level evidence/test reliability issues should be fixed so the clean-restart proof remains reproducible and downstream audits can trust the declared observation contract.

## Warnings

### WR-01: Clean-restart fixture declares an observation target that evidence never emits

**File:** `tests/integration/steering_replay/fixtures/clean-restart-degraded.yaml:47` and `tests/integration/steering_replay/test_clean_restart.py:118`

**Issue:** The fixture declares `cycle_1_observed_current_state` as an observation target, but `_build_evidence()` writes the field as `cycle_1_observed_state`. Any downstream checker that verifies every declared `observation_targets` key exists in the JSON evidence will report the proof as incomplete even though the value is present under a different name.

**Fix:** Align the contract and emitted evidence. The lowest-churn fix is to update the fixture target to the existing evidence key:

```yaml
observation_targets:
  - pre_steering_rule_state
  - cycle_1_observed_state
  - cycle_1_effective_steering_state
```

Alternatively, keep the fixture name and add an alias in `_build_evidence()`:

```python
"cycle_1_observed_current_state": cycle_1_observed_state,
```

### WR-02: Documentation test depends on pre-existing generated evidence

**File:** `tests/integration/steering_replay/test_clean_restart.py:246-247`

**Issue:** `test_clean_restart_outcome_is_documented()` reads `clean-restart-reproduction.json` from `.planning/.../evidence/` without generating it or declaring a dependency on `test_clean_restart_reproduction_runs()`. This makes the test order- and workspace-dependent: it can pass against stale committed evidence, fail when run alone in a clean checkout before the evidence file exists, or race under parallel pytest execution.

**Fix:** Make the test self-contained by generating fresh evidence in the test, or combine the documentation assertions with the producer test. For example:

```python
def test_clean_restart_outcome_is_documented(staging_workspace: Path):
    fixture = _fixture()
    result = run_fixture(FIXTURE, staging_workspace / "clean-restart-degraded-doc")
    evidence = _build_evidence(result, fixture)

    assert evidence["outcome"] in (
        "reproduced-intentional",
        "reproduced-bug",
        "not-reproducible",
    )
    assert len(evidence["outcome_rationale"]) >= 40
```

---

_Reviewed: 2026-06-02T18:13:51Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
