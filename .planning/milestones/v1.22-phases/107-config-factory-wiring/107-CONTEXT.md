# Phase 107: Config & Factory Wiring - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire LinuxCakeBackend into the config system and factory. Operators set `router_transport: "linux-cake"` in YAML, the `get_backend()` factory creates a LinuxCakeBackend, and `wanctl-check-config` validates linux-cake specific settings. No WANController/SteeringDaemon integration (that requires deeper wiring — Phase 108 for steering). No VM setup (Phase 109).

</domain>

<decisions>
## Implementation Decisions

### Config Field Naming
- **D-01:** Extend existing `router_transport` field to accept `"linux-cake"` as a third value alongside `"rest"` and `"ssh"`. No new transport field — reuse the established pattern.
- **D-02:** Bridge interface names go under the `cake_params` YAML section (created in Phase 106): `upload_interface: "eth0"` and `download_interface: "eth1"`.
- **D-03:** The `cake_params` section is only required when `router_transport: "linux-cake"`. When transport is `rest` or `ssh`, its absence is not an error.

### Factory Wiring
- **D-04:** Add `"linux-cake"` branch to `get_backend()` in `backends/__init__.py`. When selected, creates `LinuxCakeBackend.from_config(config)`.
- **D-05:** `LinuxCakeBackend.from_config(config)` reads `cake_params.upload_interface` or `cake_params.download_interface` from config to set the interface. Direction is determined by the daemon context (upload vs download instance).
- **D-06:** Factory change is surgical — no changes to WANController, SteeringDaemon, or any existing code paths. Existing `routeros` path is unchanged.

### check-config Validations
- **D-07:** When `router_transport: "linux-cake"`, `wanctl-check-config` validates:
  1. `cake_params` section exists and is a dict
  2. `upload_interface` and `download_interface` are specified (required strings)
  3. `overhead` keyword is valid (one of: docsis, bridged-ptm, ethernet, raw)
  4. `tc` binary exists at `/usr/sbin/tc` or in PATH
- **D-08:** Interface existence checks (does the NIC exist on the system) are NOT performed — `check-config` is an offline validator. Runtime checks happen in `test_connection()`.
- **D-09:** Existing check-config validations for `rest`/`ssh` transport are unchanged.

### Claude's Discretion
- `from_config()` parameter extraction patterns
- Test fixture structure for config validation tests
- Error message wording

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Backend & Factory
- `src/wanctl/backends/__init__.py` — `get_backend()` factory function (add linux-cake branch)
- `src/wanctl/backends/linux_cake.py` — `LinuxCakeBackend` class with `from_config()` classmethod
- `src/wanctl/backends/base.py` — RouterBackend ABC
- `src/wanctl/backends/routeros.py` — RouterOSBackend.from_config() reference pattern

### Config System
- `src/wanctl/autorate_config.py` — Config class, SCHEMA, `_load_specific_fields()`
- `src/wanctl/config_base.py` — BaseConfig, validate_schema(), validate_field()
- `src/wanctl/cake_params.py` — CakeParamsBuilder (Phase 106 output, reads cake_params section)

### Validation CLI
- `src/wanctl/check_config.py` — wanctl-check-config CLI with category-based validation
- `src/wanctl/config_validation_utils.py` — CheckResult, Severity, validation helpers

### Tests
- `tests/test_backends.py` — Existing backend factory tests
- `tests/test_check_config.py` — Existing check-config validation tests

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `get_backend()` factory — add one elif branch for `"linux-cake"`
- `CheckResult`/`Severity` data model — reuse for linux-cake validation results
- `_check_unknown_keys()` pattern in check_config — reuse for cake_params section validation
- `LinuxCakeBackend.from_config()` — already exists but may need interface parameter wiring

### Established Patterns
- Config transport selection: `router_transport` field, defaults to `"rest"`
- Factory creates backend from config object, not raw dict
- check-config categories: schema, cross-field, unknown-keys, paths, env-vars, deprecated
- CheckResult with severity + suggestion + category

### Integration Points
- `get_backend()` in `backends/__init__.py` — the single change point for factory routing
- `check_config.py` — add linux-cake category validators
- `autorate_config.py` Config class — may need `cake_params` section loading

</code_context>

<specifics>
## Specific Ideas

- YAML example for linux-cake config:
  ```yaml
  router_transport: "linux-cake"
  cake_params:
    upload_interface: "enp8s0"
    download_interface: "enp9s0"
    overhead: "docsis"
    memlimit: "32mb"
    rtt: "100ms"
  ```
- `get_backend()` currently checks `config.router.get("type", "routeros")` — may need to also check `router_transport`
- check-config auto-detects config type (autorate vs steering) — linux-cake is always autorate

</specifics>

<deferred>
## Deferred Ideas

- WANController integration with LinuxCakeBackend — requires deeper wiring than factory alone
- Steering daemon dual-backend config — Phase 108 scope
- Config migration tool from MikroTik to linux-cake YAML — nice-to-have, not required

</deferred>

---

*Phase: 107-config-factory-wiring*
*Context gathered: 2026-03-24*
