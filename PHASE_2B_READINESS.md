# Phase 2B Readiness: Time-of-Day Bias

**Status:** 📋 Planned (Not Yet Implemented)
**Prerequisite:** Phase 2A deployed and stable (✅ Complete)
**Architecture:** Config-only, link-agnostic

---

## Purpose

Phase 2B adds **time-of-day awareness** to floor selection without changing core control logic.

**Goal:** Use historical patterns to preemptively adjust floors during known congestion periods.

---

## Why Phase 2B Can Remain Config-Only

### Observation: Cable Has Evening Congestion, DSL Doesn't

**Spectrum (cable):**
- 6pm-9pm: Neighborhood congestion
- RTT rises, SOFT_RED/RED states common
- Desired behavior: Lower floors preemptively during evening

**AT&T (DSL):**
- No time-of-day pattern
- Congestion rare, random
- Desired behavior: No time-of-day adjustment

**Key insight:** The controller doesn't need to know **why** a deployment has time-of-day bias.

It just needs to apply a floor multiplier during specified hours.

---

## Proposed Implementation (Config-Driven)

### Configuration Addition

```yaml
continuous_monitoring:
  # ... existing parameters ...

  # Time-of-day bias (Phase 2B)
  tod_bias:
    enabled: true  # Enable time-of-day adjustments

    # Define time windows (24-hour format, local time)
    windows:
      - name: "evening_peak"
        hours: [18, 19, 20, 21]  # 6pm-9pm
        floor_multiplier: 0.85   # Reduce floors to 85% during this window

      - name: "late_night"
        hours: [2, 3, 4, 5]      # 2am-5am
        floor_multiplier: 1.10   # Increase floors to 110% (less congestion)

    # Default multiplier (when no window matches)
    default_multiplier: 1.0  # 100% of configured floors
```

### Controller Behavior (Link-Agnostic)

```python
def get_effective_floor(self, state: str, direction: str) -> int:
    """Get effective floor for current state, adjusted for time-of-day."""

    # 1. Get base floor from config
    if direction == "download":
        if state == "GREEN":
            base_floor = self.config.download_floor_green
        elif state == "YELLOW":
            base_floor = self.config.download_floor_yellow
        elif state == "SOFT_RED":
            base_floor = self.config.download_floor_soft_red
        elif state == "RED":
            base_floor = self.config.download_floor_red
    else:  # upload
        # Similar logic...

    # 2. Apply time-of-day multiplier (if enabled)
    multiplier = self._get_tod_multiplier()

    # 3. Return adjusted floor
    return int(base_floor * multiplier)


def _get_tod_multiplier(self) -> float:
    """Get time-of-day floor multiplier for current hour."""

    if not self.config.tod_bias_enabled:
        return 1.0  # No adjustment

    current_hour = datetime.now().hour

    # Find matching time window
    for window in self.config.tod_windows:
        if current_hour in window['hours']:
            return window['floor_multiplier']

    # No window matched, use default
    return self.config.tod_default_multiplier
```

### Example: Spectrum Evening Peak

**Config:**
```yaml
tod_bias:
  enabled: true
  windows:
    - name: "evening_peak"
      hours: [18, 19, 20, 21]
      floor_multiplier: 0.85  # 15% reduction
```

**Behavior:**
- **7:00pm (in window):**
  - Base floor (GREEN): 550M
  - Multiplier: 0.85
  - Effective floor: 467M
  - **Preemptively lowers floor to reduce evening congestion**

- **11:00pm (out of window):**
  - Base floor (GREEN): 550M
  - Multiplier: 1.0 (default)
  - Effective floor: 550M
  - **Normal behavior**

### Example: AT&T (No Time-of-Day Pattern)

**Config:**
```yaml
tod_bias:
  enabled: false  # No time-of-day adjustment
```

**Behavior:**
- Always uses base floors (multiplier = 1.0)
- No evening bias (DSL doesn't have neighborhood congestion)

---

## Why This Remains Link-Agnostic

### 1. No Medium-Specific Logic

The controller doesn't know:
- What link type it's managing
- Why a deployment has evening congestion
- Whether congestion is due to DOCSIS, DSL, or fiber

It **only** knows:
- Current hour
- Configured time windows
- Multipliers to apply

### 2. Configuration Expresses Behavior

**Cable (has evening congestion):**
```yaml
tod_bias:
  enabled: true
  windows:
    - hours: [18, 19, 20, 21]
      floor_multiplier: 0.85
```

**DSL (no pattern):**
```yaml
tod_bias:
  enabled: false
```

**Fiber (future, if needed):**
```yaml
tod_bias:
  enabled: true
  windows:
    - hours: [12, 13]  # Lunch hour, if observed
      floor_multiplier: 0.90
```

### 3. Same Algorithm Everywhere

The multiplier logic is **universal**:
1. Get current hour
2. Find matching window
3. Apply multiplier
4. Return adjusted floor

**No branching on link type.**

---

## Integration with Phase 2A (4-State)

Phase 2B works seamlessly with Phase 2A:

### Spectrum Download (4-State + Time-of-Day)

**Evening (7pm):**
```
Base floors:     GREEN=550M, YELLOW=350M, SOFT_RED=275M, RED=200M
Multiplier:      0.85 (evening window)
Effective:       GREEN=467M, YELLOW=297M, SOFT_RED=233M, RED=170M
```

**Late night (3am):**
```
Base floors:     GREEN=550M, YELLOW=350M, SOFT_RED=275M, RED=200M
Multiplier:      1.0 (default, no window)
Effective:       GREEN=550M, YELLOW=350M, SOFT_RED=275M, RED=200M
```

**Behavior:**
- State transitions still driven by RTT thresholds (Phase 2A)
- Floors preemptively adjusted by time-of-day (Phase 2B)
- **Both phases compose without code changes**

### AT&T (3-State, No Time-of-Day)

**All hours:**
```
Base floors:     GREEN=25M, YELLOW=25M, RED=25M
Multiplier:      1.0 (tod_bias disabled)
Effective:       GREEN=25M, YELLOW=25M, RED=25M
```

**Same controller code, different config.**

---

## Deployment Strategy

### 1. Observation Phase (Current)

**Do NOT implement Phase 2B yet.**

First, observe Phase 2A for 1-2 weeks:
- Collect logs during evening peaks (6-9pm)
- Identify consistent time-of-day patterns
- Measure SOFT_RED/RED frequency by hour

**Success criteria for Phase 2B:**
- Clear evening peak visible in logs
- SOFT_RED/RED states correlate with time of day
- User reports issues during predictable hours

### 2. Configuration Design

Based on observations, design time windows:

**Example (Spectrum):**
```yaml
tod_bias:
  enabled: true
  windows:
    # Evening peak (observed in logs)
    - name: "evening_peak"
      hours: [18, 19, 20, 21]
      floor_multiplier: 0.85  # Preemptively lower floors

    # Late night (observed quiet period)
    - name: "late_night"
      hours: [2, 3, 4, 5, 6]
      floor_multiplier: 1.05  # Slightly higher floors (less congestion)

  default_multiplier: 1.0
```

### 3. Controller Implementation

**Code changes needed:**
- Add `tod_bias` config parsing
- Add `_get_tod_multiplier()` method
- Modify `get_effective_floor()` to apply multiplier

**Estimated LOC:** ~30 lines (config parsing + multiplier logic)

**Verification:**
- No link-specific logic
- Same code for all deployments
- Backward compatible (tod_bias.enabled = false)

### 4. Testing

**Unit tests:**
- Verify multiplier logic for all hours
- Test window overlap handling
- Verify disabled behavior (multiplier = 1.0)

**Integration tests:**
- Run Spectrum config with tod_bias enabled
- Run AT&T config with tod_bias disabled
- Verify same controller binary

### 5. Deployment

**Rollout:**
1. Deploy to Spectrum first (has evening pattern)
2. Monitor for 48 hours during peak hours
3. Verify floors adjust correctly by hour
4. No deployment to AT&T (tod_bias disabled)

---

## Success Criteria (Phase 2B)

**Phase 2B is successful if:**
- ✅ SOFT_RED/RED states reduce during evening peaks
- ✅ User experience improves during 6-9pm
- ✅ No negative impact during off-peak hours
- ✅ AT&T deployment unaffected (same code, different config)
- ✅ Logs show effective floors adjusting by time of day

**Warning signs:**
- ⚠️ Floors too low during evening (user-visible bandwidth collapse)
- ⚠️ No improvement in SOFT_RED/RED frequency
- ⚠️ Multiplier logic broken (floors not adjusting)

---

## Why Phase 2B Validates Portable Architecture

### 1. Same Code, Different Behaviors

**Spectrum:** Time-of-day bias enabled (evening congestion pattern)
**AT&T:** Time-of-day bias disabled (no pattern)

**Same controller binary.**

### 2. Configuration Drives Behavior

No `if link_type == "cable": apply_evening_bias()`

Just: `multiplier = get_tod_multiplier()` (reads config)

### 3. Composability

Phase 2A (4-state) + Phase 2B (time-of-day) compose naturally:
- 4-state thresholds control state transitions
- Time-of-day multiplier controls effective floors
- Both config-driven, both link-agnostic

### 4. Extensibility

Future phases (2C, 2D) can add more multipliers:
- CAKE stats multiplier (corroboration)
- Adaptive threshold multiplier (variance-based)
- All compose via config

---

## Next Steps (When Ready for Phase 2B)

1. **Wait for Phase 2A stability (1-2 weeks observation)**
2. **Analyze logs for time-of-day patterns**
3. **Design time windows based on data**
4. **Implement `_get_tod_multiplier()` method**
5. **Add config schema for `tod_bias`**
6. **Write unit tests**
7. **Deploy to Spectrum only**
8. **Monitor for 48 hours**
9. **Document Phase 2B in `PHASE_2B_TOD_BIAS.md`**

---

## Summary

**Phase 2B is ready to implement because:**
- ✅ Phase 2A validated portable architecture
- ✅ Time-of-day bias can be config-only
- ✅ No link-specific logic needed
- ✅ Backward compatible (tod_bias.enabled = false)
- ✅ Composes with Phase 2A (4-state + time-of-day)

**Do not implement yet:**
- ⏳ Wait for Phase 2A observation period (1-2 weeks)
- ⏳ Collect time-of-day pattern data
- ⏳ Design time windows based on observed behavior

**When Phase 2A is stable and patterns are clear:** Implement Phase 2B per this design.

---

**Architecture validated:** ✅ Portable controller supports time-of-day bias without code fragmentation.
