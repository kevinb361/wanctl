# Portable Controller Architecture

**Status:** ✅ Production (v4.2 Phase 2A)
**Last Updated:** 2025-12-17

---

## Core Design Principle

> **The controller is link-agnostic. Behavior is invariant across all deployments.**

This system runs **identical code** on:

- DOCSIS cable (Spectrum 940/38 Mbps)
- VDSL2 DSL (AT&T 95/18 Mbps)
- GPON fiber (future deployments)
- Any congestion-managed queue

**There is no WAN-specific logic, no per-link state machines, no behavior forks.**

All variability is expressed exclusively through **configuration parameters**.

---

## Architectural Guarantees

### 1. Single Codebase

**Constraint:** One implementation serves all link types.

```
src/wanctl/autorate_continuous.py
    ↓
    Runs unchanged on:
    - DOCSIS (Spectrum)
    - DSL (AT&T)
    - Fiber (Dad's network)
    - Any future deployment
```

**Verification:**

```bash
# Same Python file, different configs
wan-spectrum: python -m wanctl.autorate_continuous --config spectrum_config.yaml
wan-att:      python -m wanctl.autorate_continuous --config att_config.yaml
wan-fiber:    python -m wanctl.autorate_continuous --config fiber_config.yaml
```

### 2. Configuration-Driven Behavior

**All behavioral differences live in YAML:**

| Behavior           | Parameter              | Example Values                         |
| ------------------ | ---------------------- | -------------------------------------- |
| Floor values       | `floor_green_mbps`     | 550M (cable), 25M (DSL), 800M (fiber)  |
| Ceiling values     | `ceiling_mbps`         | 940M (cable), 95M (DSL), 950M (fiber)  |
| Bloat thresholds   | `target_bloat_ms`      | 15ms (cable), 3ms (DSL), 10ms (fiber)  |
| Baseline RTT       | `baseline_rtt_initial` | 24ms (cable), 31ms (DSL), 5ms (fiber)  |
| Step-up speed      | `step_up_mbps`         | 10M (cable), 2M (DSL), 20M (fiber)     |
| Backoff aggression | `factor_down`          | 0.85 (cable), 0.90 (DSL), 0.90 (fiber) |

**The controller doesn't know or care what link type it's managing.**

### 3. State Machine Universality

The controller implements **one universal state machine** that adapts via thresholds:

```
GREEN  ──[delta > target_bloat_ms]──>  YELLOW
  ▲                                       │
  │                                       │
  └──────────[recovery]──────────────────┘

YELLOW ──[delta > warn_bloat_ms]────>  SOFT_RED  (if floor_soft_red_mbps differs)
  ▲                                       │
  │                                       │
  └──────────[recovery]──────────────────┘

SOFT_RED ──[delta > hard_red_bloat_ms]──> RED
  ▲                                        │
  │                                        │
  └──────────[recovery]───────────────────┘
```

**State transitions are threshold-driven, not link-specific.**

### 4. N-State Flexibility

The same code supports:

- **3-state:** Set `floor_soft_red_mbps == floor_yellow_mbps`
- **4-state:** Set `floor_soft_red_mbps` to a distinct value (Phase 2A)
- **Future N-state:** Add more floors and thresholds via config

**Upload vs. Download:**

- Spectrum: Download=4-state, Upload=3-state
- AT&T: Both=3-state
- Fiber: TBD (likely both=3-state)

This is purely **config-driven** — no code branching.

---

## What "Portable" Means

### ✅ Portable (Good)

- Same Python executable
- Same control algorithm
- Same state machine logic
- Same EWMA smoothing (α values configurable)
- Same floor/ceiling enforcement
- Same RTT measurement methodology
- Same RouterOS SSH interface

### ❌ Not Portable (Forbidden)

- `if wan_type == "cable": ...`
- Separate state machines for DSL vs. fiber
- Hardcoded thresholds in code
- Special-case logic for DOCSIS
- Medium-specific heuristics (bufferbloat assumptions)
- Per-ISP tuning embedded in source

---

## Configuration as the Source of Truth

### Semantic Model

Every deployment requires a configuration that answers:

1. **What is the physical link?**
   - `baseline_rtt_initial`: Propagation delay + fixed overhead
   - `ceiling_mbps`: Realistic maximum throughput

2. **What is the congestion tolerance?**
   - `target_bloat_ms`: When to start backing off
   - `warn_bloat_ms`: When to enter intermediate state
   - `hard_red_bloat_ms`: When to declare hard congestion

3. **What are the operational constraints?**
   - `floor_*_mbps`: Minimum acceptable speeds per state
   - `factor_down`: How aggressively to back off
   - `step_up_mbps`: How quickly to recover

4. **What is the measurement environment?**
   - `ping_hosts`: Reflectors for RTT measurement
   - `use_median_of_three`: Handle reflector variance
   - `alpha_baseline`, `alpha_load`: EWMA smoothing factors

**The controller interprets this configuration universally.**

---

## Invariants (Enforced Across All Deployments)

### 1. Threshold Ordering

```
0 < target_bloat_ms < warn_bloat_ms < hard_red_bloat_ms
```

**Meaning:** Congestion severity increases monotonically.

### 2. Floor Ordering (4-state)

```
floor_red_mbps ≤ floor_soft_red_mbps ≤ floor_yellow_mbps ≤ floor_green_mbps ≤ ceiling_mbps
```

**Meaning:** Each state has a progressively higher floor.

### 3. Floor Ordering (3-state)

```
floor_red_mbps ≤ floor_yellow_mbps ≤ floor_green_mbps ≤ ceiling_mbps
```

**3-state is a special case:** `floor_soft_red_mbps == floor_yellow_mbps`

### 4. Ceiling Constraint

```
floor_*_mbps ≤ ceiling_mbps (for all states)
```

**Meaning:** Floors never exceed ceiling.

### 5. EWMA Alpha Range

```
0 < alpha_baseline < 1
0 < alpha_load < 1
```

**Typical values:**

- `alpha_baseline`: 0.015-0.02 (slow tracking)
- `alpha_load`: 0.20 (fast response)

### 6. Upload Independence (Phase 2A)

Upload state does **not** influence download state.

Configs may use:

- Download: 4-state
- Upload: 3-state

**These are independent control loops.**

---

## Backward Compatibility

### Legacy Configs (Pre-Phase 2)

If config lacks `floor_*_mbps` state-based values:

```yaml
download:
  floor_mbps: 50 # Legacy single floor
  ceiling_mbps: 100
```

**Controller behavior:**

```python
floor_green = floor_yellow = floor_soft_red = floor_red = 50M
# Degrades to 3-state with single floor
```

### Phase 2A Configs (4-state)

If `floor_soft_red_mbps` is missing:

```python
floor_soft_red_mbps = floor_yellow_mbps  # Fallback to 3-state
```

**This ensures smooth upgrades without breaking existing deployments.**

---

## Why Portability Matters

### 1. Testability

A single codebase means:

- One set of unit tests
- One integration test suite
- Bugs fixed once, everywhere

### 2. Maintainability

No need to synchronize:

- DSL-specific patches
- Cable-specific tuning
- Fiber-specific heuristics

**Changes propagate to all deployments automatically.**

### 3. Predictability

Same control algorithm means:

- Deterministic behavior
- Reproducible issues
- Easier debugging

### 4. Extensibility

New features (e.g., Phase 2B time-of-day bias) work on **all link types** immediately.

---

## Future Phases (Remain Config-Only)

### Phase 2B: Time-of-Day Bias

**Proposal:** Use historical congestion data to preemptively adjust floors.

**Implementation:**

```yaml
tod_bias:
  enabled: true
  evening_floor_multiplier: 0.85 # Lower floor during 6-9pm
  morning_floor_multiplier: 1.0 # Normal floor during off-peak
```

**No link-specific logic required.**

Cable naturally has evening congestion; DSL may not. The controller doesn't care — it just applies the config.

### Phase 2C: CAKE Stats Corroboration

**Proposal:** Use CAKE drop/queue stats to validate congestion state.

**Implementation:**

```yaml
cake_corroboration:
  enabled: true
  drop_threshold: 10 # Drops/sec to confirm RED
  queue_threshold: 0.8 # Queue utilization to confirm YELLOW
```

**Same code, all deployments.**

### Phase 2D: Adaptive Thresholds

**Proposal:** Adjust thresholds based on observed variance.

**Implementation:**

```yaml
adaptive_thresholds:
  enabled: true
  variance_window: 300 # 5min history
  threshold_headroom: 1.5 # Multiplier above baseline
```

**Link-agnostic.**

---

## Validation Checklist

Before deploying any new phase or feature:

- [ ] No `if wan_name == ...` logic in controller
- [ ] No medium-specific state machines
- [ ] All new behaviors configurable via YAML
- [ ] Same code runs on all deployments
- [ ] Backward compatibility with existing configs
- [ ] Invariants documented and enforced
- [ ] Reference configs provided (cable, DSL, fiber)

---

## Reference Configurations

### DOCSIS Cable (Spectrum)

**Characteristics:**

- High capacity (900+ Mbps)
- Variable latency (CMTS scheduler)
- Evening congestion
- Upstream affects downstream RTT

**Config strategy:**

- 4-state download (GREEN/YELLOW/SOFT_RED/RED)
- 3-state upload
- Higher floors (550M/350M/275M/200M)
- Moderate bloat tolerance (15/45/80ms)

**File:** `configs/spectrum_config.yaml`

### VDSL2 DSL (AT&T)

**Characteristics:**

- Lower capacity (~95/18 Mbps)
- Stable latency
- Less congestion variance
- Upload sensitive to backoff

**Config strategy:**

- 3-state both directions
- Lower floors (25M/6M)
- Tight bloat tolerance (3/10ms)
- Conservative backoff (0.95 upload)

**File:** `configs/att_config.yaml`

### GPON Fiber (Future)

**Characteristics:**

- Very high capacity (900+ Mbps symmetric)
- Low latency (~5ms)
- Minimal congestion
- Fast recovery possible

**Config strategy:**

- 3-state both directions
- High floors (800M/800M)
- Moderate bloat tolerance (10/30ms)
- Aggressive recovery (20M step-up)

**File:** `configs/dad_fiber_config.yaml` (template exists)

---

## Summary

The CAKE controller is a **portable, link-agnostic congestion control system**.

**Key principles:**

1. Single codebase for all deployments
2. All behavioral differences expressed in configuration
3. No medium-specific or ISP-specific logic
4. State machine driven by thresholds, not link type
5. Backward compatible with legacy configs
6. Future phases remain config-only

**This architecture enables:**

- Rapid deployment to new links (just write a config)
- Consistent behavior across deployments
- Simplified testing and maintenance
- Extensibility without code fragmentation

**Phase 2A demonstrates this:** Spectrum uses 4-state, AT&T uses 3-state, same controller.

**Phase 2B will continue this:** Time-of-day bias via config, no code changes needed.

---

**Next:** See `CONFIG_SCHEMA.md` for formal configuration semantics.
