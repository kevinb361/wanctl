---
phase: 243-cycle-budget-benchmark-gate
plan: 05
subsystem: benchmarking
tags: [bench-02, safe-17, amendment, provenance, production-evidence, gate-eval]

requires:
  - phase: 243-cycle-budget-benchmark-gate
    provides: Plan 04 isolation-gated 8-arm production run, fixed evidence bundle, and the input_error fixed verdict
provides:
  - Provenance-bearing threshold amendment (new blob) that supersedes the link-blind icmplib p99 ceiling, zero-stall rule, and first-sample task gate without rewriting the failed frozen history
  - Amended gate evaluator measuring fping regression against same-run production evidence (bounded stall count/rate, backend-delta tasks)
  - Amended verdict outcome=pass produced by rerunning the evaluator over existing fixed evidence — no new production benchmark launched
affects: [phase-243, phase-245-ab, bench-02, safe-17]

tech-stack:
  added: []
  patterns:
    - Amend-don't-rewrite: failed frozen thresholds preserved; amendment is a new SHA-linked blob carrying AMENDMENT_ID + AMENDS_THRESHOLDS_BLOB_SHA
    - Link-aware representativeness: icmplib avg stays a hard input_error guard; historical p99 band kept informational (p99_blocking=false)
    - Local re-evaluation over committed fixed evidence; production benchmark rerun explicitly forbidden until local verdict resolves

key-files:
  created:
    - .planning/phases/243-cycle-budget-benchmark-gate/243-BENCHMARK-PREREGISTRATION-AMENDMENT.md
    - .planning/phases/243-cycle-budget-benchmark-gate/evidence/243-BENCHMARK-VERDICT-amended.json
  modified:
    - scripts/phase243-thresholds.json
    - scripts/phase243-gate-eval.py
    - tests/test_phase243_gate_eval.py
    - docs/PHASE243-BENCHMARK-RUNBOOK.md

key-decisions:
  - "Amended the gate semantics rather than rewriting the frozen thresholds; the original fixed verdict stays input_error and is preserved as failed preregistered history."
  - "icmplib p99 representativeness made informational (p99_blocking=false); gate_p99_delta_pct remains the canonical same-run fping-vs-icmplib p99 regression signal."
  - "Zero-stall rule replaced with bounded count/rate (<=2 per arm AND <=0.01%); first-sample task gate replaced with backend-delta (fping max <= icmplib max + 1)."
  - "No production benchmark rerun: the amended verdict was produced locally over the existing fixed evidence bundle."

patterns-established:
  - "A pre-registered gate is amended via a new provenance-bearing blob, never by editing the frozen one — the original failure remains auditable."
  - "Complete production evidence must not be rejected for link-specific jitter; input_error is reserved for genuinely missing/malformed inputs."
  - "Bounded-noise gates (stall count/rate, backend-delta tasks) tolerate real production baseline noise while still failing true fping regressions."

requirements-completed: [BENCH-02, SAFE-17]

duration: single session
completed: 2026-06-18
---

# Phase 243 Plan 05: Production-Calibrated Gate Amendment Summary

**Amended the benchmark gate semantics with a new provenance-bearing threshold blob so it measures fping regression instead of rejecting Spectrum link jitter, then re-ran the evaluator over existing fixed evidence to produce an `outcome: pass` amended verdict — with no controller-path changes and no new production run.**

## Context

Plan 04 completed the live 8-arm production benchmark but recorded `input_error` in `243-BENCHMARK-VERDICT-fixed.json`. The failure was not an fping regression — it was over-tight, link-blind validity semantics: Spectrum icmplib p99 (12.1 idle / 12.6 load) exceeded a historical absolute ceiling, isolated 1–2 stalls per arm tripped a zero-stall rule, and the task gate compared against an icmplib first-sample baseline (fping max tasks 5 vs icmplib max 7–8). Plan 05 amends benchmark/evaluator semantics only to fix this, preserving BENCH-02 preregistration provenance.

## Verdict

- **Outcome:** `pass` (amended) — recorded in `.planning/phases/243-cycle-budget-benchmark-gate/evidence/243-BENCHMARK-VERDICT-amended.json`, evaluated 2026-06-18T13:31Z.
- **Coverage:** 4 same-run comparisons — `att/idle`, `att/load`, `spectrum/idle`, `spectrum/load` (fping vs icmplib per WAN/load).
- **Provenance:** amended thresholds blob SHA `1eb1af334ded03c674bde835fbfa76e4b3867e91`; amends frozen blob `c39915330d4e77652ed48b981652a075b7835a71`; `AMENDMENT_ID=243-05-production-calibrated-validity-semantics`.
- **History preserved:** the original fixed verdict remains `input_error`; this amendment does not rewrite it. The frozen blob's failure stays auditable.

## Accomplishments

- Amended `scripts/phase243-thresholds.json` as a new provenance blob: added `AMENDMENT_ID`, `AMENDS_THRESHOLDS_BLOB_SHA`, `AMENDMENT_REASON`, `STALL_MAX_COUNT_PER_ARM=2`, `STALL_MAX_RATE_PCT=0.01`, `TASKS_BACKEND_DELTA_BOUND=1`; kept the old keys present for auditability.
- Wrote `243-BENCHMARK-PREREGISTRATION-AMENDMENT.md` recording that the frozen thresholds did not pass, why the validity gates were link-blind/over-tight, and that the amendment is a new blob rather than a rewrite.
- Updated `scripts/phase243-gate-eval.py`: icmplib avg stays a hard `input_error` guard; historical icmplib p99 band is now informational (`p99_blocking=false`, `p99_legacy_band_pass`); `gate_p99_delta_pct` remains the canonical same-run fping p99 regression gate; zero-stall replaced with bounded count/rate; first-sample task gate replaced with backend-delta semantics.
- Updated `tests/test_phase243_gate_eval.py` with fixed-run-like fixtures (Spectrum icmplib p99 12.1/12.6, fping p99 8.7/8.0, stalls 1–2, fping tasks <=5, icmplib tasks 7–8) plus counterexamples for relative p99, stall count/rate, and task delta.
- Added a "Phase 243-05 amendment" section to `docs/PHASE243-BENCHMARK-RUNBOOK.md` forbidding another production run until the amended evaluator is run locally over existing fixed evidence.
- Re-ran the evaluator over `evidence/production-run-fixed/` only (no `phase243-bench-run.sh`, systemd-run, fping production arms, RouterOS, qdisc, or service) → amended verdict `pass`.

## Task Commits

1. **Task 1–3: Amend thresholds/evaluator/tests + record amended verdict** — `1a757b9a` (`fix`)
2. **Record amended benchmark verdict** — `4670c6d5` (`docs`)
3. **Verify amended benchmark gate** — `e63d8eea` (`docs`)
4. **Sync roadmap verification state** — `2055d16d` (`docs`)

## Files Created/Modified

- `scripts/phase243-thresholds.json` — Amended (new provenance blob) with amendment metadata and bounded stall/task keys; old frozen keys retained for audit.
- `scripts/phase243-gate-eval.py` — Link-aware representativeness, bounded stall count/rate, backend-delta task semantics; `input_error` reserved for missing/malformed inputs.
- `tests/test_phase243_gate_eval.py` — Fixed-run-like fixtures plus relative-p99/stall/task counterexamples; existing fail-mode coverage retained.
- `docs/PHASE243-BENCHMARK-RUNBOOK.md` — Amendment section; blocks another production run until local evaluator resolves.
- `.planning/phases/243-cycle-budget-benchmark-gate/243-BENCHMARK-PREREGISTRATION-AMENDMENT.md` — Human-readable provenance/amendment narrative.
- `.planning/phases/243-cycle-budget-benchmark-gate/evidence/243-BENCHMARK-VERDICT-amended.json` — Local rerun verdict over fixed evidence, `outcome: pass`.

## Decisions Made

- The amended verdict is the basis for treating Phase 243 as passed; the frozen `input_error` verdict is intentionally not overwritten.
- `gate_p99_delta_pct` is the canonical same-run fping-vs-icmplib p99 regression gate; a link with 12ms icmplib p99 is not invalid if same-run fping is at or below that control.
- Bounded stall (count<=2 AND rate<=0.01%) and backend-delta tasks (fping max <= icmplib max + 1) tolerate observed production baseline noise while still failing real fping regressions.

## Deviations from Plan

None. Tasks 1–3 executed as planned; benchmark/evaluator semantics only, no `src/wanctl/` changes.

## Issues Encountered

- None during execution. The underlying motivation (Plan 04 `input_error` from link-blind gates) is documented above and in the amendment note.

## Verification

- `.venv/bin/pytest -o addopts='' tests/test_phase243_gate_eval.py -q` — `24 passed`.
- `python3 -c "import json; json.load(open('scripts/phase243-thresholds.json'))"` — parses; amendment keys present (`AMENDMENT_ID`, `AMENDS_THRESHOLDS_BLOB_SHA`, `STALL_MAX_COUNT_PER_ARM=2`, `STALL_MAX_RATE_PCT=0.01`, `TASKS_BACKEND_DELTA_BOUND=1`).
- `243-BENCHMARK-VERDICT-amended.json` `outcome` is `pass` over 4 comparisons; provenance records amended blob SHA `1eb1af33…` amending frozen `c3991533…`.
- `243-VERIFICATION.md` status `passed` (re-verification after the amendment).
- No `src/wanctl/` controller-path drift.

## Known Stubs

None.

## Threat Flags

None — surfaces are benchmark/evaluator semantics, threshold provenance, and a local re-evaluation over committed fixed evidence (T-243-16…T-243-19 mitigations from the plan threat model).

## User Setup Required

None.

## Next Phase Readiness

Phase 243's benchmark gate is cleared under the amended provenance-bearing basis. Phase 245's live A/B still depends on **Phase 244 (health-payload attribution metadata)**, which remains unplanned. PROV-03 should be read as a source-bound router-hop guarantee, not a named-modem-interface claim.

## Self-Check: PASSED

- Found amended thresholds blob, amendment note, amended verdict (`outcome: pass`), and updated runbook on disk.
- Found Plan 05 commits: `1a757b9a`, `4670c6d5`, `e63d8eea`, `2055d16d`.
- `tests/test_phase243_gate_eval.py` green (24 passed); no controller-source drift.

---
*Phase: 243-cycle-budget-benchmark-gate*
*Completed: 2026-06-18*
