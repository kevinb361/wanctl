# Phase 119: Auto-Fusion Healing - Context

**Gathered:** 2026-03-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Automatic fusion state management based on protocol correlation. The controller detects ICMP/IRTT path divergence via rolling Pearson correlation, suspends fusion when correlation degrades for a sustained period, recovers through a 3-state machine (ACTIVE/SUSPENDED/RECOVERING), fires Discord alerts on transitions, locks the tuner's fusion_icmp_weight during suspension, and exposes heal state via the health endpoint. Eliminates the manual SIGUSR1 toggle workflow for ICMP/IRTT path divergence (current ATT production issue).

</domain>

<decisions>
## Implementation Decisions

### Correlation Detection
- **D-01:** Use rolling Pearson correlation between ICMP and IRTT signal deltas, NOT the existing simple ratio metric in `_check_protocol_correlation()`. Pearson catches the ATT scenario where the ratio looks "normal" (0.74) but signals disagree on directional trends.
- **D-02:** Sustained detection uses a 60-second time window average of Pearson correlation. At 20Hz, this is ~1,200 samples per window -- statistically robust. Threshold is configurable via YAML.

### State Machine
- **D-03:** 3-state machine: ACTIVE -> SUSPENDED -> RECOVERING -> ACTIVE.
- **D-04:** SUSPENDED triggers when 60-second rolling Pearson correlation drops below configurable threshold for sustained period.
- **D-05:** RECOVERING -> ACTIVE requires sustained good correlation above threshold for a longer window (e.g., 5 minutes). Asymmetric hysteresis: fast to suspend (~1 min), slow to recover (~5 min). This mirrors the controller's existing philosophy (rate decreases immediate, increases require sustained GREEN cycles).

### Healer vs Operator SIGUSR1
- **D-06:** Operator overrides with healer pause. When operator sends SIGUSR1 to re-enable fusion while healer is in SUSPENDED state, fusion re-enables immediately AND the healer pauses monitoring for a configurable grace period (default 30 minutes). After grace expires, healer resumes -- if correlation is still bad, it re-suspends. If the operator's change fixed the path, correlation improves during grace and healer stays ACTIVE.

### Parameter Locking
- **D-07:** Claude's discretion on mechanism for locking `fusion_icmp_weight` in the tuner during SUSPENDED state. Options: reuse existing `_tuning_parameter_locks` dict (time-based), or add a new `healer_locked_params` set (event-based). Choose based on code fit and separation of concerns.

### Claude's Discretion
- Parameter lock mechanism (D-07)
- Pearson correlation implementation details (window management, sample buffer structure)
- Exact configurable threshold values and defaults
- Grace period default (30 minutes suggested, Claude may adjust)
- Where the healer state machine lives (new module vs integrated into autorate_continuous.py)
- Alert message content and severity levels for state transitions
- Health endpoint payload structure for heal state and correlation history
- Test structure and fixture design

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Fusion Core (primary modification target)
- `src/wanctl/autorate_continuous.py` lines 2425-2470 -- `_compute_fused_rtt()` weighted average core
- `src/wanctl/autorate_continuous.py` lines 2472-2530 -- `_reload_fusion_config()` SIGUSR1 handler
- `src/wanctl/autorate_continuous.py` lines 2389-2423 -- `_check_protocol_correlation()` existing ratio check
- `src/wanctl/autorate_continuous.py` lines 1777-1779 -- Fusion state variables init

### Alert System
- `src/wanctl/alert_engine.py` -- AlertEngine with `fire()` method, per-rule cooldowns, severity levels
- `src/wanctl/webhook_delivery.py` -- Discord/webhook delivery backend

### Tuning Parameter Locking
- `src/wanctl/tuning/safety.py` lines 159-190 -- `is_parameter_locked()` / `lock_parameter()` with monotonic expiry
- `src/wanctl/tuning/models.py` line 70 -- `TuningConfig.exclude_params` frozenset
- `src/wanctl/tuning/analyzer.py` -- `run_tuning_analysis()` orchestration, parameter skip logic

### Health Endpoint
- `src/wanctl/health_check.py` lines 225-242 -- Current fusion and irtt.protocol_correlation sections

### Signal Processing
- `src/wanctl/signal_processing.py` -- SignalProcessor, Hampel filter, EWMA tracking patterns

### Existing Tests
- `tests/test_fusion_core.py` -- Fusion RTT computation tests
- `tests/test_fusion_reload.py` -- SIGUSR1 reload state transition tests
- `tests/test_fusion_config.py` -- YAML loading validation
- `tests/test_alert_engine.py` -- AlertEngine core tests
- `tests/test_tuning_safety_wiring.py` -- Parameter locking/revert tests

### Prior Phase Context
- `.planning/phases/118-metrics-retention-strategy/118-CONTEXT.md` -- Retention config patterns (SIGUSR1 reload pattern added in Phase 118)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AlertEngine.fire()` -- Ready-made alert delivery with per-rule cooldowns and severity. Add new `fusion_suspended` / `fusion_recovered` / `fusion_recovering` alert types.
- `_check_protocol_correlation()` -- Existing per-cycle ratio calculation. Can be extended or replaced with Pearson correlation feeding into the healer.
- `is_parameter_locked()` / `lock_parameter()` in `tuning/safety.py` -- Existing lock mechanism with monotonic expiry (candidate for reuse per D-07).
- `_reload_fusion_config()` -- SIGUSR1 handler already reloads fusion state. Grace period pause integrates here.
- Health endpoint fusion section -- Already exposes `enabled`, `icmp_weight`, `active_source`, `fused_rtt_ms`. Extend with heal state.

### Established Patterns
- SIGUSR1 reload: generalized handler reloads multiple config sections (dry_run, wan_state, webhook_url, fusion, retention). Healer pause hooks into this.
- AlertEngine per-rule config: `rules[alert_type]` with `enabled`, `cooldown_sec`, `severity` -- new fusion alert types follow this pattern.
- Signal processing EWMA: time-constant-based alpha calculation (`alpha = 0.05 / tc`). Pearson correlation could use similar windowed approach.
- State tracking: WANController already tracks `_fusion_enabled`, `_fusion_icmp_weight`, `_irtt_correlation`. Healer adds `_fusion_heal_state`.

### Integration Points
- `_compute_fused_rtt()` -- Must check healer state (SUSPENDED -> return filtered_rtt without fusion)
- `_check_protocol_correlation()` -- Feed Pearson correlation samples into healer each cycle
- `_reload_fusion_config()` -- Add grace period pause logic
- `run_tuning_analysis()` -- Check healer lock before tuning fusion_icmp_weight
- Health endpoint -- Add `fusion.heal_state`, `fusion.correlation_history` fields

### Key Constraint: 50ms Hot Loop
All healer logic that runs per-cycle must be sub-millisecond. The Pearson correlation update and state machine check must not add measurable overhead to the 50ms cycle budget (currently 30-40ms execution).

</code_context>

<specifics>
## Specific Ideas

- ATT production issue: ICMP/IRTT path divergence with ratio 0.74 (within "normal" 0.67-1.5 range) causes permanent delta offset. Pearson correlation would catch this because the signals move independently despite similar magnitudes.
- The 60-second suspension window + 5-minute recovery window creates asymmetric hysteresis matching the controller's "fast decrease, slow increase" philosophy.
- Grace period (30 min default) matches the tuner's revert cooldown concept (24h) -- "back off after intervention, resume monitoring later."
- Existing `_irtt_correlation` attribute already stores the per-cycle ratio -- can be augmented with rolling Pearson alongside.

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 119-auto-fusion-healing*
*Context gathered: 2026-03-27*
