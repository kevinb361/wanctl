---
phase: 232-cleanup-boundary-guard-tooling-fixes
verified: 2026-06-11T12:36:04Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 3/4
  gaps_closed:
    - "BOUND-01 guard now fails closed when an anchor-present protected file is removed from the git index while content remains in the worktree."
    - "BOUND-01 guard now treats protected manifest rows as regular files and fails closed when a protected file is replaced by a directory."
  gaps_remaining: []
  regressions: []
---

# Phase 232: Cleanup Boundary Guard + Tooling Fixes Verification Report

**Phase Goal:** Cleanup Boundary Guard + Tooling Fixes. Phase 232 must deliver BOUND-01 before sweep work, fix the Phase 231 rollback confirm-path tooling risk (FIX-01), validate/close the operator-summary digest permission todo without blind reimplementation (FIX-02), and verify SAFE-15 controller-path zero-diff at the phase boundary.
**Verified:** 2026-06-11T12:36:04Z
**Status:** passed
**Re-verification:** Yes — after BOUND-01 gap closure in `232-04-PLAN.md`

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A guard (script/test) encodes the future-doc denylist — `src/wanctl/autorate_continuous.py`, native deploy path, native controller tests, native config validation, rollback commands/docs — and fails closed if any denylisted surface is touched/removed; operator can run it on demand and it is wired so sweep work cannot proceed past a denylist violation (BOUND-01). | ✓ VERIFIED | `scripts/check-cleanup-boundary.sh` contains the 26-row manifest, explicit `must-match-anchor` / `must-exist` policies, `--print-manifest`, JSON evidence, and exit 0/1/2 contract. Re-run passed on current repo. Gap-closure spot checks now return exit 1 with row statuses `UNTRACKED` for `git rm --cached src/wanctl/autorate_continuous.py` and `NON_FILE` for `scripts/phase231-rollback.sh` replaced by a directory. `tests/test_cleanup_boundary_guard.py` has default-suite and scratch-repo tests covering clean, missing, untracked, modified immutable, must-exist drift/removal, directory replacement, anchor-absent future-doc, and unknown-anchor behavior. |
| 2 | `phase231-rollback.sh` no longer carries the confirm-path risk flagged in the v1.50 Phase 231 code review, remains double-gated and dry-run by default, and a test/inspection demonstrates the fix without performing any live rollback or production mutation (FIX-01). | ✓ VERIFIED | `run_confirm()` prepends `set -euo pipefail`, invokes `ssh ... "bash -s" <"$remote_script"` without `-n`, refuses confirm unless `--i-have-operator-approval` is present, and fails closed when `cake-autorate-${WAN}.service` is `active` or `activating`. `tests/test_phase231_rollback.py` verifies payload first line, argv excluding `-n`, read-only probes retaining `-n`, external-writer failure states, check ordering, and preflight/dry-run read-only command logs. |
| 3 | The `2026-04-17-operator-summary-digest-permission-handling` todo is closed by validating behavior against v1.44 Phase 208 T12/TOOL-03, with tests/recorded evidence and no blind reimplementation (FIX-02). | ✓ VERIFIED | Closed todo exists with `closed_by_phase: 232` and verdict `validated_already_implemented_v144_phase208_tool03`; pending todo is absent. `evidence/fix02-digest-validation.md` maps each tolerance truth to `tests/test_operator_digest.py`, records a fresh `9 passed` run, documents query-error behavior accurately, and states no `src/wanctl/operator_summary.py` reimplementation was required. |
| 4 | SAFE-15 controller-path zero-diff holds at the phase boundary and is verified, not assumed. | ✓ VERIFIED | `evidence/safe15-boundary-232.json` has `passed: true`, `controller_path_diff_count: 0`, and per-file object IDs equal vs `v1.50`. Re-ran `scripts/phase225-safe13-boundary-check.sh --anchor v1.50` successfully and independently checked `git diff --quiet v1.50..HEAD -- src/wanctl/wan_controller.py src/wanctl/wan_controller_state.py src/wanctl/queue_controller.py src/wanctl/cake_signal.py src/wanctl/alert_engine.py src/wanctl/fusion_healer.py src/wanctl/backends/`. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `scripts/check-cleanup-boundary.sh` | BOUND-01 denylist guard with JSON evidence, on-demand CLI, explicit per-row policies, fail-closed file/index classification | ✓ VERIFIED | Exists, executable/substantive, shell syntax and shellcheck pass. Classification order is `MISSING`, `NON_FILE`, `UNTRACKED`, `MODIFIED`, `allowlisted-modified`, `ok`; violation set includes `MISSING`, `NON_FILE`, `UNTRACKED`, `MODIFIED`. |
| `tests/test_cleanup_boundary_guard.py` | Default-suite gate plus synthetic fail-closed proofs | ✓ VERIFIED | Exists and focused tests pass (`9` cleanup-boundary tests inside `40 passed` phase slice). Contains regression tests for `git rm --cached` and directory replacement. `gsd-sdk verify.artifacts` missed the spaced tokenized form of `git", "rm", "--cached"`; manual source verification confirms the behavior is present. |
| `scripts/phase231-rollback.sh` | Hardened confirm path with fail-fast remote preamble and external-writer post-check | ✓ VERIFIED | `run_confirm()` includes the fail-fast preamble, no `-n` on `bash -s`, double gate, and `active`/`activating` check for the main external cake service. |
| `tests/test_phase231_rollback.py` | Shim-based confirm-path proof and read-only assertions | ✓ VERIFIED | Tests execute the real script through a PATH-injected SSH shim and assert payload, argv, failure states, ordering, and no mutation verbs in read-only modes. |
| `scripts/phase231-migration-held.sh` | WR-01 SC2318 fix | ✓ VERIFIED | `metrics_check()` assigns `wan` before deriving `db`, matching the planned shellcheck fix. |
| `.planning/todos/closed/2026-04-17-operator-summary-digest-permission-handling.md` | Closed todo with phase/verdict and Resolution | ✓ VERIFIED | File exists with `closed_by_phase: 232`, verdict, and Resolution pointing to Phase 232 evidence. |
| `.planning/phases/232-cleanup-boundary-guard-tooling-fixes/evidence/fix02-digest-validation.md` | FIX-02 validation evidence | ✓ VERIFIED | Contains implementation anchor, truth→test mapping, fresh pytest output, supplemental live-check record, and MET verdict. |
| `.planning/phases/232-cleanup-boundary-guard-tooling-fixes/evidence/safe15-boundary-232.json` | SAFE-15 boundary proof JSON | ✓ VERIFIED | `passed: true`, `controller_path_diff_count: 0`, `dirty_tree_clean: true`, and matching per-file object IDs are present. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `tests/test_cleanup_boundary_guard.py` | `scripts/check-cleanup-boundary.sh` | `subprocess.run(["bash", str(SCRIPT), ...])` | ✓ WIRED | Real-repo and scratch-repo tests invoke the actual guard script; `gsd-sdk verify.key-links` passed for the gap-closure plan. |
| `scripts/check-cleanup-boundary.sh` | `.planning/cake-autorate-trials/WANCTL_CAKE_AUTORATE_FUTURE.md` | manifest row sourced from future-doc denylist | ✓ WIRED | Manifest includes the future doc as `must-exist`; anchor-absent scratch test confirms untracked regular file is allowed but deletion fails. |
| `scripts/check-cleanup-boundary.sh` | git index state | `git ls-files --error-unmatch` | ✓ WIRED | `is_tracked()` feeds `anchor_present and not tracked` classification before hash checks; independent spot check returned `UNTRACKED`. |
| `tests/test_phase231_rollback.py` | `scripts/phase231-rollback.sh` | PATH-injected ssh shim + subprocess | ✓ WIRED | Tests execute the real script and capture ssh argv/stdin. |
| `scripts/phase231-rollback.sh` | `cake-autorate-${WAN}.service` | post-rollback `systemctl is-active` verification | ✓ WIRED | Main external cake service checked for `active` and `activating`. Advisory review WR-01 recommends also checking bridge/watchdog units before any live rollback, but the Phase 231 CR-01 confirm-path fix is present. |
| `evidence/fix02-digest-validation.md` | `tests/test_operator_digest.py` | truth→test mapping | ✓ WIRED | Evidence names each pinning test and includes fresh run output. |
| `evidence/safe15-boundary-232.json` | `scripts/phase225-safe13-boundary-check.sh` | `--anchor v1.50 --out` invocation | ✓ WIRED | JSON schema and values match the established checker output. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `scripts/check-cleanup-boundary.sh` | `checks[]`, `violations[]` | Embedded manifest + `git rev-parse`, `git hash-object`, `git ls-files`, `Path.exists()`, `Path.is_file()` | Yes | ✓ FLOWING — real git/worktree state drives JSON rows and exit code; previous hollow edge is closed by enforced `UNTRACKED` and `NON_FILE` statuses. |
| `tests/test_cleanup_boundary_guard.py` | scratch repo states | `git init`, manifest-generated files, `git rm --cached`, file unlink/mkdir mutations in temp repos | Yes | ✓ FLOWING — tests mutate only temp repos and assert guard JSON rows. |
| `scripts/phase231-rollback.sh` | `remote_script`, `external_active`, `active` | generated rollback commands + SSH `systemctl is-active` probes | Yes | ✓ FLOWING for the planned CR-01/main cake-service check. |
| `fix02-digest-validation.md` | T12/TOOL-03 evidence | `tests/test_operator_digest.py` run output and code/test mapping | Yes | ✓ FLOWING evidence artifact. |
| `safe15-boundary-232.json` | protected file object IDs/diff counts | `scripts/phase225-safe13-boundary-check.sh --anchor v1.50` | Yes | ✓ FLOWING proof artifact. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Cleanup guard passes current repo | `bash scripts/check-cleanup-boundary.sh --out /tmp/bound01-reverify.json` | `cleanup boundary check passed`; JSON `overall_pass: true`, 26 checks | ✓ PASS |
| Focused phase tests pass | `.venv/bin/pytest -o addopts='' tests/test_cleanup_boundary_guard.py tests/test_phase231_rollback.py tests/test_phase231_migration_held.py tests/test_operator_digest.py -q` | `40 passed in 3.55s` | ✓ PASS |
| Static checks pass | `bash -n scripts/check-cleanup-boundary.sh && shellcheck scripts/check-cleanup-boundary.sh && .venv/bin/ruff check ...` | `All checks passed!` | ✓ PASS |
| SAFE-15 recheck passes | `bash scripts/phase225-safe13-boundary-check.sh --anchor v1.50 --out /tmp/safe15-reverify.json && git diff --quiet v1.50..HEAD -- src/wanctl/...` | boundary check passed; independent diff exit 0 | ✓ PASS |
| Guard fails closed on git-index removal of protected file | Scratch repo: `git rm --cached src/wanctl/autorate_continuous.py`; run guard | exit 1, row `status: UNTRACKED`, `tracked: false`, `is_file: true` | ✓ PASS |
| Guard fails closed on protected file replaced by directory | Scratch repo: replace `scripts/phase231-rollback.sh` file with directory; run guard | exit 1, row `status: NON_FILE`, `exists: true`, `is_file: false` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| BOUND-01 | 232-01, 232-04 | Machine-checkable guard encodes no-delete list; sweep fails closed if denylisted surface is touched/removed | ✓ SATISFIED | Guard/test artifacts exist and are wired; previous bypasses now fail with `UNTRACKED`/`NON_FILE`; focused tests and independent spot checks pass. |
| FIX-01 | 232-02 | Rollback confirm-path risk fixed; script dry-run/double-gated; no live rollback | ✓ SATISFIED | Source and shim tests verify fail-fast preamble, no `-n` on payload, approval gate, read-only preflight/dry-run, and main cake-service post-check. |
| FIX-02 | 232-03 | Digest permission todo closed by validation/evidence; no reimplementation unless unmet | ✓ SATISFIED | Closed todo + validation evidence + `tests/test_operator_digest.py` green; no Plan 03 source reimplementation. |
| SAFE-15 | 232-03 / cross-phase invariant | Controller-path zero-diff at phase boundary | ✓ SATISFIED | JSON proof and independent diff recheck confirm no controller-path diff vs `v1.50`. |

All requested IDs are accounted for in PLAN frontmatter and REQUIREMENTS.md. REQUIREMENTS.md maps SAFE-15 to Phase 234 for closeout accounting and explicitly notes verification at 232/233/234 boundaries; Phase 232 includes and verifies it.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `tests/test_cleanup_boundary_guard.py` | 91 | `placeholder for {path}` scratch content | ℹ️ Info | Intentional temp-repo fixture content; not runtime/user-visible data. |
| `scripts/phase231-rollback.sh` | 283-287 | Advisory WR-01 from updated review: only primary `cake-autorate-${WAN}.service` is post-verified inactive/activating | ⚠️ Warning | Residual hardening concern for state-bridge/watchdog units before any future live rollback exercise; does not block FIX-01's scoped CR-01 confirm-path fix. |
| `scripts/check-cleanup-boundary.sh`, `scripts/phase231-rollback.sh`, `scripts/phase231-migration-held.sh` | option parsing | Advisory IN-01: missing option values can fall through to shell `shift` failure | ℹ️ Info | CLI usability/exit-code polish; not blocking the phase goal. |

### Human Verification Required

None. Verification was limited to repo-local scripts/tests/evidence; live rollback is explicitly out of scope, and the optional live digest check was supplemental evidence only.

### Gaps Summary

No blocking gaps remain. The initial BOUND-01 gaps were closed by Plan 232-04: the guard now rejects untracked anchor-present protected rows and non-file protected path replacements, and the tests pin both cases. FIX-01, FIX-02, and SAFE-15 remain verified with no regressions.

---

_Verified: 2026-06-11T12:36:04Z_  
_Verifier: the agent (gsd-verifier)_
