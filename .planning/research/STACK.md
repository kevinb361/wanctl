# Technology Stack: WAN-Aware Steering Integration

**Project:** wanctl v1.11
**Researched:** 2026-03-08

## Recommendation: Zero New Dependencies

No new external libraries, frameworks, or tools are needed. Every primitive required for WAN-aware steering already exists in the codebase.

### Existing Primitives (Reuse)

| Component | Location | Reuse For |
|-----------|----------|-----------|
| Atomic JSON state file IPC | `state_utils.py:atomic_write_json()` | Autorate writes WAN state, steering reads |
| Safe file reader | `state_utils.py:safe_json_load_file()` | Read WAN state from state file |
| State file staleness check | `steering/daemon.py:BaselineLoader._check_staleness()` | Same check applies to WAN state data |
| Confidence scoring | `steering_confidence.py:compute_confidence()` | Add WAN state as new weighted signal |
| Sustained detection | `steering_confidence.py:compute_confidence()` | SOFT_RED_sustained pattern: check last N history entries |
| Sustain timers | `steering_confidence.py:TimerManager` | Existing degrade/recovery timers gate confidence score |
| Flap detection | `steering_confidence.py:FlapDetector` | Already prevents oscillation; WAN signal benefits automatically |
| Dirty tracking | `wan_controller_state.py:WANControllerState._is_state_changed()` | Extend to include congestion dict |
| Config schema validation | `config_base.py:BaseConfig` | Add wan_state section to schema |
| Health endpoint | `steering/health.py` | Add WAN state to existing congestion section |

### What Needs to Be Added (All Pure Python, Zero Deps)

| Addition | File | Lines | Complexity |
|----------|------|-------|------------|
| `congestion` dict in autorate state file | `wan_controller_state.py`, `autorate_continuous.py` | ~15 | Low |
| WAN state reader + refactored BaselineLoader | `steering/daemon.py` | ~20 | Low |
| `wan_state` + `wan_state_history` on ConfidenceSignals | `steering/steering_confidence.py` | ~5 | Low |
| WAN weights on ConfidenceWeights | `steering/steering_confidence.py` | ~5 | Low |
| WAN scoring block in compute_confidence() | `steering/steering_confidence.py` | ~15 | Low |
| wan_dl_state in steering state schema | `steering/daemon.py:get_initial_state()` | ~3 | Low |
| wan_state config section | `steering/daemon.py:SteeringConfig` | ~10 | Low |
| Health endpoint WAN state | `steering/health.py` | ~5 | Low |

**Total new production code: ~80 lines across existing files. Zero new files.**

## Signal Fusion Pattern

### Weighted Additive Scoring (Existing Architecture)

The `ConfidenceController` already implements multi-signal weighted scoring:

```
confidence = base_score(CAKE_state)
           + rtt_contribution
           + drop_trend
           + queue_sustained
```

WAN state is an additional additive term:

```
confidence = base_score(CAKE_state)
           + rtt_contribution
           + drop_trend
           + queue_sustained
           + wan_state_contribution    <-- NEW
```

### Confidence Weights for WAN State

| WAN State | Weight | Rationale |
|-----------|--------|-----------|
| RED (sustained 3 cycles) | 30 | Strong ISP congestion; alone not enough to steer (threshold=55) |
| SOFT_RED (sustained 3 cycles) | 15 | Moderate congestion; amplifies CAKE signals |
| YELLOW | 5 | Early warning; minimal contribution |
| GREEN | 0 | Healthy; no contribution |

**Threshold math proving WAN is amplifier, not trigger:**
- WAN RED (30) alone: 30 < 55 threshold. Cannot trigger steering.
- WAN RED (30) + CAKE YELLOW (10): 40 < 55. Still not enough.
- WAN RED (30) + CAKE RED (50): 80 > 55. Steers. (Both signals agree.)
- WAN RED (30) + CAKE YELLOW (10) + drops increasing (10) + queue high (10): 60 > 55. Steers. (Multiple signals agree.)

This preserves the invariant: **CAKE stats remain primary, WAN state amplifies/confirms.**

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Signal fusion | Weighted additive in compute_confidence() | Independent parallel Schmitt triggers with AND/OR | Complicates recovery logic, loses signal correlation, more state to manage |
| WAN state filtering | History-based sustained detection in compute_confidence() | Separate WANStateGate class with own timers | Unnecessary abstraction; existing SOFT_RED_sustained pattern handles this in 5 lines |
| IPC mechanism | JSON state file (existing) | Unix domain socket / shared memory | Over-engineering; file IPC proven at 50ms cycle with atomic writes |
| Hysteresis timer | Cycle-counting via history list | time.monotonic() wall-clock timers | Cycle-counting is deterministic and already used for SOFT_RED_sustained |
| State encoding | String enum in JSON ("GREEN"/"RED") | Numeric encoding (0/1/2/3) | String is self-documenting, consistent with existing congestion_state field in steering |

## State File IPC Extension

### Current Autorate State File Schema

```json
{
    "download": {"green_streak": 0, "soft_red_streak": 0, "red_streak": 0, "current_rate": 920000000},
    "upload": {"green_streak": 0, "soft_red_streak": 0, "red_streak": 0, "current_rate": 42000000},
    "ewma": {"baseline_rtt": 23.4, "load_rtt": 25.1},
    "last_applied": {"dl_rate": 920000000, "ul_rate": 42000000},
    "timestamp": "2026-03-08T12:00:00"
}
```

### Proposed Extension (Backward Compatible)

```json
{
    ...existing fields unchanged...
    "congestion": {
        "dl_state": "GREEN",
        "ul_state": "GREEN"
    }
}
```

**Why `congestion` as key:** Clean namespace, doesn't pollute existing sections. Mirrors steering health endpoint's `congestion` key.

**Backward compatibility:** Old steering code ignoring `congestion` key continues working. New steering code handles missing key gracefully (returns None, treats as no signal).

## Configuration Extension

### Proposed YAML Additions to steering.yaml

```yaml
# WAN-aware steering (v1.11)
wan_state:
  enabled: true                    # Master toggle
  degrade_sustain_cycles: 3        # Sustained RED before scoring contribution
  recovery_sustain_cycles: 3       # Sustained GREEN before clearing contribution
  weight_red: 30                   # WAN RED contribution to confidence
  weight_soft_red: 15              # WAN SOFT_RED contribution
  weight_yellow: 5                 # WAN YELLOW contribution
```

**Why configurable weights:** Different ISPs have different RTT characteristics. Cable (Spectrum) has more volatile RTT than fiber. Matching the portable controller architecture principle.

## Sources

All from direct codebase analysis:
- `src/wanctl/wan_controller_state.py` -- state file schema
- `src/wanctl/autorate_continuous.py` -- WANController.run_cycle(), save_state()
- `src/wanctl/steering/steering_confidence.py` -- ConfidenceSignals, compute_confidence(), ConfidenceWeights
- `src/wanctl/steering/daemon.py` -- BaselineLoader, SteeringDaemon, update_state_machine()
- `src/wanctl/steering/congestion_assessment.py` -- assess_congestion_state()
- `configs/steering.yaml` -- production config structure
