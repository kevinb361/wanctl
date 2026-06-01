---
phase: 221
slug: matrix-evidence-closeout-scope-a2
status: complete
created: 2026-06-01
---

# Phase 221 — Technical Research

> Research backing the operator-driven matrix execution and Phase 221 closeout report. No new harness, no new aggregator, no controller-path code. Everything below feeds plan structure, not implementation novelty.

---

## Research Question

How do we operate the 54-run target/path/window matrix landed by Phase 220 across multiple calendar days, then write `221-CLOSEOUT.md` applying CRITERIA-01 thresholds + the three-step verdict roll-up algorithm verbatim, then close-or-carry the folded `tcp_12down` todo — all while keeping the Phase 220 mutation boundary green and the controller path untouched?

---

## R1 — Phase 221 Is an Execution + Reporting Phase

The Phase 221 deliverables are NOT code:

1. **EVIDENCE-LEDGER.md** — running status table updated across operator sessions.
2. **CLOSEOUT.md** — final per-cell + per-axis + matrix-level verdict report.
3. **Optional `CLOSEOUT.json`** — schema_version=1 machine-readable companion (D-21 envelope) IF aggregator already emits structured output (it does — Phase 220-02 aggregator output JSON).
4. **Todo move** — `git mv` from `pending/` to `closed/` + body append.
5. **`tests/test_phase221_mutation_boundary.py`** — SAFE-11 clone at Phase 221 boundary.

Implications for plan structure:
- **No Wave 0 fixture wave** — there is no aggregator to test (Phase 220-02 already pinned). Wave 0 is the SAFE-11 boundary clone landed FIRST so subsequent commits cannot regress the controller-path forbidden list.
- **Wave 1 is operator-driven, multi-session, multi-day** — the matrix execution wave. Plans in this wave document the operator runbook and the per-session ledger update Claude performs, NOT a code task.
- **Wave 2 is the closeout report** — only fires after the ledger says 54/54 complete or a matrix-fail trigger (D-09) fires.
- **Wave 3 is the todo move + closeout-amendment + final SAFE-11 re-run** — depends on the closeout verdict (only D-15 close-with-prejudice rule attaches if verdict = carried_narrower).

This sequencing matches CONTEXT D-03 (multi-session resume via ledger) and D-16 (closeout cites the todo-move commit SHA — natural ordering: aggregator → closeout → todo move → closeout amend).

---

## R2 — EVIDENCE-LEDGER.md Schema

The ledger is the multi-session state surface. Claude reads `evidence/` directories, updates the ledger, commits, exits. The ledger MUST be machine-greppable so Claude in a future session can resume without re-reading every evidence directory.

**Schema (markdown table, one row per cell, three sub-rows per replicate — or rolled-up single row if all 3 replicates done):**

| cell_id | replicates | window | path | target | last_replicate_utc | mtr_pre_sha256 | mtr_post_flag | base_sha | status | notes |
|---------|------------|--------|------|--------|--------------------|----------------|---------------|----------|--------|-------|
| dallas__spectrum__off-peak | 0/3 | off-peak | spectrum | dallas | — | — | — | — | pending | — |
| dallas__spectrum__daytime | 3/3 | daytime | spectrum | dallas | 2026-06-01T15:38:16Z | 6c8e… | false | abc123… | complete | rehearsal cell from 220-04 |

Status vocabulary: `pending | partial | complete | incomplete | bgp-changed`
- `pending` = 0/3 replicates run
- `partial` = 1 or 2 of 3 replicates run, no failure (operator paused)
- `complete` = 3/3 replicates with no D-08 failure
- `incomplete` = ≥1 replicate hit 3 failed attempts per D-08
- `bgp-changed` = replicate's `mtr-pre` differs from previous cell's `mtr-post` for same target; cell still computable but D-10 flag set

**Cell completion detection (greppable):** Claude's session-start procedure is:
```bash
find .planning/phases/220-matrix-runner-scope-a1/evidence -name 'signal-sheet.json' \
  -path '*__r*/signal-sheet.json' | wc -l
```
… then compares against 54. The aggregator (Phase 220-02) accepts the evidence path and emits cube JSON; the ledger row is the human-readable mirror, the file system is the source of truth.

**Why not just rely on filesystem:** the ledger captures rationale (incomplete reason; bgp-changed footnote) that the filesystem does not. Aggregator output JSON also captures it but the ledger is the operator-facing summary across sessions.

---

## R3 — Closeout Report Structure (D-04 through D-07)

The report's section structure is fixed by CONTEXT decisions:

1. **Frontmatter**: `phase: 221`, `verdict: <one of three>`, `matrix_base_sha: <sha>`, `phase220_yaml_sha: <sha>`, `closeout_commit_for_todo: <pending|sha>`, `aggregator_run_utc: <iso>`.
2. **§1 Verdict** — single sentence + one of `{defect_located, hypothesis_killed, carried_narrower_with_close_with_prejudice_rule}`.
3. **§2 Threshold Citation** — Phase 220 YAML SHA + the six locked threshold values copied verbatim from `scripts/phase220-matrix.yaml`'s `thresholds:` block. Citation, not redefinition.
4. **§3 Table 1: Canonical Control** — per-cell rows for the 6 canonical cells (3 windows × 2 paths = 6). Columns per D-05.
5. **§4 Table 2: Supplemental Cells** — per-cell rows for the 12 supplemental cells (2 supplemental targets × 2 paths × 3 windows = 12).
6. **§5 Per-Axis Rollup** — three sub-sections (per-target, per-path, per-window), each with axis-value + axis-verdict, per D-06. Aggregation rule cited inline.
7. **§6 Matrix-Level Verdict Decision Tree** — bulleted trace per D-07. Each branch shows `MATCHED` or `FAILED` with the evidence. Example skeleton:
   ```
   - [FAILED] defect_located requires ≥1 supplemental cell_defect across ≥2 windows AND orthogonal corroboration.
     - Supplemental cell_defects found: <count> across <list of (cell_id, window)>
     - Orthogonal corroboration check: <path-orthogonal? target-orthogonal? driver-orthogonal?>
   - [MATCHED] hypothesis_killed requires canonical p99 ≤ 200ms on ≥2/3 windows AND no supplemental > 1.5× control p99.
     - Canonical p99: off-peak=<X>, daytime=<Y>, prime-time=<Z>  → <count>/3 below 200ms
     - Supplemental ratios: <max ratio, cell>
   ```
8. **§7 BGP-Change Footnote (if any)** — list cells with `mtr_post_flag: true`. Per D-10, these cells are excluded from defect-corroboration arguments.
9. **§8 Failed-Cell Footnote (if any)** — list cells marked `INCOMPLETE` with failure reasons.
10. **§9 Historical Context (reportage only — NOT a verdict input)** — per CONTEXT specifics, mention whether any Phase 221 cell reproduced the folded-todo p99 > 1000ms (2026-04-15 p99 = 3059ms historical worst case) and how the Phase 214 daytime/prime-time anchors (606ms, 560ms) resolved under the matrix.
11. **§10 Todo Disposition** — verdict applied, target path of moved todo file, commit SHA of the todo-move commit (D-16). On `carried_narrower_with_close_with_prejudice_rule`, CRITERIA-02 rule pasted **verbatim from REQUIREMENTS.md**.
12. **§11 Mutation Boundary** — citation of `tests/test_phase221_mutation_boundary.py` last-run timestamp + pass/fail.

**Style anchor:** Phase 217 baseline summaries (markdown cadence) + Phase 214 matrix-summary structure (verdict tables).

---

## R4 — Aggregator Invocation Timing (Claude's Discretion in CONTEXT)

Per CONTEXT discretion item: run aggregator ONCE at end-of-matrix; intermediate runs MAY appear in evidence but MUST NOT appear in closeout.

Concrete: the closeout-writing plan invokes:
```
.venv/bin/python scripts/phase220-matrix-aggregator.py \
  --evidence-root .planning/phases/220-matrix-runner-scope-a1/evidence \
  --output .planning/phases/221-matrix-evidence-closeout-scope-a2/221-CLOSEOUT.json
```
… and the closeout-writing plan reads `221-CLOSEOUT.json` to populate §3, §4, §5 tables. Aggregator emits schema_version=1 envelope per Phase 219 D-17.

**Avoid data-driven-stop:** the ledger-update plans (multi-session) MUST NOT invoke the aggregator. Only the dedicated closeout-writing plan does, and only after ledger shows 54/54 or matrix-fail trigger.

---

## R5 — Todo Move Mechanics (D-13 through D-17)

Steps (executed in a single commit per D-16 simplest path):

1. **Create `closed/` directory if absent.** The repo today has `pending/`, `completed/`, `done/`. CONTEXT D-13 specifies `closed/` — Plan 04 creates it via `git mv` (git auto-creates the dir).
2. **`git mv .planning/todos/pending/<file> .planning/todos/closed/<file>`**
3. **Append YAML frontmatter fields (D-14):** `closed_by_phase`, `verdict`, `close_with_prejudice`. Append in-place via a Python script that re-writes the file with the three fields added INSIDE the existing `---` block.
4. **Append `## Phase 221 Closeout` section (D-15):**
   - Verdict + summary line
   - `See .planning/phases/221-matrix-evidence-closeout-scope-a2/221-CLOSEOUT.md`
   - Matrix `base_sha` + Phase 220 YAML SHA
   - On carry verdict: paste CRITERIA-02 rule verbatim from `.planning/REQUIREMENTS.md` (extract via grep)
5. **Commit:** `chore(221): close folded tcp_12down todo (verdict: <X>)`. Record commit SHA.
6. **Amend closeout report (D-16):** edit `221-CLOSEOUT.md` §10 to fill `closeout_commit_for_todo` with the SHA from step 5. Separate amend commit. OR — alternative path — combine steps 5+6 into a single commit if the closeout is written FIRST with `closeout_commit_for_todo: PENDING_FINAL_COMMIT` and the final commit replaces both files at once. **Recommendation:** two-commit path (close todo first, then amend closeout). Reasoning: the todo-close commit is auditable on its own; the closeout-amend commit shows the cross-reference being inserted as a deliberate operation.

**"Narrower" = the rule itself (D-17):** no scope narrowing in the closure stanza. The carried verdict is exactly `carried_narrower_with_close_with_prejudice_rule`; no daytime-only or path-only narrowing permitted.

---

## R6 — SAFE-11 Phase 221 Allowlist

Cloning `tests/test_phase220_mutation_boundary.py` per the Phase 214/219/220 pattern. The Phase 221 allowlist is:

**Allowed for additive edits:**
- `.planning/phases/221-matrix-evidence-closeout-scope-a2/**` — all artifacts inside the phase dir (EVIDENCE-LEDGER.md, CLOSEOUT.md, CLOSEOUT.json, PLAN files, SUMMARY files, VALIDATION.md, VERIFICATION.md, RESEARCH.md)
- `.planning/todos/closed/**` — todo move destination
- `.planning/todos/pending/<file>.md` — DELETION via `git mv` (rename detected by git, not a `pending/` mutation)
- `tests/test_phase221_mutation_boundary.py` — this test file itself
- `docs/PHASE221-CLOSEOUT.md` — IF emitted (Claude discretion; CONTEXT does not require). Restricted to describing closeout report only; no threshold-tuning language; no future-tuning predictions.

**Forbidden (controller-path — unchanged from Phase 220):**
- `src/wanctl/wan_controller.py`, `queue_controller.py`, `cake_signal.py`, `alert_engine.py`
- `src/wanctl/backends/**/*.py`
- `src/wanctl/fusion*.py`
- All Phase 213 scripts (`scripts/phase213-*`) — frozen
- All Phase 214 scripts (`scripts/phase214-*`) — frozen
- All Phase 220 scripts (`scripts/phase220-*`) — frozen (the matrix runner, aggregator, YAML, precompute-pins are LOCKED by Phase 220 close; Phase 221 uses them read-only)

**Allowlist mutation pattern (PHASE220_SCRIPT_ALLOWLIST equivalent):** Phase 221 does NOT add new scripts — there are no `phase221-*` scripts. The `PHASE221_SCRIPT_ALLOWLIST` is the empty set. The test asserts no NEW `scripts/phase221*` files appear.

**Base SHA detection:** clone Phase 220 pattern — env var `PHASE221_BASE_SHA`, else git log marker `docs(phase-221): begin phase execution`, else fall back to Phase 220 YAML's base_sha. This last fallback ties Phase 221 SAFE-11 to the same source-floor anchor Phase 220 enforced.

**`docs/` restriction (verbatim from REQ SAFE-11):** "no threshold-tuning language, no future tuning predictions." The test asserts no `docs/` diff contains tokens matching the forbidden-mutation regex (already in Phase 220 test — copy verbatim). Phase 221's expected `docs/` diff is zero (closeout report lives in `.planning/`, not `docs/`).

---

## R7 — Multi-Session Resume Strategy

Each operator session is short (mid-day check-in or end-of-window cell-run). Claude's session-start procedure must be deterministic:

```bash
# Detect completed replicate count
COMPLETED=$(find .planning/phases/220-matrix-runner-scope-a1/evidence \
  -path '*__r*/signal-sheet.json' | wc -l)
# Detect ledger row count
LEDGER_ROWS=$(grep -c '^| ' .planning/phases/221-matrix-evidence-closeout-scope-a2/221-EVIDENCE-LEDGER.md || echo 0)
```

If `COMPLETED < 54`: session is in **execution phase**. Claude reads new evidence dirs added since last ledger update, appends/updates ledger rows, commits ledger only. Does NOT invoke aggregator.

If `COMPLETED == 54`: session is in **closeout phase**. Claude invokes aggregator, writes CLOSEOUT.md/json, moves todo, amends closeout, re-runs SAFE-11. Each step is a separate commit.

If `COMPLETED < 54` but matrix-fail trigger fired (D-09: >2 supplemental incomplete OR any canonical incomplete): session is in **abort phase**. Claude writes a short `221-MATRIX-INVALID.md` recording the failure mode and stops. Phase reopens for replan.

---

## R8 — BGP Change Handling (D-10) — Reportage Surface

The wrapper already writes `mtr-pre-<N>.txt` per replicate (Phase 220 plumbing). On a BGP change, it ALSO writes `mtr-post-<N>.txt`. Phase 221's reading procedure:

1. For each cell directory, glob for `mtr-post-*.txt`. If ANY exist for the cell, the cell carries `mtr_post_flag: true` in §3/§4 closeout table.
2. Per D-10, cells with `mtr_post_flag: true` AND `cell_verdict == cell_defect` are EXCLUDED from defect-corroboration arguments in §6 decision tree. Cells are still listed in §3/§4 with their primary driver, but the §6 trace skips them for the orthogonal-corroboration count.

The aggregator (Phase 220-02) does not know about BGP exclusion — that's a closeout-time decision. The closeout-writing plan applies the exclusion when populating the §6 decision tree, NOT when reading aggregator cube output.

---

## R9 — Folded Todo Body Append Mechanics

The folded todo's existing content (problem statement, fresh validation runs, classifier outputs, prior investigation log) MUST be preserved. The closure stanza is APPENDED at the end of the file.

```bash
# Pseudocode
TODO=.planning/todos/closed/2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl.md
cat >> "$TODO" <<EOF

## Phase 221 Closeout

**Verdict:** {defect_located | hypothesis_killed | carried_narrower_with_close_with_prejudice_rule}
**Summary:** {one-line summary derived from §6 trace}
**Report:** See `.planning/phases/221-matrix-evidence-closeout-scope-a2/221-CLOSEOUT.md`
**Matrix base_sha:** {sha}
**Phase 220 YAML SHA:** {sha}

{IF verdict == carried_narrower_with_close_with_prejudice_rule:}
### Close-With-Prejudice Rule (verbatim, REQUIREMENTS.md CRITERIA-02)

> {verbatim text grepped from .planning/REQUIREMENTS.md - see Plan 04 for extraction shell}
EOF
```

YAML frontmatter mutation (D-14) — three NEW fields appended INSIDE the existing `---` block. A short Python helper script reads the file, locates the closing `---`, inserts the three fields BEFORE it. Safer than `sed` because the frontmatter contains `---` substrings only at start/end of YAML block.

---

## R10 — Closeout Report as Pure Read of Aggregator Output

To avoid drift between the closeout report and the aggregator's verdict computation, the closeout report MUST NOT re-derive cell verdicts. The flow is:

1. Aggregator produces `221-CLOSEOUT.json` with `cells: [{cell_id, ..., cell_verdict}]`, `per_axis: {...}`, `matrix_verdict: "..."`, and `decision_tree_trace: [...]`.
2. Closeout-writing plan READS the JSON and FORMATS markdown tables.
3. The only NEW computation in the closeout report is the §6 BGP-exclusion overlay (R8) — and that's a filter, not a recomputation.
4. The §9 historical-context reportage (Phase 214 anchor comparison, folded-todo p99 reproduction check) is read FROM the JSON via lookup-by-cell-id.

**This means the aggregator must already emit `decision_tree_trace` field.** Phase 220-02 aggregator output structure — verify before Plan 02 writes. If absent, the closeout-writing plan synthesizes the trace from aggregator's `matrix_verdict` + `per_axis` + `cells` fields. This is documented in Plan 02 acceptance criteria as a verification step.

---

## R11 — `CLOSEOUT.json` Emission Decision

CONTEXT discretion: emit machine-readable JSON IF aggregator already produces structured cube output. It does (Phase 220-02). Therefore: **YES, emit `221-CLOSEOUT.json`**.

The JSON IS the aggregator output (renamed). The markdown CLOSEOUT.md is a human-formatted view of the same data plus BGP-exclusion overlay and §9 reportage. Schema_version=1 per Phase 219 D-17 envelope.

---

## R12 — Validation Strategy

Per `gsd-sdk` validation gate. Since Phase 221 has no aggregator/wrapper code, validation is:

| Layer | Test |
|-------|------|
| **Wave 0** | `tests/test_phase221_mutation_boundary.py` exists with controller-path forbidden list + empty allowlist. SAFE-11 passes green from first commit. |
| **Wave 1 (ledger)** | Source assertion: ledger row count matches `find evidence -name signal-sheet.json` count. No automated pytest — this is operator-session work; ledger is human-greppable. |
| **Wave 2 (closeout)** | Source assertions: `221-CLOSEOUT.md` parses as markdown; contains exactly one of three verdict tokens in §1; §3 has 6 canonical rows; §4 has 12 supplemental rows; §6 trace cites Phase 220 YAML SHA; `221-CLOSEOUT.json` is valid JSON + schema_version=1. |
| **Wave 3 (todo move)** | Source assertions: `pending/<file>` does not exist; `closed/<file>` exists; YAML frontmatter has three new fields; body contains `## Phase 221 Closeout`; on carry verdict, body contains CRITERIA-02 verbatim text. |
| **Phase close** | `tests/test_phase221_mutation_boundary.py` passes green; controller-path diff empty against Phase 220 base_sha. |

The mutation-boundary test is the only pytest. Other validation is source/shell assertions in plan `<acceptance_criteria>`.

---

## R13 — Pitfall Mitigations Applied

- **Pitfall 2 (data-driven threshold leakage):** D-01 (always run all 54), D-04 (canonical separation), D-05 (per-cell rows cite base_sha per cell), and §2 closeout citing Phase 220 YAML SHA. Plans enforce: no closeout writeup until ledger reaches 54/54 OR D-09 matrix-fail fires.
- **Pitfall 4 (BGP path change):** D-10, R8 above. Wrapper already handles mtr-post; closeout overlays the exclusion in §6.
- **Pitfall 8 (mutation boundary):** SAFE-11 clone + Wave 0 landing + final phase-close re-run.
- **Pitfall 12 (`/health` is never quality):** N/A — Phase 221 makes no controller deploys, reads no `/health`.

---

## R14 — Validation Architecture

(Required section name for VALIDATION.md auto-detection.)

The Phase 221 validation contract is short because there is no novel code. The contract is:

1. **SAFE-11 mutation-boundary pytest must pass green at every Phase 221 commit boundary.** Wave 0 lands the test; every subsequent commit re-runs it.
2. **Ledger row count must match filesystem evidence count after every ledger-update commit.** Plan 02-N acceptance criteria asserts this with `find … | wc -l`.
3. **Closeout report markdown MUST cite the Phase 220 YAML SHA verbatim and contain exactly one of three verdict tokens.** Plan 03 acceptance asserts this with `grep -c`.
4. **Closeout JSON MUST validate against schema_version=1 envelope.** Plan 03 acceptance asserts this with a Python one-liner.
5. **Todo move MUST be a `git mv` rename (not a delete+add), preserving git history.** Plan 04 acceptance asserts this with `git log --follow`.
6. **Closeout amend MUST cite the todo-move commit SHA.** Plan 04 acceptance asserts this with `grep`.

No fixtures, no goldens. The verdict IS the evidence.

---

*Phase: 221-matrix-evidence-closeout-scope-a2*
*Research recorded: 2026-06-01*
*Source for all R-claims: CONTEXT.md (D-01..D-17), REQUIREMENTS.md (CLOSEOUT-01..03 + SAFE-11 + CRITERIA-01/02), Phase 220 plans + summaries, Phase 220 SAFE-11 test source.*
