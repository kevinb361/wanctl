---
id: SEED-007
status: resolved
selected_for: v1.54
planted: 2026-05-26
planted_during: v1.44 closeout — `/gsd-review-backlog` triage of pending todos
trigger_when: v1.45+ milestone planning
scope: Small-Medium
priority: 6
prerequisites: []
priority_rationale: "Storage-axis work, independent of control-surface seeds (002–005) and hardware-axis SEED-006. Safe to plan in parallel. Internal sequencing: Phase A (flat-gauge fire-on-change) is straightforward and shippable independently; Phase B (CAKE tin skip-on-unchanged) is gated on a consumer audit that determines whether the optimization is safe."
sources:
  - .planning/todos/completed/2026-04-17-audit-autorate-flat-gauge-fire-on-change.md
  - .planning/todos/completed/2026-04-17-cake-tin-skip-on-unchanged-consumer-audit.md
  - "Steering precedent: commit 9b78ac3 (fire-on-change for `wanctl_steering_enabled` eliminated ~172k rows/day)"
---

# SEED-007: Storage hygiene — flat-gauge fire-on-change + CAKE tin skip-on-unchanged

Previously labeled T6 / T7 in v1.45+ deferred items. Migrated from two pending todos (`2026-04-17-audit-autorate-flat-gauge-fire-on-change.md` and `2026-04-17-cake-tin-skip-on-unchanged-consumer-audit.md`) during 2026-05-26 backlog triage. Two sequential phases delivering metric write-rate reductions on the per-WAN DBs.

## Why This Matters

The `wanctl_steering_enabled` fire-on-change pattern (commit `9b78ac3`) eliminated ~172k rows/day of redundant continuous emission on the steering daemon. The same pattern likely applies to several boolean/categorical gauges in the autorate services (`wanctl@spectrum`, `wanctl@att`) — and a larger optimization (CAKE tin metrics skip-on-unchanged) is available behind a consumer audit gate.

Per-WAN DBs sit at ~310 MB each today; net potential of the two phases combined is ~30-40% reduction in per-WAN DB write volume. Small, cumulative wins.

## When to Surface

**Trigger:** v1.45+ milestone planning. Independent of in-flight control-surface seeds — can plan in parallel with SEED-003/004/005 and SEED-006.

**Internal sequence:** Phase A (autorate flat-gauge audit + fire-on-change) is shippable independently. Phase B (CAKE tin skip-on-unchanged) is gated on a consumer audit; if any consumer needs continuous sampling, Phase B is either deferred or the consumer is fixed first.

## Scope Estimate

**Small-Medium** across two phases.

### Phase A — Autorate flat-gauge fire-on-change audit (Small)

For each per-WAN DB, run the same profile applied to steering:
- per-metric-name COUNT over last 60s
- identify metrics emitting at 2Hz / 20Hz with near-zero value variance

Candidates to investigate (not pre-verified):
- `wanctl_fusion_bypass_active`
- `wanctl_irtt_asymmetry_direction`
- `wanctl_state` (may legitimately change often; likely not a candidate)
- anything else emitting at ~2 rows/sec of mostly-flat values

For each confirmed candidate, apply the steering pattern:
- Instance attr `self._last_<metric>_emitted: float | None = None` in init path
- Skip `append` to batch if value unchanged
- Always emit on first call (cache is None)

Unit tests using the `SimpleNamespace`-based pattern in `tests/steering/test_steering_metrics_recording.py::TestSteeringEnabledFireOnChange`.

Deploy carefully — one change at a time, watch for missed-emission regressions via canary + soak.

Tool available since 2026-05-16: `wanctl-history --ingestion-rate --wan <wan>` (v1.44 Phase 208 TOOL-02) provides per-metric rows/sec measurement before and after each change.

### Phase B — CAKE tin skip-on-unchanged (Medium, gated)

`wanctl_cake_tin_dropped` and `wanctl_cake_tin_ecn_marked` are zero the vast majority of cycles on a quiet link. Skipping when unchanged could save 10-15 rows/sec per WAN — substantially larger than the steering_enabled win.

**Gating audit (must complete before code change):**
1. `grep` the repo + docs for every read of `wanctl_cake_tin_*` — CLI tools, dashboard queries, flent post-processing, anything.
2. For each consumer, determine whether it queries:
   - `last-value-before-T` → sparse-series OK, optimization safe
   - `COUNT(*) over window` → continuous-series required, optimization unsafe
3. If all consumers are last-value-style → ship the skip-on-unchanged with the same cache-per-key pattern as `steering_enabled` (but per-tin per-direction).
4. If any consumer needs continuous sampling → either skip Phase B or fix the consumer first.

This changes the data shape from continuous-series to sparse-series — the audit is the load-bearing work; the code change is small once cleared.

## Out of Scope

- Generic schema migration for historic data — only emission-side changes.
- Read-side compaction or vacuum scheduling — separate concern.
- Cross-WAN aggregation logic — Phase A/B preserve per-WAN topology established in v1.36/v1.37.

## Open Questions for Plan Phase

- **Phase A:** profile output format — keep the ad-hoc per-metric-name COUNT script, or add a dedicated `wanctl-history --metric-distribution` subcommand? (`--ingestion-rate` already gives totals; the distribution view would surface flat-gauge candidates programmatically.)
- **Phase A:** rollout cadence — one candidate per canary cycle (safest), or batch related candidates (faster, harder to attribute regressions)?
- **Phase B:** if the consumer audit finds one consumer needing continuous sampling, does fixing that consumer belong in this seed or split off?
- **Both:** soak duration — typically 24h post-change, or shorter for storage-only changes with no control-loop impact?

## Recommended Defaults (carry into plan phase unless changed)

- Tool: `wanctl-history --ingestion-rate --wan <wan>` for pre/post measurement
- Cadence: one candidate per canary cycle in Phase A; full pre-flight audit before any Phase B code change
- Rollback gate: emission rate of changed metric returns to pre-change levels (regression) OR downstream consumer query fails (missing data)
- Test pattern: `SimpleNamespace`-based fire-on-change tests modeled on `test_steering_metrics_recording.py::TestSteeringEnabledFireOnChange`

## Reference

- `commit 9b78ac3` — steering_enabled fire-on-change precedent
- `tests/steering/test_steering_metrics_recording.py::TestSteeringEnabledFireOnChange` — test pattern
- `src/wanctl/history.py:438-489` — `--ingestion-rate` formatters (v1.44 Phase 208 TOOL-02)
