# Phase 217: Production Cycle-Budget Baseline - Context

**Gathered:** 2026-05-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Capture at least one hour of live cycle-budget profiling on a representative
production WAN, attribute per-cycle cost across the instrumented subsystems
(RTT measurement, CAKE stats, router communication, logging/metrics, storage
writes), then **close or promote** the pending todo
`2026-04-15-profile-post-hotpath-baseline-on-production-wan` and explicitly
decide whether performance work is deprioritized in favor of quality/tuning.

**This is a measurement + decision phase, not an optimization phase.** No
control-path, threshold, or algorithm changes. Optimization only happens later,
and only if the data promotes the todo to a follow-on phase.

Requirements: PERF-01, PERF-02, PERF-03 (locked by REQUIREMENTS.md + ROADMAP).

</domain>

<decisions>
## Implementation Decisions

### Target WAN
- **D-01:** Profile **Spectrum only**. It is the active quality-concern link
  for the v1.46 milestone, live on `1.45.0` with the v1.44 `besteffort wash`
  CAKE topology. One clean profile from the link we actually care about beats a
  dual-WAN capture that doubles risk surface on the 24/7 loop. ATT (DSL,
  diffserv4) is a different transport and not the milestone subject.

### Load Conditions
- **D-02:** Capture **~1h organic household traffic** (steady-state budget)
  **plus a short driven RRUL/upload segment** using the Phase 213 baseline
  harness. Rationale: most subsystem costs are per-cycle constant, but
  `autorate_router_write_*` cost spikes only on rate change (flash-wear guard),
  so a quiet household would under-sample the router-write path. The driven
  segment exercises that path; the organic window establishes representative
  steady-state.

### Reference Baseline (judging "healthy")
- **D-03:** Judge against **absolute health bars**, not the todo's original
  v1.39-era comparison. Primary bars: (a) `autorate_cycle_total` headroom
  vs the 50ms cycle budget, and (b) the structural dominance test — **no single
  subsystem >40% of `autorate_cycle_total`**.
- **D-04:** **Drop the unanchored ±15% / ±25%-vs-v1.39 clauses** from the todo's
  close conditions. No concrete v1.39-era cycle-budget number was ever committed
  as data (only "implied by the original todo's framing"), so that comparison is
  unfalsifiable. The planner should honor the absolute-bar framing instead.
  Archived v1.0 / v1.9 profiling artifacts (see canonical refs) may be cited as
  **informational context only** if cheap to extract — not as a pass/fail gate.

  > **Close-condition reinterpretation (explicit):** the todo's conditions 1 and
  > 2 partition on the historical comparison. Under D-03/D-04 the partition
  > becomes: **no-action** if cycle_total has comfortable 50ms headroom AND no
  > subsystem >40%; **promote** if either a subsystem exceeds 40% or total
  > headroom is thin. Condition 3 (folded into a broader perf/observability
  > phase) is unchanged.

### Capture & Safety
- **D-05:** Enable `--profile` via a **systemd override drop-in** (not a
  permanent edit to `deploy/systemd/wanctl@.service`). Clean enable → ≥1h
  capture → revert drop-in → restart. The `--profile` flag is already wired in
  `src/wanctl/autorate_continuous.py:295`.
- **D-06:** Commit the artifact to
  `.planning/perf/v1.45-baseline-spectrum-<date>.profile.json` (create the
  `.planning/perf/` dir) plus a **1-page summary** stating which close-condition
  outcome applies and the deprioritize/promote decision (PERF-03).
- **D-07:** **Create the missing `docs/PROFILING.md`** runbook. The todo lists it
  in its `files:` block but it does not exist; this phase should leave a durable
  enable/capture/revert/analyze procedure so the next profiling pass is
  repeatable.

### Claude's Discretion
User answered "what do you think" to all four gray areas — the recommended
option was locked for each (D-01 through D-07). The planner/researcher have
flexibility on: exact driven-segment duration, the analysis script invocation
(`scripts/analyze_profiling.py`), summary format, and whether to quantify the
profiling observer-effect inline or as a noted caveat.

### Folded Todos
- **`2026-04-15-profile-post-hotpath-baseline-on-production-wan`** — this todo
  IS the phase. Its close-condition partition is the phase's exit gate, as
  reinterpreted by D-03/D-04. The phase closes the todo (no-action) or promotes
  it (optimization phase) per the captured data.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase contract
- `.planning/todos/pending/2026-04-15-profile-post-hotpath-baseline-on-production-wan.md` — the phase's exit gate; close-condition partition (read D-03/D-04 for the reinterpretation that overrides its ±15% clauses)
- `.planning/ROADMAP.md` §"Phase 217" — goal + 4 success criteria
- `.planning/REQUIREMENTS.md` — PERF-01, PERF-02, PERF-03

### Profiling tooling (existing)
- `src/wanctl/perf_profiler.py` — profiler core; label→`*_ms` conversion
- `src/wanctl/autorate_continuous.py:295,494` — `--profile` CLI flag wiring + apply-to-all-controllers
- `src/wanctl/health_check.py:128-135,265` — canonical subsystem label set (`autorate_rtt_measurement`, `autorate_cake_stats`, `autorate_logging_metrics`, `autorate_router_communication`, `autorate_cycle_total`)
- `src/wanctl/wan_controller.py:2435-2447` — per-subsystem timing emission (incl. `router_apply_primary/pending`, `router_write_download/upload`)
- `scripts/profiling_collector.py` — log → profiling-data collection
- `scripts/analyze_profiling.py` — subsystem cost breakdown / analysis
- `docs/PROFILING.md` — **DOES NOT EXIST YET; create per D-07**

### Load-driving harness
- Phase 213 (`.planning/phases/213-experience-baseline-harness/`) — RRUL / upload / download baseline runbook to drive the under-load segment (D-02)

### Archived baselines (informational only, per D-04)
- `.planning/milestones/v1.0-phases/01-measurement-infrastructure-profiling/PROFILING-ANALYSIS.md`
- `.planning/milestones/v1.9-phases/47-cycle-profiling-infrastructure/47-RESEARCH.md`

### Operator tooling referenced by the todo rescope
- `wanctl-history --ingestion-rate --wan <wan>` (v1.44 Phase 208) — per-metric write-rate, useful for storage-write attribution

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Full profiling stack already exists (`perf_profiler.py`, collector, analyzer,
  `--profile` flag). This phase consumes it — it should not need to build new
  instrumentation.
- Phase 213 harness drives the under-load segment without new tooling.

### Established Patterns
- Hot-path profiling is gated: per-cycle debug/profiling payload construction is
  skipped when DEBUG/profile is off (the original todo's optimization). Enabling
  `--profile` re-activates that path → inherent **observer-effect**; research
  should note/quantify it so the captured budget isn't read as steady-state
  cost-with-profiling-off.
- Router writes are change-gated (flash-wear: `last_applied_dl/ul_rate`), which
  is exactly why D-02 adds a driven segment.

### Integration Points
- `.planning/perf/` is a new artifact dir (does not exist).
- `docs/PROFILING.md` is a new runbook (does not exist).
- No `src/` control-path changes expected — measurement + docs + artifacts only.

</code_context>

<specifics>
## Specific Ideas

- Current production version is **1.45.0** (`pyproject.toml`,
  `src/wanctl/__init__.py`). The todo says "1.44.0" and root `CLAUDE.md` says
  "1.43.0" — both stale. Artifacts and summary should be labeled **v1.45**.
- Artifact naming: `.planning/perf/v1.45-baseline-spectrum-<date>.profile.json`.

</specifics>

<deferred>
## Deferred Ideas

- **Any actual optimization** (RTT-path restructuring, per-cycle metrics/logging
  allocation, router/transport cost reduction) is explicitly out of scope. If
  the data promotes the todo, that work becomes a v1.46+ optimization phase.
- **ATT cycle-budget profile** — not captured this phase (Spectrum-only per
  D-01). Open a separate pass if DSL-path budget later becomes a concern.

</deferred>

---

*Phase: 217-production-cycle-budget-baseline*
*Context gathered: 2026-05-29*
