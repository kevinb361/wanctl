# Phase 217 Cycle-Budget Summary

Spectrum `1.45.0` was captured from `2026-05-29T23:43:16Z` to `2026-05-30T00:44:16Z` using live `journalctl` streaming after a short rehearsal proved the path. The canonical profile artifact is `.planning/perf/v1.45-baseline-spectrum-20260529.profile.json` with `71560` `Cycle timing` records. The driven segment ran `tcp_upload` and `rrul` from `2026-05-30T00:13:16Z` to `2026-05-30T00:16:37Z`; `router_write_coverage` is `present`.

## Cycle Budget

Bar: `passes_headroom = cycle_total.avg_ms < 40.0 AND cycle_total.p99_ms < 50.0`.

| Metric | Value |
|--------|-------|
| `cycle_total.avg_ms` | `2.883` |
| `cycle_total.p99_ms` | `6.9` |
| `headroom_avg_ms` | `47.117` |
| `utilization_pct` | `5.766` |
| `passes_headroom` | `true` |

## Subsystem Dominance

Bar: `passes_dominance = max(category_pct.values()) < 40.0`.

| Category | Avg ms | Percent of cycle total |
|----------|--------|------------------------|
| RTT measurement | `0.039` | `1.35%` |
| CAKE stats | `0.175` | `6.07%` |
| Router communication | `0.013` | `0.45%` |
| Logging / metrics | `0.238` | `8.26%` |

Dominant category: `logging_metrics` at `8.26%`. `passes_dominance = true`.

Router category uses `autorate_router_communication` only; `autorate_router_apply_*` and `autorate_router_write_*` are child sub-timers and would double-count if summed.

## Storage Attribution

Storage is unmeasured in this dev checkout: `.venv/bin/python -m wanctl.history --ingestion-rate --wan spectrum --from 2026-05-29T23:43:16Z --to 2026-05-30T00:44:16Z --json` could not find the production metrics database. The committed artifact `.planning/perf/v1.45-baseline-spectrum-20260529.ingestion.json` records this as a structured `unmeasured` result with the explicit window bounds.

Storage writes have no hot-path label by design. Storage percent of `cycle_total` is undefined and is not asserted.

## Observer Effect

Adjacent `/health` windows were collected. OFF-window average `cycle_budget.cycle_time_ms.avg` was `0.70ms`; ON-window average was `3.02ms`; `observer_effect_ms = 2.32ms`. The ON window was captured under `--debug` with JSON emission, so the profiled `cycle_total` is still treated as the authoritative upper-bound budget artifact.

This is not a same-window `/health`-vs-DEBUG delta. Same-window comparison would be near zero by construction because both reads come from the same in-process profiler stats.

## Historical Context

Archived v1.0 was RTT-dominant at a 2s interval, and v1.9 expected roughly 30-45ms at the 50ms cadence. Per D-04, these are informational context only and not a pass/fail gate. The original +/-15% and +/-25%-vs-v1.39 clauses are dropped as unfalsifiable because no concrete v1.39-era number was committed.

## Verdict

Rule: `no_action` if `passes_headroom AND passes_dominance`; `promote` otherwise.

Verdict: `no_action`. Both `passes_headroom` and `passes_dominance` are true, and `router_write_coverage` is `present`, so the no-action verdict is unconditional for this Phase 217 baseline.

## Decision

Performance work is deprioritized in favor of quality/tuning work.

Artifacts: `.planning/perf/v1.45-baseline-spectrum-20260529.profile.json`, `.planning/perf/v1.45-baseline-spectrum-20260529.ingestion.json`, and `.planning/perf/217-capture-window.json`.
