# Architecture

**Analysis Date:** 2026-01-09

## Pattern Overview

**Overall:** Daemon-based adaptive bandwidth control with optional multi-WAN steering

**Key Characteristics:**
- Continuous monitoring loops (2-second intervals for steering, configurable for autorate)
- State machine-driven (GREEN/YELLOW/SOFT_RED/RED states for congestion)
- Dual-transport router control (REST preferred, SSH fallback)
- Configuration-driven (same code for fiber, cable, DSL, multi-WAN)
- Multi-signal decision making (RTT + CAKE drops + queue depth)
- File-based state persistence with locking for concurrent safety

## Layers

**Router Control Layer:**
- Purpose: Communicate with MikroTik RouterOS device
- Contains: REST API client, SSH client, factory pattern selector
- Depends on: requests, paramiko, configuration
- Used by: Autorate and steering daemons
- Files: `src/wanctl/routeros_rest.py`, `src/wanctl/routeros_ssh.py`, `src/wanctl/router_client.py`

**Measurement Layer:**
- Purpose: Collect network metrics (RTT, CAKE stats, queue depth)
- Contains: ICMP ping, CAKE statistics reader, RTT aggregation
- Depends on: Router control layer, system utilities (ping)
- Used by: Autorate and steering daemons
- Files: `src/wanctl/rtt_measurement.py`, `src/wanctl/steering/cake_stats.py`

**Congestion Assessment Layer:**
- Purpose: Evaluate network health from measurements
- Contains: Three-state congestion model (GREEN/YELLOW/RED), confidence scoring, EWMA smoothing
- Depends on: Measurements
- Used by: State machines
- Files: `src/wanctl/steering/congestion_assessment.py`, `src/wanctl/steering/steering_confidence.py`

**State Management Layer:**
- Purpose: Persist and track daemon state across cycles
- Contains: JSON file I/O, state schemas, locking
- Depends on: File system, error handling
- Used by: Autorate and steering daemons
- Files: `src/wanctl/state_manager.py`, `src/wanctl/state_utils.py`

**Control Logic Layer:**
- Purpose: Implement bandwidth adjustment and steering algorithms
- Contains: State machines, rate limiter, queue controller, steering daemon
- Depends on: Router control, measurement, congestion assessment, state management
- Used by: Main entry points
- Files: `src/wanctl/autorate_continuous.py`, `src/wanctl/steering/daemon.py`

**Configuration & Validation Layer:**
- Purpose: Parse config YAML and validate all inputs
- Contains: Schema definitions, bandwidth bounds, RTT thresholds, identifier validation
- Depends on: PyYAML, error handling
- Used by: All layers (dependency injection)
- Files: `src/wanctl/config_base.py`, `src/wanctl/config_validation_utils.py`

## Data Flow

**Autorate Continuous Cycle (10-minute intervals by default):**

1. Load configuration from YAML
2. Acquire lock file (prevent concurrent execution)
3. Measure RTT to public reflector (ping)
4. Calculate RTT delta from baseline
5. Update EWMA (exponential moving average)
6. Read CAKE queue statistics from RouterOS
7. Assess congestion state (GREEN/YELLOW/SOFT_RED/RED)
8. Update state machine (good/bad counters, transitions)
9. Adjust CAKE queue limits if state changed
10. Persist state to JSON file
11. Release lock

**Steering Daemon Cycle (2-second intervals):**

1. Load baseline RTT from autorate state
2. Measure current RTT
3. Calculate RTT delta
4. Read CAKE statistics (optional, cake-aware mode)
5. Compute confidence score (0-100)
6. Apply sustain timers (degrade, hold_down, recovery)
7. Update steering state machine
8. Enable/disable RouterOS mangle rules if state changed
9. Persist state to JSON file

**State Machine:**
- **GOOD state:** All traffic uses primary WAN (default)
- **DEGRADED state:** Latency-sensitive traffic routed to alternate WAN
- Transitions: Triggered by sustained RTT degradation (configurable threshold + sample count)
- Recovery: Requires sustained improvement (asymmetric hysteresis)

## Key Abstractions

**WANController:**
- Purpose: Encapsulate control logic for a single WAN
- Location: `src/wanctl/autorate_continuous.py` (line ~459)
- Pattern: Class with state machine methods

**RouterOS (Client):**
- Purpose: Abstract router API (REST or SSH)
- Location: `src/wanctl/router_client.py` (factory pattern)
- Pattern: Factory returns appropriate client based on config

**StateManager:**
- Purpose: Manage state persistence and schema
- Location: `src/wanctl/state_manager.py`
- Pattern: Handles JSON serialization, validation, locking

**BaselineRTTManager:**
- Purpose: EWMA smoothing for baseline RTT with idle-only updates
- Location: `src/wanctl/baseline_rtt_manager.py`
- Pattern: Prevents baseline drift during load

**CakeStatsReader:**
- Purpose: Read CAKE queue statistics (graceful degradation if unavailable)
- Location: `src/wanctl/steering/cake_stats.py`
- Pattern: Returns None on failure, logging provides diagnostics

## Entry Points

**Autorate Entry:**
- Location: `src/wanctl/autorate_continuous.py` (main() function, line ~808)
- Triggers: systemd timer or manual invocation
- Responsibilities: Parse args, load config, run continuous control loop

**Steering Entry:**
- Location: `src/wanctl/steering/daemon.py` (main() function, line ~889)
- Triggers: systemd timer (every 2 seconds)
- Responsibilities: Parse args, load steering config, run steering cycle

**Calibration Entry:**
- Location: `src/wanctl/calibrate.py`
- Triggers: Manual invocation for baseline RTT discovery
- Responsibilities: Measure RTT, suggest bandwidth limits, no persistent changes

## Error Handling

**Strategy:** Exceptions thrown at layer boundaries, caught and logged at daemon level, operations continue with graceful degradation

**Patterns:**
- `ConfigValidationError` - Invalid configuration (fatal)
- `LockAcquisitionError` - Cannot acquire lock (skip cycle, retry next interval)
- CAKE read failures - Log warning, continue with RTT-only mode
- RTT measurement failures - Retry up to 3 times, use last known RTT as fallback
- RouterOS command failures - Log error, skip state transition, preserve previous state

## Cross-Cutting Concerns

**Input Validation:**
- All config values validated at parse time
- All user input (queue names, WAN names) validated against identifier rules
- Prevents command injection in RouterOS queries
- Centralized in `config_validation_utils.py`

**Bounds Checking:**
- RTT thresholds: MIN_SANE_BASELINE_RTT=10ms, MAX_SANE_BASELINE_RTT=60ms
- Bandwidth limits: enforced_rate_bounds prevents queue rate out of range
- EWMA factors: alpha must be in [0.0, 1.0]
- Confidence scores: clamped to [0, 100]

**Locking:**
- File-based locks prevent concurrent execution of same WAN
- Lock path: `/run/wanctl/<wan_name>.lock`
- Ensures state consistency across processes
- Files: `src/wanctl/lockfile.py`

**Logging:**
- Structured logging with context (WAN name, cycle number)
- Levels: DEBUG (detailed), INFO (state transitions), WARNING (failures), ERROR (fatal)
- Destination: File and optionally syslog

---

*Architecture analysis: 2026-01-09*
*Update when major patterns change*
