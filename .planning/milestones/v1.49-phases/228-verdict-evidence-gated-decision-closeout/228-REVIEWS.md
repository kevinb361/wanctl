---
phase: 228
reviewers: [codex]
reviewed_at: 2026-06-04T18:06:41Z
plans_reviewed: [228-01-PLAN.md, 228-02-PLAN.md, 228-03-PLAN.md, 228-04-PLAN.md]
convergence_cycles: 2
cycle_2_remaining_high: 0
---

# Cross-AI Plan Review — Phase 228

> Convergence loop. Reviewer: Codex (`codex-cli 0.135.0`). Claude skipped (self — review ran inside
> Claude Code). Load-bearing factual claims are independently verified against the repo before each
> cycle's findings are written; verification notes are inline under **[Verified]**.

---

# Cycle 2 (current) — 2026-06-04T18:06:41Z

Reviewed the REVISED plans (commit 69198a9, replan addressing the cycle-1 Codex HIGH+MEDIUM
findings). Goal: verify the 2 HIGH families (228-01 columnar tc parsing + 228-02 coupled
`gate_tin_separation` dependency) and the MEDIUMs are actually resolved, and surface new concerns.

**Result: REMAINING_UNRESOLVED_HIGH = 0.** All four cycle-1 HIGHs are RESOLVED. Remaining items are
MEDIUM/LOW precision gaps (tin-separation occupancy-metric completeness, proof automation, closeout
wording), none gating.

## Independent verification (Claude, against the live repo, this cycle)

- **[Verified]** `scripts/phase226-baseline-summary.py:24` still has
  `TIN_RE = re.compile(r"^\s*Tin\s+(?P<name>\S+)")` — columnar parsing not yet implemented (correct:
  plans are unexecuted; 228-01 is the fix).
- **[Verified]** candidate `baseline-summary.json` still has `interfaces: {}` and no `tin_separation`
  key (unexecuted state).
- **[Verified]** candidate tc artifact IS columnar (`Bulk  Best Effort  Video  Voice` header
  confirmed in `candidate-20260604T163152Z/run-01/tc-qdisc-spec-modem.during.txt`).
- **[Verified]** `.planning/todos/` has three terminal dirs (`closed/`, `completed/`, `done/`) — the
  228-04 ambiguity is real.
- **[Verified]** `scripts/phase227-rollback.sh` has a `--out FILE` flag (line 22/135) and refuses
  without `--confirm` — the 228-03 `--out` fix is grounded.
- **[Verified]** `scripts/phase227-rollback.sh` uses `status == "healthy"` (lines 53/73/74); no
  "GREEN" token in the script — the 228-03 health-vocabulary fix matches reality.
- **[Verified]** `scripts/phase228-gate-eval.py` / `scripts/phase228-rollback-proof.py` do not yet
  exist (unexecuted).

## Codex Review (cycle 2)

# Phase 228 Plan Review — Convergence Cycle 2

Verdict: the revised plans materially resolve the cycle-1 HIGH findings. I do not see any remaining
HIGH concern. The remaining issues are mostly medium/low precision gaps around tin-separation metric
completeness, proof automation, and avoiding overstatement in closeout language.

### Plan 228-01

**Strengths:** Real committed candidate fixture is the regression guard. BE-by-name explicitly
required and tested with `be_tin.id == 1`. Besteffort single-tin preserved as valid "no separation."
`{}` → 4 tins explicitly framed as a parser correction with `parser_correction` provenance.

**Concerns:**
- **MEDIUM:** `TIN_SEPARATION.OCCUPANCY_METRICS` lists both `non_be_packets` and `non_be_sojourn`,
  but Task 2 concretely emits `non_be_packets_delta` / `non_be_present` / delay maps /
  `useful_separation` — no explicit `non_be_sojourn` field or test. Part of the pre-registered
  occupancy rule is left under-specified.
- **MEDIUM:** Pre-existing-field preservation not fully locked: Task 3 verifies baseline RRUL p99
  only; Task 4(f) checks top-level key *presence*, not value equality for all protected fields on
  both summaries.
- **LOW:** sha256 staleness fix has a mechanism but no automated assertion that the chosen manifest
  actually contains the current re-emitted hashes.

### Plan 228-02

**Strengths:** `depends_on: [01]` correct (prevents evaluating empty candidate tin data).
Zero-baseline math explicit and test-covered. UL p99 absence is `not_observed`, not pass.
Primary tin-separation semantics defined (`spec-router` primary, `spec-modem` corroborating).
Accept path tested (protects against reverse-fit reject).

**Concerns:**
- **MEDIUM:** tin-separation gate inherits the 228-01 gap — checks `non_be_present` /
  `useful_separation`, doesn't explicitly prove every `OCCUPANCY_METRICS` entry was evaluated.
- **MEDIUM:** `safe13_lift.rationale` bakes in expected "no useful per-tin separation" narrative;
  it should derive from actual per-interface gate results. If primary fails but corroborating shows
  a useful gap, the verdict should say so precisely.
- **LOW:** reproducibility check verifies key fields but doesn't require a canonical re-run compare
  (ignoring only `evaluated_at`).
- **LOW:** one context sentence says tin separation fails on "the EF-harm picture" — keep EF harm
  out of the tin-separation gate itself; use it only in rationale/closeout.

### Plan 228-03

**Strengths:** `autonomous: false` correct for live Spectrum mutation. Rollback run proof routed to
Phase 228 evidence via explicit `--out`. Restoration reframed "value-restored + annotated," not
byte-identical. Repo proof now full redacted diff + unrelated-drift test. Proof generator file-fed
testable before the live mutation.

**Concerns:**
- **MEDIUM:** Task 3 deploys raw Snapshot A bytes then rewrites the repo annotation afterward →
  repo/deployed comment-hash drift post-deploy. Proof should record that final repo differs from
  deployed by comment only, OR rewrite-before-deploy.
- **MEDIUM:** Health "no crashloop" under-specified — a single `status == "healthy"` payload doesn't
  prove restarts aren't climbing without a before/after restart count or bounded observation window.
- **LOW:** `--snapshot-ref <snapshot-a-redacted.yaml>` is a placeholder; pin the actual committed
  Phase 226 Snapshot A redacted Spectrum YAML path.
- **LOW:** stale "health GREEN" wording remains in objective/artifact prose (the task/test path uses
  `status == "healthy"`).
- **LOW:** qdisc race only partially constrained — plan allows reuse OR retry; require bounded retry
  unless the reused proof is proven settle-safe.

### Plan 228-04

**Strengths:** Dedicated SAFE-13 no-lift decision record. Closeout cites verdict evidence rather
than duplicating the full numeric set. Todo ambiguity handled by inspecting the repo + recording a
moved trail. SAFE-13 proof scope explicitly separated from Spectrum restoration proof. Milestone
archival correctly deferred.

**Concerns:**
- **MEDIUM:** closeout/no-lift wording shouldn't globally claim "no useful per-tin separation" unless
  the verdict proves it across the relevant interfaces; prefer "no useful primary-interface
  separation" if only `spec-router` fails.
- **LOW:** Task 3 verify greps all of `.planning/todos/` — can false-pass on unrelated files; verify
  the exact moved file and its moved-from/moved-to/reopen-gate content.
- **LOW:** Task 4 verify should assert `passed is True`, `controller_path_diff_count == 0`,
  `att_config_diff_count == 0` (the SAFE script exits nonzero on failure, but a JSON assertion makes
  the evidence contract explicit).
- **LOW:** `files_modified` lists the pending todo path even though the task moves it to a terminal
  dir; reflect the final chosen destination.

## Cycle-1 Resolution Audit (Codex)

| Prior Concern | Status | Justification |
|---|---|---|
| 228-01 HIGH-A: columnar diffserv4 parses to `{}` | RESOLVED | 228-01 Task 1 adds columnar parsing; Task 4 real-fixture test requires committed candidate router/modem artifacts parse to four named tins. |
| 228-01 HIGH-B: assumed tin ids `0..3`, BE not id 0 | RESOLVED | truths/tasks require `{id, cake_name}` and BE by `cake_name == "Best Effort"`; Task 4(d) asserts diffserv4 BE `id == 1`. |
| 228-01 MEDIUM: re-emitting summaries stales hashes | PARTIALLY RESOLVED | Task 3 requires refreshing `artifact-sha256.txt` or writing `phase228-reemit-sha256.txt`, and 228-02 pins current hashes; missing automated hash-manifest assertion. |
| 228-01 LOW: additive-only framing too narrow | RESOLVED | Task 3 explicitly frames `{}` → four tins as an expected parser correction with `parser_correction` provenance. |
| 228-02 HIGH-C: depends on trustworthy tin separation | RESOLVED | `depends_on: [01]`, reads 228-01 `tin_separation`, fails closed on missing primary data. |
| 228-02 MEDIUM: zero-baseline percent math | RESOLVED | Explicit zero-baseline rule + Task 3(c2) tests 0/0 pass and 0/positive fail without division. |
| 228-02 MEDIUM: missing UL p99 field | RESOLVED | `gate_ul_stability` labels absent UL p99 `not_observed`; Task 3(d2) tests it. |
| 228-02 MEDIUM: primary interface undefined | RESOLVED | Plan defines `spec-router` primary / `spec-modem` corroborating; Task 3(e) tests primary-only pass semantics. |
| 228-03 HIGH-D: rollback omitted `--out` | RESOLVED | Task 3 uses explicit Phase 228 `--out .../phase227-rollback-run-proof.json`; verify asserts the file exists there. |
| 228-03 MEDIUM: byte-restore vs annotation contradiction | RESOLVED | Consistently reframed value-restored + annotated, not byte-identical including comments. |
| 228-03 MEDIUM: repo proof selected lines only | RESOLVED | Task 1 requires full redacted diff; Task 2(b2) tests unrelated drift fails. |
| 228-03 MEDIUM: health "GREEN" vocabulary | PARTIALLY RESOLVED | Mechanism/test uses `status == "healthy"`, but stale "GREEN" wording remains in objective/artifact prose. |
| 228-03 LOW: racy immediate qdisc read | PARTIALLY RESOLVED | Plan mentions bounded retry or reuse, but doesn't force retry unless reused proof is proven settle-safe. |
| 228-04 MEDIUM: todo close convention ambiguous | RESOLVED | Task 3 inspects newest-active convention, chooses one deliberately, records moved-from/moved-to trail. |
| 228-04 LOW: SAFE-13 proof could overstate Spectrum restore | RESOLVED | Tasks 1 & 4 explicitly separate SAFE-13 controller/ATT proof from the 228-03 Spectrum rollback proof. |

**REMAINING_UNRESOLVED_HIGH: 0**

## Cycle 2 Consensus Summary

Single external reviewer (Codex) + Claude's independent repo verification. The convergence loop's
job — clear the cycle-1 HIGHs — is done.

### Agreed (verified) state
- All 4 cycle-1 HIGHs RESOLVED: columnar diffserv4 parsing + `{id, cake_name}` tin identity (228-01),
  the coupled tin-separation dependency now correctly ordered and fail-closed (228-02), and the
  rollback `--out` evidence-hygiene fix (228-03). Claude independently confirmed the underlying repo
  facts each fix targets.
- 3 PARTIALLY RESOLVED items remain, all MEDIUM/LOW, none gating: (a) 228-01 sha256 manifest has a
  mechanism but no automated assertion; (b) 228-03 stale "GREEN" prose lingers though the actual
  test path uses `status == "healthy"`; (c) 228-03 qdisc-read race only soft-constrained
  (retry-or-reuse, not forced bounded retry).

### New (cycle-2) MEDIUM concerns worth a light touch before execute (non-gating)
- **Occupancy-metric completeness (228-01/228-02):** thresholds list `non_be_sojourn` alongside
  `non_be_packets`, but the plans only concretely emit/evaluate `non_be_packets`. Either emit a
  `non_be_sojourn` signal or have the gate explicitly mark threshold-listed metrics present /
  `not_observed` so "all five families against real data" is literally true.
- **Derive rationale from gate output (228-02/228-04):** `safe13_lift.rationale` and the closeout
  "no useful per-tin separation" line should read from actual per-interface gate results rather than
  baking in the expected narrative (precision, not correctness — the reject stands on RRUL p99).
- **Post-deploy config provenance (228-03):** rewriting the annotation after deploy leaves repo vs
  deployed differing by a comment; record that explicitly or rewrite-before-deploy.

### Divergent Views
None — single reviewer. Claude's verification agrees with every load-bearing Codex claim checked.

---

# Cycle 1 — 2026-06-04T17:43:37Z

> Reviewer set: Codex (`codex-cli 0.135.0`). Claude skipped (self). Load-bearing factual claims were
> independently verified against the repo before this cycle was written.

## Codex Review (cycle 1)

### Summary

The phase decomposition is mostly sound: verdict first, rollback second, closeout last, with SAFE-13
kept explicit. The biggest issue is Plan 228-01 rests on a false current-state assumption: the
authoritative diffserv4 candidate summary currently has `interfaces: {}` because the existing parser
recognizes `Tin 0` style output, while diffserv4 CAKE output is columnar (`Bulk / Best Effort /
Video / Voice`). Without fixing and testing that parser path, the tin-separation gate will be weak
or fail-closed for the wrong reason.

### PLAN 228-01 — Concerns
- **HIGH:** Existing candidate summary has `interfaces: {}`. Raw diffserv4 `tc` output is columnar,
  not `Tin N` blocks, so current `parse_tc_qdisc()` will not populate tins for candidate data. The
  plan must explicitly add/test columnar CAKE parsing or tin separation will not be evidence-based.
- **HIGH:** The plan assumes tin ids `0..3`, but diffserv4 output uses names/columns: `Bulk`,
  `Best Effort`, `Video`, `Voice`. "BE tin is 0" is true for besteffort output, not columnar.
- **MEDIUM:** Re-emitting summaries changes `baseline-summary.json` / `BASELINE-SUMMARY.md`; existing
  `artifact-sha256.txt` hashes may become stale unless explicitly handled.
- **LOW:** "Only additive diff" is too narrow if parser support changes `interfaces` `{}` → real tins.

### PLAN 228-02 — Concerns
- **HIGH:** Depends on 228-01 producing trustworthy `tin_separation`; given the parser issue, this
  plan can produce a reject for the wrong tin-separation reason.
- **MEDIUM:** Percent-increase gates need defined zero-baseline behavior (restart_rate 0.0/0.0
  div-by-zero risk).
- **MEDIUM:** `gate_ul_stability` — current summaries don't expose a UL p99 field; verdict should
  mark that subcheck `not_observed`, not silently imply coverage.
- **MEDIUM:** "Primary interface" for tin separation not defined (spec-router vs spec-modem).
- **LOW:** `safe13_lift:false` appropriate for the authoritative reject, but evaluator shouldn't make
  it look automatic for every hypothetical accept.

### PLAN 228-03 — Concerns
- **HIGH:** The example real rollback command omits `--out`, so `phase227-rollback.sh` writes to its
  Phase 227 default proof path, polluting prior-phase evidence.
- **MEDIUM:** Replacing the `configs/spectrum.yaml` annotation after deploy conflicts with the
  "Snapshot A byte restore" language.
- **MEDIUM:** Repo proof only compares selected lines (can miss unrelated drift).
- **MEDIUM:** Health wording says `GREEN`; existing health scripts use `status == "healthy"`.
- **LOW:** Single immediate qdisc read after restart can be racy.

### PLAN 228-04 — Concerns
- **MEDIUM:** Depends on 228-03 proof semantics; closeout may overstate "restored to Snapshot A."
- **MEDIUM:** Todo close convention ambiguous (`closed` / `completed` / `done`).
- **LOW:** Docs should cite the verdict JSON; avoid copying the full verdict into public docs.
- **LOW:** SAFE-13 boundary check proves controller/ATT only; closeout shouldn't imply it verifies
  Spectrum config restoration.

### Overall (cycle 1)

Fix Plan 228-01 before execution (columnar diffserv4 parsing + real-artifact tests), then tighten
228-02 provenance/zero-denominator semantics and 228-03's rollback `--out` plus Snapshot A proof
language. 4 HIGH concerns (228-01 ×2, 228-02 coupled, 228-03 `--out`).

**Cycle 1 unresolved HIGH: 4.** All carried into the cycle-2 resolution audit above.
