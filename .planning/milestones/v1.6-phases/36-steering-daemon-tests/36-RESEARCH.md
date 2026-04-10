# Phase 36: Steering Daemon Tests - Research

**Researched:** 2026-01-25
**Domain:** Python unit testing for steering daemon (pytest, mocking, coverage)
**Confidence:** HIGH

## Summary

This phase targets 90%+ coverage for `src/wanctl/steering/daemon.py`, currently at 44.2% (307 of 552 statements missing). The codebase already has 66 tests in `test_steering_daemon.py` establishing patterns for mocking SteeringDaemon dependencies. Coverage gaps fall into clear categories: RouterOSController (rule status parsing, enable/disable with retry), BaselineLoader (file I/O, sanity bounds), main() entry point (argument parsing, config loading, health server lifecycle), SteeringConfig._load_* methods, run_cycle() integration, and confidence controller integration paths.

Existing test patterns use `@pytest.fixture` for mock_config, mock_state_mgr, mock_router, mock_logger; `unittest.mock.patch` for patching at import points; and class-based test organization (TestCollectCakeStats, TestRunDaemonLoop, etc.).

**Primary recommendation:** Add tests in the established pattern focusing on: (1) RouterOSController rule parsing with MikroTik output formats, (2) main() lifecycle with health server mocking, (3) confidence controller dry-run vs live mode paths.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 9.0.2 | Test framework | Already in use, codebase standard |
| pytest-cov | 7.0.0 | Coverage reporting | Already in use for coverage tracking |
| unittest.mock | stdlib | Mocking/patching | Standard Python, no extra deps |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest.approx | built-in | Float comparison | EWMA, RTT delta tests |
| MagicMock | stdlib | Flexible mocks | Config, logger, router mocking |
| patch | stdlib | Import patching | Isolating external dependencies |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest.approx | math.isclose | pytest.approx integrates with assertions |
| MagicMock | Mock | MagicMock has spec support, used throughout |

**Installation:**
```bash
# Already installed in project
.venv/bin/pip install pytest pytest-cov
```

## Architecture Patterns

### Recommended Test Structure
```
tests/
└── test_steering_daemon.py    # Existing - extend with new test classes
    ├── TestCollectCakeStats   # Existing (15 tests)
    ├── TestRunDaemonLoop      # Existing (14 tests)
    ├── TestExecuteSteeringTransition  # Existing (12 tests)
    ├── TestUpdateEwmaSmoothing  # Existing (9 tests)
    ├── TestUnifiedStateMachine  # Existing (16 tests)
    ├── TestRouterOSController   # NEW - rule parsing, enable/disable
    ├── TestBaselineLoader       # NEW - file I/O, bounds checking
    ├── TestMainEntryPoint       # NEW - argparse, config, lifecycle
    ├── TestRunCycle             # NEW - integration of cycle components
    └── TestConfidenceIntegration # NEW - dry-run vs live mode
```

### Pattern 1: Mock Config Fixture
**What:** Create mock config with all required attributes
**When to use:** Every steering daemon test
**Example:**
```python
@pytest.fixture
def mock_config(self):
    config = MagicMock()
    config.primary_wan = "spectrum"
    config.state_good = "SPECTRUM_GOOD"
    config.state_degraded = "SPECTRUM_DEGRADED"
    config.cake_aware = True
    config.mangle_rule_comment = "ADAPTIVE-STEER"
    config.metrics_enabled = False
    config.use_confidence_scoring = False
    config.confidence_config = None
    # ... other attributes as needed
    return config
```

### Pattern 2: Router Client Mocking
**What:** Patch get_router_client_with_failover for RouterOSController tests
**When to use:** Testing rule status parsing, enable/disable verification
**Example:**
```python
@pytest.fixture
def mock_router_client(self):
    client = MagicMock()
    client.run_cmd.return_value = (0, " 4    ;;; ADAPTIVE-STEER...", "")
    return client

def test_rule_enabled_parsing(self, mock_config, mock_logger, mock_router_client):
    with patch("wanctl.steering.daemon.get_router_client_with_failover") as mock_get:
        mock_get.return_value = mock_router_client
        controller = RouterOSController(mock_config, mock_logger)
        result = controller.get_rule_status()
        assert result is True
```

### Pattern 3: Main Entry Point Testing via Patch
**What:** Test main() by patching dependencies, not running as subprocess
**When to use:** Testing argument parsing, config loading, lifecycle
**Example:**
```python
def test_main_config_load_failure(self, tmp_path):
    invalid_config = tmp_path / "invalid.yaml"
    invalid_config.write_text("invalid: [")

    with patch("sys.argv", ["daemon", "--config", str(invalid_config)]):
        with patch("wanctl.steering.daemon.register_signal_handlers"):
            result = main()
            assert result == 1
```

### Anti-Patterns to Avoid
- **Subprocess testing for main():** Don't use runpy.run_module() - patch at import boundaries instead
- **Real file I/O for config:** Use tmp_path fixture, not actual /etc paths
- **Hardcoded MikroTik output:** Define as constants/fixtures for reuse
- **Testing internal implementation:** Focus on behavior, not exact log messages

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Float comparison | abs(a-b) < epsilon | pytest.approx(val, abs=tol) | Handles edge cases, clear assertions |
| Temporary files | manual cleanup | tmp_path fixture | Auto-cleanup, pytest integration |
| Mock attribute setup | manual MagicMock config | @pytest.fixture pattern | Reusable, consistent |
| Coverage checking | manual line counting | --cov-report=term-missing | Authoritative, accurate |

**Key insight:** The existing 66 tests establish all necessary patterns - new tests should follow existing fixture and class organization.

## Common Pitfalls

### Pitfall 1: MikroTik Output Format Variations
**What goes wrong:** Rule parsing fails for different RouterOS versions or display modes
**Why it happens:** MikroTik output format varies (tabs vs spaces, flag positions)
**How to avoid:** Test all known formats:
- Enabled: `" 4    ;;; ADAPTIVE-STEER..."`
- Disabled: `" 4 X  ;;; ADAPTIVE-STEER..."`
- With tabs: `"\t4\t\t;;; ADAPTIVE-STEER..."`
- Rule not found: Output without "ADAPTIVE" keyword
**Warning signs:** Tests pass locally but fail on different RouterOS versions

### Pitfall 2: Health Server Port Conflicts
**What goes wrong:** Tests fail with "Address already in use" errors
**Why it happens:** Previous test didn't clean up server, or parallel test execution
**How to avoid:** Use `find_free_port()` pattern from test_steering_health.py, always cleanup in finally
**Warning signs:** Intermittent test failures, works in isolation but fails in suite

### Pitfall 3: Confidence Controller Dry-Run Mode Confusion
**What goes wrong:** Tests expect routing changes but dry_run=True returns None
**Why it happens:** Production default is dry_run=True for safe deployment
**How to avoid:** Explicitly set dry_run mode in test config:
```python
config.confidence_config = {
    "dry_run": {"enabled": False},  # For live mode tests
    ...
}
```
**Warning signs:** Tests pass but confidence paths show no coverage

### Pitfall 4: State Machine Counter Tests
**What goes wrong:** Counter tests fail because state handler resets counters
**Why it happens:** _handle_good_state and _handle_degraded_state both reset opposite counters
**How to avoid:** Understand counter lifecycle:
- GOOD state: red_count increments on RED, resets on GREEN/YELLOW; good_count always 0
- DEGRADED state: good_count increments on GREEN, resets on RED/YELLOW; red_count always 0
**Warning signs:** Assertion errors on counter values after state changes

## Code Examples

### RouterOSController Rule Status Parsing
```python
# Source: daemon.py lines 450-478
MIKROTIK_OUTPUTS = {
    "enabled": " 4    ;;; ADAPTIVE-STEER mark-routing=LATENCY_SENSITIVE",
    "disabled": " 4 X  ;;; ADAPTIVE-STEER mark-routing=LATENCY_SENSITIVE",
    "disabled_tab": "\t4\tX\t;;; ADAPTIVE-STEER mark-routing=LATENCY_SENSITIVE",
    "not_found": "Flags: X - disabled\n;;;\n",
    "malformed": "Error: syntax error",
}

def test_get_rule_status_enabled(mock_router_client, mock_config, mock_logger):
    mock_router_client.run_cmd.return_value = (0, MIKROTIK_OUTPUTS["enabled"], "")
    with patch("wanctl.steering.daemon.get_router_client_with_failover") as mock_get:
        mock_get.return_value = mock_router_client
        controller = RouterOSController(mock_config, mock_logger)
        assert controller.get_rule_status() is True
```

### BaselineLoader Sanity Bounds
```python
# Source: daemon.py lines 555-596
def test_baseline_out_of_bounds_too_low(tmp_path, mock_config, mock_logger):
    state_file = tmp_path / "spectrum_state.json"
    state_file.write_text('{"ewma": {"baseline_rtt": 5.0}}')  # Below 10ms min
    mock_config.primary_state_file = state_file
    mock_config.baseline_rtt_min = 10.0
    mock_config.baseline_rtt_max = 60.0

    loader = BaselineLoader(mock_config, mock_logger)
    result = loader.load_baseline_rtt()

    assert result is None  # Rejected as out of bounds
    mock_logger.warning.assert_called()
```

### Main Entry Point Config Error
```python
# Source: daemon.py lines 1354-1379
def test_main_invalid_config_returns_1(tmp_path, capsys):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text("invalid: yaml: [")

    with patch("sys.argv", ["steering-daemon", "--config", str(bad_config)]):
        with patch("wanctl.steering.daemon.register_signal_handlers"):
            result = main()

    assert result == 1
    captured = capsys.readouterr()
    assert "ERROR" in captured.out
```

### Confidence Controller Live Mode
```python
# Source: daemon.py lines 1034-1062
def test_confidence_live_mode_enables_steering(daemon_with_confidence, mock_router):
    # Configure for live mode (not dry_run)
    daemon_with_confidence.config.confidence_config["dry_run"]["enabled"] = False

    signals = CongestionSignals(
        rtt_delta=50.0, rtt_delta_ewma=50.0,
        cake_drops=10, queued_packets=100, baseline_rtt=25.0
    )

    # Mock confidence controller to return ENABLE decision
    daemon_with_confidence.confidence_controller.evaluate.return_value = "ENABLE_STEERING"

    result = daemon_with_confidence.update_state_machine(signals)

    assert result is True
    mock_router.enable_steering.assert_called_once()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| runpy.run_module for entry point | Source inspection + patch | Phase 35 | Avoids subprocess complexity |
| Single mock_config fixture | Class-specific fixtures | Ongoing | Better isolation, clearer dependencies |
| Hardcoded output strings | MIKROTIK_OUTPUTS constants | New | Reusable, documented variations |

**Deprecated/outdated:**
- Testing via subprocess: Replaced by import-level patching (simpler, faster, better coverage)

## Open Questions

1. **Command string specificity**
   - What we know: RouterOSController builds command strings for mangle rule operations
   - What's unclear: How specific should tests be about exact command format?
   - Recommendation: Verify command contains key elements (rule comment), don't test exact string

2. **Retry logic test depth**
   - What we know: enable_steering/disable_steering use verify_with_retry
   - What's unclear: Should steering tests re-verify retry behavior tested in test_retry_utils?
   - Recommendation: Trust retry_utils tests, verify steering calls verify_with_retry correctly

3. **Health server lifecycle in main()**
   - What we know: main() starts health server in try, shuts down in finally
   - What's unclear: Level of integration testing for health server lifecycle
   - Recommendation: Test start/shutdown paths exist, detailed health behavior tested in test_steering_health.py

## Sources

### Primary (HIGH confidence)
- `/home/kevin/projects/wanctl/src/wanctl/steering/daemon.py` - Source under test
- `/home/kevin/projects/wanctl/tests/test_steering_daemon.py` - 66 existing tests, patterns
- `/home/kevin/projects/wanctl/tests/test_steering_health.py` - Health server test patterns
- `/home/kevin/projects/wanctl/tests/test_router_client.py` - Router client mocking patterns

### Secondary (MEDIUM confidence)
- `/home/kevin/projects/wanctl/tests/test_steering_timers.py` - Confidence controller patterns
- `/home/kevin/projects/wanctl/tests/conftest.py` - Shared fixtures

### Coverage Analysis (HIGH confidence)
- Current: 44.2% (307/552 statements missing)
- Target: 90%+
- Key gaps: Lines 450-536 (RouterOSController), 555-596 (BaselineLoader), 1354-1479 (main())

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pytest/mock already in use, patterns established
- Architecture: HIGH - 66 existing tests define clear patterns
- Pitfalls: HIGH - Real issues from codebase analysis

**Research date:** 2026-01-25
**Valid until:** 90 days (stable Python testing ecosystem)
