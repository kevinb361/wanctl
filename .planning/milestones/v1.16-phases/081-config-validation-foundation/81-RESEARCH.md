# Phase 81: Config Validation Foundation - Research

**Researched:** 2026-03-12
**Domain:** CLI config validation tool (offline, no daemon startup)
**Confidence:** HIGH

## Summary

Phase 81 builds a standalone `wanctl-check-config` CLI tool that validates autorate config files offline and reports all problems at once. The tool reuses existing infrastructure heavily: `BaseConfig.BASE_SCHEMA`, `Config.SCHEMA`, `validate_schema()`, `validate_bandwidth_order()`, `validate_threshold_order()`, and `deprecate_param()` already exist in the codebase. The primary new work is (1) building a non-throwing validation runner that collects results instead of raising on first error, (2) adding checks not currently in the schema (file/path existence, env vars, unknown keys), and (3) formatting output with PASS/WARN/FAIL per category.

A critical finding: the autorate SCHEMA only covers 24 of ~57 config paths in production configs. Many valid fields (`router.transport`, `router.password`, `state_file`, `timeouts.*`, `fallback_checks.*`, `health_check.*`, `metrics.*`, `alerting.*`, `use_median_of_three`) are loaded imperatively in `_load_specific_fields()` but never declared in SCHEMA. Unknown key detection must account for all valid paths, not just SCHEMA paths, or it will false-positive on every production config.

**Primary recommendation:** Create `src/wanctl/check_config.py` following the `wanctl-history` pattern (create_parser/main). Build a `ValidationResult` dataclass and per-category validator functions that return lists of results. Reuse SCHEMA definitions but wrap `validate_schema()` in a non-throwing collector. Build a comprehensive KNOWN_KEYS set from SCHEMA + imperative loads.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Category-grouped output: results organized under headings (Schema Validation, Cross-field Checks, File Paths, Environment Variables, Deprecated Parameters)
- Each individual check shows PASS, WARN, or FAIL markers
- One-line summary at bottom: `Result: PASS/WARN/FAIL (N errors, N warnings)`
- Color by default (green/yellow/red), `--no-color` flag to disable
- Show all checks by default (pass + fail), `-q/--quiet` flag suppresses passing checks
- Deprecated params are WARN severity, exit code 2 if only deprecated params found
- Show the translated value for deprecated params with auto-translation display
- WARN on unknown config keys with "did you mean: X?" suggestion
- Check parent directory exists for log files and state files -- ERROR if missing
- Check SSH key file exists and is readable -- ERROR if missing
- WARN on insecure SSH key permissions (0644/0755) with recommendation to chmod 600
- Include fix suggestions with copy-pasteable commands (mkdir -p, chmod 600)
- WARN if referenced env vars (e.g., ${ROUTER_PASSWORD}) are not set -- warning, not error
- Exit codes: 0=all pass, 1=at least one error, 2=warnings only
- Zero new dependencies -- reuse BaseConfig, validate_schema, argparse, existing validators
- Must never reject currently-working production configs -- backward compat is primary constraint
- Output should feel like `ruff check` or `mypy` -- structured, scannable, actionable

### Claude's Discretion
- Internal architecture (validator class hierarchy, result collection data structures)
- Check ordering within categories
- Color implementation details (ANSI codes vs library)
- "Did you mean" fuzzy matching algorithm
- Exact CLI argument parsing structure (following wanctl-history argparse pattern)

### Deferred Ideas (OUT OF SCOPE)
- Steering config validation -- Phase 82
- Config type auto-detection -- Phase 82
- JSON output mode (--json) -- Phase 82
- Cross-config validation (steering references autorate config) -- Phase 82
- `--strict` flag promoting warnings to errors -- backlog
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CVAL-01 | Operator can validate an autorate config file offline via `wanctl-check-config` | CLI entry point in pyproject.toml, argparse pattern from wanctl-history, new check_config.py module |
| CVAL-04 | All validation errors are collected and reported (not just the first) | Non-throwing validation runner wrapping validate_schema(); ValidationResult collection pattern |
| CVAL-05 | Cross-field semantic validation catches contradictions (floor ordering, threshold ordering, ceiling < floor) | Reuse validate_bandwidth_order() and validate_threshold_order() from config_validation_utils.py |
| CVAL-06 | File/permission checks verify referenced paths exist and are accessible | New path validation category: log dirs, state dirs, SSH key existence + permissions |
| CVAL-07 | Environment variable resolution check warns when ${ROUTER_PASSWORD} env var is unset | Pattern from router_client.py _resolve_password(): detect ${VAR} syntax, check os.environ |
| CVAL-08 | Deprecated parameters are collected and surfaced prominently in output | Reuse deprecate_param() from config_validation_utils.py, wrap to capture results |
| CVAL-11 | Exit codes indicate result (0=pass, 1=errors, 2=warnings only) | sys.exit() in main(), severity tracking in result aggregator |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| argparse | stdlib | CLI argument parsing | Already used by wanctl-history, wanctl-dashboard |
| pathlib | stdlib | File/directory existence checks | Already used everywhere in wanctl |
| difflib | stdlib | Fuzzy matching for "did you mean" suggestions | `get_close_matches()` -- verified working for typo detection |
| os | stdlib | Environment variable checking, file permissions | `os.environ`, `os.stat()` |
| stat | stdlib | Permission bit constants | `stat.S_IRWXO`, `stat.S_IRWXG` for SSH key permission checks |
| yaml | 6.0.1+ | YAML parsing (already a dependency) | Already used by BaseConfig |

### Supporting (all existing project code, no new deps)
| Module | Purpose | When to Use |
|--------|---------|-------------|
| `wanctl.config_base` | `validate_schema()`, `ConfigValidationError`, `BaseConfig.BASE_SCHEMA` | Schema validation category |
| `wanctl.autorate_continuous.Config` | `Config.SCHEMA` definition (24 fields) | Schema validation category |
| `wanctl.config_validation_utils` | `validate_bandwidth_order()`, `validate_threshold_order()`, `deprecate_param()` | Cross-field and deprecated categories |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw ANSI codes | `colorama` or `rich` | User locked "zero new dependencies"; ANSI codes are trivial and wanctl-dashboard already does terminal compat |
| `difflib.get_close_matches` | `thefuzz`/`rapidfuzz` | stdlib is sufficient for simple typo detection; tested with `ceilling_mbps` -> `ceiling_mbps` successfully |
| Custom YAML loader | `pydantic`, `cerberus` | Existing validate_schema() + SCHEMA definitions are the established pattern; zero new deps constraint |

**Installation:**
```bash
# No new packages needed. Zero new dependencies.
```

## Architecture Patterns

### Recommended Project Structure
```
src/wanctl/
  check_config.py        # NEW: CLI tool + validation logic
  config_base.py         # EXISTING: BaseConfig, validate_schema, SCHEMA helpers
  config_validation_utils.py  # EXISTING: cross-field validators, deprecate_param
  autorate_continuous.py      # EXISTING: Config.SCHEMA (import for field list)
```

### Pattern 1: ValidationResult Data Model
**What:** A simple dataclass for individual check results plus a collector that aggregates them by category.
**When to use:** Every validator function returns a list of ValidationResult, main collects them all.
**Example:**
```python
from dataclasses import dataclass
from enum import Enum

class Severity(Enum):
    PASS = "pass"
    WARN = "warn"
    ERROR = "error"

@dataclass
class CheckResult:
    category: str       # "Schema Validation", "Cross-field Checks", etc.
    field: str          # config path or check name
    severity: Severity
    message: str
    suggestion: str | None = None  # e.g., "mkdir -p /var/log/wanctl"
```

### Pattern 2: Non-Throwing Schema Validation
**What:** Wrap the existing `validate_schema()` call in a try/catch that parses the collected error message, plus run individual `validate_field()` calls that DON'T raise, collecting results instead.
**When to use:** Schema validation category.
**Why necessary:** Current `validate_schema()` collects errors internally but then raises a single `ConfigValidationError` with all errors concatenated. The check tool needs each error as a separate `CheckResult`. Two approaches:
  - (A) Parse the error message from `validate_schema()` (fragile, depends on formatting)
  - (B) Iterate `BASE_SCHEMA + Config.SCHEMA` directly, calling `validate_field()` per-field with try/except per field

**Recommendation:** Approach (B) -- iterate the schema directly. This is more robust and gives per-field granularity. Each passing field also gets a PASS result.

```python
def validate_schema_fields(data: dict, schema: list[dict]) -> list[CheckResult]:
    results = []
    for field_spec in schema:
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

### Pattern 3: Comprehensive Known Keys for Unknown Detection
**What:** Build a full set of known config paths (not just SCHEMA) to avoid false positives.
**When to use:** Unknown key detection category.
**Critical finding:** SCHEMA only covers 24 of ~57 valid paths. The following top-level keys are valid but NOT in SCHEMA:
  - `router.transport`, `router.password`, `router.port`, `router.verify_ssl`
  - `state_file`
  - `timeouts.ssh_command`, `timeouts.ping`
  - `continuous_monitoring.use_median_of_three`
  - `continuous_monitoring.fallback_checks.*` (7 sub-keys)
  - `continuous_monitoring.download.floor_mbps` (legacy single-floor)
  - `continuous_monitoring.download.floor_green_mbps`, `floor_yellow_mbps`, `floor_soft_red_mbps`, `floor_red_mbps`
  - `continuous_monitoring.upload.floor_mbps` (legacy)
  - `continuous_monitoring.upload.floor_green_mbps`, `floor_yellow_mbps`, `floor_red_mbps`
  - `continuous_monitoring.thresholds.baseline_update_threshold_ms`
  - `continuous_monitoring.thresholds.baseline_rtt_bounds` (the dict itself)
  - `health_check.*` (3 sub-keys)
  - `metrics.*` (3 sub-keys)
  - `alerting.*` (many sub-keys)
  - `storage.*` (2 sub-keys)
  - `schema_version`

**Implementation:** Define a `KNOWN_AUTORATE_KEYS` set as a module-level constant that includes both SCHEMA paths and all imperatively-loaded paths. This is more maintainable than trying to introspect the Config class.

### Pattern 4: CLI Entry Point (following wanctl-history)
**What:** `create_parser()` returns ArgumentParser, `main()` parses args and returns exit code.
**When to use:** CLI structure.
```python
def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wanctl-check-config",
        description="Validate wanctl configuration files offline",
    )
    parser.add_argument("config_file", help="Path to YAML config file")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")
    parser.add_argument("-q", "--quiet", action="store_true", help="Only show warnings and errors")
    return parser

def main() -> int:
    parser = create_parser()
    args = parser.parse_args()
    # ... run validation, format output, return exit code
```

### Anti-Patterns to Avoid
- **Importing daemon startup code:** The check tool must import `Config.SCHEMA` without triggering `Config.__init__()` or any daemon wiring. Import the class for its SCHEMA attribute only, never instantiate it.
- **Short-circuiting on first error:** Every validator must continue checking after finding an error. The whole point is "see all problems at once."
- **False positives on valid production configs:** Run the tool against `configs/spectrum.yaml`, `configs/att.yaml` before shipping. If any currently-working config shows unexpected errors, the tool is wrong.
- **Using `BaseConfig.__init__()` for validation:** It raises on first schema error group and triggers side effects (logging setup, file operations). Build validation from the primitives (`validate_field`, `validate_schema` field specs) instead.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Schema field validation | Custom type/range checks | `validate_field()` from config_base.py | Already handles type coercion (int->float), range, choices, required/optional |
| Bandwidth ordering | Custom floor comparison logic | `validate_bandwidth_order()` from config_validation_utils.py | Already handles 3-state and 4-state floor ordering with Mbps conversion |
| Threshold ordering | Custom threshold comparison | `validate_threshold_order()` from config_validation_utils.py | Already validates target < warn < hard_red |
| Deprecated param detection | Scanning for old keys manually | `deprecate_param()` from config_validation_utils.py | Already knows the old->new mappings and transform functions |
| Fuzzy string matching | Custom edit distance | `difflib.get_close_matches()` | stdlib, tested working: `ceilling_mbps` -> `ceiling_mbps` at cutoff=0.6 |
| YAML parsing | Custom parser | `yaml.safe_load()` | Already a project dependency, handles all edge cases |
| Env var detection | Custom regex | Check for `${...}` pattern matching `_resolve_password()` in router_client.py | Existing pattern: `password.startswith("${") and password.endswith("}")` |

**Key insight:** ~70% of the validation logic already exists in the codebase. The new work is primarily (1) wrapping existing validators in a non-throwing collector, (2) adding file/path checks, (3) building the unknown-key set, and (4) formatting output.

## Common Pitfalls

### Pitfall 1: SCHEMA Coverage Gap
**What goes wrong:** Building unknown-key detection from only SCHEMA paths, causing every valid production config to report false warnings for `state_file`, `timeouts`, `router.transport`, `router.password`, etc.
**Why it happens:** SCHEMA declares 24 fields, but autorate configs use ~57 paths. The gap exists because many fields are loaded imperatively in `_load_specific_fields()`.
**How to avoid:** Build a comprehensive `KNOWN_AUTORATE_KEYS` set by hand, covering all valid keys from both SCHEMA and imperative loads. Validate against production configs.
**Warning signs:** Running the tool against `configs/spectrum.yaml` produces warnings for keys like `state_file` or `timeouts`.

### Pitfall 2: Legacy Config False Negatives
**What goes wrong:** Tool flags `floor_mbps` as unknown because SCHEMA uses `floor_green_mbps`/`floor_red_mbps` etc.
**Why it happens:** ATT config uses legacy single-floor format (`floor_mbps`) while Spectrum uses v2 multi-floor format (`floor_green_mbps`, `floor_yellow_mbps`, etc.). Both are valid.
**How to avoid:** Include both legacy and modern floor keys in KNOWN_KEYS. Cross-field validation should handle both formats gracefully (as `_load_download_config` already does with the `if "floor_green_mbps" in dl` branch).
**Warning signs:** ATT config shows warnings for `floor_mbps`.

### Pitfall 3: Importing Side Effects
**What goes wrong:** Importing from `autorate_continuous` triggers global-scope side effects (logger config, constant computation).
**Why it happens:** The module has module-level code and imports many daemon modules.
**How to avoid:** Only import `Config` class for its SCHEMA attribute. Do not instantiate. Better yet, consider defining the SCHEMA access as a lazy import or using `importlib`.
**Warning signs:** Import of check_config module causes unexpected log output or slow startup.

### Pitfall 4: Color Code Leaking to Pipes
**What goes wrong:** Piping output (e.g., `wanctl-check-config foo.yaml | grep FAIL`) produces garbled ANSI codes.
**Why it happens:** Tool emits ANSI color codes even when stdout is not a terminal.
**How to avoid:** Check `sys.stdout.isatty()` -- disable color when not a TTY, or when `--no-color` is passed, or when `NO_COLOR` env var is set (de facto standard).
**Warning signs:** Piped output contains `\033[` escape sequences.

### Pitfall 5: Threshold Mutual Exclusivity
**What goes wrong:** Validation rejects configs that specify `baseline_time_constant_sec` but not `alpha_baseline`, treating it as "missing required field."
**Why it happens:** SCHEMA declares both `alpha_baseline` and `baseline_time_constant_sec` as optional. But `_load_threshold_config()` requires at least one of each pair. The check tool must replicate this "either/or" logic.
**How to avoid:** Add cross-field check: "either `alpha_baseline` or `baseline_time_constant_sec` must be present" (same for load pair). This is a cross-field semantic check, not a schema check.
**Warning signs:** Production configs (which use time constants) show schema errors for missing alpha values.

### Pitfall 6: Env Var Check Environment Mismatch
**What goes wrong:** Tool reports ERROR for unset `${ROUTER_PASSWORD}` when the operator is running validation on their laptop, not on the deployment container.
**Why it happens:** Env vars are environment-specific; the check tool may run in a different environment than the daemon.
**How to avoid:** WARN severity (not ERROR) for unset env vars, with message explaining the env-specific nature. This is already a locked decision in CONTEXT.md.

## Code Examples

### Example 1: Full Config Path Set for Autorate
```python
# Comprehensive known keys for autorate configs
# Sources: BASE_SCHEMA + Config.SCHEMA + imperative loads in _load_specific_fields
KNOWN_AUTORATE_PATHS: set[str] = {
    # From BASE_SCHEMA
    "wan_name", "router", "router.host", "router.user", "router.ssh_key",
    "logging", "logging.main_log", "logging.debug_log",
    "logging.max_bytes", "logging.backup_count",
    "lock_file", "lock_timeout",
    # From Config.SCHEMA
    "queues", "queues.download", "queues.upload",
    "continuous_monitoring", "continuous_monitoring.enabled",
    "continuous_monitoring.baseline_rtt_initial",
    "continuous_monitoring.download",
    "continuous_monitoring.download.ceiling_mbps",
    "continuous_monitoring.download.step_up_mbps",
    "continuous_monitoring.download.factor_down",
    "continuous_monitoring.download.factor_down_yellow",
    "continuous_monitoring.download.green_required",
    # Legacy single-floor (ATT format)
    "continuous_monitoring.download.floor_mbps",
    # Modern multi-floor (Spectrum format)
    "continuous_monitoring.download.floor_green_mbps",
    "continuous_monitoring.download.floor_yellow_mbps",
    "continuous_monitoring.download.floor_soft_red_mbps",
    "continuous_monitoring.download.floor_red_mbps",
    # Upload (same legacy vs modern pattern)
    "continuous_monitoring.upload",
    "continuous_monitoring.upload.ceiling_mbps",
    "continuous_monitoring.upload.step_up_mbps",
    "continuous_monitoring.upload.factor_down",
    "continuous_monitoring.upload.factor_down_yellow",
    "continuous_monitoring.upload.green_required",
    "continuous_monitoring.upload.floor_mbps",
    "continuous_monitoring.upload.floor_green_mbps",
    "continuous_monitoring.upload.floor_yellow_mbps",
    "continuous_monitoring.upload.floor_red_mbps",
    # Thresholds
    "continuous_monitoring.thresholds",
    "continuous_monitoring.thresholds.target_bloat_ms",
    "continuous_monitoring.thresholds.warn_bloat_ms",
    "continuous_monitoring.thresholds.hard_red_bloat_ms",
    "continuous_monitoring.thresholds.alpha_baseline",
    "continuous_monitoring.thresholds.alpha_load",
    "continuous_monitoring.thresholds.baseline_time_constant_sec",
    "continuous_monitoring.thresholds.load_time_constant_sec",
    "continuous_monitoring.thresholds.accel_threshold_ms",
    "continuous_monitoring.thresholds.baseline_update_threshold_ms",
    "continuous_monitoring.thresholds.baseline_rtt_bounds",
    "continuous_monitoring.thresholds.baseline_rtt_bounds.min",
    "continuous_monitoring.thresholds.baseline_rtt_bounds.max",
    # Ping
    "continuous_monitoring.ping_hosts",
    "continuous_monitoring.use_median_of_three",
    # Fallback checks
    "continuous_monitoring.fallback_checks",
    "continuous_monitoring.fallback_checks.enabled",
    "continuous_monitoring.fallback_checks.check_gateway",
    "continuous_monitoring.fallback_checks.check_tcp",
    "continuous_monitoring.fallback_checks.gateway_ip",
    "continuous_monitoring.fallback_checks.tcp_targets",
    "continuous_monitoring.fallback_checks.fallback_mode",
    "continuous_monitoring.fallback_checks.max_fallback_cycles",
    # Router (imperatively loaded)
    "router.transport", "router.password", "router.port", "router.verify_ssl",
    # State file (imperatively loaded)
    "state_file",
    # Timeouts (imperatively loaded)
    "timeouts", "timeouts.ssh_command", "timeouts.ping",
    # Health check (imperatively loaded)
    "health_check", "health_check.enabled", "health_check.host", "health_check.port",
    # Metrics (imperatively loaded)
    "metrics", "metrics.enabled", "metrics.host", "metrics.port",
    # Storage (from STORAGE_SCHEMA)
    "storage", "storage.retention_days", "storage.db_path",
    # Alerting (imperatively loaded, many sub-keys)
    "alerting", "alerting.enabled", "alerting.webhook_url",
    "alerting.default_cooldown_sec", "alerting.default_sustained_sec",
    "alerting.rules",
    # Schema version
    "schema_version",
}
```

### Example 2: Env Var Detection Pattern
```python
# Source: router_client.py _resolve_password() pattern
import os
import re

ENV_VAR_PATTERN = re.compile(r'\$\{([^}]+)\}')

def check_env_vars(data: dict) -> list[CheckResult]:
    """Scan all string values in config for ${VAR} references."""
    results = []
    for path, value in _walk_strings(data):
        match = ENV_VAR_PATTERN.search(str(value))
        if match:
            var_name = match.group(1)
            if var_name in os.environ:
                results.append(CheckResult(
                    "Environment Variables", path, Severity.PASS,
                    f"{path}: ${{{var_name}}} is set"
                ))
            else:
                results.append(CheckResult(
                    "Environment Variables", path, Severity.WARN,
                    f"{path}: ${{{var_name}}} is not set in current environment",
                    suggestion="Set before running daemon, or check deployment environment"
                ))
    return results
```

### Example 3: File/Path Checks
```python
import os
import stat
from pathlib import Path

def check_paths(data: dict) -> list[CheckResult]:
    results = []

    # Log directory checks
    for log_path_key in ["logging.main_log", "logging.debug_log"]:
        log_path = _get_nested(data, log_path_key)
        if log_path:
            parent = Path(log_path).parent
            if parent.exists():
                results.append(CheckResult(
                    "File Paths", log_path_key, Severity.PASS,
                    f"{log_path_key}: parent directory exists ({parent})"
                ))
            else:
                results.append(CheckResult(
                    "File Paths", log_path_key, Severity.ERROR,
                    f"{log_path_key}: parent directory missing ({parent})",
                    suggestion=f"mkdir -p {parent}"
                ))

    # SSH key check
    ssh_key = _get_nested(data, "router.ssh_key")
    if ssh_key:
        key_path = Path(ssh_key)
        if not key_path.exists():
            results.append(CheckResult(
                "File Paths", "router.ssh_key", Severity.ERROR,
                f"router.ssh_key: file not found ({ssh_key})"
            ))
        else:
            mode = key_path.stat().st_mode
            if mode & (stat.S_IRWXG | stat.S_IRWXO):
                results.append(CheckResult(
                    "File Paths", "router.ssh_key", Severity.WARN,
                    f"router.ssh_key: insecure permissions ({oct(mode & 0o777)})",
                    suggestion=f"chmod 600 {ssh_key}"
                ))
            else:
                results.append(CheckResult(
                    "File Paths", "router.ssh_key", Severity.PASS,
                    f"router.ssh_key: exists with secure permissions"
                ))

    return results
```

### Example 4: Output Formatting
```python
# ANSI color codes (disable when --no-color or not TTY)
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"

MARKERS = {
    Severity.PASS:  f"{GREEN}\u2713 PASS{RESET}",
    Severity.WARN:  f"{YELLOW}\u26a0 WARN{RESET}",
    Severity.ERROR: f"{RED}\u2717 FAIL{RESET}",
}

# Example output:
# === Schema Validation ===
# PASS  wan_name: valid
# PASS  router.host: valid
# FAIL  continuous_monitoring.download.ceiling_mbps: Value out of range...
#
# === Cross-field Checks ===
# PASS  Download floor ordering: valid
# FAIL  Upload: ceiling (18M) < floor (25M)
#
# === Deprecated Parameters ===
# WARN  alpha_baseline is deprecated -> use baseline_time_constant_sec
#       (auto-translated: 0.005 -> 10.0s)
#
# Result: FAIL (2 errors, 1 warning)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `validate_schema()` raises on all errors at once | Still current, but check tool needs per-field results | Phase 81 | Wrap in per-field iteration instead of batch |
| `alpha_baseline` / `alpha_load` raw values | `baseline_time_constant_sec` / `load_time_constant_sec` | v1.13 | Both must be accepted; time constants are preferred |
| Single `floor_mbps` for download/upload | State-based floors (`floor_green_mbps`, etc.) | v1.0 Phase 2A | Both formats must be accepted (ATT uses legacy, Spectrum uses modern) |

**Deprecated/outdated:**
- `alpha_baseline`: deprecated, use `baseline_time_constant_sec` (auto-translated via `deprecate_param`)
- `alpha_load`: deprecated, use `load_time_constant_sec` (auto-translated via `deprecate_param`)

## Open Questions

1. **Alerting sub-key validation depth**
   - What we know: `alerting.*` has many sub-keys (enabled, webhook_url, default_cooldown_sec, default_sustained_sec, rules with per-type overrides). Loading is complex (50+ lines of imperative validation).
   - What's unclear: Should check-config validate all alerting sub-keys deeply, or just validate the top-level structure?
   - Recommendation: Validate alerting the same way the daemon does -- check enabled/bool, cooldown/int, sustained/int, rules/dict. Skip deep per-rule validation for Phase 81 (can add depth later).

2. **state_file vs lock_file-derived state path**
   - What we know: Spectrum config has `state_file: "/var/lib/wanctl/spectrum_state.json"` but `_load_state_config()` actually derives state path from `lock_file` (ignoring `state_file` top-level key).
   - What's unclear: Is `state_file` a dead/ignored config key? Should the check tool warn about it?
   - Recommendation: Include `state_file` in KNOWN_KEYS (it exists in production configs), but do NOT validate its path since the daemon ignores it. Consider a low-priority NOTE suggesting removal.

3. **hard_red_bloat_ms presence in ATT config**
   - What we know: ATT config lacks `hard_red_bloat_ms` (uses default). Spectrum has it. Both are valid because the field has `"required": False` would need to be checked... but it's actually not in SCHEMA at all (it's loaded via `thresh.get("hard_red_bloat_ms", DEFAULT_HARD_RED_BLOAT_MS)`).
   - What's unclear: Can we cross-validate threshold ordering when `hard_red_bloat_ms` uses its default?
   - Recommendation: Use the default value when not specified, then validate ordering with the effective values. This matches daemon behavior.

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
| CVAL-01 | CLI accepts config file path, runs validation, produces output | unit + integration | `.venv/bin/pytest tests/test_check_config.py::TestCLI -x` | Wave 0 |
| CVAL-04 | Multiple errors all reported (not just first) | unit | `.venv/bin/pytest tests/test_check_config.py::TestErrorCollection -x` | Wave 0 |
| CVAL-05 | Floor ordering, threshold ordering, ceiling < floor caught | unit | `.venv/bin/pytest tests/test_check_config.py::TestCrossField -x` | Wave 0 |
| CVAL-06 | Missing log dirs, SSH key paths detected | unit | `.venv/bin/pytest tests/test_check_config.py::TestPathChecks -x` | Wave 0 |
| CVAL-07 | Unset ${ROUTER_PASSWORD} warned | unit | `.venv/bin/pytest tests/test_check_config.py::TestEnvVars -x` | Wave 0 |
| CVAL-08 | Deprecated params surfaced as WARN | unit | `.venv/bin/pytest tests/test_check_config.py::TestDeprecated -x` | Wave 0 |
| CVAL-11 | Exit codes 0/1/2 correct | unit | `.venv/bin/pytest tests/test_check_config.py::TestExitCodes -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_check_config.py -x`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_check_config.py` -- covers CVAL-01, CVAL-04, CVAL-05, CVAL-06, CVAL-07, CVAL-08, CVAL-11
- [ ] `tests/conftest.py` -- may need new fixtures for temp config files (existing conftest likely sufficient)

## Sources

### Primary (HIGH confidence)
- **Codebase inspection:** `src/wanctl/config_base.py` -- BaseConfig, validate_schema(), validate_field(), BASE_SCHEMA, STORAGE_SCHEMA
- **Codebase inspection:** `src/wanctl/config_validation_utils.py` -- validate_bandwidth_order(), validate_threshold_order(), deprecate_param()
- **Codebase inspection:** `src/wanctl/autorate_continuous.py` lines 120-278 -- Config.SCHEMA (24 fields), _load_specific_fields() (imperative loads)
- **Codebase inspection:** `src/wanctl/router_client.py` lines 93-109 -- _resolve_password() env var pattern
- **Codebase inspection:** `src/wanctl/history.py` lines 289-420 -- CLI pattern (create_parser/main)
- **Codebase inspection:** `configs/spectrum.yaml`, `configs/att.yaml` -- production config structure (57 paths autorate, 15+ top-level steering)
- **Codebase inspection:** `pyproject.toml` -- console_scripts pattern, dependencies (zero new deps verified)
- **Python stdlib verification:** `difflib.get_close_matches('ceilling_mbps', ['ceiling_mbps', ...])` returns `['ceiling_mbps']` at cutoff=0.6

### Secondary (MEDIUM confidence)
- NO_COLOR convention: https://no-color.org/ (de facto standard for respecting --no-color)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all stdlib + existing project code, zero new deps, verified by running imports
- Architecture: HIGH -- patterns directly observed in codebase (wanctl-history CLI, validate_schema, deprecate_param)
- Pitfalls: HIGH -- SCHEMA coverage gap verified empirically (24 of 57 paths), legacy format verified in ATT config, env var pattern verified in router_client.py

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (stable domain, no external dependencies changing)
