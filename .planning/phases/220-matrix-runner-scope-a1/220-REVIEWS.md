---
phase: 220
reviewers: [codex]
reviewed_at: 2026-05-30T22:55:00
cycle: 2
plans_reviewed: [220-01-PLAN.md, 220-02-PLAN.md, 220-03-PLAN.md, 220-04-PLAN.md]
prior_cycle_reference: commit 3d69de7 (cycle 1) → replan commit 62fa143 → cycle 2 (this file)
---

# Cross-AI Plan Review — Phase 220 (matrix-runner-scope-a1) — Cycle 2

This is **cycle 2 of a convergence loop**. Cycle 1 raised 6 HIGH concerns; replan commit `62fa143` claimed to address all 6. Cycle 2 verifies resolution and looks for new HIGHs introduced by the changes.

## Codex Review

**Cycle-1 HIGH Disposition**

| Plan | H1 Plan03 deps | H2 driver_orthogonal | H3 base_sha | H4 213/214 drift guard | H5 replicates | H6 ATT egress |
|---|---|---|---|---|---|---|
| Plan 01 | FULLY RESOLVED | FULLY RESOLVED | PARTIALLY RESOLVED | PARTIALLY RESOLVED | PARTIALLY RESOLVED | PARTIALLY RESOLVED |
| Plan 02 | FULLY RESOLVED | FULLY RESOLVED | PARTIALLY RESOLVED | PARTIALLY RESOLVED | PARTIALLY RESOLVED | NOT RESOLVED |
| Plan 03 | FULLY RESOLVED | FULLY RESOLVED | PARTIALLY RESOLVED | PARTIALLY RESOLVED | PARTIALLY RESOLVED | PARTIALLY RESOLVED |
| Plan 04 | FULLY RESOLVED | FULLY RESOLVED | PARTIALLY RESOLVED | PARTIALLY RESOLVED | PARTIALLY RESOLVED | PARTIALLY RESOLVED |

**Why Not Converged**

H1 is fixed: Plan 03 is now Wave 2 and depends on `220-02`.

H2 is fixed: the distinct `(target, path)` pair rule prevents same-path window repeats or replicate reruns from satisfying driver orthogonality. The planned negative test is the right shape.

H3 is still partial: Plan 03 says to prefer env `PHASE220_BASE_SHA` over YAML (`220-03-PLAN.md:138`), while the invariant says YAML is the source-floor. That creates a bypass: set env to a later SHA and drift can pass. It also conflicts with the missing-env test expecting exit 4.

H4 is still partial: wrapper-time script drift checks are specified, but tests only exercise unstaged drift, not staged or committed-since-base drift. The same env override issue can also bypass committed drift checks.

H5 is still partial: replicate grouping is now specified, but fixture/test pins conflict. One test says `[580, 800, 590] -> 590` (`220-01-PLAN.md:397`), while fixture/scenario text says `[610, 800, 590] -> 610` (`220-01-PLAN.md:431`).

H6 is not fully fixed: Plan 02's final `paths` schema drops `egress_signature` entirely (`220-02-PLAN.md:159`), while Plan 03 only hard-fails when that field is set. ATT therefore defaults to warning/continue, which degrades MATRIX-03. Also, Plan 03 exits dry-run before the ATT egress block, but the dry-run test expects `att_egress_check`.

**NEW HIGHs Introduced**

- **HIGH (new): Plan 01 is internally non-executable as written.** It now modifies `scripts/phase220-matrix.yaml` and `scripts/phase220-precompute-pins.py`, but final verification still says `git diff --stat scripts/` must be zero and success criteria still say only `tests/` and fixtures are touched (`220-01-PLAN.md:517`). Fixture counts are also stale: files list 10 signal/manifests, acceptance expects 9. This can block Wave 0 before Plan 02/03 ever run.

CYCLE_2_VERDICT: unconverged; unresolved-HIGH count: 5

---

## Consensus Summary

Only Codex was invoked for this cycle.

### Cycle 1 HIGHs — Resolution Status

| # | Concern | Status |
|---|---------|--------|
| H1 | Plan 03 parallel-safety | FULLY RESOLVED — Plan 03 now in Wave 2, depends_on includes 220-02; Plan 01 ships scaffold |
| H2 | driver_orthogonal overly permissive | FULLY RESOLVED — tightened to require ≥2 distinct (target, path) pairs; new fixture + test |
| H3 | base_sha semantics inconsistent | PARTIALLY RESOLVED — source-floor anchor declared, but Plan 03 still allows env override of YAML, creating a bypass |
| H4 | D-14 wrapper-time 213/214 immutability | PARTIALLY RESOLVED — wrapper checks specified, but tests only exercise unstaged channel; env override re-opens the same hole |
| H5 | Replicate aggregation | PARTIALLY RESOLVED — grouping + median rule specified, but the [580,800,590]→590 vs [610,800,590]→610 pin disagreement breaks the contract |
| H6 | ATT egress validation | NOT FULLY RESOLVED — `egress_signature` is referenced in Plan 03 but missing from Plan 02's canonical schema; ATT defaults to warn/continue, degrading MATRIX-03; dry-run ordering also conflicts with the test marker |

### New HIGHs Introduced By Replan

1. **Plan 01 self-contradiction (HIGH, new)** — Plan 01 now touches `scripts/phase220-matrix.yaml` (Task 0) and `scripts/phase220-precompute-pins.py` (Task 0b), but the plan's own `<verification>` and `<success_criteria>` still mandate `git diff --stat scripts/` == 0 and "no files outside tests/ touched." Wave 0 cannot land cleanly until this is reconciled. Fixture-count acceptance criteria also drift (files list 10, acceptance expects 9).

### Divergent Views

None — single reviewer (Codex) this cycle.

### Recommended Cycle-3 Fixes (concise)

1. Pick one base_sha source authoritatively (recommend: YAML wins; env is read-only echo for traceability). Remove the env-precedence path in `220-03-PLAN.md:138` and align `test_missing_base_sha_returns_4` against the YAML-absent failure mode.
2. Extend wrapper-drift tests to also stage a commit on a throwaway branch and assert exit 4 against the `committed-since-base_sha` channel (and the staged channel). Otherwise H4's three-channel claim is contractually un-enforced.
3. Reconcile the replicate-outlier fixture: choose either `[580, 800, 590] -> 590` OR `[610, 800, 590] -> 610` and propagate across Plan 01 Task 2's test names, scenario YAMLs (`three-replicate-outlier.yaml`), and the `__r2/__r3` signal-sheet p99_ms literals. The current text has both pins, which is unimplementable.
4. Lift `paths[].egress_signature` from "optional" in Plan 03 to "required when path_name=='att'" in Plan 02's final schema. Otherwise MATRIX-03 silently degrades on a missing-field path.
5. Move the ATT egress `att_egress_check` marker into the dry-run branch (currently emitted only in the live branch after the dry-run exits), so `test_wrapper_validates_att_egress_when_path_is_att` can find it.
6. Fix Plan 01's `<verification>` + `<success_criteria>`: explicitly allow the scripts/ allowlist {`phase220-matrix.yaml`, `phase220-precompute-pins.py`} and align the fixture-count assertions (10 signal-sheets + 10 cell-manifests + 6 scenarios) with the `files_modified` list.
