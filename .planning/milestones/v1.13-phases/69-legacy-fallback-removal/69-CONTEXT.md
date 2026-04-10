# Phase 69: Legacy Fallback Removal - Context

**Gathered:** 2026-03-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace silent config parameter fallbacks with clear deprecation warnings. Remove legacy validation code from config_validation_utils.py. Resolve RTT-only mode disposition (retire it). Update calibrate.py to generate modern param names.

</domain>

<decisions>
## Implementation Decisions

### Error Severity
- Warning + continue: daemon stays running, legacy value is translated to modern equivalent
- No escalation path — warnings are permanent, no future hard error planned
- Consistent with existing warn+disable pattern (WAN config validation)

### Deprecation Helper
- Centralized helper function with optional transform callback (e.g., alpha_baseline -> time_constant conversion)
- Location: Claude's discretion (config_validation_utils.py or config_base.py both reasonable)
- Helper supports value translation: `deprecate_param(config, old_key, new_key, transform_fn=None)`
- Log frequency: Claude's discretion (every startup vs log-once)

### Warning Message Format
- Claude's discretion to match existing logging style
- Must include: deprecated param name, modern replacement name, translated value

### RTT-Only Mode (LGCY-07)
- Retired: CAKE three-state model is always active, no RTT-only mode
- Remove `cake_aware` key from configs/steering.yaml
- If `cake_aware` appears in config at runtime: warn + ignore (consistent with other legacy params)
- Document retirement in CONFIG_SCHEMA.md and CHANGELOG.md

### Legacy State Names
- Existing normalization (SPECTRUM_GOOD/WAN1_GOOD/WAN2_GOOD -> state_good) already correct
- Warn-once + normalize pattern already implemented (daemon.py:862-884)
- Just verify test coverage exists for this path
- Also check for degraded state equivalent (SPECTRUM_DEGRADED etc.) — include if found

### Scope Boundary
- `floor_mbps` (single floor) stays — legitimate feature, NOT legacy (Category C per Phase 67)
- `bad_samples`/`good_samples` removed from validate_sample_counts() signature
- `calibrate.py` updated to generate `baseline_time_constant_sec`/`load_time_constant_sec` instead of `alpha_baseline`/`alpha_load`

### LGCY-04 Removal Scope
- Remove bad_samples/good_samples from validate_sample_counts() signature
- Return type changes from tuple[int, int, int, int] to tuple[int, int] (red_required, green_required)
- Update all callers to expect 2-tuple
- Claude does thorough pass for any other legacy references/docstrings in the file
- Update test_config_validation_utils.py tests to match new signature

### Deployment
- Update configs/steering.yaml in repo only — deployment happens separately via deploy.sh
- Claude verifies deploy.sh includes steering.yaml in file list (sanity check)

### Testing Strategy
- One test per legacy param: asserts both warning logged AND translated value correct (~8 parametrized cases)
- Integration smoke test: load config with ALL legacy params, prove daemon starts, all warnings fire
- Migrate any existing test_config_edge_cases.py tests that break due to changes
- Tests for legacy state name normalization verified/added

### Claude's Discretion
- Deprecation helper location (config_validation_utils.py vs config_base.py)
- Warning message exact format (structured vs table)
- Log frequency (every startup vs log-once via set tracking)
- Whether to clean up legacy references in docstrings found during implementation

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- warn+disable pattern in WAN config validation (steering/daemon.py) — model for warn+continue
- _legacy_state_warned set (daemon.py:861) — model for log-once tracking
- ConfigValidationError in config_base.py — existing error type (not used for warnings, but available)

### Established Patterns
- BaseConfig._load_specific_fields() — each daemon subclass loads its config here, natural injection point for deprecation checks
- validate_identifier() — existing config value sanitization pattern in steering config
- Rate-limited warnings — used throughout for 20Hz cycle rate (not needed at startup, but pattern exists)

### Integration Points
- autorate_continuous.py:365-396 — alpha_baseline/alpha_load fallback chain (MODIFY)
- steering/daemon.py:186-190 — cake_state_sources.spectrum fallback (MODIFY)
- steering/daemon.py:213,218 — spectrum_download/spectrum_upload fallback (MODIFY)
- config_validation_utils.py:309-369 — validate_sample_counts() (MODIFY)
- steering/daemon.py:862-884 — legacy state name normalization (VERIFY)
- calibrate.py:~548-560 — config generation output (MODIFY)
- configs/steering.yaml — remove cake_aware key (MODIFY)

### Legacy Param Inventory
| Legacy Param | Modern Replacement | Location | Transform |
|---|---|---|---|
| alpha_baseline | baseline_time_constant_sec | autorate_continuous.py | interval/alpha |
| alpha_load | load_time_constant_sec | autorate_continuous.py | interval/alpha |
| cake_aware | (retired) | steering config | warn+ignore |
| spectrum_download | primary_download | steering/daemon.py | identity |
| spectrum_upload | primary_upload | steering/daemon.py | identity |
| cake_state_sources.spectrum | cake_state_sources.primary | steering/daemon.py | identity |
| bad_samples | red_samples_required | config_validation_utils.py | identity |
| good_samples | green_samples_required | config_validation_utils.py | identity |

</code_context>

<specifics>
## Specific Ideas

- Follow the exact warn+disable pattern already used for invalid WAN config — proven in production
- Phase 67 AUDIT.md has the complete legacy parameter inventory — use as authoritative source
- The legacy state name handling (SPECTRUM_GOOD) is already production-proven, just needs test verification

</specifics>

<deferred>
## Deferred Ideas

- Broader legacy state name cleanup beyond good/degraded — if other patterns exist, capture for Phase 70
- calibrate.py could also generate state-based floors (floor_green_mbps etc.) — not in Phase 69 scope

</deferred>

---

*Phase: 69-legacy-fallback-removal*
*Context gathered: 2026-03-11*
