# Steering Daemon Structural Analysis

**Analysis Date:** 2026-01-13
**File:** `src/wanctl/steering/daemon.py`
**Lines:** 1,179
**Functions/Methods:** 24 total

---

## Section 1: Overview

### File Statistics
- **Total lines:** 1,179
- **Functions/Methods:** 24 (5 module-level functions, 19 methods across 5 classes)
- **Classes:** 5 (SteeringConfig, RouterOSController, BaselineLoader, SteeringDaemon, SteeringStateSchema factory)
- **Complexity score:** MEDIUM-HIGH (main daemon class has 8 methods, main() has 175 lines)

### Current Architecture Summary
The steering daemon implements adaptive multi-WAN steering with a three-layer decision architecture:
- **Layer 1 (Measurement):** RTT measurement + CAKE stats collection
- **Layer 2 (Assessment):** Congestion state evaluation (GREEN/YELLOW/RED) + EWMA smoothing
- **Layer 3 (Decision):** Hysteresis-based state machine → RouterOS mangle rule toggle

**Execution model:** Continuous daemon mode with 50ms cycle interval (20Hz, synchronized with autorate)

**Key responsibilities:**
1. **Steering control loop** - Continuous execution with signal handling (main())
2. **State machine management** - Hysteresis logic with asymmetric streak counting (update_state_machine)
3. **Baseline RTT synchronization** - Load from autorate state files (update_baseline_rtt, BaselineLoader)
4. **Congestion detection** - Multi-signal assessment (CAKE-aware vs legacy modes)
5. **RouterOS integration** - Mangle rule enable/disable with verification (RouterOSController)
6. **State persistence** - JSON state file management with transition history

### Configuration-Driven Design
- Identical code runs on all deployments (cable/DSL/fiber)
- State names derived from topology config: `{primary_wan.upper()}_GOOD`, `{primary_wan.upper()}_DEGRADED`
- Dual transport support: REST API (preferred, 2x faster) vs SSH (fallback)

---

## Section 2: Complexity Hotspots

### Hotspot 1: SteeringDaemon.run_cycle() (lines 849-977)
**Complexity metrics:**
- **Lines:** 129 lines (11% of file)
- **Responsibilities:** 8+ distinct responsibilities
- **Nesting depth:** 3 levels (if/if/if in CAKE-aware block)
- **Branches:** 6+ decision points
- **Dependencies:** 6 external components (state_mgr, router, baseline_loader, cake_reader, rtt_measurement, metrics)

**Why complex:**
- Orchestrates entire steering cycle (baseline update → measurement → assessment → decision → persistence)
- CAKE-aware vs legacy mode branching throughout method
- Error handling for ping failures, CAKE read failures, baseline unavailability
- Inline EWMA smoothing logic (lines 909-923)
- Inline history management (W4 fix: deque append, lines 878-879)
- Inline metrics recording (lines 966-974)

**Impact on maintainability:**
- Difficult to unit test individual stages (baseline update, measurement, assessment) in isolation
- Mixed abstraction levels (high-level orchestration + low-level EWMA math)
- Hard to add new measurement sources without modifying core loop

**Impact on testability:**
- Requires full daemon initialization (config, state, router, RTT measurement, baseline loader)
- CAKE-aware mode conditional logic increases test combinations (2^3 = 8 paths)
- Integration tests dominate; unit tests challenging

---

### Hotspot 2: SteeringDaemon._update_state_machine_cake_aware() (lines 669-772)
**Complexity metrics:**
- **Lines:** 104 lines (9% of file)
- **Responsibilities:** 5 (state normalization, RED detection, YELLOW logging, recovery detection, routing control)
- **Nesting depth:** 4 levels (if is_good_state / if assessment == RED / if red_count >= threshold / if enable_steering)
- **Branches:** 8+ decision points (assessment type, counter thresholds, routing success)
- **Cyclomatic complexity:** ~12 (multiple nested conditionals)

**Why complex (CONCERNS.md flagged):**
- **Multiple state transitions:** good_count, red_count, current_state all updated interdependently
- **State normalization:** Legacy name handling (SPECTRUM_GOOD → config.state_good) adds branches (lines 686-689, 729-732)
- **Asymmetric hysteresis:** RED requires `red_samples_required` cycles, recovery requires `green_samples_required` cycles
- **Routing integration:** Router enable/disable calls embedded in state logic (lines 706-717, 749-760)
- **Metrics recording:** Conditional metrics calls (lines 712-715, 755-758) mixed with state logic

**Impact on maintainability:**
- State transition logic is fragile - changing counter reset logic risks flapping
- Hard to reason about all state paths (GOOD→DEGRADED vs DEGRADED→GOOD asymmetry)
- Mixed concerns: state machine + routing control + metrics

**Impact on testability:**
- 8+ test cases needed to cover all assessment states × current states × threshold scenarios
- Mocking RouterOS controller required for all tests
- State counter edge cases (red_count = threshold - 1) hard to reproduce

---

### Hotspot 3: SteeringDaemon._update_state_machine_legacy() (lines 774-847)
**Complexity metrics:**
- **Lines:** 74 lines (6% of file)
- **Responsibilities:** 4 (state normalization, threshold checking, counter management, routing control)
- **Nesting depth:** 3 levels (if is_good_state / if delta > threshold / if bad_count >= samples)
- **Branches:** 6+ decision points

**Why complex:**
- Parallel structure to _cake_aware version but with RTT-only logic
- Same fragility issues: interdependent counters (bad_count, good_count), routing calls
- Legacy backward compatibility maintains code duplication

**Impact on maintainability:**
- Code duplication with _cake_aware version (~60% overlap in structure)
- Bug fixes must be applied to both methods
- Inconsistent state naming logic handled in both places

**Impact on testability:**
- Requires separate test suite parallel to CAKE-aware tests
- Hard to verify both modes maintain identical state transition semantics

---

### Hotspot 4: main() (lines 983-1179)
**Complexity metrics:**
- **Lines:** 197 lines (17% of file, largest function)
- **Responsibilities:** 12+ (arg parsing, signal registration, config load, logging setup, component initialization, lock acquisition, daemon creation, systemd watchdog, event loop, failure tracking, cleanup)
- **Nesting depth:** 3 levels (try/while/if)
- **Branches:** 10+ decision points (shutdown checks, reset mode, systemd availability, cycle success, watchdog state)

**Why complex:**
- Mixes initialization, configuration, control loop, and cleanup in single function
- Systemd watchdog logic embedded in main loop (lines 1100-1147)
- Shutdown signal checking at 4 different points (lines 1042, 1088, 1118, 1151)
- Consecutive failure tracking + watchdog state management (lines 1108-1147)
- Lock acquisition + atexit emergency cleanup (lines 1073-1085)

**Impact on maintainability:**
- Difficult to refactor control loop without breaking initialization/cleanup
- Watchdog logic deeply coupled to cycle success tracking
- Hard to add new operational modes (e.g., single-shot, calibration)

**Impact on testability:**
- Cannot unit test control loop without full process lifecycle (signal handling, locks, atexit)
- Integration tests only (requires systemd mocks for watchdog tests)
- Shutdown scenarios hard to reproduce reliably

---

### Hotspot 5: SteeringConfig._load_specific_fields() (lines 188-316)
**Complexity metrics:**
- **Lines:** 129 lines (11% of file)
- **Responsibilities:** 10+ (router config, topology, state derivation, primary WAN state file, mangle rule, RTT measurement, CAKE queues, operational mode, thresholds, state persistence, logging, lock file, timeouts, router dict, metrics)
- **Nesting depth:** 2 levels (if/if for legacy support, lines 214-217)
- **Branches:** 5+ decision points (defaults, legacy name handling, conditional validation)

**Why complex:**
- **Flat structure:** All configuration fields loaded in single method (no grouping)
- **Legacy support:** Backward-compatible name handling (spectrum → primary, lines 214-217)
- **Derived state:** State names computed from topology (`{primary_wan.upper()}_GOOD`)
- **Validation scattered:** Some fields validated (mangle_rule_comment, ping_host, queue names), others not
- **Dict construction:** Router dict manually assembled (lines 304-312)

**Impact on maintainability:**
- Hard to find specific config field logic (must scan entire method)
- Adding new config section requires editing large method
- Validation inconsistency (some fields validated, others just assigned)

**Impact on testability:**
- Difficult to test individual config sections in isolation
- Config validation tests require full config object construction
- Legacy support logic requires specific test cases (spectrum vs primary naming)

---

## Section 3: Refactoring Opportunities

### Opportunity 3.1: Extract EWMA Smoothing Logic
**Current state:**
- **Location:** run_cycle() lines 909-923 (inline EWMA updates)
- **Lines:** 15 lines (EWMA logic + state updates)
- **Complexity:** Low (pure math, but duplicated pattern)

**Proposed improvement:**
```python
def update_ewma_smoothing(self, delta: float, queued_packets: int) -> None:
    """Update EWMA smoothed values for RTT delta and queue depth."""
    state = self.state_mgr.state

    state["rtt_delta_ewma"] = ewma_update(
        state["rtt_delta_ewma"],
        delta,
        self.config.rtt_ewma_alpha
    )

    state["queue_ewma"] = ewma_update(
        state["queue_ewma"],
        float(queued_packets),
        self.config.queue_ewma_alpha
    )
```

**Risk level:** **LOW**
- Pure extraction of mathematical operations
- No algorithm changes
- Clear input/output contract (delta, queued_packets → state updates)
- Existing ewma_update() function handles validation (C5 fix)
- Easy to unit test independently

**Testability improvement:**
- Can test EWMA smoothing without full cycle execution
- Test edge cases (alpha=0, alpha=1, queue_ewma overflow) in isolation
- Verify state updates without mocking router/RTT measurement

**Dependencies:** None (self-contained extraction)

---

### Opportunity 3.2: Extract CAKE Stats Collection
**Current state:**
- **Location:** run_cycle() lines 863-898 (CAKE stats read + history management + failure tracking)
- **Lines:** 36 lines
- **Complexity:** Medium (conditional logic for CAKE-aware mode, failure tracking W8 fix)

**Proposed improvement:**
```python
def collect_cake_stats(self) -> tuple[int, int]:
    """
    Collect CAKE statistics (drops and queued packets).

    Returns:
        tuple[int, int]: (cake_drops, queued_packets)
        Returns (0, 0) if CAKE-aware disabled or read fails
    """
    state = self.state_mgr.state

    if not self.config.cake_aware or not self.cake_reader:
        return 0, 0

    stats = self.cake_reader.read_stats(self.config.primary_download_queue)
    if stats:
        # Successful read - reset failure counter
        state["cake_read_failures"] = 0

        # Update history (W4 fix: deques handle automatic eviction)
        state["cake_drops_history"].append(stats.dropped)
        state["queue_depth_history"].append(stats.queued_packets)

        return stats.dropped, stats.queued_packets
    else:
        # W8 fix: Track consecutive failures
        state["cake_read_failures"] += 1
        if state["cake_read_failures"] == 1:
            self.logger.warning(
                f"CAKE stats read failed for {self.config.primary_download_queue}, "
                f"using RTT-only decisions (failure {state['cake_read_failures']})"
            )
        elif state["cake_read_failures"] >= 3:
            if state["cake_read_failures"] == 3:
                self.logger.error(
                    f"CAKE stats unavailable after {state['cake_read_failures']} attempts, "
                    f"entering degraded mode (RTT-only decisions)"
                )

        return 0, 0
```

**Risk level:** **LOW**
- Pure extraction of CAKE stats collection logic
- Preserves all failure handling (W8 fix)
- Clear contract: returns (drops, packets) or (0, 0) for failures
- No state machine changes

**Testability improvement:**
- Test CAKE read failures without full cycle execution
- Verify W8 fix (consecutive failure tracking) in isolation
- Test history updates without mocking RTT measurement

**Dependencies:** None (self-contained extraction)

---

### Opportunity 3.3: Extract State Machine Routing Control
**Current state:**
- **Location:** _update_state_machine_cake_aware() lines 706-717, 749-760 (router enable/disable with transition logging)
- **Lines:** 12 lines per transition (24 lines total)
- **Complexity:** Medium (routing call + verification + transition logging + metrics)

**Proposed improvement:**
```python
def execute_steering_transition(
    self,
    from_state: str,
    to_state: str,
    enable_steering: bool
) -> bool:
    """
    Execute steering state transition with routing control.

    Args:
        from_state: Current state
        to_state: Target state
        enable_steering: True to enable steering, False to disable

    Returns:
        True if transition succeeded, False if routing failed
    """
    # Execute routing change
    if enable_steering:
        if not self.router.enable_steering():
            self.logger.error(f"Failed to enable steering, staying in {from_state}")
            return False
    else:
        if not self.router.disable_steering():
            self.logger.error(f"Failed to disable steering, staying in {from_state}")
            return False

    # Log transition
    self.state_mgr.log_transition(from_state, to_state)
    self.state_mgr.state["current_state"] = to_state

    # Record metrics
    if self.config.metrics_enabled:
        record_steering_transition(
            self.config.primary_wan,
            from_state,
            to_state
        )

    return True
```

**Risk level:** **MEDIUM**
- Extracts routing control from state machine logic
- Preserves router error handling (stay in current state on failure)
- Requires state machine methods to use return value
- Changes state machine structure (separation of concerns)

**Testability improvement:**
- Test routing transitions without state machine complexity
- Verify metrics recording without nested state logic
- Test router failure handling in isolation

**Dependencies:**
- State machine methods (_update_state_machine_cake_aware, _update_state_machine_legacy) must be updated to call this method
- Both methods have parallel structure, so changes can be applied identically

---

### Opportunity 3.4: Extract Baseline RTT Update Logic
**Current state:**
- **Location:** run_cycle() lines 856-859 (baseline update check + early return)
- **Lines:** 4 lines (simple, but critical path)
- **Complexity:** Low

**Proposed improvement:**
Already well-factored - update_baseline_rtt() is a separate method. No further extraction needed.

**Risk level:** N/A (already extracted)

---

### Opportunity 3.5: Unify State Machine Methods (CAKE-aware + Legacy)
**Current state:**
- **Location:** _update_state_machine_cake_aware (lines 669-772) + _update_state_machine_legacy (lines 774-847)
- **Lines:** 178 lines total (104 + 74)
- **Complexity:** HIGH (code duplication, parallel structure, ~60% overlap)

**Proposed improvement:**
```python
def _update_state_machine_unified(self, signals: CongestionSignals) -> bool:
    """
    Unified state machine for both CAKE-aware and legacy modes.

    Decision logic:
    - CAKE-aware: Uses CongestionState assessment (GREEN/YELLOW/RED)
    - Legacy: Uses raw RTT delta thresholds

    Both modes share:
    - State normalization (legacy name handling)
    - Counter management (asymmetric hysteresis)
    - Routing control (enable/disable steering)
    - Metrics recording
    """
    state = self.state_mgr.state
    current_state = state["current_state"]

    # State normalization
    if self._is_current_state_good(current_state):
        if current_state != self.config.state_good:
            state["current_state"] = self.config.state_good
            current_state = self.config.state_good
        is_good_state = True
    else:
        if current_state != self.config.state_degraded:
            state["current_state"] = self.config.state_degraded
            current_state = self.config.state_degraded
        is_good_state = False

    # Determine degradation condition (mode-specific)
    if self.config.cake_aware:
        assessment = assess_congestion_state(signals, self.thresholds, self.logger)
        is_degraded = (assessment == CongestionState.RED)
        is_recovered = (assessment == CongestionState.GREEN)
    else:
        delta = signals.rtt_delta
        is_degraded = (delta > self.config.bad_threshold_ms)
        is_recovered = (delta < self.config.recovery_threshold_ms)

    # State machine logic (unified)
    state_changed = False
    if is_good_state:
        state_changed = self._handle_good_state(
            is_degraded, current_state, signals
        )
    else:
        state_changed = self._handle_degraded_state(
            is_recovered, current_state, signals
        )

    return state_changed
```

**Risk level:** **HIGH**
- **Touches core state machine logic** (protected zone)
- Unifies two parallel implementations (risk of behavioral divergence)
- Requires careful testing to ensure both modes maintain identical semantics
- Changes abstraction (assessment vs threshold comparison must be equivalent)

**Testability improvement:**
- Single test suite covers both modes (reduces test duplication)
- Mode-specific behavior isolated to "is_degraded" condition
- Easier to add new modes (e.g., confidence-based scoring)

**Dependencies:**
- Requires extracting _handle_good_state() and _handle_degraded_state() helper methods
- Must verify equivalence: `assessment == RED` ≡ `delta > bad_threshold_ms`
- Needs comprehensive integration tests before deployment

**Recommendation:** **DEFER to Phase 15** - High risk, requires architectural approval

---

### Opportunity 3.6: Extract Configuration Field Loading Groups
**Current state:**
- **Location:** SteeringConfig._load_specific_fields() lines 188-316
- **Lines:** 129 lines (flat structure)
- **Complexity:** Medium (many responsibilities, no grouping)

**Proposed improvement:**
```python
def _load_specific_fields(self):
    """Load steering daemon-specific configuration fields"""
    self._load_router_config()
    self._load_topology_config()
    self._load_mangle_config()
    self._load_measurement_config()
    self._load_cake_config()
    self._load_mode_config()
    self._load_thresholds_config()
    self._load_state_config()
    self._load_logging_config()
    self._load_lock_config()
    self._load_timeouts_config()
    self._load_metrics_config()

def _load_router_config(self):
    """Load router transport settings (REST or SSH)"""
    router = self.data['router']
    self.router_transport = router.get('transport', 'ssh')
    self.router_password = router.get('password', '')
    self.router_port = router.get('port', 443)
    self.router_verify_ssl = router.get('verify_ssl', False)

# ... (similar groupings for other config sections)
```

**Risk level:** **LOW**
- Pure structural refactoring (no logic changes)
- Improves code organization and readability
- Easy to test (each group can be tested independently)

**Testability improvement:**
- Test individual config sections without loading entire config
- Isolate validation logic per section
- Easier to debug config errors (error traces point to specific section)

**Dependencies:** None (self-contained refactoring)

---

### Opportunity 3.7: Extract Daemon Control Loop from main()
**Current state:**
- **Location:** main() lines 1117-1154 (while loop + failure tracking + watchdog + sleep)
- **Lines:** 38 lines (embedded in 197-line main function)
- **Complexity:** Medium (control loop + watchdog + shutdown handling)

**Proposed improvement:**
```python
def run_daemon_loop(
    daemon: SteeringDaemon,
    config: SteeringConfig,
    logger: logging.Logger,
    shutdown_event: threading.Event
) -> int:
    """
    Run continuous daemon loop with watchdog and failure tracking.

    Returns:
        Exit code: 0 for success, 1 for failure
    """
    consecutive_failures = 0
    MAX_CONSECUTIVE_FAILURES = 3
    watchdog_enabled = True

    # Optional systemd watchdog support
    try:
        from systemd.daemon import notify as sd_notify
        HAVE_SYSTEMD = True
    except ImportError:
        HAVE_SYSTEMD = False
        sd_notify = None

    logger.info(f"Starting daemon mode with {config.measurement_interval}s cycle interval")
    if HAVE_SYSTEMD:
        logger.info("Systemd watchdog support enabled")

    while not shutdown_event.is_set():
        cycle_start = time.monotonic()

        # Run one cycle
        cycle_success = daemon.run_cycle()

        elapsed = time.monotonic() - cycle_start

        # Track consecutive failures for watchdog
        if cycle_success:
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            logger.warning(f"Cycle failed ({consecutive_failures}/{MAX_CONSECUTIVE_FAILURES})")

            # Stop watchdog notifications if sustained failures
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES and watchdog_enabled:
                watchdog_enabled = False
                logger.error(
                    f"Sustained failure: {consecutive_failures} consecutive failed cycles. "
                    f"Stopping watchdog - systemd will terminate us."
                )
                if HAVE_SYSTEMD:
                    sd_notify("STATUS=Degraded - consecutive failures exceeded threshold")

        # Notify systemd watchdog ONLY if healthy
        if HAVE_SYSTEMD and watchdog_enabled and cycle_success:
            sd_notify("WATCHDOG=1")
        elif HAVE_SYSTEMD and not watchdog_enabled:
            sd_notify(f"STATUS=Degraded - {consecutive_failures} consecutive failures")

        # Sleep for remainder of cycle interval (interruptible)
        sleep_time = max(0, config.measurement_interval - elapsed)
        if sleep_time > 0 and not shutdown_event.is_set():
            shutdown_event.wait(timeout=sleep_time)

    logger.info("Shutdown signal received, exiting gracefully")
    return 0
```

**Risk level:** **MEDIUM**
- Extracts control loop but must preserve all shutdown semantics
- Watchdog logic tightly coupled to failure tracking
- Shutdown event handling must remain identical

**Testability improvement:**
- Test control loop without full process lifecycle
- Mock shutdown event for shutdown scenario testing
- Test watchdog logic without systemd integration

**Dependencies:**
- main() must be refactored to call this function
- Shutdown event must be passed (already module-level _shutdown_event)

---

## Section 4: Confidence Scoring Integration

### Current State: Separate Implementation
**What exists:**
- `steering_confidence.py` (644 lines): Full Phase 2B confidence-based steering implementation
  - `compute_confidence()`: Multi-signal scoring (0-100 scale)
  - `TimerManager`: Sustain timers (degrade, hold_down, recovery)
  - `FlapDetector`: Oscillation detection with penalty
  - `Phase2BController`: Complete confidence-based controller

**What's used in daemon.py:**
- `congestion_assessment.py`: Three-state model (GREEN/YELLOW/RED)
- `assess_congestion_state()`: Decision logic based on thresholds
- Simple hysteresis: red_count/good_count with fixed thresholds

**Key difference:**
- **Confidence scoring (Phase 2B):** Multi-signal weighted scoring (0-100) with sustain timers
- **Current hysteresis:** Binary thresholds (good_samples, red_samples_required) with streak counting

### Integration Opportunity: Replace Hysteresis with Confidence Scoring

**Current hysteresis logic (daemon.py):**
```python
# Lines 669-772: CAKE-aware state machine
if assessment == CongestionState.RED:
    red_count += 1
    if red_count >= self.thresholds.red_samples_required:
        # Enable steering
        ...
elif assessment == CongestionState.GREEN:
    good_count += 1
    if good_count >= self.thresholds.green_samples_required:
        # Disable steering
        ...
```

**Proposed confidence integration:**
```python
# Use Phase2BController instead of simple counters
signals = ConfidenceSignals(
    cake_state=assessment.value,
    rtt_delta_ms=delta,
    drops_per_sec=cake_drops,
    queue_depth_pct=queue_utilization,
    cake_state_history=state["cake_state_history"],
    drops_history=state["drops_history"],
    queue_history=state["queue_history"]
)

decision = self.confidence_controller.evaluate(signals, current_state)

if decision == "ENABLE_STEERING":
    # Enable steering (timer expired)
    ...
elif decision == "DISABLE_STEERING":
    # Disable steering (recovery timer expired)
    ...
```

**What breaks if integrated:**
1. **State counters obsolete:** red_count, good_count replaced by TimerState
2. **Threshold config changes:** Need confidence.steer_threshold, confidence.recovery_threshold (not samples)
3. **Sustain timers:** New config: sustain_duration_sec, recovery_sustain_sec, hold_down_duration_sec
4. **History tracking:** Need cake_state_history, drops_history, queue_history (not just values)
5. **Flap detection:** New behavior (penalty increases steer threshold, not present in current code)

**Migration path:**
- **Phase 1:** Add confidence controller alongside hysteresis (dry-run mode, log only)
- **Phase 2:** Compare confidence decisions vs hysteresis decisions (validation)
- **Phase 3:** Switch to confidence controller (remove red_count/good_count logic)
- **Phase 4:** Remove legacy hysteresis code

### Risk Assessment: HIGH

**Risks:**
- **Behavioral change:** Confidence scoring may trigger steering at different times than hysteresis
- **Config compatibility:** Existing configs need migration (samples → durations, thresholds → confidence scores)
- **State persistence:** State file schema changes (add history fields, remove counters)
- **Testing burden:** Must validate equivalent behavior across all congestion scenarios

**Benefits:**
- **Better decisions:** Multi-signal scoring more robust than binary thresholds
- **Flap prevention:** Built-in oscillation detection with adaptive thresholds
- **Observability:** Confidence score provides continuous health metric (0-100)
- **Code reuse:** Phase 2B controller already implemented and tested

### Recommendation: INTEGRATE (Phase 15)

**Approach:** Hybrid (parallel implementation)
1. Add confidence controller to SteeringDaemon.__init__() (conditional on config flag)
2. If `mode.use_confidence_scoring = true`, use Phase2BController
3. Otherwise, use current hysteresis logic (backward compatibility)
4. Deploy with dry-run mode first (log-only, no routing changes)
5. Validate confidence decisions match hysteresis over 1-week period
6. Switch to confidence mode after validation

**Protected during integration:**
- Baseline RTT bounds (10-60ms, C4 fix)
- RouterOS mangle rule validation (command injection prevention, C2 fix)
- EWMA smoothing (alpha bounds validation, C5 fix)

---

## Section 5: Protected Zones

**Definition:** Code that MUST NOT change without explicit architectural approval

### Protected Zone 1: State Transition Logic (lines 669-847)
**Location:** _update_state_machine_cake_aware() + _update_state_machine_legacy()

**What's protected:**
- State transition conditions (RED → DEGRADED, GREEN → GOOD)
- Counter management (red_count, good_count increment/reset logic)
- Asymmetric hysteresis (different thresholds for degrade vs recovery)
- State normalization (legacy name handling)

**Why protected:**
- Core steering algorithm - changes affect routing behavior
- Carefully tuned to prevent flapping (asymmetric thresholds)
- Production-validated time constants (red_samples_required=2, green_samples_required=15)

**Allowed changes:**
- Extract routing control (Opportunity 3.3) - preserves state logic
- Add logging/metrics (non-functional)
- Refactor for testability (preserve semantics)

**Prohibited changes (without approval):**
- Changing counter reset logic (e.g., reset good_count on YELLOW instead of RED)
- Modifying threshold comparisons (e.g., `>=` to `>`)
- Removing state normalization (breaks legacy config compatibility)

---

### Protected Zone 2: Baseline RTT Validation (lines 492-502)
**Location:** BaselineLoader.load_baseline_rtt()

**What's protected:**
- Baseline RTT bounds (10-60ms, configurable)
- Sanity check logic (reject out-of-bounds baselines)
- Warning messages (security-relevant, C4 fix)

**Why protected:**
- Security fix (C4): Prevents malicious baseline attacks
- Prevents steering disruption from compromised autorate state
- Typical home ISP latencies validated (20-50ms normal)

**Allowed changes:**
- Make bounds configurable (already done, lines 280-282)
- Add logging for debugging
- Extract to utility function (preserve validation)

**Prohibited changes (without approval):**
- Removing bounds check (security regression)
- Widening bounds without justification (e.g., 0-1000ms)
- Changing default bounds (10-60ms production-validated)

---

### Protected Zone 3: EWMA Smoothing (lines 909-923, congestion_assessment.py)
**Location:** run_cycle() inline EWMA updates + ewma_update() function

**What's protected:**
- EWMA formula: `(1 - alpha) * current + alpha * new_value`
- Alpha bounds validation (0.0 ≤ alpha ≤ 1.0, C5 fix)
- Numeric overflow protection (NaN/Inf checking)
- Max value bounds (±1000ms for RTT)

**Why protected:**
- Mathematical correctness (exponential smoothing algorithm)
- Numeric stability (C5 fix prevents erratic behavior)
- Production-tuned alpha values (rtt_ewma_alpha=0.3, queue_ewma_alpha=0.4)

**Allowed changes:**
- Extract EWMA updates to method (Opportunity 3.1) - preserves algorithm
- Make alpha configurable (already done, lines 266-275)
- Add unit tests for edge cases

**Prohibited changes (without approval):**
- Changing EWMA formula (e.g., different weighting)
- Removing bounds validation (C5 regression)
- Modifying alpha defaults without performance validation

---

### Protected Zone 4: RouterOS Mangle Rule Control (lines 400-456)
**Location:** RouterOSController.enable_steering() + disable_steering()

**What's protected:**
- Mangle rule comment validation (command injection prevention, C2 fix)
- Retry with verification (W6 fix: handles RouterOS processing delay)
- Error handling (log + return False on failure)

**Why protected:**
- Security-critical (C2 fix: prevents command injection)
- Reliability-critical (W6 fix: verified state transitions)
- Production-validated retry parameters (3 retries, 0.1s initial delay, 2x backoff)

**Allowed changes:**
- Extract verification logic to utility (preserve retry behavior)
- Add metrics for routing failures
- Improve error messages

**Prohibited changes (without approval):**
- Removing comment validation (security regression)
- Removing retry/verification (reliability regression)
- Changing retry parameters without performance testing

---

### Protected Zone 5: Signal Handling (lines 100-144)
**Location:** _signal_handler(), register_signal_handlers(), is_shutdown_requested()

**What's protected:**
- Thread-safe shutdown event (threading.Event, W5 fix)
- SIGTERM/SIGINT handler registration
- Shutdown check in control loop (lines 1042, 1088, 1118, 1151)

**Why protected:**
- Concurrency-critical (W5 fix: eliminates race conditions)
- Graceful shutdown requirement (systemd integration)
- Lock cleanup dependency (shutdown must complete to release lock)

**Allowed changes:**
- Add logging at shutdown (non-functional)
- Extract signal handler to shared module (preserve semantics)

**Prohibited changes (without approval):**
- Replacing threading.Event with boolean flag (concurrency regression)
- Removing signal handler registration (graceful shutdown broken)
- Changing shutdown check logic (may leave locks held)

---

## Section 6: Recommendations for Phase 15

### Prioritized Implementation Order

**Week 1: Low-Risk Extractions (Confidence: HIGH)**
1. **Opportunity 3.1** (EWMA smoothing) - 15 lines, pure math extraction
2. **Opportunity 3.2** (CAKE stats collection) - 36 lines, preserves W8 fix
3. **Opportunity 3.6** (config field grouping) - 129 lines, structural refactoring

**Expected outcome:** 20% reduction in run_cycle() complexity, improved config readability

---

**Week 2: Medium-Risk Extractions (Confidence: MEDIUM)**
4. **Opportunity 3.3** (routing control extraction) - 24 lines, requires state machine changes
5. **Opportunity 3.7** (daemon loop extraction) - 38 lines, preserves watchdog logic

**Expected outcome:** State machine methods 15% smaller, main() 20% smaller, improved testability

---

**Week 3: High-Risk Integrations (Confidence: LOW, requires approval)**
6. **Opportunity 3.5** (unify state machines) - 178 lines, HIGH RISK
7. **Section 4** (confidence scoring integration) - Replaces hysteresis logic, HIGH RISK

**Expected outcome:** 40% reduction in state machine code duplication, better steering decisions

**Prerequisite:** Comprehensive integration testing, 1-week parallel validation in production

---

### Testing Strategy Recommendations

**Unit Testing (Week 1-2):**
- Test extracted methods independently (EWMA, CAKE stats, config loading)
- Mock minimal dependencies (state manager, logger only)
- Parametrized tests for config variations (CAKE-aware vs legacy)
- Edge case tests (alpha bounds, CAKE read failures, empty history)

**Integration Testing (Week 2-3):**
- Full daemon cycle tests with real state files
- Router mock with enable/disable verification
- Shutdown scenario tests (signal handling, lock cleanup)
- Watchdog behavior tests (consecutive failures, degraded mode)

**Validation Testing (Week 3-4):**
- Parallel run: confidence controller + hysteresis (log both decisions)
- Decision comparison: confidence == "ENABLE_STEERING" vs red_count >= threshold
- Flap detection validation: verify penalty engages on oscillation
- Performance regression: verify 50ms cycle interval maintained

---

### Dependencies on Phase 14 (WANController Refactoring)

**Shared extraction opportunities:**
1. **RTT measurement with retry** (WANController line ~750, SteeringDaemon line ~574-618)
   - Both use measure_with_retry() utility
   - Both have fallback to history (W7 fix)
   - Extraction in Phase 14 benefits Phase 15 (shared pattern)

2. **State persistence utilities** (WANController line ~460, SteeringDaemon uses StateManager)
   - WANController opportunity #3.5 (extract state manager)
   - SteeringDaemon already uses StateManager (no extraction needed)
   - Phase 14 creates precedent for state manager pattern

3. **EWMA smoothing** (both use ewma_update() from congestion_assessment.py)
   - Already shared utility function
   - No further extraction needed

**Recommendation:** Execute Phase 14 first - establishes RTT measurement pattern for Phase 15 to follow

---

### Risk Mitigation

**For HIGH-risk changes (Opportunities 3.5, Section 4):**
1. **Parallel implementation:** Keep both old and new code paths (config flag)
2. **Dry-run mode:** Log decisions without routing changes (Phase 2B already supports)
3. **Canary deployment:** Deploy to 1 WAN first, validate 48 hours before second WAN
4. **Rollback plan:** Config flag can instantly revert to hysteresis mode
5. **Monitoring:** Add metrics for decision comparison (confidence vs hysteresis agreement rate)

**For MEDIUM-risk changes (Opportunities 3.3, 3.7):**
1. **Unit tests:** Cover all extracted methods before integration
2. **Integration tests:** Full cycle tests with routing mocks
3. **Code review:** Focus on state machine semantics preservation

**For LOW-risk changes (Opportunities 3.1, 3.2, 3.6):**
1. **Quick wins:** Deploy early to build confidence
2. **Regression tests:** Verify existing behavior unchanged
3. **Performance tests:** Validate 50ms cycle interval maintained

---

## Summary Statistics

**Complexity hotspots identified:** 5
- run_cycle(): 129 lines, 8+ responsibilities
- _update_state_machine_cake_aware(): 104 lines, fragile state logic (CONCERNS.md flagged)
- _update_state_machine_legacy(): 74 lines, code duplication
- main(): 197 lines, 12+ responsibilities
- _load_specific_fields(): 129 lines, flat structure

**Refactoring opportunities documented:** 7
- 3 LOW risk (quick wins, Week 1)
- 2 MEDIUM risk (testability improvements, Week 2)
- 2 HIGH risk (architectural changes, Week 3+)

**Protected zones defined:** 5
- State transition logic (core algorithm)
- Baseline RTT validation (security fix C4)
- EWMA smoothing (numeric stability C5)
- RouterOS mangle rule control (security fix C2)
- Signal handling (concurrency fix W5)

**Risk distribution:**
- LOW: 3 opportunities (60% of Week 1-2 work)
- MEDIUM: 2 opportunities (30% of Week 2 work)
- HIGH: 2 opportunities (10% of Week 3+ work, requires approval)

**Key insight from CONCERNS.md:**
State machine fragility (lines ~630-680) confirmed - multiple interdependent counters (red_count, good_count) with asymmetric hysteresis. Refactoring must preserve this carefully-tuned logic.

**Confidence integration finding:**
Phase 2B controller (steering_confidence.py) exists but unused. Integration opportunity: replace hysteresis with confidence scoring (HIGH RISK, requires validation). Recommendation: hybrid approach (config flag) for gradual rollout.
