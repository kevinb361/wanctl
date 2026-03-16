# Phase 81: Config Validation Foundation - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Standalone CLI tool `wanctl-check-config` that validates autorate config files offline. Collects all problems (schema, cross-field, file paths, env vars, deprecated params) and reports them together with PASS/WARN/FAIL per category. Steering config support, auto-detection, and JSON output are Phase 82.

</domain>

<decisions>
## Implementation Decisions

### Output presentation
- Category-grouped output: results organized under headings (Schema Validation, Cross-field Checks, File Paths, Environment Variables, Deprecated Parameters)
- Each individual check shows ✓ PASS, ⚠ WARN, or ✗ FAIL
- One-line summary at bottom: `Result: PASS/WARN/FAIL (N errors, N warnings)`
- Color by default (green/yellow/red), `--no-color` flag to disable — consistent with wanctl-dashboard
- Show all checks by default (pass + fail), `-q/--quiet` flag suppresses passing checks

### Deprecated parameter handling
- Deprecated params are WARN severity — exit code 2 if only deprecated params found
- Show the translated value: `⚠ alpha_baseline is deprecated → use baseline_time_constant_sec instead (auto-translated: 0.005 → 10.0s)`
- Reuse existing `deprecate_param()` from config_validation_utils.py

### Unknown/unrecognized keys
- WARN on unknown config keys (catches typos like `ceilling_mbps`)
- Include "did you mean: X?" suggestion when a close match exists in the schema

### File and path checks
- Check parent directory exists for log files and state files — ERROR if missing
- Check SSH key file exists and is readable — ERROR if missing
- WARN on insecure SSH key permissions (0644/0755) with recommendation to chmod 600
- Include fix suggestions: `→ create with: mkdir -p /var/lib/wanctl`

### Environment variable handling
- WARN if referenced env vars (e.g., `${ROUTER_PASSWORD}`) are not set in current environment
- Warning, not error — tool may run in different environment than daemon

### Exit codes
- 0: all checks pass (no errors, no warnings)
- 1: at least one error found
- 2: warnings only (no errors)

### Claude's Discretion
- Internal architecture (validator class hierarchy, result collection data structures)
- Check ordering within categories
- Color implementation details (ANSI codes vs library)
- "Did you mean" fuzzy matching algorithm
- Exact CLI argument parsing structure (following wanctl-history argparse pattern)

</decisions>

<specifics>
## Specific Ideas

- Output should feel like running `ruff check` or `mypy` — structured, scannable, actionable
- Fix suggestions on errors give operators copy-pasteable commands (mkdir -p, chmod 600)
- Must never reject currently-working production configs — backward compat is primary constraint
- Zero new dependencies — reuse BaseConfig, validate_schema, argparse, existing validators

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `BaseConfig` (config_base.py): Abstract config loader with YAML parsing, schema version detection, security validators
- `validate_schema()` (config_base.py:156-209): Already collects all errors, returns validated dict
- `validate_bandwidth_order()` (config_validation_utils.py:61-134): Floor ordering checks with Mbps conversion
- `validate_threshold_order()` (config_validation_utils.py:137-187): Bloat threshold ordering
- `validate_baseline_rtt()`, `validate_rtt_thresholds()`, `validate_sample_counts()`, `validate_alpha()`: Additional cross-field validators
- `deprecate_param()` (config_validation_utils.py:22-58): Warn+translate helper with formula support
- `ConfigValidationError` (config_base.py:12-15): Existing exception class

### Established Patterns
- CLI entry points registered in pyproject.toml console_scripts (wanctl-history, wanctl-dashboard)
- `wanctl-history` pattern: `create_parser()` returns ArgumentParser, `main()` entry point
- Error collection pattern: `errors = []` → append during validation → raise with all collected
- Config SCHEMA definitions in each daemon's Config class (17 autorate fields, 8 steering fields)

### Integration Points
- New `wanctl-check-config` entry point in pyproject.toml console_scripts
- New module: `src/wanctl/check_config.py` (or similar)
- Imports from config_base.py, config_validation_utils.py, autorate_continuous.py (Config.SCHEMA)
- Must not import or trigger daemon startup code — validation only

</code_context>

<deferred>
## Deferred Ideas

- Steering config validation — Phase 82
- Config type auto-detection — Phase 82
- JSON output mode (--json) — Phase 82
- Cross-config validation (steering references autorate config) — Phase 82
- `--strict` flag promoting warnings to errors — add to backlog if needed

</deferred>

---

*Phase: 81-config-validation-foundation*
*Context gathered: 2026-03-12*
