# Phase 51: Steering Reliability - Context

**Gathered:** 2026-03-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix steering daemon reliability issues: add warning logging for legacy state normalization, change anomaly detection from cycle-failure to cycle-skip semantics, add stale baseline detection with degradation, and replace raw JSON loading with safe_json_load_file(). Requirements: STEER-01, STEER-02, STEER-03, STEER-04.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion

User reviewed all gray areas and determined requirements are specific enough for Claude to handle implementation decisions. Key areas at Claude's discretion:

- **Anomaly skip semantics (STEER-02):** Anomaly detection currently returns False (cycle-failure), incrementing consecutive_failures toward watchdog restart after 3 strikes. Requirement says return True (cycle-skip). Claude decides: whether to reset failure counter, whether to record metrics, how to log the distinction between "skip" and "success."
- **Stale baseline degradation (STEER-03):** When baseline RTT is >5 minutes stale, requirement says "warns/degrades." Claude decides: degradation behavior (config fallback vs last loaded value vs disable steering), whether 5min threshold is configurable, warning rate-limiting at 20Hz cycle rate.
- **Warning rate-limiting (STEER-01, STEER-03):** Both add warnings that could fire every 50ms cycle. Claude decides rate-limiting approach (e.g., log once, use existing rate_limiter, or log every N cycles).

</decisions>

<specifics>
## Specific Ideas

No specific requirements beyond the architectural review findings. All four requirements are prescriptive:
- STEER-01: Log warning when legacy state name normalization triggers in `_is_current_state_good()`
- STEER-02: Anomaly detection returns cycle-skip (True) instead of cycle-failure (False)
- STEER-03: BaselineLoader checks autorate state file timestamp, warns/degrades when >5min stale
- STEER-04: BaselineLoader uses `safe_json_load_file()` instead of raw `open()`/`json.load()`

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `safe_json_load_file()` (state_utils.py:132-178): Handles JSONDecodeError, OSError, generic exceptions with configurable default and error_context -- direct replacement for BaselineLoader's raw open/json.load
- `_is_current_state_good()` (steering/daemon.py:694-707): Pure boolean check against config.state_good and 3 legacy names (SPECTRUM_GOOD, WAN1_GOOD, WAN2_GOOD) -- no logging currently
- `MAX_SANE_RTT_DELTA_MS = 500.0` (steering/daemon.py:117): Anomaly threshold constant
- `BaselineLoader` (steering/daemon.py:560-608): Reads `state['ewma']['baseline_rtt']` from autorate state file, validates against baseline_rtt_min/max bounds

### Established Patterns
- Failure accumulation in `run_daemon_loop()` (daemon.py:1498-1510): `consecutive_failures` increments on False return from `run_cycle()`, watchdog stops at 3 consecutive failures
- Rate-limited logging: `rate_limiter.py` exists with `RateLimiter` class for throttling operations
- `atomic_write_json()` in state_utils.py for safe state writes -- same module as safe_json_load_file
- autorate_continuous.py writes state file with `last_updated` timestamp already present in state dict

### Integration Points
- `BaselineLoader.load_baseline_rtt()` called from `SteeringDaemon._update_baseline()` (daemon.py) -- runs each cycle
- Anomaly detection at daemon.py:1311-1324 sets `anomaly_detected = True`, returned as False at line 1448-1450
- State file path from `self.config.primary_state_file` -- autorate writes this file each cycle
- `run_cycle()` return value consumed by `run_daemon_loop()` for failure counting (daemon.py:1498-1502)

### Key Behavior Notes
- Anomaly detection currently: delta > 500ms triggers warning log, sets anomaly_detected=True, run_cycle returns False, failure counter increments. After 3 consecutive anomalies, watchdog stops notifying -> systemd restart. This is the core bug STEER-02 fixes.
- BaselineLoader currently has NO staleness check -- reads whatever is in the file regardless of age
- BaselineLoader uses raw open/json.load with manual try/except -- safe_json_load_file handles all this plus more error types

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope.

</deferred>

---

*Phase: 51-steering-reliability*
*Context gathered: 2026-03-07*
