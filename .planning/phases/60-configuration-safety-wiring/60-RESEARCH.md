# Phase 60: Configuration + Safety + Wiring - Research

**Researched:** 2026-03-09
**Domain:** YAML config schema validation, feature toggle wiring, startup grace period
**Confidence:** HIGH

## Summary

Phase 60 wires the WAN-aware steering feature end-to-end: YAML `wan_state:` config section with schema validation, configurable weights replacing class constants, a 30-second startup grace period, and a feature toggle that ships disabled by default. All integration points already exist from Phase 59 -- this phase adds the configuration layer, safety gates, and the `wan_override` boolean for optional WAN-solo failover.

The codebase has well-established patterns for every piece needed. `SteeringConfig._load_specific_fields()` (daemon.py:374-404) shows exactly how new config sections are loaded in dependency order. The `SCHEMA` class attribute (daemon.py:137-165) shows field spec format. `_load_confidence_config()` (daemon.py:240-291) is the nearest precedent -- a section loaded conditionally with safe defaults and cross-field validation. `validate_schema()` in config_base.py handles all type/range checking and error accumulation.

**Primary recommendation:** Follow the `_load_confidence_config()` pattern exactly: new `_load_wan_state_config()` method, called after `_load_confidence_config()` in `_load_specific_fields()`, with all fields optional and safe defaults. Grace period uses `time.monotonic()` timestamp comparison. Feature disabled by default means `wan_zone` is read but ignored in `compute_confidence()` and `update_recovery_timer()`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Raw weight numbers exposed in config (`red_weight: 25`)
- `soft_red_weight` is NOT independently configurable -- derived as `red_weight * 0.48` (matches CAKE SOFT_RED:RED ratio)
- Weights clamped to `steer_threshold - 1` by default at validation time
- Clamping produces a startup warning: "red_weight clamped to {max} (must be < steer_threshold)"
- Defaults: `red_weight: 25` -> derived `soft_red_weight: 12`
- New boolean: `wan_override: false` by default
- When `wan_override: true`: removes weight ceiling, `red_weight` >= `steer_threshold` is allowed
- Startup warning when enabled: "WAN override active -- WAN RED can trigger failover independently of CAKE signals"
- `wan_override: true` + `enabled: false` -> validation warning ("override has no effect when disabled")
- Invalid `wan_state:` section -> warn + disable WAN awareness feature (rest of steering runs normally)
- Field-level strictness: wrong type -> disable feature; out-of-range value -> clamp to default with warning
- Unknown keys inside `wan_state:` -> warn about unrecognized keys (typo detection)
- Validation uses existing `validate_schema()` framework from `config_base.py`
- When `wan_state.enabled: false`: read WAN zone from state file but don't use in scoring or recovery gate
- Zero additional I/O cost -- zone is in same `safe_json_load_file()` call already performed for baseline RTT
- Enables health endpoint (Phase 61) to show "WAN zone: available but disabled"
- Single startup log line: "WAN awareness: disabled (enable via wan_state.enabled)"
- 30 seconds after daemon start, WAN signal is read but not used in scoring or recovery gate
- Grace period restarts on every daemon restart (not persistent across restarts)
- `enabled: false` -> "WAN awareness: disabled (enable via wan_state.enabled)"
- `enabled: true` -> "WAN awareness: enabled (grace period: 30s, red_weight: 25, wan_override: false)"
- `enabled: true` but no autorate state file -> one-time warning: "WAN awareness enabled but autorate state file not found"
- User wants `wan_override` as explicit boolean rather than allowing weight values to implicitly unlock solo-trigger behavior

### Claude's Discretion
- Config key naming within `wan_state:` section (e.g., `red_weight` vs `wan_red_weight`)
- How grace period timer is implemented (timestamp comparison, cycle counter, etc.)
- Where in the code the enabled/grace checks go (daemon level vs confidence module)
- How derived `soft_red_weight` rounding is handled
- Schema field spec ordering and validation message wording
- Test structure and organization

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CONF-01 | YAML `wan_state:` section with `enabled`, weight values, staleness threshold, grace period | SteeringConfig._load_specific_fields() pattern, SCHEMA class attribute format, validate_schema() framework |
| CONF-02 | Config validated via existing schema validation framework | validate_schema() in config_base.py:155-208, field spec dict format with path/type/required/min/max/default |
| SAFE-03 | Startup grace period ignores WAN signal for first 30s after daemon start | time.monotonic() timestamp in SteeringDaemon.__init__(), checked before wan_zone contribution in compute_confidence() |
| SAFE-04 | Feature ships with `wan_state.enabled: false` as default -- no behavioral change on upgrade | Conditional loading pattern from _load_confidence_config(), disabled-mode read-but-don't-use pattern |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyYAML | >=6.0.1 | YAML config parsing | Already in use, loaded via BaseConfig.__init__() |
| time (stdlib) | 3.12 | monotonic() for grace period | Already used for staleness checks |

### Supporting
No new dependencies required. All work uses existing codebase patterns.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| time.monotonic() for grace | Cycle counter | monotonic() is simpler, resilient to cycle timing drift |
| Custom validation | validate_schema() | validate_schema() already handles type/range/required -- use it |

**Installation:**
```bash
# No new packages needed
```

## Architecture Patterns

### Recommended Code Organization
```
src/wanctl/
  config_base.py              # No changes (validate_schema reused as-is)
  steering/
    daemon.py                 # Add: _load_wan_state_config(), SCHEMA entries, grace period init
    steering_confidence.py    # Modify: ConfidenceWeights -> config-driven, add enabled/grace gate
configs/
  steering.yaml               # Add: wan_state: section
  examples/steering.yaml.example  # Add: wan_state: section (commented)
tests/
  test_steering_daemon.py     # Add: TestWanStateConfig class
  test_steering_confidence.py # Add: tests for config-driven weights, enabled/grace gate
```

### Pattern 1: Config Section Loading (Nearest Precedent)
**What:** `_load_confidence_config()` at daemon.py:240-291 -- loads optional section, sets attribute to None when disabled, builds structured dict.
**When to use:** Any new YAML section that is optional with safe defaults.
**Example:**
```python
# Source: daemon.py:240-291 (existing pattern)
def _load_confidence_config(self) -> None:
    if not self.use_confidence_scoring:
        self.confidence_config = None
        return
    confidence = self.data.get("confidence", {})
    # Validate cross-field constraints
    # Build config dict
    self.confidence_config = { ... }
```

### Pattern 2: Schema Field Spec Format
**What:** SCHEMA class attribute lists field specs as dicts with path/type/required/min/max/default.
**When to use:** Declarative config validation.
**Example:**
```python
# Source: daemon.py:137-165 (existing pattern)
SCHEMA = [
    {"path": "topology.primary_wan", "type": str, "required": True},
    {"path": "measurement.interval_seconds", "type": (int, float), "required": True, "min": 0.01, "max": 60},
    {"path": "state.history_size", "type": int, "required": True, "min": 1, "max": 3000},
]
```

### Pattern 3: Feature Toggle Init
**What:** `SteeringDaemon.__init__()` at daemon.py:719-729 -- conditional initialization based on config flag.
**When to use:** Optional features that may or may not be active.
**Example:**
```python
# Source: daemon.py:719-729 (existing pattern)
self.confidence_controller: ConfidenceController | None = None
if self.config.use_confidence_scoring and self.config.confidence_config:
    self.confidence_controller = ConfidenceController(...)
```

### Pattern 4: Graceful Degradation on Config Error
**What:** Invalid section disables feature, does not crash daemon.
**When to use:** Optional config sections that should not prevent startup.
**Difference from confidence:** Confidence config raises on bad values. wan_state uses warn+disable approach per user decision.

### Anti-Patterns to Avoid
- **Adding wan_state fields to SCHEMA class attribute for mandatory validation:** The user decided invalid wan_state should warn+disable, not crash. SCHEMA validation raises ConfigValidationError on failure. Instead, validate wan_state fields manually in _load_wan_state_config() with try/except.
- **Modifying ConfidenceWeights class constants directly:** Replace them with instance attributes passed through from config, keeping class constants as fallback defaults.
- **Checking enabled/grace in update_state_machine():** The check belongs where WAN zone is consumed -- in compute_confidence() and update_recovery_timer(). Keep the gate as close to the consumer as possible.
- **Persistent grace period state:** Grace period restarts on daemon restart -- do not persist to state file.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Type/range validation | Custom type checks | validate_field() from config_base.py | Already handles int/float coercion, range bounds, choices |
| Nested config access | Manual dict traversal | _get_nested() from config_base.py | Handles missing keys with defaults |
| Config error accumulation | Single-error-stop | validate_schema() collects all errors | Better UX (all errors at once) |

**Key insight:** The config_base.py validation framework is complete. The only custom logic needed is: (1) wan_state section-level error -> disable feature, (2) clamping out-of-range weights with warning, (3) derived soft_red_weight computation, (4) wan_override cross-field checks.

## Common Pitfalls

### Pitfall 1: SCHEMA Validation Crashes Daemon on Invalid wan_state
**What goes wrong:** Adding wan_state fields to the SCHEMA class attribute means validate_schema() raises ConfigValidationError on invalid values, crashing the daemon on startup.
**Why it happens:** The existing pattern (confidence config) validates manually because it is optional. wan_state should follow the same approach.
**How to avoid:** Do NOT add wan_state fields to SCHEMA. Validate in _load_wan_state_config() with try/except, logging warnings and setting wan_state_config=None on failure.
**Warning signs:** Tests show daemon crashing on invalid wan_state YAML.

### Pitfall 2: ConfidenceWeights Constants Not Overridden Properly
**What goes wrong:** Changing class constants on ConfidenceWeights affects all instances and tests. Test isolation breaks.
**Why it happens:** Class-level constants are shared state.
**How to avoid:** Pass weight values as parameters to compute_confidence() or through the ConfidenceController, not by mutating class attributes. Keep class constants as documentation/defaults.
**Warning signs:** Test failures when run in different order.

### Pitfall 3: Grace Period Uses time.time() Instead of time.monotonic()
**What goes wrong:** System clock adjustments (NTP jumps) cause grace period to expire early or never expire.
**Why it happens:** time.time() is wall clock, susceptible to NTP corrections.
**How to avoid:** Use time.monotonic() which is immune to clock adjustments. Already used throughout codebase for staleness checks.
**Warning signs:** Grace period behaving inconsistently in production.

### Pitfall 4: Clamping Modifies Config Dict In-Place
**What goes wrong:** If _load_wan_state_config() clamps red_weight in self.data, the raw YAML dict is mutated. Health endpoint later reports clamped value as "configured" value.
**Why it happens:** Python dicts are mutable references.
**How to avoid:** Store clamped values in wan_state_config dict (derived config), keep self.data untouched. Log warning at clamping time.
**Warning signs:** Health endpoint shows different value than YAML file.

### Pitfall 5: wan_override Cross-Field Validation Ordering
**What goes wrong:** Checking `wan_override: true` + `enabled: false` before validating individual fields means validation may warn about override even when fields are invalid.
**Why it happens:** Cross-field checks depend on individual field validity.
**How to avoid:** Validate individual fields first (types, ranges). If any fail, disable feature and skip cross-field checks. Only check cross-field constraints if all individual fields are valid.
**Warning signs:** Confusing warning messages about override when feature is disabled due to invalid config.

### Pitfall 6: soft_red_weight Rounding Produces Non-Integer
**What goes wrong:** `red_weight * 0.48` with red_weight=25 gives 12.0, but red_weight=15 gives 7.2 (not an integer).
**Why it happens:** Float multiplication does not guarantee integer results.
**How to avoid:** Use `int(red_weight * 0.48)` (truncate) or `round(red_weight * 0.48)`. Document the rounding strategy. Truncation is conservative (lower weight = safer).
**Warning signs:** Float weight values causing unexpected scoring behavior.

## Code Examples

Verified patterns from existing codebase:

### Config Section Loading Pattern
```python
# Source: daemon.py:240-291 (_load_confidence_config)
# Adapted for wan_state section
def _load_wan_state_config(self) -> None:
    """Load WAN state awareness configuration.

    Invalid section -> warn + disable feature.
    """
    wan_state = self.data.get("wan_state", {})

    # Default: disabled
    enabled = wan_state.get("enabled", False)
    if not isinstance(enabled, bool):
        logger.warning(f"wan_state.enabled: expected bool, got {type(enabled).__name__}; disabling WAN awareness")
        self.wan_state_config = None
        return

    # Build config with defaults
    try:
        red_weight = wan_state.get("red_weight", 25)
        # type check, range check, clamping...
        self.wan_state_config = {
            "enabled": enabled,
            "red_weight": red_weight,
            "soft_red_weight": int(red_weight * 0.48),
            "staleness_threshold_sec": ...,
            "grace_period_sec": ...,
            "wan_override": ...,
        }
    except Exception as e:
        logger.warning(f"Invalid wan_state config: {e}; disabling WAN awareness")
        self.wan_state_config = None
```

### Schema Validation Field Spec
```python
# Source: config_base.py:119-134 (STORAGE_SCHEMA)
# Pattern for optional fields with defaults
WAN_STATE_FIELDS = [
    {"path": "wan_state.enabled", "type": bool, "required": False, "default": False},
    {"path": "wan_state.red_weight", "type": int, "required": False, "default": 25, "min": 1, "max": 100},
    {"path": "wan_state.staleness_threshold_sec", "type": (int, float), "required": False, "default": 5, "min": 1, "max": 60},
    {"path": "wan_state.grace_period_sec", "type": (int, float), "required": False, "default": 30, "min": 0, "max": 300},
    {"path": "wan_state.wan_override", "type": bool, "required": False, "default": False},
]
```

### Grace Period Timestamp Pattern
```python
# Source: time.monotonic() used in daemon.py:637 (_is_wan_zone_stale)
# Adapted for grace period
class SteeringDaemon:
    def __init__(self, ...):
        ...
        # Grace period: WAN signal read but not used for first N seconds
        self._startup_time = time.monotonic()
        self._grace_period_sec = (
            config.wan_state_config["grace_period_sec"]
            if config.wan_state_config
            else 30.0
        )

    def _is_wan_grace_period_active(self) -> bool:
        """Check if startup grace period is still active."""
        return (time.monotonic() - self._startup_time) < self._grace_period_sec
```

### Feature Toggle Gate Pattern
```python
# Source: daemon.py:1172 (confidence controller check)
# Adapted for WAN awareness in compute_confidence
# Gate: skip WAN weight if disabled or grace period active
if signals.wan_zone is not None and wan_state_enabled and not grace_active:
    if signals.wan_zone == "RED":
        score += weights.wan_red
        contributors.append("WAN_RED")
    elif signals.wan_zone == "SOFT_RED":
        score += weights.wan_soft_red
        contributors.append("WAN_SOFT_RED")
```

### Unknown Key Detection Pattern
```python
# No direct precedent in codebase -- simple set difference
known_keys = {"enabled", "red_weight", "staleness_threshold_sec", "grace_period_sec", "wan_override"}
actual_keys = set(wan_state.keys())
unknown = actual_keys - known_keys
if unknown:
    logger.warning(f"wan_state: unrecognized keys {unknown} (possible typo)")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ConfidenceWeights as class constants | Config-driven weights passed through | Phase 60 (this phase) | Weights tunable via YAML |
| STALE_WAN_ZONE_THRESHOLD_SECONDS=5 hardcoded | Configurable via wan_state.staleness_threshold_sec | Phase 60 (this phase) | Production-tunable staleness |
| WAN zone always contributes to scoring | Gated by enabled flag + grace period | Phase 60 (this phase) | Safe staged rollout |

**Deprecated/outdated:**
- ConfidenceWeights.WAN_RED=25 and WAN_SOFT_RED=12 as fixed class constants will become defaults only. Config values take precedence.

## Open Questions

1. **Where exactly to put the enabled/grace gate**
   - What we know: WAN zone is consumed in two places -- `compute_confidence()` (lines 148-155) and `update_recovery_timer()` (line 336). Both are in steering_confidence.py.
   - What's unclear: Gate in SteeringDaemon before building ConfidenceSignals (set wan_zone=None when disabled/grace)? Or gate inside compute_confidence()/update_recovery_timer() with new parameters?
   - Recommendation: Gate in SteeringDaemon is simpler -- when disabled or grace active, set `self._wan_zone = None` equivalent before passing to ConfidenceSignals. This way compute_confidence() and update_recovery_timer() need no changes (wan_zone=None already means "skip WAN weight" per SAFE-02). This avoids modifying the scoring functions' signatures.

2. **How to pass config-driven weights to compute_confidence()**
   - What we know: compute_confidence() currently reads from ConfidenceWeights class constants. Changing class constants globally affects all tests.
   - What's unclear: Best approach to inject config values.
   - Recommendation: Add optional `wan_red_weight` and `wan_soft_red_weight` parameters to compute_confidence() with defaults from ConfidenceWeights. This preserves backward compatibility and is the minimal change.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `.venv/bin/pytest tests/test_steering_daemon.py tests/test_steering_confidence.py -x -q` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONF-01 | wan_state: section loads with all fields + defaults | unit | `.venv/bin/pytest tests/test_steering_daemon.py -k "wan_state" -x` | Wave 0 |
| CONF-01 | wan_state: section in production YAML config | unit | `.venv/bin/pytest tests/test_steering_daemon.py -k "wan_state_defaults" -x` | Wave 0 |
| CONF-02 | Invalid types/ranges detected by validation | unit | `.venv/bin/pytest tests/test_steering_daemon.py -k "wan_state_invalid" -x` | Wave 0 |
| CONF-02 | Unknown keys produce warning | unit | `.venv/bin/pytest tests/test_steering_daemon.py -k "wan_state_unknown" -x` | Wave 0 |
| CONF-02 | Weight clamping with warning | unit | `.venv/bin/pytest tests/test_steering_daemon.py -k "wan_state_clamp" -x` | Wave 0 |
| CONF-02 | wan_override cross-field checks | unit | `.venv/bin/pytest tests/test_steering_daemon.py -k "wan_override" -x` | Wave 0 |
| SAFE-03 | Grace period ignores WAN signal for 30s | unit | `.venv/bin/pytest tests/test_steering_confidence.py -k "grace_period" -x` | Wave 0 |
| SAFE-03 | Grace period expires and WAN signal used | unit | `.venv/bin/pytest tests/test_steering_confidence.py -k "grace_expired" -x` | Wave 0 |
| SAFE-04 | Feature disabled by default | unit | `.venv/bin/pytest tests/test_steering_daemon.py -k "wan_state_disabled_default" -x` | Wave 0 |
| SAFE-04 | Disabled mode reads zone but does not use | unit | `.venv/bin/pytest tests/test_steering_confidence.py -k "wan_disabled" -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_steering_daemon.py tests/test_steering_confidence.py -x -q`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_steering_daemon.py::TestWanStateConfig` -- covers CONF-01, CONF-02
- [ ] `tests/test_steering_confidence.py::TestWanStateGating` -- covers SAFE-03, SAFE-04
- [ ] No framework install needed -- pytest already configured

## Sources

### Primary (HIGH confidence)
- `src/wanctl/config_base.py` -- validate_schema(), validate_field(), BaseConfig, SCHEMA pattern
- `src/wanctl/steering/daemon.py` -- SteeringConfig, _load_specific_fields(), _load_confidence_config(), BaselineLoader, STALE_WAN_ZONE_THRESHOLD_SECONDS, SteeringDaemon.__init__()
- `src/wanctl/steering/steering_confidence.py` -- ConfidenceWeights, ConfidenceSignals, compute_confidence(), update_recovery_timer()
- `configs/steering.yaml` -- production config structure
- `configs/examples/steering.yaml.example` -- example config with documentation
- `tests/test_steering_daemon.py` -- TestSteeringConfig, valid_config_dict fixture
- `tests/test_steering_confidence.py` -- TestComputeConfidence, wan_zone test patterns

### Secondary (MEDIUM confidence)
None needed -- all findings from direct codebase inspection.

### Tertiary (LOW confidence)
None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all patterns exist in codebase
- Architecture: HIGH -- direct precedent in _load_confidence_config() pattern
- Pitfalls: HIGH -- identified from actual codebase patterns and constraints in CONTEXT.md

**Research date:** 2026-03-09
**Valid until:** 2026-04-09 (stable codebase, no external dependencies)
