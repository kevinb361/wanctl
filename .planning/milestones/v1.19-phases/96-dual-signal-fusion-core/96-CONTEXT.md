# Phase 96: Dual-Signal Fusion Core - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Weighted combination of IRTT UDP RTT and icmplib ICMP RTT to produce a fused congestion control input that is more robust than either signal alone. The fused value replaces the ICMP-only filtered_rtt as input to update_ewma(). Weights are YAML-configurable with warn+default validation. When IRTT is unavailable or stale, fusion falls back to ICMP-only with zero behavioral change. This phase builds the fusion engine ONLY -- disabled-by-default gating, SIGUSR1 toggle, and health endpoint visibility are in Phase 97.

</domain>

<decisions>
## Implementation Decisions

### Default fusion weights
- Default **ICMP 0.7 / IRTT 0.3** -- ICMP remains dominant (20Hz vs 0.1Hz)
- IRTT provides a stabilizing cross-check, not a dominant signal
- Uses **raw IRTT rtt_mean_ms** directly -- no additional filtering (IRTT already averages across burst packets; Hampel is tuned for 50ms ICMP cadence)
- **Reuse latest IRTT value** between measurements -- cached value used for all ~200 cycles until next burst; staleness gate handles truly old values

### Staleness and fallback
- Stale defined as **IRTT age > 3x cadence** (existing gate, default 30s) -- same threshold for all IRTT consumers
- **Instant fallback** to ICMP-only when IRTT goes stale -- no gradual weight shift
- When IRTT is **completely disabled** (_irtt_thread is None), fusion is a **pure pass-through** -- filtered_rtt goes straight to update_ewma() unchanged, zero overhead
- **DEBUG logging** of fused_rtt alongside icmp_rtt and irtt_rtt for operator troubleshooting

### Weight configuration and validation
- **Single knob**: `fusion.icmp_weight: 0.7` in YAML -- IRTT weight derived as `1.0 - icmp_weight`
- Impossible for weights to not sum to 1.0 (one degree of freedom)
- **Invalid values** (outside 0.0-1.0): WARNING log + clamp to default 0.7
- Follows proven warn+default pattern from signal_processing, owd_asymmetry, reflector_quality configs

### Fusion insertion point
- Fusion happens **between** signal_processor.process() and update_ewma()
- `fused_rtt = icmp_weight * filtered_rtt + irtt_weight * irtt_rtt` when IRTT is fresh
- `fused_rtt = filtered_rtt` (pass-through) when IRTT stale/unavailable/disabled
- update_ewma(fused_rtt) replaces update_ewma(filtered_rtt)

### Claude's Discretion
- Internal class/module structure (inline in run_cycle vs separate FusionEngine class)
- Whether to compute fused_rtt in a method or inline
- How to structure the fusion YAML section (top-level `fusion:` vs nested under existing section)
- Test fixture design for mocking IRTT results at different staleness levels

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Fusion insertion point (CRITICAL)
- `src/wanctl/autorate_continuous.py` lines 2098-2110 -- The exact code path where signal_processor.process() feeds into update_ewma(). Fusion inserts HERE.
- `src/wanctl/autorate_continuous.py` lines 2152-2169 -- IRTT result read and staleness gate in run_cycle(). Fusion needs this IRTT data.

### IRTT infrastructure
- `src/wanctl/irtt_thread.py` -- IRTTThread with lock-free caching; get_latest() returns cached IRTTResult
- `src/wanctl/irtt_measurement.py` -- IRTTResult frozen dataclass with rtt_mean_ms field

### Signal processing pipeline (must preserve)
- `src/wanctl/signal_processing.py` -- SignalProcessor.process() returns SignalResult with filtered_rtt; fusion uses this output
- `src/wanctl/autorate_continuous.py` line 2110 -- Current: `self.update_ewma(signal_result.filtered_rtt)` -- fusion modifies this line

### Configuration patterns
- `src/wanctl/autorate_continuous.py` -- Config loading patterns (_load_irtt_config, _load_owd_asymmetry_config, _load_reflector_quality_config) -- model for fusion config

### EWMA and congestion control (DO NOT MODIFY)
- `src/wanctl/autorate_continuous.py` -- update_ewma() method, download.adjust_4state(), upload.adjust() -- these consume the fused RTT but must NOT be changed

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `IRTTThread.get_latest()`: Lock-free cache read returning latest IRTTResult -- source of IRTT RTT for fusion
- `SignalProcessor.process()`: Returns SignalResult with filtered_rtt -- source of ICMP RTT for fusion
- `_load_*_config()` pattern: Proven config loading with warn+default validation -- template for fusion config

### Established Patterns
- **Staleness gate**: `age <= cadence * 3` check already used for protocol correlation and asymmetry analysis
- **Warn+default config**: Invalid values produce WARNING and fall back to defaults (never crash)
- **Signal flow**: raw_rtt -> signal_processor -> filtered_rtt -> update_ewma() -> load_rtt -> state machine
- **Lock-free caching**: Frozen dataclass + GIL pointer swap for thread-safe IRTT reads

### Integration Points
- `WANController.run_cycle()` line 2110: THE integration point -- replace `signal_result.filtered_rtt` with `fused_rtt`
- `WANController.__init__()`: Where fusion config and state variables would be initialized
- Config loading in `_load_specific_fields()`: Where `_load_fusion_config()` would be added

</code_context>

<specifics>
## Specific Ideas

No specific requirements -- open to standard approaches following existing patterns

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 96-dual-signal-fusion-core*
*Context gathered: 2026-03-18*
