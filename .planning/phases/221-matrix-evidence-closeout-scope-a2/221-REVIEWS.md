---
phase: 221
reviewers: [codex]
reviewed_at: 2026-06-01T16:30:15Z
plans_reviewed:
  - 221-01-PLAN.md
  - 221-02-PLAN.md
  - 221-03-PLAN.md
  - 221-04-PLAN.md
---

# Cross-AI Plan Review — Phase 221

## Codex Review

# Phase 221 Plan Review

## Summary

The plan set is well-structured and mostly aligned with the Phase 221 goal: read-only matrix execution, no threshold edits, no controller-path mutation, final closeout, and folded-todo disposition. The main issue is not intent, it is executability. Several plans assume a Phase 220 evidence layout and aggregator output schema that do not match the current repo. Most importantly, `scripts/phase220-matrix-aggregator.py` currently returns `per_cell` / `per_target` / `per_path` / `per_window`, not the rich `cells[]` schema Plan 03 expects, and it currently fails on the existing evidence root because it reads an invalid/null sidecar and a root-level summary `signal-sheet.json`. Until that is resolved, Phase 221 is HIGH risk.

---

## 221-01-PLAN.md

### Strengths

- Correctly lands SAFE-11 first, before evidence collection and reporting.
- Good choice to freeze Phase 220 scripts from Phase 221's point of view.
- Ledger-first design is useful for multi-session operator work.
- The plan catches its own earlier mistake and changes the rehearsal row from `3/3 complete` to `1/3 partial`.

### Concerns

- **HIGH:** BGP/path-change detection is wrong. The plan uses `mtr-post-*.txt` existence, but the wrapper always writes post-flight MTR at [scripts/phase220-target-path-matrix.sh:372](/home/kevin/projects/wanctl/scripts/phase220-target-path-matrix.sh:372). The real signal is `path_change_detected` in `phase220-cell.json`.
- **MEDIUM:** Must-haves still say the rehearsal row is pre-populated as `complete 3/3`, while the task action says `partial 1/3`. That contradiction will confuse execution.
- **MEDIUM:** Ledger row-count regex excludes hyphenated targets like `vultr-dallas`, so the 18-row acceptance check will fail.
- **LOW:** The mutation-boundary clone should preserve the useful Phase 220 source-wide checks, not just the three named test functions.

### Suggestions

- Use `phase220-cell.json["path_change_detected"]` for `mtr_post_flag` / BGP flagging.
- Normalize all plan text to `dallas__spectrum__daytime = 1/3 partial`.
- Replace cell-id regexes with something like `^\| [^|]+__[^|]+__[^|]+ \|`.
- Add an explicit acceptance check that Phase 220 scripts are frozen via committed, staged, and unstaged diff channels.

### Risk Assessment

**MEDIUM.** The plan is directionally sound, but the BGP flag and validation regex issues need fixing before execution.

---

## 221-02-PLAN.md

### Strengths

- Good multi-session model: one ledger update per operator session.
- Correctly avoids running the aggregator mid-matrix, reducing data-driven stop risk.
- Matrix-fail criteria are explicit and tied back to D-09.
- Inline operator runbook is a good choice; keeping docs untouched respects SAFE-11.

### Concerns

- **HIGH:** Evidence discovery does not match the wrapper. The wrapper writes `RUN-*` directories with `RUN-*/phase220-cell.json`; Plan 02 counts `*__r*/signal-sheet.json`. Future runs will be missed unless another process copies them into canonical cell dirs.
- **HIGH:** Failure handling depends on `failure_reason` / `attempts_exceeded` fields, but the wrapper does not emit those. Failed attempts may leave no sidecar at all.
- **HIGH:** The plan deadlocks on "valid with footnote." D-09 allows `≤2` supplemental incomplete cells, but Plan 03 only fires when `completed_replicates == 54`.
- **MEDIUM:** Evidence durability is underspecified. If evidence dirs are not committed, closeout references are not reproducible. If they are committed, final allowlist checks must allow them.
- **MEDIUM:** `bgp-changed` as a primary status conflicts with completion status. A 3/3 cell with path drift should still be `complete` with a separate flag.

### Suggestions

- Reconcile from valid `RUN-*/phase220-cell.json` records where `schema_version == 1` and `cell_id` is non-null.
- Add a manual/sidecar failed-attempt log if D-08 retry exhaustion must be tracked.
- Make status one of `pending|partial|complete|incomplete`; keep `path_change_detected` as a separate boolean.
- Decide one policy: either all 54 are mandatory, or Plan 03 must accept a D-09 valid-with-footnote state below 54.
- Define whether raw evidence is committed, normalized into Phase 221, or explicitly external.

### Risk Assessment

**HIGH.** This is the operational heart of the phase, and its evidence discovery does not match the actual wrapper output.

---

## 221-03-PLAN.md

### Strengths

- Good report shape: threshold citation, canonical/supplemental separation, per-axis rollup, decision trace, todo disposition, SAFE-11 status.
- Correctly treats historical p99 values as reportage, not verdict input.
- Good instinct to run the aggregator only once at closeout.

### Concerns

- **HIGH:** The expected JSON schema is not what the aggregator emits. Actual output returns keys like `per_cell`, `per_target`, `per_path`, and `matrix_verdict` at [scripts/phase220-matrix-aggregator.py:311](/home/kevin/projects/wanctl/scripts/phase220-matrix-aggregator.py:311), not `cells[]`, `thresholds`, `phase220_yaml_sha`, timestamps, p50/p95, MTR refs, or `decision_tree_trace`.
- **HIGH:** The aggregator currently fails on the live evidence root with `KeyError: 'p99_ms'`, because it scans every `**/phase220-cell.json` at [scripts/phase220-matrix-aggregator.py:499](/home/kevin/projects/wanctl/scripts/phase220-matrix-aggregator.py:499), including an invalid/null sidecar at [phase220-cell.json:2](/home/kevin/projects/wanctl/.planning/phases/220-matrix-runner-scope-a1/evidence/RUN-20260601T150527Z/phase220-cell.json:2).
- **HIGH:** BGP overlay can flip the final verdict, but Plan 04 requires `CLOSEOUT.md` verdict to equal JSON `matrix_verdict`. Those contracts conflict.
- **MEDIUM:** Synthesizing `decision_tree_trace` in Plan 03 reimplements verdict logic outside the aggregator. That weakens the "pure read" guarantee.
- **LOW:** The MATCHED/FAILED grep acceptance uses an escaped `\|` inside an ERE alternation and may not match as intended.

### Suggestions

- Add a pre-Phase-221 blocker: run the aggregator against current evidence and either repair it or normalize the evidence root before matrix execution.
- Change Plan 03 to read actual aggregator output plus raw sidecars/signal sheets, or update Phase 220 aggregator/schema under an explicit exception.
- Do not allow a markdown-only verdict flip. Either the final verdict equals aggregator output, or the JSON is amended with an explicit `final_verdict_after_bgp_overlay`.
- Replace decision-tree synthesis with a descriptive trace derived from existing aggregator fields, unless the aggregator is extended and tested.

### Risk Assessment

**HIGH.** As written, Plan 03 cannot produce the promised artifacts from the current aggregator output.

---

## 221-04-PLAN.md

### Strengths

- Todo disposition is clear and traceable.
- Closing on any verdict is the right operational choice given the close-with-prejudice rule.
- Two-commit flow for todo move then closeout SHA amendment is auditable.
- Final SAFE-11 plus hot-path test slice is appropriate.

### Concerns

- **MEDIUM:** `git mv` will not reliably create `.planning/todos/closed/`; run `mkdir -p` first.
- **HIGH:** Preflight requires `CLOSEOUT.md` verdict to match JSON `matrix_verdict`, but Plan 03 allows BGP overlay to change the final verdict.
- **MEDIUM:** `yaml.safe_dump` may reformat the whole frontmatter, not just append fields. That is probably acceptable, but it contradicts "historical content preserved" expectations.
- **MEDIUM:** One final verification command uses the YAML blob SHA as a commit range base; use the YAML `base_sha` field or the same resolver as the test.
- **MEDIUM:** Final diff allowlist must match the evidence durability decision from Plan 02.

### Suggestions

- Add `mkdir -p .planning/todos/closed` before `git mv`.
- Resolve the JSON/markdown verdict contract before Plan 04.
- Use targeted frontmatter insertion if minimizing churn matters.
- Make final diff checks call the same base-SHA resolver used by `tests/test_phase221_mutation_boundary.py`.

### Risk Assessment

**MEDIUM-HIGH.** The todo mechanics are good, but they depend on Plan 03 producing a consistent closeout verdict.

---

## Overall Risk Assessment

**HIGH until corrected.** The phase is read-only and low operational risk to the controller, but high execution risk because the plans do not currently line up with the actual Phase 220 wrapper/evidence/aggregator surfaces. Fix the evidence indexing, BGP flag semantics, incomplete-cell readiness rule, and aggregator schema/runtime failure first. After that, the plan set drops to **MEDIUM/LOW** because the remaining work is documentation, ledger maintenance, and todo disposition.

---

## Consensus Summary

Only one reviewer (Codex) was invoked for this phase, so consensus is single-reviewer. The findings should still be treated as authoritative for planning iteration because they are grounded in direct file inspection of the actual Phase 220 wrapper, evidence sidecars, and aggregator code.

### Agreed Strengths

- SAFE-11 mutation-boundary landed early before evidence collection (Plan 01).
- Ledger-first multi-session operator model (Plans 01–02).
- Aggregator runs once at closeout, not per cell (Plan 02 → Plan 03).
- Two-commit closeout audit trail with hot-path test slice (Plan 04).
- Read-only posture and close-with-prejudice operational stance hold across all four plans.

### Agreed Concerns (single-reviewer, but high confidence)

- **HIGH — Evidence layout mismatch:** Plan 02's discovery logic (`*__r*/signal-sheet.json`) does not match the wrapper's actual output (`RUN-*/phase220-cell.json`). This blocks accurate ledger reconciliation.
- **HIGH — BGP/path-change detection logic:** Plan 01 uses `mtr-post-*.txt` existence; the real signal is `phase220-cell.json["path_change_detected"]`.
- **HIGH — Aggregator schema drift:** Plan 03 expects a `cells[]` rich schema; the actual aggregator emits `per_cell` / `per_target` / `per_path` / `matrix_verdict`. Plan 03 cannot produce its promised artifacts as written.
- **HIGH — Aggregator runtime failure:** Aggregator KeyErrors on the live evidence root due to an invalid/null sidecar at `RUN-20260601T150527Z/phase220-cell.json`. Must be repaired or evidence root normalized before Phase 221 runs.
- **HIGH — Verdict contract conflict:** Plan 03 allows BGP overlay to flip the markdown verdict; Plan 04 preflight requires CLOSEOUT.md verdict == JSON `matrix_verdict`. Contracts are mutually inconsistent.
- **HIGH — Incomplete-cell readiness rule:** Plan 02 deadlocks because D-09 allows ≤2 supplemental incomplete cells while Plan 03 only triggers at `completed_replicates == 54`.
- **MEDIUM — Ledger regex excludes hyphenated targets** (`vultr-dallas`); the 18-row acceptance check will fail.
- **MEDIUM — Rehearsal row contradiction:** Plan 01 must-haves say `complete 3/3`, task action says `partial 1/3`.
- **MEDIUM — Evidence durability underspecified:** Need an explicit decision on whether raw evidence is committed, normalized into Phase 221, or external — and the final-diff allowlist must match.
- **MEDIUM — Decision-tree trace synthesized outside aggregator** weakens the "pure read" guarantee.

### Divergent Views

None — only one reviewer.

### Recommended Next Step

Open a planning iteration (`/gsd:plan-phase 221 --reviews`) to:

1. Decide aggregator strategy: either (a) extend `scripts/phase220-matrix-aggregator.py` under an explicit exception to produce the Plan 03 schema, or (b) rewrite Plan 03 to consume the existing `per_cell` / `per_target` / `per_path` shape plus raw sidecars.
2. Repair or skip the invalid `RUN-20260601T150527Z/phase220-cell.json` so the aggregator stops KeyError'ing.
3. Switch BGP flag derivation in Plan 01 to `path_change_detected` from `phase220-cell.json`.
4. Update Plan 02 evidence discovery to `RUN-*/phase220-cell.json` with `schema_version == 1` filter.
5. Reconcile the verdict contract: pick one of (a) JSON is final and markdown mirrors it, or (b) markdown is final and JSON is amended with `final_verdict_after_bgp_overlay`. Apply consistently across Plans 03 and 04.
6. Resolve the D-09 vs `==54` readiness deadlock — decide whether Plan 03 accepts a valid-with-footnote state.
7. Fix the ledger row regex and the `complete 3/3` vs `partial 1/3` contradiction in Plan 01.
8. Specify evidence durability and align the final-diff allowlist in Plan 04.
