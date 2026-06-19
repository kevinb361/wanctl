# Testing Patterns

**Analysis Date:** 2026-06-19

## Test Framework

**Runner:**
- pytest 8.x
- Config: `pyproject.toml` `[tool.pytest.ini_options]`
- Default addopts: `--cov-config=pyproject.toml --timeout=30 -m 'not integration'`
- Timeout method: `thread` (via `pytest-timeout`)

**Plugins:**
- `pytest-cov` — coverage collection and enforcement
- `pytest-xdist` — parallel test execution (worker isolation via autouse fixture)
- `pytest-timeout` — per-test 30s hard timeout (thread-based)

**Assertion library:** pytest built-in (`assert`)

**Run commands:**
```bash
.venv/bin/pytest tests/ -v                          # All non-integration tests
.venv/bin/pytest tests/ --cov=src --cov-report=term-missing --cov-report=html   # With coverage + HTML report
.venv/bin/pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=90 -p no:randomly  # CI coverage check
make test          # Run all tests without coverage
make coverage      # Run with coverage + HTML report
make coverage-check  # CI enforcement (≥90% required)
make ci            # All checks: lint + type + coverage-check + dead-code + check-deps + check-boundaries + check-brittleness
```

**Hot-path regression slice:**
```bash
.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q
```
This slice is the canonical fast regression check — covers the control-loop critical path without full suite overhead.

## Test File Organization

**Location:** All tests in `tests/` — flat for unit tests, subdirectory for integration and special categories:
```
tests/
├── conftest.py              # Global fixtures and autouse setup
├── helpers.py               # Shared factory functions (no fixtures)
├── fixtures/                # JSON/NDJSON corpus files, phase-specific fixtures
│   ├── phase213/            # Health snapshots from Phase 212 evidence
│   ├── phase214/            # Measurement collapse fixtures
│   ├── phase219/, phase220/ # Storage fixtures
│   └── phase201_replay_corpus.py  # Replay trace generators
├── integration/             # Integration tests (excluded by default with -m 'not integration')
│   ├── conftest.py
│   ├── framework/           # Test harness (LatencyCollector, SLAChecker, LoadProfile)
│   ├── profiles/            # SLA profiles for different test scenarios
│   └── test_latency_control.py   # Real-network RRUL tests
├── backends/                # Backend-specific tests
├── dashboard/               # Dashboard tests
├── steering/                # Steering daemon tests (has own conftest.py)
├── storage/                 # Storage layer tests
├── tuning/                  # Tuning strategy tests
├── test_<module>.py         # Unit tests for src/wanctl/<module>.py
└── test_phase<NNN>_*.py     # Phase-boundary, mutation-boundary, SAFE-NN verifier tests
```

**Naming:**
- Unit test files: `test_<module>.py` matching source module
- Phase-scoped tests: `test_phase<NNN>_<slug>.py` (e.g., `test_phase245_safe17_verifier.py`)
- Replay harnesses: `test_phase_<NNN>_replay.py`

## Test Structure

**Test class organization:**
```python
class TestAdjust3StateZoneClassification:
    """Tests for QueueController.adjust() zone classification.

    3-state zones:
    - GREEN: delta <= target_delta (15ms)
    - YELLOW: target_delta < delta <= warn_delta (15ms < delta <= 45ms)
    - RED: delta > warn_delta (delta > 45ms)
    """
    BASELINE = 25.0
    TARGET_DELTA = 15.0
    WARN_DELTA = 45.0

    @pytest.mark.parametrize(
        "delta,expected_zone",
        [
            (5.0, "GREEN"),
            (15.0, "GREEN"),
            (20.0, "YELLOW"),
            ...
        ],
    )
    def test_zone_classification(self, controller_3state, delta, expected_zone):
        ...
```
- Group related tests in classes named `Test<What><Scenario>`
- Class-level constants define shared threshold/config values for that test group
- Docstrings describe the behavior under test, not the implementation

**Section separators within test files:**
```python
# =============================================================================
# 3-STATE ZONE CLASSIFICATION TESTS
# =============================================================================
```
79-character `=` banners between test class groups, matching source convention.

**Standard patterns:**
- Setup via `@pytest.fixture` — no `setUp()`/`tearDown()`
- Assertions as plain `assert` — no `self.assertEqual()`
- Parametrize with `@pytest.mark.parametrize` for boundary/zone classification
- Test names encode the scenario: `test_zone_classification`, `test_upload_thresholds_use_upload_specific_config`

## Fixtures

**Global fixtures in `tests/conftest.py`:**

```python
@pytest.fixture(autouse=True)
def reset_prometheus_registry():
    """Reset Prometheus metrics registry before and after each test.
    Required for xdist worker isolation (D-18).
    """
    try:
        from wanctl import metrics
        metrics.reset()
    except (ImportError, AttributeError):
        pass
    yield
    ...

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def mock_autorate_config():
    """Shared mock config for autorate WANController tests.
    Contains the full superset of attributes used across all autorate tests.
    """
    config = MagicMock()
    config.wan_name = "TestWAN"
    config.baseline_rtt_initial = 25.0
    # ... full attribute set explicitly declared
    return config
```

**Key fixture rules:**
- `reset_prometheus_registry` is `autouse=True` — runs for every test to ensure clean metrics state in xdist workers
- `mock_autorate_config` is a superset fixture: all MagicMock attributes explicitly set to prevent accidental truthy fabrication by MagicMock (explicitly noted in comments, e.g., `config.docsis_mode = False`)
- Phase-specific corpus fixtures use `scope="session"` for expensive file-loading: `phase201_attempt3_trace`, `phase212_health_spectrum`
- `scope="session"` corpus fixtures are immutable; per-test synthesized data uses function scope

**Local fixtures in test files:**
```python
@pytest.fixture
def controller_3state():
    """Create a QueueController with typical 3-state config (upload)."""
    return QueueController(
        name="TestUpload",
        floor_green=35_000_000,   # 35 Mbps
        floor_yellow=30_000_000,
        ...
    )
```
Document the fixture thresholds in the docstring — future test authors need to know what values to expect.

**Steering and storage fixtures** live in subdirectory `conftest.py` files:
- `tests/steering/conftest.py` — steering mock config
- `tests/storage/` — storage-specific setup

## Mocking

**Standard library:** `unittest.mock` (`MagicMock`, `patch`, `patch.object`)

**Preferred patterns:**

```python
# patch.object for module-level functions on the target module under test
with patch.object(rtt_measurement, "ping_host") as mock_ping:
    mock_ping.return_value = make_host_result(rtts=[15.0])
    ...

# patch() string form for module-level dependencies
with patch("wanctl.routeros_rest.requests.Session") as mock_class:
    mock_class.return_value = mock_session
    ...

# MagicMock for complex objects; set all expected attributes explicitly
router = MagicMock()
router.set_limits.return_value = True
router.needs_rate_limiting = True
```

**Brittleness enforcement:**
- `scripts/check_test_brittleness.py` (`make check-brittleness`) enforces D-10: cross-module private attribute patches are forbidden
- Same-module patches (`test_foo.py` patching `wanctl.foo._private`) are acceptable
- Cross-module patches (`test_foo.py` patching `wanctl.bar._private`) fail the check at threshold 0

**What to mock:**
- External I/O: network calls, router API (`RouterOS.set_limits`), ICMP pings (`icmplib.ping`)
- Time: `time.monotonic()` when testing timer-dependent behavior
- File system: use `temp_dir` fixture for real temp files; mock `Path.read_text()` for unit tests
- Thread workers: inject `MagicMock()` RTT threads via constructor

**What NOT to mock:**
- The unit under test itself
- Frozen dataclasses and value types — construct them directly
- `QueueController` in `test_wan_controller.py` unless explicitly testing the integration seam

**Helper factories in `tests/helpers.py`:**
```python
def make_host_result(
    address: str = "8.8.8.8",
    rtts: list[float] | None = None,
    is_alive: bool = True,
) -> MagicMock:
    """Build a mock icmplib Host object for testing."""
    host = MagicMock()
    host.address = address
    host.rtts = rtts or [12.3]
    host.min_rtt = min(rtts)
    ...
    return host
```
Plain functions in `tests/helpers.py`, not fixtures. Import directly.

## Fixtures and Factories

**Test data location:**
- `tests/fixtures/` — JSON/NDJSON corpus files for replay and ingestion tests
- Phase-specific sub-directories: `tests/fixtures/phase213/`, `tests/fixtures/phase214/`
- Generator scripts: `tests/fixtures/_phase_203_generator.py` (synthesize data programmatically)

**Fixture generators pattern:**
```python
# tests/fixtures/phase201_replay_corpus.py
def load_attempt3_trace() -> list[dict]:
    """Load Phase 201 attempt-3 capture from packaged NDJSON."""
    ...

def synthesize_idle_trace() -> list[dict]:
    """Synthesize a minimal idle-state trace for testing."""
    ...
```
Session-scoped fixtures load these via `conftest.py`.

**Mock config construction:** Use `mock_autorate_config` from `conftest.py` as the base; override specific attributes in test:
```python
def test_upload_thresholds(self, mock_autorate_config, mock_router, mock_rtt_measurement, mock_logger):
    mock_autorate_config.upload_target_bloat_ms = 42.0
    ...
```

## Coverage

**Requirements:** ≥90% (`fail_under = 90` in `[tool.coverage.report]`)

**Collection:**
- `source = ["src", "tests"]`, `branch = True`, `parallel = True`
- HTML report: `coverage-report/` (open `coverage-report/index.html`)

**Commands:**
```bash
make coverage           # Run + generate HTML report
make coverage-check     # CI enforcement (fails below 90%)
```

## Test Types

**Unit tests (default — not integration):**
- Test a single function, method, or class in isolation
- Located at top level `tests/test_<module>.py`
- Run on every `make test` / `make ci`
- Example: `tests/test_cake_signal.py`, `tests/test_queue_controller.py`

**Replay harnesses:**
- Exercise the full control loop against captured real-world traces
- Verify byte-identical or deterministic output across code changes
- Files: `tests/test_phase_<NNN>_replay.py`
- Pattern: load fixture corpus, run controller step-by-step, assert output matches golden data
- Used to prove SAFE-NN invariants (no behavioral change when adding new features)

**Phase mutation-boundary tests (`test_phase<NNN>_mutation_boundary.py`):**
- Enforce that `src/wanctl/` was NOT modified during observational/analysis phases
- Use `git diff` to assert no controller-path changes between a base SHA and HEAD
- Check unstaged, staged, and committed diffs across protected paths
- Example pattern from `tests/test_phase214_mutation_boundary.py`:
  ```python
  def _assert_no_git_diff(paths: list[str], label: str) -> None:
      checks = [
          ("unstaged", ["diff", "--name-only", "--", *paths]),
          ("staged",   ["diff", "--cached", "--name-only", "--", *paths]),
          ("committed", ["diff", "--name-only", f"{base}..HEAD", "--", *paths]),
      ]
  ```

**SAFE-NN verifier tests (`test_phase<NNN>_safe<NN>_verifier.py`):**
- Test a shell script (`scripts/phase<NNN>-safe<NN>-boundary-check.sh`) that verifies controller-path zero-diff invariants
- Pin to a specific `PHASE_CLOSE_ANCHOR` commit hash — not HEAD — so later phases don't invalidate the boundary
- Use `git worktree` to test self-mutation detection:
  ```python
  PHASE_CLOSE_ANCHOR = "ffaa8a0e"   # Pin to close commit, NOT HEAD

  @pytest.fixture
  def detached_worktree(tmp_path: Path):
      worktree = tmp_path / "safe17-worktree"
      result = run(["git", "worktree", "add", "--detach", str(worktree), PHASE_CLOSE_ANCHOR])
      ...
  ```
- Tests verify: script exists + executable, static contract (embedded strings), exits 0 on clean tree, writes evidence JSON, self-test detects violations
- Evidence JSON: `passed: true`, `safe<NN>_verdict: "pass"`, `anchor_sha`, `head_sha`, `changed_files_vs_anchor: []`

**Integration tests (`tests/integration/`, excluded by default):**
- Marked `@pytest.mark.integration` and `@pytest.mark.slow`
- Require real network access, `flent`, `fping`, and SSH to the controller host
- Run with: `pytest tests/integration/test_latency_control.py -k quick -v`
- Not run in normal CI (`-m 'not integration'` default addopts)

## Common Patterns

**Parametrized boundary tests:**
```python
@pytest.mark.parametrize(
    "delta,expected_zone",
    [
        (5.0,  "GREEN"),   # delta <= 15 (well below target)
        (15.0, "GREEN"),   # delta == target (boundary)
        (20.0, "YELLOW"),  # 15 < delta <= 45
        (45.0, "YELLOW"),  # delta == warn (boundary)
        (50.0, "RED"),     # delta > 45
    ],
)
def test_zone_classification(self, controller_3state, delta, expected_zone):
    ...
```
Include comments explaining each boundary case. Always test both sides of each threshold.

**Frozen dataclass contract tests:**
```python
def test_frozen(self) -> None:
    snap = CakeSignalSnapshot(drop_rate=0.0, ..., cold_start=True)
    with pytest.raises(FrozenInstanceError):
        snap.drop_rate = 1.0  # type: ignore[misc]
```
Every frozen dataclass gets a `test_frozen` test verifying immutability.

**Async / threading tests:**
```python
# WANController constructor patched to avoid file I/O
with patch.object(WANController, "load_state"):
    controller = WANController(
        wan_name="TestWAN",
        config=mock_config,
        router=mock_router,
        rtt_measurement=mock_rtt_measurement,
        logger=mock_logger,
    )
```
Always patch `load_state` when constructing `WANController` in tests to avoid filesystem access.

**Safety invariant annotations:**
```python
def test_fallback_on_rest_failure(self, ...):
    """SAFETY INVARIANT: REST API failure must automatically fall back to SSH."""
    ...
```
Use `SAFETY INVARIANT:` in docstrings to flag tests that protect architectural contracts.

**Git-diff based tests:**
```python
def _git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )
```
Standard helper pattern across mutation-boundary test files. Each file defines its own `_git()`.

**Byte-identical / deterministic output:**
```python
def test_fixture_matches_generator_output(self) -> None:
    """Re-running the generator must produce byte-identical NDJSON."""
    ...
```
Replay tests assert that running the generator twice produces identical output, proving determinism.

## Test Markers

| Marker | Meaning |
|--------|---------|
| `@pytest.mark.integration` | Requires live infrastructure; excluded by default |
| `@pytest.mark.slow` | Long-running test; typically combined with `integration` |
| `@pytest.mark.timeout(N)` | Override per-test timeout from 30s default |
| `@pytest.mark.parametrize(...)` | Parametrized test case |

Default filter: `-m 'not integration'` — integration tests never run in CI without explicit flag.

---

*Testing analysis: 2026-06-19*
