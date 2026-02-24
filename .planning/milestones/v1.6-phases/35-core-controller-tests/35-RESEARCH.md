# Phase 35: Core Controller Tests - Research

**Researched:** 2026-01-25
**Domain:** Python unit testing, control loop verification, signal handling
**Confidence:** HIGH

## Summary

This phase increases test coverage for `autorate_continuous.py` from 33% to 90%+. The module is 680 statements with 440 currently uncovered. The existing test patterns in `test_wan_controller.py` and `test_signal_utils.py` provide proven mocking strategies that can be directly extended.

Key coverage gaps by area:
- **Entry points (main(), ContinuousAutoRate)**: Lines 1399-1808 (daemon loop, validation mode, oneshot mode)
- **QueueController state transitions**: Lines 611-760 (adjust(), adjust_4state() methods untested)
- **Config loading**: Lines 267-518 (Config class methods, threshold/floor validation)
- **Error recovery paths**: ICMP blackout handling, router failure cascades

**Primary recommendation:** Mock at router client and RTT measurement boundaries, use pytest fixtures extensively, test state machines with explicit transition sequences.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 9.0.2 | Test framework | Already in project, de facto Python standard |
| unittest.mock | stdlib | Mocking | No external deps, project already uses it |
| pytest-cov | 7.0.0 | Coverage reporting | Already configured in pyproject.toml |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest fixtures | builtin | Test setup/teardown | All tests, shared mock configs |
| parametrize | builtin | Test data variations | State transition matrix tests |
| caplog | builtin | Log capture | Verifying error/warning messages |
| tmp_path | builtin | Temp directories | Config file tests, state file tests |

### Not Needed
| Instead of | Don't Use | Reason |
|------------|-----------|--------|
| freezegun | freezegun | 50ms cycles are fast enough to test with real time |
| responses | responses | Router client already provides mock boundaries |
| pytest-asyncio | pytest-asyncio | No async code in autorate_continuous.py |

## Architecture Patterns

### Recommended Test Structure
```
tests/
├── test_autorate_continuous.py     # NEW: main() entry points
├── test_queue_controller.py        # NEW: QueueController state machines
├── test_continuous_autorate.py     # NEW: ContinuousAutoRate class
├── test_wan_controller.py          # EXISTING: extend with run_cycle coverage
└── test_autorate_baseline_bounds.py # EXISTING: baseline validation
```

### Pattern 1: Mock Config Fixture (Proven Pattern)
**What:** Create comprehensive mock config objects that satisfy all Config class fields
**When to use:** Every test that instantiates WANController or ContinuousAutoRate
**Example:**
```python
# Source: tests/test_wan_controller.py
@pytest.fixture
def mock_config():
    config = MagicMock()
    config.wan_name = "TestWAN"
    config.baseline_rtt_initial = 25.0
    config.download_floor_green = 800_000_000
    config.download_floor_yellow = 600_000_000
    config.download_floor_soft_red = 500_000_000
    config.download_floor_red = 400_000_000
    config.download_ceiling = 920_000_000
    # ... all fields
    return config
```

### Pattern 2: Router Client Mock Boundary
**What:** Mock RouterOS.set_limits() to test control logic without network I/O
**When to use:** All WANController and run_cycle tests
**Example:**
```python
@pytest.fixture
def mock_router():
    router = MagicMock()
    router.set_limits.return_value = True  # Success
    return router

# To test failure:
mock_router.set_limits.return_value = False
```

### Pattern 3: Signal Handler Direct Invocation
**What:** Call signal handlers directly rather than sending real signals
**When to use:** All signal-related tests (SIGTERM, SIGINT)
**Example:**
```python
# Source: tests/test_signal_utils.py
def test_signal_handler_sets_shutdown_event():
    assert not _shutdown_event.is_set()
    _signal_handler(signal.SIGTERM, None)
    assert _shutdown_event.is_set()
```

### Pattern 4: State Transition Parametrization
**What:** Use pytest.mark.parametrize for exhaustive state transition coverage
**When to use:** QueueController adjust() and adjust_4state() tests
**Example:**
```python
@pytest.mark.parametrize("delta,expected_zone", [
    (5.0, "GREEN"),   # delta <= target (15ms)
    (20.0, "YELLOW"), # target < delta <= warn (45ms)
    (50.0, "SOFT_RED"), # warn < delta <= hard_red (80ms)
    (100.0, "RED"),   # delta > hard_red
])
def test_4state_zone_classification(delta, expected_zone):
    # Test state determination
```

### Anti-Patterns to Avoid
- **Sending real signals**: Use `_signal_handler()` directly, not `os.kill()`
- **Real network I/O**: Always mock router client, never hit actual router
- **Mocking too deeply**: Mock at RouterOS/RTTMeasurement level, not socket level
- **Time-based flakiness**: Avoid tests that depend on precise timing

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Config fixtures | Inline mock setup | Shared pytest fixtures | DRY, consistent across tests |
| State verification | Manual assertions | Explicit assert sequences | Clear failure messages |
| Log verification | String parsing | pytest caplog fixture | Built-in, reliable |
| Temp files | Manual cleanup | tmp_path fixture | Auto-cleanup, isolation |

**Key insight:** The existing test files (test_wan_controller.py, test_signal_utils.py) already demonstrate the optimal mocking boundaries - extend these patterns rather than inventing new ones.

## Common Pitfalls

### Pitfall 1: Incomplete Mock Config
**What goes wrong:** Tests fail with AttributeError for missing config fields
**Why it happens:** Config class has 30+ fields, easy to miss one
**How to avoid:** Copy the complete mock_config fixture from test_wan_controller.py
**Warning signs:** "AttributeError: Mock object has no attribute 'X'"

### Pitfall 2: Not Resetting Signal State
**What goes wrong:** Tests affect each other via global _shutdown_event
**Why it happens:** Signal state is module-level, persists across tests
**How to avoid:** Use reset_shutdown_state() in setup/teardown
**Warning signs:** Tests pass in isolation but fail together

### Pitfall 3: Testing Private Methods Directly
**What goes wrong:** Tests break on internal refactoring
**Why it happens:** Testing _update_baseline_if_idle() instead of update_ewma()
**How to avoid:** Test through public API when possible, test private only for critical invariants
**Warning signs:** Tests for methods starting with underscore

### Pitfall 4: Missing load_state Patch
**What goes wrong:** Tests hit filesystem for state files
**Why it happens:** WANController.__init__ calls load_state()
**How to avoid:** Always patch load_state in controller fixtures:
```python
with patch.object(WANController, "load_state"):
    controller = WANController(...)
```
**Warning signs:** Tests create unexpected files in /tmp

### Pitfall 5: Baseline Freeze Invariant Violation
**What goes wrong:** Baseline drift under load - tests pass but controller broken
**Why it happens:** Not testing the delta < threshold condition
**How to avoid:** Explicit test that simulates 100 cycles under load, verifies baseline unchanged
**Warning signs:** None - this is a silent failure, must be explicitly tested

## Code Examples

### Entry Point Testing (main())
```python
# Test validate-config mode
def test_validate_config_success(tmp_path, capsys):
    config_file = tmp_path / "test.yaml"
    config_file.write_text(VALID_CONFIG_YAML)

    with patch("sys.argv", ["prog", "--config", str(config_file), "--validate-config"]):
        result = main()

    assert result == 0
    captured = capsys.readouterr()
    assert "Configuration valid" in captured.out

# Test oneshot mode
def test_oneshot_mode(tmp_path):
    config_file = tmp_path / "test.yaml"
    config_file.write_text(VALID_CONFIG_YAML)

    with patch("sys.argv", ["prog", "--config", str(config_file), "--oneshot"]):
        with patch.object(ContinuousAutoRate, "run_cycle", return_value=True) as mock_cycle:
            result = main()

    assert result is None
    mock_cycle.assert_called_once_with(use_lock=True)
```

### Signal Handler Testing
```python
def test_sigterm_triggers_graceful_shutdown():
    reset_shutdown_state()  # Clean slate

    # Simulate daemon receiving SIGTERM
    _signal_handler(signal.SIGTERM, None)

    assert is_shutdown_requested()
    # Control loop would exit on next iteration
```

### State Transition Testing
```python
def test_4state_green_to_yellow_transition():
    controller = QueueController(
        name="Test",
        floor_green=800_000_000,
        floor_yellow=600_000_000,
        floor_soft_red=500_000_000,
        floor_red=400_000_000,
        ceiling=920_000_000,
        step_up=10_000_000,
        factor_down=0.85,
        factor_down_yellow=0.96,
        green_required=5,
    )

    baseline = 25.0

    # GREEN state: delta = 10ms (< 15ms target)
    zone, rate = controller.adjust_4state(baseline, 35.0, 15.0, 45.0, 80.0)
    assert zone == "GREEN"

    # YELLOW state: delta = 25ms (15 < delta <= 45)
    zone, rate = controller.adjust_4state(baseline, 50.0, 15.0, 45.0, 80.0)
    assert zone == "YELLOW"
```

### Baseline Freeze Invariant Test (Critical)
```python
def test_baseline_freeze_under_load():
    """SAFETY INVARIANT: Baseline must NOT drift under load."""
    # Setup
    controller.baseline_rtt = 20.0
    controller.load_rtt = 20.0
    original_baseline = controller.baseline_rtt

    # Simulate 100 cycles under sustained load
    for _ in range(100):
        high_rtt = 55.0  # Far above baseline
        controller.update_ewma(high_rtt)

    # Baseline must NOT have drifted toward load
    assert controller.baseline_rtt == pytest.approx(original_baseline, abs=0.1)
```

### Error Recovery Testing
```python
def test_router_failure_returns_false():
    mock_router.set_limits.return_value = False

    result = controller.apply_rate_changes_if_needed(90_000_000, 18_000_000)

    assert result is False
    controller.logger.error.assert_called()

def test_tcp_rtt_fallback_on_icmp_blackout():
    """v1.1.0 fix: TCP RTT used when ICMP is blocked."""
    controller.config.fallback_enabled = True

    with patch.object(controller, "verify_connectivity_fallback", return_value=(True, 25.5)):
        should_continue, measured_rtt = controller.handle_icmp_failure()

    assert should_continue is True
    assert measured_rtt == 25.5  # TCP RTT, not stale ICMP
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Sending real signals | Direct handler invocation | Always best practice | No flaky tests, deterministic |
| Mocking socket layer | Mocking router client | Project standard | Simpler mocks, faster tests |
| YAML config files | MagicMock config objects | Project standard | No filesystem dependency |

**Deprecated/outdated:**
- freezegun: Not needed - 50ms cycle interval is fast enough
- pytest-mock: Project uses unittest.mock directly (simpler)

## Open Questions

1. **SIGHUP Testing**
   - What we know: SIGHUP is not currently implemented (only SIGTERM/SIGINT)
   - What's unclear: Is SIGHUP support planned?
   - Recommendation: Skip unless SIGHUP handlers exist in signal_utils.py

2. **Exact vs Direction Assertions**
   - What we know: Some tests use exact rate values, others verify direction
   - What's unclear: Project preference for rate assertion granularity
   - Recommendation: Use exact for deterministic paths, direction-only for EWMA-influenced

## Sources

### Primary (HIGH confidence)
- `tests/test_wan_controller.py` - Existing patterns, proven fixtures (1100+ lines)
- `tests/test_signal_utils.py` - Signal testing patterns (150+ lines)
- `src/wanctl/autorate_continuous.py` - Source under test (1813 lines)
- `src/wanctl/signal_utils.py` - Signal handler implementation

### Secondary (MEDIUM confidence)
- pytest 9.0 documentation - Fixture patterns, parametrize usage
- Coverage report - Identified gaps: lines 1399-1808, 611-760

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All tools already in project
- Architecture: HIGH - Extending proven existing patterns
- Pitfalls: HIGH - Observed from existing test files

**Research date:** 2026-01-25
**Valid until:** 2026-02-25 (stable domain, 30 days)
