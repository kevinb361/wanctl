# Phase 82: Steering Config + Output Modes - Research

**Researched:** 2026-03-12
**Domain:** Extending check_config CLI with steering validation + auto-detection + JSON output
**Confidence:** HIGH

## Summary

Phase 82 extends the existing `wanctl-check-config` tool (786 lines, Phase 81) with three capabilities: (1) steering config validation with `KNOWN_STEERING_PATHS` and steering-specific cross-field checks, (2) auto-detection of config type from YAML contents (`topology` key = steering, `continuous_monitoring` key = autorate), and (3) `--json` output mode for CI/scripting. All required infrastructure already exists in check_config.py -- Severity enum, CheckResult dataclass, category validators returning `list[CheckResult]`, format_results(), create_parser(), main(). The work is additive: new validator functions for steering, a detection function, a JSON formatter, and refactoring main() to dispatch based on detected/specified type.

The critical finding is that steering configs have ~65 valid paths across both production and example configs (vs ~57 for autorate). Many paths are loaded imperatively by SteeringConfig._load_specific_fields() and not declared in SCHEMA (10 fields). The SCHEMA only covers topology (3), mangle_rule (1), measurement (3), state (2), and thresholds (1 dict) = 10 fields total. A comprehensive `KNOWN_STEERING_PATHS` set must be constructed covering all valid paths to avoid false-positive unknown-key warnings. Production backward compatibility is the primary constraint -- the tool must pass cleanly on `configs/steering.yaml`.

Cross-config validation (CVAL-09) requires reading a second YAML file (`topology.primary_wan_config`), parsing it, and checking that its `wan_name` matches `topology.primary_wan`. File existence is WARN (dev machine may not have the other config); wan_name mismatch is ERROR. This is the highest-value check in Phase 82 since wan_name mismatch is the most common steering misconfiguration.

**Primary recommendation:** Add steering validators in check_config.py following the existing pattern (functions returning `list[CheckResult]`). Add `detect_config_type()` as a pure function. Add `format_results_json()` parallel to `format_results()`. Refactor `main()` to dispatch validators based on detected/specified type.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Auto-detection strategy: `topology` key -> steering, `continuous_monitoring` key -> autorate
- Both present -> error (ambiguous config); Neither present -> error with suggestion to use `--type autorate|steering`
- `--type` flag overrides auto-detection entirely when provided (authoritative, not fallback)
- Detection result shown silently in summary line: `Result: PASS (autorate config)` -- no separate "Detected:" banner
- Steering cross-config checks get own category section: `=== Cross-config Checks ===`
- `topology.primary_wan_config` file existence is WARN (not ERROR)
- If referenced config exists, parse it and verify `wan_name` matches `topology.primary_wan` -- ERROR on mismatch
- Cross-config depth: file existence + wan_name match only -- do NOT run full autorate validation on the referenced file
- Steering-specific cross-field checks: confidence threshold ordering (recovery_threshold < steer_threshold), measurement.interval_seconds range, state.history_size range
- `--json` flag replaces text output entirely -- only JSON goes to stdout
- JSON structure: `config_type`, `result`, `errors` count, `warnings` count, `categories` object
- Categories object: keys are category names, values are arrays of check result objects
- Each check result: `field`, `severity` (pass/warn/error), `message`, `suggestion` (present when available, omitted when null)
- Include ALL results (pass, warn, error) in JSON -- CI scripts filter with jq
- Exit codes unchanged when --json is used (0=pass, 1=errors, 2=warnings-only)
- `--json` and `--quiet` are independent: --json always includes all results regardless of -q
- Must never reject currently-working production configs -- backward compat is primary constraint
- Zero new dependencies -- reuse json stdlib, existing patterns from Phase 81

### Claude's Discretion
- Internal refactoring of check_config.py to support dual config types (validator registry, dispatch pattern, etc.)
- KNOWN_STEERING_PATHS set construction (analogous to KNOWN_AUTORATE_PATHS)
- Steering deprecated parameter detection (mode.cake_aware, legacy cake_state_sources/cake_queues keys)
- JSON serialization approach (json.dumps vs custom encoder)
- How to load SteeringConfig.SCHEMA without triggering daemon side effects

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CVAL-02 | Operator can validate a steering config file offline via `wanctl-check-config` | SteeringConfig.SCHEMA (10 fields) + comprehensive KNOWN_STEERING_PATHS (~65 paths) + steering cross-field validators |
| CVAL-03 | Tool auto-detects config type (autorate vs steering) from file contents | Pure function checking `topology` and `continuous_monitoring` keys; `--type` override |
| CVAL-09 | Steering cross-config validation verifies topology.primary_wan_config path exists and wan_name matches | New `check_cross_config()` function reads referenced YAML, compares wan_name vs topology.primary_wan |
| CVAL-10 | JSON output mode (`--json`) for scripting and CI integration | `format_results_json()` parallel to `format_results()`, json.dumps with indent=2 |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| json | stdlib | JSON output serialization | Already used extensively in health_check.py, history.py |
| argparse | stdlib | CLI argument parsing (extend existing parser) | Already in check_config.py |
| pathlib | stdlib | File existence checks for cross-config validation | Already used throughout |
| yaml | 6.0.1+ | YAML parsing for cross-config file loading | Already a dependency |

### Supporting (all existing project code, no new deps)
| Module | Purpose | When to Use |
|--------|---------|-------------|
| `wanctl.check_config` | Existing Severity, CheckResult, validators, format_results, create_parser | Extend all of these |
| `wanctl.steering.daemon.SteeringConfig` | SCHEMA class attribute (10 fields) | Schema validation for steering configs |
| `wanctl.config_base` | BaseConfig.BASE_SCHEMA, validate_field, _get_nested | Shared schema validation |
| `wanctl.config_validation_utils` | validate_alpha (EWMA bounds checking) | Steering threshold validation |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| json.dumps | Custom JSON builder | json.dumps is stdlib, handles all types, indent=2 matches health_check.py pattern |
| Type dispatch in main() | Separate CLI entry points | Single tool is user decision; dispatch inside main() keeps CLI simple |
| Importing SteeringConfig.SCHEMA | Hardcoded steering schema list | Import gives single source of truth; class attribute access has no side effects |

**Installation:**
```bash
# No new packages needed. Zero new dependencies.
```

## Architecture Patterns

### Recommended Approach
Extend `src/wanctl/check_config.py` in-place. No new files needed.

```
src/wanctl/
  check_config.py        # MODIFY: add steering validators, auto-detect, JSON output
  steering/daemon.py     # READ ONLY: import SteeringConfig.SCHEMA
```

### Pattern 1: Config Type Detection
**What:** Pure function that examines top-level keys to determine config type.
**When to use:** Before running validators in main().
**Example:**
```python
def detect_config_type(data: dict) -> str:
    """Detect config type from YAML contents.

    Returns:
        "autorate" or "steering"

    Raises:
        SystemExit: If detection is ambiguous or fails.
    """
    has_topology = "topology" in data
    has_continuous = "continuous_monitoring" in data

    if has_topology and has_continuous:
        # Ambiguous -- both markers present
        print("Error: config contains both 'topology' and 'continuous_monitoring' -- "
              "ambiguous config type. Use --type autorate|steering", file=sys.stderr)
        sys.exit(1)
    elif has_topology:
        return "steering"
    elif has_continuous:
        return "autorate"
    else:
        print("Error: could not determine config type -- "
              "no 'topology' or 'continuous_monitoring' key found. "
              "Use --type autorate|steering", file=sys.stderr)
        sys.exit(1)
```

**Why this works:** Every steering config requires `topology` (in SCHEMA as required). Every autorate config requires `continuous_monitoring` (in SCHEMA as required). No overlap -- these are config-type-specific sections.

### Pattern 2: Validator Dispatch
**What:** main() selects which validators to run based on config type.
**When to use:** After detection/type override, before running validators.
**Example:**
```python
def _run_autorate_validators(data: dict) -> list[CheckResult]:
    """Run all autorate-specific validators."""
    results: list[CheckResult] = []
    results.extend(validate_schema_fields(data))  # Uses Config.SCHEMA
    results.extend(validate_cross_fields(data))
    results.extend(check_unknown_keys(data))       # Uses KNOWN_AUTORATE_PATHS
    results.extend(check_paths(data))
    results.extend(check_env_vars(data))
    results.extend(check_deprecated_params(data))
    return results

def _run_steering_validators(data: dict) -> list[CheckResult]:
    """Run all steering-specific validators."""
    results: list[CheckResult] = []
    results.extend(validate_steering_schema_fields(data))  # Uses SteeringConfig.SCHEMA
    results.extend(validate_steering_cross_fields(data))
    results.extend(check_steering_unknown_keys(data))       # Uses KNOWN_STEERING_PATHS
    results.extend(check_paths(data))                        # Reuse -- same path checks
    results.extend(check_env_vars(data))                     # Reuse -- same env var checks
    results.extend(check_steering_deprecated_params(data))
    results.extend(check_steering_cross_config(data))        # NEW: cross-config checks
    return results
```

**Key insight:** `check_paths()` and `check_env_vars()` are config-type-agnostic -- they walk the dict generically. Schema validation, cross-field, unknown keys, and deprecated params need type-specific implementations.

### Pattern 3: Steering Schema Validation
**What:** Parallel to `validate_schema_fields()` but using `SteeringConfig.SCHEMA`.
**When to use:** Schema validation category for steering configs.
**Example:**
```python
from wanctl.steering.daemon import SteeringConfig

def validate_steering_schema_fields(data: dict) -> list[CheckResult]:
    """Validate steering schema fields from BASE_SCHEMA + SteeringConfig.SCHEMA."""
    results: list[CheckResult] = []
    combined_schema = BaseConfig.BASE_SCHEMA + SteeringConfig.SCHEMA
    for field_spec in combined_schema:
        path = field_spec["path"]
        try:
            validate_field(
                data, path,
                field_spec.get("type", str),
                field_spec.get("required", True),
                field_spec.get("min"),
                field_spec.get("max"),
                field_spec.get("choices"),
                field_spec.get("default"),
            )
            results.append(CheckResult("Schema Validation", path, Severity.PASS, f"{path}: valid"))
        except ConfigValidationError as e:
            results.append(CheckResult("Schema Validation", path, Severity.ERROR, str(e)))
    return results
```

**Import safety:** `from wanctl.steering.daemon import SteeringConfig` imports the class but does NOT instantiate it. The module-level code in steering/daemon.py sets constants and imports dependencies, but those are all lightweight. The SCHEMA is a class attribute (list of dicts) -- no side effects from accessing it.

### Pattern 4: Cross-Config Validation (CVAL-09)
**What:** Reads the file referenced by `topology.primary_wan_config`, checks existence, and verifies wan_name match.
**When to use:** Steering-only, in its own `=== Cross-config Checks ===` category.
**Example:**
```python
def check_steering_cross_config(data: dict) -> list[CheckResult]:
    """Validate cross-config references in steering config."""
    results: list[CheckResult] = []
    primary_wan_config = _get_nested(data, "topology.primary_wan_config")
    primary_wan = _get_nested(data, "topology.primary_wan")

    if not primary_wan_config or not isinstance(primary_wan_config, str):
        return results  # Schema validation already catches missing required field

    config_path = Path(primary_wan_config)
    if not config_path.exists():
        results.append(CheckResult(
            "Cross-config Checks",
            "topology.primary_wan_config",
            Severity.WARN,
            f"topology.primary_wan_config: file not found ({primary_wan_config})",
            suggestion="Verify path is correct or run on the deployment machine",
        ))
        return results

    # File exists -- parse and check wan_name
    results.append(CheckResult(
        "Cross-config Checks",
        "topology.primary_wan_config",
        Severity.PASS,
        f"topology.primary_wan_config: file exists ({primary_wan_config})",
    ))

    try:
        with open(config_path) as f:
            ref_data = yaml.safe_load(f)
        if not isinstance(ref_data, dict):
            results.append(CheckResult(
                "Cross-config Checks",
                "topology.primary_wan_config",
                Severity.WARN,
                f"topology.primary_wan_config: referenced file is not a valid YAML mapping",
            ))
            return results

        ref_wan_name = ref_data.get("wan_name")
        if ref_wan_name is None:
            results.append(CheckResult(
                "Cross-config Checks",
                "wan_name match",
                Severity.WARN,
                f"Referenced config ({primary_wan_config}) has no wan_name field",
            ))
        elif ref_wan_name == primary_wan:
            results.append(CheckResult(
                "Cross-config Checks",
                "wan_name match",
                Severity.PASS,
                f"wan_name match: topology.primary_wan '{primary_wan}' matches "
                f"referenced config wan_name '{ref_wan_name}'",
            ))
        else:
            results.append(CheckResult(
                "Cross-config Checks",
                "wan_name match",
                Severity.ERROR,
                f"wan_name mismatch: topology.primary_wan is '{primary_wan}' but "
                f"referenced config ({primary_wan_config}) has wan_name '{ref_wan_name}'",
                suggestion=f"Change topology.primary_wan to '{ref_wan_name}' "
                           f"or update the referenced config",
            ))
    except yaml.YAMLError:
        results.append(CheckResult(
            "Cross-config Checks",
            "topology.primary_wan_config",
            Severity.WARN,
            f"topology.primary_wan_config: could not parse referenced file ({primary_wan_config})",
        ))

    return results
```

### Pattern 5: JSON Output
**What:** Serialize `list[CheckResult]` to structured JSON.
**When to use:** When `--json` flag is provided.
**Example:**
```python
import json

def format_results_json(results: list[CheckResult], config_type: str) -> str:
    """Format validation results as JSON for CI/scripting."""
    error_count = sum(1 for r in results if r.severity == Severity.ERROR)
    warn_count = sum(1 for r in results if r.severity == Severity.WARN)

    if error_count > 0:
        result_word = "FAIL"
    elif warn_count > 0:
        result_word = "WARN"
    else:
        result_word = "PASS"

    # Group by category
    categories: dict[str, list[dict]] = {}
    for r in results:
        entry: dict[str, str] = {
            "field": r.field,
            "severity": r.severity.value,
            "message": r.message,
        }
        if r.suggestion is not None:
            entry["suggestion"] = r.suggestion
        categories.setdefault(r.category, []).append(entry)

    output = {
        "config_type": config_type,
        "result": result_word,
        "errors": error_count,
        "warnings": warn_count,
        "categories": categories,
    }

    return json.dumps(output, indent=2)
```

**Pipe-friendly:** `wanctl-check-config --json steering.yaml | jq .result` outputs `"PASS"`.

### Pattern 6: Summary Line with Config Type
**What:** Include detected config type in the summary line.
**When to use:** Text output summary (both autorate and steering).
**Example:**
```
Result: PASS (steering config)
Result: FAIL (autorate config) (2 errors, 1 warning)
```
This replaces the current summary which has no config type indicator.

### Anti-Patterns to Avoid
- **Instantiating SteeringConfig:** Only access `SteeringConfig.SCHEMA` class attribute. Never call `SteeringConfig(path)` -- it triggers full daemon initialization.
- **Running autorate validation on the referenced config:** Cross-config depth is "file existence + wan_name match only." Do NOT recursively validate.
- **Separate CLI entry point:** The user decision is one tool (`wanctl-check-config`) that auto-detects. Do NOT add `wanctl-check-steering-config`.
- **JSON and text mixed output:** When `--json` is used, ONLY JSON goes to stdout. No text headers, no summary line -- just the JSON object.
- **Raising SystemExit from detect function directly:** Better to return a result or raise a custom exception that main() catches, so tests can exercise detection without sys.exit.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Steering schema validation | Custom field checks | `validate_field()` + `SteeringConfig.SCHEMA` | Same pattern as autorate, single source of truth |
| EWMA alpha bounds | Custom range check | `validate_alpha()` from config_validation_utils | Already handles clamping and logging |
| YAML parsing of referenced file | Custom parser | `yaml.safe_load()` | Already a dependency, handles all edge cases |
| JSON serialization | Custom string building | `json.dumps(indent=2)` | Matches existing patterns in health_check.py, history.py |
| Config path walking | New traversal | `_walk_leaf_paths()`, `_walk_string_values()` | Already exist in check_config.py, work for any dict |
| Fuzzy matching for unknown keys | New algorithm | `difflib.get_close_matches()` | Already used for autorate unknown keys |

**Key insight:** ~80% of the steering validation reuses existing check_config.py infrastructure. The genuinely new work is: (1) KNOWN_STEERING_PATHS set, (2) steering-specific cross-field checks, (3) cross-config validator, (4) detect_config_type, (5) format_results_json, (6) CLI args (--type, --json).

## Common Pitfalls

### Pitfall 1: Incomplete KNOWN_STEERING_PATHS
**What goes wrong:** Running `wanctl-check-config configs/steering.yaml` reports false warnings for valid keys like `capacity_protection`, `cake_state_sources`, `bad_threshold_ms`, `mode.cake_aware`.
**Why it happens:** SteeringConfig.SCHEMA only declares 10 fields. The remaining ~55 paths are loaded imperatively or exist as optional/legacy/future config keys.
**How to avoid:** Build KNOWN_STEERING_PATHS from three sources: (1) SCHEMA paths, (2) all imperatively loaded paths from _load_specific_fields methods, (3) legacy/deprecated paths that production configs may still contain. Validate against `configs/steering.yaml` and `configs/examples/steering.yaml.example`.
**Warning signs:** Any production steering config showing "Unknown config key" warnings for legitimate keys.

### Pitfall 2: Steering Import Side Effects
**What goes wrong:** `from wanctl.steering.daemon import SteeringConfig` triggers slow imports or unexpected behavior in tests.
**Why it happens:** steering/daemon.py imports many modules at the top (alert_engine, router_client, systemd_utils, etc.) which import their own dependencies.
**How to avoid:** This is acceptable overhead -- the imports don't trigger side effects (no module-level code that contacts routers or writes files). The SCHEMA is a class attribute, not an instance attribute. For tests that don't want this overhead, the SCHEMA can be copied or mocked. But for the production tool, the import is fine (check_config.py is a CLI run once, not a hot path).
**Warning signs:** check_config.py import taking > 1s. If this happens, extract SCHEMA to a separate constants module.

### Pitfall 3: detect_config_type raising SystemExit in Tests
**What goes wrong:** Tests calling `detect_config_type()` with ambiguous data get SystemExit instead of testable behavior.
**Why it happens:** If detection errors call `sys.exit()` directly.
**How to avoid:** Return a result tuple or raise a ValueError. Let main() handle user-facing error output and sys.exit. Tests can then assert on exceptions.
**Warning signs:** Tests needing `pytest.raises(SystemExit)` for detection logic.

### Pitfall 4: JSON Output Includes ANSI Codes
**What goes wrong:** JSON output contains embedded ANSI color escape codes in message strings.
**Why it happens:** If the same CheckResult objects go through color formatting before JSON serialization.
**How to avoid:** JSON output path must bypass color formatting entirely. format_results_json() reads raw CheckResult.message (which never contains ANSI codes -- color is only applied in format_results()).
**Warning signs:** JSON message fields containing `\033[` sequences.

### Pitfall 5: Cross-Config Check Crashes on Invalid Referenced File
**What goes wrong:** `wanctl-check-config steering.yaml` crashes with unhandled exception when `topology.primary_wan_config` points to a non-YAML file, a binary file, or a file with permissions issues.
**Why it happens:** yaml.safe_load() can raise unexpected exceptions (UnicodeDecodeError, PermissionError) beyond just YAMLError.
**How to avoid:** Wrap the entire cross-config check in try/except with broad error handling. Any failure to read/parse the referenced file should be WARN, not a crash.
**Warning signs:** Tool crash when referenced config path is `/dev/null`, a binary file, or a file without read permissions.

### Pitfall 6: Missing alerting.rules.* Dynamic Key Exclusion for Steering
**What goes wrong:** Steering configs with alerting rules trigger false "unknown key" warnings for rule-specific sub-keys.
**Why it happens:** The autorate validator already excludes `alerting.rules.*` sub-keys. The steering validator needs the same exclusion.
**How to avoid:** Both autorate and steering unknown-key checkers must skip paths starting with `alerting.rules.`.
**Warning signs:** Steering configs with alerting enabled showing unknown key warnings for rule names.

## Code Examples

### Comprehensive KNOWN_STEERING_PATHS
```python
# All valid steering config paths
# Sources: BASE_SCHEMA + SteeringConfig.SCHEMA + imperative loads + legacy/optional keys
# Verified against: configs/steering.yaml, configs/examples/steering.yaml.example
KNOWN_STEERING_PATHS: set[str] = {
    # From BASE_SCHEMA
    "wan_name",
    "router", "router.host", "router.user", "router.ssh_key",
    "logging", "logging.main_log", "logging.debug_log",
    "logging.max_bytes", "logging.backup_count",
    "lock_file", "lock_timeout",
    # From SteeringConfig.SCHEMA
    "topology", "topology.primary_wan", "topology.primary_wan_config", "topology.alternate_wan",
    "mangle_rule", "mangle_rule.comment",
    "measurement", "measurement.interval_seconds", "measurement.ping_host", "measurement.ping_count",
    "state", "state.file", "state.history_size",
    "thresholds",
    # Thresholds -- imperatively loaded in _load_thresholds
    "thresholds.green_rtt_ms", "thresholds.yellow_rtt_ms", "thresholds.red_rtt_ms",
    "thresholds.min_drops_red", "thresholds.min_queue_yellow", "thresholds.min_queue_red",
    "thresholds.rtt_ewma_alpha", "thresholds.queue_ewma_alpha",
    "thresholds.red_samples_required", "thresholds.green_samples_required",
    # Thresholds -- baseline bounds (imperatively loaded in _load_baseline_bounds)
    "thresholds.baseline_rtt_bounds",
    "thresholds.baseline_rtt_bounds.min", "thresholds.baseline_rtt_bounds.max",
    # Thresholds -- used in production config and storage config_snapshot
    "thresholds.bad_threshold_ms", "thresholds.recovery_threshold_ms",
    # Router -- imperatively loaded in _load_router_transport
    "router.transport", "router.password", "router.port", "router.verify_ssl",
    # CAKE state sources -- imperatively loaded in _load_state_sources
    "cake_state_sources", "cake_state_sources.primary",
    # Legacy deprecated: cake_state_sources.spectrum (-> primary)
    "cake_state_sources.spectrum",
    # CAKE queues -- imperatively loaded in _load_cake_queues
    "cake_queues",
    "cake_queues.primary_download", "cake_queues.primary_upload",
    # Legacy deprecated: cake_queues.spectrum_download/spectrum_upload
    "cake_queues.spectrum_download", "cake_queues.spectrum_upload",
    # Mode -- imperatively loaded in _load_operational_mode
    "mode", "mode.reset_counters", "mode.enable_yellow_state", "mode.use_confidence_scoring",
    # Legacy deprecated: mode.cake_aware (removed v1.12, ignored)
    "mode.cake_aware",
    # Confidence -- imperatively loaded in _load_confidence_config
    "confidence",
    "confidence.steer_threshold", "confidence.recovery_threshold",
    "confidence.sustain_duration_sec", "confidence.recovery_sustain_sec",
    "confidence.hold_down_duration_sec",
    "confidence.flap_detection_enabled", "confidence.flap_window_minutes",
    "confidence.max_toggles", "confidence.penalty_duration_sec",
    "confidence.penalty_threshold_add", "confidence.dry_run",
    # WAN state -- imperatively loaded in _load_wan_state_config
    "wan_state",
    "wan_state.enabled", "wan_state.red_weight",
    "wan_state.staleness_threshold_sec", "wan_state.grace_period_sec",
    "wan_state.wan_override",
    # Capacity protection (future, present in production config)
    "capacity_protection",
    "capacity_protection.att_upload_reserve_mbps",
    "capacity_protection.att_download_reserve_mbps",
    # Timeouts -- imperatively loaded in _load_timeouts
    "timeouts", "timeouts.ssh_command", "timeouts.ping", "timeouts.ping_total",
    # Logging -- steering-specific (log_cake_stats)
    "logging.log_cake_stats",
    # Health check -- imperatively loaded in _load_health_check_config
    "health_check", "health_check.enabled", "health_check.host", "health_check.port",
    # Metrics -- imperatively loaded in _load_metrics_config
    "metrics", "metrics.enabled",
    # Storage (from STORAGE_SCHEMA, shared)
    "storage", "storage.retention_days", "storage.db_path",
    # Alerting -- imperatively loaded in _load_alerting_config
    "alerting", "alerting.enabled", "alerting.webhook_url",
    "alerting.default_cooldown_sec", "alerting.default_sustained_sec",
    "alerting.rules", "alerting.mention_role_id", "alerting.mention_severity",
    "alerting.max_webhooks_per_minute",
    # Schema version
    "schema_version",
}
```

### Steering Cross-Field Checks
```python
def validate_steering_cross_fields(data: dict) -> list[CheckResult]:
    """Validate steering-specific cross-field constraints."""
    results: list[CheckResult] = []

    # Confidence threshold ordering: recovery_threshold < steer_threshold
    confidence = data.get("confidence", {})
    mode = data.get("mode", {})
    if mode.get("use_confidence_scoring") and confidence:
        steer = confidence.get("steer_threshold", 55)
        recovery = confidence.get("recovery_threshold", 20)
        if isinstance(steer, (int, float)) and isinstance(recovery, (int, float)):
            if recovery >= steer:
                results.append(CheckResult(
                    "Cross-field Checks",
                    "confidence.thresholds",
                    Severity.ERROR,
                    f"confidence.recovery_threshold ({recovery}) must be less than "
                    f"steer_threshold ({steer})",
                ))
            else:
                results.append(CheckResult(
                    "Cross-field Checks",
                    "confidence.thresholds",
                    Severity.PASS,
                    f"Confidence threshold ordering: valid "
                    f"(recovery={recovery} < steer={steer})",
                ))

    # measurement.interval_seconds range (already in SCHEMA, but semantic check)
    measurement = data.get("measurement", {})
    interval = measurement.get("interval_seconds")
    if interval is not None and isinstance(interval, (int, float)):
        if interval < 0.05:
            results.append(CheckResult(
                "Cross-field Checks",
                "measurement.interval_seconds",
                Severity.WARN,
                f"measurement.interval_seconds ({interval}) is below autorate cycle "
                f"interval (0.05s) -- steering may miss events",
            ))
        else:
            results.append(CheckResult(
                "Cross-field Checks",
                "measurement.interval_seconds",
                Severity.PASS,
                f"measurement.interval_seconds ({interval}s): valid",
            ))

    # state.history_size relative to interval
    state = data.get("state", {})
    history_size = state.get("history_size")
    if history_size is not None and interval is not None:
        window_sec = history_size * interval if isinstance(interval, (int, float)) else None
        if window_sec is not None and window_sec < 30:
            results.append(CheckResult(
                "Cross-field Checks",
                "state.history_size",
                Severity.WARN,
                f"state.history_size ({history_size}) x interval ({interval}s) = "
                f"{window_sec:.0f}s window -- less than 30s may cause unstable steering",
            ))

    return results
```

### Steering Deprecated Parameters
```python
def check_steering_deprecated_params(data: dict) -> list[CheckResult]:
    """Detect deprecated steering parameters."""
    results: list[CheckResult] = []

    # mode.cake_aware -- removed in v1.12, always active
    mode = data.get("mode", {})
    if isinstance(mode, dict) and "cake_aware" in mode:
        results.append(CheckResult(
            "Deprecated Parameters",
            "mode.cake_aware",
            Severity.WARN,
            "mode.cake_aware is deprecated -- CAKE three-state model is always active, "
            "this key is ignored",
            suggestion="Remove mode.cake_aware from config",
        ))

    # cake_state_sources.spectrum -> primary
    sources = data.get("cake_state_sources", {})
    if isinstance(sources, dict) and "spectrum" in sources:
        results.append(CheckResult(
            "Deprecated Parameters",
            "cake_state_sources.spectrum",
            Severity.WARN,
            "cake_state_sources.spectrum is deprecated -> use cake_state_sources.primary",
        ))

    # cake_queues.spectrum_download -> primary_download
    queues = data.get("cake_queues", {})
    if isinstance(queues, dict):
        if "spectrum_download" in queues:
            results.append(CheckResult(
                "Deprecated Parameters",
                "cake_queues.spectrum_download",
                Severity.WARN,
                "cake_queues.spectrum_download is deprecated -> use cake_queues.primary_download",
            ))
        if "spectrum_upload" in queues:
            results.append(CheckResult(
                "Deprecated Parameters",
                "cake_queues.spectrum_upload",
                Severity.WARN,
                "cake_queues.spectrum_upload is deprecated -> use cake_queues.primary_upload",
            ))

    return results
```

### Updated main() Dispatch
```python
def main() -> int:
    parser = create_parser()
    args = parser.parse_args()

    # Load YAML (unchanged)
    try:
        with open(args.config_file) as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: config file not found: {args.config_file}", file=sys.stderr)
        return 1
    except yaml.YAMLError as e:
        print(f"Error: invalid YAML in {args.config_file}: {e}", file=sys.stderr)
        return 1

    if not isinstance(data, dict):
        print(f"Error: config file must contain a YAML mapping", file=sys.stderr)
        return 1

    # Determine config type
    if args.type:
        config_type = args.type
    else:
        config_type = detect_config_type(data)

    # Dispatch validators
    if config_type == "steering":
        results = _run_steering_validators(data)
    else:
        results = _run_autorate_validators(data)

    # Format and print
    if args.json:
        output = format_results_json(results, config_type)
    else:
        output = format_results(results, no_color=args.no_color, quiet=args.quiet,
                                config_type=config_type)
    print(output)

    # Exit code (unchanged logic)
    has_errors = any(r.severity == Severity.ERROR for r in results)
    has_warnings = any(r.severity == Severity.WARN for r in results)
    if has_errors:
        return 1
    if has_warnings:
        return 2
    return 0
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Only autorate config validation | Steering + autorate with auto-detect | Phase 82 | Single tool validates any wanctl config |
| Text-only output | Text + JSON output modes | Phase 82 | CI/scripting integration |
| Manual --type specification | Auto-detection with --type override | Phase 82 | Simpler UX for operators |
| `cake_state_sources.spectrum` | `cake_state_sources.primary` | v1.13 | Deprecated, auto-translated by daemon |
| `mode.cake_aware` | Always-on CAKE three-state | v1.12 | Deprecated, ignored by daemon |
| `cake_queues.spectrum_download/upload` | `cake_queues.primary_download/upload` | v1.13 | Deprecated, auto-translated |

## Open Questions

1. **capacity_protection keys**
   - What we know: `capacity_protection` section with `att_upload_reserve_mbps` and `att_download_reserve_mbps` exists in production steering config. The daemon does NOT load these fields -- they're future/placeholder config.
   - What's unclear: Should they be validated (type/range checks), or just accepted as known keys?
   - Recommendation: Include in KNOWN_STEERING_PATHS to suppress unknown-key warnings. No schema validation (not loaded by daemon). Low priority.

2. **Steering EWMA alpha cross-field validation**
   - What we know: `validate_alpha()` clamps EWMA values in daemon. `thresholds.rtt_ewma_alpha` and `thresholds.queue_ewma_alpha` are loaded with defaults.
   - What's unclear: Should check_config call validate_alpha() on these values?
   - Recommendation: Yes, add as cross-field checks. Valid range is 0.0-1.0. If out of range, WARN (daemon clamps, doesn't crash).

3. **format_results() signature change**
   - What we know: format_results() currently has no config_type parameter. Adding it changes the function signature.
   - What's unclear: Does this break any tests?
   - Recommendation: Add `config_type: str = "autorate"` as a keyword argument with default. This preserves backward compatibility for existing calls and tests.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `.venv/bin/pytest tests/test_check_config.py -x` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CVAL-02 | Steering config validates with schema + cross-field + unknown keys | unit | `.venv/bin/pytest tests/test_check_config.py::TestSteeringValidation -x` | Wave 0 |
| CVAL-03 | Auto-detection: topology=steering, continuous_monitoring=autorate, both=error, neither=error | unit | `.venv/bin/pytest tests/test_check_config.py::TestConfigTypeDetection -x` | Wave 0 |
| CVAL-09 | Cross-config: file existence WARN, wan_name match PASS, wan_name mismatch ERROR | unit | `.venv/bin/pytest tests/test_check_config.py::TestCrossConfigValidation -x` | Wave 0 |
| CVAL-10 | JSON output: correct structure, all results included, pipe-friendly | unit | `.venv/bin/pytest tests/test_check_config.py::TestJsonOutput -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_check_config.py -x`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_check_config.py::TestSteeringValidation` -- covers CVAL-02
- [ ] `tests/test_check_config.py::TestConfigTypeDetection` -- covers CVAL-03
- [ ] `tests/test_check_config.py::TestCrossConfigValidation` -- covers CVAL-09
- [ ] `tests/test_check_config.py::TestJsonOutput` -- covers CVAL-10

*(Existing test_check_config.py has autorate tests; new test classes extend it)*

## Sources

### Primary (HIGH confidence)
- **Codebase inspection:** `src/wanctl/check_config.py` (786 lines) -- existing tool with Severity, CheckResult, 6 validators, format_results, create_parser, main
- **Codebase inspection:** `src/wanctl/steering/daemon.py` lines 131-670 -- SteeringConfig.SCHEMA (10 fields), _load_specific_fields orchestration, all _load_* methods for imperatively loaded fields
- **Codebase inspection:** `configs/steering.yaml` -- production steering config (55 paths, including capacity_protection, bad_threshold_ms, recovery_threshold_ms)
- **Codebase inspection:** `configs/examples/steering.yaml.example` -- example steering config (50 paths, including cake_queues, timeouts, schema_version, logging.log_cake_stats)
- **Codebase inspection:** `src/wanctl/config_base.py` -- BaseConfig.BASE_SCHEMA (10 fields), validate_field, _get_nested
- **Codebase inspection:** `tests/test_check_config.py` -- existing test patterns (7 test classes, fixture helpers)
- **Codebase inspection:** `src/wanctl/config_validation_utils.py` -- validate_alpha() for EWMA bounds, deprecate_param() for legacy key detection

### Secondary (MEDIUM confidence)
- **Codebase inspection:** `src/wanctl/storage/config_snapshot.py` -- confirms bad_threshold_ms and recovery_threshold_ms are accessed from config data

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all stdlib + existing project code, zero new deps, json.dumps pattern verified in health_check.py/history.py
- Architecture: HIGH -- extends existing check_config.py patterns directly; SteeringConfig.SCHEMA verified accessible as class attribute; all imperative load methods audited
- Pitfalls: HIGH -- KNOWN_STEERING_PATHS exhaustively verified against both production and example configs (~65 paths); import side effects analyzed; cross-config error handling patterns documented

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (stable domain, no external dependencies changing)
