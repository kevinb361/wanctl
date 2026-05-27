# Phase 214: Measurement Collapse Investigation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-05-27
**Phase:** 214-measurement-collapse-investigation
**Areas discussed:** Todo folding, Matrix bounds, Evidence correlation, Flent parser gap, Signal disposition

---

## Todo Folding

| Option | Description | Selected |
|--------|-------------|----------|
| tcp_12down only | Fold the mapped bad-p99/measurement-collapse todo; leave unrelated steering, flapping, ATT canary, and profiling items deferred. | yes |
| tcp + steering | Also fold steering clean-restart drift as context, even though Phase 212/213 found no raw steering counter movement. | |
| All matches | Fold every matched todo, including low-score profiling and unrelated watch-list/canary items. | |
| None | Do not fold todo content into this context. | |

**User's choice:** you decide
**Notes:** Chose the narrow default. The `tcp_12down` todo is explicitly mapped to Phase 214 in ROADMAP/REQUIREMENTS. Other matched todos belong to Phase 216, 217, 218, or later steering/canary work.

---

## Matrix Bounds

| Option | Description | Selected |
|--------|-------------|----------|
| Three Spectrum windows | Off-peak, daytime, and prime-time Spectrum `tcp_12down`, one valid run each; optional retry only for invalid artifacts. | yes |
| Full dual-WAN matrix | Run all windows on both Spectrum and ATT. | |
| Single fresh rerun | Run one current `tcp_12down` and close if clean. | |

**User's choice:** you decide
**Notes:** Selected the bounded reproduction matrix from the folded todo and ROADMAP success criteria. ATT remains optional contrast evidence, not a full parallel investigation.

---

## Evidence Correlation

| Option | Description | Selected |
|--------|-------------|----------|
| Full aligned correlation | Require flent p50/p95/p99, throughput, health NDJSON, measurement quality, reflector misses, protocol divergence, steering snapshots, and logs for the same window. | yes |
| Health plus flent only | Use flent and `/health` rows without log/steering correlation. | |
| Logs first | Use journal/log evidence as the primary explanation surface. | |

**User's choice:** you decide
**Notes:** Selected full aligned correlation because the active question is why daemon-state GREEN can coexist with bad user-visible p99.

---

## Flent Parser Gap

| Option | Description | Selected |
|--------|-------------|----------|
| Fix first | Build/fix Phase 214 `.flent.gz` latency extraction before interpreting p99 evidence. | yes |
| Reuse Phase 213 zeros | Treat Phase 213 signal-sheet p99/median fields as sufficient. | |
| Manual summaries only | Rely on operator-readable flent summaries instead of machine-readable extraction. | |

**User's choice:** you decide
**Notes:** Selected fix first. Phase 213 emitted `flent_p99=0.0`/`flent_median=0.0`, so downstream planning must not treat those as real latency percentiles.

---

## Signal Disposition

| Option | Description | Selected |
|--------|-------------|----------|
| Observational first | If reproduced, propose health/degraded-signal or alert semantics first; no controller behavior change in Phase 214. | yes |
| Control candidate | Let Phase 214 design a control-path response if collapse reproduces. | |
| No new signal | Only document findings; never propose a new degraded signal. | |

**User's choice:** you decide
**Notes:** Selected observational first because MEAS-03 says any new degraded-measurement signal is observational unless evidence proves it should affect control decisions.

---

## Claude's Discretion

- User delegated both todo folding and gray-area discussion with "you decide".
- Defaults chosen prioritize stability, bounded production load, source-bound reproducibility, and evidence before behavior changes.

## Deferred Ideas

- Steering clean-restart reproduction remains deferred unless Phase 214 evidence newly implicates steering.
- v1.45 flapping peak-count watch-list remains Phase 218 and should not be induced.
- ATT cake-primary/canary work remains outside Phase 214.
- One-hour cycle-budget profiling remains Phase 217.
