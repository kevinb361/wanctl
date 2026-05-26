---
phase: 210-windowed-peak-accumulator-implementation
plan: 03
subsystem: safety-audit
tags: [wanctl, safe-10, audit, flapping-alerts]

# Dependency graph
requires:
  - phase: 210-windowed-peak-accumulator-implementation
    plan: 01
    provides: two-deque flapping peak-window production implementation
  - phase: 210-windowed-peak-accumulator-implementation
    plan: 02
    provides: flapping peak-window test coverage
provides:
  - SAFE-10 closeout evidence against committed HEAD and worktree
  - hunk-range proof for wan_controller.py-only source changes
  - window-deque-clear absence proof
affects: [phase-211-production-verification]

# Tech tracking
tech-stack:
  added: []
  patterns: [worktree-aware source-boundary audit, structural grep invariant]

key-files:
  created:
    - .planning/phases/210-windowed-peak-accumulator-implementation/210-03-SUMMARY.md
  modified: []

key-decisions:
  - "Use the v1.44 archive marker 21ee630 as the SAFE-10 baseline because c9932d2 resolves locally to a v1.42-era commit, not the v1.44 close point."

patterns-established:
  - "SAFE-10 closeout compares both baseline..HEAD and baseline..worktree, and records git status --porcelain verbatim."

requirements-completed: [SAFE-10]

# Metrics
duration: 4.1min
completed: 2026-05-26
---

# Phase 210 Plan 03: SAFE-10 Closeout Audit Summary

**SAFE-10 audit confirms Phase 210 source changes are isolated to `src/wanctl/wan_controller.py`, with no peak-window deque clears and all required test/static checks passing.**

## Baseline commit

Resolved baseline used for this audit: `21ee630`.

Resolution path: archive-fallback / equivalent v1.44 close marker, selected from the most recent commit whose subject is `chore: archive v1.44 phase directories`.

Important baseline note: `git rev-parse c9932d2` resolves in this checkout, but to `c9932d23fbb631111b365332db6f1e39622cc898` with subject `refactor(201-14): document rev-4 invariant and format implementation`, which is not the v1.44 close point. Using it would incorrectly include v1.44 source changes in the SAFE-10 diff. The plan permits `c9932d2 or equivalent`; `21ee630` is the local equivalent v1.44 archive marker.

Command output:

```text
BASELINE=21ee630
SUBJECT=chore: archive v1.44 phase directories
```

## Worktree status (git status --porcelain)

Command output:

```text
 M .planning/PROJECT.md
 D .planning/todos/pending/2026-04-17-ingestion-rate-tool.md
 D .planning/todos/pending/2026-04-17-operator-summary-digest-permission-handling.md
 D .planning/todos/pending/2026-04-28-add-silicom-bypass-nic-operational-tooling.md
 D .planning/todos/pending/2026-04-28-add-silicom-bypass-test-harness.md
```

Status note: worktree is non-empty, but all entries are `.planning/` paths. There are no uncommitted `src/` or `tests/` changes.

## src/wanctl/ HEAD diff stat

Command output:

```text
 src/wanctl/wan_controller.py | 19 +++++++++++--------
 1 file changed, 11 insertions(+), 8 deletions(-)
```

Assertion result: PASS — the only `src/wanctl/` file in `BASELINE..HEAD` is `src/wanctl/wan_controller.py`.

## src/wanctl/ worktree diff stat

Command output:

```text
 src/wanctl/wan_controller.py | 19 +++++++++++--------
 1 file changed, 11 insertions(+), 8 deletions(-)
```

Comparison to HEAD diff: identical. There are no uncommitted `src/wanctl/` changes beyond HEAD.

Assertion result: PASS — the only `src/wanctl/` file in `BASELINE..worktree` is `src/wanctl/wan_controller.py`.

## SAFE-09 allowlist diff (HEAD AND worktree)

Files checked:
- `src/wanctl/linux_cake.py`
- `src/wanctl/netlink_cake.py`
- `src/wanctl/cake_params.py`
- `src/wanctl/cake_signal.py`
- `src/wanctl/check_config_validators.py`

HEAD diff command output:

```text
```

Worktree diff command output:

```text
```

Assertion result: PASS — both outputs are empty; the SAFE-09 five-file allowlist is untouched in both HEAD and worktree diffs from the v1.44 close marker.

## alert_engine.py diff (HEAD AND worktree)

HEAD diff command output:

```text
```

Worktree diff command output:

```text
```

Assertion result: PASS — both outputs are empty; `alert_engine.py` is untouched and `cooldown_sec` semantics are preserved.

## wan_controller.py hunk inventory

Command output from `/tmp/safe10-hunks.txt`:

```text
@@ -730,2 +730,3 @@ class WANController:
@@ -4298,0 +4300 @@ class WANController:
@@ -4307 +4309,2 @@ class WANController:
@@ -4316 +4319 @@ class WANController:
@@ -4323 +4325,0 @@ class WANController:
@@ -4329,0 +4332 @@ class WANController:
@@ -4338 +4341,2 @@ class WANController:
@@ -4347 +4351 @@ class WANController:
@@ -4354 +4357,0 @@ class WANController:
```

## wan_controller.py automated hunk-range check

Allowed bounds recorded for audit:
- Region A: `__init__` flapping attrs, post-edit line range `725-745`
- Region B: `_check_flapping_alerts`, post-edit line range `4270-4370`

Script invocation:

```bash
git diff --unified=0 $BASELINE -- src/wanctl/wan_controller.py \
  | grep -E '^@@' \
  | awk '{print $3}' \
  | sed 's/^+//; s/,/ /' \
  | awk '
    {
      start = $1
      len   = ($2 == "" ? 1 : $2)
      end   = start + len - 1
      in_init  = (start >= 725 && end <= 745)
      in_alert = (start >= 4270 && end <= 4370)
      if (!(in_init || in_alert)) {
        printf "SAFE-10 VIOLATION: hunk %d-%d falls outside allowed regions (__init__ 725-745, _check_flapping_alerts 4270-4370)\n", start, end
        violations++
      }
    }
    END {
      if (violations) exit 1
      else exit 0
    }
  '
echo "AWK_EXIT=$?"
```

Command output:

```text
AWK_EXIT=0
```

Assertion result: PASS — every `wan_controller.py` diff hunk falls inside Region A or Region B.

## Window-deque-clear absence check

Detector-body check command:

```bash
awk '/def _check_flapping_alerts/,/^    def [^_]/' src/wanctl/wan_controller.py \
  | grep -cE "self\._(dl|ul)_peak_window_transitions\.clear\(\)"
```

Detector-body output:

```text
0
```

File-wide check command:

```bash
grep -cE "self\._(dl|ul)_peak_window_transitions\.clear\(\)" src/wanctl/wan_controller.py
```

File-wide output:

```text
0
```

Assertion result: PASS — no `_dl_peak_window_transitions.clear()` or `_ul_peak_window_transitions.clear()` call exists inside `_check_flapping_alerts` or anywhere in `wan_controller.py`.

Why this matters: the two-deque design depends on episode deques being cleared on fire while independent peak-window deques survive and drain only through `flap_window` pruning. Any explicit peak-window `.clear()` would reintroduce the ALERT-01 regression where `peak_transition_count > flap_threshold` cannot be reached under sustained fixed-threshold oscillation.

## Hot-path regression slice

Command:

```bash
.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q
```

Summary output:

```text
673 passed in 41.23s
```

Assertion result: PASS.

## Alerting + integration tests

Command:

```bash
.venv/bin/pytest tests/test_alert_engine.py tests/integration/test_flapping_integration.py -q
```

Summary output:

```text
132 passed in 7.00s
```

Assertion result: PASS.

## Static checks

Commands:

```bash
.venv/bin/ruff check src/wanctl/wan_controller.py tests/test_alert_engine.py tests/integration/test_flapping_integration.py
.venv/bin/mypy src/wanctl/wan_controller.py
```

Output:

```text
All checks passed!
Success: no issues found in 1 source file
```

Assertion result: PASS.

## SAFE-10 verdict

PASS.

Itemized check status:
- Baseline: PASS — used `21ee630` v1.44 archive marker as the local equivalent close baseline; direct `c9932d2` is documented as stale/mismatched in this checkout.
- Worktree status captured verbatim: PASS — non-empty only for `.planning/` paths; no uncommitted `src/` or `tests/` changes.
- `src/wanctl/` HEAD diff stat: PASS — only `src/wanctl/wan_controller.py`.
- `src/wanctl/` worktree diff stat: PASS — identical to HEAD diff; only `src/wanctl/wan_controller.py`.
- SAFE-09 allowlist diff: PASS — empty in both HEAD and worktree.
- `alert_engine.py` diff: PASS — empty in both HEAD and worktree.
- Hunk range check: PASS — `AWK_EXIT=0`; all hunks within `725-745` or `4270-4370`.
- Window-deque-clear absence: PASS — detector count `0`; file-wide count `0`.
- Hot-path regression slice: PASS — `673 passed in 41.23s`.
- Alerting + integration tests: PASS — `132 passed in 7.00s`.
- Static checks: PASS — ruff and mypy pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Audit correctness] Corrected stale baseline SHA resolution**
- **Found during:** Task 1 baseline resolution.
- **Issue:** The plan says direct `git rev-parse c9932d2` should identify the v1.44 close baseline, but in this checkout it resolves to `c9932d23fbb631111b365332db6f1e39622cc898`, subject `refactor(201-14): document rev-4 invariant and format implementation`. Diffing from that commit incorrectly includes v1.44 source changes and produces a false SAFE-10 violation.
- **Fix:** Used the plan's allowed `or equivalent` baseline path: the most recent `archive v1.44 phase directories` marker, `21ee630`, which matches the actual v1.44 close boundary in this repository.
- **Files modified:** `.planning/phases/210-windowed-peak-accumulator-implementation/210-03-SUMMARY.md`
- **Commit:** `c0c6c7a`

## Issues Encountered

- Pre-existing unrelated `.planning/` worktree changes were present before this plan started and are recorded verbatim in the Worktree status section. They were not staged or modified by this plan.

## Known Stubs

None.

## Threat Flags

None — this plan creates only an audit summary and introduces no network endpoints, auth paths, file access patterns, or trust-boundary schema changes.

## Self-Check: PASSED

- FOUND: `.planning/phases/210-windowed-peak-accumulator-implementation/210-03-SUMMARY.md`
- FOUND: task commit `c0c6c7a`

---
*Phase: 210-windowed-peak-accumulator-implementation*
*Completed: 2026-05-26*
