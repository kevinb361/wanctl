# Feature Landscape: WAN-Aware Steering

**Domain:** Multi-signal WAN failover steering (local queue health + end-to-end path quality)
**Researched:** 2026-03-08
**Overall confidence:** HIGH (well-understood domain, existing codebase thoroughly documented)

## Executive Summary

WAN-aware steering adds autorate's end-to-end WAN RTT state (GREEN/YELLOW/SOFT_RED/RED) as a secondary signal to steering's existing CAKE-based congestion assessment. The gap being closed: CAKE queue stats can show GREEN (local shaping succeeds, no drops, low queue) while the ISP path is degraded upstream of the shaper. Autorate already detects this via RTT delta measurement against frozen baseline. Steering currently ignores it.

The feature landscape is well-bounded. Industry SD-WAN systems universally combine local queue health with end-to-end path metrics. The question is not whether to combine signals but how to weight them and what hysteresis to apply. wanctl already has all the infrastructure: JSON state file sharing, confidence scoring, sustain timers, flap detection, and configurable YAML thresholds.

## Table Stakes

Features users expect. Missing = the milestone delivers no value or creates dangerous gaps.

| Feature | Why Expected | Complexity | Dependencies |
|---------|--------------|------------|-------------|
| Autorate exports dl_state to state file | Steering cannot read what autorate does not write. Currently `save_state()` writes streaks and EWMA but not the computed zone. | Low | 3-line change in `WANController.save_state()` -- `dl_zone` and `ul_zone` are already in scope from `run_cycle()` |
| Steering reads WAN state from autorate state file | Core data flow for the entire milestone | Low | Extend existing `BaselineLoader` (already reads same file for `ewma.baseline_rtt`) to also extract `congestion.dl_state` |
| Map autorate 4-state to confidence weight | Translate GREEN/YELLOW/SOFT_RED/RED into additive contribution to the confidence score | Low | Add weight constants to existing `ConfidenceWeights` class in `steering_confidence.py` alongside existing CAKE-state weights |
| Sustained WAN RED triggers failover | Transient RED must not trigger steering; sustained confirmation required (~1s = 20 cycles at 50ms) | Low | Existing `TimerManager.update_degrade_timer()` already implements sustain countdown; WAN RED just boosts confidence above `steer_threshold` |
| Sustained WAN GREEN allows recovery | Recovery must verify WAN is healthy, not just CAKE queue | Low | Existing `TimerManager.update_recovery_timer()` already checks `cake_state == "GREEN"` and `rtt_delta < 10.0`; add WAN state to recovery eligibility |
| CAKE stats remain primary signal | WAN state is secondary/amplifying -- CAKE RED alone can still trigger steering; WAN RED alone cannot | Low | Architectural constraint enforced by weight values. Existing `ConfidenceWeights.RED_STATE = 50` is near threshold (55). WAN RED adds on top; never overrides. |
| Configurable WAN state weights in YAML | Production tuning without code changes | Low | Pattern established: `confidence:` section in `configs/steering.yaml` has all threshold params; add `wan_state:` subsection |
| Staleness guard on autorate state file | If autorate daemon crashes or state file is stale (>5min), WAN signal must be ignored (not assumed GREEN) | Low | `BaselineLoader._check_staleness()` already implements this exact pattern for baseline RTT; replicate for WAN state reads |
| Backward compatibility | Old steering must work if autorate state file lacks `congestion` key (pre-upgrade) | Low | `state.get("congestion", {}).get("dl_state", None)` -- None means "no WAN signal, use CAKE only" |

## Differentiators

Features that improve the system beyond basic signal combination. Valued but not blocking.

| Feature | Value Proposition | Complexity | Dependencies |
|---------|-------------------|------------|-------------|
| WAN SOFT_RED as intermediate signal | Autorate SOFT_RED means "RTT elevated 45-80ms but not catastrophic." Smaller confidence boost enables earlier detection of building congestion before full RED. | Low | Add `WAN_SOFT_RED_WEIGHT` (10-15 points) to `ConfidenceWeights`; autorate 4-state model already distinguishes SOFT_RED from RED |
| Health endpoint exposes WAN state | Operators see what autorate reports, what steering reads, staleness, and whether WAN signal influenced the last decision | Low | Extend `SteeringHealthHandler._get_health_status()` with `wan_state: {source_state, weight_contribution, staleness_seconds}` |
| Structured log for WAN signal reads | Every cycle logs WAN state read result with staleness, contribution, and confidence impact | Low | Add to existing `[CONFIDENCE]` log line format in `compute_confidence()` |
| Grace period on startup | Autorate needs cycles to establish baseline; WAN state should be untrusted for first N seconds after steering daemon starts | Low | Simple monotonic-clock check: ignore WAN signal until `uptime > startup_grace_sec` (configurable) |
| Asymmetric sustain timers for WAN vs CAKE | WAN RED may need longer sustain than CAKE RED (WAN probes measure full ISP path, more variable); recovery from WAN-triggered failover may need to be slower | Medium | New timer fields: `wan_degrade_sustain_sec`, `wan_recovery_sustain_sec`; risk of complexity from two timer sets |
| RTT delta exported in autorate state | Steering could use autorate's raw RTT delta directly for supplementary scoring without recomputing | Low | Already computed as `load_rtt - baseline_rtt`; add to autorate state file as convenience field |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| WAN state overrides CAKE state | Violates "CAKE is primary" architecture. CAKE has ground truth about local queue. WAN RTT can spike from unrelated causes (ISP routing changes, probe path issues). Override creates false positives. | WAN state amplifies confidence score additively. CAKE RED (50) + WAN RED (25) = 75 > threshold. CAKE GREEN (0) + WAN RED (25) = 25 < threshold. WAN alone never steers. |
| Weighted average replacing confidence model | The existing additive confidence model is proven, tested (1,978 tests), and understood. Replacing with weighted average or ML scoring is unnecessary. SD-WAN vendors use composite scores for dozens of paths; wanctl has exactly two WANs. | Add WAN state as another additive contributor to existing `compute_confidence()`. Same pattern as RTT delta, drops, queue depth. |
| Real-time IPC (shared memory, sockets, pipes) | Replacing JSON state file adds coupling, failure modes, and complexity. JSON read takes <1ms; file is already written atomically by autorate every 50ms cycle. | Keep JSON state file. Simple, debuggable (`cat state.json`), resilient to daemon crashes, already proven reliable. |
| Steering reads autorate's raw RTT directly | Autorate already computes state from RTT. Re-interpreting raw RTT duplicates autorate's state machine logic, creating two sources of truth that can disagree. | Steering reads autorate's computed state (GREEN/YELLOW/SOFT_RED/RED), not raw measurements. Autorate is authoritative for WAN health. |
| Per-direction signals (separate dl/ul) | Autorate has both dl_zone and ul_zone, but steering cares about download congestion (inbound path). Upload congestion does not degrade latency-sensitive inbound traffic. Two directions doubles complexity for marginal value. | Read download state only. Upload is noise for steering decisions. |
| Dynamic weight adjustment | Self-tuning weights that increase WAN influence when it "correctly predicted" congestion. ML-adjacent, hard to test, can diverge. Flap detector already handles disagreeing signals. | Fixed weights, tunable only via YAML config. Operators adjust after observing production. |
| Steering existing connections mid-stream | Moving TCP connections mid-stream breaks sequences and causes retransmits worse than the congestion being avoided. | Binary mangle rule toggle (existing pattern). Only new connections route to ATT. Existing connections expire naturally. |
| WAN state EWMA smoothing | Applying additional EWMA to zone state smooths an already-smoothed signal. Autorate zone classification uses EWMA-smoothed RTT with 4-state hysteresis (streak counters). Double-smoothing delays detection. | Use zone state directly. It is already the product of EWMA + hysteresis. |
| Separate WAN state polling interval | Adds timer complexity. Steering already reads state file every cycle. | Read WAN state in same file read as baseline RTT. One read, two data points. |

## Feature Dependencies

```
Autorate exports dl_state in state file
  |
  v
Steering reads WAN state (extends BaselineLoader)
  |
  +--> Staleness guard (safety check on read)
  |      |
  |      +--> Grace period on startup (extension of staleness concept)
  |
  +--> Map 4-state to confidence weight (ConfidenceWeights additions)
  |      |
  |      +--> SOFT_RED as intermediate signal (additional weight)
  |      |
  |      +--> Sustained WAN RED triggers failover
  |      |    (via elevated confidence -> existing sustain timer)
  |      |
  |      +--> Sustained WAN GREEN allows recovery
  |           (via lowered confidence -> existing recovery timer)
  |
  +--> YAML config for weights and thresholds (parallel, needed for tuning)
  |
  +--> Health endpoint WAN state (needs data to expose)
  |
  +--> Structured logging (needs data to log)

CAKE stats remain primary signal = architectural constraint, enforced by weight values
Backward compatibility = defensive coding in reader, no dependency
```

## MVP Recommendation

Build all Table Stakes. They form a minimal coherent unit:

1. **Autorate exports dl_state** -- nothing works without this
2. **Steering reads WAN state** -- the data pipe
3. **Map to confidence weight** -- the signal fusion point
4. **Sustained WAN RED/GREEN** -- already handled by existing sustain infrastructure; just needs WAN-elevated confidence to feed into it
5. **CAKE remains primary** -- enforced by weight values, not separate code
6. **YAML config** -- required for production tuning
7. **Staleness guard** -- safety feature
8. **Backward compatibility** -- graceful degradation for upgrade path

Defer:
- **Asymmetric sustain timers**: Only build if production shows WAN signal is too noisy with shared timer. Start simple.
- **Health endpoint WAN state**: Phase 2 within milestone. Debugging aid, not core.
- **Grace period on startup**: Low risk since autorate typically starts before steering. Implement if startup race observed.

## Signal Priority Model

Based on SD-WAN industry patterns and wanctl's existing architecture:

**Recommended weight values (additive, 0-100 scale):**

| Signal | Points | Rationale |
|--------|--------|-----------|
| CAKE RED state | 50 | Ground truth, local measurement. Existing value. |
| WAN RED from autorate | 20-25 | Strong amplifier. Alone: below threshold (55). With CAKE YELLOW (10): above threshold. |
| WAN SOFT_RED from autorate | 10-15 | Weak amplifier. Alone: far below threshold. With CAKE YELLOW or drops: approaches threshold. |
| RTT delta > 120ms (steering) | 25 | Severe latency. Existing value. |
| RTT delta > 80ms (steering) | 15 | Moderate latency. Existing value. |
| Drops increasing | 10 | Trend signal. Existing value. |
| Queue depth sustained | 10 | Pressure signal. Existing value. |
| WAN YELLOW from autorate | 0-5 | Informational. Too noisy to influence decisions meaningfully. |
| WAN GREEN from autorate | 0 | Healthy. No contribution. |

**Decision scenarios showing the gap being closed:**

| CAKE State | WAN State | Score | Outcome | Notes |
|------------|-----------|-------|---------|-------|
| RED | RED | 70-75 | STEER (fast) | Both signals agree, high confidence |
| RED | GREEN | 50 | STEER (normal) | CAKE alone sufficient at threshold |
| GREEN | RED | 20-25 | HOLD | WAN alone insufficient -- could be probe noise |
| YELLOW | RED | 30-35 | HOLD (borderline) | Needs sustained + drops to cross threshold |
| YELLOW + drops | RED | 45-50 | STEER (borderline) | Multiple signals converging |
| GREEN | GREEN | 0 | HOLD | All clear |

**The gap scenario (row 3):** CAKE GREEN + WAN RED = 20-25 points. Intentionally below the 55 threshold. WAN RED alone should NOT steer -- it could be ISP routing hiccup, probe path issue, or transient. But if CAKE starts showing YELLOW or drops trend upward, the combined score approaches threshold. This is "amplifying" behavior: WAN signal lowers the bar for CAKE to trigger steering.

## Existing Infrastructure Reuse

Nearly all infrastructure exists. This is a wiring milestone, not a building milestone.

| What's Needed | What Exists | Gap |
|---------------|-------------|-----|
| Autorate writes dl_state | `WANControllerState.save()` writes streaks/EWMA | Add `congestion.dl_state` to state dict (3 lines) |
| Steering reads WAN state | `BaselineLoader.load_baseline_rtt()` reads from same file | Add `load_wan_state()` method, ~15 lines |
| Confidence scoring | `compute_confidence()` with signal contributors | Add WAN state weight branch, ~10 lines |
| Sustain timers | `TimerManager` with degrade/recovery/hold_down | None -- WAN-boosted confidence flows through existing timers |
| Recovery eligibility | Checks `cake_state == "GREEN"`, `rtt_delta < 10`, `drops < 0.001` | Add `wan_state in ("GREEN", None)` to eligibility |
| Flap detection | `FlapDetector` with window, max_toggles, penalty | None -- protects against all steering oscillation |
| YAML config | `configs/steering.yaml` `confidence:` section | Add `wan_state:` subsection, ~6 lines |
| Staleness | `BaselineLoader._check_staleness()` | Replicate pattern for WAN state, ~10 lines |
| Health endpoint | `SteeringHealthHandler._get_health_status()` | Add `wan_state` dict to response, ~8 lines |
| Dry-run mode | `DryRunLogger` in confidence controller | None -- WAN-boosted decisions auto-logged in dry-run |
| Backward compat | `state.get()` pattern used throughout | `.get("congestion", {}).get("dl_state", None)` |

## Missing Piece: Autorate Must Export dl_state

Currently, `WANControllerState.save()` writes:
```json
{
  "download": {"green_streak": N, "soft_red_streak": N, "red_streak": N, "current_rate": N},
  "upload": {"green_streak": N, ...},
  "ewma": {"baseline_rtt": F, "load_rtt": F},
  "last_applied": {"dl_rate": N, "ul_rate": N},
  "timestamp": "ISO-8601"
}
```

It does NOT write the computed `dl_zone` or `ul_zone` from `adjust_4state()`. This is the one structural change needed in autorate: save the current download congestion state alongside existing data.

Required addition to autorate state file:
```json
{
  "congestion": {"dl_state": "GREEN", "ul_state": "GREEN"}
}
```

This is a 3-line change in `WANController.save_state()` (already has `dl_zone` and `ul_zone` in scope from `run_cycle()`).

## Sources

- [Versa SD-WAN Advanced Path Selection](https://versa-networks.com/blog/sophisticated-path-selection-capabilities-underpin-sd-wan-performance/) -- composite scoring, SLA violation detection, brownout at loss >= 50% (MEDIUM confidence)
- [Versa SLA Monitoring](https://docs.versa-networks.com/Secure_SD-WAN/01_Configuration_from_Director/SD-WAN_Configuration/Advanced_SD-WAN_Configuration/Configure_SLA_Monitoring_for_SD-WAN_Traffic_Steering) -- statistical + inline loss measurement combination (MEDIUM confidence)
- [Cisco Meraki Connection Monitoring](https://documentation.meraki.com/MX/Firewall_and_Traffic_Shaping/Connection_Monitoring_for_WAN_Failover) -- 15-second hysteresis, multi-probe failover (MEDIUM confidence)
- [CAKE Technical Documentation](https://www.bufferbloat.net/projects/codel/wiki/CakeTechnical/) -- queue management, drop signaling (HIGH confidence)
- [sqm-autorate](https://github.com/sqm-autorate/sqm-autorate) -- community precedent for RTT-based CAKE adjustment (HIGH confidence)
- [ipSpace SD-WAN Fast Failover](https://blog.ipspace.net/2020/01/fast-failover-in-sd-wan-networks/) -- sub-second failover patterns (MEDIUM confidence)
- Existing wanctl codebase: `steering_confidence.py`, `congestion_assessment.py`, `daemon.py`, `wan_controller_state.py` (HIGH confidence -- direct code inspection)
