---
phase: 243-cycle-budget-benchmark-gate
verified: 2026-06-18T13:37:19Z
status: passed
score: 10/10 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 4/5
  gaps_closed:
    - "A valid pre-registered benchmark proves fping introduces no 50ms cycle-budget regression under the amended gate"
  gaps_remaining: []
  regressions: []
phase245_blocker_status: "Phase 243 benchmark gate blocker cleared under amended provenance-bearing threshold basis; Phase 245 still depends on Phase 244 health attribution metadata per roadmap."
---

# Phase 243: Cycle-Budget Benchmark Gate Verification Report

**Phase Goal:** A pre-registered, committed-before-the-run benchmark proves fping introduces no 50ms cycle-budget regression under a real systemd unit, and acts as a hard gate that blocks the live A/B on regression.
**Verified:** 2026-06-18T13:37:19Z
**Status:** passed
**Re-verification:** Yes — after 243-05 amendment and amended fixed-evidence verdict

## Goal Achievement

Phase 243 now achieves the benchmark-gate objective **under the Phase 243-05 amended gate semantics**. The original frozen threshold blob did **not** pass: `.planning/phases/243-cycle-budget-benchmark-gate/evidence/243-BENCHMARK-VERDICT-fixed.json` records `outcome: input_error` with the original thresholds blob `c39915330d4e77652ed48b981652a075b7835a71`.

The amendment does not rewrite that history. It creates a new provenance-bearing threshold basis in `scripts/phase243-thresholds.json` with `AMENDMENT_ID=243-05-production-calibrated-validity-semantics` and `AMENDS_THRESHOLDS_BLOB_SHA=c39915330d4e77652ed48b981652a075b7835a71`. The amended evaluator rerun over the existing fixed production evidence records `outcome: pass` in `.planning/phases/243-cycle-budget-benchmark-gate/evidence/243-BENCHMARK-VERDICT-amended.json`, with amended threshold blob SHA `1eb1af334ded03c674bde835fbfa76e4b3867e91`.

Phase 245 blocker status: the Phase 243 benchmark gate no longer blocks Phase 245. Roadmap-wise, Phase 245 still also depends on Phase 244 health-payload attribution metadata.

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Operator can run an idle-and-under-load cycle-budget + CPU benchmark of `fping` vs `icmplib` under a real systemd unit | ✓ VERIFIED | Previous harness gap remains closed; fixed production evidence exists under `evidence/production-run-fixed/` with all required selected arms and profile/hygiene inputs. |
| 2 | A pre-registered no-regression gate blocks the live A/B if fping regresses, leaks, zombies, or stalls | ✓ VERIFIED | `scripts/phase243-gate-eval.py` enforces avg/p99/CPU/n-floor/zombie/fd/stall/task gates, preserves `input_error` for malformed/incomplete inputs, and maps complete regressions to `rollback_trigger`. Focused tests cover pass and counterexamples. |
| 3 | Benchmark evidence is captured and the gate verdict is recorded | ✓ VERIFIED | `.planning/.../evidence/243-BENCHMARK-VERDICT-amended.json` exists, records all four pair comparisons (`att/idle`, `att/load`, `spectrum/idle`, `spectrum/load`), and records `outcome: pass`. |
| 4 | SAFE-17 boundary verifier passes / no controller-path drift | ✓ VERIFIED | `git diff --name-only -- src/wanctl`, `git diff --name-only 4670c6d5^ 4670c6d5 -- src/wanctl`, and `git diff --name-only 1a757b9a^ 1a757b9a -- src/wanctl` produced no output. `git show --name-only` confirms amendment commits touched planning/docs/scripts/tests only, not `src/wanctl`. |
| 5 | A valid benchmark proves no fping 50ms cycle-budget regression | ✓ VERIFIED | Re-ran the amended evaluator over existing fixed evidence to `/tmp/opencode/phase243-verifier-rerun.json`; output was `pass` with threshold blob `1eb1af334ded03c674bde835fbfa76e4b3867e91`. All amended verdict gates pass. |
| 6 | Phase 243 remains benchmark/evaluator-only with no controller behavior changes | ✓ VERIFIED | 243-05 changed `scripts/phase243-thresholds.json`, `scripts/phase243-gate-eval.py`, tests, docs, amendment/verdict artifacts; no `src/wanctl`, RouterOS/qdisc/service production behavior changes were present in amendment commits. |
| 7 | Fixed production evidence is treated as complete input, not invalidated by link-blind historical p99 ceilings | ✓ VERIFIED | Amended verdict has `p99_blocking: false`; Spectrum `p99_legacy_band_pass: false` at icmplib p99 12.1/12.6 but `gate_icmplib_representativeness` verdict still passes because avg representativeness remains the hard validity guard. |
| 8 | Gate amendment preserves BENCH-02 provenance without pretending original thresholds passed | ✓ VERIFIED | Amendment note lines 3-5 state original thresholds did not pass; threshold blob and amended verdict carry `AMENDS_THRESHOLDS_BLOB_SHA=c39915330d4e77652ed48b981652a075b7835a71`; fixed verdict remains `input_error`. |
| 9 | Representativeness/stall/task semantics measure fping regression rather than baseline noise | ✓ VERIFIED | Evaluator keeps same-run `gate_p99_delta_pct`, replaces zero-stall with count/rate limits, and uses backend-delta task semantics. Tests include fixed-run-like p99 12.1/12.6, stalls 1-2, fping tasks <=5 vs icmplib tasks 7-8, plus rollback counterexamples. |
| 10 | The evaluator is rerun against existing fixed evidence before any new production benchmark | ✓ VERIFIED | Recorded amended verdict and verifier rerun both used `evidence/production-run-fixed/`; runbook says do not launch another production run while complete fixed evidence still returns `input_error` under amended semantics. |

**Score:** 10/10 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `scripts/phase243-thresholds.json` | Amended thresholds with provenance metadata and bounded stall/task semantics | ✓ VERIFIED | Contains `AMENDMENT_ID`, `AMENDS_THRESHOLDS_BLOB_SHA`, `AMENDMENT_REASON`, `STALL_MAX_COUNT_PER_ARM=2`, `STALL_MAX_RATE_PCT=0.01`, and `TASKS_BACKEND_DELTA_BOUND=1`; original keys retained for audit. |
| `.planning/phases/243-cycle-budget-benchmark-gate/243-BENCHMARK-PREREGISTRATION-AMENDMENT.md` | Human-readable amendment preserving provenance | ✓ VERIFIED | States original thresholds did not pass, scope is benchmark/evaluator-only, new threshold blob is provenance-bearing, and no `src/wanctl`/controller/qdisc/service behavior changes occur. |
| `scripts/phase243-gate-eval.py` | Amended evaluator semantics | ✓ VERIFIED | Implements informational legacy p99, blocking avg representativeness, bounded stall count/rate, backend-delta tasks, fail-closed input errors, and pass/rollback outcomes. |
| `tests/test_phase243_gate_eval.py` | Regression tests for fixed-run-like values and counterexamples | ✓ VERIFIED | `24 passed`; tests cover Spectrum p99 12.1/12.6, fping p99 8.7/8.0, stalls, task deltas, malformed input, and rollback counterexamples. |
| `.planning/.../evidence/243-BENCHMARK-VERDICT-amended.json` | Local evaluator rerun over fixed production evidence | ✓ VERIFIED | Records `outcome: pass`, amended threshold metadata, four comparisons, and provenance blob SHA `1eb1af334ded03c674bde835fbfa76e4b3867e91`. |
| `docs/PHASE243-BENCHMARK-RUNBOOK.md` | Operator guidance for amended gate | ✓ VERIFIED | Section 7 explicitly states original thresholds did not pass, amended blob is a new basis, and no new production run should happen while complete fixed evidence returns `input_error`. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `phase243-gate-eval.py` | `phase243-thresholds.json` | `load_thresholds()` and threshold-key reads | ✓ WIRED | Evaluator loads the committed JSON blob and reads amended keys for task and stall gates. |
| `phase243-gate-eval.py` | amended verdict provenance | `_record_provenance()` | ✓ WIRED | Verdict provenance records threshold blob SHA and prereg commit SHA; amended verdict references the new threshold blob. |
| `phase243-gate-eval.py` | `production-run-fixed/` evidence | CLI `--arm` profile/hygiene inputs | ✓ WIRED | Verifier rerun over selected fixed evidence returned `pass` with all four pair IDs. |
| `tests/test_phase243_gate_eval.py` | fixed production evidence facts | fixed-run-like fixtures | ✓ WIRED | Tests encode p99/stall/task facts and fail real regression cases. |
| amendment note/runbook | original failed blob | `AMENDS_THRESHOLDS_BLOB_SHA` narrative | ✓ WIRED | Both artifacts preserve that original thresholds did not pass and that amended semantics are a new basis. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `phase243-gate-eval.py` | threshold values | `scripts/phase243-thresholds.json` via `load_thresholds()` | Yes | ✓ FLOWING |
| `phase243-gate-eval.py` | comparison gates | profile JSON + hygiene NDJSON + thresholds JSON | Yes | ✓ FLOWING |
| `243-BENCHMARK-VERDICT-amended.json` | verdict outcome | amended evaluator over existing fixed production evidence | Yes; `outcome: pass` | ✓ FLOWING |
| `tests/test_phase243_gate_eval.py` | counterexample expectations | constructed fixtures and real threshold blob | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Focused evaluator tests pass | `.venv/bin/pytest tests/test_phase243_gate_eval.py -q` | `24 passed in 0.94s` | ✓ PASS |
| Ruff passes for evaluator/test files | `.venv/bin/ruff check scripts/phase243-gate-eval.py tests/test_phase243_gate_eval.py` | `All checks passed!` | ✓ PASS |
| Amendment metadata and verdict provenance validate | Python JSON assertion over thresholds + amended verdict | `amendment provenance and pass verdict ok` | ✓ PASS |
| Amended evaluator reruns over fixed evidence | `python3 scripts/phase243-gate-eval.py ... --output /tmp/opencode/phase243-verifier-rerun.json` | `pass`, blob `1eb1af334ded03c674bde835fbfa76e4b3867e91`, four comparisons | ✓ PASS |
| SAFE-17/no source drift | `git diff --name-only -- src/wanctl` and amendment-commit `src/wanctl` diffs | no output | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| BENCH-01 | 243-02, 243-04 | Operator can run idle/load benchmark under real systemd unit | ✓ SATISFIED | Fixed production evidence exists and previous harness gap remains closed. |
| BENCH-02 | 243-01, 243-03, 243-04, 243-05 | Pre-registered/provenance-bearing no-regression gate blocks live A/B on regression/invalid input | ✓ SATISFIED | Original blob failed and is preserved; amended blob is a new provenance-bearing basis; amended verdict over fixed evidence is `pass`; regression/malformed-input tests pass. |
| SAFE-17 | 243-01, 243-04, 243-05 | No unapproved controller-path drift | ✓ SATISFIED | Amendment commits and working tree have no `src/wanctl` drift; changes are benchmark/evaluator/docs/tests/planning only. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| — | — | — | — | No blocker anti-patterns found in amended evaluator. `grep` for TODO/FIXME/placeholder/not-implemented/empty-return patterns in `scripts/phase243-gate-eval.py` found no matches. |

### Human Verification Required

None for this verifier decision. The amended gate outcome, provenance, and SAFE-17/no-drift checks are programmatically verifiable from committed artifacts.

### Gaps Summary

No gaps remain for Phase 243 after the 243-05 amendment. The earlier blocker was real for the original thresholds (`input_error`), but the amended threshold blob is explicitly provenance-bearing and the amended evaluator over fixed production evidence now produces `outcome: pass`. Phase 243's gate is therefore cleared under the amended basis.

---

_Verified: 2026-06-18T13:37:19Z_
_Verifier: the agent (gsd-verifier)_
