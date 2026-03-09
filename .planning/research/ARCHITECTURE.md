# Architecture: WAN-Aware Steering Integration

**Domain:** Multi-signal congestion detection for dual-WAN steering
**Researched:** 2026-03-09
**Confidence:** HIGH (all findings from direct codebase analysis of 2,109-test, 16,493 LOC production system)

## Executive Summary

WAN-aware steering closes a specific gap: autorate measures ISP-level congestion via end-to-end RTT (the WAN path), but this signal never reaches the steering daemon. Steering currently relies only on CAKE queue stats (local link congestion) and its own independent RTT measurement. When the ISP is congested but local CAKE queues are clean (because CAKE is doing its job), steering has no reason to act. This is the scenario v1.11 addresses.

The integration requires exactly 4 changes:
1. Autorate writes its congestion zone to the state file (1 field addition)
2. Steering reads that zone when it already reads baseline_rtt (extend existing reader)
3. A small hysteresis gate filters the raw zone before scoring (new ~60-line class)
4. compute_confidence() gains a WAN weight (1 constant, ~10 lines)

No architectural spine changes. No new files required (all changes fit in existing modules). No new IPC mechanisms. No daemon coupling.

## Current Architecture (Before v1.11)

### System Topology

```
cake-spectrum container              cake-att container
+-----------------------------+      +-------------------+
| autorate_continuous (50ms)  |      | autorate (50ms)   |
|   - RTT measurement        |      |   - RTT meas.     |
|   - 4-state zone logic      |      |   - Rate adjust   |
|   - Rate adjustment         |      +-------------------+
|   - Writes: spectrum_state  |
|     .json                   |
|                             |
| steering_daemon (500ms)     |
|   - Own RTT measurement     |
|   - CAKE queue stats        |
|   - Reads: spectrum_state   |
|     .json (baseline_rtt)    |
|   - Confidence scoring      |
|   - RouterOS mangle control |
+-----------------------------+
```

### Inter-Process Communication

The ONLY communication channel between autorate and steering is the state file at `/run/wanctl/spectrum_state.json` (derived from lock file path), read via `safe_json_load_file()`.

**Current state file schema (written by WANControllerState.save()):**
```json
{
  "download": {
    "green_streak": 0,
    "soft_red_streak": 0,
    "red_streak": 0,
    "current_rate": 940000000
  },
  "upload": {
    "green_streak": 0,
    "soft_red_streak": 0,
    "red_streak": 0,
    "current_rate": 38000000
  },
  "ewma": {
    "baseline_rtt": 24.5,
    "load_rtt": 25.1
  },
  "last_applied": {
    "dl_rate": 940000000,
    "ul_rate": 38000000
  },
  "timestamp": "2026-03-09T12:00:00.000000"
}
```

**What steering reads today:** Only `ewma.baseline_rtt` (via `BaselineLoader.load_baseline_rtt()` at line 575 of daemon.py).

**What autorate computes but does NOT persist:**
- `dl_zone` -- the 4-state congestion zone (GREEN/YELLOW/SOFT_RED/RED) computed by `adjust_4state()` in each cycle
- `ul_zone` -- the 3-state upload zone
- These are used for rate decisions and metrics but lost after each cycle

### The Gap

The steering daemon's `assess_congestion_state()` operates on CAKE queue stats (drops, queue depth) from the local link. It has a 3-state model (GREEN/YELLOW/RED). This works when congestion manifests as local queue buildup.

But when the ISP path is congested BEYOND the CAKE queue (e.g., CMTS scheduler delays on Spectrum cable), CAKE queues remain clean while RTT rises. In this case:
- Autorate sees it: `dl_zone = SOFT_RED` or `RED` (RTT delta > 45ms or >80ms)
- Steering misses it: CAKE drops=0, queue=0, so `assess_congestion_state()` returns GREEN

This means steering won't activate during ISP-level congestion when CAKE is effectively managing the local queue -- exactly the scenario where steering would help most.

## Proposed Architecture (After v1.11)

### Data Flow (Changed Components Marked)

```
autorate_continuous.save_state()
        |
        v
[spectrum_state.json]
    |-- ewma.baseline_rtt         (existing)
    |-- ewma.load_rtt             (existing)
    |-- congestion.dl_state  ---- (NEW: "GREEN"|"YELLOW"|"SOFT_RED"|"RED")
    |-- congestion.ul_state  ---- (NEW: "GREEN"|"YELLOW"|"RED")
    |-- congestion.timestamp ---- (NEW: ISO 8601)
        |
        v
AutorateStateLoader.load()  ----- (RENAMED from BaselineLoader)
    |-- baseline_rtt              (existing extraction)
    |-- wan_dl_state              (NEW extraction)
        |
        v
WANStateGate.update(raw_state) -- (NEW: hysteresis filter)
    |-- confirmed_state           (filtered, stable signal)
        |
        v
compute_confidence(signals)  ---- (MODIFIED: add WAN weight)
    |-- score (0-100)
        |
        v
[existing ConfidenceController / TimerManager pipeline, UNCHANGED]
```

### Component Inventory: NEW vs. MODIFIED vs. UNCHANGED

| Component | Status | File | Change Description |
|-----------|--------|------|--------------------|
| `WANControllerState.save()` | MODIFIED | `wan_controller_state.py` | Add `congestion` section to state dict |
| `WANControllerState._is_state_changed()` | MODIFIED | `wan_controller_state.py` | Include `congestion` in dirty tracking |
| `WANController.save_state()` | MODIFIED | `autorate_continuous.py` | Pass `dl_zone`, `ul_zone` to save() |
| `WANController.run_cycle()` | MODIFIED | `autorate_continuous.py` | Capture zones before save_state call |
| `BaselineLoader` -> `AutorateStateLoader` | RENAMED+MODIFIED | `steering/daemon.py` | Add `load_wan_state()`, rename class |
| `WANStateGate` | **NEW** | `steering/wan_state_gate.py` OR inline in `steering/daemon.py` | ~60 lines, hysteresis filter |
| `compute_confidence()` | MODIFIED | `steering/steering_confidence.py` | Add WAN weight constant + scoring branch |
| `ConfidenceSignals` | MODIFIED | `steering/steering_confidence.py` | Add `wan_state: str` field (default "GREEN") |
| `ConfidenceWeights` | MODIFIED | `steering/steering_confidence.py` | Add `WAN_RED_STATE`, `WAN_SOFT_RED_STATE` |
| `SteeringDaemon.__init__()` | MODIFIED | `steering/daemon.py` | Wire WANStateGate |
| `SteeringDaemon.run_cycle()` | MODIFIED | `steering/daemon.py` | Read WAN state, pass through gate to confidence |
| `SteeringConfig` | MODIFIED | `steering/daemon.py` | Add wan_state config section |
| `steering.yaml` | MODIFIED | `configs/steering.yaml` | Add wan_state config block |
| `SteeringHealthHandler` | MODIFIED | `steering/health.py` | Expose WAN state in health endpoint |
| `assess_congestion_state()` | **UNCHANGED** | `steering/congestion_assessment.py` | NOT touched (CAKE-only responsibility) |
| `TimerManager` | **UNCHANGED** | `steering/steering_confidence.py` | NOT touched |
| `FlapDetector` | **UNCHANGED** | `steering/steering_confidence.py` | NOT touched |
| `CakeStatsReader` | **UNCHANGED** | `steering/cake_stats.py` | NOT touched |
| `StateManager` / `SteeringStateManager` | **UNCHANGED** | `state_manager.py` | NOT touched |
| `RouterOSController` | **UNCHANGED** | `steering/daemon.py` | NOT touched |

### Architectural Spine Compliance

Checking each spine rule from CLAUDE.md:

1. **"All decisions based on RTT delta (not absolute RTT)"** -- COMPLIANT. WAN state derived from RTT delta in autorate. Steering uses it as an additional confidence signal, not a direct decision.

2. **"Baseline must remain frozen during load"** -- COMPLIANT. No changes to baseline logic.

3. **"Rate decreases: immediate / Rate increases: require sustained GREEN"** -- COMPLIANT. No changes to rate logic.

4. **"Only secondary WAN makes routing decisions"** -- COMPLIANT. Only cake-spectrum's steering daemon reads the signal.

5. **"Steering is binary: enabled or disabled"** -- COMPLIANT. WAN state feeds confidence score, which drives the existing binary GOOD/DEGRADED state machine.

6. **"Only new latency-sensitive connections rerouted"** -- COMPLIANT. No change to mangle rule behavior.

7. **"Autorate baseline RTT is authoritative (steering must not alter)"** -- COMPLIANT. Steering reads, never writes.

**No spine rules are violated by this design.**

## Detailed Component Design

### 1. State File Extension (autorate side)

**File:** `wan_controller_state.py`

Add a `congestion` key to the state dict alongside existing `download`, `upload`, `ewma`, `last_applied`:

```python
# In WANControllerState.save():
state = {
    "download": download,
    "upload": upload,
    "ewma": ewma,
    "last_applied": last_applied,
    "congestion": {          # NEW
        "dl_state": dl_state,  # "GREEN"|"YELLOW"|"SOFT_RED"|"RED"
        "ul_state": ul_state,  # "GREEN"|"YELLOW"|"RED"
    },
    "timestamp": datetime.datetime.now().isoformat(),
}
```

**Impact on dirty tracking:** `_is_state_changed()` must include `congestion` in its comparison dict. Since `dl_zone` changes rarely (stays GREEN for thousands of cycles), this adds negligible write overhead.

**Backward compatibility:** Steering's reader must handle state files without the `congestion` key (produced by older autorate versions during rolling upgrades).

### 2. AutorateStateLoader (renamed BaselineLoader)

**File:** `steering/daemon.py` (inline, where BaselineLoader currently lives)

Rename `BaselineLoader` to `AutorateStateLoader`. Add `load_wan_state()` method that reads `congestion.dl_state` from the same file already opened for baseline_rtt:

```python
def load_wan_state(self) -> str | None:
    """Load WAN congestion state from autorate state file.

    Returns: "GREEN", "YELLOW", "SOFT_RED", "RED", or None if unavailable.
    """
    state = safe_json_load_file(
        self.config.primary_state_file,
        logger=self.logger,
        error_context="autorate state",
    )
    if state is None:
        return None

    congestion = state.get("congestion", {})
    dl_state = congestion.get("dl_state")

    if dl_state not in ("GREEN", "YELLOW", "SOFT_RED", "RED"):
        return None  # Invalid or missing -- caller treats as unknown

    return dl_state
```

**Design decision -- single read vs. combined read:** The existing `load_baseline_rtt()` opens the file independently. With two pieces of data needed from the same file, refactor to a single read that returns both:

```python
@dataclass
class AutorateSnapshot:
    baseline_rtt: float | None
    wan_dl_state: str | None  # "GREEN"|"YELLOW"|"SOFT_RED"|"RED" or None
    file_age_seconds: float | None
```

This eliminates the double-read anti-pattern.

### 3. WANStateGate (new component)

**Location decision:** Small enough (~60 lines) to live in `steering/daemon.py` alongside AutorateStateLoader. If it grows, can be extracted later. Creating a new file for 60 lines is over-engineering.

**Purpose:** Applies Schmitt-trigger hysteresis to the raw WAN state before it enters the confidence scorer. This prevents rapid GREEN/RED oscillation at zone boundaries from injecting noise.

```python
class WANStateGate:
    """Hysteresis filter for WAN congestion state.

    Prevents rapid oscillation of WAN state from causing
    confidence score instability. Requires sustained bad state
    before confirming degradation, and sustained good state
    before confirming recovery.
    """

    def __init__(
        self,
        degrade_cycles: int,     # Cycles of RED/SOFT_RED before confirming
        recovery_cycles: int,    # Cycles of GREEN before clearing
        staleness_threshold: float,  # Seconds before treating state as stale
        logger: logging.Logger,
    ):
        ...

    def update(self, raw_state: str | None, file_age: float | None) -> str:
        """Process raw WAN state through hysteresis.

        Returns: confirmed state ("GREEN", "YELLOW", "SOFT_RED", "RED")
        Defaults to "GREEN" for None/stale/unknown input.
        """
        ...
```

**Hysteresis parameters (from milestone context):**
- Degrade: ~1 second sustained RED/SOFT_RED (at steering's 500ms cycle = 2 cycles)
- Recovery: ~3 seconds sustained GREEN (at 500ms = 6 cycles)
- Staleness: 5 seconds (if state file not updated in 5s, treat as unknown/GREEN)

**Staleness detection:** The state file's `timestamp` field (ISO 8601) or filesystem mtime. BaselineLoader already has `_check_staleness()` with `STALE_BASELINE_THRESHOLD_SECONDS = 300` (5 minutes). For WAN state, a tighter threshold is needed: 5 seconds (proposed in milestone context), because the steering decision should not be based on a 5-minute-old congestion reading.

### 4. Confidence Scoring Extension

**File:** `steering/steering_confidence.py`

Add WAN state weights to `ConfidenceWeights`:

```python
class ConfidenceWeights:
    # Existing weights...
    RED_STATE = 50
    SOFT_RED_SUSTAINED = 25
    # ...

    # NEW: WAN-level congestion signals (from autorate state)
    WAN_RED = 30       # ISP-level congestion confirmed by autorate
    WAN_SOFT_RED = 15  # ISP-level RTT-only congestion
```

Add `wan_state` field to `ConfidenceSignals`:

```python
@dataclass
class ConfidenceSignals:
    cake_state: str
    rtt_delta_ms: float
    drops_per_sec: float
    queue_depth_pct: float
    # ... existing fields ...

    # NEW: WAN-level congestion state from autorate
    wan_state: str = "GREEN"  # Default GREEN = no contribution
```

Extend `compute_confidence()`:

```python
# After existing CAKE state scoring:
if signals.wan_state == "RED":
    score += ConfidenceWeights.WAN_RED
    contributors.append("wan_RED")
elif signals.wan_state == "SOFT_RED":
    score += ConfidenceWeights.WAN_SOFT_RED
    contributors.append("wan_SOFT_RED")
```

**Weight rationale:**
- WAN_RED (30) is lower than CAKE RED_STATE (50) because WAN state is a secondary/amplifying signal, not primary. CAKE stats remain the authoritative local signal.
- WAN_RED (30) alone is not enough to trigger steering (threshold is 55). It requires corroboration from at least one other signal (YELLOW=10 + WAN_RED=30 = 40, still under 55).
- WAN_RED (30) + CAKE YELLOW (10) + RTT_DELTA_HIGH (15) = 55, which triggers the sustain timer. This is the intended "WAN amplifies weak local signals" behavior.
- WAN_SOFT_RED (15) is a weak signal, acting as a tiebreaker when other signals are marginal.

### 5. Configuration Extension

**File:** `configs/steering.yaml`

```yaml
# WAN-aware steering (v1.11)
# Reads autorate's WAN congestion state as additional failover signal
wan_state:
  enabled: true
  staleness_threshold_sec: 5.0    # Ignore WAN state older than 5s
  degrade_sustain_cycles: 2       # ~1s at 500ms cycle
  recovery_sustain_cycles: 6      # ~3s at 500ms cycle
```

### 6. Health Endpoint Extension

**File:** `steering/health.py`

Add WAN state to the health response:

```python
health["wan_state"] = {
    "raw": raw_wan_state,           # Direct from state file
    "confirmed": confirmed_state,    # After hysteresis gate
    "file_age_seconds": file_age,
    "stale": file_age > staleness_threshold if file_age else True,
}
```

## Integration Points With Existing Code

### Integration Point 1: WANController.run_cycle() -> save_state()

Currently at line 1430-1441 of `autorate_continuous.py`:
```python
dl_zone, dl_rate, dl_transition_reason = self.download.adjust_4state(...)
ul_zone, ul_rate, ul_transition_reason = self.upload.adjust(...)
```

The zones are local variables. They need to be stored as instance variables (or passed through) so `save_state()` can include them:

```python
# Store for state persistence
self._last_dl_zone = dl_zone
self._last_ul_zone = ul_zone
```

Then `save_state()` passes them to `WANControllerState.save()`.

**Risk:** LOW. These are simple string assignments. No algorithm changes.

### Integration Point 2: SteeringDaemon.run_cycle() cycle flow

Currently at line 1305-1478 of `steering/daemon.py`:

1. `update_baseline_rtt()` -- reads state file for baseline
2. CAKE stats collection
3. RTT measurement
4. State management (delta, EWMA, signals, state machine)

WAN state injection happens at step 1 (combined with baseline read) and feeds into step 4:

```python
# Step 1: Load autorate state (baseline + WAN state)
snapshot = self.autorate_loader.load()
if not snapshot.baseline_rtt:
    return False

# Step 1b: Filter WAN state through hysteresis gate
wan_confirmed = self.wan_gate.update(snapshot.wan_dl_state, snapshot.file_age)

# ... steps 2-3 unchanged ...

# Step 4: Build signals with WAN state
signals = ConfidenceSignals(
    cake_state=state.get("congestion_state", "GREEN"),
    rtt_delta_ms=delta,
    drops_per_sec=float(cake_drops),
    queue_depth_pct=float(queued_packets),
    wan_state=wan_confirmed,  # NEW
    # ... existing history fields ...
)
```

### Integration Point 3: ConfidenceController.evaluate() signal conversion

Currently at line 1150-1158:
```python
phase2b_signals = ConfidenceSignals(
    cake_state=state.get("congestion_state", "GREEN"),
    rtt_delta_ms=signals.rtt_delta,
    ...
)
```

This is where `wan_state` gets passed through. Since ConfidenceSignals gets a default of "GREEN" for the new field, existing call sites that don't set it will behave identically to pre-v1.11.

## Suggested Build Order

Dependencies flow downward. Each phase builds on the previous.

### Phase 1: State File Extension (Writer Side)

**Changes:** `wan_controller_state.py`, `autorate_continuous.py`
**Tests:** Verify state file contains congestion section, dirty tracking includes it, backward compat (old readers ignore new field)
**Why first:** The data source must exist before consumers can use it. Zero risk to steering daemon -- it simply ignores the new field until Phase 3.

### Phase 2: WANStateGate + AutorateStateLoader (Reader Side)

**Changes:** `steering/daemon.py` (rename BaselineLoader, add WANStateGate class)
**Tests:** Unit tests for WANStateGate hysteresis logic, AutorateStateLoader with/without congestion field, staleness detection
**Why second:** Reader must exist before it can be wired into the scoring pipeline. WANStateGate is testable in isolation.

### Phase 3: Confidence Scoring Extension

**Changes:** `steering/steering_confidence.py` (ConfidenceWeights, ConfidenceSignals, compute_confidence)
**Tests:** Verify WAN weights contribute correctly, verify default "GREEN" produces zero contribution, verify combined scoring scenarios
**Why third:** Depends on ConfidenceSignals having the wan_state field from Phase 2's data model.

### Phase 4: Wiring + Config + Health

**Changes:** `steering/daemon.py` (SteeringDaemon.__init__, run_cycle), `steering/health.py`, `configs/steering.yaml`
**Tests:** Integration test of full run_cycle with WAN state injection, health endpoint includes WAN state, config loading
**Why last:** End-to-end wiring depends on all components existing. Config is the final enablement mechanism.

### Phase 5 (Optional): Observability + Tuning

**Changes:** SQLite metrics for WAN state, log format updates
**Tests:** Verify metrics recorded, log grep for WAN state decisions

## Anti-Patterns to Avoid

### 1. Direct Signal Passthrough (No Hysteresis)

Using raw WAN state directly in confidence scoring without WANStateGate. ISP RTT jitter at zone boundaries (e.g., delta oscillating around 45ms SOFT_RED threshold) causes rapid state changes that inject noise into the confidence score.

**Instead:** Always filter through WANStateGate.

### 2. Dual Independent Decision Paths

Having WAN state trigger steering independently of CAKE stats (e.g., "if WAN RED for 5s, steer regardless of CAKE"). This creates a second decision path bypassing ConfidenceController's multi-signal corroboration.

**Instead:** WAN state feeds INTO the existing confidence pipeline as an additive weight. It amplifies weak local signals but cannot trigger steering alone.

### 3. Modifying assess_congestion_state()

Injecting WAN state into the CAKE congestion assessment function. `assess_congestion_state()` has a clear single responsibility: map CAKE-specific signals to a 3-state congestion model. WAN state is a different signal class.

**Instead:** WAN state enters at the confidence scoring layer.

### 4. Coupling Daemon Cycles

Making steering wait for or synchronize with autorate cycles. The daemons run at different rates (50ms vs 500ms) and must remain independently scheduled.

**Instead:** Steering reads whatever state exists at its own cycle time. Staleness detection handles the case where autorate is slow/crashed.

### 5. Double File Reads

Creating a separate reader for WAN state that opens the same state file independently of baseline_rtt reading. Double I/O per cycle, inconsistent snapshots.

**Instead:** Single read via AutorateStateLoader, returns both values.

### 6. Overweighting WAN State

Setting WAN_RED weight so high that it can trigger steering alone (e.g., WAN_RED=55 >= steer_threshold). This would bypass the multi-signal corroboration design.

**Instead:** WAN_RED=30 requires at least one corroborating signal to reach threshold.

## Scalability Considerations

Not applicable. Single-machine, two-daemon system controlling one home network. The additional computation (one dict lookup, one string comparison, one integer addition per steering cycle) is negligible compared to RTT measurement (~5-10ms) and router communication (~0.1-0.2ms) that dominate the cycle budget.

## Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Stale state file causes steering based on old WAN state | Medium | Medium | 5-second staleness threshold, defaults to GREEN |
| WAN state oscillation at zone boundary | Low | Medium | WANStateGate hysteresis filter |
| Autorate crash leaves permanent WAN RED in state file | Medium | Low | Staleness detection clears after 5s |
| Rolling upgrade: old autorate, new steering | None | Certain | Default "GREEN" when congestion key missing |
| Rolling upgrade: new autorate, old steering | None | Certain | Old steering ignores unknown keys |
| Flash wear from new state field | None | None | dl_zone rarely changes (stays GREEN 99%+ of cycles) |

## Sources

All findings from direct codebase analysis (HIGH confidence):
- `src/wanctl/wan_controller_state.py` -- WANControllerState schema, save(), dirty tracking
- `src/wanctl/autorate_continuous.py` -- WANController.run_cycle() (lines 1378-1568), save_state() (lines 1613-1638), adjust_4state() (lines 706-828)
- `src/wanctl/steering/daemon.py` -- BaselineLoader (lines 567-638), SteeringDaemon (lines 645-1478), run_cycle() (lines 1305-1478), SteeringConfig (lines 133-410), build_steering_schema() (lines 415-442)
- `src/wanctl/steering/steering_confidence.py` -- ConfidenceWeights, ConfidenceSignals, compute_confidence(), ConfidenceController
- `src/wanctl/steering/congestion_assessment.py` -- assess_congestion_state() (UNCHANGED)
- `src/wanctl/steering/health.py` -- SteeringHealthHandler._get_health_status()
- `src/wanctl/steering/cake_stats.py` -- CongestionSignals dataclass, CakeStatsReader
- `src/wanctl/state_utils.py` -- atomic_write_json(), safe_json_load_file()
- `src/wanctl/state_manager.py` -- SteeringStateManager
- `configs/steering.yaml` -- production steering configuration
- `configs/spectrum.yaml` -- production autorate configuration
- `docs/ARCHITECTURE.md` -- Portable Controller Architecture (portability invariants)
- `docs/STEERING.md` -- Steering design principles
