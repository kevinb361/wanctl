# Phase 121: Core Hysteresis Logic - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Add dwell timer and deadband margin to QueueController's state machine to prevent GREEN/YELLOW oscillation at the EWMA threshold boundary during peak DOCSIS load. Both download (4-state) and upload (3-state) protected.

</domain>

<decisions>
## Implementation Decisions

### Rate Behavior During Dwell
- **D-01:** Hold rates steady when delta exceeds threshold but dwell counter hasn't expired. No preemptive decay. Matches the spike detector confirmation pattern (_spike_streak). If congestion is real, dwell expires in 150ms (3 cycles at 50ms) and YELLOW kicks in normally.

### Dwell Scope
- **D-02:** Dwell gates GREEN→YELLOW transitions only. RED remains immediate (1 sample). SOFT_RED keeps its existing `soft_red_required` sustain counter. The flapping lives at the target_bloat boundary — heavy congestion (SOFT_RED/RED deltas) must bypass dwell for fast response.

### Deadband Direction
- **D-03:** Asymmetric deadband — applies only to YELLOW→GREEN recovery. GREEN→YELLOW entry uses `target_bloat_ms` as-is. YELLOW→GREEN recovery requires delta < (target_bloat_ms - deadband_ms). This prevents boundary oscillation without delaying congestion detection.

### Counter Behavior
- **D-04:** Dwell counter resets to zero when delta drops below threshold mid-dwell (per HYST-03). Only uninterrupted consecutive above-threshold cycles trigger YELLOW.

### Scope Consistency
- **D-05:** Both `adjust()` (3-state, upload) and `adjust_4state()` (4-state, download) get identical dwell/deadband logic. The dwell counter (`_yellow_dwell`) lives on QueueController as an instance variable, one per direction.

### Claude's Discretion
- Implementation details of counter variable naming and method signatures
- Whether to extract hysteresis logic into a helper method or keep inline in adjust/adjust_4state

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### State Machine
- `src/wanctl/autorate_continuous.py` lines 1325-1560 — QueueController class with adjust() and adjust_4state() methods (the exact code being modified)
- `src/wanctl/autorate_continuous.py` lines 1694-1698 — _spike_streak / accel_confirm pattern (reference implementation for confirmation counters)

### Configuration
- `src/wanctl/autorate_continuous.py` lines 376-462 — `_load_threshold_config()` where new params will be loaded
- `src/wanctl/check_config.py` — Config validation (needs accel_confirm_cycles pattern for new params)

### Production Data
- `CHANGELOG.md` unreleased section — 44h validation record documenting EWMA boundary oscillation pattern (the problem this phase solves)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_spike_streak` / `accel_confirm` counter pattern: exact same concept (count consecutive occurrences before acting). Proven in production since 2026-03-28.
- `soft_red_required` sustain counter: same concept applied to SOFT_RED state transitions. Both are prior art for dwell timers.

### Established Patterns
- QueueController owns all state transition logic — dwell counter naturally goes here
- Streak counters (`green_streak`, `red_streak`, `soft_red_streak`) are instance variables on QueueController
- Threshold values are loaded in `_load_threshold_config()` and stored as Config attributes
- `adjust()` and `adjust_4state()` have parallel structure — changes should mirror each other

### Integration Points
- `QueueController.__init__()` — add dwell_cycles and deadband_ms params (or read from config)
- `QueueController.adjust()` — add dwell counter check at GREEN→YELLOW transition (line ~1391)
- `QueueController.adjust_4state()` — add dwell counter check at GREEN→YELLOW transition (line ~1499)
- Both methods' GREEN→YELLOW recovery check — add deadband margin to threshold comparison

</code_context>

<specifics>
## Specific Ideas

- Defaults (dwell_cycles=3, deadband_ms=3.0) chosen from tonight's production data: 3 cycles at 50ms = 150ms dwell, well within 500ms latency budget. Deadband of 3.0ms creates hysteresis band [target_bloat-3, target_bloat] which prevents oscillation when delta hovers at 12ms (observed in 30+ transition events on 2026-03-30 at 10PM CDT).
- The existing `green_required` counter prevents rate INCREASES until sustained GREEN. The new dwell counter prevents state TRANSITION until sustained above-threshold. Different mechanisms for different problems.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 121-core-hysteresis-logic*
*Context gathered: 2026-03-31*
