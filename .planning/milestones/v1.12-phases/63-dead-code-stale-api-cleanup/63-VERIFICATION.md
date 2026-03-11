---
phase: 63-dead-code-stale-api-cleanup
verified: 2026-03-10T12:37:39Z
status: passed
score: 5/5 must-haves verified
re_verification: false
---

# Phase 63: Dead Code & Stale API Cleanup Verification Report

**Phase Goal:** Remove dead code (pexpect, subprocess import) and stale API surface (timeout_total) left over from icmplib migration
**Verified:** 2026-03-10T12:37:39Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #   | Truth                                                    | Status     | Evidence                                                               |
| --- | -------------------------------------------------------- | ---------- | ---------------------------------------------------------------------- |
| 1   | pexpect does not appear in pyproject.toml [project.dependencies] | VERIFIED | pyproject.toml lists 6 deps; grep returns 0 matches for "pexpect"     |
| 2   | rtt_measurement.py has no subprocess import              | VERIFIED   | No `import subprocess` line; imports are: concurrent.futures, logging, re, statistics, Enum, icmplib |
| 3   | RTTMeasurement constructor has no timeout_total parameter | VERIFIED  | `__init__` signature: logger, timeout_ping, aggregation_strategy, log_sample_stats only |
| 4   | No caller passes timeout_total to RTTMeasurement         | VERIFIED   | steering/daemon.py RTTMeasurement call at line 1942 has no timeout_total kwarg; grep across all src returns 0 matches |
| 5   | All 2,210+ existing tests pass with zero new failures    | VERIFIED   | 2207 tests passed in 278.87s (net reduction from 2210 expected; 3 dead-code tests removed per plan) |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact                              | Expected                                           | Status   | Details                                                                      |
| ------------------------------------- | -------------------------------------------------- | -------- | ---------------------------------------------------------------------------- |
| `pyproject.toml`                      | Production deps without pexpect                    | VERIFIED | 6 deps: requests, pyyaml, paramiko, tabulate, icmplib, cryptography          |
| `docker/Dockerfile`                   | pip install block without pexpect                  | VERIFIED | pip install block has exactly 6 packages matching pyproject.toml             |
| `scripts/install.sh`                  | Install script without pexpect references          | VERIFIED | grep -c pexpect returns 0                                                    |
| `src/wanctl/rtt_measurement.py`       | No subprocess import, no timeout_total param       | VERIFIED | Clean 4-param constructor; no subprocess in import list                      |
| `src/wanctl/steering/daemon.py`       | No timeout_total/timeout_ping_total plumbing       | VERIFIED | _load_timeouts has only timeout_ssh_command and timeout_ping; import is DEFAULT_STEERING_SSH_TIMEOUT only |
| `src/wanctl/timeouts.py`             | No DEFAULT_STEERING_PING_TOTAL_TIMEOUT; get_ping_timeout has no total param | VERIFIED | Constant absent; function signature is `get_ping_timeout(component: ComponentName) -> int` |

### Key Link Verification

| From                             | To                              | Via                              | Status   | Details                                                                              |
| -------------------------------- | ------------------------------- | -------------------------------- | -------- | ------------------------------------------------------------------------------------ |
| `src/wanctl/steering/daemon.py`  | `src/wanctl/rtt_measurement.py` | RTTMeasurement constructor call  | VERIFIED | Line 1942: `RTTMeasurement(logger, timeout_ping=config.timeout_ping, aggregation_strategy=RTTAggregationStrategy.MEDIAN, log_sample_stats=False)` — no timeout_total kwarg |
| `tests/test_rtt_measurement.py`  | `src/wanctl/rtt_measurement.py` | icmplib mock (not subprocess)    | VERIFIED | All 4 patch targets in test file use `"wanctl.rtt_measurement.icmplib.ping"`; class renamed TestIcmplibInHotPath |

### Requirements Coverage

| Requirement | Source Plan | Description                                                                                          | Status    | Evidence                                                                    |
| ----------- | ----------- | ---------------------------------------------------------------------------------------------------- | --------- | --------------------------------------------------------------------------- |
| DEAD-01     | 63-01-PLAN  | pexpect removed from production dependencies (moved to dev extras or removed entirely)               | SATISFIED | Absent from pyproject.toml, requirements.txt, docker/Dockerfile, install.sh |
| DEAD-02     | 63-01-PLAN  | Dead subprocess import removed from rtt_measurement.py and affected tests refactored to mock icmplib | SATISFIED | No subprocess import in rtt_measurement.py; tests mock icmplib.ping         |
| DEAD-03     | 63-01-PLAN  | Dead timeout_total parameter removed from RTTMeasurement API and all callers updated                | SATISFIED | Parameter gone from constructor; no caller passes it; timeouts.py simplified |

No orphaned requirements — REQUIREMENTS.md maps exactly DEAD-01, DEAD-02, DEAD-03 to Phase 63, all of which appear in 63-01-PLAN.md.

### Anti-Patterns Found

No anti-patterns found in the 9 files modified by this phase. Ruff check passes clean on all 9 modified files.

Note: 15 pre-existing ruff errors exist in unrelated test files (test_autorate_telemetry.py — unsorted imports and unused loop variables). These predate this phase and are not attributable to Phase 63 work.

Note: `src/wanctl.egg-info/requires.txt` still lists pexpect, but this file is gitignored (stale build artifact from 2026-03-07, before the phase ran on 2026-03-10). It has no production impact.

### Human Verification Required

None. All aspects of this phase are verifiable programmatically — dependency removal, import removal, API signature changes, and test pass/fail are all greppable or runnable.

### Gaps Summary

No gaps. All 5 observable truths verified, all 6 artifacts substantive and wired, both key links confirmed, all 3 requirements satisfied by evidence in the codebase.

---

_Verified: 2026-03-10T12:37:39Z_
_Verifier: Claude (gsd-verifier)_
