# Architecture Patterns: WAN-Aware Steering

**Domain:** Multi-signal congestion detection for dual-WAN steering
**Researched:** 2026-03-08

## Current Architecture (Before v1.11)

```
 autorate_continuous (50ms cycle)          steering daemon (500ms cycle)
 ================================          ==============================
 RTT measurement                           RTT measurement (own ping)
        |                                         |
 4-state zone (GREEN/YELLOW/SOFT_RED/RED)  CAKE queue stats (drops, queue)
        |                                         |
 Rate adjustment (CAKE limits)             assess_congestion_state() -> GREEN/YELLOW/RED
        |                                         |
 save_state() --> [state file] --> read --> baseline_rtt extraction
        |                                         |
 (WAN state LOST HERE)                     compute_confidence() -> score
                                                  |
                                           TimerManager -> sustain filtering
                                                  |
                                           SteeringDaemon -> GOOD/DEGRADED decision
```

**Gap:** Autorate's WAN congestion state (the 4-state zone reflecting ISP-level latency) is computed but not persisted in the state file. Steering reads the state file for baseline RTT but has no access to the WAN congestion signal.

## Proposed Architecture (After v1.11)

```
 autorate_continuous (50ms cycle)          steering daemon (500ms cycle)
 ================================          ==============================
 RTT measurement                           RTT measurement (own ping)
        |                                         |
 4-state zone (GREEN/YELLOW/SOFT_RED/RED)  CAKE queue stats (drops, queue)
        |                                         |
 Rate adjustment (CAKE limits)             assess_congestion_state() -> GREEN/YELLOW/RED
        |                                         |
 save_state() --> [state file] --> read --> baseline_rtt + WAN state extraction
                  (now includes                   |
                   congestion section)      WANStateGate (hysteresis filter)
                                                  |
                                           compute_confidence() -> score
                                           (now includes WAN weight)
                                                  |
                                           TimerManager -> sustain filtering
                                                  |
                                           SteeringDaemon -> GOOD/DEGRADED decision
```

### Component Boundaries

| Component | Responsibility | Communicates With | Changed? |
|-----------|---------------|-------------------|----------|
| `WANController.save_state()` | Persist rate controller state + WAN zone | State file (write) | YES: add congestion section |
| `BaselineLoader` -> `AutorateStateLoader` | Read autorate state for baseline RTT + WAN state | State file (read), SteeringDaemon | YES: rename, add wan_state extraction |
| `WANStateGate` (NEW) | Hysteresis filtering of raw WAN state | AutorateStateLoader (input), ConfidenceController (output) | NEW (~50 lines) |
| `compute_confidence()` | Weighted multi-signal confidence scoring | WANStateGate, CakeStats, RTT | YES: add WAN weight |
| `TimerManager` | Sustain-timer hysteresis on confidence score | ConfidenceController | NO CHANGE |
| `SteeringDaemon` | State machine (GOOD/DEGRADED), router control | ConfidenceController, Router | MINIMAL: wire WANStateGate |
| `SteeringConfig` | Load YAML config | Config file | YES: add wan_state section |

### Data Flow

```
[Autorate State File]
    |
    |-- ewma.baseline_rtt    -->  AutorateStateLoader.load()
    |                                    |
    |-- congestion.dl_state  -->  AutorateStateLoader.load()
                                         |
                                  WANStateGate.update(raw_state)
                                         |
                                  confirmed_state (after hysteresis)
                                         |
                                  compute_confidence(signals) -> score
                                         |
                                  [existing TimerManager flow]
```

**Key design decision:** WANStateGate sits between the file reader and the confidence scorer. It is not inside ConfidenceController -- it is a pre-processing filter. This keeps ConfidenceController's contract unchanged: it receives signal snapshots and scores them statelessly. The temporal (stateful) filtering happens in WANStateGate, matching the architectural pattern where "confidence recomputes from scratch every cycle" (see existing docstring in compute_confidence).

## Patterns to Follow

### Pattern 1: Schmitt Trigger (Asymmetric Hysteresis)

**What:** Two different thresholds for entering vs. leaving a state, preventing oscillation at a single threshold boundary.

**When:** A signal fluctuates around a threshold and you need stable, committed decisions.

**Why it fits:** ISP RTT fluctuates. Without hysteresis, WAN state would rapidly toggle RED/GREEN at the boundary, injecting noise into the confidence score.

**Implementation (existing analog in codebase):**
```python
# Already in steering_confidence.py TimerManager:
# - degrade_timer: counts up while confidence >= threshold
# - recovery_timer: counts up while confidence <= threshold
# - Asymmetric: degrade_timer=2s, recovery_timer=3s

# WANStateGate follows same pattern:
# - degrade_counter: counts while raw_state in {RED, SOFT_RED}
# - recovery_counter: counts while raw_state == GREEN
# - Asymmetric: degrade_sustain=1s, recovery_sustain=3s
```

### Pattern 2: Weighted Additive Scoring

**What:** Multiple signals contribute weighted points to a single score. Decision threshold applied to aggregate score, not individual signals.

**When:** You have multiple noisy signals of different reliability and want to require corroboration.

**Why it fits:** No single signal (CAKE drops, RTT, WAN state) is sufficient alone. Weighted scoring requires multiple signals to agree before acting.

**Implementation (existing, extend with WAN weight):**
```python
# Already in steering_confidence.py compute_confidence():
score = 0
if signals.cake_state == "RED":
    score += 50  # Strong signal
if signals.rtt_delta_ms > 80.0:
    score += 15  # Supporting signal
# NEW:
if wan_confirmed_state == "RED":
    score += 30  # Amplifying signal
```

### Pattern 3: Graceful Degradation on Missing Data

**What:** When a data source is unavailable, the system continues with reduced capability rather than failing.

**When:** IPC between processes might fail (stale file, missing key, process crash).

**Why it fits:** If autorate crashes, its state file stops updating. Steering must continue to work using CAKE stats alone.

**Implementation (existing analog):**
```python
# Already in BaselineLoader.load_baseline_rtt():
state = safe_json_load_file(self.config.primary_state_file, ...)
if state is None:
    return None  # Caller uses fallback

# WAN state follows same pattern:
wan_state = loader.load_wan_state()
if wan_state is None:
    # Contributes 0 to confidence (treated as GREEN/unknown)
```

### Pattern 4: Dirty Tracking for Flash Wear

**What:** Only write state file when content has actually changed.

**When:** High-frequency control loops where most cycles produce identical state.

**Why it fits:** dl_zone often stays GREEN for thousands of cycles. Without dirty tracking, every cycle would write to flash storage.

**Implementation (existing):**
```python
# WANControllerState._is_state_changed() already compares dicts
# Must include new congestion field in comparison
```

### Pattern 5: Confidence Scoring Recomputation

**What:** Recompute score from scratch every cycle with no carry-over state.

**When:** You want immediate response to improving signals.

**Why it fits:** When ISP congestion clears, confidence should drop immediately. Temporal behavior belongs in timers (WANStateGate, TimerManager), not in the score.

**Existing docstring:** "Confidence recomputes from scratch every cycle (NO hysteresis). When signals improve, confidence drops immediately."

## Anti-Patterns to Avoid

### Anti-Pattern 1: Direct Signal Passthrough

**What:** Using raw WAN state directly in confidence scoring without hysteresis filtering.

**Why bad:** ISP RTT jitter at zone boundaries causes rapid GREEN/RED oscillation. This injects noise into the confidence score, potentially triggering false steers.

**Instead:** Always filter through WANStateGate before scoring.

### Anti-Pattern 2: Dual Independent Decision Paths

**What:** Having WAN state trigger steering independently of CAKE stats (e.g., "if WAN RED for 5s, steer regardless of CAKE").

**Why bad:** Creates a second steering decision path that bypasses ConfidenceController's multi-signal corroboration. Can cause steering during false ISP RTT spikes when local link is healthy.

**Instead:** WAN state feeds INTO the existing confidence pipeline, never bypasses it.

### Anti-Pattern 3: Coupling Autorate and Steering Cycles

**What:** Making steering wait for or synchronize with autorate cycles.

**Why bad:** The two daemons run at different rates (50ms vs 500ms) and must remain independently scheduled. Coupling creates deadlock risk and violates the daemon independence principle.

**Instead:** Steering reads whatever state file content exists at its own cycle time. State files are the decoupling mechanism.

### Anti-Pattern 4: Modifying ConfidenceController's Statelessness

**What:** Making `compute_confidence()` track state between calls (e.g., internal WAN history).

**Why bad:** The existing design explicitly states "Confidence recomputes from scratch every cycle." State tracking belongs in WANStateGate, not in the scorer.

**Instead:** WANStateGate handles state. It passes a clean, confirmed state string to compute_confidence().

### Anti-Pattern 5: Modifying assess_congestion_state()

**What:** Injecting WAN state into the CAKE congestion assessment function.

**Why bad:** `assess_congestion_state()` maps CAKE-specific signals (RTT delta, drops, queue depth) to a congestion state. It has a clear single responsibility. WAN state is a separate signal class.

**Instead:** WAN state enters at the confidence scoring layer, which is designed to aggregate multiple signal sources.

### Anti-Pattern 6: Double File Reads

**What:** Creating a separate reader class that opens the same autorate state file independently of BaselineLoader.

**Why bad:** Double I/O per cycle, inconsistent snapshots (file could change between reads), code duplication.

**Instead:** Combine into one reader (AutorateStateLoader) that parses once and extracts both baseline_rtt and wan_state.

## Scalability Considerations

Not applicable for this milestone. This is a single-machine, two-daemon system controlling one home network. The architectural patterns are appropriate for this scale. No performance concern: the additional computation (one dict lookup, one string comparison, one integer addition) is negligible compared to RTT measurement and router communication that dominate the cycle budget.

## Sources

All findings from direct codebase analysis:
- `src/wanctl/wan_controller_state.py` -- autorate state persistence schema
- `src/wanctl/autorate_continuous.py` -- WANController.run_cycle(), save_state()
- `src/wanctl/steering/daemon.py` -- BaselineLoader, SteeringDaemon, run_cycle()
- `src/wanctl/steering/steering_confidence.py` -- ConfidenceSignals, compute_confidence(), ConfidenceWeights, TimerManager
- `src/wanctl/steering/congestion_assessment.py` -- assess_congestion_state(), CongestionState
- `src/wanctl/state_utils.py` -- atomic_write_json(), safe_json_load_file()
- `configs/steering.yaml` -- production steering configuration
