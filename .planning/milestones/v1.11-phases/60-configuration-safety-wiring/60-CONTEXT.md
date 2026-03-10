# Phase 60: Configuration + Safety + Wiring - Context

**Gathered:** 2026-03-09
**Status:** Ready for planning

<domain>
## Phase Boundary

WAN-aware steering is fully wired end-to-end in the steering daemon, controlled by YAML configuration, and ships disabled by default. Adds `wan_state:` config section with schema validation, 30s startup grace period, feature toggle, and `wan_override` for optional WAN-solo failover.

</domain>

<decisions>
## Implementation Decisions

### Weight Tuning Guardrails
- Raw weight numbers exposed in config (`red_weight: 25`)
- `soft_red_weight` is NOT independently configurable — derived as `red_weight * 0.48` (matches CAKE SOFT_RED:RED ratio)
- Weights clamped to `steer_threshold - 1` by default at validation time
- Clamping produces a startup warning: "red_weight clamped to {max} (must be < steer_threshold)"
- Defaults: `red_weight: 25` → derived `soft_red_weight: 12`

### WAN Override (solo-trigger)
- New boolean: `wan_override: false` by default
- When `true`: removes weight ceiling, `red_weight` >= `steer_threshold` is allowed
- Enables WAN RED alone to trigger failover (hysteresis from autorate streak counters + steering's `sustain_duration_sec`)
- Startup warning when enabled: "WAN override active — WAN RED can trigger failover independently of CAKE signals"
- `wan_override: true` + `enabled: false` → validation warning ("override has no effect when disabled")
- FUSE-03 unchanged — describes default behavior; override is explicit opt-out

### Config Validation Behavior
- Invalid `wan_state:` section → warn + disable WAN awareness feature (rest of steering runs normally)
- Field-level strictness: wrong type → disable feature; out-of-range value → clamp to default with warning
- Unknown keys inside `wan_state:` → warn about unrecognized keys (typo detection)
- Validation uses existing `validate_schema()` framework from `config_base.py`

### Disabled-Mode Depth
- When `wan_state.enabled: false`: read WAN zone from state file but don't use in scoring or recovery gate
- Zero additional I/O cost — zone is in same `safe_json_load_file()` call already performed for baseline RTT
- Enables health endpoint (Phase 61) to show "WAN zone: available but disabled" for staged rollout verification
- Single startup log line: "WAN awareness: disabled (enable via wan_state.enabled)"

### Grace Period Behavior
- 30 seconds after daemon start, WAN signal is read but not used in scoring or recovery gate
- Same read-but-don't-use pattern as disabled mode during the grace window
- Health endpoint (Phase 61) can show "grace period active, current zone: RED"
- Grace period restarts on every daemon restart (not persistent across restarts)

### Startup Logging
- `enabled: false` → "WAN awareness: disabled (enable via wan_state.enabled)"
- `enabled: true` → "WAN awareness: enabled (grace period: 30s, red_weight: 25, wan_override: false)"
- `enabled: true` but no autorate state file → one-time warning: "WAN awareness enabled but autorate state file not found"

### Claude's Discretion
- Config key naming within `wan_state:` section (e.g., `red_weight` vs `wan_red_weight`)
- How grace period timer is implemented (timestamp comparison, cycle counter, etc.)
- Where in the code the enabled/grace checks go (daemon level vs confidence module)
- How derived `soft_red_weight` rounding is handled
- Schema field spec ordering and validation message wording
- Test structure and organization

</decisions>

<specifics>
## Specific Ideas

- User wants `wan_override` as explicit boolean rather than allowing weight values to implicitly unlock solo-trigger behavior — intent must be unmistakable in config
- Keep config patterns consistent between daemons where possible (same `sustain_duration_sec` hysteresis applies to WAN-triggered steering)

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `BaseConfig` + `SCHEMA` + `_load_specific_fields()` at `config_base.py:211-464`: Config loading framework — add `wan_state` section loading
- `validate_schema()` at `config_base.py:155-208`: Schema validation with dot-notation, type/range checks — add `wan_state.*` field specs
- `ConfidenceWeights` at `steering_confidence.py:27-64`: Currently class-level constants — replace WAN_RED/WAN_SOFT_RED with config-driven values
- `ConfidenceSignals.wan_zone` at `steering_confidence.py:72-90`: Already wired from Phase 59 — gate with enabled/grace checks
- `BaselineRTTLoader.load_baseline_rtt()` at `steering/daemon.py:575-618`: Already returns `(baseline_rtt, wan_zone)` tuple from Phase 59
- `SteeringDaemon._wan_zone` at `steering/daemon.py:746`: Instance attribute already stores zone — read-but-don't-use pattern builds on this

### Established Patterns
- Feature toggle: `mode.use_confidence_scoring` gates `ConfidenceController` init (daemon.py:720) — same pattern for `wan_state.enabled`
- Config section loading: `_load_specific_fields()` loads in dependency order (daemon.py:374-404) — add `wan_state` after confidence
- Schema constants: `SCHEMA` class attribute lists field specs (daemon.py:137-165) — extend with `wan_state.*` fields
- Staleness thresholds: `STALE_WAN_ZONE_THRESHOLD_SECONDS = 5` already exists (daemon.py:565) — make configurable via `wan_state.staleness_threshold_sec`

### Integration Points
- `SteeringConfig._load_specific_fields()`: Add `wan_state` section parsing after confidence config
- `SteeringConfig.SCHEMA`: Add `wan_state.enabled`, `wan_state.red_weight`, `wan_state.staleness_threshold_sec`, `wan_state.grace_period_sec`, `wan_state.wan_override`
- `ConfidenceWeights`: Replace class constants with config-driven values passed from SteeringConfig
- `compute_confidence()`: Check enabled + grace period before applying WAN weight
- `update_recovery_timer()`: Check enabled + grace period before applying WAN recovery gate
- `SteeringDaemon.__init__()`: Initialize grace period timer, store wan_state config
- Steering YAML config files: Add `wan_state:` section with all fields

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 60-configuration-safety-wiring*
*Context gathered: 2026-03-09*
