# Phase 59: WAN State Reader + Signal Fusion - Context

**Gathered:** 2026-03-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Steering daemon reads WAN congestion zone from the autorate state file (already read for baseline RTT) and incorporates it as an amplifying weight in `compute_confidence()`. WAN state alone cannot trigger steering -- it only pushes the score closer to threshold when CAKE signals are also present. Includes fail-safe behavior for stale/missing data and a recovery gate requiring WAN GREEN.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion

All implementation decisions delegated to Claude, informed by requirements, existing CAKE weight patterns, and the "WAN is amplifying only" constraint:

**WAN weight magnitude:**
- WAN_RED weight must be < steer_threshold (~55) to satisfy FUSE-03
- Should follow existing weight scaling: CAKE RED=50, SOFT_RED=25, YELLOW=10
- WAN weights should be meaningful amplifiers but never dominant -- research should validate specific values
- WAN_SOFT_RED weight should be proportionally lower than WAN_RED (same ratio as CAKE SOFT_RED:RED)

**Recovery gate strictness:**
- FUSE-05: Recovery requires WAN GREEN (or unavailable) in addition to existing CAKE checks
- Whether WAN YELLOW blocks recovery is at Claude's discretion -- research should inform based on operational safety
- Recovery gate integrates with existing `update_recovery_timer()` -- not a separate timer

**Sustained WAN RED detection:**
- Whether WAN RED contributes immediately or requires sustained cycles is at Claude's discretion
- Consider: autorate zone is already EWMA-filtered with streak counters (noted in REQUIREMENTS.md Out of Scope: "WAN state EWMA smoothing" rejected as "double-smoothing")
- This suggests immediate contribution may be appropriate since the signal is already filtered upstream

**State file read integration:**
- WAN zone extracted in `BaselineRTTLoader.load_baseline_rtt()` from same `safe_json_load_file()` call (FUSE-01: zero additional I/O)
- Return both baseline_rtt and WAN zone from the loader, or extend the loader to expose zone separately
- Zone accessed via `state.get("congestion", {}).get("dl_state", None)` per Phase 58 context

**Staleness and degradation:**
- SAFE-01: Zone older than 5s defaults to GREEN (fail-safe)
- SAFE-02: Autorate completely unavailable (state is None) → skip WAN weight entirely (None = no signal)
- Staleness check can reuse existing `_check_staleness()` infrastructure in BaselineRTTLoader

</decisions>

<specifics>
## Specific Ideas

No specific requirements -- open to standard approaches. Requirements (FUSE-01 through FUSE-05, SAFE-01, SAFE-02) are very precisely scoped. Research findings should validate weight values and integration approach.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `BaselineRTTLoader.load_baseline_rtt()` at `steering/daemon.py:575-618`: Already reads autorate state file via `safe_json_load_file()` -- extend to extract `congestion.dl_state`
- `compute_confidence()` at `steering/steering_confidence.py:85-146`: Pure function, takes `ConfidenceSignals` dataclass -- add WAN signal field
- `ConfidenceWeights` class at `steering/steering_confidence.py:27-64`: Fixed weight constants -- add WAN_RED, WAN_SOFT_RED
- `ConfidenceSignals` dataclass at `steering/steering_confidence.py:67-82`: Input struct -- add `wan_zone: str | None` field
- `TimerManager.update_recovery_timer()` at `steering/steering_confidence.py:292-359`: Recovery eligibility check -- add WAN GREEN gate

### Established Patterns
- Confidence recomputes from scratch every cycle (NO hysteresis) -- WAN weight follows same pattern
- `ConfidenceWeights` uses class-level constants, not config -- WAN weights follow same pattern (Phase 60 adds config override)
- `ConfidenceSignals` uses `field(default_factory=list)` for optional historical context -- WAN zone can use `None` default
- Recovery eligibility is a boolean check (`confidence <= self.recovery_threshold`) -- WAN gate adds an AND condition
- `_check_staleness()` at `steering/daemon.py:620-636`: Rate-limited staleness warning, reusable for WAN zone staleness

### Integration Points
- `SteeringDaemon._build_confidence_signals()` (around `daemon.py:1145-1157`): Where `ConfidenceSignals` is constructed -- add `wan_zone` from loader
- `SteeringDaemon.run_cycle()` (around `daemon.py:1070-1080`): Calls `load_baseline_rtt()` -- extend to receive WAN zone
- Recovery check at `daemon.py:604-606`: Where `update_recovery_timer()` is called -- pass WAN zone for gate check
- Tests: `test_steering_confidence.py` for compute_confidence tests, `test_steering_daemon.py` for integration

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope.

</deferred>

---

*Phase: 59-wan-state-reader-signal-fusion*
*Context gathered: 2026-03-09*
