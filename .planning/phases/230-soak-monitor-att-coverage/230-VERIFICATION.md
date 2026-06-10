---
phase: 230-soak-monitor-att-coverage
verified: 2026-06-10T02:45:01Z
status: passed
score: 7/7 must-haves verified
overrides_applied: 0
---

# Phase 230: soak-monitor ATT Coverage Verification Report

**Phase Goal:** soak-monitor observes the actual live ATT external-controller units instead of the disabled native service, and handles ATT external-controller mode at full Spectrum parity — closing the migration's live observability hole.
**Verified:** 2026-06-10T02:45:01Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | soak-monitor error-scan reads the live ATT units instead of disabled `wanctl@att.service`, demonstrated against live journals/scan output. | ✓ VERIFIED | `scripts/soak-monitor.sh` maps `att` to `cake-autorate-att.service`, `cake-autorate-att-state-bridge.service`, and `silicom-bypass-watchdog-cake-autorate-att.service` via `external_units_for` (lines 283-289). Evidence note records live `--json` aggregate units containing all three ATT units and excluding `wanctl@att.service` (230-MON01-EVIDENCE.md lines 111-130). |
| 2 | soak-monitor mode detection has no Spectrum-only hardcoding at the Phase 230 call sites; ATT external-controller mode is handled at Spectrum parity. | ✓ VERIFIED | `is_external_cake_mode "$ssh_target" "$wan_name"` is used in per-WAN JSON/table paths and aggregate unit generation (lines 273-315, 398-421, 476-499). Static check found old aggregate `is_spectrum_cake_trial_active "kevin@10.10.110.223"` count `0`. |
| 3 | All four former Spectrum-hardcoded call sites route ATT through the live-unit set in external mode and keep native `wanctl@att.service` only as fallback. | ✓ VERIFIED | Per-WAN JSON/table paths call `is_external_cake_mode` and pass `"${wan_units[@]}"` to `check_errors`; JSON/non-JSON aggregate paths both use `aggregate_units_for` and the same generated `service_units` array (lines 398-421, 476-499). Fake-ssh test asserts aggregate external-mode units exclude `wanctl@att.service`. |
| 4 | Unit lists pass into `check_errors` as bash arrays, not unquoted command-substitution word splitting. | ✓ VERIFIED | `read -r -a` appears in the per-WAN and aggregate helper paths; `shellcheck disable=SC2046` count is `0`; `shellcheck -S error scripts/soak-monitor.sh` passed. |
| 5 | Regression tests and behavior evidence prove MON-01/MON-02, including runtime `--json` aggregate output. | ✓ VERIFIED | `tests/test_soak_monitor_att_coverage.py` contains five tests including fake-ssh runtime `--json` assertion; `.venv/bin/pytest tests/test_soak_monitor_att_coverage.py -q` passed (`5 passed in 0.64s`). |
| 6 | A representative ATT-unit error condition is surfaced post-fix and missed pre-fix. | ✓ VERIFIED | `230-MON01-EVIDENCE.md` records local fake-ssh representative run: post-fix `att.errors_1h=3` and aggregate `errors_1h=3`; pre-fix with the same shim reports `0` (lines 191-360). |
| 7 | SAFE-14 controller-path zero-diff holds at the phase boundary. | ✓ VERIFIED | `git diff --stat 87980bdf -- <protected controller paths>` produced no diff; `git status --porcelain -- src/wanctl/` was clean; `git diff --name-only 4ad2986e -- scripts/ tests/` shows only `scripts/soak-monitor.sh` and `tests/test_soak_monitor_att_coverage.py`. Evidence recorded in `230-SAFE14-BOUNDARY.md`. |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `scripts/soak-monitor.sh` | WAN-parameterized external-mode predicate, ATT live-unit map, generalized per-WAN and aggregate scans. | ✓ VERIFIED | Substantive implementation present; wired in runtime paths; shellcheck clean. |
| `tests/test_soak_monitor_att_coverage.py` | Static + fake-ssh behavior regression tests for ATT coverage and generalized predicate. | ✓ VERIFIED | Five tests present; focused suite passed. |
| `.planning/phases/230-soak-monitor-att-coverage/230-MON01-EVIDENCE.md` | Live unit-set contrast and representative ATT-error proof. | ✓ VERIFIED | Contains live post-fix units, mode-detection statuses, pinned pre-fix contrast, post=3/pre=0 representative run. |
| `.planning/phases/230-soak-monitor-att-coverage/230-SAFE14-BOUNDARY.md` | SAFE-14 zero-diff and scope-accounting proof. | ✓ VERIFIED | Contains two baselines, empty protected diff, clean dirty-tree status, two-file scope list, test results. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| per-WAN error scan | ATT live units | `is_external_cake_mode` → `external_units_for` → `check_errors "${wan_units[@]}"` | ✓ WIRED | Both JSON and table per-WAN branches use the generalized path. |
| aggregate JSON/non-JSON scan | Same live unit set | `aggregate_units_for` → `service_units` array → JSON units/label/hint and `check_errors` | ✓ WIRED | JSON output and non-JSON summary derive from the same generated array. |
| regression tests | real script behavior | fake PATH `ssh` shim running `bash scripts/soak-monitor.sh --json` | ✓ WIRED | Test asserts aggregate units include ATT live units, `steering.service` once, and exclude `wanctl@att.service`. |
| evidence artifacts | committed code/history | live `--json`, `git show 4ad2986e`, SAFE diffs | ✓ WIRED | Recent commits include implementation, evidence, boundary proof, and review artifacts. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `scripts/soak-monitor.sh` | `wan_units` / `service_units` | `TARGETS` → `is_external_cake_mode` → `external_units_for` / native fallback | Yes | ✓ FLOWING — generated arrays feed both `check_errors` and reported JSON/labels. |
| `tests/test_soak_monitor_att_coverage.py` | `units` from parsed JSON | Actual script stdout under fake `ssh` shim | Yes | ✓ FLOWING — test invokes the script, parses JSON, and checks runtime output. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Focused Phase 230 regression suite passes | `.venv/bin/pytest tests/test_soak_monitor_att_coverage.py -q` | `5 passed in 0.64s` | ✓ PASS |
| soak-monitor is shellcheck-clean | `shellcheck -S error scripts/soak-monitor.sh` | exit 0, no output | ✓ PASS |
| SAFE-14 protected paths unchanged | `git diff --stat 87980bdf -- <protected paths>` | empty output | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| MON-01 | 230-01, 230-02 | soak-monitor error-scan covers live ATT units instead of disabled `wanctl@att.service`. | ✓ SATISFIED | Code maps ATT external mode to all three live units; tests and evidence prove aggregate/per-WAN runtime coverage and post=3/pre=0 representative error contrast. |
| MON-02 | 230-01, 230-02 | soak-monitor handles ATT external-controller mode at Spectrum parity; no Spectrum-only mode hardcoding. | ✓ SATISFIED | WAN-parameterized `is_external_cake_mode` drives per-WAN and aggregate scan selection; static check confirms old hardcoded aggregate call removed. |

No orphaned Phase 230 requirements found in `.planning/REQUIREMENTS.md`; MON-01 and MON-02 are both claimed by both plans and accounted for above.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| — | — | None blocking | — | Grep scan found no TODO/FIXME/placeholders, SC2046 suppressions, old aggregate hardcoding, or old hardcoded journal hint in changed implementation/test files. |

### Human Verification Required

None. Live/external evidence requiring operator confirmation was already captured in committed evidence (`230-MON01-EVIDENCE.md`) and cross-checked against code and tests here.

### Gaps Summary

No gaps found. Phase 230 achieved its goal: ATT external-controller monitoring now targets live units at Spectrum parity, tests guard the behavior, representative evidence proves the blind spot is closed, and SAFE-14 holds.

---

_Verified: 2026-06-10T02:45:01Z_  
_Verifier: the agent (gsd-verifier)_
