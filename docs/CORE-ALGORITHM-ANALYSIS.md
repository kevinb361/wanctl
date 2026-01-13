# Core Algorithm Analysis

**Analysis Date:** 2026-01-13
**Phase:** 07-core-algorithm-analysis
**Purpose:** Guide Phases 14-15 refactoring with risk-assessed opportunities

---

## Executive Summary

- **Total opportunities identified:** 12 (LOW: 6, MEDIUM: 4, HIGH: 2)
- **Recommended approach:** Low-risk extractions first, core algorithm changes require explicit approval
- **Expected impact:** Improved testability and maintainability without behavior changes
- **Key insight:** Both controllers share complexity patterns (long `run_cycle()` methods, state machines, EWMA smoothing) - refactoring benefits are multiplicative

### Risk Distribution

| Risk Level | Count | Scope |
|------------|-------|-------|
| LOW | 6 | Pure extractions, no algorithm changes |
| MEDIUM | 4 | Structural improvements, requires testing |
| HIGH | 2 | Core algorithm changes, requires explicit approval |

---

## WANController Analysis

**File:** `src/wanctl/autorate_continuous.py`
**Lines:** 473 (lines 562-1034, 33.5% of file)
**Methods:** 10

### Current Structure

| Method | Lines | Complexity | Primary Responsibility |
|--------|-------|------------|------------------------|
| `__init__` | 82 | MEDIUM | Initialize controllers, load state |
| `measure_rtt` | 42 | MEDIUM | Ping hosts, aggregate RTT |
| `update_ewma` | 15 | LOW | Update baseline/load EWMAs |
| `verify_local_connectivity` | 13 | LOW | Check gateway reachability |
| `verify_tcp_connectivity` | 23 | MEDIUM | TCP handshake checks |
| `verify_connectivity_fallback` | 20 | LOW | Orchestrate fallback checks |
| **`run_cycle`** | **176** | **HIGH** | **Main control loop** |
| `load_state` | 40 | MEDIUM | Restore persisted state |
| `save_state` | 32 | LOW | Persist state to disk |

### Complexity Hotspots

**1. `run_cycle()` (Lines 785-960) - PRIMARY HOTSPOT**
- **Lines:** 176 (11% of class)
- **Responsibilities:** 6+ distinct operations
- **Nesting:** 4 levels deep
- **Branches:** 7+ execution paths
- **Issues:**
  - Multiple concerns intermixed (measurement, connectivity, rate control, persistence)
  - Fallback mode selection: 3 modes × multiple cycle states = 6+ branches
  - State mutation spread throughout method
  - Difficult to test individual execution paths

**2. `__init__()` (Lines 564-644) - SECONDARY HOTSPOT**
- **Lines:** 82
- **Issues:** Multiple initialization phases, high parameter coupling, disk I/O during construction

**3. `measure_rtt()` (Lines 645-686) - TERTIARY HOTSPOT**
- **Lines:** 42
- **Issues:** Concurrent futures complexity, multiple failure modes, non-deterministic behavior

### Refactoring Opportunities

#### LOW Risk

**W1. Extract Fallback Connectivity Logic**
- **Location:** Lines 798-858 (61 lines within `run_cycle()`)
- **Proposed:** `handle_icmp_failure() -> tuple[bool, float | None]`
- **Benefits:** 32% reduction in `run_cycle()`, isolates fallback logic for independent testing
- **Testing:** Mock connectivity checks, verify return values
- **Dependencies:** None (self-contained)

**W2. Extract Flash Wear Protection Logic**
- **Location:** Lines 892-942 (51 lines within `run_cycle()`)
- **Proposed:** `apply_rate_changes_if_needed(dl_rate, ul_rate) -> bool`
- **Benefits:** Separates flash wear protection (architectural invariant) from cycle logic
- **Testing:** Mock router, verify skip behavior on unchanged rates
- **Dependencies:** None (uses existing instance variables)

**W3. Simplify Concurrent RTT Measurement**
- **Location:** Lines 654-683 (30 lines in `measure_rtt()`)
- **Proposed:** Move concurrent futures logic to `rtt_measurement.py` utility
- **Benefits:** Reduces `measure_rtt()` from 42 to ~15 lines, reusable by steering daemon
- **Testing:** Test concurrent ping logic independently
- **Dependencies:** Requires changes to `src/wanctl/rtt_measurement.py`

**Combined Impact:** Reduces `run_cycle()` from 176 to ~70 lines (60% reduction)

#### MEDIUM Risk

**W4. Extract EWMA Update Validation Logic**
- **Location:** Lines 688-702 (15 lines in `update_ewma()`)
- **Proposed:** Add `_update_baseline_if_idle()` helper with explicit conditional logic
- **Benefits:** Makes baseline update conditional logic more explicit, adds debug logging
- **Why MEDIUM:** Touches core algorithm (baseline update threshold)
- **Testing:** Verify baseline freezes under load, updates when idle
- **Approval:** Defer to Phase 14 implementation

**W5. Extract State Persistence to Dedicated Manager**
- **Location:** Lines 962-1033 (72 lines for load/save)
- **Proposed:** Create `WANControllerState` class following steering daemon's `StateManager` pattern
- **Benefits:** Separates persistence from business logic, enables reuse
- **Why MEDIUM:** Changes initialization flow, schema migration concerns
- **Testing:** State compatibility tests required

### Protected Zones

| Zone | Lines | Why Protected | Safe Changes | Prohibited Changes |
|------|-------|---------------|--------------|-------------------|
| **Baseline Update Threshold** | 688-702 | Prevents baseline drift under load | Make threshold configurable, add logging | Remove conditional, change formula |
| **Flash Wear Protection** | 898, 937-938 | Prevents NAND flash wear (100K-1M writes) | Extract to method, add metrics | Remove change detection |
| **Rate Limiting Logic** | 905-917 | Prevents RouterOS API overload | Make limits configurable | Remove rate limiting |
| **QueueController Transitions** | QueueController class | Core autorate algorithm | Extract state logic, add logging | Modify thresholds/hysteresis |

---

## SteeringDaemon Analysis

**File:** `src/wanctl/steering/daemon.py`
**Lines:** 1,179
**Functions/Methods:** 24 (5 module-level, 19 methods across 5 classes)

### Current Structure

**Classes:**
- `SteeringConfig` (188-316): Configuration loading
- `RouterOSController` (400-456): Mangle rule control
- `BaselineLoader` (492-502): Baseline RTT synchronization
- `SteeringDaemon`: Core daemon class
- `SteeringStateSchema`: State validation

**Key Methods:**
| Method | Lines | Complexity | Primary Responsibility |
|--------|-------|------------|------------------------|
| `run_cycle` | 129 | HIGH | Orchestrate steering cycle |
| `_update_state_machine_cake_aware` | 104 | HIGH | CAKE-aware state transitions |
| `_update_state_machine_legacy` | 74 | MEDIUM | RTT-only state transitions |
| `main` | 197 | HIGH | Daemon lifecycle |
| `_load_specific_fields` | 129 | MEDIUM | Config field loading |

### Complexity Hotspots

**1. `run_cycle()` (Lines 849-977) - PRIMARY HOTSPOT**
- **Lines:** 129 (11% of file)
- **Responsibilities:** 8+ distinct responsibilities
- **Issues:**
  - Orchestrates entire steering cycle (baseline → measurement → assessment → decision → persistence)
  - CAKE-aware vs legacy mode branching throughout
  - Mixed abstraction levels (high-level orchestration + low-level EWMA math)
  - Inline history management (W4 fix)

**2. `_update_state_machine_cake_aware()` (Lines 669-772) - FLAGGED IN CONCERNS.md**
- **Lines:** 104 (9% of file)
- **Cyclomatic Complexity:** ~12
- **Issues:**
  - Multiple state transitions (good_count, red_count, current_state) interdependent
  - State normalization adds branches (legacy name handling)
  - Routing integration embedded in state logic
  - CONCERNS.md flagged: "State machine state transitions fragile"

**3. `_update_state_machine_legacy()` (Lines 774-847)**
- **Lines:** 74
- **Issues:** Code duplication with CAKE-aware version (~60% overlap)

**4. `main()` (Lines 983-1179) - LARGEST FUNCTION**
- **Lines:** 197 (17% of file)
- **Responsibilities:** 12+ (arg parsing, signal registration, config load, logging setup, component initialization, lock acquisition, daemon creation, systemd watchdog, event loop, failure tracking, cleanup)

### Refactoring Opportunities

#### LOW Risk

**S1. Extract EWMA Smoothing Logic**
- **Location:** Lines 909-923 (15 lines in `run_cycle()`)
- **Proposed:** `update_ewma_smoothing(delta, queued_packets)`
- **Benefits:** Can test EWMA smoothing without full cycle execution
- **Dependencies:** None (self-contained extraction)

**S2. Extract CAKE Stats Collection**
- **Location:** Lines 863-898 (36 lines in `run_cycle()`)
- **Proposed:** `collect_cake_stats() -> tuple[int, int]`
- **Benefits:** Test CAKE read failures without full cycle, preserves W8 fix
- **Dependencies:** None (self-contained extraction)

**S3. Extract Configuration Field Loading Groups**
- **Location:** Lines 188-316 (129 lines in `_load_specific_fields()`)
- **Proposed:** Split into 12 focused methods (`_load_router_config()`, etc.)
- **Benefits:** Test individual config sections, easier debugging
- **Dependencies:** None (structural refactoring)

#### MEDIUM Risk

**S4. Extract State Machine Routing Control**
- **Location:** Lines 706-717, 749-760 (24 lines total)
- **Proposed:** `execute_steering_transition(from_state, to_state, enable_steering) -> bool`
- **Benefits:** Test routing transitions without state machine complexity
- **Why MEDIUM:** Requires state machine methods to use return value
- **Dependencies:** Both state machine methods must be updated

**S5. Extract Daemon Control Loop from main()**
- **Location:** Lines 1117-1154 (38 lines)
- **Proposed:** `run_daemon_loop(daemon, config, logger, shutdown_event) -> int`
- **Benefits:** Test control loop without full process lifecycle
- **Why MEDIUM:** Watchdog logic tightly coupled to failure tracking
- **Dependencies:** Shutdown event handling must remain identical

#### HIGH Risk (Requires Explicit Approval)

**S6. Unify State Machine Methods (CAKE-aware + Legacy)**
- **Location:** Lines 669-772 + 774-847 (178 lines total)
- **Proposed:** `_update_state_machine_unified(signals: CongestionSignals) -> bool`
- **Benefits:** 40% reduction in state machine code, single test suite
- **Why HIGH:** Touches core state machine logic (protected zone), unifies two parallel implementations
- **Dependencies:** Must verify equivalence: `assessment == RED` ≡ `delta > bad_threshold_ms`
- **Recommendation:** DEFER to Phase 15 with validation period

**S7. Confidence Scoring Integration**
- **Current:** Phase 2B controller (`steering_confidence.py`, 644 lines) exists but unused
- **Proposed:** Replace hysteresis with confidence scoring via config flag
- **Benefits:** Multi-signal scoring (0-100), built-in flap detection, better decisions
- **Why HIGH:** Behavioral change, config compatibility issues, state persistence schema changes
- **Migration Path:**
  1. Add confidence controller alongside hysteresis (dry-run mode, log only)
  2. Compare decisions over 1-week validation period
  3. Switch via config flag after validation
  4. Remove legacy hysteresis code
- **Recommendation:** INTEGRATE in Phase 15 with hybrid approach (config flag for gradual rollout)

### Confidence Scoring Integration Details

**Current Hysteresis Logic:**
```python
if assessment == CongestionState.RED:
    red_count += 1
    if red_count >= red_samples_required:
        # Enable steering
elif assessment == CongestionState.GREEN:
    good_count += 1
    if good_count >= green_samples_required:
        # Disable steering
```

**Proposed Confidence Integration:**
```python
decision = confidence_controller.evaluate(signals, current_state)
if decision == "ENABLE_STEERING":
    # Timer expired, enable steering
elif decision == "DISABLE_STEERING":
    # Recovery timer expired, disable steering
```

**What Changes:**
- State counters (red_count, good_count) → TimerState
- Sample thresholds → Duration thresholds (sustain_duration_sec)
- No flap detection → Built-in FlapDetector with penalty

**What's Protected During Integration:**
- Baseline RTT bounds (10-60ms, C4 fix)
- RouterOS mangle rule validation (C2 fix)
- EWMA smoothing (alpha bounds, C5 fix)

### Protected Zones

| Zone | Lines | Why Protected | Safe Changes | Prohibited Changes |
|------|-------|---------------|--------------|-------------------|
| **State Transition Logic** | 669-847 | Core steering algorithm, carefully tuned asymmetric hysteresis | Extract routing control, add logging | Change counter reset logic, modify thresholds |
| **Baseline RTT Validation** | 492-502 | Security fix C4, prevents malicious baseline attacks | Make bounds configurable | Remove bounds check, widen without justification |
| **EWMA Smoothing** | 909-923 | Numeric stability C5, production-tuned alphas | Extract to method, make alpha configurable | Change formula, remove bounds validation |
| **RouterOS Mangle Control** | 400-456 | Security C2 + reliability W6 (command injection, retry with verification) | Add metrics, improve errors | Remove validation, remove retry |
| **Signal Handling** | 100-144 | Concurrency W5, graceful shutdown | Add logging, extract to shared module | Replace Event with boolean, remove registration |

---

## Cross-Cutting Patterns

### Common Complexity Drivers

Both controllers share these complexity sources:

1. **State Machine Transitions**
   - WANController: 4-state download, 3-state upload (delegated to QueueController)
   - SteeringDaemon: GOOD/DEGRADED with asymmetric hysteresis
   - Both use streak counting (green_streak, red_count, good_count)

2. **EWMA Smoothing Parameters**
   - Both use same formula: `(1 - alpha) * current + alpha * new_value`
   - Both share `ewma_update()` from `congestion_assessment.py`
   - Both need alpha bounds validation (C5 fix)

3. **Multi-Signal Decision Making**
   - WANController: RTT delta + CAKE queue depth (via QueueController)
   - SteeringDaemon: RTT delta + CAKE drops + queue depth

### Shared Refactoring Opportunities

| Opportunity | Benefits Both | Implementation |
|-------------|---------------|----------------|
| Concurrent RTT measurement utility | Reduce duplication, shared testing | Move to `rtt_measurement.py` |
| State persistence manager pattern | Consistent state handling | WANController adopts steering's StateManager |
| Signal handler standardization | Already done in Phase 6 | N/A |
| Rate limiter utility | WANController has it, steering could use | Extract to shared module |

### Architectural Considerations

**Interface Contracts:**
- Autorate state file schema (baseline_rtt field) consumed by steering
- WANController owns baseline RTT updates
- SteeringDaemon is read-only consumer via BaselineLoader

**Dependencies:**
- WANController → SteeringDaemon: One-way (state file only)
- Can refactor independently (Phase 14 and 15 don't block each other)
- Phase 14 concurrent RTT utility benefits Phase 15

**State File Schema:**
- Must be preserved during refactoring
- Migration required if adding/removing fields
- Both controllers share common fields (baseline_rtt, ewma values)

---

## Implementation Guidance for Phases 14-15

### Phase 14: WANController Refactoring

**Recommended Order:**

1. **W1: Extract Fallback Connectivity Logic** (LOW)
   - Independent, easy to verify
   - Largest complexity reduction (32% of `run_cycle()`)
   - Implementation: 2-3 hours

2. **W2: Extract Flash Wear Protection Logic** (LOW)
   - Clear boundaries, no algorithm changes
   - Protects critical hardware invariant
   - Implementation: 2-3 hours

3. **W3: Simplify Concurrent RTT Measurement** (LOW)
   - Reusable utility for Phase 15
   - Independent of WANController
   - Implementation: 3-4 hours

4. **W4: Extract EWMA Update Validation** (MEDIUM - EXPLICIT APPROVAL REQUIRED)
   - Touches baseline update threshold
   - Requires validation tests
   - Implementation: 4-6 hours

5. **W5: Extract State Persistence Manager** (MEDIUM)
   - Lower priority than 1-3
   - Establishes pattern for consistency
   - Implementation: 6-8 hours

**Testing Strategy:**

| Phase | Focus | Tests |
|-------|-------|-------|
| Before | Baseline capture | Test all fallback modes, flash wear, rate limiting |
| Per-Opportunity | Unit tests | New extracted methods |
| After | Regression | Verify existing integration tests pass |
| Production | Validation | 24-hour stability, soak-monitor.sh |

**Rollback Plan:**
- Each refactoring is atomic commit
- Revert individual commit if issues found
- Production validation after each LOW/MEDIUM change

### Phase 15: SteeringDaemon Refactoring

**Recommended Order:**

1. **S1: Extract EWMA Smoothing Logic** (LOW)
   - Pure math extraction
   - Implementation: 1-2 hours

2. **S2: Extract CAKE Stats Collection** (LOW)
   - Preserves W8 fix
   - Implementation: 2-3 hours

3. **S3: Extract Configuration Field Groups** (LOW)
   - Structural refactoring
   - Implementation: 3-4 hours

4. **S4: Extract State Machine Routing Control** (MEDIUM)
   - Improves testability
   - Implementation: 4-5 hours

5. **S5: Extract Daemon Control Loop** (MEDIUM)
   - Requires careful shutdown semantics preservation
   - Implementation: 4-5 hours

6. **S6: Unify State Machines** (HIGH - EXPLICIT APPROVAL REQUIRED)
   - Requires validation period
   - Implementation: 8-10 hours + 1 week validation

7. **S7: Confidence Scoring Integration** (HIGH - EXPLICIT APPROVAL REQUIRED)
   - Hybrid approach with config flag
   - Implementation: 10-12 hours + 1 week validation

**Dependencies on Phase 14:**

- **RTT Measurement Utility (W3):** Benefits S1/S2 (shared pattern)
- **State Manager Pattern (W5):** Establishes precedent (steering already uses)
- **No strict ordering:** Phases can proceed independently if needed

**Testing Strategy:**

| Phase | Focus | Tests |
|-------|-------|-------|
| Week 1-2 | LOW risk | Unit tests for extracted methods |
| Week 2-3 | MEDIUM risk | Integration tests with router mocks |
| Week 3-4 | HIGH risk validation | Parallel run (confidence vs hysteresis), decision comparison |
| Week 4+ | Production | 1-week parallel validation before switching |

---

## Risk Mitigation

### Pre-Refactoring Checklist

- [ ] All existing tests passing (474 unit tests)
- [ ] Production baseline metrics captured (cycle time, CPU, RTT stability)
- [ ] Rollback procedure documented
- [ ] Change affects non-protected zones only (or has explicit approval)

### Validation Requirements

- [ ] Unit tests for new extractions
- [ ] Integration tests for modified flows
- [ ] Baseline comparison: Refactored behavior === Original behavior
- [ ] Production soak test: 24-hour stability validation

### Protected Zone Modification Protocol

If touching protected zones (state machines, EWMA, rate calculations):

1. **Explicit approval required** from user
2. **Mathematical proof** of behavioral equivalence
3. **Extended testing period** (7 days minimum)
4. **Staged rollout** (ATT first, Spectrum second)

### Rollback Procedures

| Risk Level | Rollback Strategy |
|------------|-------------------|
| LOW | Revert single commit, redeploy |
| MEDIUM | Revert to last known-good, validate 24 hours |
| HIGH | Config flag instant revert (no redeploy needed) |

---

## Appendices

### Appendix A: Method Complexity Matrix

**WANController Methods:**

| Method | Lines | Params | Cyclomatic | Priority |
|--------|-------|--------|------------|----------|
| run_cycle | 176 | 0 | HIGH (7+) | P1 |
| __init__ | 82 | 5 | MEDIUM | P2 |
| measure_rtt | 42 | 0 | MEDIUM | P1 |
| load_state | 40 | 0 | MEDIUM | P2 |
| save_state | 32 | 0 | LOW | P2 |
| verify_tcp_connectivity | 23 | 0 | MEDIUM | P3 |
| verify_connectivity_fallback | 20 | 0 | LOW | P1 |
| update_ewma | 15 | 1 | LOW | P2 |
| verify_local_connectivity | 13 | 0 | LOW | P3 |

**SteeringDaemon Methods/Functions:**

| Method/Function | Lines | Cyclomatic | Priority |
|-----------------|-------|------------|----------|
| main | 197 | HIGH (10+) | P2 |
| _load_specific_fields | 129 | MEDIUM | P1 |
| run_cycle | 129 | HIGH (6+) | P1 |
| _update_state_machine_cake_aware | 104 | HIGH (12) | P3 |
| _update_state_machine_legacy | 74 | MEDIUM (6) | P3 |

### Appendix B: State Machine Diagrams

**WANController Download (4-State):**
```
              ┌─────────────────────────────────────┐
              │           QueueController           │
              │  (delegated from WANController)     │
              └─────────────────────────────────────┘

    ┌─────────┐    delta >= soft_red    ┌──────────┐
    │  GREEN  │────────────────────────▶│ SOFT_RED │
    │         │◀────────────────────────│  (clamp) │
    └─────────┘    green_streak >= 5    └──────────┘
         │                                    │
         │ delta >= hard_red           delta >= hard_red
         ▼                                    ▼
    ┌─────────┐                         ┌──────────┐
    │ YELLOW  │◀───────────────────────▶│   RED    │
    │ (ramp)  │    delta >= hard_red    │ (decay)  │
    └─────────┘                         └──────────┘
```

**SteeringDaemon (2-State with Asymmetric Hysteresis):**
```
                         red_count >= red_samples_required
    ┌─────────────┐          (enable steering)           ┌─────────────┐
    │  GOOD       │─────────────────────────────────────▶│  DEGRADED   │
    │ (primary)   │                                      │ (secondary) │
    │             │◀─────────────────────────────────────│             │
    └─────────────┘     good_count >= green_samples      └─────────────┘
                         (disable steering)

    Asymmetric: red_samples_required=2 (fast escalation)
                green_samples_required=15 (slow recovery)
```

### Appendix C: Dependency Graph

**File Dependencies:**
```
autorate_continuous.py
├── router_client.py (RouterOS wrapper)
├── state_utils.py (atomic writes, JSON load)
├── rtt_measurement.py (ICMP ping)
├── config_base.py (configuration)
├── queue_controller.py (state machine delegation)
└── [state file: /var/lib/wanctl/autorate-{wan}.json]

steering/daemon.py
├── router_client.py (RouterOS wrapper)
├── state_utils.py (StateManager base)
├── cake_stats.py (CAKE reader)
├── congestion_assessment.py (EWMA, state assessment)
├── steering_confidence.py (Phase 2B, unused)
├── [state file: /var/lib/wanctl/steering.json]
└── [reads: /var/lib/wanctl/autorate-{primary}.json] (baseline RTT)
```

**State File Schema (Shared Fields):**
```json
{
  "baseline_rtt": 25.4,
  "load_rtt": 28.1,
  "timestamp": "2026-01-13T22:50:00Z"
}
```

---

**Analysis Complete:** 2026-01-13
**Next:** Execute Phase 8 (Extract Common Helpers) or Phase 14-15 when ready for core refactoring
