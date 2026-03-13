# Phase 82: Steering Config + Output Modes - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Extend `wanctl-check-config` to validate steering config files with auto-detection, add steering-specific cross-field and cross-config checks, and provide `--json` output mode for CI/scripting. Does not add new CLI tools or modify existing daemon behavior.

</domain>

<decisions>
## Implementation Decisions

### Auto-detection strategy
- Single marker detection: `topology` key -> steering, `continuous_monitoring` key -> autorate
- Both present -> error (ambiguous config)
- Neither present -> error with message: "could not determine config type" and suggestion to use `--type autorate|steering`
- `--type` flag overrides auto-detection entirely when provided (authoritative, not fallback)
- Detection result shown silently in summary line: `Result: PASS (autorate config)` — no separate "Detected:" banner

### Steering cross-config validation
- Own category section: `=== Cross-config Checks ===` (separate from Cross-field Checks)
- Check that `topology.primary_wan_config` file exists — WARN (not ERROR) if missing, since tool may run on dev machine without other config
- If referenced config exists, parse it and verify `wan_name` matches `topology.primary_wan` — ERROR on mismatch
- Depth: file existence + wan_name match only — do NOT run full autorate validation on the referenced file
- Include steering-specific cross-field checks: confidence threshold ordering (recovery_threshold < steer_threshold), measurement.interval_seconds range, state.history_size range

### JSON output mode
- `--json` flag replaces text output entirely — only JSON goes to stdout, no text
- Structure: grouped by category (mirrors text output structure)
- Top-level fields: `config_type`, `result`, `errors` count, `warnings` count, `categories` object
- `categories` object: keys are category names, values are arrays of check result objects
- Each check result: `field`, `severity` (pass/warn/error), `message`, `suggestion` (present when available, omitted when null)
- Include ALL results (pass, warn, error) — CI scripts can filter with jq
- Exit codes unchanged when --json is used (0=pass, 1=errors, 2=warnings-only)
- `--json` and `--quiet` are independent: --json always includes all results regardless of -q

### Claude's Discretion
- Internal refactoring of check_config.py to support dual config types (validator registry, dispatch pattern, etc.)
- KNOWN_STEERING_PATHS set construction (analogous to KNOWN_AUTORATE_PATHS)
- Steering deprecated parameter detection (mode.cake_aware, legacy cake_state_sources/cake_queues keys)
- JSON serialization approach (json.dumps vs custom encoder)
- How to load SteeringConfig.SCHEMA without triggering daemon side effects

</decisions>

<specifics>
## Specific Ideas

- Must never reject currently-working production configs — backward compat is primary constraint
- Zero new dependencies — reuse json stdlib, existing patterns from Phase 81
- Cross-config wan_name mismatch is the single most common steering misconfiguration — catching this is the key value of CVAL-09
- JSON output should be pipe-friendly: `wanctl-check-config --json steering.yaml | jq .result`

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `check_config.py` (787 lines): Complete autorate validator with Severity enum, CheckResult dataclass, format_results(), create_parser(), main()
- `SteeringConfig` (steering/daemon.py:131): Has SCHEMA list with topology, mangle_rule, measurement, state, thresholds fields
- `SteeringConfig._load_*` methods: Contain cross-field validation logic (confidence threshold ordering, deprecated param detection) that can be extracted
- `KNOWN_AUTORATE_PATHS` set: Pattern for unknown key detection — need equivalent KNOWN_STEERING_PATHS
- `_walk_leaf_paths()`, `_walk_string_values()`: Generic helpers already work for any config dict

### Established Patterns
- Category validators return `list[CheckResult]` — new steering validators follow same signature
- `validate_field()` from config_base.py works with any SCHEMA list (autorate or steering)
- `deprecate_param()` pattern used by SteeringConfig for legacy keys (spectrum -> primary)
- CLI entry points in pyproject.toml console_scripts

### Integration Points
- `main()` in check_config.py needs dispatch: detect type -> run appropriate validators
- New `--type` and `--json` arguments added to `create_parser()`
- `format_results()` needs a parallel `format_results_json()` function
- Import SteeringConfig.SCHEMA (class attribute access only, no instantiation)

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 82-steering-config-output-modes*
*Context gathered: 2026-03-12*
