# Phase 57: v1.10 Gap Closure - Research

**Researched:** 2026-03-09
**Domain:** Test fixture consolidation, docstring/default correction
**Confidence:** HIGH

## Summary

Phase 57 closes the last unsatisfied v1.10 requirement (TEST-01: fixture consolidation) and fixes two cosmetic residuals identified in the milestone audit. The work is entirely within existing test infrastructure and one production module (`router_client.py`). No new libraries, no architectural changes, no new features.

The codebase already has partially completed consolidation: `tests/conftest.py` defines `mock_autorate_config` and `mock_steering_config` shared fixtures, and 5 module-level test files already delegate to them. The remaining work is converting 25 class-level `mock_config` fixture definitions across 5 files (`test_wan_controller.py`, `test_steering_daemon.py`, `test_autorate_baseline_bounds.py`, `test_failure_cascade.py`, `test_router_client.py`) to delegate to the shared fixtures. The `router_client.py` changes are two-line edits (docstring + default).

**Primary recommendation:** Follow the proven delegation pattern already established -- class-level `mock_config(self, mock_autorate_config)` that overrides only per-class deviations, keeping the `mock_config` name to avoid renaming hundreds of test method parameters.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TEST-01 | Consolidate duplicated mock_config fixtures across 8+ test files into shared conftest.py fixtures, with each test file using the shared version instead of defining its own | Shared fixtures already exist in conftest.py. 5 files already consolidated. 5 files remain with 25 class-level definitions that need delegation. Proven pattern documented below. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | (existing) | Test framework | Already configured, 2,109 tests passing |
| unittest.mock | stdlib | MagicMock fixtures | All fixtures use MagicMock pattern |

No new dependencies needed. This phase modifies existing test files and one production module only.

## Architecture Patterns

### Existing Consolidation Pattern (PROVEN)

The codebase already has a working pattern for fixture consolidation, established by earlier partial execution:

**Pattern 1: Module-level alias (for files where tests use `mock_config` parameter name)**
```python
# In test file (module-level)
@pytest.fixture
def mock_config(mock_autorate_config):
    """Alias shared autorate config as mock_config for this module."""
    return mock_autorate_config
```
Used in: `test_autorate_error_recovery.py`, `test_cake_stats.py` (with extensions)

**Pattern 2: Module-level direct usage (for files where tests were renamed)**
```python
# In test file (fixture parameter renamed to shared name)
@pytest.fixture
def controller(mock_autorate_config, mock_router, ...):
    ...
```
Used in: `test_autorate_continuous.py`, `test_autorate_telemetry.py`, `test_steering_telemetry.py`

**Pattern 3: Class-level delegation with overrides (for class-scoped fixtures)**
```python
# In test class
@pytest.fixture
def mock_config(self, mock_autorate_config):
    """Extend shared config with class-specific overrides."""
    mock_autorate_config.alpha_baseline = 0.5  # High alpha for fast updates
    return mock_autorate_config
```
This is the pattern needed for Task 2 of this phase. The `mock_config` name is preserved to avoid renaming hundreds of test method signatures.

**Pattern 4: Class-level pass-through (when config matches exactly)**
```python
@pytest.fixture
def mock_config(self, mock_autorate_config):
    return mock_autorate_config
```

### Fixture Categorization

**Already consolidated (5 files, Pattern 1/2):**
- `test_autorate_continuous.py` -- direct usage of `mock_autorate_config`
- `test_autorate_error_recovery.py` -- alias to `mock_config`
- `test_autorate_telemetry.py` -- direct usage of `mock_autorate_config`
- `test_steering_telemetry.py` -- direct usage of `mock_steering_config`
- `test_cake_stats.py` -- alias with router extension

**Needs consolidation (5 files, 25 definitions):**

| File | Definitions | Type | Fixture Shape |
|------|-------------|------|---------------|
| `test_wan_controller.py` | 7 class-level | autorate | Most identical to shared, one has `metrics_enabled=True` |
| `test_steering_daemon.py` | 8 `mock_config` + 6 `mock_config_cake`/`mock_config_legacy` | steering | Most identical to shared, some have `cake_aware=False`, `use_confidence_scoring=True` |
| `test_autorate_baseline_bounds.py` | 1 class-level | autorate | Has `alpha_baseline=0.5`, `fallback_enabled=False` (intentional overrides) |
| `test_failure_cascade.py` | 1 module-level | autorate | Nearly identical to shared, has `queue_down`/`queue_up` (already in shared) |
| `test_router_client.py` | 2 class-level | minimal (router only) | Only sets `router_transport = "rest"` -- very different shape, may be best left as-is |

**Inline definitions (NOT fixtures, leave as-is):**
- `test_queue_controller.py` -- inline `mock_config = MagicMock()` inside test method body
- `test_health_check.py` -- inline `mock_config = MagicMock()` inside test methods
- `test_autorate_entry_points.py` -- inline `mock_config = MagicMock()` inside test methods

### Key Observations for Consolidation

1. **`test_router_client.py` mock_configs are fundamentally different** -- they only set `router_transport = "rest"` on a MagicMock. These test the router client factory, not autorate/steering controllers. The shared `mock_autorate_config`/`mock_steering_config` fixtures are wrong shape for these. Leave them as-is.

2. **`test_steering_daemon.py` has `mock_config_cake` and `mock_config_legacy` variants** -- these are distinct names, not duplicating `mock_config`. Leave them, but they could delegate to `mock_steering_config` with overrides if desired.

3. **`test_failure_cascade.py` module-level fixture** -- nearly identical to shared `mock_autorate_config`. Can be replaced with simple alias pattern.

4. **`test_autorate_baseline_bounds.py`** -- has intentional `alpha_baseline=0.5` (fast EWMA for test speed) and `fallback_enabled=False`. Delegate to shared with two overrides.

5. **`test_wan_controller.py` class-level fixtures** -- the 7 definitions are nearly identical. Most match the shared fixture exactly or differ only in missing `download_factor_down_yellow`, `upload_factor_down_yellow`, `queue_down`, `queue_up`. Since MagicMock returns MagicMock for unset attributes, the missing attributes don't break anything when using the shared superset fixture.

### Router Client Cosmetic Fixes

Two trivial edits in `src/wanctl/router_client.py`:

1. **Docstring lines 33 and 43:** Update YAML examples
   - Line 33: `transport: "ssh"` --> `transport: "rest"`
   - Line 43: `verify_ssl: false` --> `verify_ssl: true`

2. **Line 76:** Change default in `get_router_client()`
   - `getattr(config, "router_transport", "ssh")` --> `getattr(config, "router_transport", "rest")`
   - Note: `get_router_client_with_failover()` already defaults to `"rest"` (line 303). Production daemons use the failover path, so this non-failover function's default is cosmetic but should be consistent.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Config fixture variation | Separate full MagicMock per class | Shared fixture + attribute overrides | DRY, single source of truth for config shape |
| Fixture naming migration | Rename all test method params | Alias pattern (`mock_config` wrapping shared) | Avoids touching hundreds of lines |

## Common Pitfalls

### Pitfall 1: MagicMock Auto-Attribute Trap
**What goes wrong:** MagicMock returns a new MagicMock for any unset attribute. If a test checks `config.some_attr == specific_value` and the shared fixture doesn't set `some_attr`, the test sees a MagicMock instead of the expected value and fails silently or produces wrong results.
**How to avoid:** The shared fixture must be a SUPERSET of all attributes used across consumers. Diff each class-level fixture against the shared one to identify any attributes in the class version but not in the shared version.
**Warning signs:** Tests pass but behavior changes subtly (e.g., boolean checks on MagicMock are always truthy).

### Pitfall 2: Class-Level Fixture Override Mutation
**What goes wrong:** If a class-level fixture modifies the shared fixture object (e.g., `mock_autorate_config.alpha_baseline = 0.5`), and pytest reuses the same fixture instance across classes, mutations from one class leak into another.
**How to avoid:** pytest creates a new fixture instance per test by default (function scope). The shared conftest fixtures are function-scoped, so each test gets a fresh MagicMock. This is safe. Do NOT change fixture scope to `session` or `module`.
**Warning signs:** Tests pass individually but fail when run together.

### Pitfall 3: Forgetting `self` in Class-Level Fixtures
**What goes wrong:** Class-level pytest fixtures defined with `def mock_config(self, mock_autorate_config)` require `self` as first parameter. Forgetting it causes pytest collection errors.
**How to avoid:** Always include `self` in class method fixtures.

### Pitfall 4: Router Client Default Change Breaking Tests
**What goes wrong:** Changing `get_router_client()` default from `"ssh"` to `"rest"` could break tests that depend on the old default.
**How to avoid:** Check `test_router_client.py` for tests that call `get_router_client()` without setting `router_transport` on the config mock. If any test expects SSH behavior by default, it needs updating.

## Code Examples

### Consolidation: Class-level delegation (exact match)
```python
# Before: Full duplication (45+ lines)
@pytest.fixture
def mock_config(self):
    config = MagicMock()
    config.wan_name = "TestWAN"
    config.baseline_rtt_initial = 25.0
    # ... 40+ more lines ...
    return config

# After: Delegation (1-2 lines)
@pytest.fixture
def mock_config(self, mock_autorate_config):
    return mock_autorate_config
```

### Consolidation: Class-level delegation with overrides
```python
# Before: Full duplication with alpha_baseline=0.5
@pytest.fixture
def mock_config(self):
    config = MagicMock()
    config.wan_name = "TestWAN"
    config.alpha_baseline = 0.5  # High alpha for fast updates
    # ... 35+ more lines ...
    return config

# After: Override only what differs
@pytest.fixture
def mock_config(self, mock_autorate_config):
    mock_autorate_config.alpha_baseline = 0.5  # High alpha for fast updates
    mock_autorate_config.fallback_enabled = False
    return mock_autorate_config
```

### Consolidation: Module-level alias
```python
# Before: Full 45-line fixture definition
@pytest.fixture
def mock_config():
    config = MagicMock()
    # ... full copy ...
    return config

# After: One-line alias
@pytest.fixture
def mock_config(mock_autorate_config):
    return mock_autorate_config
```

### Router client docstring fix
```python
# Before (lines 32-43):
# Configuration (in YAML):
#     router:
#       transport: "ssh"  # or "rest"
#       ...
#       verify_ssl: false

# After:
# Configuration (in YAML):
#     router:
#       transport: "rest"  # or "ssh"
#       ...
#       verify_ssl: true
```

### Router client default fix
```python
# Before (line 76):
transport = getattr(config, "router_transport", "ssh")

# After:
transport = getattr(config, "router_transport", "rest")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Full mock_config copy per file/class | Shared conftest fixtures + delegation | Phase 55 (partial) | 5 files already consolidated |
| `router_transport` default `"ssh"` | Default `"rest"` everywhere | Phase 50 (failover path only) | Non-failover path still says `"ssh"` |

## Open Questions

None. All three success criteria are well-defined and the implementation path is clear.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (via `.venv/bin/pytest`) |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `.venv/bin/pytest tests/ -x -q` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements --> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TEST-01 | Shared conftest fixtures used by all test files; no redundant full definitions | structural (fixture consolidation) | `.venv/bin/pytest tests/ -x -q` (all 2,109 tests must still pass) | N/A -- this IS the test infrastructure |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/ -x -q`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green + `grep -rn "def mock_config" tests/ | wc -l` shows reduced count

### Wave 0 Gaps
None -- existing test infrastructure covers all phase requirements. The phase IS test infrastructure work.

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection of all 11 test files containing `mock_config` references
- `tests/conftest.py` -- existing shared fixtures (lines 35-137)
- `src/wanctl/router_client.py` -- current docstring, defaults, and factory functions
- `.planning/phases/55-test-quality/55-01-PLAN.md` -- original consolidation plan (never executed for Task 2)
- `.planning/v1.10-MILESTONE-AUDIT.md` -- gap identification and cosmetic residuals

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new dependencies, purely existing codebase
- Architecture: HIGH - consolidation pattern already proven in 5 files
- Pitfalls: HIGH - common pytest fixture patterns, well-understood

**Research date:** 2026-03-09
**Valid until:** indefinite (internal codebase patterns, no external dependencies)
