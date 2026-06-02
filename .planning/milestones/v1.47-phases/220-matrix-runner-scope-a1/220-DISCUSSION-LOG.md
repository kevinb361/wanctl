# Phase 220: Matrix Runner (Scope A1) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-30
**Phase:** 220-matrix-runner-scope-a1
**Areas discussed:** Kill / defect thresholds, Replicate count + matrix budget, Matrix verdict roll-up algorithm, Wave 0 fixture strategy

---

## Kill Threshold (CRITERIA-01 kill criteria)

| Option | Description | Selected |
|--------|-------------|----------|
| REQ example as-is | Canonical control p99 ≤ 200ms on ≥ 2/3 windows AND zero supplemental cell exceeds 1.5× control p99 across all windows. Matches REQUIREMENTS.md example and Phase 214 anchor. | ✓ |
| Moderate (loosen the ratio) | Control p99 ≤ 250ms on ≥ 2/3 windows AND supplemental p99 ≤ 1.75× control. Tolerates noisier control + wider supplemental tail. | |
| Permissive | Control p99 ≤ 300ms on ≥ 2/3 windows AND supplemental p99 ≤ 2× control. Easier to kill. | |

**User's choice:** "you decide" → Claude selected REQ example as-is.
**Notes:** Tight thresholds prevent judgment leakage from Phase 214's already-seen 606/560ms anchor. Aligns with the pre-registration discipline in CRITERIA-01.

---

## Defect Threshold (CRITERIA-01 defect criteria)

| Option | Description | Selected |
|--------|-------------|----------|
| REQ example as-is | ≥ 1 supplemental cell p99 > 500ms reproduced across ≥ 2 windows + corroborating driver in {reflector_loss, loss, queue_delay}. Matches REQUIREMENTS.md verbatim. | ✓ |
| Stricter — catastrophic-only | ≥ 1 supplemental cell p99 > 700ms + same corroboration. Closer to historical >1000ms catastrophic signal. | |
| Looser — sensitivity-biased | ≥ 1 supplemental cell p99 > 400ms + same corroboration. More false-positive risk. | |
| REQ example + restrict drivers to {loss, queue_delay} only | Excludes `reflector_loss` from corroborating driver set. Avoids re-labeling reflector noise as Spectrum defect. | |

**User's choice:** "you decide" → Claude selected REQ example as-is.
**Notes:** `reflector_loss` stays in the corroborating-driver allowlist because the matrix-level orthogonal-corroboration rule (CLOSEOUT-01) already discriminates reflector-side-only loss from path-side loss across the cube.

---

## Per-Window p99 Measurement

| Option | Description | Selected |
|--------|-------------|----------|
| Median of replicate p99s | Robust to single-replicate outliers. Matches "reproduced" intent. | ✓ |
| Max of replicate p99s | Sensitive but high false-positive risk. | |
| Pooled p99 across replicates | Statistically cleanest; loses replicate-level "reproduced" information. | |
| ≥ 50% of replicates exceed threshold | Encodes "reproduced" at replicate level; awkward at N=2. | |

**User's choice:** "you decide on all" → Claude selected Median of replicate p99s.
**Notes:** MWU + bootstrap CI uses pooled per-second samples (n ≈ 90 per cell), separate from the threshold-comparison statistic. Two independent rollup statistics serve different decision surfaces.

---

## Replicate Count + Matrix Budget

| Option | Description | Selected |
|--------|-------------|----------|
| N = 3 replicates × 30s flent × 60s spacing | Matches Phase 214 anchor flent duration; 54 runs total; 27 min per window slot. | ✓ (Claude discretion) |

**User's choice:** "you decide on all" → Claude selected the above as the operational anchor for Phase 221.
**Notes:** 3 replicates is the minimum to (a) support `median-of-replicates` rollup with N>2 odd, (b) pool ≈ 90 per-second samples per cell for MWU/bootstrap power, and (c) keep per-window slot load under 30 minutes including inter-cell spacing. Phase 221 operator load = 54 runs across 3 time-of-day windows.

---

## Matrix Verdict Roll-Up Algorithm

| Option | Description | Selected |
|--------|-------------|----------|
| Three-step roll-up (per-cell → per-axis → matrix) with mandatory orthogonal corroboration for `defect_located`; canonical separated from supplemental | Encodes CLOSEOUT-01 "no single-cell defect without orthogonal corroboration" rule. Canonical control reported on its own row, NEVER pooled with supplemental in MWU. | ✓ (Claude discretion) |

**User's choice:** "you decide on all" → Claude selected the above.
**Notes:** Orthogonal corroboration = path-orthogonal OR target-orthogonal OR driver-orthogonal. Verdict decision tree is pre-registered in CONTEXT.md and frozen at first live cell run.

---

## Wave 0 Fixture Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Hybrid: reuse Phase 214 `.flent.gz` for unchanged chain; craft NEW synthetic per-cell fixtures for aggregator surface | Pin two MWU p-values + bootstrap CI bounds with seeded `random.Random(220)`, B=2000. Five rollup paths covered. | ✓ (Claude discretion) |
| Reuse Phase 214 fixtures only | Faster but doesn't exercise canonical-vs-supplemental separation or multi-window cube rollup. | |
| Craft all-new fixtures | Better signal but re-tests stable upstream surface. | |

**User's choice:** "you decide on all" → Claude selected Hybrid.
**Notes:** Don't re-test what isn't changing. The aggregator is the novel surface; pinning real `.flent.gz`-derived MWU outputs adds determinism noise without testing aggregator-specific logic.

---

## Claude's Discretion

- Exact YAML schema layout for `phase220-matrix.yaml` — extension of Phase 214 per-window YAML pattern.
- Per-cell sidecar manifest schema — extend Phase 214 sidecar with cube discriminator fields.
- MWU two-sided normal-approximation tie-handling — Wilcoxon mid-rank tie correction.
- Bootstrap percentile CI corner cases (degenerate inputs) — return `degenerate: true` rather than crash.
- Aggregator JSON `schema_version: 1` (Phase 219 D-17 convention).
- `base_sha` set at Phase 220 plan-commit time via `git rev-parse HEAD`.
- `mtr` snapshots: per-cell pre-flight; post-flight only on detected path change.
- `random.Random(220)` bootstrap seed — thematic, documented.

## Deferred Ideas

- Aggregator visualization (heat-map / sparkline output).
- Auto-rotating supplemental target pool (anti-feature).
- DSCP marking probe (anti-feature, scope-drift risk).
- Cube projection to additional axes (time-of-day-hour, weekday, weather, RouterOS uptime).
- `mtr` path-change auto-replan.
- Multi-protocol matrix (UDP_FLOOD, tcp_1up, RRUL).
- ML/prediction for next-best-target (anti-feature).

## Reviewed Todos (not folded)

- `2026-04-17-operator-summary-digest-permission-handling` — unrelated tooling hygiene.
- `2026-04-17-investigate-steering-degraded-on-clean-restart` — out of scope for v1.47 read-only milestone.
- `2026-04-17-monitor-flapping-peak-count-on-next-docsis-event` — Phase 218 watch-list item; parallel to v1.47.
- `2026-04-24-resolve-att-cake-primary-canary-after-phase-196` — gated on Phase 191 closure; unrelated.
- `2026-04-28-add-silicom-bypass-nic-operational-tooling`, `2026-04-28-add-silicom-bypass-test-harness` — SEED-006 dormant; out of scope.
