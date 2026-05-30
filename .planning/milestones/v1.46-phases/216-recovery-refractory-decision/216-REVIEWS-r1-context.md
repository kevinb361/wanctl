---
phase: 216
reviewers: [codex]
reviewed_at: 2026-05-29
review_target: CONTEXT.md (pre-plan decision review — no plans exist yet)
plans_reviewed: []
---

# Cross-AI Review — Phase 216

> **Note:** Phase 216 has not been planned yet. This is an adversarial review of the
> CONTEXT.md *decision set* (the constraints for the upcoming plan), not a plan review.
> Codex independently read the source and ran the targeted tests during review.

## Codex Review

**Summary**

As written, the decision set is operationally reasonable but semantically overclaims.
Closing Phase 216 as "no new change; resolved by Phase 197" is probably the right
production-control call, but not because Phase 213 validated refractory behavior. Phase 213
mostly shows the refractory path was not exercised. The report should say that plainly:
current passive evidence shows no live recovery symptom, while Phase 197's code/tests and
prior post-197 validation are the actual basis for closing the stale thread.

**Strengths**

- Keeps Phase 216 decision-only. No tuning, RouterOS writes, restarts, or active congestion provocation.
- Correctly treats Phase 197 as shipped reality instead of re-litigating the stale Phase 196 candidate design.
- D-02 is the right gate: `backlog_suppressed_delta` must not drive a verdict until its source semantics are understood.
- Preserves the important Phase 160 invariant: refractory remains cascade-safety machinery.
- D-06 correctly avoids mixing stale steering threshold names into refractory conclusions.
- Verified the targeted tests still pass: `tests/test_phase_197_replay.py` + `tests/test_phase213_classify.py` = `21 passed`.

**Concerns**

- **HIGH:** Passive Phase 213 evidence does not validate refractory semantics.
  `pct_samples_refractory_active=0.0` means the relevant code path was not exercised. It
  supports "no current symptom under this baseline," not "refractory behavior is correct."

- **HIGH:** RECOV-03 is easy to overstate. "Recovery lag after transient congestion" requires
  an actual transient congestion episode. The 213 rows showing `time_to_green_after_red_sec=0.0`
  appear to be "no RED/SOFT_RED observed," not "RED recovered instantly." The 213 review already
  flagged that unrecovered RED could be recorded as zero lag — `213-REVIEW.md:69`.

- **MEDIUM:** "Validate Phase 197 against 213 evidence" is not meaningful for the
  refractory-active branch. The meaningful validation is Phase 197's tests and code path:
  `queue_during_refractory` / `rtt_fallback_during_refractory` in `src/wanctl/wan_controller.py:2879`,
  plus replay tests in `tests/test_phase_197_replay.py:208`.

- **MEDIUM:** The backlog artifact hypothesis is likely right, but it should be proven, not
  assumed. The classifier merges all `health-*.ndjson` files per target test window
  (`scripts/phase213-classify.py:98`), then computes `max-min` over cumulative counters
  (`scripts/phase213-classify.py:271`). The underlying counter increments on backlog-suppressing
  GREEN recovery, not refractory itself (`src/wanctl/queue_controller.py:265`).

- **MEDIUM:** A real refractory-only regression could still slip through if it only appears
  during rare drop-triggered events. Phase 197 tests reduce that risk; Phase 213 does not.

- **LOW:** The expected-landing language is a bit anchoring. "The verdict writes itself" should
  be replaced with explicit exit criteria.

**Suggestions**

- Reword D-01: "Use Phase 213 passive baseline to decide no new production capture is justified;
  do not claim it validates refractory-active semantics."
- Mark RECOV-03 carefully: satisfied for a no-change decision because no recovery/refractory
  tuning is being made; NOT satisfied as evidence for future tuning unless an actual
  transient/refractory event exists.
- Make D-03 validation source explicit: Phase 197 code/tests and existing post-197 evidence
  validate the shipped fix; Phase 213 only checks for current symptoms.
- In D-02, require the report to show the counter provenance: cumulative lifetime counter,
  per-WAN health files merged, `max-min` artifact risk, and whether any target-WAN-only per-file
  delta remains meaningful.
- Add reopen criteria to the thread closeout: reopen if natural production artifacts show
  `arb_refractory_active > 0` with RTT fallback, recovery lag, or throughput collapse.

**Risk Assessment**

**MEDIUM as written.** The likely verdict, "no new change / resolved by Phase 197," is
defensible. The weak part is the reasoning. If the report claims Phase 213 proves refractory
semantics, that is not sound. If it instead says Phase 213 shows no current symptom and Phase
197's code/tests are the semantic proof, the closeout risk drops to LOW-MEDIUM.

---

## Consensus Summary

Single reviewer (Codex). The verdict direction (close as no-change / resolved-by-197) is
endorsed; the **reasoning** needs tightening before it hardens into a plan.

### Agreed Strengths
- Decision-only posture (no control-path mutation) is correct and safe.
- Treating Phase 197 as shipped reality (not re-litigating the split-cake design) is right.
- D-02's "verify the backlog counter before it counts" gate is the correct discipline.

### Agreed Concerns (highest priority)
1. **(HIGH) Don't conflate "no symptom" with "validated."** Phase 213 had 0% refractory-active
   samples, so it cannot prove refractory semantics are correct — it only shows no live symptom
   under that baseline. The semantic proof is Phase 197's code + replay tests.
2. **(HIGH) `time_to_green_after_red_sec=0.0` is suspect.** It likely means "no RED observed,"
   not "instant recovery" — and `213-REVIEW.md:69` already warned unrecovered RED can log as
   zero lag. RECOV-03's "measured from production artifacts" bar is met *only* in the narrow
   sense that no tuning is being made; it is NOT satisfied as a basis for future tuning.
3. **(MEDIUM) Prove, don't assume, the backlog artifact.** Counter is cumulative lifetime,
   merged across per-WAN health files, deltized via `max-min`, and increments on
   backlog-suppressing GREEN recovery (not refractory). Show this provenance in the report.

### Divergent Views
None (single reviewer).

### Recommended actions before planning
- Tighten D-01 / D-03 wording to separate "no current symptom (213)" from "semantic proof (197)".
- Replace the "verdict writes itself" anchoring with explicit exit/reopen criteria.
- Add a thread reopen trigger: natural production event with `arb_refractory_active > 0` plus
  RTT fallback, recovery lag, or throughput collapse.
- Planner should read `213-REVIEW.md` (the zero-lag caveat at line 69) before relying on the
  recovery-lag rows.
