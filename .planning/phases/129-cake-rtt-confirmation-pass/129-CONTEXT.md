# Phase 129: CAKE RTT + Confirmation Pass - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Two activities:
1. Test CAKE rtt parameter (50ms vs 100ms) on linux-cake transport
2. Confirmation re-test of ALL 7 changed parameters with full winner set active, checking for interaction effects

</domain>

<decisions>
## Implementation Decisions

### Methodology (inherited from Phases 127-128)
- **D-01:** Same RRUL flent methodology, YAML + SIGUSR1, Dallas netperf server
- **D-02:** 1 run per value, re-test if <5% delta
- **D-03:** Document results in docs/CABLE_TUNING.md and 127-DL-RESULTS.md

### CAKE rtt test
- **D-04:** Test CAKE rtt 50ms vs 100ms. This is a CAKE scheduler parameter (not a wanctl controller parameter). Changed via `cake_params` section in spectrum.yaml or directly via `tc qdisc change`.
- **D-05:** Router CAKE RTT residuals (25/30ms found during gate check) are irrelevant — router CAKE is disabled. Only testing VM's local CAKE rtt.

### Confirmation pass scope
- **D-06:** Re-test ALL 7 changed parameters (6 DL + 1 UL), not just the DL response group. Full scope because thresholds shifted dramatically (9→15, 45→60, 60→100).
- **D-07:** Parameters to re-test (each as A/B with current winner vs original loser):
  - DL green_required: 3 vs 5
  - DL step_up_mbps: 10 vs 15
  - DL factor_down: 0.85 vs 0.90
  - DL target_bloat_ms: 15 vs 9
  - DL warn_bloat_ms: 60 vs 45
  - DL hard_red_bloat_ms: 100 vs 60
  - UL step_up_mbps: 2 vs 1

### Confirmation pass criteria
- **D-08:** If a winner flips during confirmation (original loser now wins with all params active), KEEP THE NEW WINNER. The full-set result is more authoritative than the isolated test since that's how production runs.

### Claude's Discretion
- CAKE rtt config location (cake_params section vs tc command)
- Order of confirmation re-tests
- Whether to run CAKE rtt test before or after confirmation pass

</decisions>

<canonical_refs>
## Canonical References

### Prior phase results
- `.planning/phases/127-dl-parameter-sweep/127-DL-RESULTS.md` — DL + UL sweep results
- `.planning/phases/127-dl-parameter-sweep/127-CONTEXT.md` — Full methodology
- `.planning/phases/128-ul-parameter-sweep/128-CONTEXT.md` — UL context

### CAKE rtt context
- `docs/CONFIG_SCHEMA.md` — cake_params configuration reference
- `feedback_router_cake_rtt_residual.md` — Router CAKE RTT residuals from prior testing (now irrelevant)

</canonical_refs>

<code_context>
## Existing Code Insights

### CAKE rtt configuration
- `cake_params` section in spectrum.yaml controls CAKE scheduler parameters
- CAKE rtt affects the AQM target delay — lower = more aggressive queue management
- Current production CAKE rtt: 50ms (need to verify)

### Established Patterns
- Same SSH + sed + SIGUSR1 + flent workflow from Phases 127-128

</code_context>

<specifics>
## Specific Ideas

- CAKE rtt is fundamentally different from controller params — it's a kernel scheduler setting, not wanctl logic
- The confirmation pass is ~14 flent runs (7 params × 2 values each)
- CAKE rtt test is 2 runs
- Total: ~16 flent runs, ~20-25 minutes
- If any winner flips during confirmation, that changes the final config for Phase 130

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 129-cake-rtt-confirmation-pass*
*Context gathered: 2026-04-02*
