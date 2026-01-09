# Coding Conventions

**Analysis Date:** 2026-01-09

## Naming Patterns

**Files:**
- snake_case for all Python modules (autorate_continuous.py, config_base.py)
- Utility files: _utils.py suffix (config_validation_utils.py, lock_utils.py, rate_utils.py)
- Test files: test_*.py alongside source (tests/test_baseline_rtt_manager.py)
- Scripts: lowercase with hyphens (deploy.sh, install.sh)

**Functions:**
- snake_case for all functions (update_state_machine, read_stats)
- Private functions: _leading_underscore for module-internal (not enforced by convention)
- Async functions: async def function_name()
- Handlers/callbacks: on_<event> or <verb>_<noun> (e.g., handle_timeout)

**Variables:**
- snake_case for variables and parameters
- UPPER_SNAKE_CASE for constants (DEFAULT_BAD_THRESHOLD_MS, MAX_SANE_BASELINE_RTT)
- Private members: _leading_underscore for attributes (Python convention)
- Loop variables: Standard (i, j for loops, or descriptive names)

**Classes:**
- PascalCase for all classes (WANController, StateManager, RouterOS)
- Base classes: BaseClassName pattern (BaseConfig, BaselineRTTManager)
- No I prefix for interfaces (Python uses duck typing)

**Types:**
- PascalCase for type aliases (ConfidenceSignals, CakeStats)
- Generic types: Standard Python typing (List[str], Optional[Dict[str, Any]])

## Code Style

**Formatting:**
- Ruff with black-compatible settings
- Line length: 100 characters (from `pyproject.toml`)
- Quotes: Double quotes for strings
- Semicolons: Not used in Python (no configuration needed)
- Indentation: 4 spaces (Python standard)

**Linting:**
- Ruff (`pyproject.toml` line 35) for linting and sorting
- pyflakes for static analysis
- No explicit ESLint/Prettier (Python only)

**Run Commands:**
```bash
# Format (Ruff in write mode)
uv run ruff format src/ tests/

# Lint
uv run ruff check src/ tests/

# Check both
uv run ruff check --fix src/
```

## Import Organization

**Order:**
1. Standard library (sys, pathlib, logging, etc.)
2. Third-party packages (requests, paramiko, pyyaml)
3. Local modules (from wanctl.config_base import, from . import)
4. Type imports (from typing import, from types import)

**Grouping:**
- Blank line between groups
- Alphabetical within each group
- Type imports: `from typing import` for runtime, `TYPE_CHECKING` for annotations

**Path Aliases:**
- Absolute imports preferred: `from wanctl.config_base import BaseConfig`
- Relative imports in packages: `from . import config_base` or `from .config_base import Config`
- No @/ aliases or custom path manipulation

## Error Handling

**Patterns:**
- Throw exceptions for invalid config, unexpected state
- Catch at boundaries (daemon main(), daemon cycles)
- Custom exceptions: ConfigValidationError, LockAcquisitionError
- Async: try/await, no callback chains

**Error Types:**
- Raise ConfigValidationError for validation failures (config_validation_utils.py)
- Raise LockAcquisitionError for lock failures (lockfile.py)
- Raise ValueError for invalid arguments
- Raise FileNotFoundError for missing files
- Log full exception with traceback in error handler

**Logging:**
- Log with exception context: `logger.error("msg", exc_info=True)` or use traceback module
- Include user-facing context (WAN name, cycle number)
- Debug logs for detailed diagnostics

## Logging

**Framework:**
- Python `logging` module (built-in)
- Custom setup in `logging_utils.py`
- Levels: DEBUG, INFO, WARNING, ERROR

**Patterns:**
- Initialize logger per-module: `logger = logging.getLogger(__name__)`
- Inject logger via dependency: Pass as parameter to classes
- Structured context: Include relevant identifiers in log messages
- Examples: `logger.info(f"[{wan_name}] RTT={rtt:.1f}ms")`

## Comments

**When to Comment:**
- Explain why, not what (code should be self-documenting)
- Document complex algorithms or non-obvious decisions
- Explain workarounds and constraints
- Avoid obvious comments: `# increment counter`

**JSDoc/Docstrings:**
- Required for all public functions and classes
- Format: Google-style docstrings (preferred) or standard Python docstrings
- Include: brief, args, returns, raises
- Example:
  ```python
  def read_stats(self, queue_name: str) -> Optional[CakeStats]:
      """Read CAKE statistics for a specific queue.

      Returns delta stats since last read (best practice - no counter resets).

      Args:
          queue_name: Name of CAKE queue to read

      Returns:
          CakeStats with delta counters and instantaneous values, or None on error
      """
  ```

**TODO Comments:**
- Format: `# TODO: description` (no username, use git blame)
- Link to issue: `# TODO: Fix race condition (issue #123)`
- Frequency: Discouraged, prefer GitHub issues

## Function Design

**Size:**
- Keep under 50 lines
- Extract helpers for complex logic
- One level of abstraction per function

**Parameters:**
- Max 3 parameters (use dataclass if more needed)
- Destructure objects: `def process(config: Config, logger: Logger):`
- Avoid mutable defaults: Use None and assign in function

**Return Values:**
- Explicit returns (no implicit None)
- Return early for guard clauses
- Use Optional[T] for nullable returns
- Use Tuple or dataclass for multiple returns

## Module Design

**Exports:**
- Named exports preferred (avoid star imports)
- Public API documented in module docstring
- Private functions: Start with underscore (convention)

**Barrel Files:**
- Use `__init__.py` for package organization
- Re-export public API from package
- Avoid circular imports (use TYPE_CHECKING)

**Organization:**
- Related functions grouped in classes (StateManager, RouterOS)
- Utility functions in dedicated modules (config_validation_utils.py)
- One main class per file (except tests)

## Testing Conventions

- Use pytest (parametrized tests, fixtures)
- Fixture setup: `@pytest.fixture def logger():`
- Test class organization: `class TestFeatureName:`
- Test methods: `def test_specific_case(self):`
- Mocking: pytest-mock or unittest.mock

---

*Convention analysis: 2026-01-09*
*Update when patterns change*
