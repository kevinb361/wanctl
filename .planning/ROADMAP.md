# Roadmap: wanctl

## Milestones

- 🚧 **v1.49 Spectrum DSCP Tinning Re-evaluation** — active (Phases 225–228; read-only DSCP survival trace → Spectrum-only `diffserv4 wash` A/B → evidence-gated verdict; negative result is a valid close)
- ✅ **v1.48 Steering Runtime Drift Closure** — shipped 2026-06-03 (Phases 222–224; live steering daemon aligned `1.39 → 1.47` in production, canary kept_aligned, SAFE-12 held) — `milestones/v1.48-ROADMAP.md`
- ✅ **v1.47 Measurement Evidence Closure** — shipped 2026-06-02 (Phases 219–221; 18/18 REQs satisfied; `tcp_12down` closed-with-prejudice per CRITERIA-02) — `milestones/v1.47-ROADMAP.md`
- ✅ **v1.46 Internet Quality Recovery** — shipped-with-deferral 2026-05-30 (Phases 212–217; VERIFY-01/02 carried to Phase 218 event-gated watch-list) — `milestones/v1.46-ROADMAP.md`
- ✅ **v1.45 Flapping Peak-Counter Window Repair** — shipped-with-deferral 2026-05-27 (Phases 210–211; VERIFY-01 deferred → rolled into Phase 218) — `milestones/v1.45-phases/`
- ✅ **v1.44 Topology-Correct CAKE — Spectrum besteffort wash migration** — shipped 2026-05-26 (Phases 205–209) — `milestones/v1.44-ROADMAP.md`
- ✅ **v1.43 UL Suppression Metrics & Gate Calibration** — shipped 2026-05-13 — `milestones/v1.43-ROADMAP.md`
- ✅ **v1.42 DOCSIS-Aware UL Congestion Control** — shipped 2026-05-06 — `milestones/v1.42-ROADMAP.md`
- ✅ **v1.41 Per-Direction Control Surfaces** — closed 2026-05-04 (gaps_found) — `milestones/v1.41-ROADMAP.md`
- ✅ **v1.40 Queue-Primary Signal Arbitration** — shipped 2026-05-03 — `milestones/v1.40-ROADMAP.md`
- ✅ **v1.39 Control-Path Timing & Measurement Accounting** — shipped 2026-04-24 (operator waiver; archived 2026-05-06 gaps_found) — `milestones/v1.39-ROADMAP.md`
- 📁 **v1.0 — v1.38** — see `MILESTONES.md` for the full historical index

> v1.48 full phase detail, success criteria, and REQ coverage archived to `milestones/v1.48-ROADMAP.md`. Delivered: git-history drift audit → offline replay/spine proof → production canary aligning the live steering daemon `1.39 → 1.47` (kept_aligned, SAFE-12 held at phase boundary and milestone close). 12 plans, 11/11 REQs.

---

## Active Milestone: v1.49 Spectrum DSCP Tinning Re-evaluation

**Goal:** Re-test whether per-tin `diffserv4 wash` CAKE earns its keep on Spectrum now that end-to-end DSCP plumbing exists (CRS hardware QoS trust, Ruckus QoS mirroring, cake-shaper bridge pre-CAKE classification) — confirming or overturning the v1.44 "classification theater" decision (fulfilled seed SEED-001) with fresh evidence under the current topology. A negative result — keep `besteffort wash` — closes the milestone cleanly (v1.46/v1.47 evidence-milestone precedent).

**Thesis origin:** Pending todo `2026-06-03-retest-spectrum-diffserv4-wash-after-local-qos-changes` (`area: validation`). The load-bearing premise of SEED-001 ("ISPs strip DSCP, the shaper sees unmarked ingress, so diffserv4 is theater") may no longer hold after local QoS posture changed. v1.49 first proves whether marks survive to CAKE ingress, then — only if they do — runs the A/B.

**Scope:** Two-thread single thesis — (1) read-only DSCP survival trace as a gated precondition, (2) Spectrum-only `diffserv4 wash` A/B with pre-registered accept/rollback gates. SEED-005 (UL tuning), SEED-007 (storage hygiene), and `/gsd-cleanup` orphan sweep are explicitly out of scope. Phase 218 (v1.45 VERIFY watch-list) continues event-gated in parallel and is not a v1.49 driver. RECLAIM-04 carried indefinitely. The `diffserv4 nowash` experiment is out of v1.49 (only a later follow-up if `wash` clearly wins).

**Hard constraints (immutable across this milestone):**
- **ATT byte-identical the entire milestone** — different carrier (DSL, not DOCSIS), different DSCP behavior; the Spectrum finding does not generalize. Spectrum-only A/B.
- **External network gear (CRS / Ruckus / router) is NOT mutated in-milestone** — the DSCP trace is read-only by operator decision; landing marks correctly via gear config is a separate operator-approved action outside v1.49.
- **The cake-shaper bridge nftables rules (wanctl-owned deploy) MAY change** — they are in-scope deploy surface, not external gear.
- **A negative result (keep `besteffort wash`) is a valid milestone close** — no success criterion forces shipping `diffserv4`.

**SAFE-13 invariant (cross-cutting, verified at every phase boundary):**
Controller-path source — `wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, `alert_engine.py`, fusion — remains zero-diff vs v1.48 close through the audit + evidence phases. The tin-agnostic CAKE signal + `allow_wash` gate already shipped in v1.44 Phase 205, so the controller can already drive `diffserv4 wash`; the A/B is expected to be a config (`configs/spectrum.yaml`) + validation exercise, not an algorithm change. **Any lift of SAFE-13 is an explicit, evidence-gated roadmap decision made inside Phase 228 — only if the A/B proves a control-path change is warranted. Default expectation: zero controller-path diff.** Same discipline that held SAFE-07/08/09/11/12 through v1.43–v1.48. ATT config remains byte-identical the entire milestone.

### Phases

**Phase Numbering:** Continues from v1.48 last phase (224). v1.49 starts at Phase 225.

- [ ] **Phase 225: DSCP Survival Trace** — Read-only end-to-end trace of where DSCP is set / preserved / stripped (CRS trust maps → Ruckus QoS mirroring → cake-shaper bridge → CAKE ingress), the observed DSCP distribution at Spectrum CAKE ingress under representative + deliberately-marked (EF) traffic, and a gated verdict: marks survive (proceed to A/B) or marks don't (early-exit confirming v1.44).
- [ ] **Phase 226: Baseline Capture + Threshold Lock + Snapshot A** — Snapshot A rollback anchor, full baseline evidence on the current `920/18 besteffort wash`, and pre-registered GATE-01 accept/rollback thresholds locked before any candidate deploy. Gated on a "marks survive" verdict from Phase 225.
- [ ] **Phase 227: Candidate diffserv4-wash Deploy + Matched Capture** — Spectrum-only `diffserv4 wash` (DL+UL) deployed under the Snapshot A anchor, with the identical evidence set captured under matched load plus a realtime-flow protection comparison (marked EF UDP vs unmarked UDP vs unmarked bulk TCP).
- [ ] **Phase 228: Verdict + Evidence-Gated Decision + Closeout** — Verdict computed against the locked GATE-01 thresholds; explicit accept/reject decision; the evidence-gated SAFE-13-lift call; rollback to `besteffort wash` with Snapshot A restoration if any trigger fires; closeout recorded in `docs/BRIDGE_QOS.md`, `configs/spectrum.yaml`, and `CHANGELOG.md`.

### Phase Details

#### Phase 225: DSCP Survival Trace

**Goal:** Operator can read a complete, read-only, evidence-backed picture of whether DSCP marks survive the current end-to-end path to Spectrum CAKE ingress — and gets a gated verdict that either short-circuits the A/B (marks don't survive → v1.44 confirmed, milestone can close negative) or unblocks it (marks survive → proceed to Phase 226). Read-only / evidence phase — no external network-gear mutation, no production CAKE-mode change.
**Depends on:** Nothing (first v1.49 phase). Re-opens fulfilled seed SEED-001's load-bearing premise; builds on v1.28 Phase 141 bridge DSCP classification and `docs/BRIDGE_QOS.md`.
**Requirements:** DSCP-01, DSCP-02, DSCP-03, SAFE-13 (cross-phase invariant)
**Success Criteria** (what must be TRUE):
  1. Operator can read a documented trace identifying where DSCP is set / preserved / stripped across CRS trust maps → Ruckus QoS mirroring → cake-shaper bridge → CAKE ingress, captured read-only with zero external network-gear (CRS / Ruckus / router) mutation.
  2. Operator can see the actual DSCP distribution arriving at Spectrum CAKE ingress under representative traffic AND under a deliberately marked (EF) flow, establishing whether marks reach the shaper.
  3. Operator gets a gated DSCP-03 verdict: if marks do NOT survive to CAKE ingress, an early-exit finding ("diffserv4 remains classification theater — v1.44 confirmed") that short-circuits the A/B as unnecessary and lets the milestone close negative; if marks DO survive, an explicit "proceed to A/B" gate that unblocks Phase 226.
  4. No external network gear is mutated and no Spectrum CAKE-mode change is deployed in this phase — trace and capture only.
  5. SAFE-13 verified at phase boundary: zero controller-path source diff vs v1.48 close (`wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, `alert_engine.py`, fusion all byte-identical); ATT config byte-identical.
**Plans:** 1/3 plans executed

#### Phase 226: Baseline Capture + Threshold Lock + Snapshot A

**Goal:** Operator can establish a reversible, fully-instrumented starting line before any production CAKE-mode change: a Snapshot A rollback anchor capturing Spectrum config + production CAKE/qdisc state, a complete baseline evidence set on the current `920/18 besteffort wash`, and a pre-registered set of GATE-01 accept/rollback thresholds locked at plan time (v1.44/v1.47 "thresholds locked before deploy" discipline). Gated on a Phase 225 "marks survive" verdict — if DSCP-03 early-exited, this phase does not run and the milestone closes negative.
**Depends on:** Phase 225 (conditional — proceeds only on a "marks survive to CAKE ingress" verdict; a DSCP-03 early-exit short-circuits to milestone close).
**Requirements:** AB-01, AB-02, GATE-01, SAFE-13 (cross-phase invariant)
**Success Criteria** (what must be TRUE):
  1. Operator captures a Snapshot A rollback anchor (Spectrum config + production CAKE/qdisc state) before any production change, restorable to the exact pre-A/B state (v1.44 / v1.46 Phase 215 precedent).
  2. Operator captures baseline evidence on the current `920/18 besteffort wash`: `tc -s qdisc` on spec-router and spec-modem, per-tin counters/drops/backlog/delay under load, Spectrum health/state, and RRUL/flent latency-under-load.
  3. Operator has pre-registered GATE-01 accept/rollback thresholds locked before any candidate deploy: RRUL p99 latency regression tolerance (per the v1.44 rollback gate, >5%), daemon restart-rate, pressure-state transition-rate, upload stability, and useful non-BestEffort tin separation — recorded in a committed artifact so the verdict cannot be reverse-fitted.
  4. No candidate `diffserv4 wash` is deployed in this phase — baseline + anchor + locked thresholds only; the candidate deploy is reserved for Phase 227.
  5. SAFE-13 verified at phase boundary: zero controller-path source diff vs v1.48 close; ATT config byte-identical.
**Plans:** TBD

#### Phase 227: Candidate diffserv4-wash Deploy + Matched Capture

**Goal:** Operator can deploy candidate `diffserv4 wash` (download + upload) on Spectrum only under the Snapshot A anchor and capture the identical evidence set under matched load, plus a realtime-flow protection comparison, so the verdict in Phase 228 has a direct apples-to-apples baseline-vs-candidate dataset.
**Depends on:** Phase 226 (Snapshot A captured, baseline evidence recorded, GATE-01 thresholds locked).
**Requirements:** AB-03, AB-04, SAFE-13 (cross-phase invariant)
**Success Criteria** (what must be TRUE):
  1. Operator can deploy candidate `diffserv4 wash` on Spectrum only (DL+UL), ATT untouched, and capture the identical evidence set as Phase 226 (`tc -s qdisc` on spec-router/spec-modem, per-tin counters/drops/backlog/delay under load, Spectrum health/state, RRUL/flent latency-under-load) under matched load for direct comparison.
  2. Operator can compare realtime-flow protection between baseline and candidate: marked EF UDP jitter vs unmarked UDP, plus unmarked bulk-TCP throughput and latency distribution (degrades to best-effort capture if the test rig cannot mark cleanly, but the check is not dropped).
  3. The candidate is deployed via config (`configs/spectrum.yaml`) + the existing `allow_wash` gate / tin-agnostic CAKE signal (v1.44 Phase 205) — no controller algorithm change is required to drive `diffserv4 wash`.
  4. SAFE-13 verified at phase boundary: zero controller-path source diff vs v1.48 close; ATT config byte-identical. The cake-shaper bridge nftables rules MAY change; controller path MUST NOT.
**Plans:** TBD

#### Phase 228: Verdict + Evidence-Gated Decision + Closeout

**Goal:** Operator gets a verdict computed against the pre-registered GATE-01 thresholds, an explicit accept/reject decision, an evidence-gated decision on whether a controller-path change (SAFE-13 lift) is warranted, a clean rollback to `besteffort wash` with Snapshot A restoration if any trigger fires, and a recorded closeout. Either outcome — accept `diffserv4 wash` or keep `besteffort wash` — is a valid milestone close.
**Depends on:** Phase 227 (matched baseline-vs-candidate evidence captured).
**Requirements:** GATE-02, GATE-03, SAFE-13 (cross-phase invariant)
**Success Criteria** (what must be TRUE):
  1. Operator gets a GATE-02 verdict computed against the locked GATE-01 thresholds: accept `diffserv4 wash` (clear latency/jitter or realtime-protection win with no throughput loss, daemon instability, or pressure-state churn) or reject in favor of `besteffort wash`.
  2. Operator gets an explicit, evidence-gated SAFE-13 decision: whether the A/B evidence warrants any controller-path change (e.g. per-tin backlog weighting in `cake_signal.py`). Default and expected outcome is NO lift — zero controller-path diff — and any lift is recorded as a deliberate roadmap decision with evidence rationale, not a pre-committed edit.
  3. If any GATE-01 rollback trigger fires (RRUL p99 regression beyond tolerance, higher restart rate, more pressure-state churn/flapping, upload instability, or no useful non-BestEffort tin separation), Spectrum is rolled back to `besteffort wash` and BOTH production and repo are verified restored to Snapshot A.
  4. The closeout records the verdict in `docs/BRIDGE_QOS.md`, `configs/spectrum.yaml`, and `CHANGELOG.md`, including the negative-result path (keep `besteffort wash`) as a valid close.
  5. SAFE-13 verified at phase boundary AND at v1.49 milestone close: zero controller-path source diff vs v1.48 close unless an explicit evidence-gated lift was recorded in criterion 2; ATT config byte-identical the entire milestone.
**Plans:** TBD

### Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 225. DSCP Survival Trace | 1/3 | In Progress|  |
| 226. Baseline Capture + Threshold Lock + Snapshot A | 0/? | Not started | - |
| 227. Candidate diffserv4-wash Deploy + Matched Capture | 0/? | Not started | - |
| 228. Verdict + Evidence-Gated Decision + Closeout | 0/? | Not started | - |

### Coverage

All 13 v1.49 REQ-IDs map cleanly. SAFE-13 is a cross-phase invariant verified at every phase boundary and at milestone close (matching SAFE-07/08/09/11/12 precedent through v1.43–v1.48).

| Phase | REQ-IDs |
|-------|---------|
| 225 | DSCP-01, DSCP-02, DSCP-03, SAFE-13 (cross-phase) |
| 226 | AB-01, AB-02, GATE-01, SAFE-13 (cross-phase) |
| 227 | AB-03, AB-04, SAFE-13 (cross-phase) |
| 228 | GATE-02, GATE-03, SAFE-13 (cross-phase) |

**Coverage:** 13/13 REQ-IDs mapped. No orphans, no duplicates. DSCP (3) + AB (4) + GATE (3) + SAFE-13 (1, cross-phase on all four). The DSCP-03 verdict in Phase 225 is a conditional gate: a "marks don't survive" early-exit short-circuits Phases 226–228 and closes the milestone negative (v1.44 confirmed).

---

## Backlog

### Parallel (event-gated)

- **Phase 218 (v1.45 VERIFY watch-list)** — VERIFY-01 / VERIFY-02 still event-gated on natural production DOCSIS flapping event with `details.peak_transition_count > 30`. No synthetic event generation per inherited ROADMAP constraint. Runs parallel to v1.49; not a v1.49 driver.

### Deferred (post-v1.49 candidates)

- **RECLAIM-04** — Spectrum upload reclaim re-attempt with fundamentally different probe shape. Carried indefinitely after Phase 215 bounded VOID exhaustion; not v1.49.
- **diffserv4 nowash experiment** — only a later follow-up IF `diffserv4 wash` clearly wins and there is an explicit reason to preserve DSCP propagation beyond cake-shaper. Out of v1.49.
- **SEED-005** — Conservative UL tuning sweep. Dormant; separate thesis.
- **SEED-006** — Silicom bypass tooling + harness. Dormant.
- **SEED-007** — Storage hygiene fire-on-change. Dormant; separate thesis.

### Out of Scope for v1.49 (single-thesis discipline)

- **ATT (any change)** — different carrier (DSL, not DOCSIS), different DSCP behavior; the Spectrum finding does not generalize. ATT stays byte-identical.
- **External network gear mutation (CRS / Ruckus / router)** — v1.49 trace is read-only by operator decision; landing marks correctly via gear config is a separate operator-approved action.
- **Controller algorithm/threshold changes** — frozen under SAFE-13 unless A/B evidence forces an explicit Phase 228 roadmap decision.
- **SEED-005 / SEED-007 / `/gsd-cleanup` orphan quick-task sweep + operator-summary digest permission handling** — housekeeping / separate theses, not this thesis.
