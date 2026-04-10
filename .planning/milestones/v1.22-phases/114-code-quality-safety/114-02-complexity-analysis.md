# Complexity Hotspot Analysis (CQUAL-05)

## Summary

- **Files analyzed:** 5 (top by LOC)
- **Total LOC:** 10,605
- **Functions exceeding complexity 15:** 16 (from Phase 112 baseline)
- **Functions exceeding complexity 20:** 4
- **All recommendations deferred to v1.23** per D-10 -- document only, no code changes

## Phase 112 Baseline Reference

From `112-03-findings.md`: 16 functions exceed mccabe complexity 15, with 4 exceeding 20. Current `pyproject.toml` uses `max-complexity=20` with per-file-ignores for the 4 highest (`autorate_continuous.py`, `health_check.py`, `steering/daemon.py`).

---

## Per-File Analysis

### 1. autorate_continuous.py (4,342 LOC)

The largest file in the codebase. Contains the main autorate daemon, its configuration, bandwidth state machine, per-WAN controller, and the daemon entry point.

#### Responsibilities

| # | Responsibility | Lines | Span | Description |
|---|----------------|-------|------|-------------|
| 1 | Config class | 129-1175 | 1,046 | YAML config loading with 20+ `_load_*` methods |
| 2 | RouterOS class | 1176-1224 | 48 | Thin wrapper for router API calls |
| 3 | QueueController class | 1225-1467 | 242 | 3-state + 4-state bandwidth FSM |
| 4 | _apply_tuning_to_controller | 1468-1548 | 80 | Maps tuning results to controller attributes |
| 5 | WANController class | 1549-3450 | 1,901 | Per-WAN control loop: RTT, EWMA, signals, alerts |
| 6 | ContinuousAutoRate class | 3451-3573 | 122 | Multi-WAN orchestrator (thin) |
| 7 | Startup helpers | 3574-3793 | 219 | validate_config_mode, parse_args, init_storage, etc. |
| 8 | main() | 3794-4342 | 548 | CLI entry point + daemon loop + shutdown |

#### High-Complexity Functions

| Function | Complexity | Lines | Span | Why complex |
|----------|-----------|-------|------|-------------|
| `main()` | 68 | 3794-4342 | 548 | Argument parsing, 3 operational modes (validate/oneshot/daemon), daemon loop with failure tracking, watchdog management, maintenance scheduling, tuning scheduling, IRTT thread lifecycle, shutdown with cleanup |
| `run_cycle()` | 30 | 2616-2993 | 377 | RTT measurement with fallback paths, ICMP failure handling, signal processing, EWMA updates, baseline management, 4-state download + 3-state upload FSM, rate application, alert checking, profiling |
| `_load_tuning_config()` | 19 | 939-1108 | 169 | Validates 15+ tuning parameters with type checks, range validation, default values, and interconnected constraints |
| `_load_alerting_config()` | 17 | 519-656 | 137 | Validates 7 alert types, each with enabled/threshold/cooldown fields, plus global webhook config |
| `adjust_4state()` | 17 | 1340-1467 | 127 | 4-state FSM with hysteresis: streak tracking, sustain logic, transition reasons, floor clamping |
| `_apply_tuning_to_controller()` | 16 | 1468-1548 | 80 | Parameter dispatch: 12 elif branches mapping parameter names to controller attributes |
| `_check_congestion_alerts()` | 15 | 2994-3110 | 116 | Sustained congestion detection: per-direction streak tracking, cooldown timers, alert firing |
| `_check_irtt_loss_alerts()` | 15 | 3111-3203 | 92 | 3-tier IRTT loss alerting: packet loss, sustained loss, loss spike with cooldowns |

#### Extraction Recommendations (deferred to v1.23 per D-10)

| Candidate | Target module | Risk | Benefit | Effort |
|-----------|---------------|------|---------|--------|
| Config class (1,046 LOC) | `autorate_config.py` | **Low** -- pure config loading, no runtime coupling | Reduces file by 24%. Config has clear boundary. | Low |
| main() daemon loop (lines 3905-4140) | `autorate_daemon_loop.py` | **Medium** -- needs access to controller, watchdog, IRTT thread | Reduces main() from 548 to ~100 lines (parse+init+call). Complexity 68 -> ~15 + ~35. | Medium |
| Alert methods (3 methods, ~320 LOC) | `alert_checks.py` | **Low** -- stateless methods that take WANController state as params | Clean separation. Already use self only for state reads. | Low |
| Startup helpers (already extracted) | (no change) | N/A | Already in standalone functions (_init_storage, etc.) | N/A |

---

### 2. steering/daemon.py (2,411 LOC)

The steering daemon. Contains steering-specific config, RouterOS controller for mangle rules, baseline RTT loading, the steering state machine, and the daemon entry point.

#### Responsibilities

| # | Responsibility | Lines | Span | Description |
|---|----------------|-------|------|-------------|
| 1 | SteeringConfig class | 133-696 | 563 | YAML config loading with 20+ `_load_*` methods |
| 2 | create_steering_state_schema | 697-733 | 36 | State file schema definition |
| 3 | RouterOSController class | 734-848 | 114 | Mangle rule enable/disable via router API |
| 4 | BaselineLoader class | 849-955 | 106 | Loads baseline RTT from autorate state files |
| 5 | SteeringDaemon class | 956-2078 | 1,122 | Steering state machine + cycle logic |
| 6 | run_daemon_loop() | 2079-2170 | 91 | Daemon loop with watchdog + failure tracking |
| 7 | main() | 2171-2411 | 240 | CLI entry point + startup + shutdown |

#### High-Complexity Functions

| Function | Complexity | Lines | Span | Why complex |
|----------|-----------|-------|------|-------------|
| `main()` | 23 | 2171-2411 | 240 | Argument parsing, config loading, storage init, maintenance, lock acquisition, reset mode, daemon mode with shutdown cleanup |
| `_load_alerting_config()` | 17 | 448-585 | 137 | Similar to autorate: validates multiple alert types with thresholds and cooldowns |
| `_load_wan_state_config()` | 14 | 323-447 | 124 | WAN-aware steering config with zone mappings, grace periods, confidence settings |
| `run_cycle()` | 14 | 1799-2078 | 279 | RTT measurement, baseline update, EWMA, state machine update, CAKE stats, profiling |

#### Extraction Recommendations (deferred to v1.23 per D-10)

| Candidate | Target module | Risk | Benefit | Effort |
|-----------|---------------|------|---------|--------|
| SteeringConfig class (563 LOC) | `steering/config.py` | **Low** -- pure config loading, mirrors autorate pattern | Reduces file by 23%. Clean boundary. | Low |
| main() startup/shutdown (lines 2171-2290 + 2350-2411) | Refactor into extract functions | **Medium** -- needs careful lock/cleanup ordering | Reduces main() from 240 to ~80 lines. Complexity 23 -> ~10 + helpers. | Medium |

---

### 3. check_config.py (1,472 LOC)

Configuration validation CLI. Contains all validation rules for autorate, steering, and linux-cake configs, plus output formatting and the CLI entry point.

#### Responsibilities

| # | Responsibility | Lines | Span | Description |
|---|----------------|-------|------|-------------|
| 1 | Data types (Severity, CheckResult) | 39-337 | 298 | Enum + result dataclass with display formatting |
| 2 | Autorate validators | 338-765 | 427 | Schema, cross-field, paths, env vars, deprecated params |
| 3 | Steering validators | 798-995 | 197 | Schema, cross-field, unknown keys, deprecated for steering |
| 4 | Linux CAKE validator | 1104-1200 | 96 | Bridge/interface/CAKE-specific validation |
| 5 | Output formatting | 1258-1387 | 129 | Text + JSON result formatting |
| 6 | CLI entry point | 1388-1472 | 84 | Argument parsing + validator dispatch |

#### High-Complexity Functions

| Function | Complexity | Lines | Span | Why complex |
|----------|-----------|-------|------|-------------|
| `validate_cross_fields()` | 15 | 367-495 | 128 | Many cross-field constraints: floor < ceiling, threshold ordering, scheduler dependencies |
| `format_results()` | 13 | 1258-1336 | 78 | Category grouping, severity counting, color formatting, summary generation |

#### Extraction Recommendations (deferred to v1.23 per D-10)

| Candidate | Target module | Risk | Benefit | Effort |
|-----------|---------------|------|---------|--------|
| Steering validators | `check_steering_config.py` | **Low** -- standalone functions with no state | Reduces file by 13%. Parallel to autorate validators. | Low |
| Output formatting | `check_formatter.py` | **Low** -- pure formatting, no validation logic | Clean separation of concerns. | Low |

---

### 4. check_cake.py (1,249 LOC)

CAKE audit CLI. Contains router connectivity checks, queue tree validation, CAKE parameter verification, diff/fix workflow, and CLI entry point.

#### Responsibilities

| # | Responsibility | Lines | Span | Description |
|---|----------------|-------|------|-------------|
| 1 | Config extraction helpers | 81-182 | 101 | Extract router config, queue names, ceilings from YAML |
| 2 | Audit checks | 183-743 | 560 | env vars, connectivity, queue tree, CAKE params, link params, mangle rules |
| 3 | Fix workflow | 744-1099 | 355 | Snapshot, diff, confirm, apply changes |
| 4 | CLI entry point | 1100-1249 | 149 | Argument parsing, client creation, mode dispatch |

#### High-Complexity Functions

| Function | Complexity | Lines | Span | Why complex |
|----------|-----------|-------|------|-------------|
| `run_audit()` | 13 | 626-743 | 117 | Orchestrates 6 check categories with conditional skipping based on config type and previous failures |
| `run_fix()` | 12 | 937-1047 | 110 | Snapshot-diff-confirm-apply workflow with direction-specific change extraction |
| `main()` | 13 | 1156-1249 | 93 | Mode dispatch (audit/fix/compare), config loading, client creation, exit code logic |

#### Extraction Recommendations (deferred to v1.23 per D-10)

| Candidate | Target module | Risk | Benefit | Effort |
|-----------|---------------|------|---------|--------|
| Fix workflow (355 LOC) | `check_cake_fix.py` | **Low** -- separate workflow with clear boundary | Reduces file by 28%. Audit and fix have different responsibilities. | Low |

---

### 5. calibrate.py (1,131 LOC)

Interactive calibration CLI. Contains network measurement functions, binary search algorithm, config generation, step-based calibration workflow, and CLI entry point.

#### Responsibilities

| # | Responsibility | Lines | Span | Description |
|---|----------------|-------|------|-------------|
| 1 | Display helpers + data types | 64-190 | 126 | Colors, print functions, CalibrationResult |
| 2 | Network measurement functions | 191-512 | 321 | SSH check, netperf check, RTT, throughput, CAKE limits, binary search |
| 3 | Calibration steps | 622-918 | 296 | Step-based workflow: connectivity, baseline, throughput, binary search, summary, save |
| 4 | Orchestration + CLI | 919-1131 | 212 | run_calibration sequence, main() argument parsing |

#### High-Complexity Functions

No functions in calibrate.py exceed complexity 15. The highest-complexity function is `run_calibration()` which orchestrates the step functions in sequence. The step-based decomposition already keeps individual functions manageable.

#### Extraction Recommendations (deferred to v1.23 per D-10)

| Candidate | Target module | Risk | Benefit | Effort |
|-----------|---------------|------|---------|--------|
| Network measurements | `calibrate_measurements.py` | **Low** -- pure functions with subprocess calls | Clean separation. Measurements are reusable. | Low |
| Display helpers | Consolidate with check_config formatting | **Low** -- shared Colors class pattern | DRY principle. Multiple CLIs use similar output. | Low |

---

## Priority Ranking

Ranked by (complexity reduction * safety * effort):

| Priority | Extraction | From File | Risk | Complexity Reduction | Estimated Effort |
|----------|-----------|-----------|------|---------------------|-----------------|
| 1 | **Config class -> autorate_config.py** | autorate_continuous.py | Low | -1,046 LOC (24%) | Low (move + import update) |
| 2 | **SteeringConfig -> steering/config.py** | steering/daemon.py | Low | -563 LOC (23%) | Low (move + import update) |
| 3 | **main() daemon loop extraction** | autorate_continuous.py | Medium | Complexity 68 -> ~15 + ~35 | Medium (refactor) |
| 4 | **Fix workflow -> check_cake_fix.py** | check_cake.py | Low | -355 LOC (28%) | Low (move + import update) |
| 5 | **Alert methods extraction** | autorate_continuous.py | Low | -320 LOC from WANController | Low (extract methods) |
| 6 | **Steering validators -> check_steering_config.py** | check_config.py | Low | -197 LOC (13%) | Low (move) |
| 7 | **main() startup extraction** | steering/daemon.py | Medium | Complexity 23 -> ~10 | Medium (refactor) |
| 8 | **Network measurements** | calibrate.py | Low | -321 LOC (28%) | Low (move) |

## v1.23 Recommendation

### Suggested extraction order

1. **Wave 1 (Config extraction):** Move Config classes out of both daemon files (Priority 1+2). These are the safest, largest extractions with zero runtime risk. Combined: 1,609 LOC removed from the two largest files.

2. **Wave 2 (CLI tool cleanup):** Extract fix workflow from check_cake.py (Priority 4) and steering validators from check_config.py (Priority 6). Low risk, improves maintainability of CLI tools.

3. **Wave 3 (Core daemon refactoring):** Extract main() daemon loop (Priority 3) and alert methods (Priority 5) from autorate_continuous.py. This directly targets the complexity-68 `main()` and the complexity-30 `run_cycle()`.

4. **Wave 4 (Steering daemon + calibrate):** Refactor steering main() (Priority 7) and split calibrate.py (Priority 8).

### Estimated total effort
- **Wave 1:** 2-4 hours (mechanical move + import updates + test verification)
- **Wave 2:** 1-2 hours (same pattern)
- **Wave 3:** 4-8 hours (requires careful refactoring of daemon loop + testing under production conditions)
- **Wave 4:** 2-3 hours

### Risk mitigation
- Each extraction should be followed by full test suite run (`pytest tests/ -v`)
- Config extractions (Wave 1) should verify YAML loading still works identically
- Daemon loop extraction (Wave 3) should include production soak testing
- All extractions should maintain the existing public API (entry points, class names)

### Complexity target
After all extractions, the target complexity profile would be:
- No function above complexity 35 (currently main() is 68)
- No file above 2,500 LOC (currently autorate_continuous.py is 4,342)
- Max 3 functions above complexity 20 (currently 4)
