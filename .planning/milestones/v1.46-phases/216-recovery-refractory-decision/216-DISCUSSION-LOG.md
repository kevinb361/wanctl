# Phase 216: Recovery/Refractory Decision - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-29
**Phase:** 216-recovery-refractory-decision
**Areas discussed:** Evidence basis, Backlog-suppression flag, Phase 197 status, Deliverable

---

## Evidence Basis (RECOV-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Passive 213 only | Close on existing 213 artifacts. Recovery lag=0/refractory=0% is itself evidence the live system isn't lagging. Lowest risk, no new production load. | ✓ |
| Add targeted capture | 216 runs a controlled congestion event to drive refractory active and measure the recovery window. More evidence, but adds production load + mutation risk 213 deferred. | |
| Reuse 196 soak artifacts | Pull the original Phase 196 cake-primary soak captures as the refractory-active dataset, comparing pre/post Phase 197 behavior. | |

**User's choice:** Passive 213 only
**Notes:** Captured as D-01. 213 measured `time_to_green_after_red_sec=0.0` both WANs and `pct_samples_refractory_active=0.0` — absence of lag is itself evidence. RECOV-03's "measured from production artifacts" bar is met by the 213 recovery-lag rows.

---

## Backlog-Suppression Flag

| Option | Description | Selected |
|--------|-------------|----------|
| Verify metric semantics first | Researcher confirms whether `backlog_suppressed_delta` is a real per-event distress counter or a per-cycle/window artifact before it influences the verdict. | ✓ |
| Treat as real signal | Accept the flag at face value; weight toward a tune/code verdict even though refractory shows 0%. | |
| Exclude from decision | Disregard the flag entirely; rely only on recovery-lag and refractory-active metrics. | |

**User's choice:** Verify metric semantics first
**Notes:** Captured as D-02. The ~14451 value is near-identical across all five ATT tests (0% refractory active), which strongly smells like a per-cycle/window counter artifact. Resolve by reading the counter source + the 213 classifier, not by capturing new data.

---

## Phase 197 Status

| Option | Description | Selected |
|--------|-------------|----------|
| 197 = de-facto resolution | Treat Phase 197 as the implemented answer; 216 validates it against 213 evidence and closes as resolved-by-197 unless evidence contradicts. | ✓ |
| Re-evaluate split design | The thread's original split dl_cake detection/arbitration design is still open on its merits; weigh pursuing it as a code-design phase. | |
| Verify 197 deployed | Confirm 197 code is running on live production before framing. | |

**User's choice:** 197 = de-facto resolution
**Notes:** Captured as D-03. Verified during discussion that 197's split-semantics (`ARBITRATION_REASON_QUEUE_DURING_REFRACTORY` / `RTT_FALLBACK_DURING_REFRACTORY`) is live in `src/wanctl/wan_controller.py:101-102`. 197 took a different route than the thread's original split-cake candidate; thread was never updated, hence stale-open.

---

## Deliverable

| Option | Description | Selected |
|--------|-------------|----------|
| Decision report + thread close | `216-REPORT.md` with evidence-cited verdict, update thread to closed, mark RECOV-01/02/03; seed follow-up phase if code/tune needed. | ✓ |
| Report + ADR | Same report plus a formal ADR in docs/ for the long-term refractory-semantics decision. | |
| Lightweight close | Brief decision note appended to the thread file only; no separate report. | |

**User's choice:** Decision report + thread close
**Notes:** Captured as D-04. Mirrors operator-first closeout style of 212/213/214/215 reports.

---

## Claude's Discretion

- Exact report structure, whether the artifact check (D-02) is a standalone step or folded into the evidence review, thread-close wording, and scoping of any seeded follow-up phase — all planner discretion, provided D-01..D-06 hold.

## Deferred Ideas

- ATT cake-primary canary todo (`2026-04-24-...`) — reviewed, not folded: active validation canary requiring an ATT mode switch + flent load, conflicts with passive-only D-01, gated on Phase 191 closure.
- Post-hotpath cycle-budget profiling todo (`2026-04-15-...`) — reviewed, not folded: Phase 217 owns it.
- Active refractory provocation — considered and rejected in favor of passive 213 baseline.
- Original `dl_cake_for_detection`/`dl_cake_for_arbitration` split design — superseded by Phase 197 unless shown insufficient.
