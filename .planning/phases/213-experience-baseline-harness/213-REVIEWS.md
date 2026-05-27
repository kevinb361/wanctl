---
phase: 213
reviewers: [codex]
reviewed_at: 2026-05-27
plans_reviewed:
  - 213-01-PLAN.md
  - 213-02-PLAN.md
  - 213-03-PLAN.md
  - 213-04-PLAN.md
  - 213-05-PLAN.md
codex_model: default (codex-cli 0.125.0)
verdict: REVISE
risk_as_written: HIGH
risk_after_fixes: MEDIUM
---

# Cross-AI Plan Review — Phase 213

## Codex Review

**Summary**

The plan set is well-scoped and mostly respects the evidence-only boundary, but I would not execute it as written. The biggest risks are not controller mutation; they are evidence validity and safety hygiene: the WAN/source-bind mapping is inconsistent, raw steering state handling contradicts the later redaction gate, some "offline" tests would SSH into production, and the classifier is under-tested relative to the phase goal. Fix those before Plan 05.

**Strengths**

- Good wave structure: fixtures/contracts first, leaf scripts in parallel, then orchestrator/classifier/runbook, then live execution.
- Strong intent around D-10 mutation boundary: no `src/wanctl/` changes, no config writes, no deploys, no RouterOS writes.
- D-08/D-14 are called out repeatedly, especially around steering v1.39 threshold-name non-interpretation.
- Reuses existing harnesses instead of greenfielding: `phase191-flent-capture.sh`, `soak-capture.sh`, Phase 198 patterns, Phase 212 evidence layout.
- BASE-01/02/03 are all represented: runbook, co-sampled evidence, signal-sheet classification, final operator report.

**Concerns**

- **HIGH — WAN/source-bind mapping is inconsistent.** Plan 04/05 use one `--local-bind` for both Spectrum and ATT, and Plan 05's real command uses `10.10.110.233` for `--wans spectrum,att`. But `scripts/phase198-rerun-flent-3run.sh:116` says Spectrum was locked to `10.10.110.226` and `10.10.110.233` exits AT&T. This can invalidate every per-WAN label.

- **HIGH — raw steering state handling is contradictory.** 213-03 Task 2 emits `<prefix>-state.raw.json` under evidence, but 213-05 Task 1/2 require `find ... -name "*.raw.json"` to be empty. Gitignore does not make `find` empty, and raw secret-bearing files should not persist under evidence at all.

- **HIGH — "offline" automated tests would touch production.** 213-01/213-04's manifest test invokes `phase213-baseline-capture.sh --dry-run`, but the planned dry-run performs SSH/sudo checks against `cake-shaper`. That breaks the stated offline test model and makes routine pytest depend on production reachability.

- **HIGH — background pollers can leak on failure.** 213-04 Task 1 starts two pollers, then runs flent/browse/SSH work under `set -e`. If any middle step fails before the kill/wait block, pollers can keep running. Add per-test and global `EXIT` cleanup traps.

- **HIGH — mutation-boundary test design has holes.** 213-01 says to skip missing scripts inside the loop; if implemented with `pytest.skip()` in-loop, the whole test skips on the first missing script and does not scan scripts that already exist. Also Plan 04 wants script heredocs/docstrings to mention "steering toggle", which matches the forbidden regex.

- **MEDIUM — classifier is under-specified and under-tested.** 213-04 Task 2 implements six buckets, flent parsing, browse CSV parsing, steering deltas, and recommendation logic, but Plan 01 tests only bucket presence, bucket 1, D-14 grep, and recommendation existence. Buckets 2/3/5/6 could be broken while tests pass.

- **MEDIUM — upload ceiling inference is not portable.** The plan says bucket 1 may infer ceiling from `setpoint + 6`. Health exposes `setpoint_mbps` but not upload ceiling in `src/wanctl/health_check.py:343`. Hard-coding Spectrum math cuts against the link-agnostic architecture.

- **MEDIUM — flent artifact paths do not match the planned classifier shape.** `scripts/phase191-flent-capture.sh:126` writes under `OUTPUT_ROOT/LABEL/WAN/TIMESTAMP`, not directly under the Phase 213 per-test directory. The classifier needs recursive discovery or the orchestrator must copy/symlink stable summaries.

- **MEDIUM — `.planning/` is ignored.** `.gitignore:11` ignores `.planning/`. That may be intentional, but Plan 05 talks about committed evidence/report artifacts there. The plan needs an explicit `git add -f` and redaction gate story.

- **MEDIUM — signal-sheet location is inconsistent.** Some text expects `evidence/signal-sheet-<ts>.md`; other text links `evidence/RUN-<ts>/signal-sheet.*`. Pick one canonical location, preferably inside the run dir with optional top-level index/copy.

- **MEDIUM — alert-window SQL is only source-grep verified.** The synthetic `alerts-test.db` from Plan 01 is not actually used by Plan 03. Add a local fixture mode or a small helper so the SQL/window merge behavior is tested without SSH.

- **LOW — Plan 05 wording says `--wans att,spectrum` is "loaded concurrently."** That order is still serialized. If the order is forbidden for comparability, say that; don't call it concurrent.

**Suggestions**

- Replace `--local-bind` with per-WAN binding, e.g. `--bind-map spectrum=10.10.110.226,att=10.10.110.233`, and enforce egress per WAN before each WAN suite.
- Split dry-run modes: one offline manifest/schema mode for pytest, one live `--check-prereqs` mode for Plan 05.
- Change steering snapshot to write raw state to `mktemp`, redact into evidence, then delete raw via `trap`.
- Factor the jq projection into a separate `.jq` file or add a `--project-health-fixture` mode; don't make tests scrape shell quoting.
- Add classifier fixtures for all six buckets, plus flent summary/browse CSV/steering delta parsing.
- Add stable flent artifact normalization in the orchestrator: copy or symlink summary/raw outputs into each `<wan>/<test>/` directory.
- Put signal-sheet files inside `RUN-<ts>/`; optionally copy a top-level `latest` or timestamped index.
- Add `.planning/STATE.md` to 213-05 modified files if the phase closeout expects a state update.

**Risk Assessment**

**HIGH as written.** The controller mutation risk is low because D-10 is taken seriously, but the evidence-validity risk is high. The source-bind issue alone can make the baseline misleading, and the raw-state/test-production contradictions can break execution or leak sensitive local artifacts. After fixing those structural issues, the plan should drop to **MEDIUM** risk, mostly because Plan 05 intentionally generates production WAN load.

---

## Consensus Summary

Single-reviewer mode (codex only). No cross-reviewer consensus available.

### Codex-Flagged Strengths
- Wave structure (fixtures/contracts → leaf scripts → orchestrator/classifier → live run)
- D-10 mutation boundary discipline
- D-08/D-14 invariant enforcement intent
- Existing-harness reuse (phase191, soak-capture, phase198, Phase 212 evidence layout)
- Full BASE-01/02/03 coverage

### Codex-Flagged HIGH Concerns (must address before execution)

1. **WAN/source-bind mismatch with Phase 198** — same `--local-bind` used for both Spectrum and ATT; Phase 198 locked Spectrum to `10.10.110.226` and ATT to `10.10.110.233`. Compromises per-WAN label validity.
2. **Raw steering state contradiction** — Plan 03 emits `*-state.raw.json` into evidence, Plan 05 verify gate requires no `*.raw.json` exists. Either drop raw emission entirely (mktemp + redact + trap-delete) or remove the verify gate.
3. **"Offline" tests SSH to production** — Plan 04 `--dry-run` performs SSH/sudo prereq checks against `cake-shaper`; Plan 01's manifest-schema test invokes that same `--dry-run`. Pytest becomes production-dependent. Split into offline `--check-manifest` and live `--check-prereqs`.
4. **Background poller leak on `set -e`** — Plan 04 starts pollers then runs flent/browse/SSH; if middle step fails, pollers stay alive. Add `trap '<kill pollers>' EXIT` per-test and globally.
5. **Mutation-boundary test loop holes** — in-loop `pytest.skip()` short-circuits at first missing script; Plan 04 wants "steering toggle" in heredocs which matches the forbidden regex (false-positive trip). Use parametrized tests + word-boundary regex.

### Codex-Flagged MEDIUM Concerns
- Classifier under-tested (only buckets 1 + D-14 grep + presence; buckets 2/3/5/6 could regress silently)
- Bucket 1 `setpoint + 6` inference is Spectrum-specific (violates link-agnostic architecture)
- Flent artifact path mismatch (`OUTPUT_ROOT/LABEL/WAN/TIMESTAMP` vs expected per-test dir)
- `.gitignore` ignores `.planning/` — Plan 05 needs explicit `git add -f` story
- Signal-sheet location inconsistent across the plan set
- Alert-window SQL only source-grep verified, not behaviorally tested
- Plan 05 calls serialized `--wans att,spectrum` "concurrent" (terminology only)

### Divergent Views
N/A — single reviewer.

### Plan-Checker vs Codex Delta
The internal `gsd-plan-checker` returned PASS across 12 dimensions (goal coverage, requirement coverage, decision compliance, deep-work fields, dependencies, threat model, validation completeness, Nyquist, closeout, mutation guardrail). Codex agrees on those dimensions but caught **implementation-realism issues** the goal-backward checker missed:

- Cross-phase consistency (source-bind mapping inherited from Phase 198 wasn't re-verified in the plan)
- Internal cross-plan contradictions (Plan 03 raw emission vs Plan 05 raw absence gate)
- Test isolation (offline label vs SSH prereqs)
- Shell error-handling realism (`set -e` + background pids + middle-step failure)
- Test design realism (in-loop skip + heredoc string collision with grep regex)

This is the canonical cross-AI review payoff: semantic compliance vs implementation realism.

---

## Next Step

To incorporate this feedback into a revised plan set:

```
/gsd-plan-phase 213 --reviews
```

The planner will read this REVIEWS.md and produce targeted edits to the 5 plans (most likely concentrated in 213-03, 213-04, 213-05 plus the mutation-boundary test in 213-01).
