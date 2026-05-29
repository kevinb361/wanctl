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
- **D-01:** Close the thread on the **existing Phase 213 passive baseline**
  (`RUN-20260527T222043Z`). The phase does **not** run a new active capture or
  provoke a refractory event. Rationale: 213 already measured
  `time_to_green_after_red_sec=0.0` on both WANs and `pct_samples_refractory_active=0.0`
  — i.e., under real test load the live system is not lagging and refractory
  never engaged. That absence is itself evidence. Active provocation adds
  production load + mutation risk that 213 explicitly deferred, and is not
  needed to make the verdict. RECOV-03's "measured from production artifacts"
  bar is satisfied by the 213 recovery-lag rows.

### Backlog-Suppression Flag Handling
- **D-02:** The 213 classifier flagged `refractory_semantics` as runner-up
  **solely** on `backlog_suppressed_delta` (~14451, near-identical across all
  five ATT tests; 13097–14451 on Spectrum) while `pct_samples_refractory_active=0.0`.
  Before this flag is allowed to influence the verdict, the researcher MUST
  determine whether `backlog_suppressed_delta` is a **real per-event distress
  counter** or a **per-cycle / per-window accumulation artifact**. The identical
  14451 across unrelated ATT tests strongly suggests an artifact (e.g., a
  monotonic counter delta scaled by window length), not material suppression
  activity. Resolve the metric's semantics by reading the counter source and the
  213 classifier, not by capturing new data.

### Phase 197 Reconciliation
- **D-03:** Treat **Phase 197 as the de-facto resolution** of the Phase 196
  conflict. Phase 197 shipped the split-semantics arbitration — suppress RTT-veto
  during refractory and return queue-primary directly via
  `ARBITRATION_REASON_QUEUE_DURING_REFRACTORY` (live in `wan_controller.py:101`).
  216 validates that shipped behavior against the 213 evidence and closes the
  thread as **resolved-by-197** unless evidence contradicts it. Note: 197 took a
  *different* route than the thread's original candidate design (split
  `dl_cake_for_detection` from `dl_cake_for_arbitration`); the thread was never
  updated to reflect 197, which is why it is stale-open. The original split
  design is NOT pursued on its own merits unless 213 evidence shows 197 is
  insufficient.

### Deliverable / Thread Closure
- **D-04:** Produce a **`216-REPORT.md`** with the evidence-cited verdict, then
  update the thread file status to `closed` and mark RECOV-01/02/03. If the
  verdict is "config tune" or "code design", seed a follow-up phase in ROADMAP.md
  (do not implement here). Report style mirrors the operator-first closeout of
  212/213/214/215 reports.

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
- The evidence currently leans **no-change / resolved-by-197**: recovery lag = 0,
  refractory 0% active, and the only flag is the likely-artifact backlog counter.
  This is the operator's read going in, NOT a locked verdict. The planner/
  researcher must confirm D-02 (artifact check) and D-03 (197 validation) before
  the report records the final call.

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

### Phase 197 — the shipped fix (D-03 validation target)
- `.planning/milestones/v1.40-phases/197-queue-primary-refractory-semantics-split-dl-cake-for-detecti/197-01-PLAN.md` — the implemented split-semantics arbitration (D-04/D-06/D-07): suppress RTT-veto during refractory, `queue_during_refractory` + `rtt_fallback_during_refractory` reasons.
- `.planning/milestones/v1.40-phases/197-queue-primary-refractory-semantics-split-dl-cake-for-detecti/197-DISCUSSION-LOG.md` — the design decisions D-01..D-11 behind 197.

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
  distress signal or a counter/window artifact? Settle that, validate 197
  against the recovery-lag=0 evidence, and the verdict writes itself.
- Frame the report as "the Phase 196 thread is closed because Phase 197 already
  resolved the original throughput regression, and current baseline evidence
  confirms no recovery lag" — unless the artifact check surprises us.
- Keep the verdict honest: "no-change" here means "no NEW change; 197's shipped
  change stands and is validated", not "nothing was ever done".

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
