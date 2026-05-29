# Phase 216: Recovery/Refractory Decision - Context

**Gathered:** 2026-05-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 216 reviews the **Phase 196 queue-primary refractory semantics thread**
against current (v1.46) baseline evidence and closes it with exactly one
verdict: **no-change**, **config-only tune**, or **new code-design phase**
(RECOV-01).

This is a **decision-only** phase. It produces a verdict and an evidence-cited
report; it does **not** edit the control path. No `green_required`, `step_up`,
backlog-suppression, or refractory-behavior change lands inside 216. If the
verdict is "tune" or "code", a separate gated follow-up phase is seeded in
ROADMAP.md rather than slipping behavior changes into the decision phase
(success criterion 4, v1.46 safety posture).

**In scope:** reconciling the thread against current evidence, validating the
already-shipped Phase 197 fix, confirming whether the 213 backlog-suppression
flag is a real signal, recording the verdict, closing the thread, and seeding a
follow-up phase if needed.

**Out of scope:** any production tuning, controller code edits, RouterOS writes,
service restarts, steering toggles, or active congestion provocation. Those are
later, gated, single-knob phases — not 216.

</domain>

<decisions>
## Implementation Decisions

### Evidence Basis (RECOV-03)
- **D-01:** Use the **existing Phase 213 passive baseline**
  (`RUN-20260527T222043Z`) to decide that **no new production capture is
  justified** — NOT to claim it validates refractory-active semantics. The phase
  does **not** run a new active capture or provoke a refractory event. Critical
  framing (per cross-AI review): Phase 213 had `pct_samples_refractory_active=0.0`,
  so the refractory code path was *never exercised* during the baseline. 213
  therefore shows **"no current symptom under this load"**, NOT "refractory
  behavior is correct." The recovery-lag rows (`time_to_green_after_red_sec=0.0`)
  are also suspect: they most likely mean "no RED/SOFT_RED was observed," not
  "RED recovered instantly." Worse, `213-REVIEW.md` §WR-02 documents a classifier
  bug (`phase213-classify.py:146-159`): a window that enters RED and never recovers
  computes `lag = float(green_after or 0)` and is logged as `0` seconds — so a zero
  row can mean "never recovered." Do not read these zeros as positive recovery
  evidence. Active provocation adds production
  load + mutation risk that 213 deferred and is not justified by current symptoms.
- **D-01a (RECOV-03 scope):** RECOV-03's "measured from production artifacts" bar
  is satisfied **only for a no-change decision** — because no recovery/refractory
  tuning is being made, no transient-congestion measurement is required. It is
  **NOT** satisfied as evidence supporting any *future* tuning: that would require
  a production artifact containing an actual transient/refractory event
  (`arb_refractory_active > 0`), which the 213 run does not contain. Any future
  tune/code phase must capture that event first.

### Backlog-Suppression Flag Handling
- **D-02:** The 213 classifier flagged `refractory_semantics` as runner-up
  **solely** on `backlog_suppressed_delta` (~14451, near-identical across all
  five ATT tests; 13097–14451 on Spectrum) while `pct_samples_refractory_active=0.0`.
  Before this flag is allowed to influence the verdict, the researcher MUST
  **prove (not assume)** whether `backlog_suppressed_delta` is a **real per-event
  distress counter** or a **per-cycle / per-window accumulation artifact**. The
  identical 14451 across unrelated ATT tests strongly suggests an artifact, but
  the report MUST show the counter provenance explicitly:
  - The classifier merges **all** `health-*.ndjson` files per target test window
    (`scripts/phase213-classify.py:98`), then computes the delta as `max - min`
    over **cumulative lifetime counters** (`scripts/phase213-classify.py:271`).
  - The underlying counter increments on **backlog-suppressing GREEN recovery, not
    refractory itself** (`src/wanctl/queue_controller.py:265`).
  - The report must state whether any *target-WAN-only, per-file* delta remains
    meaningful after stripping the merge + cumulative-counter artifact.
  Resolve the semantics by reading the counter source and the classifier, not by
  capturing new data.

### Phase 197 Reconciliation
- **D-03:** Treat **Phase 197 as the de-facto resolution** of the Phase 196
  conflict. Phase 197 shipped the split-semantics arbitration — suppress RTT-veto
  during refractory and return queue-primary directly via
  `ARBITRATION_REASON_QUEUE_DURING_REFRACTORY` (live in `wan_controller.py:101`).
  **The semantic proof that 197 resolved the conflict is Phase 197's own code +
  replay tests** (`tests/test_phase_197_replay.py`, asserting the
  `queue_during_refractory` / `rtt_fallback_during_refractory` branches) plus any
  existing post-197 production validation — **NOT** the Phase 213 baseline. Phase
  213's role in D-03 is narrow: confirm there is **no current live symptom** of the
  original regression, not to validate the refractory-active branch (213 has zero
  refractory-active samples to validate against). Note: 197 took a *different*
  route than the thread's original candidate design (split `dl_cake_for_detection`
  from `dl_cake_for_arbitration`); the thread was never updated to reflect 197,
  which is why it is stale-open. The original split design is NOT pursued on its
  own merits unless the 197 code/tests are shown insufficient.

### Deliverable / Thread Closure
- **D-04:** Produce a **`216-REPORT.md`** with the evidence-cited verdict, then
  update the thread file status to `closed` and mark RECOV-01/02/03. If the
  verdict is "config tune" or "code design", seed a follow-up phase in ROADMAP.md
  (do not implement here). Report style mirrors the operator-first closeout of
  212/213/214/215 reports.
- **D-04a (reopen criteria):** The thread closeout MUST record explicit reopen
  triggers, since the close is based on absence-of-symptom rather than an exercised
  refractory window. Reopen the refractory thread (or open a new follow-up) if a
  natural production artifact later shows `arb_refractory_active > 0` accompanied by
  any of: RTT fallback during what should be queue-primary load, measurable recovery
  lag after RED/SOFT_RED, or throughput collapse during the refractory window.

### Hard Constraints (carry-forward, non-negotiable)
- **D-05:** RECOV-02 / Phase 160 cascade safety is preserved by construction —
  216 changes no code, but any follow-up it seeds MUST keep refractory free of
  cascading CAKE drop/backlog reductions and MUST keep a valid queue-delay
  scalar available for queue-primary classification where needed.
- **D-06:** Phase 212 steering-drift constraint: do **not** interpret
  v1.39-shaped steering threshold field names as v1.45 semantics. Refractory
  decision relies on autorate `/health` + CAKE signal evidence, not steering
  threshold-name comparison.

### Expected Landing (not pre-decided — the phase produces the verdict)
- The evidence currently leans **no-change / resolved-by-197**, but this is the
  operator's prior, NOT a locked verdict, and the framing matters (per review):
  213 shows *no current symptom*; the 0% refractory-active rate means it does NOT
  prove correctness. The verdict does not "write itself" — it requires meeting
  explicit exit criteria:
  - **Exit criterion 1 (D-02):** backlog flag is shown to be a merge/cumulative-counter
    artifact (or, if real, re-opens the analysis).
  - **Exit criterion 2 (D-03):** Phase 197's code + replay tests are confirmed to
    cover the refractory-active arbitration branches.
  - **Exit criterion 3 (D-01):** Phase 213 confirms no current live symptom of the
    original regression.
  Only with all three met does the report land on no-change / resolved-by-197.

### Claude's Discretion
- Planner retains discretion on: exact report structure, whether the artifact
  check (D-02) is a standalone analysis step or folded into the evidence review,
  the precise thread-close wording, and how the seeded follow-up phase (if any)
  is scoped — provided D-01 through D-06 hold.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase / Milestone Scope
- `.planning/ROADMAP.md` §"Phase 216: Recovery/Refractory Decision" — goal, depends-on (213; maybe 214/215), success criteria 1–4.
- `.planning/REQUIREMENTS.md` §"Recovery / Refractory (RECOV)" — RECOV-01, RECOV-02, RECOV-03.
- `.planning/PROJECT.md` §"Current Milestone: v1.46 Internet Quality Recovery" — milestone goal and operating context.
- `.planning/STATE.md` §"Cross-Cutting Invariants" / "v1.46 safety posture" — no production tuning before baseline evidence + rollback gates.

### The Thread Being Closed (authoritative)
- `.planning/threads/phase-196-queue-primary-refractory-semantics-investigation.md` — the open thread: design-conflict statement, code path, candidate split design, required tests, next steps. **216 must update its status to closed.**

### Current Baseline Evidence (D-01 basis)
- `.planning/phases/213-experience-baseline-harness/213-REPORT.md` — §"Download recovery lag — NOT FLAGGED" and §"Refractory semantics — FLAGGED AS RUNNER-UP"; next-phase verdict and constraints (lines ~27–83).
- `.planning/phases/213-experience-baseline-harness/evidence/RUN-20260527T222043Z/signal-sheet.md` — refractory_semantics section (`backlog_suppressed_delta`, `pct_samples_refractory_active`), download recovery-lag rows.
- `.planning/phases/213-experience-baseline-harness/evidence/RUN-20260527T222043Z/signal-sheet.json` — machine-readable signal sheet for the artifact check (D-02).
- `.planning/phases/213-experience-baseline-harness/213-CONTEXT.md` — 213 decisions; especially the steering-drift carry-forward (D-08/D-14) and the deferred "active steering toggle to force bucket evidence → Phase 216" note.
- `.planning/phases/213-experience-baseline-harness/213-REVIEW.md` §WR-02 — **MUST read before relying on recovery-lag rows.** Documents that `analyze_download_recovery` (`scripts/phase213-classify.py:146-159`) leaves `green_after=None` when a window enters RED/SOFT_RED and never returns to GREEN, then computes `lag = float(green_after or 0)` — so a **non-recovery is logged as `0` seconds**. A `time_to_green_after_red_sec=0.0` row is therefore NOT proof of fast recovery; it may mean "never recovered" or "no RED observed." The verdict must not treat these zeros as positive recovery evidence.
- `scripts/phase213-classify.py:98,271` — the classifier merges all per-WAN `health-*.ndjson` per window (`:98`) and computes `backlog_suppressed_delta` as `max-min` over cumulative lifetime counters (`:271`); read both for the D-02 artifact provenance.

### Phase 197 — the shipped fix (D-03 validation target)
- `.planning/milestones/v1.40-phases/197-queue-primary-refractory-semantics-split-dl-cake-for-detecti/197-01-PLAN.md` — the implemented split-semantics arbitration (D-04/D-06/D-07): suppress RTT-veto during refractory, `queue_during_refractory` + `rtt_fallback_during_refractory` reasons.
- `.planning/milestones/v1.40-phases/197-queue-primary-refractory-semantics-split-dl-cake-for-detecti/197-DISCUSSION-LOG.md` — the design decisions D-01..D-11 behind 197.
- `tests/test_phase_197_replay.py` — **the actual semantic proof for D-03**: replay tests asserting the `queue_during_refractory` / `rtt_fallback_during_refractory` arbitration branches. The verdict's "197 is validated" claim rests on these, not on 213.

### Original Conflict Provenance
- `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/196-12-SUMMARY.md` — Phase 196 corrected-Spectrum throughput regression that opened the thread.
- `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/throughput-root-cause-investigation.json` — root-cause artifact (refractory masking forced RTT fallback during queue-primary load).
- `.planning/phases/194-download-queue-primary-distress-classification/194-PATTERNS.md` — invariant: selector MUST run after refractory masking and see masked `dl_cake`.
- `.planning/phases/194-download-queue-primary-distress-classification/194-01-PLAN.md` — DO NOT read `self._dl_cake_snapshot` inside the selector.
- `.planning/milestones/v1.33-phases/163-parameter-sweep/163-02-SUMMARY.md` — why `refractory_cycles=40` was kept conservatively (shorter cooldown risks cascading reductions).

### Drift Constraint (D-06)
- `.planning/phases/212-production-inventory-and-drift-audit/212-REPORT.md` — steering version/threshold drift register; the v1.39-vs-v1.45 semantics constraint 216 must carry forward.

### Code Surfaces (artifact check + 197 validation)
- `src/wanctl/wan_controller.py` — arbitration reasons (`ARBITRATION_REASON_QUEUE_DURING_REFRACTORY` :101, `RTT_FALLBACK_DURING_REFRACTORY` :102), `_dl_refractory_remaining`, `_refractory_cycles`, refractory masking (sets `dl_cake=None` during refractory).
- `src/wanctl/queue_controller.py` — `_dwell_bypassed_this_cycle` / `_dwell_bypassed_count` (the dwell-bypass trigger that arms refractory) and backlog counter emission.
- `src/wanctl/cake_signal.py` — `refractory_cycles` default (40) and CAKE detection signal; relevant to the backlog-suppression metric semantics.
- `src/wanctl/health_check.py` — `/health` payload (`dwell_bypassed_count`, refractory fields) that the 213 classifier consumed.
- `tests/test_wan_controller.py` — asserts refractory masks snapshots; the regression guard for any seeded follow-up.

### Folded Todo
- None.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 197's arbitration semantics are already in `wan_controller.py` — 216
  validates, it does not re-implement. The two refractory-specific reason
  constants (`queue_during_refractory`, `rtt_fallback_during_refractory`) are the
  observable proof that 197 shipped.
- The 213 signal sheet (`.json` + `.md`) is the ready-made evidence corpus; the
  artifact check (D-02) reads it plus the counter source, no new capture.

### Established Patterns
- Production control path is link-agnostic and change-conservative ("suggest,
  don't implement"). 216 honors this trivially by being decision-only.
- Operator-first report closeout (212/213/214/215): evidence-cited verdict,
  stable artifact paths, explicit constraints carried forward. 216-REPORT.md
  follows the same shape.

### Integration Points
- Autorate `/health` (`cake_signal`, refractory fields) is the evidence surface —
  Spectrum `:9101`, ATT `:9101` (bound endpoints per Phase 212). No live probing
  needed; 213 already captured.
- Refractory arm path: `queue_controller` sets `dwell_bypassed_this_cycle` →
  `wan_controller` sets `_dl_refractory_remaining = refractory_cycles (40)` →
  during refractory `dl_cake` is masked but (post-197) arbitration still returns
  queue-primary.

</code_context>

<specifics>
## Specific Ideas

- The crux to settle is a single empirical question: is the 213
  `backlog_suppressed_delta` (~14451, eerily constant across ATT tests) a real
  distress signal or a merge/cumulative-counter artifact? Settle that, confirm
  Phase 197's code/tests cover the refractory branches, and confirm 213 shows no
  live symptom — then the report meets its exit criteria.
- Frame the report honestly: "the Phase 196 thread is closed because Phase 197's
  shipped code + replay tests resolve the original throughput regression, and the
  current Phase 213 baseline shows no live symptom." Do NOT write "Phase 213
  validated refractory semantics" — 213 never exercised the refractory path
  (0% active).
- Keep the verdict honest: "no-change" here means "no NEW change; 197's shipped
  change stands and is validated by its own tests", not "nothing was ever done"
  and not "213 proved it correct".

</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- `.planning/todos/pending/2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md`
  — Resolve ATT cake-primary canary after Phase 196 (score 0.6). **Not folded:**
  it is an *active* validation canary requiring an ATT cake-primary mode switch +
  flent load, which conflicts with D-01 (passive-only) and the v1.46 no-tuning
  posture. It is also gated on Phase 191 closure (still open). It validates
  cake-primary *mode end-to-end on ATT*, which is distinct from the refractory
  *semantics decision* 216 owns. Defer to a dedicated cake-primary validation
  phase once Phase 191 closes.
- `.planning/todos/pending/2026-04-15-profile-post-hotpath-baseline-on-production-wan.md`
  — Post-hotpath cycle-budget profiling (score 0.4). Phase 217 explicitly owns
  this; out of scope for the refractory decision.

### Out-Of-Scope Suggestions Considered
- Active refractory provocation / controlled congestion event to capture
  in-window refractory evidence — considered (D-01 question) and rejected in
  favor of the existing passive 213 baseline. Candidate for a future phase only
  if 216's evidence review proves ambiguous.
- Pursuing the thread's original `dl_cake_for_detection` / `dl_cake_for_arbitration`
  split design — superseded by Phase 197's shipped approach (D-03); only revisited
  if 197 is shown insufficient.

</deferred>

---

*Phase: 216-recovery-refractory-decision*
*Context gathered: 2026-05-29*
