# Coding Conventions

**Analysis Date:** 2026-01-21

## Naming Patterns

**Files:**
- Snake case for all Python files: `rtt_measurement.py`, `autorate_continuous.py`, `state_manager.py`
- Hierarchical organization under `src/wanctl/` with subpackages for major features: `steering/`, `backends/`
- Test files mirror source structure with `tests/` prefix: `tests/test_rtt_measurement.py`, `tests/test_autorate_continuous.py`

**Functions:**
- Snake case for all functions: `parse_ping_output()`, `enforce_rate_bounds()`, `safe_json_load_file()`
- Prefix with verb for action functions: `handle_errors()`, `validate_field()`, `verify_connectivity_fallback()`
- Use `is_` or `has_` prefix for boolean-returning functions: `is_retryable_error()`, `is_shutdown_requested()`
- Private/internal functions prefixed with underscore: `_get_nested()`, `_type_name()`, `_compute_state_hash()`

**Variables:**
- Snake case for all variables and attributes: `baseline_rtt`, `download_floor_green`, `icmp_unavailable_cycles`
- Type annotations required for function parameters and returns (Python 3.11+ style): `list[float]`, `dict[str, Any]`, `float | None`
- Constants in UPPER_SNAKE_CASE: `CYCLE_INTERVAL_SECONDS`, `DEFAULT_BASELINE_UPDATE_THRESHOLD_MS`, `MBPS_TO_BPS`

**Classes:**
- PascalCase for all classes: `WANController`, `StateManager`, `RouterOSBackend`, `RateLimiter`
- Base classes follow `Base` prefix: `BaseConfig`, `RouterBackend` (abstract base)

**Types:**
- Type hints universally applied: All public functions fully typed
- Modern union syntax preferred: `float | None` instead of `Optional[float]`
- Generic types use bracket syntax: `list[dict[str, Any]]`, `Callable[[int], str]`
- Custom exception classes inherit from standard base: `class ConfigValidationError(ValueError):`

## Code Style

**Formatting:**
- Line length: 100 characters (configured in `pyproject.toml` under `[tool.ruff]`)
- Indentation: 4 spaces (Python standard)
- Tool: Ruff (formatter applied via `ruff format src/ tests/`)
- Double quotes for strings

**Linting:**
- Tool: Ruff (linter configured in `pyproject.toml` under `[tool.ruff.lint]`)
- Rules enforced:
  - E/W: pycodestyle errors and warnings
  - F: pyflakes (undefined variables, unused imports)
  - I: isort (import sorting)
  - B: flake8-bugbear (common bugs)
  - UP: pyupgrade (modern Python syntax)
- Line length exceptions (E501) ignored - handled by formatter
- B008 ignored: function call in default argument (by design)

**Type Checking:**
- Tool: MyPy (configured in `pyproject.toml` under `[tool.mypy]`)
- Settings:
  - `python_version = "3.12"`
  - `disallow_untyped_defs = false` (but `check_untyped_defs = true`)
  - `warn_return_any = false`
  - `ignore_missing_imports = true` (external packages)
  - `disable_error_code = ["import-untyped"]`

## Import Organization

**Order:**
1. Standard library imports (e.g., `import logging`, `from pathlib import Path`)
2. Third-party imports (e.g., `import yaml`, `import requests`, `import paramiko`)
3. Local wanctl imports (e.g., `from wanctl.config_base import BaseConfig`)

**Path Aliases:**
- All imports use absolute paths: `from wanctl.state_manager import StateManager`
- Never use relative imports: `from .state_manager import StateManager` (not used)
- Known first-party package configured: `known-first-party = ["wanctl"]` in `pyproject.toml`

**Module Organization:**
- Barrel imports used for subpackages: `from wanctl.backends import RouterBackend`
- `__init__.py` files explicitly control public API
- Heavy import logic avoided - pure function exports preferred

## Error Handling

**Patterns:**

1. **Custom Exceptions for Domain Errors:**
   - `ConfigValidationError(ValueError)`: Configuration validation failures in `config_base.py`
   - `LockAcquisitionError(Exception)`: Lock file acquisition failures in `lock_utils.py`
   - Domain-specific exceptions, not generic

2. **Decorator-Based Error Handling:**
   - `@handle_errors()` decorator centralizes repetitive try/except patterns
   - Location: `src/wanctl/error_handling.py`
   - Usage: `@handle_errors(default_return=None, log_level='warning', log_traceback=True)`
   - Replaces 70+ scattered error handling instances across codebase
   - Parameters: `default_return`, `log_level`, `log_traceback`, `error_msg`, `exception_types`, `reraise`, `on_error`

3. **Retryable vs Non-Retryable Distinction:**
   - `is_retryable_error()` in `retry_utils.py` determines retry eligibility
   - Transient errors: `subprocess.TimeoutExpired`, `ConnectionError`, connection-related `OSError`, requests timeouts
   - Non-transient: authentication failures, syntax errors, logic errors, 4xx HTTP status
   - Used by `@retry_with_backoff()` decorator for exponential backoff with jitter

4. **Fallback Mode Handling (ICMP Blackout):**
   - ICMP blackout handling with three modes: `graceful_degradation`, `freeze`, `use_last_rtt`
   - Implemented in `WANController.handle_icmp_failure()` in `autorate_continuous.py`
   - Returns tuple: `(should_continue: bool, measured_rtt: float | None)`
   - Graceful degradation: cycle 1 uses last RTT, cycles 2-3 freeze rates, cycle 4+ fails/restarts

5. **Validation Error Pattern:**
   - Config validation uses `raise ConfigValidationError(f"message")` for failures
   - Path-based error messages include full dotted path: `f"Invalid type for {path}: expected X, got Y"`
   - Validation centralized in functions: `validate_field()` in `config_base.py`

## Logging

**Framework:** Python standard `logging` module

**Patterns:**

1. **Initialization:**
   - Loggers created per module: `logger = logging.getLogger(__name__)`
   - Setup via `setup_logging()` in `logging_utils.py`
   - Produces both structured JSON logs and human-readable formats
   - Configuration via YAML in `/etc/wanctl/` for production

2. **JSON Structured Logging:**
   - Formatter: `JSONFormatter` class in `logging_utils.py`
   - Fields: `timestamp` (ISO 8601 with timezone), `level`, `logger`, `message`, plus custom extras
   - Extra fields passed via `extra` dict: `logger.info("msg", extra={"wan_name": "spectrum", "state": "GREEN"})`
   - Compatible with log aggregators: Loki, ELK, Splunk, CloudWatch

3. **Log Levels by Context:**
   - DEBUG: Low-level state changes, parse details, per-cycle events
   - INFO: Cycle summaries, rate changes, major state transitions
   - WARNING: Transient failures, ICMP blackouts, retries, degraded operation
   - ERROR: Persistent failures, config errors, router connectivity loss
   - CRITICAL: Unrecoverable system failures

4. **Common Log Extras:**
   - `wan_name`: WAN identifier ("spectrum", "att")
   - `state`: Current congestion state ("GREEN", "YELLOW", "SOFT_RED", "RED")
   - `rtt_delta`: RTT delta in milliseconds
   - `dl_rate`, `ul_rate`: Bandwidth rates in bps
   - `bloat_ms`: Current queue bloat measurement in milliseconds

5. **Rate Limiting:**
   - Repeated warnings deduplicated with DEBUG-level prefixes to reduce noise
   - See `autorate_continuous.py` for rate limit event logging: `record_rate_limit_event()`

## Comments

**When to Comment:**
- Architecture decisions that override obvious approaches
- Non-obvious algorithm logic (e.g., EWMA smoothing rationale, hysteresis thresholds)
- Configuration tuning rationale (e.g., `DEFAULT_HARD_RED_BLOAT_MS = 80`)
- Performance implications (e.g., regex pre-compilation for hot paths: `_RTT_PATTERN = re.compile(...)`)
- References to external documentation or design principles
- Invariant conditions that must be maintained (see CLAUDE.md for examples)

**When NOT to Comment:**
- Self-explanatory code: good variable names preferred
- Temporary debugging: use logging instead
- Repeating function docstring: already documented

**JSDoc/TSDoc:**
- Docstrings for all public classes and functions (100% coverage)
- Format: Triple-quoted strings immediately after `def` or `class` line
- Structure:
  ```python
  def enforce_rate_bounds(rate: float, floor: float | None = None) -> int:
      """Enforce floor and ceiling constraints on bandwidth rate.

      Args:
          rate: Current rate to constrain (in bps)
          floor: Minimum allowed rate or None

      Returns:
          Bounded rate as integer (in bps)

      Raises:
          ValueError: If floor > ceiling

      Examples:
          >>> enforce_rate_bounds(50_000_000, floor=20_000_000)
          50000000
      """
  ```
- Include Args, Returns, Raises, Examples sections
- Inline docstring examples should be executable via doctest

## Function Design

**Size:**
- Typical range: 10-50 lines
- Utility functions often 5-20 lines
- Complex logic broken into multiple functions with clear responsibilities
- No arbitrary size limit, but consider readability and testability

**Parameters:**
- Maximum 6-8 positional parameters; excess bundled into config objects
- Type annotations required for all parameters
- Default values used for optional parameters
- Optional parameters typically placed at end
- Consider validator functions for complex initialization

**Return Values:**
- Explicit return types required via annotation
- Tuple returns used for compound results: `(bool, dict)`, `(float | None, str)`
- None returns permitted for optional results (use `T | None` annotation)
- Generators prefer `yield` over building lists (for streaming data)

## Module Design

**Exports:**
- All public API functions/classes explicitly exported
- Private functions prefixed with underscore
- Constants grouped at module top after imports
- `__all__` not used; rely on naming convention

**Barrel Files:**
- Subpackage `__init__.py` files import and re-export key classes
- Example: `src/wanctl/backends/__init__.py` exports `RouterBackend`
- Enables: `from wanctl.backends import RouterBackend` instead of full path

**Separation of Concerns:**
- State management isolated: `state_manager.py`, `wan_controller_state.py`
- Router communication abstracted: `backends/` package with abstract base interface
- Configuration validation centralized: `config_base.py`, `config_validation_utils.py`
- Utilities grouped by domain: `rate_utils.py`, `retry_utils.py`, `lock_utils.py`, `logging_utils.py`
- Steering logic: `steering/` subpackage with independent daemon

## Production Standards

**Atomic Operations:**
- State writes use `atomic_write_json()` from `state_utils.py` (write-to-temp-then-rename)
- Prevents corruption from interrupted writes
- Used by: `WANControllerState.save()`, `StateManager.save()`

**Dirty Tracking:**
- State dirty-tracking via hash comparison (excludes timestamp)
- Prevents unnecessary disk writes in high-frequency loops (50ms cycles)
- Implementation: `WANControllerState._compute_state_hash()`, `_last_saved_hash` tracking
- Hash excludes timestamp to avoid redundant writes

**Rate Bounding:**
- All bandwidth rates validated against floor/ceiling constraints
- Function: `enforce_rate_bounds()` in `rate_utils.py`
- Floor enforced first, then ceiling (order matters for consistency)
- All rates in bps (bits per second), never mixed units

**Configuration Externalization:**
- All tuning parameters in YAML files, never hardcoded
- Environment variable substitution: `"${ROUTER_PASSWORD}"` in YAML files
- Schema validation enforces: type checks, numeric ranges, required fields
- See `Config.SCHEMA` pattern in `autorate_continuous.py` and `steering/daemon.py`

---

*Convention analysis: 2026-01-21*
