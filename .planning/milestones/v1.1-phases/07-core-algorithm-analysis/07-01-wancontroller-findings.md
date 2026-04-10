# WANController Class: Structural Analysis and Refactoring Opportunities

**Phase:** 07-core-algorithm-analysis
**Plan:** 01
**Date:** 2026-01-13
**File Analyzed:** `src/wanctl/autorate_continuous.py`

## 1. Overview

### File Statistics
- **Total Lines:** 1,412
- **WANController Class:** Lines 562-1034 (473 lines, 33.5% of file)
- **Total Methods:** 10 (including `__init__`)
- **Dependencies:** 8 external modules (router_client, state_utils, rtt_measurement, config_base, etc.)

### Current Architecture Summary
WANController orchestrates continuous bandwidth control for a single WAN interface. It integrates:
- **RTT measurement** (ICMP ping with median-of-three aggregation)
- **EWMA smoothing** (dual-speed: fast load tracking, slow baseline tracking)
- **State-based queue control** (4-state download, 3-state upload via QueueController)
- **Router API interaction** (via RouterOS wrapper)
- **State persistence** (JSON serialization of hysteresis counters and EWMA values)
- **Fallback connectivity checks** (graceful degradation when ICMP blocked)

### Key Responsibilities
1. Measure RTT via ICMP ping (concurrent for median-of-three)
2. Update dual EWMA values (baseline and load)
3. Delegate rate adjustments to QueueController instances
4. Apply rate changes to router (with flash wear protection)
5. Persist state to disk (hysteresis counters, EWMA, last applied rates)
6. Handle connectivity failures (ICMP unavailable, total WAN loss)
7. Enforce rate limiting (protect router API during instability)
8. Record metrics (Prometheus integration)

---

## 2. Complexity Hotspots

### Method Inventory

| Method | Lines | Params | Cyclomatic Complexity | Primary Responsibility |
|--------|-------|--------|----------------------|------------------------|
| `__init__` | 82 (564-644) | 5 | Low (linear) | Initialize controllers, load state |
| `measure_rtt` | 42 (645-686) | 0 | Medium (2 branches, concurrent futures) | Ping hosts, aggregate RTT |
| `update_ewma` | 15 (688-702) | 1 | Low (1 conditional) | Update baseline/load EWMAs |
| `verify_local_connectivity` | 13 (704-723) | 0 | Low (1 conditional) | Check gateway reachability |
| `verify_tcp_connectivity` | 23 (725-752) | 0 | Medium (loop, exception handling) | TCP handshake checks |
| `verify_connectivity_fallback` | 20 (754-783) | 0 | Low (2 checks, early returns) | Orchestrate fallback checks |
| **`run_cycle`** | **176 (785-960)** | **0** | **HIGH (7+ branches, nested logic)** | **Main control loop** |
| `load_state` | 40 (962-1002) | 0 | Medium (nested dict access) | Restore persisted state |
| `save_state` | 32 (1004-1033) | 0 | Low (dict construction) | Persist state to disk |

### 2.1 Primary Hotspot: `run_cycle()` (176 lines)

**Location:** Lines 785-960
**Complexity:** HIGH

#### Why It's Complex
1. **Multiple responsibilities (6+ distinct operations):**
   - RTT measurement orchestration
   - Fallback connectivity handling (3 modes: graceful_degradation, freeze, use_last_rtt)
   - EWMA updates
   - Queue controller delegation (download 4-state, upload 3-state)
   - Flash wear protection logic
   - Rate limiting enforcement
   - Metrics recording

2. **Deep nesting (4 levels):**
   - Level 1: `if measured_rtt is None`
   - Level 2: `if has_connectivity`
   - Level 3: `if self.config.fallback_mode == 'graceful_degradation'`
   - Level 4: `if self.icmp_unavailable_cycles == 1`/`elif .../`else`

3. **Long conditional chains:**
   - Fallback mode selection: 3 modes × multiple cycle states = 6+ branches
   - Flash wear protection: rate change detection + rate limiting check
   - Multiple early returns (lines 826, 833, 839, 852, 857)

4. **State mutation spread throughout:**
   - `self.icmp_unavailable_cycles` (lines 807, 862, 865)
   - `self.last_applied_dl_rate`, `self.last_applied_ul_rate` (lines 937-938)
   - EWMA state via `update_ewma()` (line 868)
   - Queue controller state via `adjust_4state()`/`adjust()` (lines 871-880)

#### Impact on Maintainability
- **Difficult to test:** 176 lines with multiple execution paths require extensive mocking
- **Hard to reason about:** Multiple concerns intermixed (measurement, connectivity, rate control, persistence)
- **Fragile to change:** Modifying one section (e.g., fallback logic) risks breaking others (e.g., rate limiting)
- **Poor separation of concerns:** Business logic (connectivity checks) mixed with infrastructure (metrics, persistence)

### 2.2 Secondary Hotspot: `__init__()` (82 lines)

**Location:** Lines 564-644
**Complexity:** MEDIUM

#### Why It's Complex
1. **Multiple initialization phases:**
   - Store 9 instance variables from parameters (lines 565-569)
   - Initialize baseline/load RTT (lines 572-573)
   - Create 2 QueueController instances (lines 576-596)
   - Copy 8 config thresholds/params (lines 598-611)
   - Initialize flash wear protection (lines 620-621)
   - Initialize rate limiter (lines 629-632)
   - Initialize fallback tracking (line 640)
   - Load persisted state (line 643)

2. **High parameter coupling:**
   - Accepts 5 parameters (wan_name, config, router, rtt_measurement, logger)
   - Accesses 15+ config attributes (download_floor_green, upload_ceiling, target_bloat_ms, etc.)

3. **Hidden side effects:**
   - `self.load_state()` at line 643 mutates state during construction
   - Loads from disk, making initialization non-deterministic

#### Impact on Maintainability
- **Testing difficulty:** Requires full Config object, mocked RouterOS, mocked RTTMeasurement
- **Long construction time:** Disk I/O during `__init__` blocks startup
- **Hard to mock:** Many dependencies must be satisfied before instantiation

### 2.3 Tertiary Hotspot: `measure_rtt()` (42 lines)

**Location:** Lines 645-686
**Complexity:** MEDIUM

#### Why It's Complex
1. **Dual execution paths:**
   - Median-of-three (lines 654-683): concurrent futures, aggregation logic
   - Single host (lines 685-686): simple ping

2. **Concurrent programming:**
   - ThreadPoolExecutor with 3 workers (line 659)
   - Future completion handling with timeout (line 666)
   - Exception handling per-future (lines 668-673)

3. **Multiple failure modes:**
   - Individual ping failures (caught per-future)
   - All pings fail (line 682)
   - Partial success (1-2 pings, lines 675-680)

#### Impact on Maintainability
- **Concurrency complexity:** Futures and timeouts add cognitive load
- **Non-deterministic behavior:** Depends on network conditions, reflector availability
- **Testing challenges:** Requires mocking concurrent futures and network I/O

---

## 3. Refactoring Opportunities

### 3.1 Extract Fallback Connectivity Logic from `run_cycle()`

**Opportunity:** Extract lines 798-858 (ICMP failure handling block) to dedicated method

**Current State:**
- **Lines:** 61 (within 176-line method)
- **Nesting:** 4 levels deep
- **Branches:** 7+ execution paths (fallback checks × 3 modes)

**Proposed Improvement:**
```python
def handle_icmp_failure(self) -> tuple[bool, float | None]:
    """
    Handle ICMP ping failure with fallback connectivity checks.

    Returns:
        (should_continue, measured_rtt_or_none)
        - should_continue: True if cycle should proceed, False to abort
        - measured_rtt_or_none: RTT to use (last known) or None if aborting
    """
    # Move lines 798-858 here
    # Return tuple indicating (continue_cycle, rtt_value)
```

**Benefits:**
- Reduces `run_cycle()` from 176 to ~120 lines (32% reduction)
- Isolates fallback logic for independent testing
- Clarifies intent: "Handle failure, decide whether to continue"

**Risk Level:** **LOW**
- Pure extraction - no algorithm changes
- Clear input/output contract (boolean + optional RTT)
- Existing behavior preserved via return tuple
- Easy to test: mock connectivity checks, verify return values

**Testability Improvement:**
- Can test all 3 fallback modes (graceful_degradation, freeze, use_last_rtt) in isolation
- Can verify cycle counter increments without running full cycle
- Can simulate partial failures (ICMP down, TCP up) without RouterOS dependency

**Dependencies:**
- None (method is self-contained, uses existing instance state)

---

### 3.2 Extract Flash Wear Protection Logic from `run_cycle()`

**Opportunity:** Extract lines 892-942 (flash wear + rate limiting block) to dedicated method

**Current State:**
- **Lines:** 51 (within 176-line method)
- **Nesting:** 3 levels (rate changed check → rate limiter check → router update)
- **Responsibilities:** 3 (change detection, rate limiting, router API call)

**Proposed Improvement:**
```python
def apply_rate_changes_if_needed(self, dl_rate: int, ul_rate: int) -> bool:
    """
    Apply rate changes to router with flash wear protection and rate limiting.

    Only updates router if rates changed (flash wear protection) and within
    rate limit window (API overload protection).

    Args:
        dl_rate: Download rate in bps
        ul_rate: Upload rate in bps

    Returns:
        True if rates applied (or skipped without error), False on failure
    """
    # Move lines 892-942 here
    # Return False only on router.set_limits() failure
```

**Benefits:**
- Reduces `run_cycle()` to ~70 lines (60% total reduction with #3.1)
- Separates flash wear protection logic (architectural invariant) from cycle logic
- Enables testing of rate limiting without full cycle execution
- Clear single responsibility: "Apply rates if changed and not rate-limited"

**Risk Level:** **LOW**
- Pure extraction - no changes to flash wear or rate limiting algorithms
- Clear input/output: rates in, success boolean out
- Preserves existing behavior via early returns
- No state machine interaction

**Testability Improvement:**
- Can test flash wear protection in isolation (same rates → no router call)
- Can test rate limiting independently (exceed window → skip update, log warning)
- Can verify metrics recording (router update event) without full controller
- Can mock router.set_limits() cleanly without RTT measurement overhead

**Dependencies:**
- Requires `self.router`, `self.rate_limiter`, `self.logger`, `self.config` (all already instance variables)

---

### 3.3 Extract EWMA Update Validation Logic

**Opportunity:** Add validation wrapper around `update_ewma()` to enforce baseline update threshold

**Current State:**
- **Lines:** 15 (method is small but critical)
- **Algorithm:** Baseline only updates if delta < threshold (architectural invariant)
- **Location:** Lines 688-702

**Proposed Improvement:**
```python
def update_ewma(self, measured_rtt: float) -> None:
    """Update both EWMAs (fast load, slow baseline)"""
    # Fast EWMA for load_rtt (always updated)
    self.load_rtt = (1 - self.alpha_load) * self.load_rtt + self.alpha_load * measured_rtt

    # Slow EWMA for baseline_rtt (conditional update)
    self._update_baseline_if_idle(measured_rtt)

def _update_baseline_if_idle(self, measured_rtt: float) -> None:
    """
    Update baseline RTT ONLY when line is idle (delta < threshold).

    Architectural invariant: Prevents baseline drift under load, which would
    mask true bloat. This is PROTECTED logic - do not modify without approval.
    """
    delta = self.load_rtt - self.baseline_rtt
    if delta < self.baseline_update_threshold:
        # Line is idle - safe to update baseline
        self.baseline_rtt = (1 - self.alpha_baseline) * self.baseline_rtt + self.alpha_baseline * measured_rtt
        self.logger.debug(f"{self.wan_name}: Baseline updated (delta={delta:.1f}ms)")
    # else: Under load - freeze baseline (no log to avoid spam)
```

**Benefits:**
- Makes baseline update conditional logic more explicit
- Adds debug logging for baseline updates (helps debugging drift issues)
- Isolates protected algorithm from general EWMA update
- Better aligns with architectural documentation (baseline update is critical)

**Risk Level:** **MEDIUM**
- Touches core algorithm (baseline update threshold)
- Requires careful testing to ensure no behavior change
- Adds logging that could increase log volume (mitigated by debug-level)
- Baseline tracking is flagged as architectural invariant in CONCERNS.md

**Testability Improvement:**
- Can verify baseline freezes under load (delta > threshold → no update)
- Can verify baseline updates when idle (delta < threshold → updates)
- Can test edge case: delta exactly equals threshold
- Can verify logging behavior (baseline update events)

**Dependencies:**
- None (self-contained, no external dependencies)

**Recommendation:** Defer to Phase 14 - requires explicit approval for core algorithm changes

---

### 3.4 Simplify `measure_rtt()` Concurrent Logic

**Opportunity:** Extract concurrent futures logic to utility function or use simpler pattern

**Current State:**
- **Lines:** 30 (lines 654-683, median-of-three path)
- **Complexity:** ThreadPoolExecutor + futures + timeout + exception handling
- **Duplication:** Pattern could be reused by steering daemon (also pings multiple hosts)

**Proposed Improvement:**
```python
# In rtt_measurement.py (shared utility):
def ping_hosts_concurrent(
    self,
    hosts: list[str],
    count: int = 1,
    timeout: float = 3.0
) -> list[float]:
    """
    Ping multiple hosts concurrently and return successful RTTs.

    Args:
        hosts: List of hostnames/IPs to ping
        count: Number of pings per host
        timeout: Total timeout for all pings

    Returns:
        List of successful RTT measurements (may be empty)
    """
    # Move concurrent futures logic here
    # Return list of successful RTTs

# In WANController:
def measure_rtt(self) -> float | None:
    """Measure RTT and return average in milliseconds"""
    if self.use_median_of_three and len(self.ping_hosts) >= 3:
        rtts = self.rtt_measurement.ping_hosts_concurrent(
            hosts=self.ping_hosts[:3],
            count=1,
            timeout=3.0
        )
        if len(rtts) >= 2:
            return statistics.median(rtts)
        elif len(rtts) == 1:
            return rtts[0]
        else:
            self.logger.warning(f"{self.wan_name}: All pings failed (median-of-three)")
            return None
    else:
        return self.rtt_measurement.ping_host(self.ping_hosts[0], count=1)
```

**Benefits:**
- Moves concurrent programming complexity to shared utility
- WANController focuses on aggregation strategy (median/single)
- Reusable by steering daemon (also needs concurrent pings)
- Reduces WANController `measure_rtt()` from 42 to ~15 lines

**Risk Level:** **LOW**
- Pure refactoring - no algorithm changes
- Existing `RTTMeasurement` class is natural home for this logic
- Easy to test: mock futures, verify timeout behavior
- No state machine interaction

**Testability Improvement:**
- Can test concurrent ping logic independently (no WANController needed)
- Can verify timeout behavior in isolation
- Can test aggregation strategies (median, mean) separately from concurrent execution
- Can reuse tests for steering daemon ping logic

**Dependencies:**
- Requires changes to `src/wanctl/rtt_measurement.py` (add new method)
- WANController imports RTTMeasurement (already done)

---

### 3.5 Extract State Persistence to Dedicated Manager

**Opportunity:** Move `load_state()` and `save_state()` to separate StateManager class

**Current State:**
- **Lines:** 72 total (40 load + 32 save)
- **Responsibilities:** JSON I/O, error handling, state schema management
- **Duplication:** Steering daemon has similar pattern (lines ~900-950 in steering/daemon.py)

**Proposed Improvement:**
```python
# New file: src/wanctl/wan_controller_state.py
class WANControllerState:
    """Manages state persistence for WANController."""

    def __init__(self, state_file: Path, logger: logging.Logger):
        self.state_file = state_file
        self.logger = logger

    def load(self) -> dict | None:
        """Load state from disk, return None if not found or invalid."""
        return safe_json_load_file(
            self.state_file,
            logger=self.logger,
            default=None,
            error_context="WANController state"
        )

    def save(
        self,
        download_state: dict,
        upload_state: dict,
        ewma: dict,
        last_applied: dict
    ) -> None:
        """Save state to disk with atomic write."""
        state = {
            'download': download_state,
            'upload': upload_state,
            'ewma': ewma,
            'last_applied': last_applied,
            'timestamp': datetime.datetime.now().isoformat()
        }
        atomic_write_json(self.state_file, state)

# In WANController:
def __init__(self, ...):
    # ...
    self.state_manager = WANControllerState(config.state_file, logger)
    self._load_state_from_manager()

def _load_state_from_manager(self) -> None:
    """Load persisted state via state manager."""
    state = self.state_manager.load()
    if state is not None:
        # Restore download/upload/ewma/last_applied (lines 975-1000)
        # ...
```

**Benefits:**
- Separates persistence logic from business logic
- Enables reuse across multiple controllers (DRY principle)
- Simplifies testing (mock StateManager instead of file I/O)
- Consistent with existing patterns (`state_utils.py` has atomic_write_json, safe_json_load_file)

**Risk Level:** **MEDIUM**
- Requires creating new module (`wan_controller_state.py`)
- Changes initialization flow (state manager must be created before load)
- Affects error handling (state_manager.load() vs inline JSON parsing)
- Moderate testing effort (verify state schema compatibility)

**Testability Improvement:**
- Can test state schema validation independently
- Can verify atomic write behavior without WANController
- Can test migration from old state format to new format
- Can mock StateManager to control load/save behavior in controller tests

**Dependencies:**
- Requires new file: `src/wanctl/wan_controller_state.py`
- Uses existing utilities: `state_utils.py` (atomic_write_json, safe_json_load_file)

**Recommendation:** Consider for Phase 14, but lower priority than #3.1 and #3.2

---

## 4. Protected Zones (Core Algorithm)

These areas MUST NOT be modified without explicit approval. Changes risk breaking proven production behavior.

### 4.1 EWMA Baseline Update Threshold (Lines 688-702)

**What:** Conditional baseline update in `update_ewma()`

**Why Protected:**
- **Architectural invariant** (documented in PORTABLE_CONTROLLER_ARCHITECTURE.md)
- **Prevents baseline drift under load** - critical for detecting congestion
- If baseline tracks load RTT, delta approaches zero and bloat detection fails
- Threshold value (3ms default) is tuned for production ISP behavior

**Lines:**
```python
delta = self.load_rtt - self.baseline_rtt
if delta < self.baseline_update_threshold:
    # Line is idle - safe to update baseline
    self.baseline_rtt = (1 - self.alpha_baseline) * self.baseline_rtt + self.alpha_baseline * measured_rtt
# else: Under load - freeze baseline
```

**Safe Changes:**
- Making threshold configurable (move to YAML)
- Adding debug logging
- Adding baseline bounds validation

**Unsafe Changes:**
- Removing conditional (always update baseline)
- Changing threshold value without validation
- Modifying EWMA formula (alpha blending)

---

### 4.2 Flash Wear Protection (Lines 898, 937-938)

**What:** Rate change detection before router updates

**Why Protected:**
- **Hardware protection** - RouterOS writes queue changes to NAND flash
- Repeated writes to same value accelerate flash wear
- MikroTik devices have limited write cycles (~100K-1M depending on model)
- At 20Hz cycle rate, unnecessary writes = 72M/hour = years of flash life lost

**Lines:**
```python
if dl_rate != self.last_applied_dl_rate or ul_rate != self.last_applied_ul_rate:
    # ... apply changes ...
    self.last_applied_dl_rate = dl_rate
    self.last_applied_ul_rate = ul_rate
```

**Safe Changes:**
- Extracting to dedicated method (see #3.2)
- Adding metrics for skipped updates
- Logging change deltas

**Unsafe Changes:**
- Removing change detection (always update router)
- Not tracking last_applied_* state
- Not persisting last_applied_* across restarts

---

### 4.3 Rate Limiting Logic (Lines 905-917)

**What:** Rate limiter check before applying router updates

**Why Protected:**
- **API overload protection** - rapid state oscillations can overwhelm RouterOS API
- Default: 10 changes per 60 seconds (tested in production)
- Prevents watchdog timeouts during network instability
- Critical for REST API (SSH is more forgiving but slower)

**Lines:**
```python
if not self.rate_limiter.can_change():
    wait_time = self.rate_limiter.time_until_available()
    self.logger.warning(f"Rate limit exceeded ... next slot in {wait_time:.1f}s")
    # ... record metrics, save state, return True ...
    return True  # Don't fail - just throttle
```

**Safe Changes:**
- Making rate limit configurable (max_changes, window_seconds)
- Improving logging (include current/max counts)
- Adding metrics for throttled updates

**Unsafe Changes:**
- Removing rate limiting entirely
- Returning False (triggering watchdog restart)
- Not saving state when throttled (loses EWMA continuity)

---

### 4.4 Queue Controller State Transitions (Delegated to QueueController)

**What:** Download 4-state / Upload 3-state logic in QueueController.adjust_4state() and adjust()

**Why Protected:**
- **Core autorate algorithm** - state transitions determine bandwidth adjustments
- Hysteresis counters prevent oscillation (green_streak, soft_red_streak, red_streak)
- State-based floors prevent over-aggressive backoff
- Tuned for VDSL2/Cable/Fiber connections in production

**Lines (in QueueController class):**
- `adjust_4state()`: Lines 470-555 (download)
- `adjust()`: Lines 421-468 (upload)

**Safe Changes:**
- Extracting state transition logic to separate methods
- Adding debug logging for state changes
- Making hysteresis counts configurable (green_required, soft_red_required)

**Unsafe Changes:**
- Modifying state transition thresholds (green_threshold, soft_red_threshold, hard_red_threshold)
- Changing hysteresis counter logic (when to reset streaks)
- Altering rate adjustment formulas (step_up, factor_down)
- Modifying state-based floor selection

**Note:** QueueController is separate from WANController but closely coupled. Changes to WANController that affect state transitions (passing different thresholds, changing call sequence) are also high-risk.

---

## 5. Recommendations for Phase 14

### Priority 1: High-Value, Low-Risk (Start Here)

1. **#3.1: Extract Fallback Connectivity Logic**
   - **Why first:** Largest complexity reduction (32% of `run_cycle()`)
   - **Risk:** LOW - pure extraction, clear contract
   - **Testing:** Straightforward (mock connectivity checks)
   - **Implementation time:** 2-3 hours

2. **#3.2: Extract Flash Wear Protection Logic**
   - **Why second:** Second-largest reduction (29% of `run_cycle()`), protects critical hardware invariant
   - **Risk:** LOW - well-defined boundaries, no algorithm changes
   - **Testing:** Easy (mock router, verify skip behavior)
   - **Implementation time:** 2-3 hours

3. **#3.4: Simplify Concurrent RTT Measurement**
   - **Why third:** Reusable utility, improves steering daemon too
   - **Risk:** LOW - no algorithm changes, moves complexity to utility
   - **Testing:** Independent of WANController
   - **Implementation time:** 3-4 hours (includes rtt_measurement.py changes)

**Combined Impact:** Reduces `run_cycle()` from 176 to ~70 lines (60% reduction), improves testability across board

---

### Priority 2: Medium-Value, Medium-Risk (After P1 Complete)

4. **#3.3: Extract EWMA Update Validation**
   - **Why deferred:** Touches core algorithm (baseline update threshold)
   - **Risk:** MEDIUM - requires explicit approval, careful validation
   - **Testing:** Critical (must verify no baseline drift)
   - **Implementation time:** 4-6 hours (includes validation tests)
   - **Approval required:** Yes (core algorithm change)

5. **#3.5: Extract State Persistence to Manager**
   - **Why deferred:** Requires new module, affects initialization
   - **Risk:** MEDIUM - changes persistence flow, schema migration concerns
   - **Testing:** Moderate (state compatibility tests)
   - **Implementation time:** 6-8 hours (includes new module, migration tests)
   - **Approval required:** No (architectural improvement)

---

### Priority 3: Future Consideration (Post-Phase 14)

6. **Extract Metrics Recording to Decorator/Aspect**
   - **Why deferred:** Lower impact, requires broader refactoring pattern
   - **Risk:** LOW-MEDIUM (depends on implementation approach)
   - **Implementation time:** 8-10 hours (affects multiple methods)

7. **Split WANController into Coordinator + Worker**
   - **Why deferred:** Major architectural change, high risk
   - **Risk:** HIGH - requires rethinking class boundaries
   - **Implementation time:** 20-30 hours (major refactor)

---

### Testing Strategy Recommendations

1. **Baseline Tests (Before Any Refactoring):**
   - Capture current behavior via integration tests
   - Test all fallback modes (graceful_degradation, freeze, use_last_rtt)
   - Test flash wear protection (rate unchanged → no router call)
   - Test rate limiting (exceed window → throttle)
   - Test EWMA updates (idle vs load conditions)

2. **Per-Opportunity Tests:**
   - For each extraction (#3.1-3.5), write unit tests for new method
   - Verify existing integration tests still pass (no behavior change)
   - Add edge case tests (e.g., connectivity check timeout, rate limit boundary)

3. **Protected Zone Validation:**
   - After refactoring, re-run production validation suite
   - Verify baseline does not drift under synthetic load (RRUL test)
   - Verify flash wear protection still works (monitor router write counts)
   - Verify rate limiting still engages during instability

4. **Regression Testing:**
   - Use existing soak-monitor.sh to verify daemon stability
   - Monitor logs for new errors or unexpected behavior
   - Compare pre/post refactoring metrics (cycle duration, failure rate)

---

## 6. Summary and Next Steps

### Key Findings

1. **WANController is complex but well-structured:**
   - Clear separation from QueueController (state machine logic)
   - Good use of utilities (state_utils, rtt_measurement, rate_limiter)
   - Well-documented invariants (flash wear, baseline update threshold)

2. **Primary complexity source:** `run_cycle()` method (176 lines, 60% opportunity reduction via #3.1 + #3.2)

3. **Protected zones are clearly defined:**
   - Baseline update threshold (EWMA logic)
   - Flash wear protection (change detection)
   - Rate limiting (API overload protection)
   - QueueController state transitions (delegated, not in WANController)

4. **Refactoring opportunities are low-risk:**
   - Most are pure extractions (no algorithm changes)
   - Clear input/output contracts
   - Existing utilities support modular design

### Recommended Implementation Order (Phase 14)

1. **Week 1:** #3.1 (Fallback Logic) + #3.2 (Flash Wear) + Baseline Tests
2. **Week 2:** #3.4 (Concurrent RTT) + Integration Tests
3. **Week 3:** #3.3 (EWMA Validation) + #3.5 (State Manager) - requires approval for #3.3
4. **Week 4:** Production validation + soak testing

### Risks and Mitigation

| Risk | Mitigation |
|------|-----------|
| Baseline drift after #3.3 | Require explicit approval, add validation tests, monitor production baseline |
| State schema incompatibility after #3.5 | Add migration tests, support both old/new formats for 1 version |
| Increased test maintenance | Use parametrized tests, share fixtures, document test patterns |
| Production instability | Phase rollout (dev → staging → production), keep rollback plan |

---

**Analysis Complete:** 2026-01-13
**Next Phase:** 07-02-PLAN.md (SteeringDaemon Analysis)
