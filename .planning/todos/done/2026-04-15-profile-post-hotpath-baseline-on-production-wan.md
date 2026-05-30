---
created: 2026-04-15T08:36:10.231Z
title: Profile post-hotpath baseline on production WAN
area: performance
files:
  - docs/PROFILING.md
  - scripts/profiling_collector.py
  - scripts/analyze_profiling.py
  - src/wanctl/perf_profiler.py
  - src/wanctl/cake_stats_thread.py
  - src/wanctl/wan_controller.py
---

## Problem

Recent hot-path work reduced controller overhead by:
- skipping per-cycle debug formatting and profiling payload construction when DEBUG is off
- collapsing background CAKE stats reads to one netlink dump per cycle
- sizing the RTT background worker pool to configured reflector count

Those changes were verified in repo tests, but there is not yet a fresh production measurement showing how much `autorate_cycle_total` moved or whether RTT measurement still dominates the budget. The next optimization step should be based on live profiling from an active production WAN rather than assumptions.

## Solution

Run a controlled production profiling pass on one representative WAN:
- enable `--profile` on `wanctl@<wan>.service`
- collect at least one hour of logs
- extract and compare `autorate_cycle_total`, `autorate_rtt_measurement`, `autorate_router_communication`, `autorate_logging_metrics`, and `autorate_cake_stats`
- disable the override after collection

Use the result to decide whether the next safe optimization target is:
- per-cycle metrics/logging allocation in `_run_logging_metrics()`
- RTT-path restructuring
- router update path / transport cost

## Rescope — 2026-05-26

Original framing is stale. This todo was filed against a small hot-path change in mid-April 2026. Since then, v1.40 → v1.44 shipped substantial control-surface evolution that all runs on the same 50ms cycle budget:

- **v1.40 Phase 197** — queue-primary refractory semantics (split `dl_cake_for_detection` from `dl_cake_for_arbitration`); fusion-healer bypass alignment
- **v1.41 Phase 200** — per-direction RTT bloat thresholds + Spectrum yellow-decay clamp
- **v1.42 Phase 201** — DOCSIS-aware UL congestion control + bounded RED decay
- **v1.44 Phase 207** — fail-closed source-diff verifier (control-loop unchanged but verification added)
- **v1.44 Phase 208** — `wanctl-history --ingestion-rate` (new operator tooling available for instrumentation)

The right question now is: **what is the production cycle budget after the full v1.40 → v1.44 evolution, and where are the new hot-path costs?** Run `--profile` against current `1.44.0` on one representative WAN for ≥1 hour, compare against the v1.39-era baseline implied by this todo's original framing, and decide which subsystem to optimize next.

New tooling available since this todo was filed:
- `wanctl-history --ingestion-rate --wan <wan>` (v1.44 Phase 208) — per-metric write-rate measurement
- `signal_arbitration` /health block (v1.40) — exposes queue-primary vs RTT-secondary attribution
- Refractory arbitration metric (v1.40 Phase 197) — refractory-window visibility

Pending. May be promoted to a v1.45+ performance baseline phase if the production measurement reveals a substantive optimization target.

### Close conditions (added 2026-05-26 per peer-review feedback)

This todo closes when one of these is true:

1. **Baseline captured + no action needed.** A `--profile` artifact of ≥1 hour from production `1.44.0` on one representative WAN is committed under `.planning/perf/` (path TBD) with subsystem cost breakdown. **All three** must hold: (a) overall budget within ±15% of the v1.39-era cycle budget implied in the original todo, (b) no single subsystem accounts for >40% of `autorate_cycle_total`, (c) no individual subsystem regressed by >25% vs the v1.39-era contribution. Outcome: filed as reference data, no follow-on phase needed.

2. **Baseline captured + optimization target identified.** Same artifact, but **any** of: (a) one subsystem accounts for >40% of cycle budget, (b) overall budget regressed by >15% from v1.39-era baseline, (c) any individual subsystem regressed by >25%. Promote to a v1.45+ optimization phase targeting the subsystem flagged by whichever clause tripped; this todo closes when the phase is opened.

3. **Superseded by a broader observability/perf phase.** If a v1.45+ phase is scoped that includes ≥1h production profiling as a constituent task, this todo is folded into that phase and closed.

Conditions 1 and 2 partition the outcome space (no dead zone): if all three "no action" sub-conditions hold, condition 1 closes; otherwise at least one clause of condition 2 trips and closes via promotion.

Concrete artifacts: `.planning/perf/v1.44-baseline-<wan>-<date>.profile.json` (or equivalent) + a 1-page summary noting whether one of conditions 1-3 applies.

## Closed — 2026-05-30 (Phase 217)

Phase 217 captured the production Spectrum `1.45.0` cycle-budget baseline and closed this todo as no-action under the D-04 absolute-bar reinterpretation.

Measured result: `cycle_total.avg_ms = 2.883`, `cycle_total.p99_ms = 6.9`, dominant category `logging_metrics = 8.26%`, `max_category_pct = 8.26%`. The driven segment landed and `router_write_coverage` is `present`.

The Phase 217 partition supersedes the original +/-15% and +/-25%-vs-v1.39 clauses because no concrete v1.39-era baseline number was committed. The active bars were `cycle_total.avg_ms < 40.0`, `cycle_total.p99_ms < 50.0`, and `max(category_pct) < 40.0`; all passed.

Reference: `.planning/perf/217-cycle-budget-summary.md` and `.planning/perf/v1.45-baseline-spectrum-20260529.profile.json`.
