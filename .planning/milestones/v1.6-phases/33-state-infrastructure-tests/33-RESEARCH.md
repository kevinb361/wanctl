# Phase 33: State & Infrastructure Tests - Research

**Researched:** 2026-01-25
**Domain:** Python test coverage, file I/O testing, signal/systemd mocking
**Confidence:** HIGH

## Summary

Phase 33 covers test coverage for state management (`state_manager.py` 39% -> 90%) and infrastructure utilities (`error_handling.py` 21% -> 90%, `signal_utils.py` 50% -> 90%, `systemd_utils.py` 33% -> 90%, `path_utils.py` 71% -> 90%).

The standard approach uses pytest's `tmp_path` fixture for real file I/O in isolated temp directories. Real file operations preferred over mocking for state_manager (tests actual atomic writes, locking behavior). Mock-based approach required for systemd/signal modules (no systemd in test environment).

**Primary recommendation:** Use real file I/O with `tmp_path` for state tests; mock `fcntl.flock` for lock contention; mock systemd.daemon.notify for systemd tests; use threading.Event directly for signal tests.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 9.0.2 | Test framework | Already configured in pyproject.toml |
| pytest-cov | 7.0.0 | Coverage measurement | Already configured |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| unittest.mock | stdlib | Mocking systemd, fcntl | External dependencies |
| caplog | pytest fixture | Log capture | Verify error messages logged |
| tmp_path | pytest fixture | Temp directories | All file I/O tests |
| monkeypatch | pytest fixture | Module-level patching | signal/systemd globals |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| tmp_path | tempfile.TemporaryDirectory | tmp_path cleaner, auto-cleanup |
| mock fcntl | multiprocessing for real locks | Real locks brittle in CI |

**Installation:** No additional packages needed.

## Architecture Patterns

### Recommended Test File Structure
```
tests/
├── test_state_manager.py      # Exists, expand coverage
├── test_error_handling.py     # NEW - error_handling.py tests
├── test_signal_utils.py       # NEW - signal_utils.py tests
├── test_systemd_utils.py      # NEW - systemd_utils.py tests
└── test_path_utils.py         # Exists, expand coverage
```

### Pattern 1: Real File I/O with tmp_path
**What:** Use pytest's tmp_path fixture for actual file operations
**When to use:** All state_manager tests, path_utils tests
**Example:**
```python
def test_save_creates_file(self, tmp_path, logger):
    """Test that save creates the state file."""
    state_file = tmp_path / "state.json"
    schema = StateSchema({"count": 0})
    manager = StateManager(state_file, schema, logger)
    manager.state = {"count": 42}

    result = manager.save()

    assert result is True
    assert state_file.exists()
    # Verify JSON content
    with open(state_file) as f:
        data = json.load(f)
    assert data["count"] == 42
```

### Pattern 2: Validator Function Testing
**What:** Test validator factory functions with boundary values
**When to use:** bounded_float, string_enum, optional_positive_float
**Example:**
```python
def test_bounded_float_clamps_high(self):
    """Test bounded_float clamps values above max."""
    validator = bounded_float(0.0, 1.0, clamp=True)
    assert validator(1.5) == 1.0

def test_bounded_float_raises_when_no_clamp(self):
    """Test bounded_float raises ValueError when clamp=False."""
    validator = bounded_float(0.0, 1.0, clamp=False)
    with pytest.raises(ValueError, match="not in range"):
        validator(1.5)
```

### Pattern 3: Mocking fcntl for Lock Testing
**What:** Mock fcntl.flock to simulate lock contention
**When to use:** SteeringStateManager.save() lock tests
**Example:**
```python
def test_save_skips_when_locked_by_another_process(self, tmp_path, logger):
    """Test that save returns False when lock held by another."""
    state_file = tmp_path / "state.json"
    manager = SteeringStateManager(state_file, schema, logger)

    with patch("wanctl.state_manager.fcntl.flock") as mock_flock:
        mock_flock.side_effect = BlockingIOError("Lock held")
        result = manager.save(use_lock=True)

    assert result is False
```

### Pattern 4: Signal Testing with Direct Event Manipulation
**What:** Test signal utilities by manipulating the module-level Event
**When to use:** signal_utils.py tests
**Example:**
```python
from wanctl.signal_utils import (
    is_shutdown_requested,
    reset_shutdown_state,
    _shutdown_event,
)

def test_shutdown_event_cleared_initially(self):
    """Test shutdown event starts cleared."""
    reset_shutdown_state()
    assert is_shutdown_requested() is False

def test_signal_handler_sets_event(self):
    """Test _signal_handler sets the shutdown event."""
    reset_shutdown_state()
    _signal_handler(signal.SIGTERM, None)
    assert is_shutdown_requested() is True
```

### Pattern 5: Systemd Mock Pattern
**What:** Patch systemd.daemon.notify at module level
**When to use:** systemd_utils.py tests
**Example:**
```python
def test_notify_watchdog_calls_sd_notify(self):
    """Test notify_watchdog sends WATCHDOG=1."""
    with patch("wanctl.systemd_utils._sd_notify") as mock_notify:
        with patch("wanctl.systemd_utils._HAVE_SYSTEMD", True):
            notify_watchdog()
    mock_notify.assert_called_once_with("WATCHDOG=1")

def test_notify_watchdog_noop_when_unavailable(self):
    """Test notify_watchdog is no-op without systemd."""
    with patch("wanctl.systemd_utils._sd_notify", None):
        notify_watchdog()  # Should not raise
```

### Pattern 6: Error Handling Decorator Testing
**What:** Test @handle_errors decorator with mock objects
**When to use:** error_handling.py tests
**Example:**
```python
class MockObject:
    def __init__(self, logger):
        self.logger = logger

    @handle_errors(default_return=None, log_level=logging.WARNING)
    def method_that_fails(self):
        raise ValueError("test error")

def test_handle_errors_returns_default_on_exception(self, caplog):
    """Test decorator returns default when exception occurs."""
    logger = logging.getLogger("test")
    obj = MockObject(logger)

    with caplog.at_level(logging.WARNING):
        result = obj.method_that_fails()

    assert result is None
    assert "method_that_fails failed" in caplog.text
```

### Anti-Patterns to Avoid
- **Mocking file I/O when real I/O works:** tmp_path provides isolation; use real writes
- **Testing signal handlers with os.kill():** Race conditions; manipulate Event directly
- **Testing locks with multiprocessing:** Brittle; mock fcntl instead
- **Ignoring deque serialization:** SteeringStateManager converts deques to lists; verify

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Temp file cleanup | Manual cleanup in teardown | pytest tmp_path | Auto-cleanup, isolation |
| Log capture | Custom handler | pytest caplog | Standard, maintained |
| Module patching | Manual save/restore | monkeypatch | Automatic restore |
| Lock file creation | Manual file ops | StateManager methods | Tests actual code paths |

**Key insight:** The existing code already has reset_shutdown_state() for test isolation - use it.

## Common Pitfalls

### Pitfall 1: State Manager Backup/Corrupt Path Complexity
**What goes wrong:** StateManager.load() has complex backup recovery logic (try primary, try backup, handle corrupt)
**Why it happens:** Multiple code paths for corruption recovery
**How to avoid:** Create explicit test fixtures for each scenario:
  - Valid primary file
  - Corrupt primary, valid backup
  - Both corrupt
  - Only backup exists
**Warning signs:** Tests only exercise happy path

### Pitfall 2: Deque Serialization in SteeringStateManager
**What goes wrong:** Deques don't JSON-serialize; SteeringStateManager converts to lists
**Why it happens:** JSON doesn't support deque type
**How to avoid:** Test roundtrip: save with deques, load, verify deques restored
**Warning signs:** Tests only check list data, not deque behavior

### Pitfall 3: Lock File Race Conditions
**What goes wrong:** Real lock tests flaky in CI
**Why it happens:** Timing-dependent, parallel test execution
**How to avoid:** Mock fcntl.flock, test lock path logic rather than actual locking
**Warning signs:** Tests pass locally, fail in CI

### Pitfall 4: Signal Handler Module State
**What goes wrong:** Tests pollute each other via shared _shutdown_event
**Why it happens:** Module-level threading.Event persists across tests
**How to avoid:** Call reset_shutdown_state() in setup/teardown
**Warning signs:** Tests pass alone, fail when run together

### Pitfall 5: Systemd Import Conditional
**What goes wrong:** systemd_utils has try/except ImportError at module level
**Why it happens:** systemd.daemon optional dependency
**How to avoid:** Patch both _HAVE_SYSTEMD and _sd_notify together
**Warning signs:** Tests pass when systemd installed, fail otherwise

### Pitfall 6: Error Handling Logger Discovery
**What goes wrong:** @handle_errors tries to find logger from self
**Why it happens:** Decorator inspects args[0] for logger attribute
**How to avoid:** Test objects must have `.logger` attribute, or test fallback to module logger
**Warning signs:** Tests miss logger fallback path

## Code Examples

Verified patterns from existing codebase tests:

### State File Roundtrip Test
```python
# Source: tests/test_state_manager.py (existing pattern)
def test_load_and_save_roundtrip(self, temp_state_file, logger):
    """Test saving and loading state roundtrip."""
    schema = StateSchema({"count": 0, "name": "test"})

    # Save state
    manager1 = StateManager(temp_state_file, schema, logger)
    manager1.state = {"count": 42, "name": "custom"}
    assert manager1.save() is True

    # Load state
    manager2 = StateManager(temp_state_file, schema, logger)
    assert manager2.load() is True
    assert manager2.state["count"] == 42
    assert manager2.state["name"] == "custom"
```

### Corruption Recovery Test
```python
# Source: tests/test_state_utils.py (existing pattern)
def test_truncated_json_returns_default(self, temp_dir):
    """Truncated JSON returns default, not crash."""
    file_path = temp_dir / "state.json"
    with open(file_path, "w") as f:
        f.write('{"ewma": {"baseline_rtt": 30.0')  # Truncated

    result = safe_json_load_file(file_path, default={"initialized": True})
    assert result == {"initialized": True}
```

### Validator Test Pattern
```python
# Source: needs to be added
def test_string_enum_validates_allowed_values(self):
    """Test string_enum accepts only allowed values."""
    validator = string_enum("GREEN", "YELLOW", "RED")

    assert validator("GREEN") == "GREEN"
    assert validator("YELLOW") == "YELLOW"

    with pytest.raises(ValueError, match="not in allowed set"):
        validator("INVALID")
```

### Systemd Conditional Test Pattern
```python
# Source: needs to be added
def test_is_systemd_available_returns_module_state(self):
    """Test is_systemd_available reflects _HAVE_SYSTEMD."""
    from wanctl.systemd_utils import is_systemd_available

    with patch("wanctl.systemd_utils._HAVE_SYSTEMD", True):
        assert is_systemd_available() is True

    with patch("wanctl.systemd_utils._HAVE_SYSTEMD", False):
        assert is_systemd_available() is False
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| tempfile.NamedTemporaryFile | pytest tmp_path fixture | pytest 3.9+ | Cleaner, auto-cleanup |
| Manual mock setup/teardown | context managers (with patch) | Python 3.x | Less boilerplate |

**Deprecated/outdated:**
- Mock's `patch.object` for module globals - use `patch("module.name")` instead

## Open Questions

Things that couldn't be fully resolved:

1. **SteeringStateManager.history_maxlen behavior**
   - What we know: Deques use maxlen for bounded history
   - What's unclear: Should tests verify maxlen enforcement?
   - Recommendation: Add test that appends beyond maxlen, verify oldest evicted

2. **Error handling on_error callback coverage**
   - What we know: handle_errors has on_error callback parameter
   - What's unclear: Current coverage of callback error path
   - Recommendation: Add test for on_error callback invocation and callback failure

## Coverage Gap Analysis

### state_manager.py (39% -> 90%)

**Uncovered Functions:**
- `non_negative_int` (line 48): Tested indirectly, add explicit tests
- `optional_positive_float` (lines 85-95): Bounds validation paths
- `bounded_float` (lines 117-136): clamp=False path, ValueError path
- `string_enum` (lines 156-175): Error path for invalid values
- `StateSchema.validate_field` edge cases (lines 226-234): Type coercion failures
- `StateManager._backup_state_file` (lines 325-333): Backup creation, failure handling
- `SteeringStateManager.load` (lines 504-556): Backup recovery, deque conversion
- `SteeringStateManager.save` (lines 585-634): Locking paths, BlockingIOError
- `SteeringStateManager.add_measurement` (lines 646-649): Deque append
- `SteeringStateManager.log_transition` (lines 658-672): Transition logging

**Test Categories Needed:**
1. Validator functions: All edge cases, error paths
2. Schema validation: Type coercion, unknown fields
3. StateManager: Backup recovery, corrupt file handling
4. SteeringStateManager: Lock contention, deque serialization
5. State transitions: log_transition, add_measurement

### error_handling.py (21% -> 90%)

**Uncovered Paths:**
- `handle_errors` decorator: Logger discovery from self, format placeholders, callable default, on_error callback
- `safe_operation` context manager: Exception handling, traceback logging
- `safe_call` function: All paths untested

**Test Categories Needed:**
1. Decorator with various parameter combinations
2. Logger discovery (self.logger, fallback to module)
3. Error message formatting with placeholders
4. Callable default_return
5. on_error callback invocation
6. Context manager exception handling
7. safe_call function coverage

### signal_utils.py (50% -> 90%)

**Uncovered Paths:**
- `wait_for_shutdown` (lines 103-114): Timeout behavior
- `get_shutdown_event` direct usage

**Test Categories Needed:**
1. Signal handler behavior
2. wait_for_shutdown with timeout
3. Event state manipulation

### systemd_utils.py (33% -> 90%)

**Uncovered Paths:**
- `notify_ready`, `notify_status`, `notify_stopping`, `notify_degraded`: All notify functions
- Conditional paths when systemd unavailable

**Test Categories Needed:**
1. Each notify function with systemd available
2. Each notify function when systemd unavailable (no-op)
3. is_systemd_available reflection of module state

### path_utils.py (71% -> 90%)

**Uncovered Paths:**
- `get_cake_root` (lines 24-26): CAKE_ROOT env var path
- `ensure_directory_exists` OSError handling (lines 60-62)
- `ensure_file_directory` resolve=True path (line 95)
- `safe_file_path` without logger (line 116)

**Test Categories Needed:**
1. CAKE_ROOT environment variable
2. Directory creation error handling
3. Symlink resolution with resolve=True
4. Logger fallback behavior

## Sources

### Primary (HIGH confidence)
- `/home/kevin/projects/wanctl/src/wanctl/state_manager.py` - Source analysis
- `/home/kevin/projects/wanctl/src/wanctl/error_handling.py` - Source analysis
- `/home/kevin/projects/wanctl/src/wanctl/signal_utils.py` - Source analysis
- `/home/kevin/projects/wanctl/src/wanctl/systemd_utils.py` - Source analysis
- `/home/kevin/projects/wanctl/src/wanctl/path_utils.py` - Source analysis
- `/home/kevin/projects/wanctl/tests/test_state_manager.py` - Existing test patterns
- `/home/kevin/projects/wanctl/tests/test_state_utils.py` - Existing test patterns
- `/home/kevin/projects/wanctl/tests/test_path_utils.py` - Existing test patterns

### Secondary (MEDIUM confidence)
- pytest documentation - tmp_path fixture behavior

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Using existing pytest stack
- Architecture: HIGH - Following existing test patterns
- Pitfalls: HIGH - Derived from code analysis
- Coverage gaps: HIGH - From pytest --cov output

**Research date:** 2026-01-25
**Valid until:** 2026-02-25 (stable domain, internal code)
