# Phase 145: Method Extraction & Simplification - Research

**Researched:** 2026-04-06
**Domain:** Python refactoring -- method extraction, cyclomatic complexity reduction
**Confidence:** HIGH

## Summary

Phase 145 targets ~23 functions exceeding 100 lines (excluding docstrings) across 14 source files, with 7 "mega-functions" exceeding 200 lines. The largest is `main()` in `autorate_continuous.py` at 612 lines, followed by `WANController.run_cycle()` at 447, `WANController.__init__()` at 408, and `HealthCheckHandler._get_health_status()` at 347. There are also 10 C901 violations at threshold 15 that need resolution.

The codebase already has a strong pattern of extraction: `autorate_continuous.py` already has 5 extracted helpers (`_parse_autorate_args`, `_init_storage`, `_acquire_daemon_locks`, `_start_servers`, `_start_irtt_thread`). The phase extends this pattern. The key constraint is zero behavioral change -- all 4,239 tests must pass unchanged after every extraction, and mock targets (`patch("wanctl.module.function")`) must remain valid.

**Primary recommendation:** Decompose by file priority (wan_controller.py > autorate_continuous.py > steering/daemon.py > health_check.py > remaining), using underscore-prefixed private helpers within the same module, following lifecycle phase boundaries (init, setup, execute, cleanup).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Target functions >100 lines (Mega + Large tiers, ~21 functions). Medium functions (50-100 lines) are at Claude's discretion -- split proactively if it improves readability, otherwise leave
- **D-02:** Include the steering/ subpackage in scope. steering/daemon.py (run_cycle 268 LOC, main 214 LOC) and steering/health.py (_get_health_status 211 LOC) have the same mega-function problem
- **D-03:** C901 complexity is already clean -- no violations at any threshold. Focus is entirely on line count reduction, not branching depth
- **D-04:** Decompose mega-functions (>200 LOC) by lifecycle phases: init, setup, validate, execute, cleanup. Each phase becomes a named helper function. Natural for main() and __init__ patterns
- **D-05:** main() stays in autorate_continuous.py. Helpers extracted alongside. pyproject.toml entry_points, systemd units, and docs are NOT modified
- **D-06:** Same approach for steering/daemon.py main() -- keep in place, extract helpers
- **D-07:** Approximate ~50 line target. Allow 50-60 for functions that are cohesive and readable as-is. Don't force artificial splits on clean code just to hit a number
- **D-08:** Measurement: lines excluding docstrings. Blank lines and comments count toward the total
- **D-09:** Extracted helpers stay in the same module as underscore-prefixed private functions (_setup_logging, _init_storage, etc.). Keeps related code together
- **D-10:** Exception: if placing helpers in the same file would push it over ~500 LOC (Phase 144 threshold), move helpers to a new focused module instead
- **D-11:** Follow existing naming patterns: descriptive verb_noun names (e.g., _parse_autorate_args, _init_storage, _acquire_daemon_locks)

### Claude's Discretion
- Exact decomposition boundaries for each function
- Whether medium functions (50-100 lines) get split or left as-is
- Helper grouping when multiple helpers are extracted from one function
- Whether to create new modules for files that would exceed 500 LOC after extraction
- Naming convention for extracted helpers (Claude picks descriptive names per function)

### Deferred Ideas (OUT OF SCOPE)
- Medium functions (50-100 lines, ~79 functions) may be addressed proactively at Claude's discretion but are not mandatory targets
- Pre-existing files between 500-836 LOC deferred from Phase 144 (health_check, routeros_rest, state_manager, history) -- file-level splitting not in scope here, but method extraction within them is
- "Integration test for router communication" -- testing area, not relevant to method extraction scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CPLX-02 | Long methods (>50 lines) are extracted into smaller, testable functions | Inventory of 23 functions >100 lines across 14 files; lifecycle decomposition pattern; underscore-prefixed private helper strategy |
| CPLX-04 | High cyclomatic complexity functions are refactored (nested if/else, long chains) | 10 C901 violations at threshold 15 identified; per-file-ignores currently suppress 5 files; extraction will naturally reduce complexity by splitting branches into focused helpers |
</phase_requirements>

## Standard Stack

No new libraries required. This is a pure refactoring phase using existing tooling.

### Core (existing, verified)
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| ruff | (project venv) | Lint + format + C901 checks | Already configured in pyproject.toml with C901 rule [VERIFIED: pyproject.toml] |
| mypy | (project venv) | Type checking post-extraction | Already configured, `check_untyped_defs = true` [VERIFIED: pyproject.toml] |
| pytest | (project venv) | Regression testing | 4,239 tests, comprehensive coverage [VERIFIED: CLAUDE.md] |

### Verification Commands
```bash
# Quick validation after each extraction
.venv/bin/ruff check src/wanctl/<modified_file>.py
.venv/bin/mypy src/wanctl/<modified_file>.py
.venv/bin/pytest tests/test_<module>.py -v

# Full CI gate
make ci

# C901 check at target threshold
.venv/bin/ruff check src/wanctl/ --select C901 --config "lint.mccabe.max-complexity = 15"
```

## Architecture Patterns

### Extraction Pattern: Same-File Private Helpers

The codebase already uses this pattern extensively. `autorate_continuous.py` has 5 module-level helpers already extracted from `main()`. [VERIFIED: source code grep]

```python
# Pattern: Extract contiguous block into _verb_noun private function
# Before:
def main() -> int | None:
    # ... 50 lines of setup ...
    # ... 100 lines of loop ...
    # ... 80 lines of cleanup ...

# After:
def _setup_daemon(controller, args) -> tuple[...]:
    """Initialize daemon state: locks, servers, threads."""
    # ... 50 lines ...

def _run_daemon_loop(controller, ...) -> None:
    """Main control loop with cycle management."""
    # ... 50 lines calling sub-helpers ...

def _cleanup_daemon(controller, lock_files, ...) -> None:
    """Shutdown: save state, release locks, close connections."""
    # ... 50 lines ...

def main() -> int | None:
    """Entry point -- orchestrates setup, loop, cleanup."""
    # ... 20 lines delegating to helpers ...
```

### Extraction Pattern: Method to Private Method (Classes)

For class methods like `WANController.__init__()` and `run_cycle()`:

```python
# Before:
class WANController:
    def __init__(self, ...):
        # 408 lines of initialization

# After:
class WANController:
    def __init__(self, ...):
        self._init_core_state(config)
        self._init_queue_controllers(config)
        self._init_rate_protection()
        self._init_storage(config)
        self._init_alerting(config)
        self._init_signal_processing(config)
        self._init_irtt_observation(config)
        self._init_fusion(config)
        self._init_reflector_scoring(config)
        self._init_profiling(config)
        self._init_tuning(config)
        self.load_state()
        if self._tuning_enabled and self._metrics_writer is not None:
            self._restore_tuning_params()

    def _init_core_state(self, config: Config) -> None:
        """Initialize baseline RTT, ping config, thresholds."""
        # ~20 lines
```

### Extraction Pattern: run_cycle Subsystem Extraction

`WANController.run_cycle()` already uses `PerfTimer` subsystem labels. Each subsystem block is a natural extraction boundary. [VERIFIED: source code]

```python
# Current structure with PerfTimer blocks:
# - autorate_rtt_measurement (~30 lines)
# - autorate_state_management (~200 lines, contains 5 sub-timers)
#   - autorate_signal_processing
#   - autorate_ewma_spike
#   - autorate_congestion_assess
#   - autorate_irtt_observation
#   - autorate_logging_metrics
# - autorate_router_communication (~45 lines)
# - autorate_post_cycle (~25 lines)

# Each PerfTimer block becomes a helper:
def _measure_rtt_subsystem(self) -> tuple[float | None, float | None]:
    """RTT measurement subsystem. Returns (measured_rtt, raw_rtt)."""

def _process_state_subsystem(self, measured_rtt: float) -> tuple[str, int, str, int, ...]:
    """State management subsystem. Returns zone/rate/transition info."""
```

### Lifecycle Phase Decomposition (D-04)

For mega-functions, decompose by lifecycle:

| Lifecycle Phase | Applies To | Pattern |
|----------------|------------|---------|
| init | `__init__()` methods | Group attribute initialization by concern |
| setup | `main()` functions | Lock acquisition, server startup, thread creation |
| validate | Config loading methods | Input validation, cross-field checks |
| execute | `run_cycle()`, loop bodies | Per-cycle subsystem dispatch |
| cleanup | `finally` blocks | Ordered resource release |

### Anti-Patterns to Avoid

- **Breaking mock targets:** If `patch("wanctl.wan_controller.record_ping_failure")` exists in tests, the function `record_ping_failure` must stay importable from `wanctl.wan_controller`. Extracting to a new module breaks the patch path. [VERIFIED: 382 patch calls in test_wan_controller.py]
- **Introducing new parameters just to extract:** Private helpers should access `self.*` attributes directly (for methods) or receive the minimum necessary arguments (for module functions). Don't create parameter-heavy intermediate APIs.
- **Losing PerfTimer coverage:** `run_cycle()` has instrumented subsystem timers. Extracted helpers should be called WITHIN the existing `PerfTimer` context managers, not replace them.
- **Splitting nested closures:** `retry_with_backoff` has decorator/wrapper nesting that is inherently complex. Don't force-extract -- the complexity is structural.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Counting function lines | Manual counting | AST-based script (used in research) | Docstring exclusion, nested function handling |
| Verifying no behavioral regression | Manual review | `make ci` (ruff + mypy + pytest) | 4,239 automated tests catch regressions |
| C901 threshold checks | Manual complexity counting | `ruff check --select C901 --config "..."` | Automated, consistent |

## Common Pitfalls

### Pitfall 1: Mock Target Breakage
**What goes wrong:** Tests use `patch("wanctl.module.function_name")` extensively. If an extracted helper moves to a new module, the patch target path changes and tests fail with `ModuleNotFoundError` or silent no-op patches.
**Why it happens:** Phase 144 already encountered this -- `_apply_tuning_to_controller` moved from autorate_continuous to wan_controller, requiring import path updates.
**How to avoid:** Keep helpers in the same module (D-09). When extraction MUST move code, grep all test files for the old path: `grep -r "patch.*module_name.function" tests/`
**Warning signs:** Tests pass but coverage drops (patching the wrong target silently succeeds).

### Pitfall 2: File LOC Explosion from In-File Helpers
**What goes wrong:** Adding 10 helpers to a 2,579-line file makes it even larger. wan_controller.py is already the biggest file.
**Why it happens:** D-09 says same-file helpers. D-10 provides the escape valve at ~500 LOC.
**How to avoid:** wan_controller.py (2,579 LOC) is already far above 500 LOC -- this is a class-internal extraction, not a file-level concern. New private methods don't add net lines (they replace inline code). The file LOC should stay roughly constant or decrease slightly (helper signatures + calls add ~2 lines per extraction, but formatting improvements offset this).
**Warning signs:** If total LOC increases by more than 5% after extraction, something is wrong.

### Pitfall 3: Accidentally Changing Behavior via Variable Scope
**What goes wrong:** When extracting a block from a function, local variables that were set early and used later may become inaccessible to the helper. The helper either receives them as parameters or sets them as return values.
**Why it happens:** Python's scoping rules mean a helper function can't modify the caller's local variables.
**How to avoid:** For class methods, use `self.*` attributes. For module functions, return tuples and unpack. Identify ALL variables that cross the extraction boundary before cutting.
**Warning signs:** `UnboundLocalError` at runtime, or tests showing different state after extraction.

### Pitfall 4: C901 Complexity Not Reduced by Line Extraction
**What goes wrong:** Extracting a long sequential block (no branches) reduces lines but not cyclomatic complexity. The C901 violations remain.
**Why it happens:** Cyclomatic complexity counts branches (if/elif/else/for/while/except/with), not lines. A 100-line function with no branches has complexity 1.
**How to avoid:** For C901 reduction, extract BRANCHING blocks specifically. `validate_cross_fields` (complexity 17) needs branch extraction, not sequential extraction.
**Warning signs:** After extraction, re-run `ruff check --select C901` and verify the count decreased.

### Pitfall 5: Nested PerfTimer Context Managers
**What goes wrong:** `run_cycle()` uses nested `with PerfTimer(...)` blocks. If a helper is extracted to run outside the timer, profiling data changes. If the helper opens its own timer, profiling overhead increases.
**Why it happens:** The PerfTimer structure is deliberate for profiling cycle budgets (Phase 131).
**How to avoid:** Extract the CODE INSIDE the `with` block, keeping the `with PerfTimer(...)` wrapper in `run_cycle()`. The helper is called within the timer context.
**Warning signs:** Health endpoint `/health` shows different cycle budget breakdown, or profiling data stops appearing.

## Current State Inventory

### Functions >100 Lines (Mandatory Targets per D-01)

**Tier 1: Mega-Functions (>200 lines) -- 7 functions**

| File | Function | Lines | C901 | Natural Decomposition |
|------|----------|-------|------|----------------------|
| autorate_continuous.py | `main()` | 612 | 68 (suppressed) | init/setup/loop/cleanup lifecycle |
| wan_controller.py | `run_cycle()` | 447 | 36 (suppressed) | PerfTimer subsystem boundaries |
| wan_controller.py | `__init__()` | 408 | n/a | Concern-grouped attribute init |
| health_check.py | `_get_health_status()` | 347 | 24 (suppressed) | Response section assembly |
| steering/daemon.py | `run_cycle()` | 269 | n/a | PerfTimer subsystem boundaries |
| steering/daemon.py | `main()` | 215 | 23 (suppressed) | init/setup/loop/cleanup lifecycle |
| steering/health.py | `_get_health_status()` | 212 | n/a | Response section assembly |

**Tier 2: Large Functions (100-200 lines) -- 16 functions**

| File | Function | Lines | C901 at 15 |
|------|----------|-------|------------|
| autorate_config.py | `_load_tuning_config()` | 167 | 19 (violation) |
| check_config_validators.py | `validate_cross_fields()` | 149 | 17 (violation) |
| check_cake.py | `check_tin_distribution()` | 141 | clean |
| steering/daemon.py | `__init__()` | 136 | clean |
| queue_controller.py | `adjust_4state()` | 135 | clean |
| tuning/strategies/signal_processing.py | `tune_alpha_load()` | 135 | 18 (violation) |
| autorate_config.py | `_load_alerting_config()` | 128 | 17 (violation) |
| steering/daemon.py | `SteeringConfig._load_alerting_config()` | 128 | clean |
| autorate_config.py | `_load_fusion_config()` | 119 | clean |
| history.py | `main()` | 115 | 17 (violation) |
| steering/daemon.py | `SteeringConfig._load_wan_state_config()` | 115 | clean |
| webhook_delivery.py | `_do_deliver()` | 109 | clean |
| check_cake_fix.py | `run_fix()` | 104 | clean |
| check_cake.py | `run_audit()` | 103 | 16 (violation) |
| wan_controller.py | `_check_congestion_alerts()` | 102 | clean |
| calibrate.py | `generate_config()` | 101 | clean |

### C901 Violations at Threshold 15 (10 total)

| File | Function | Complexity | Current Status |
|------|----------|-----------|----------------|
| autorate_config.py | `_load_alerting_config` | 17 | No per-file-ignore |
| autorate_config.py | `_load_tuning_config` | 19 | No per-file-ignore |
| check_cake.py | `run_audit` | 16 | No per-file-ignore |
| check_config_validators.py | `validate_cross_fields` | 17 | No per-file-ignore |
| error_handling.py | `handle_errors` | 18 | No per-file-ignore |
| error_handling.py | `decorator` | 17 | No per-file-ignore |
| error_handling.py | `wrapper` | 16 | No per-file-ignore |
| history.py | `main` | 17 | No per-file-ignore |
| router_connectivity.py | `classify_failure_type` | 16 | No per-file-ignore |
| tuning/strategies/signal_processing.py | `tune_alpha_load` | 18 | No per-file-ignore |

[VERIFIED: `ruff check src/wanctl/ --select C901 --config "lint.mccabe.max-complexity = 15"`]

Note: 5 additional files have C901 per-file-ignores at the current threshold of 20 (autorate_continuous.py, wan_controller.py, queue_controller.py, health_check.py, steering/daemon.py). These will be addressed by line-count extraction which naturally reduces complexity.

### File LOC Impact Assessment (D-10 Check)

Files that receive helpers must not exceed ~500 total LOC (or stay within current size if already above). Since method extraction replaces inline code with calls, net LOC change is minimal (~+2 lines per extraction for function signature overhead).

| File | Current LOC | Will Receive Helpers | LOC Risk |
|------|-------------|---------------------|----------|
| wan_controller.py | 2,579 | Many class methods | LOW -- already a class file, methods don't add net lines |
| steering/daemon.py | 2,418 | Many class + module methods | LOW -- same reasoning |
| autorate_continuous.py | 1,095 | Module-level helpers | LOW -- already has 5 helpers |
| autorate_config.py | 1,200 | Class methods | LOW -- internal method splits |
| health_check.py | 836 | Class methods | LOW |
| check_cake.py | 1,114 | Module functions | LOW |
| check_config_validators.py | 692 | Module functions | LOW |
| error_handling.py | ~200 | Complex decorator, hard to split | MEDIUM -- nested closure structure |

### Test Impact Assessment

| Module | Test File | Test Count | Mock Patterns | Risk |
|--------|-----------|------------|---------------|------|
| autorate_continuous | test_autorate_continuous.py | 29 | 91 mock/patch refs | LOW -- helpers stay in same module |
| wan_controller | test_wan_controller.py | 81 | 382 mock/patch refs | LOW -- private methods stay on class |
| health_check | test_health_check.py | 77 | 329 mock/patch refs | LOW -- response dict structure unchanged |
| steering/daemon | test_steering_daemon.py | 259 | 1238 mock/patch refs | LOW -- same module, same class |
| steering/health | test_steering_health.py | 57 | 133 mock/patch refs | LOW -- response dict structure unchanged |

[VERIFIED: AST test count + grep mock count from test files]

## Code Examples

### Example 1: Extracting main() Cleanup Block

The `finally` block in `autorate_continuous.py:main()` is ~150 lines (lines 942-1091) with 6 numbered cleanup stages. This is a textbook extraction candidate.

```python
# Source: src/wanctl/autorate_continuous.py lines 942-1091
# Before: 150 lines inline in finally block
# After:
def _cleanup_daemon(
    controller: ContinuousAutoRate,
    lock_files: list[Path],
    irtt_thread: IRTTThread | None,
    metrics_server: Any,
    health_server: Any,
) -> None:
    """Ordered daemon shutdown: state > threads > locks > connections > servers > metrics."""
    cleanup_start = time.monotonic()
    deadline = cleanup_start + SHUTDOWN_TIMEOUT_SECONDS
    _cleanup_log = logging.getLogger(__name__)
    _cleanup_log.info("Shutting down daemon...")

    _save_controller_state(controller, deadline, _cleanup_log)
    _stop_background_threads(controller, irtt_thread, deadline, _cleanup_log)
    _release_locks(controller, lock_files)
    _close_router_connections(controller, deadline, _cleanup_log)
    _stop_servers(controller, metrics_server, health_server, deadline, _cleanup_log)
    _close_metrics_writer(deadline, _cleanup_log)

    total = time.monotonic() - cleanup_start
    for wan_info in controller.wan_controllers:
        wan_info["logger"].info(f"Daemon shutdown complete ({total:.1f}s)")
```

### Example 2: Extracting WANController.__init__ by Concern

```python
# Source: src/wanctl/wan_controller.py lines 187-594
# The __init__ has clear section dividers (============= blocks)
# Each section becomes a private method:

def __init__(self, wan_name, config, router, rtt_measurement, logger):
    self.wan_name = wan_name
    self.config = config
    self.router = router
    self.rtt_measurement = rtt_measurement
    self.logger = logger
    self.router_connectivity = RouterConnectivityState(self.logger)
    self.pending_rates = PendingRateChange()

    self._init_baseline_and_thresholds(config)
    self._init_queue_controllers(config)
    self._init_flash_wear_protection()
    self._init_rate_limiter()
    self._init_state_persistence(config)
    self._init_metrics_storage(config)
    self._init_alerting(config)
    self._init_signal_processing(config)
    self._init_irtt_and_fusion(config)
    self._init_reflector_scoring(config)
    self._init_alert_timers(config)
    self._init_profiling(config)
    self._init_tuning(config)

    self.load_state()
    if self._tuning_enabled and self._metrics_writer is not None:
        self._restore_tuning_params()
```

### Example 3: Extracting Tuning Block from main() Loop

The adaptive tuning block in `main()` (lines 680-901) is ~220 lines. This is a standalone concern.

```python
# Source: src/wanctl/autorate_continuous.py lines 680-901
def _run_adaptive_tuning(controller: ContinuousAutoRate) -> None:
    """Execute one adaptive tuning pass across all WAN controllers."""
    # ... extracted tuning logic ...
```

### Example 4: C901 Reduction via Branch Extraction

```python
# Before: validate_cross_fields() complexity 17
def validate_cross_fields(data: dict) -> list[CheckResult]:
    results = []
    if condition_a:
        if sub_condition:
            results.append(...)
    if condition_b:
        ...
    # 15+ branches inline

# After: complexity reduced by extracting each validation group
def validate_cross_fields(data: dict) -> list[CheckResult]:
    results = []
    results.extend(_validate_floor_ordering(data))
    results.extend(_validate_threshold_consistency(data))
    results.extend(_validate_ceiling_constraints(data))
    return results
```

## Recommended Plan Breakdown

Based on the inventory, group by file to minimize context switching and test isolation:

| Plan | Files | Functions | Estimated Extractions |
|------|-------|-----------|----------------------|
| 01 | wan_controller.py | `__init__` (408), `run_cycle` (447), `_check_congestion_alerts` (102) | 15-20 helpers |
| 02 | autorate_continuous.py | `main` (612) | 8-10 helpers (some already exist) |
| 03 | steering/daemon.py | `run_cycle` (269), `main` (215), `__init__` (136), config loaders | 12-15 helpers |
| 04 | health_check.py + steering/health.py | `_get_health_status` (347 + 212) | 8-10 helpers |
| 05 | Remaining: autorate_config.py, check_cake.py, check_config_validators.py, queue_controller.py, others | 10 functions | 10-12 helpers |
| 06 | C901 cleanup: error_handling.py, router_connectivity.py, history.py, tuning/signal_processing.py, pyproject.toml threshold | 6 functions + config | 6-8 helpers + threshold update |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (project venv) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `.venv/bin/pytest tests/test_<module>.py -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CPLX-02 | No function >50 lines (excl docstrings) | smoke | AST-based line count script (see research) | No -- Wave 0 |
| CPLX-04 | C901 passes at threshold 15 | lint | `.venv/bin/ruff check src/wanctl/ --select C901 --config "lint.mccabe.max-complexity = 15"` | Built-in |
| CPLX-02/04 | No behavioral regression | unit | `.venv/bin/pytest tests/ -v` | 4,239 tests exist |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_<module>.py -v` + `ruff check` + `mypy` on modified files
- **Per wave merge:** `make ci` (full suite)
- **Phase gate:** Full suite green + function line audit + C901 at threshold 15

### Wave 0 Gaps
- [ ] AST-based function line count verification script (run post-extraction to verify <50 lines)
- No framework install needed -- all tools already present

## Security Domain

Not applicable. This phase is a pure internal refactoring with zero behavioral changes, no new inputs, no new outputs, no new network communication. Security posture is unchanged.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | C901 threshold target is 15 (from CPLX-04 + pyproject.toml comments referencing Phase 114) | C901 Violations | LOW -- can adjust threshold; current config is 20 with per-file ignores |
| A2 | Net LOC change per file is near-zero after extraction (inline code replaced by calls) | File LOC Impact | LOW -- if LOC grows, D-10 escape valve applies |

Note: D-03 states "C901 complexity is already clean -- no violations at any threshold." However, this is incorrect -- there are 10 C901 violations at threshold 15 and 5 additional files with per-file-ignores at threshold 20. The research inventory corrects this. [VERIFIED: ruff check output]

## Open Questions (RESOLVED)

1. **C901 Threshold Target**
   - What we know: Current `max-complexity = 20` with per-file-ignores. CPLX-04 says "high cyclomatic complexity functions are refactored." D-03 claims "C901 already clean."
   - What's unclear: Should the final threshold be 15 (success criteria says "15 or lower") or should we just remove per-file-ignores and keep 20?
   - Recommendation: Target 15 per success criteria. Method extraction naturally reduces complexity. Update pyproject.toml threshold from 20 to 15 and remove per-file-ignores as the final task.

2. **error_handling.py Nested Closures**
   - What we know: `handle_errors`/`decorator`/`wrapper` are three nested functions with combined complexity 51. The nesting is structural (decorator pattern).
   - What's unclear: Whether this can be meaningfully simplified without changing the API.
   - Recommendation: Extract specific error classification logic (the if/elif chain in wrapper) into a helper. Don't restructure the decorator pattern itself.

## Sources

### Primary (HIGH confidence)
- Source code analysis via AST-based function line counter [VERIFIED: direct code inspection]
- `pyproject.toml` ruff/mypy/pytest configuration [VERIFIED: file read]
- `ruff check --select C901` output at threshold 15 [VERIFIED: command execution]
- Phase 144 VERIFICATION.md for post-split LOC distribution [VERIFIED: file read]
- 145-CONTEXT.md for user decisions [VERIFIED: file read]

### Secondary (MEDIUM confidence)
- Test file mock pattern analysis via grep [VERIFIED: grep counts]

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries, existing tooling only
- Architecture: HIGH -- extraction patterns verified from existing codebase helpers
- Pitfalls: HIGH -- Phase 144 experience with same codebase, mock patterns verified
- Inventory: HIGH -- AST-based analysis, C901 checks run directly

**Research date:** 2026-04-06
**Valid until:** 2026-05-06 (stable -- internal refactoring, no external dependencies)
