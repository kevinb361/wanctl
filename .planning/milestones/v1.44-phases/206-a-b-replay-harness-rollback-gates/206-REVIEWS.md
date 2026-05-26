---
phase: 206
reviewers: [codex]
reviewed_at: 2026-05-14
plans_reviewed: [206-01-PLAN.md, 206-02-PLAN.md, 206-03-PLAN.md, 206-04-PLAN.md]
codex_model: gpt-5.5
codex_reasoning: xhigh
---

# Cross-AI Plan Review — Phase 206

> Single reviewer this round (codex). No consensus axis — codex's findings are signal, not tiebreaker. Treat as a second pair of eyes from a different model lineage, not as agreement.

## Codex Review

**Summary**

206-01 has a solid scaffold, but its metric semantics are too weak for the phase goal. The harness uses the existing replay lineage, commits a deterministic fixture, and freezes a schema, but it does not really produce a meaningful A/B RRUL comparison: pre/post latency and jitter come from the same series, throughput is controller rate mean rather than flent throughput, and the per-sample CAKE fields are mostly ignored because `_replay()` takes one static snapshot.

206-02 is the strongest plan after the W3 patch. The four-state input/baseline matrix is the right direction: supplied input plus missing baseline must ABORT. The remaining issue is that "optional skip" can still become a fail-open in post-soak use unless the gate has an explicit full-enforcement mode.

206-03 is useful and operator-friendly. It correctly documents the 2026-04-29 substitution and the rollback trigger definitions. The main weakness is wave ordering: it hardcodes constants before Plan 02 lands them, with drift caught only at Plan 04.

206-04 has the right intent, but the SAFE-09 check is not quite strong enough. `git diff 6508d68..HEAD` misses uncommitted and untracked `src/wanctl/` changes. For a production network controller, that is a real closeout hole.

As a set: good structure, conservative scope, and strong docs/testing posture, but I would not approve it as-is as the Phase 209 foundation until the replay semantics, actual v1.43 baseline, and SAFE-09 working-tree checks are tightened.

**Strengths**

- Scope is correctly bounded to scripts/tests/docs; no planned `src/wanctl/` edits.
- The 2026-04-22 missing-artifact problem is surfaced instead of papered over.
- Fixture reproducibility plus SHA256 pinning is good audit hygiene.
- Plan 02's mismatch fail-closed behavior is the right default.
- RRUL `>5%` strict-boundary test is good.
- Plan 04 checks both count and exact SAFE-09 allowlist, not just count.
- Operator docs include measurement source, formula, examples, and SAFE-09 exclusions.

**Concerns**

- **HIGH:** 206-01 does not produce a true A/B RRUL metric comparison. Both sides use the same `load_rtt_ms` distribution, so p99 latency and jitter deltas are structurally zero. `throughput_mbps = mean(rates)` is controller output, not flent throughput.
- **HIGH:** The generated per-row `cake_avg_delay_us` / `cake_base_delay_us` trace is ignored by the replay loop. Current `_replay()` in `tests/test_phase_193_replay.py:164` accepts one snapshot, and Plan 01 passes `samples[0]`.
- **HIGH:** Plan 04 SAFE-09 uses `git diff 6508d68..HEAD`, which excludes uncommitted worktree changes and untracked files. This can falsely pass.
- **HIGH:** `phase206_baseline_v143.json` uses placeholder baseline values. That weakens success criterion #4: "operator dry-run on the v1.43 baseline exits zero" is not the same as "placeholder fixture exits zero."
- **MEDIUM:** The reuse claim is overstated. Plan 01 grep-checks imports from Phase 193, but then reimplements controller factories and snapshot construction. Existing `_fresh_controller("spectrum")` is already 920M, not 940M.
- **MEDIUM:** Gate optional skips can still fail open. If baseline has restart/transition fields but the operator omits inputs, Plan 02 INFO-skips. That is fine for partial dry-runs, not for post-soak enforcement.
- **MEDIUM:** Restart-rate SSH behavior is internally inconsistent. The plan says production mode SSHes, but the main pseudocode only treats explicit start/end counters as present.
- **MEDIUM:** Schema-v1 stability is only key-set testing. Plan 02 extends the same `schema_version: 1` object with gate baseline fields, which blurs "A/B summary schema" vs "gate baseline schema."
- **MEDIUM:** `--flent-gz` is specified but not actually implemented in the Plan 01 action/tests.
- **LOW:** `statistics.quantiles(..., method="exclusive")` can extrapolate p99 above max with small sample counts. The real flent sample has 350 points, but the fixture allows 24.
- **LOW:** Bash path validation is described in 206-02 but not actually implemented/tested in the provided wrapper body.
- **LOW:** Importing `tests.*` from `scripts/phase206-ab-replay.py` is brittle if this script is ever run outside the repo checkout or from `/opt/wanctl`.

**Suggestions**

- In 206-01, either rename the metrics honestly or make them real:
  - If derived from controller replay, call it `controller_mean_rate_mbps`, not `throughput_mbps`.
  - If claiming RRUL throughput/p99/jitter, parse those from flent artifacts and test `--flent-gz`.
- Add a per-sample replay helper for Phase 206:
  - Keep the Phase 193 `_replay()` import as a lineage smoke test.
  - Use a new `_replay_samples(samples, layout)` for the actual harness so every row's CAKE snapshot is consumed.
- Separate schemas:
  - `ab_summary_schema_version: 1`
  - `gate_baseline_schema_version: 1`
  - Or keep `schema_version: 1` only for harness output and put baseline extensions under `gate_baseline`.
- Add a golden schema fixture or JSON Schema test that checks required keys, types, optional extension policy, and compatibility.
- In 206-02, add `--mode predeploy|post-soak` or `--require-all`.
  - `predeploy`: allow RRUL-only dry-run.
  - `post-soak`: require candidate, soak NDJSON, restart counters, and both baseline fields.
- Derive `transition_rate_per_hour_baseline` from the real `20260509T183037Z/soak-capture.ndjson` during Phase 206, not as a placeholder.
- For restart baseline, either commit real counter evidence or explicitly store `restart_rate_per_hour_baseline: 0.0` with documented source limitation. Do not call placeholder data a v1.43 baseline.
- Fix restart input behavior: either remove SSH from the gate and require explicit counter start/end, or implement and test `--restart-counter-start + --ssh-target` as "start literal, end live."
- Compute transition hours as `(max_t_monotonic - min_t_monotonic) / 3600`, not just `max / 3600`.
- Strengthen SAFE-09 in 206-04:
  - `git diff 6508d68 --name-only -- src/wanctl/ | sort -u`
  - `git diff --cached 6508d68 --name-only -- src/wanctl/ | sort -u`
  - `git ls-files --others --exclude-standard src/wanctl/`
  - `git status --short -- src/wanctl/`
- Make Plan 03 depend on Plan 02, or have Plan 02 emit a machine-readable thresholds file that the doc references.
- Add threat-model entries for stale/tampered baseline JSON, test-module imports from scripts, placeholder baseline risk, and partial-run skip risk.

**Risk Assessment**

Overall risk: **MEDIUM-HIGH as written**.

SAFE-09 risk is fixable and becomes LOW with working-tree/untracked checks. The gate semantics are mostly sound after W3, but need a full-enforcement mode. The biggest unresolved risk is semantic: Plan 01 currently proves that a deterministic script emits a stable JSON shape, not that the A/B replay meaningfully captures the 920 besteffort wash migration or supports Phase 209 canary comparison. That needs tightening before this should gate production migration.

---

## Consensus Summary

Only one external reviewer this round, so there is no "consensus" axis. Codex's findings stand or fall on their own merit.

### Agreed Strengths
(Codex-only — no second voice to confirm)

- Scope bounded to scripts/tests/docs with zero `src/wanctl/` edits (matches plan-checker's SAFE-09 PASS).
- Fixture provenance documented + SHA256 pinned.
- Plan 02 fail-closed mismatch matrix is the right default (matches plan-checker's W3 patch verification).
- Plan 04 asserts the exact 5-file allowlist, not just the count.

### Agreed Concerns
(Codex-only — but four findings are HIGH and operationally substantive)

| # | Severity | Concern | Plan-checker found this? |
|---|----------|---------|--------------------------|
| C1 | HIGH | A/B comparison is structurally null — both sides drive the controller from the same `load_rtt_ms` series, so p99/jitter deltas can only come from controller-internal rate divergence, not from RRUL semantics. `throughput_mbps = mean(rates)` is controller output, not flent throughput. | No (orthogonal axis: semantic meaningfulness, not mechanical correctness). |
| C2 | HIGH | The per-row `cake_*_delay_us` trace synthesized in the fixture is dead data — `_replay()` consumes one snapshot, the harness passes `samples[0]`, so the rest of the trace never reaches the controller. | No (related to W4 but more specific — checker said the synthesis is documented; codex says it doesn't matter because it's not used). |
| C3 | HIGH | SAFE-09 boundary check uses `git diff 6508d68..HEAD` only — misses uncommitted worktree edits and untracked files under `src/wanctl/`. Phase 209 closeout could falsely pass. | No — checker counted the diff but didn't audit which git surfaces it covers. |
| C4 | HIGH | `phase206_baseline_v143.json` is committed with placeholder numerics. Success criterion #4 says "operator dry-run on the v1.43 baseline exits zero" — placeholder ≠ baseline. | Plan-checker flagged adjacent concern (W2 schema-extension); codex sharpens it to "placeholder defeats the success criterion entirely." |

Medium concerns add weight but are clean follow-ups: schema-entanglement (Plan 02 extending schema-v1), gate full-enforcement mode missing, restart-SSH path inconsistent, `--flent-gz` advertised but unimplemented, reuse claim overstated.

### Divergent Views
N/A — single reviewer.

### Notable orthogonal lens
Codex's HIGH findings are mostly **semantic-validity** concerns (does the A/B actually measure A vs B, does the SAFE-09 check actually catch what it claims, is the v1.43 baseline actually the v1.43 baseline). Plan-checker focused on **structural/mechanical** concerns (file paths, decision coverage, frontmatter validity, threshold drift). The two lenses are complementary; both should be applied before execution.

---

*Generated by /gsd-review --codex on 2026-05-14*
*To incorporate: `/gsd-plan-phase 206 --reviews` (re-spawns planner with REVIEWS.md context)*
