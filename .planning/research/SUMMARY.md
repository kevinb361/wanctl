# Project Research Summary

**Project:** wanctl v1.16 — Validation & Operational Confidence
**Domain:** Config validation CLI, CAKE qdisc auditing, read-only router integration probes for production dual-WAN controller
**Researched:** 2026-03-12
**Confidence:** HIGH

## Executive Summary

v1.16 is an operational confidence milestone for a mature, production-grade codebase (20,140 LOC, 2,666 tests, 16 milestones shipped). The core goal is to give operators tools to verify that their wanctl config files are valid and that the router's CAKE queue configuration actually matches what wanctl expects — before problems surface at runtime. Unlike previous milestones that added new daemon features, this milestone adds only CLI tools and minor daemon startup hardening. No new runtime dependencies are required: the existing `BaseConfig`, `validate_schema()`, `RouterOSREST`, and `argparse`/`tabulate` stack is fully sufficient.

The recommended approach is two standalone CLI tools (`wanctl-check-config` and `wanctl-check-cake`) that reuse existing infrastructure without modifying daemon behavior. `wanctl-check-config` is offline — it validates YAML structure, types, value ranges, cross-field ordering, and file paths without touching the router. `wanctl-check-cake` connects to the router read-only, comparing queue tree and queue type parameters against config expectations. Both tools follow the `wanctl-history` CLI pattern (argparse, tabulate, --json, exit codes) and produce structured `ValidationResult` objects that are collected before reporting — so operators see all problems at once, not one at a time.

The dominant risk is backward compatibility: new validation rules must not reject existing production configs. The three production YAML files (`spectrum.yaml`, `att.yaml`, `steering.yaml`) evolved over 16 milestones and contain patterns new validators must tolerate (unknown keys, `${ROUTER_PASSWORD}` env var syntax, optional fields with legacy fallbacks). Every new validation rule must be warn-by-default, not fail-by-default. A second critical risk is ensuring router probes never enter the daemon startup path in a blocking or crash-inducing way — the 30s systemd WatchdogSec budget already has limited headroom with the 20s startup maintenance window.

## Key Findings

### Recommended Stack

The existing stack needs zero new dependencies. `BaseConfig.validate_schema()` already provides typed multi-error collection; `RouterOSREST` already handles REST GET queries with auth and caching; `argparse` and `tabulate` are already used by `wanctl-history`. The only new infrastructure needed is a `ValidationResult` dataclass (CheckStatus: PASS/WARN/FAIL/SKIP, plus category, check name, message, expected, actual fields) added to `config_base.py`, and two new top-level modules registered as console_scripts.

**Core technologies:**
- `config_base.py` (existing): BaseConfig, validate_schema(), validate_field() — the validation framework to extend, not replace
- `config_validation_utils.py` (existing): Domain cross-field validators (validate_bandwidth_order, validate_threshold_order, validate_alpha, deprecate_param) — called from the CLI tool, not reimplemented
- `routeros_rest.py` (existing): RouterOSREST GET requests — add one new `get_queue_type()` method for `/rest/queue/type`; same pattern as existing `get_queue_stats()`
- `argparse` (stdlib): CLI entry point — consistent with existing `wanctl-history`; no click or typer needed
- `tabulate` (existing dep): CLI output formatting — already in pyproject.toml; sufficient for check results

Pydantic, cerberus, jsonschema, routeros-api, click, and rich were all explicitly evaluated and rejected. Adding any of them would require rewriting existing infrastructure for no functional gain.

### Expected Features

**Must have (table stakes):**
- `wanctl-check-config <file>` standalone CLI — validates both autorate and steering configs offline, no router needed
- Structured error collection (all errors reported, not just first) — using collect-then-report pattern
- Cross-field semantic validation — floor ordering (`floor_red <= floor_soft_red <= floor_yellow <= floor_green <= ceiling`), threshold ordering, `steer_threshold > recovery_threshold`
- File/permission checks — log dirs, state dirs, lock dirs, SSH key path (all checked before daemon discovers them at runtime)
- Environment variable resolution check — `${ROUTER_PASSWORD}` treated as valid syntax, not a missing value
- Exit codes for CI/CD — 0=pass, 1=fail, 2=warn-only
- Human-readable output with severity levels (ERROR/WARNING/INFO)
- `wanctl-check-cake` CLI — read-only router queue audit comparing config expectations vs router reality

**Should have (differentiators):**
- Config type auto-detection (autorate vs steering) — detect from YAML keys, no `--type` flag required
- Mangle rule existence check (steering configs) — verify the steering rule exists on the router and matches `mangle_rule.comment`
- Config diff output — "max-limit: 940Mbps (config) vs 500Mbps (router)" side-by-side comparison
- JSON output mode (`--json`) — for scripting and CI pipelines, following `wanctl-history` pattern
- Deprecated parameter report — surface `deprecate_param()` warnings prominently in CLI output, not buried in daemon logs
- Optional router connectivity probe in `check-config` (`--probe` flag) — separated from offline validation

**Defer (v2+):**
- Config file generation/wizard (`wanctl-calibrate` already handles initial setup)
- Schema migration tooling (no v2.0 schema defined, YAGNI)
- Auto-fix/auto-repair (too risky for production network config)
- Full network topology discovery (out of scope — probe only the resources wanctl manages)
- Interactive TUI mode (plain text + JSON is sufficient for pipe-friendly tooling)

### Architecture Approach

The new features are read-only inspection tools — one-shot CLI commands that load config, optionally probe the router, collect results, and exit. They never run as daemons. The architecture is two new flat modules (`check_config.py`, `check_cake.py`) following the established `history.py`/`calibrate.py` pattern, registered in `pyproject.toml` as console_scripts. A `ValidationResult` dataclass added to `config_base.py` is the shared result type. Daemon startup keeps its existing fail-fast behavior (raise ConfigValidationError); the CLI tools use a parallel collect-then-report path that calls the same underlying validators but wraps results differently.

**Major components:**
1. `check_config.py` (new) — CLI entry point: YAML parse -> schema validation -> cross-field checks -> file/permission checks -> optional probe -> collect results -> report with exit code
2. `check_cake.py` (new) — CLI entry point: config load -> router client -> `/queue/tree` query -> `/queue/type` query -> comparison against config -> report with exit code
3. `config_base.py` (modified, additive) — adds `ValidationResult` and `CheckStatus` dataclass; no changes to existing validation behavior
4. `config_validation_utils.py` (minor modification) — add any cross-field validators not yet present; existing validators called as-is

Key pattern distinction: `get_router_client()` (not `get_router_client_with_failover()`) for CLI tools. A one-shot probe should report clearly if the configured transport fails, not silently fall over. FailoverRouterClient is for long-running daemons.

### Critical Pitfalls

1. **New validation rejects existing production configs** — use warn-by-default for all new rules; never add "reject unknown keys" logic; run against actual `/etc/wanctl/*.yaml` before merging; use `--strict` flag for opt-in enforcement. Recovery is low-cost (remove the offending rule) but production outage while containers fail to restart is HIGH-pain.

2. **Router probes added to daemon startup path** — probes must be CLI tools only or post-startup advisory checks with a 3s timeout max; never blocking at startup; the 30s WatchdogSec budget with 20s startup maintenance already leaves only ~5-9s of headroom. Probe timeout default of 15s in the startup path would exceed the budget.

3. **Router probe accidentally writes to router** — all probe HTTP requests must use GET; create a read-only wrapper around RouterOSREST with no POST/PATCH methods; assert HTTP method is GET in tests. Recovery if router state is modified: HIGH cost (may require manual router config restore).

4. **CAKE audit queries only `/queue/tree`, missing CAKE parameters** — RouterOS has a two-level queue model: tree entries reference queue types, and CAKE parameters (cake-bandwidth, cake-rtt, cake-flowmode, etc.) live on `/queue/type`, not `/queue/tree`. The audit needs both queries. The existing `CakeStatsReader` only reads counters from the tree, not CAKE config from the type.

5. **Unit mismatch in CAKE comparison** — config stores ceiling in Mbps, router returns `max-limit` in bps (as a string like `"940000000"`); CAKE RTT may be a preset name (`internet`) or raw ms value; define an explicit conversion table before writing any comparison logic.

## Implications for Roadmap

Based on research, a 4-phase structure is recommended. Each phase delivers independently useful functionality and has a clear boundary.

### Phase 1: Config Validation Foundation
**Rationale:** Entirely offline, no router dependency. Establishes the `ValidationResult` type and collect-then-report pattern that all subsequent phases depend on. Backward compatibility must be the primary constraint — establish it here before any validation logic is written.
**Delivers:** `wanctl-check-config` entry point for autorate configs; schema + cross-field + file checks; exit codes 0/1/2; structured text output with severity levels; `ValidationResult`/`CheckStatus` dataclass in `config_base.py`
**Addresses (FEATURES.md):** All table-stakes features except steering config support and JSON output
**Avoids (PITFALLS.md):** P1 (backward compat regression), P5 (incomplete schema coverage), P10 (CLI cannot resolve env var passwords), P11 (log noise in daemon)

### Phase 2: Steering Config Support + Deprecated Param Report
**Rationale:** Autorate and steering configs have different schemas; supporting both in a single CLI tool requires config type auto-detection. Deprecated param surfacing reuses existing `deprecate_param()` with output routing changes — low complexity, high operator value. JSON output and steering cross-validation complete the CLI feature set before moving to router-dependent work.
**Delivers:** Steering config validation in `check-config`; config type auto-detection (from YAML keys); deprecated parameter report in CLI output; `--json` mode; cross-config steering cross-validation (topology.primary_wan_config resolves and `wan_name` matches `topology.primary_wan`)
**Addresses (FEATURES.md):** Config type auto-detection, deprecated param report, JSON output, steering config coverage
**Avoids (PITFALLS.md):** P1 (steering configs must also pass unchanged), P5 (schema coverage for steering-specific fields)

### Phase 3: CAKE Qdisc Audit
**Rationale:** Router-dependent phase comes after the offline validation foundation is solid. Requires understanding the RouterOS two-level queue model and unit conversion. Uses `ValidationResult` from Phase 1. CAKE parameter names in REST JSON should be verified against the live RB5009 early in this phase.
**Delivers:** `wanctl-check-cake` CLI; REST connectivity probe; queue tree audit (queue exists, uses CAKE type, max-limit matches config ceiling); queue type audit (CAKE parameters vs config expectations); mangle rule check for steering configs; config diff output (expected vs actual per field)
**Addresses (FEATURES.md):** `wanctl-check-cake` table stake, router connectivity probe, CAKE type verification, mangle rule check, config diff differentiator
**Avoids (PITFALLS.md):** P3 (read-only probes only — GET requests enforced architecturally), P4 (unit mismatch — explicit conversion table), P6 (probe failure never blocks daemon), P7 (both `/queue/tree` and `/queue/type` queried)

### Phase 4: Integration Probes + Daemon Startup Hardening
**Rationale:** Polish and end-to-end coverage. Adding environment checks to daemon startup (`_validate_environment()`) makes config problems fail fast at startup rather than mid-cycle. State file and SQLite integrity checks complete the operational confidence picture. This phase is last because daemon startup modifications are the highest-risk changes — leaving them until validation patterns are proven by CLI tools is the right order.
**Delivers:** `_validate_environment()` in both daemon Config classes (log dirs, state dirs, lock dirs, SSH key — fast <50ms); state file consistency check (valid JSON, expected keys, freshness — via health endpoint when daemon is running); SQLite PRAGMA integrity_check; optional `wanctl check-all` convenience wrapper
**Addresses (FEATURES.md):** SQLite integrity check, health endpoint probe, state file check, daemon startup hardening
**Avoids (PITFALLS.md):** P2 (environment checks are fast, not router probes), P8 (state file race — use health endpoint when daemon is running), P9 (coverage stays >=90%)

### Phase Ordering Rationale

- Phase 1 before Phase 2: `ValidationResult` and collect-then-report pattern must exist before adding more validation categories
- Phase 2 before Phase 3: Steering config support and JSON output are needed before `check-cake` (which also produces steering-specific results in JSON)
- Phase 3 before Phase 4: Router probe infrastructure establishes the read-only probe pattern; startup hardening reuses it conceptually but does not depend on it technically
- Phase 4 last: Daemon startup modifications touch production-critical paths; they should be the last change after validation patterns are battle-tested by CLI tools
- Daemon code stays frozen through Phases 1-3: zero daemon changes needed; Phase 4 adds only a new method call in Config.__init__, not changes to existing logic

### Research Flags

Phases with standard patterns (skip `/gsd:research-phase`):
- **Phase 1:** All patterns derived from existing codebase. BaseConfig, validate_schema, argparse, tabulate — established, no novel territory.
- **Phase 2:** Same infrastructure, additive only. Config type detection is key inspection. deprecate_param output routing is minor.
- **Phase 4:** `_validate_environment()` follows established BaseConfig pattern. sqlite3 PRAGMA is stdlib.

Phases likely needing deeper research during planning:
- **Phase 3:** RouterOS REST API response format for `/rest/queue/type` should be verified against the live RB5009 before finalizing comparison logic. CAKE parameter names in REST JSON (hyphenated vs underscored field names, presence of units in values like `"100ms"` vs `100`) are documented in MikroTik docs but the exact GET response format needs live confirmation. Record real responses as test fixtures early in this phase.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Zero new deps confirmed. Explicit rejection of pydantic, cerberus, routeros-api, click, rich. Every needed capability mapped to an existing file and function. |
| Features | HIGH | Grounded in codebase analysis of existing validate_config_mode, REST client methods, and wanctl-history patterns. All must-have features map to already-existing infrastructure. |
| Architecture | HIGH | All patterns derived from existing codebase. CLI tool pattern (history.py, calibrate.py) is established. ValidationResult is a simple dataclass addition. Anti-patterns explicitly documented with specific failure modes. |
| Pitfalls | HIGH | 12 pitfalls documented with specific code locations, warning signs, and recovery costs. Grounded in 16 milestones of accumulated system knowledge about production constraints (WatchdogSec, startup budget, flash wear, circuit breaker). |

**Overall confidence:** HIGH

### Gaps to Address

- **RouterOS `/rest/queue/type` GET response format:** CAKE parameter names confirmed in MikroTik docs but exact JSON key format in a GET response (hyphenated vs underscored, unit encoding in string values) should be verified against the live RB5009 during Phase 3 planning. Record a real response early in implementation and use it as the canonical test fixture.
- **Production config backward compatibility:** Research identifies this as the primary risk but cannot fully enumerate all edge cases in production YAML without running the validator. Phase 1 must include a validation run against actual `/etc/wanctl/*.yaml` before considering the phase complete.
- **Startup budget measurement:** The 30s WatchdogSec limit and 20s startup maintenance budget are documented, but actual headroom is not measured. Phase 4 should include a startup timing measurement before and after adding `_validate_environment()` to verify the headroom assumption.

## Sources

### Primary (HIGH confidence)
- Codebase: `src/wanctl/config_base.py` — BaseConfig, validate_schema, validate_field, SCHEMA pattern, ConfigValidationError
- Codebase: `src/wanctl/config_validation_utils.py` — validate_bandwidth_order, validate_threshold_order, deprecate_param, validate_alpha
- Codebase: `src/wanctl/autorate_continuous.py` — Config class, _load_specific_fields, validate_config_mode, startup sequence, max_seconds=20 budget
- Codebase: `src/wanctl/routeros_rest.py` — RouterOSREST, _request, GET/PATCH usage, get_queue_stats pattern
- Codebase: `src/wanctl/router_client.py` — get_router_client, FailoverRouterClient, _resolve_password
- Codebase: `src/wanctl/steering/daemon.py` — SteeringConfig, SCHEMA, _load_specific_fields
- Codebase: `src/wanctl/history.py`, `calibrate.py` — CLI tool patterns (argparse, tabulate, --json, exit codes)
- Codebase: `systemd/wanctl@.service` — WatchdogSec=30s, StartLimitBurst=5/300s, EnvironmentFile semantics
- Codebase: `src/wanctl/storage/maintenance.py` — run_startup_maintenance, watchdog_fn, max_seconds pattern
- [MikroTik CAKE documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/196345874/CAKE) — CAKE parameters: cake-bandwidth, cake-rtt, cake-diffserv, cake-flowmode, cake-overhead-scheme
- [MikroTik REST API documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/47579162/REST+API) — GET=read-only, POST executes commands, 60s default timeout, JSON response format
- [MikroTik Queues documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/328088/Queues) — queue tree vs queue type model, CAKE as queue type definition

### Secondary (MEDIUM confidence)
- [Queue Tree Properties Reference (mikrotikdocs.fyi)](https://mikrotikdocs.fyi/queues/queue-tree/) — full queue tree property list including counters
- [Python argparse documentation](https://docs.python.org/3/library/argparse.html) — subcommand and argument patterns
- [tc-cake(8) Linux manual page](https://www.man7.org/linux/man-pages/man8/tc-cake.8.html) — CAKE parameter semantics and preset names

### Tertiary (LOW confidence — verify during Phase 3)
- RouterOS REST JSON field names for `/rest/queue/type` CAKE parameters — hyphen vs underscore formatting, unit encoding in string values, exact response structure needs live router verification

---
*Research completed: 2026-03-12*
*Ready for roadmap: yes*
