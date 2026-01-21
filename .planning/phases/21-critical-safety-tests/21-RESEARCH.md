# Phase 21: Critical Safety Tests - Research

**Researched:** 2026-01-21
**Domain:** Python testing with pytest, safety invariant verification
**Confidence:** HIGH

## Summary

Phase 21 addresses three critical test coverage gaps identified in CONCERNS.md (lines 183-205):

1. **Baseline RTT freeze logic** - Verify baseline remains frozen when delta > 3ms during sustained load (architectural invariant)
2. **State file corruption recovery** - Verify partial JSON write triggers graceful recovery (not crash or invalid state)
3. **REST-to-SSH transport failover** - Verify automatic fallback when REST API fails (critical safety feature)

All three areas have existing production code but lack explicit tests proving the safety invariants hold. Existing tests partially cover the functionality but don't validate the specific scenarios documented in CONCERNS.md.

**Primary recommendation:** Write focused integration tests using existing patterns (pytest fixtures, mocks) to validate each safety invariant explicitly.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | >=8.0.0 | Test framework | Python standard, used throughout project (684 existing tests) |
| unittest.mock | stdlib | Mocking | Python stdlib, already used extensively in tests/ |
| tempfile | stdlib | Temp directories/files | Python stdlib, used in conftest.py for state file tests |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest.approx | pytest | Float comparison | When testing EWMA/baseline RTT math (see test_wan_controller.py:925) |
| MagicMock | unittest.mock | Object mocking | Router clients, logger, config objects |
| patch | unittest.mock | Function/method mocking | Simulating failures, injecting test conditions |

**Installation:**
Already installed in project's dev dependencies (pyproject.toml lines 28-32)

## Architecture Patterns

### Recommended Test Structure
```
tests/
├── test_baseline_freeze_under_load.py     # TEST-01: Baseline freeze invariant
├── test_state_corruption_recovery.py      # TEST-02: State file corruption
├── test_transport_failover.py             # TEST-03: REST → SSH failover
```

### Pattern 1: Safety Invariant Test Structure
**What:** Explicit test proving a documented architectural invariant holds
**When to use:** Testing core safety properties (baseline freeze, no data loss, failover)
**Example:**
```python
# Source: test_wan_controller.py:907-925 (baseline freeze pattern)
class TestBaselineFreeze:
    """Tests proving baseline RTT freezing invariant under sustained load."""

    def test_baseline_frozen_during_sustained_load(self, controller):
        """ARCHITECTURAL INVARIANT: Baseline RTT must not drift when delta > 3ms.

        This test proves that baseline remains frozen during 100 cycles of sustained
        load where delta consistently exceeds the 3ms threshold. This is critical
        to control stability - baseline drift would mask congestion.
        """
        controller.baseline_rtt = 20.0
        controller.baseline_update_threshold = 3.0

        # Run 100 cycles with delta consistently > 3ms
        for _ in range(100):
            controller.load_rtt = 50.0  # delta = 30ms (>> 3ms)
            controller.update_ewma(measured_rtt=55.0)

        # Baseline MUST remain frozen
        assert controller.baseline_rtt == pytest.approx(20.0, abs=0.1)
```

### Pattern 2: Corruption/Failure Recovery Test
**What:** Simulate failure condition (corrupted file, network error) and verify graceful recovery
**When to use:** Testing error handling paths (state corruption, connection failures)
**Example:**
```python
# Source: test_state_utils.py:135-154 (invalid JSON pattern)
def test_partial_json_returns_default(temp_dir):
    """State file with partial JSON should return default, not crash."""
    file_path = temp_dir / "state.json"

    # Simulate interrupted write (partial JSON)
    with open(file_path, "w") as f:
        f.write('{"ewma": {"baseline_rtt": 30.0')  # Missing closing braces

    result = safe_read_json(file_path, default={"initialized": True})
    assert result == {"initialized": True}  # Graceful recovery
```

### Pattern 3: Transport Failover Test
**What:** Mock primary transport failure, verify secondary transport used automatically
**When to use:** Testing failover logic (REST → SSH, primary → backup)
**Example:**
```python
# Source: router_client.py:49-79 (get_router_client pattern)
def test_rest_failure_triggers_ssh_fallback(mock_config, logger):
    """REST API failure should trigger automatic SSH fallback."""
    mock_config.router_transport = "rest"

    # First call: REST client that will fail
    with patch('wanctl.routeros_rest.RouterOSREST.from_config') as mock_rest:
        mock_rest.return_value.run_cmd.side_effect = ConnectionError("REST failed")

        # Second call: SSH client succeeds
        with patch('wanctl.routeros_ssh.RouterOSSSH.from_config') as mock_ssh:
            mock_ssh.return_value.run_cmd.return_value = (0, "output", "")

            # Code should detect REST failure and retry with SSH
            client = get_router_client_with_failover(mock_config, logger)
            rc, stdout, stderr = client.run_cmd("/queue/tree/print")

            assert rc == 0
            assert mock_ssh.called  # SSH was used as fallback
```

### Anti-Patterns to Avoid
- **Testing implementation details instead of invariants:** Don't test that `_update_baseline_if_idle` is called; test that baseline doesn't drift
- **Single-cycle tests for multi-cycle invariants:** Baseline freeze requires sustained load (100+ cycles), not just one update
- **Mocking too deeply:** Mock external dependencies (router, network) but not the code under test

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| State file corruption simulation | Custom file writer that creates partial JSON | Write truncated JSON directly to file with open() | Standard file operations sufficient, easier to understand |
| Transport failure injection | Complex network simulator or actual network failure | unittest.mock.patch with side_effect=Exception | Pytest/unittest mocking is standard for error injection |
| EWMA baseline math validation | Custom numerical analysis library | pytest.approx() for float comparison | Handles floating point precision correctly, standard pattern |
| Temp file management | Manual cleanup with try/finally | pytest fixtures with tempfile.TemporaryDirectory | Automatic cleanup, already used in conftest.py |

**Key insight:** Python's stdlib (tempfile, unittest.mock) + pytest provide all tools needed for safety tests. External libraries would add complexity without benefit.

## Common Pitfalls

### Pitfall 1: Testing Code Path Instead of Invariant
**What goes wrong:** Test verifies method is called but doesn't prove safety property holds
**Why it happens:** Easier to mock and check method calls than validate actual behavior
**How to avoid:**
- Write test name as invariant statement: "baseline MUST NOT drift during load"
- Assert on observable state (baseline value) not internal calls
- Run realistic scenario (100 cycles) not minimal case (1 cycle)
**Warning signs:** Test uses `assert mock.called` without checking actual outcome

### Pitfall 2: Insufficient Load Duration
**What goes wrong:** Single update call doesn't prove sustained freeze (baseline could update on cycle 2)
**Why it happens:** Minimal test case mentality - one call should be enough
**How to avoid:**
- For baseline freeze: Run 100+ cycles with consistent high load (existing pattern line 914)
- For state corruption: Test multiple read attempts after corruption
- For failover: Test multiple command retries across transport switch
**Warning signs:** Test name says "sustained" but only runs 1-2 iterations

### Pitfall 3: Mocking the Code Under Test
**What goes wrong:** Mock replaces real logic, test passes but real code never runs
**Why it happens:** Mock creep - start mocking dependencies, accidentally mock target
**How to avoid:**
- Only mock: router client, logger, network I/O, filesystem for corruption
- Never mock: BaselineRTTManager.update_baseline_ewma, safe_json_load_file, get_router_client
- Use integration approach: real classes with mocked dependencies
**Warning signs:** Test mocks the exact method being tested

### Pitfall 4: Race Condition in State File Tests
**What goes wrong:** State file tests interfere with each other via shared temp paths
**Why it happens:** Tests use hardcoded paths or shared tmpdir without isolation
**How to avoid:**
- Use pytest fixtures that create fresh temp directory per test
- Pattern already exists in conftest.py:14-17 (temp_dir fixture)
- Each test gets isolated temp directory, automatic cleanup
**Warning signs:** Test failures only when running full suite, not individually

## Code Examples

Verified patterns from existing codebase:

### Baseline Freeze Test (Sustained Load)
```python
# Source: tests/test_wan_controller.py:907-925
def test_baseline_freeze_prevents_drift(self, controller):
    """Simulated load scenario: baseline must not drift toward load."""
    controller.baseline_rtt = 20.0
    controller.load_rtt = 20.0
    controller.baseline_update_threshold = 3.0
    controller.alpha_baseline = 0.1  # 10% weight

    # Simulate 100 cycles under load
    for _ in range(100):
        # Load increases
        controller.load_rtt = 50.0  # High load RTT
        measured_rtt = 55.0  # Even higher measurement

        # Update EWMA (full method to test integration)
        controller.update_ewma(measured_rtt)

    # Baseline should NOT have drifted significantly toward load
    # With delta > threshold, baseline freezes at original value
    assert controller.baseline_rtt == pytest.approx(20.0, abs=0.1)
```

### State Corruption Recovery
```python
# Source: tests/test_state_utils.py:135-154
def test_invalid_json_returns_default(self, temp_dir):
    """Test that invalid JSON file returns default."""
    file_path = temp_dir / "invalid.json"

    with open(file_path, "w") as f:
        f.write("not valid json {{{")

    result = safe_read_json(file_path)
    assert result == {}
```

### Controller Fixture with Mocked Dependencies
```python
# Source: tests/test_wan_controller.py:80-94
@pytest.fixture
def controller(self, mock_config, mock_router, mock_rtt_measurement, mock_logger):
    """Create a WANController with mocked dependencies."""
    from wanctl.autorate_continuous import WANController

    # Patch load_state to avoid file I/O
    with patch.object(WANController, "load_state"):
        controller = WANController(
            wan_name="TestWAN",
            config=mock_config,
            router=mock_router,
            rtt_measurement=mock_rtt_measurement,
            logger=mock_logger,
        )
    return controller
```

### Temp Directory Fixture
```python
# Source: tests/conftest.py:13-17
@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No explicit baseline freeze tests | Partial coverage in test_wan_controller.py | v1.1 (2026-01-14) | Freeze logic tested but not sustained load scenario |
| No state corruption tests | safe_json_load_file has basic error handling | v1.1 (2026-01-14) | Handles missing files, not partial writes |
| No transport failover tests | get_router_client factory exists but no failover logic | Initial (2025) | Factory selects transport from config, no runtime switching |

**Deprecated/outdated:**
- N/A - Test infrastructure is current (pytest 8.0+, Python 3.12)

## Open Questions

1. **Transport failover implementation status**
   - What we know: get_router_client() selects transport at initialization based on config.router_transport
   - What's unclear: No automatic failover logic exists in router_client.py (lines 49-79)
   - Recommendation: TEST-03 may require implementing failover before testing it, or test may prove "failover doesn't exist" (documenting gap)

2. **Baseline freeze test scope**
   - What we know: Existing test runs 100 cycles (line 914), tests single controller
   - What's unclear: Should test verify freeze across both WANs simultaneously? Or single controller sufficient?
   - Recommendation: Start with single controller (existing pattern), extend to dual-WAN if needed

3. **State corruption scenarios**
   - What we know: safe_json_load_file handles JSONDecodeError (state_utils.py:167)
   - What's unclear: What specific corruption patterns occur in production? (truncated? UTF-8 errors? invalid values?)
   - Recommendation: Test truncated JSON (most common during interrupted write), verify atomic_write_json prevents it

## Sources

### Primary (HIGH confidence)
- tests/test_wan_controller.py:907-925 - Existing baseline freeze test pattern
- tests/test_state_utils.py:135-154 - State file error handling pattern
- tests/conftest.py:13-17 - Temp directory fixture pattern
- src/wanctl/baseline_rtt_manager.py:51-79 - Baseline freeze logic implementation
- src/wanctl/state_utils.py:132-178 - State file corruption handling
- src/wanctl/router_client.py:49-79 - Transport factory (no failover)

### Secondary (MEDIUM confidence)
- .planning/codebase/CONCERNS.md:183-205 - Test coverage gaps analysis
- .planning/ROADMAP.md:191-200 - Phase 21 requirements

### Tertiary (LOW confidence)
- N/A - All findings verified against source code

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pytest and unittest.mock are Python standards, already in use (684 tests)
- Architecture: HIGH - patterns verified from existing test files (test_wan_controller.py, test_state_utils.py)
- Pitfalls: HIGH - based on common testing anti-patterns and codebase-specific concerns (CONCERNS.md)

**Research date:** 2026-01-21
**Valid until:** 2026-02-21 (30 days - stable testing domain)

## Implementation Notes

**TEST-01: Baseline RTT Freeze**
- Location: src/wanctl/baseline_rtt_manager.py:64 (freeze condition: delta >= threshold)
- Test should verify: 100+ cycles with delta consistently > 3ms, baseline unchanged
- Existing test (line 907) provides pattern but doesn't explicitly validate "sustained load" scenario

**TEST-02: State File Corruption**
- Location: src/wanctl/state_utils.py:132-178 (safe_json_load_file handles JSONDecodeError)
- Test should verify: Truncated JSON file returns default, logs error, doesn't crash
- Atomic write pattern (state_utils.py:20-66) should prevent corruption in first place

**TEST-03: Transport Failover**
- Location: src/wanctl/router_client.py:49-79 (get_router_client factory)
- CRITICAL FINDING: No automatic failover logic exists currently
- Test may need to implement failover wrapper or document that feature doesn't exist
- Alternative: Test that REST failure is handled gracefully (logs error, raises exception) without silent failure
