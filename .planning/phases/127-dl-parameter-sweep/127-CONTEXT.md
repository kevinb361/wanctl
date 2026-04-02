# Phase 127: DL Parameter Sweep - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

A/B test all 9 download parameters sequentially on linux-cake transport using RRUL flent methodology. Each winner applied before the next test. Document results with metrics delta and test conditions.

Parameters (in test order):
1. factor_down_yellow: 0.92 vs 0.97
2. green_required: 3 vs 5
3. step_up_mbps: 10 vs 15
4. factor_down (RED): 0.85 vs 0.90
5. dwell_cycles: 3 vs 5
6. deadband_ms: 3.0 vs 5.0
7. target_bloat_ms: 9 vs 12 vs 15
8. warn_bloat_ms: 30 vs 45 vs 60
9. hard_red_bloat_ms: 60 vs 80 vs 100

</domain>

<decisions>
## Implementation Decisions

### Test ordering
- **D-01:** Same order as the original REST-transport sweep: response factors first (factor_down_yellow, green_required, step_up, factor_down), then timing (dwell_cycles, deadband_ms), then thresholds (target_bloat_ms, warn_bloat_ms, hard_red_bloat_ms). Enables direct comparison with original (invalidated) results.

### Test conditions
- **D-02:** Run ASAP — no waiting for specific time window. Document time of day with each test result for context.
- **D-03:** 1 RRUL run per value (2 runs per A/B pair). If delta is <5%, re-run both to confirm. Adaptive approach balances speed with confidence on close calls.

### Results documentation
- **D-04:** Document results in existing docs/CABLE_TUNING_GUIDE.md. Add new section "## linux-cake Transport Results (2026-04)" with same A/B table format as original REST results. Original results stay as historical record (marked invalidated for linux-cake).

### Config change method
- **D-05:** YAML edit + SIGUSR1 on VM. SSH to cake-shaper, edit spectrum.yaml, send SIGUSR1 to reload config. Same method validated in Phase 126 gate check. Clean and auditable.

### Test methodology
- **D-06:** Sequential and cumulative — each winner applied before next test begins. This explores a path through parameter space rather than testing in isolation.
- **D-07:** RRUL flent against Dallas netperf server (104.200.21.31). Standard methodology from original sweep.
- **D-08:** Start with current production values as baseline. These may or may not be optimal on linux-cake.

### Claude's Discretion
- Exact flent command-line flags and test duration
- How to structure the A/B results tables in the tuning guide
- Whether to include raw flent data paths in the documentation

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Tuning methodology
- `docs/CABLE_TUNING_GUIDE.md` — Existing A/B test results (REST transport, invalidated), table format, parameter descriptions
- `.planning/todos/pending/2026-04-02-retest-all-params-linux-cake.md` — Full parameter list with current production values and pre-test checklist

### Transport and config
- `docs/CONFIG_SCHEMA.md` — Configuration reference for all tunable parameters
- `docs/TRANSPORT_COMPARISON.md` — REST vs linux-cake transport differences

### Prior test results (for comparison)
- Memory files: feedback_factor_down_yellow_092.md through feedback_hard_red_60_validated.md — original A/B results per parameter (REST transport)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/check-tuning-gate.sh` — Gate check script from Phase 126, confirms environment is valid
- `wanctl-benchmark` CLI — RRUL flent orchestration with grading, result storage, comparison

### Established Patterns
- SIGUSR1 reload: `sudo kill -USR1 $(pgrep -f 'autorate_continuous.*spectrum')`
- Config path: `/etc/wanctl/spectrum.yaml` (sudo required)
- Health endpoint: `http://127.0.0.1:9101/health` on VM
- flent test against Dallas: `flent rrul_be -H 104.200.21.31 -l 60`

### Integration Points
- SSH to cake-shaper VM: `ssh kevin@10.10.110.223`
- Config edit + SIGUSR1 = live parameter change without restart
- flent runs from dev machine or VM (network path to Dallas server)

</code_context>

<specifics>
## Specific Ideas

- Parameters 7-9 (threshold trio) are 3-way tests, not 2-way — need 3 runs each
- Original sweep had decisive deltas for most params (2x latency differences). Expect similar clarity on linux-cake, but feedback loop is faster so timing params (dwell, deadband) might behave differently
- Cable plant is afternoon-loaded right now — document conditions, don't wait for off-peak
- Router CAKE RTT was found at 25/30ms during gate check (residual from prior testing). Now irrelevant since router CAKE is disabled, but worth noting if results seem anomalous

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

### Reviewed Todos (not folded)
- "Re-test ALL tuning parameters on linux-cake transport" — parent todo for whole milestone, covers this phase
- "RRUL A/B tuning sweep for ATT WAN" — out of scope, ATT is separate WAN
- "Post-tuning audit findings" — operational findings, not DL sweep scope

</deferred>

---

*Phase: 127-dl-parameter-sweep*
*Context gathered: 2026-04-02*
