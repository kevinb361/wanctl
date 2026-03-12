# Phase 76: Alert Engine & Configuration - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Daemons have a working alert engine that can accept, suppress, and persist alerts -- but no delivery or detection yet. Requirements: INFRA-01 (per-event cooldown), INFRA-02 (YAML config), INFRA-03 (SQLite persistence), INFRA-05 (disabled by default).

</domain>

<decisions>
## Implementation Decisions

### Alert event model
- Three severity levels: `info`, `warning`, `critical`
- Alert type is a free-form string (e.g., `congestion_sustained`, `steering_activated`) -- not a validated enum
- Details field is a structured dict (JSON-serializable key-value pairs), not free-form text
- Core fields per event: timestamp, type, severity, wan, details (dict)

### Cooldown identity
- Cooldown key is the tuple `(type, wan)` -- per-type per-WAN
- Spectrum congestion and ATT congestion cool down independently
- Simultaneous events on both WANs both fire (then both suppressed for their cooldown window)

### Config structure
- Top-level `alerting:` section with `enabled`, `webhook_url`, `default_cooldown_sec`
- Rules are a **map keyed by type name**, not a list
- Per-rule fields: `enabled`, `cooldown_sec` (optional, overrides default), `severity` (required, no default)
- Defaults + per-rule overrides pattern (cooldown inherits from `default_cooldown_sec` if not specified per-rule)
- Example shape:
  ```yaml
  alerting:
    enabled: false
    webhook_url: ""
    default_cooldown_sec: 300
    rules:
      congestion_sustained:
        enabled: true
        cooldown_sec: 600
        severity: critical
      steering_activated:
        enabled: true
        severity: warning
  ```

### Engine placement
- Shared `AlertEngine` class in a common module (new `alert_engine.py` alongside `daemon_utils.py`)
- Each daemon instantiates its own AlertEngine -- no cross-daemon coordination
- Alerts stored in a new `alerts` table in the existing per-daemon MetricsWriter SQLite database
- Reuse MetricsWriter's connection management and WAL mode -- add table via schema extension

### Claude's Discretion
- AlertEngine internal API (method signatures, return types)
- SQLite `alerts` table schema (column names, indexes)
- Config validation implementation details (follows wan_state warn+disable pattern)
- Whether to add SIGUSR1 reload for `alerting.enabled` in this phase or defer to later
- Test structure and fixture approach

</decisions>

<specifics>
## Specific Ideas

- Follow the `wan_state` pattern exactly: disabled by default, warn+disable on invalid config, never crash the daemon
- Reuse `RateLimiter` from `rate_utils.py` as inspiration for cooldown tracking (uses `time.monotonic()`, sliding window)
- Config loading goes through `BaseConfig._load_specific_fields()` in each daemon's config class
- MetricsWriter singleton pattern with `_reset_instance()` for test isolation

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `RateLimiter` in `rate_utils.py`: Sliding window rate limiter with `can_change()`, `record_change()`, `time_until_available()` -- model for cooldown tracking
- `MetricsWriter` in `storage/writer.py`: Singleton with WAL mode, thread-safe writes, batch support -- host for new `alerts` table
- `BaseConfig` in `config_base.py`: YAML loading, BASE_SCHEMA validation, `_load_specific_fields()` extension point
- `config_validation_utils.py`: `deprecate_param()` warn+translate, threshold validators
- `state_utils.py`: `atomic_write_json()`, `safe_json_load_file()` for state persistence

### Established Patterns
- **Warn+disable**: Invalid optional-feature config logs warning and disables feature (wan_state model)
- **Disabled by default**: `wan_state.enabled: false` pattern -- check `config.X is None` to skip feature
- **Singleton with test reset**: `MetricsWriter.__new__()` + `_reset_instance()` class method
- **SIGUSR1 reload**: `signal_utils.py` threading.Event, per-field reload methods in daemon
- **Health endpoint sections**: Feature-gated dict additions to health response JSON

### Integration Points
- Both daemon config classes need `_load_alerting_config()` method
- MetricsWriter needs `alerts` table creation in schema initialization
- AlertEngine instantiated in daemon `__init__`, called from main loop (but no detection logic yet in Phase 76)
- Health endpoint can expose alerting enabled/disabled status

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 76-alert-engine*
*Context gathered: 2026-03-12*
