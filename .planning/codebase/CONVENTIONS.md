# Coding Conventions

**Analysis Date:** 2026-06-19

## Naming Patterns

**Files:**
- `snake_case.py` for all source modules (e.g., `queue_controller.py`, `rtt_backend_factory.py`)
- Phase-scoped scripts use hyphens where required by plan: `phase214-extract.py` (suppressed via `N999` per-file lint override)
- Test files: `test_<module>.py` for unit tests, `test_phase<NNN>_<slug>.py` for phase-boundary and mutation-boundary tests

**Classes:**
- `PascalCase` throughout (e.g., `WANController`, `QueueController`, `CakeSignalProcessor`, `RTTSnapshot`)
- Protocol classes named by capability without `I` prefix: `HealthDataProvider`, `Reloadable`, `RttBackend`
- Private Protocol classes scoped inside modules use leading underscore: `_BackgroundRttDriver` (`src/wanctl/wan_controller.py`)
- `TypedDict` subclasses for structured config dicts: `FusionConfig`, `IRTTConfig`, `RetentionConfig`

**Functions and methods:**
- `snake_case` for all public functions and methods
- `_snake_case` prefix for private methods (e.g., `_init_baseline_and_thresholds`, `_apply_threshold_param`)
- Class-level `__init__` helpers grouped by concern with prefix `_init_<concern>()` pattern (see `WANController.__init__` in `src/wanctl/wan_controller.py`)
- Module-level helper functions begin with `_` when private: `_active_tin_indices`, `_discover_logger`

**Variables:**
- `snake_case` for all variables
- Rate and threshold vars use explicit units in name: `floor_green_bps`, `ceiling_bps`, `deadband_ms`, `step_up_bps`
- Math/network convention single-letters (`i`, `n`) allowed — `E741` suppressed

**Constants:**
- `UPPER_SNAKE_CASE` for module-level constants
- Units encoded in name: `CYCLE_INTERVAL_SECONDS`, `SLOW_ROUTER_APPLY_LOG_MS`, `DEFAULT_BASELINE_UPDATE_THRESHOLD_MS`, `MBPS_TO_BPS`
- Metric name constants prefixed `METRIC_`: `METRIC_RTT_BASELINE_MS`, `METRIC_RTT_DELTA_MS`

## Code Style

**Formatter:**
- `ruff format` (replaces Black)
- Line length: **100 characters** (`pyproject.toml` `[tool.ruff]`)
- Applied via `make format` or `.venv/bin/ruff format src/ tests/`

**Linter:**
- `ruff check` with broad rule selection: `E`, `W`, `F`, `I`, `B`, `UP`, `C90`, `N`, `SIM`, `PERF`, `RET`, `PT`, `TRY`, `ARG`, `ERA`
- McCabe complexity cap: **15** per function
- Function line cap enforced separately via `scripts/check_function_lines.py --threshold 50`
- Suppressed rules are documented inline with justification comments (see `[tool.ruff.lint.ignore]` in `pyproject.toml`)
- Tests get additional per-file suppressions: `N802`, `N803`, `N806`, `C901` (test helpers may be complex)

**Type checking:**
- MyPy with `disallow_untyped_defs = true`, `warn_return_any = true`, `no_implicit_optional = true`
- Target: `python_version = "3.11"`
- All functions and methods must have type annotations

## Import Organization

**Order (enforced by ruff isort):**
1. Standard library (`import json`, `from pathlib import Path`)
2. Third-party (`import icmplib`, `import paramiko`)
3. First-party wanctl (`from wanctl.cake_signal import ...`)

**Rules:**
- `known-first-party = ["wanctl"]` in `[tool.ruff.lint.isort]`
- Absolute imports only — no relative imports
- `TYPE_CHECKING` guard for imports that would cause circular dependencies at runtime:
  ```python
  from typing import TYPE_CHECKING
  if TYPE_CHECKING:
      from wanctl.cake_signal import CakeSignalSnapshot
  ```
- `from __future__ import annotations` used in modules with forward references or heavy `TYPE_CHECKING` blocks (e.g., `src/wanctl/cake_signal.py`, `src/wanctl/queue_controller.py`, `src/wanctl/interfaces.py`)

**Path aliases:** None. No `src/` alias or import shortcuts — always `from wanctl.<module> import ...`.

## Data Structures

**Frozen dataclasses for immutable value types:**
```python
@dataclasses.dataclass(frozen=True, slots=True)
class RTTSnapshot:
    rtt_ms: float
    per_host_results: dict[str, float | None]
    timestamp: float
    measurement_ms: float
    active_hosts: tuple[str, ...] = ()
    successful_hosts: tuple[str, ...] = ()
```
- Use `frozen=True, slots=True` for all hot-path value types that cross thread boundaries
- Examples: `RTTSnapshot`, `RTTCycleStatus`, `RttSample`, `CakeSignalSnapshot`, `TinSnapshot`, `SignalResult`, `FpingResult`, `IRTTResult`, `ReflectorStatus`
- Note: `CakeSignalSnapshot` in `src/wanctl/cake_signal.py` omits `slots=True` due to `field(default_factory=...)` usage

**Protocols for interface contracts (`src/wanctl/interfaces.py`):**
- All cross-module Protocol definitions live in `src/wanctl/interfaces.py` (D-02 constraint)
- Structural subtyping: implementations satisfy protocols without inheritance (D-01)
- `@runtime_checkable` on all Protocols defined in `interfaces.py`
- Module-private Protocols defined inline with `_` prefix: `_BackgroundRttDriver`, `_ScorerLike`
- `ABC` + `@abstractmethod` used only for the router backend hierarchy: `src/wanctl/backends/base.py`

**TypedDict for structured config dicts:**
```python
class FusionHealingConfig(TypedDict):
    suspend_threshold: float
    recover_threshold: float
    ...
```
Used in `src/wanctl/autorate_config.py` and `src/wanctl/config_base.py`.

## Section Separators

Large files use 79-character `=` comment banners to divide logical sections:
```python
# =============================================================================
# __init__ concern-grouped helpers (Phase 145-01)
# =============================================================================
```
Test files follow the same pattern between test class groups. Shorter inline sections use `# ---...---` banners.

## Phase and Requirement Annotations

Comments referencing the phase number that introduced a behavior are standard:
```python
# Phase 201 (DOCSIS-aware UL control mode) — keyword-only with safe defaults.
self.floor_soft_red_bps = floor_soft_red  # Phase 2A
# Phase 202: per-cause window + lifetime counters (METRIC-01, METRIC-02; Q1/Q2/Q3).
```
These are the audit trail for design decisions. Do not remove them.

SAFE-NN identifiers (`# SAFE-05`, `# SAFE-17`) in comments and docstrings refer to named invariant checkpoints from `.planning/` phase documentation.

## Error Handling

**Decorator pattern for method-level suppression** (`src/wanctl/error_handling.py`):
```python
@handle_errors(default_return=None, log_level=logging.WARNING)
def my_method(self):
    ...

@handle_errors(default_return=False, log_traceback=True, error_msg="Failed: {exception}")
def verify_state(self):
    ...
```

**Context manager for block-level suppression:**
```python
with safe_operation(logger, operation="database query", default=None):
    result = expensive_operation()
```

**Functional form:**
```python
result = safe_call(load_config, config_path, logger=self.logger, default={})
```

**Principles:**
- `TRY003`, `TRY300`, `TRY301`, `TRY400` are suppressed — descriptive error messages and no-traceback logging are intentional
- Exceptions in the 50ms hot path must be caught to avoid crashing the daemon; errors return safe defaults
- Never use bare `except:` — always `except Exception` or a narrower type tuple

## Logging

**Framework:** Standard library `logging` with custom `JSONFormatter` (`src/wanctl/logging_utils.py`)

**Logger instantiation patterns:**
- Module-level loggers: `logger = logging.getLogger(__name__)` (e.g., `src/wanctl/health_check.py`, `src/wanctl/history.py`)
- Class-level loggers: `_logger = logging.getLogger(__name__)` as class attribute (e.g., `QueueController`)
- Injected loggers: `self.logger = logger` via constructor (e.g., `WANController`, `RouterOSREST`)

**Structured logging:**
```python
logger.info("State change", extra={"state": "GREEN", "rtt_delta": 5.2, "wan_name": "spectrum"})
```
Common `extra` fields: `wan_name`, `state`, `rtt_delta`, `dl_rate`, `ul_rate`

**Format strings in log calls:** `%s` style (not f-strings) inside `logger.*()` calls:
```python
self._logger.info("[HYSTERESIS] %s dwell expired, GREEN->YELLOW confirmed", _dir)
```
F-strings are used in `handle_errors` message templates and exception strings only.

**Log levels:**
- `DEBUG`: per-cycle diagnostic values, hysteresis detail
- `INFO`: state transitions, rate adjustments, startup/shutdown events
- `WARNING`: recoverable errors, degraded operation, unknown config keys
- `ERROR`: unrecoverable errors requiring operator attention

## Comments

**When to comment:**
- All public functions require docstrings (MyPy `disallow_untyped_defs` enforces signatures; docstrings are convention)
- Private helper functions with non-obvious behavior get docstrings
- Inline `# Phase NNN` comments mark when behavior was introduced
- Algorithmic comments explain *why*, not *what*: `# Wrap-around: distance from previous to U32_MAX, plus current, plus 1`

**Docstring style:** Imperative first sentence, Args/Returns sections for non-trivial functions:
```python
def u32_delta(current: int, previous: int) -> int:
    """Compute delta between two u32 counters, handling wrap-around.

    Returns 0 if the computed delta exceeds SANITY_MAX_DELTA, treating
    it as a wrap artifact rather than a real drop spike.

    Args:
        current: Current counter value.
        previous: Previous counter value.

    Returns:
        Non-negative delta, or 0 if sanity guard triggers.
    """
```
Module docstrings describe signal flows, requirements codes (e.g., `Requirements: CAKE-01, CAKE-02`), and u32/counter behavior notes.

## Module Design

**Exports:** No `__all__` — exports are implicit. Private symbols use `_` prefix.

**Barrel files:** Not used. Import from the specific module directly.

**Dependency direction:**
- `src/wanctl/interfaces.py` has no intra-wanctl imports
- `src/wanctl/backends/base.py` is pure ABC with no controller imports
- `src/wanctl/wan_controller.py` is the integration point — imports from most other modules
- `TYPE_CHECKING` guards break import cycles at runtime without affecting behavior

## Dead Code Prevention

- `vulture` + `ruff F401` run as `make dead-code`
- `vulture_whitelist.py` explicitly lists known false-positives (Textual lifecycle methods, etc.)
- Unused imports and unused symbols must not accumulate

## Boundary Enforcement

- Cross-module private attribute access checked via `scripts/check_private_access.py` (`make check-boundaries`)
- Cross-module private mock patches checked via `scripts/check_test_brittleness.py` (`make check-brittleness`)
- Function line counts checked via `scripts/check_function_lines.py --threshold 50` (`make check-lines`)
- Unused pip dependencies checked via `make check-deps`

---

*Convention analysis: 2026-06-19*
