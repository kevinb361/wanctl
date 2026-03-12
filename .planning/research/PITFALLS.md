# Pitfalls Research: Config Validation, CAKE Audit, and Router Probes

**Domain:** Adding validation, config checking, CAKE qdisc audit, and read-only router integration probes to a production 24/7 dual-WAN controller
**Researched:** 2026-03-12
**Confidence:** HIGH (grounded in codebase analysis of existing config infrastructure, router client layer, systemd integration, and MikroTik RouterOS documentation)
**Focus:** Backward compatibility of new validation, watchdog-safe startup, router probe side effects, CAKE parameter drift detection, test coverage maintenance

---

## Critical Pitfalls

Mistakes that cause daemon startup failures, production outages, or require significant rework.

---

### Pitfall 1: New Validation Rejects Existing Valid Production Configs

**What goes wrong:**
A new validation rule is added (e.g., requiring `schema_version`, enforcing `storage.db_path` format, rejecting unknown keys) that flags the existing production YAML files in `/etc/wanctl/` as invalid. The daemon refuses to start. Since both `cake-spectrum` and `cake-att` containers load config at startup and systemd's circuit breaker (`StartLimitBurst=5/300s`) kicks in after 5 failures, both daemons are bricked until manual intervention.

**Why it happens:**
The production configs (`configs/spectrum.yaml`, `configs/att.yaml`, `configs/steering.yaml`) evolved organically over 16 milestones. They lack `schema_version` fields, contain undocumented parameters (e.g., `fallback_checks.max_fallback_cycles`), and use patterns the new validator may not anticipate (e.g., `${ROUTER_PASSWORD}` environment variable syntax in YAML string fields). The developer writes validation against the example configs but does not test against the actual production files.

**How to avoid:**
- Run the new validator against ALL existing config files before merging: `spectrum.yaml`, `att.yaml`, `steering.yaml`, plus all 6 example configs
- New validations MUST use warn-and-continue, not fail-fast, for the first release. Use the established `deprecate_param()` warn+translate pattern from v1.13
- NEVER add "reject unknown keys" validation. The portable controller architecture means different deployments have different optional sections. Unknown keys must be silently ignored (current behavior)
- Add a `--strict` flag to `wanctl check-config` for explicit strict mode. Default mode warns but does not fail
- Test matrix: valid production config, valid example config, config with unknown keys, config missing optional fields, config with legacy parameters

**Warning signs:**
- Validator tests only use synthetic configs, never real production files
- Any validation rule that uses `required: True` for a field not already in `BASE_SCHEMA` or `Config.SCHEMA`
- Validator raises `ConfigValidationError` in a code path that runs during daemon startup (not just `--validate-config` mode)

**Phase to address:**
Config validation phase (first phase). Must be established with backward compatibility as the primary constraint before any validation logic is written.

---

### Pitfall 2: Validation Adds Latency to Daemon Startup, Exceeds Watchdog Budget

**What goes wrong:**
The new config validation and router probe logic runs during daemon startup before the first watchdog ping. The systemd watchdog (`WatchdogSec=30s`) starts counting from `ExecStart`. The current startup sequence already consumes significant budget: Config loading (~10ms) + storage init (~50ms) + startup maintenance (up to 20s with `max_seconds=20` budget) + lock acquisition (~10ms) + server startup (~50ms). Adding router connectivity probes (REST API call ~50-200ms), CAKE qdisc verification (queue tree print ~50-200ms), and state file consistency checks (~10-50ms) pushes the total past 20.5s, dangerously close to the 30s watchdog limit. Under load or with a slow router response, it exceeds 30s and the daemon is killed by systemd before it starts its first cycle.

**Why it happens:**
The startup maintenance already has a `max_seconds=20` time budget (line 2393 of `autorate_continuous.py`). Developers add router probes after maintenance completes, not realizing the cumulative budget. The router probe timeout defaults to 15s (from `timeout_ssh_command`), and a single retry (via `retry_with_backoff(max_attempts=2)`) could consume 30s+ alone if the router is slow to respond.

**How to avoid:**
- Router probes and CAKE audit MUST NOT run during daemon startup. They are post-startup health checks, not prerequisites
- Config validation (YAML schema, value ranges, floor/ceiling ordering) is fast (<50ms) and CAN run at startup
- Router probes should run as a separate CLI command (`wanctl check-cake`, `wanctl check-router`) or as a post-startup async check (first few cycles)
- If router probes run at startup, they MUST: (a) have a 2-3s timeout max, (b) ping the watchdog between each probe step, (c) be skipped if remaining budget < 5s
- The existing `run_startup_maintenance()` pattern (watchdog_fn + max_seconds) is the correct template for any startup work
- Add an explicit time budget tracker: `startup_deadline = time.monotonic() + 25` (leaving 5s headroom for watchdog)

**Warning signs:**
- Any new code between `Config()` construction and the main `while not is_shutdown_requested()` loop that calls `client.run_cmd()` or makes HTTP requests
- New startup code that does not call `notify_watchdog()` between steps
- Router probe with default 15s timeout in the startup path

**Phase to address:**
Architecture/CLI phase. The decision of "startup validation vs CLI tool" must be made before implementation begins.

---

### Pitfall 3: Router Probes Accidentally Modify Router State

**What goes wrong:**
A CAKE audit probe sends a RouterOS command that unintentionally modifies state. Examples: (a) Using `/queue tree set` instead of `/queue tree print` due to a typo or copy-paste from the existing `_handle_queue_tree_set()` code. (b) Using a POST request to the REST API instead of GET -- RouterOS REST API uses POST for command execution (which can modify state), while GET is read-only. (c) Executing `/queue tree reset-counters` as part of "reading stats" -- this resets cumulative counters that the steering daemon's CakeStatsReader uses for delta calculation, causing a one-cycle data gap. (d) Accidentally enabling/disabling a mangle rule during a "check mangle rule exists" operation.

**Why it happens:**
The existing codebase has both read and write operations in `routeros_rest.py`. Copy-pasting from `_handle_queue_tree_set()` to write a "check queue config" function risks including the PATCH call. The REST API uses different HTTP methods for different operations (GET=read, POST/PATCH=write), and mixing them up has immediate production impact on a live router.

**How to avoid:**
- Router probe module MUST be physically separate from the existing router command modules. New file: `router_probe.py` (or similar). Zero imports from `routeros_rest._handle_queue_tree_set` or `_handle_mangle_rule`
- All probe functions MUST use GET requests only. Create a `RouterProbe` class that wraps `RouterOSREST._request("GET", ...)` and has NO method for POST/PATCH/DELETE
- The probe class should accept the existing REST client but expose ONLY read methods: `get_queue_tree()`, `get_system_resource()`, `get_mangle_rules()`
- Add an assertion or type-level constraint: probe functions take a read-only client interface, not the full `RouterOSREST` class
- NEVER import or call `set_queue_limit()`, `_handle_queue_tree_set()`, or `_handle_mangle_rule()` from probe code
- Code review gate: any probe function that contains the strings "PATCH", "POST", "set", "enable", "disable", "reset-counters" must be rejected

**Warning signs:**
- Probe module imports `from wanctl.routeros_rest import RouterOSREST` and calls methods other than `_request("GET", ...)`
- Probe function has a `json=` parameter in an HTTP request (GET requests use `params=`, not `json=`)
- Tests for probes mock `_request` but do not assert the HTTP method is "GET"

**Phase to address:**
Router probe phase. The read-only constraint must be enforced architecturally, not just by developer discipline.

---

### Pitfall 4: CAKE Audit Compares Wrong Parameters (Config Units vs Router Units)

**What goes wrong:**
The CAKE audit compares config values against router values but uses mismatched units. The config file stores bandwidth in Mbps (`ceiling_mbps: 940`), but RouterOS returns queue `max-limit` in bits per second (`940000000`). The config stores CAKE overhead in bytes, but RouterOS may return it differently. The developer does a string comparison or integer comparison without unit conversion, and the audit reports false positives ("MISMATCH: config=940, router=940000000") or false negatives (comparing different things that happen to have the same number).

CAKE-specific parameters add complexity: RouterOS CAKE properties use names like `cake-bandwidth`, `cake-rtt`, `cake-diffserv`, `cake-flowmode`, `cake-overhead`. The config uses different naming (e.g., `ceiling_mbps` maps to `max-limit`, not `cake-bandwidth`). The CAKE `rtt` parameter on the router is in milliseconds but may be returned as a string like `"100ms"` or `"internet"` (a preset name), while the config has `baseline_rtt_initial: 24`.

**Why it happens:**
The codebase already handles the Mbps-to-bps conversion (`MBPS_TO_BPS = 1_000_000` in `autorate_continuous.py`), but the audit code may not use the same conversion factor. CAKE parameters are not directly mapped to config fields -- `max-limit` is the queue tree bandwidth limit, while `cake-bandwidth` is the CAKE qdisc's own bandwidth parameter (they are different). The developer assumes config `ceiling_mbps` maps to `cake-bandwidth`, but it actually maps to `max-limit` on the queue tree.

**How to avoid:**
- Create an explicit mapping table: `{"config_field": "ceiling_mbps", "router_field": "max-limit", "conversion": lambda x: x * 1_000_000, "unit": "bps"}`
- Document which config fields map to which RouterOS fields. Some have no direct mapping (e.g., `factor_down` is an internal algorithm parameter, not a router setting)
- CAKE qdisc parameters (`cake-bandwidth`, `cake-rtt`, `cake-flowmode`, etc.) are properties of the queue TYPE, not the queue tree entry. They require querying `/queue/type` in addition to `/queue/tree`
- RouterOS returns `max-limit` as a string like `"940000000"` -- always convert to int before comparison
- CAKE `rtt` presets (`internet`, `regional`, etc.) map to specific millisecond values. The audit must handle both preset names and raw ms values
- Test with actual RouterOS responses (record a response from the real router and use it as test fixture)

**Warning signs:**
- Audit function uses `==` comparison without unit conversion
- Audit compares `config.download_ceiling` directly to a router response field (config value is already in bps, but which field?)
- No explicit conversion table or mapping dict in the audit code
- Tests use synthetic router responses with matching units (always passing) instead of realistic responses

**Phase to address:**
CAKE audit phase. The parameter mapping must be defined before any comparison logic is written.

---

### Pitfall 5: `wanctl check-config` Silently Passes Due to Incomplete Schema Coverage

**What goes wrong:**
The `check-config` CLI tool validates the config and reports "Configuration valid" -- but only checks the fields defined in `BaseConfig.BASE_SCHEMA` and `Config.SCHEMA`. Many critical fields are loaded in `_load_specific_fields()` via dict access (e.g., `dl["floor_green_mbps"]`, `thresh["alpha_baseline"]`) and validated ONLY by the downstream validation functions (`validate_bandwidth_order()`, `validate_threshold_order()`). If the YAML has a typo like `floor_gren_mbps` (missing 'e'), it silently falls through to the legacy `floor_mbps` path (line 299: single floor for all states), and the config "validates" successfully but produces unexpected behavior (all state floors set to the same value).

**Why it happens:**
The existing `Config.SCHEMA` validates types and ranges for many fields, but `_load_specific_fields()` contains additional branching logic (lines 291-304: `if "floor_green_mbps" in dl:` vs. `else: floor = dl["floor_mbps"]`) that the schema validation does not cover. A typo in an optional field name causes it to be treated as absent, triggering the legacy fallback path instead of raising an error.

**How to avoid:**
- The `check-config` tool should execute `Config(config_path)` fully (which it already does -- see `validate_config_mode()` at line 2278). This catches downstream validation failures
- Add a "semantic validation" layer that runs AFTER Config construction: verify that the loaded values make operational sense (e.g., `download_floor_green > download_floor_red`, `ping_hosts` contains reachable IPs, queue names are non-empty)
- Add a "completeness" check: if the config has `floor_green_mbps` but is MISSING `floor_yellow_mbps`, flag it as likely incomplete rather than silently defaulting
- Add warnings for the legacy single-floor path: "Using legacy single floor_mbps for all states. Consider migrating to per-state floors (floor_green_mbps, floor_yellow_mbps, floor_red_mbps)."
- Print the ACTUAL loaded values after validation (the current `validate_config_mode()` does this for some fields but not all), so the operator can visually verify the config was interpreted correctly

**Warning signs:**
- `check-config` passes for a config with obvious typos in optional field names
- `check-config` does not print the computed floor values for each state
- Test suite for `check-config` only tests with correct configs, never with configs containing plausible typos

**Phase to address:**
Config validation phase. The semantic validation layer should be part of the first implementation.

---

### Pitfall 6: Router Probe Failure Blocks Daemon Startup or Causes Crash Loop

**What goes wrong:**
Router connectivity probe is added to daemon startup. When the router is temporarily unreachable (firmware update, reboot, network blip), the probe fails and the daemon exits with error. Systemd restarts it, probe fails again, 5 failures trigger the circuit breaker (`StartLimitBurst=5/StartLimitIntervalSec=300`), and both WAN controllers are offline for 5 minutes until manual `systemctl reset-failed`. During those 5 minutes, there is no bandwidth management, potentially causing severe bufferbloat.

**Why it happens:**
The developer treats the router probe as a hard prerequisite: "if we can't verify the router, we shouldn't start." This is wrong for a resilience-oriented system. The daemon already handles router unreachability gracefully during normal operation (via `RouterConnectivityState` and `FailoverRouterClient`). Making startup stricter than runtime creates a contradiction.

**How to avoid:**
- Router probes MUST be advisory, never blocking. The daemon starts regardless of probe results
- Probe results are logged and exposed in the health endpoint, not used as startup gates
- The `wanctl check-cake` and `wanctl check-router` CLI commands CAN fail hard (they are operator tools, not daemon components)
- During daemon startup: attempt probe with 3s timeout. On failure, log WARNING "Router probe skipped: [reason]. CAKE audit deferred to first successful cycle." Continue startup normally
- The existing `FailoverRouterClient` pattern is correct: primary fails, fall back, keep running
- If the router is unreachable at startup, the daemon enters its normal "degraded but running" state and waits for connectivity

**Warning signs:**
- Any `sys.exit(1)` or `return 1` in the startup path that is triggered by a router communication failure
- Probe code that raises exceptions which propagate to `main()`
- Probe timeout longer than 5s in the startup path

**Phase to address:**
Router probe phase. The "advisory, not blocking" principle must be the first design decision.

---

## Moderate Pitfalls

---

### Pitfall 7: CAKE Audit Cannot Distinguish Queue Type from Queue Tree Parameters

**What goes wrong:**
The audit queries `/queue/tree` via REST API and gets back queue tree properties (`name`, `max-limit`, `queue`, `parent`, etc.). It sees `"queue": "cake-download"` which is the queue TYPE name, not the CAKE parameters. To get CAKE-specific parameters (`cake-bandwidth`, `cake-rtt`, `cake-flowmode`, `cake-overhead`, `cake-diffserv`), you need to query the queue type via `/queue/type` with the name `cake-download`. The developer assumes all CAKE parameters are on the queue tree entry and reports "CAKE parameters not found" when they are simply on a different API endpoint.

**Why it happens:**
RouterOS has a two-level queue model: queue tree entries reference queue types. CAKE parameters live on the queue type definition, not the queue tree entry. The existing `CakeStatsReader` queries `/queue/tree print stats` which returns counters (packets, bytes, dropped) from the tree entry, not the CAKE configuration from the type definition.

**How to avoid:**
- Document the two-step query: (1) GET `/rest/queue/tree?name=WAN-Download-Spectrum` to get the queue type name, (2) GET `/rest/queue/type?name=cake-download` to get CAKE parameters
- The audit needs both queries: tree properties (max-limit, parent) AND type properties (cake-bandwidth, cake-rtt, etc.)
- Test with actual RouterOS REST API responses. Record real responses from the production RB5009 and use as test fixtures
- Handle the case where the queue type is NOT CAKE (e.g., `pcq-upload-default`). The audit should report "Queue uses non-CAKE type: [type]" as information, not as an error

**Warning signs:**
- Audit code queries only `/queue/tree` and expects CAKE parameters in the response
- No query to `/queue/type` in the audit implementation
- Test fixtures contain CAKE parameters directly on queue tree entries (not how RouterOS works)

**Phase to address:**
CAKE audit phase. Understanding the RouterOS queue model is a prerequisite for implementation.

---

### Pitfall 8: State File Consistency Check Races with Running Daemon

**What goes wrong:**
The `wanctl check-config` or a startup probe reads the state file (`/var/lib/wanctl/spectrum_state.json`) to verify consistency. But the autorate daemon is writing to this file every cycle (potentially 20 times per second in the hot path, though flash wear protection limits actual writes). The probe reads a partially-written file or reads stale data that the daemon has already moved past. The check reports false inconsistencies.

**Why it happens:**
The existing `atomic_write_json()` function uses temp-file-then-rename, which is atomic on POSIX. But if the probe reads at the exact moment between the temp file write and the rename, it reads the old file content. More importantly, the daemon's in-memory state (current rates, baseline RTT, congestion state) may differ from the last-persisted state file, and the probe has no way to know the daemon's live state without querying the health endpoint.

**How to avoid:**
- State file consistency checks should use the HEALTH ENDPOINT (`/health` on 9101/9102), not direct file reads. The health endpoint returns live daemon state, which is always more current than the state file
- If direct file reads are necessary (e.g., for offline checks when daemon is stopped), use `safe_read_json()` from `state_utils.py` which handles partial reads gracefully
- For "config vs state" consistency (e.g., "are the persisted rates within the configured floor/ceiling range?"), only check when the daemon is NOT running (detect via lock file: if `/run/wanctl/spectrum.lock` is held, skip state file checks)
- The `wanctl check-config` tool should explicitly NOT check state files. Config validation is about the YAML, not runtime state. State file checks belong in a separate `wanctl check-state` command

**Warning signs:**
- Check tool reads `/var/lib/wanctl/*.json` files while the daemon is running
- Check tool reports "rate 456000000 exceeds ceiling 940000000" when the rate is transiently set by the controller
- Flaky test that reads state files in test fixtures without controlling the write timing

**Phase to address:**
Config validation phase (separate state checks from config checks) and integration probe phase.

---

### Pitfall 9: Test Coverage Drops Below 90% Threshold

**What goes wrong:**
New validation, probe, and audit modules add ~500-1000 lines of new code. If tests cover only the happy path (valid config, successful probe, matching CAKE params), coverage for the new code is ~60-70%. The overall project coverage drops below the enforced 90% threshold (`fail_under=90` in `pyproject.toml`), and `make ci` fails. The developer either writes rushed low-quality tests to hit 90%, or temporarily lowers the threshold -- both create technical debt.

**Why it happens:**
Validation and probe code has many error paths: network timeouts, router unreachable, unexpected REST API response format, partial JSON, CAKE type not found, permission denied, etc. Each error path needs a test. The happy path is 1 test; the error paths are 10-15 tests. Developers write the happy path tests first and underestimate the error path test effort.

**How to avoid:**
- Plan for a 3:1 ratio of error tests to happy path tests for validation/probe code
- Each new module should have a companion test file from the first commit. No "add tests later" pattern
- Use parametrize for validation edge cases: `@pytest.mark.parametrize("field,value,expected", [...])` with valid, boundary, and invalid values
- Mock the REST API at the `_request()` level (not at `run_cmd()`) for fine-grained control over response content, status codes, and timeouts
- Establish test fixtures from real RouterOS responses early (record once, use in all tests)
- Track coverage per-module: new modules must be >=85% before merge

**Warning signs:**
- New module has <5 tests
- Tests only test with valid inputs (no error path coverage)
- `pytest --cov` shows new module at <80%
- Developer adds `# pragma: no cover` to error handling code

**Phase to address:**
Every phase. Coverage is a per-phase gate, not a final check.

---

### Pitfall 10: CLI Tool (`wanctl check-config`) Cannot Find Production Config Paths

**What goes wrong:**
The CLI tool works in the development environment (`configs/spectrum.yaml`) but fails in production because production configs are at `/etc/wanctl/spectrum.yaml` with secrets loaded from `/etc/wanctl/secrets` via systemd's `EnvironmentFile=-/etc/wanctl/secrets`. The tool cannot resolve `${ROUTER_PASSWORD}` because the environment variable is not set (it is only set by systemd when starting the daemon). The validation fails with "Missing required field: router.password" or creates a REST client with an empty password that gets authentication errors.

**Why it happens:**
The existing `_resolve_password()` function in `router_client.py` (line 93-109) handles `${ENV_VAR}` syntax, but it reads from `os.environ` which only has the variable if the secrets file has been sourced. When the operator runs `wanctl check-config /etc/wanctl/spectrum.yaml` from their shell, the environment does not include the secrets.

**How to avoid:**
- `wanctl check-config` MUST NOT attempt to connect to the router. It validates YAML structure and value ranges only. Router connectivity is a separate `wanctl check-router` command
- Password fields with `${...}` syntax should be treated as valid during config validation (they are environment variable references, not literal values). Add a special case: if password matches `^\$\{[A-Z_]+\}$`, skip password validation
- If `wanctl check-router` needs the password, accept an `--env-file` flag: `wanctl check-router --env-file /etc/wanctl/secrets` that sources the file before attempting connection
- Alternatively, use `systemd-run --property EnvironmentFile=/etc/wanctl/secrets -- wanctl check-router` to run with the same environment as the daemon
- Document the two-step workflow: `wanctl check-config` (offline, no router needed) then `wanctl check-router` (online, requires router access)

**Warning signs:**
- `check-config` attempts REST API calls
- `check-config` fails on configs with `${ROUTER_PASSWORD}` when run outside systemd
- Tests for `check-config` mock the environment to have ROUTER_PASSWORD set (hiding the real-world failure)

**Phase to address:**
Config validation CLI phase. The boundary between config-only checks and router-dependent checks must be clear.

---

## Minor Pitfalls

---

### Pitfall 11: Verbose Validation Output in Production Logs

**What goes wrong:**
Validation logging uses `logger.info()` or `logger.warning()` for every checked field ("download.ceiling_mbps valid: 940", "upload.floor_mbps valid: 8", ...). At startup, this produces 30-50 log lines of validation results that obscure the meaningful startup messages. In production logs, this noise makes it harder to find actual errors.

**How to avoid:**
- Validation details at DEBUG level. Summary at INFO level: "Config validated: 45 fields OK, 0 errors, 2 warnings"
- Warnings (deprecated params, legacy paths) at WARNING level
- Errors (invalid values, missing required fields) at ERROR level
- `wanctl check-config` prints details to stdout (it is a CLI tool), but daemon startup validation logs only the summary

**Phase to address:**
Config validation phase. Establish log level conventions in the first implementation.

---

### Pitfall 12: CAKE Audit Runs During Every Daemon Cycle

**What goes wrong:**
Developer adds CAKE parameter verification to the hot loop (`run_cycle()`), checking every 50ms that the router's queue configuration matches expectations. This adds 50-200ms of REST API overhead to every cycle, pushing cycle time from 30-40ms to 80-240ms. The 50ms cycle interval is exceeded on every cycle, causing continuous overrun warnings and degraded congestion response.

**How to avoid:**
- CAKE audit is a periodic check, not a per-cycle check. Run it at startup (if watchdog budget allows), then hourly via the maintenance interval (`MAINTENANCE_INTERVAL = 3600`)
- Use the existing periodic maintenance pattern: check `time.monotonic() - last_audit > AUDIT_INTERVAL` in the main loop, then run the audit outside the hot path
- Alternatively, CAKE audit is CLI-only (`wanctl check-cake`) and never runs inside the daemon
- If the audit must be periodic, it should be fire-and-forget in a background thread (similar to `WebhookDelivery` pattern from v1.15)

**Warning signs:**
- Audit code is called inside `run_cycle()` or `_measure_rtt()`
- Cycle profiling shows `router_communication` label jumping from 0.0-0.2ms to 50+ms
- Overrun count climbing steadily in the health endpoint

**Phase to address:**
CAKE audit phase. Decide the execution model (CLI vs periodic vs startup) before implementation.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Validating only at `--validate-config`, not at normal startup | Faster daemon start | Invalid config runs unchecked, fails mid-cycle with obscure error | Never -- always validate at startup (it is fast) |
| Hardcoding expected CAKE parameters in audit code | Quick implementation | Breaks when user changes CAKE config on router manually | Never -- read expected values from config YAML |
| Using the same REST client instance for probes and control | No extra connection setup | Probe failures corrupt client state (broken session, expired cache) | Never -- probes need their own client or a read-only wrapper |
| Skipping validation for steering daemon config | Less code to write | Steering daemon starts with invalid config, crashes during cycle | Never -- both daemons need full validation |
| Testing only with mock router responses | Faster tests, no router dependency | Mocks drift from real RouterOS behavior over releases | For unit tests, acceptable. Integration tests should use recorded real responses. |

## Integration Gotchas

Common mistakes when connecting new validation/probe features to the existing wanctl infrastructure.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| BaseConfig schema | Adding required fields to `BASE_SCHEMA` that are absent in production configs | Add as optional with defaults. Production configs must pass unchanged. |
| ConfigValidationError | Raising it during daemon startup for advisory checks | Use it for fatal errors only. Advisory issues should log warnings and continue. |
| REST API client | Creating a new `RouterOSREST` instance for probes (consumes another session, password resolution) | Reuse the existing `FailoverRouterClient` or pass in the resolved password. Or better: create a read-only probe wrapper around the existing client. |
| Health endpoint | Adding probe results to health response without versioning | Use a new top-level key (`"config_audit"`) with its own schema. Do not modify existing health response fields. |
| SIGUSR1 reload | Not extending reload chain for new validation-related config | If validation thresholds are configurable, they must reload on SIGUSR1 like `dry_run` and `wan_state.enabled`. |
| State file schema | Adding new fields to state file without backward compatibility | Follow v1.11 pattern: new fields have defaults, unknown keys are ignored, no breaking changes to existing fields. |
| `wanctl-history` CLI | Adding `--audit-log` without following existing CLI patterns | Follow the `--alerts` pattern from v1.15: same argument style, same output format, same SQLite query patterns. |

## Performance Traps

Patterns that work in development but fail in production's 50ms cycle budget.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Router probe per cycle | Cycle time jumps from 30ms to 200ms+ | Probe on startup or hourly, never per-cycle | Immediately in production |
| Validating config YAML on every SIGUSR1 reload | Reload takes 50-100ms instead of <1ms | Cache validation result, only re-validate if config file mtime changed | When operator sends frequent SIGUSR1 |
| Fetching all queue tree entries to find one | REST API returns ALL queues, parsed in Python | Use filter parameter: `?name=WAN-Download-Spectrum` | When router has >50 queue tree entries |
| Synchronous DNS resolution for ping hosts during validation | 2-5s timeout per host if DNS is slow | Validate format only (IP/hostname regex), do not resolve. Resolution happens at measurement time. | When DNS server is slow or unreachable |
| CAKE audit stores results in SQLite per-check | Adds write I/O to the hot path | Store audit results in memory, persist only on explicit request or hourly | At 50ms intervals, any I/O is significant |

## Security Mistakes

Domain-specific security issues for validation and router probes.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Probe output includes router password in error messages | Password visible in logs if REST auth fails | Never log credentials. Use `RouterOSREST` which already scrubs passwords (v1.12 SECR-02). Probe error messages should say "authentication failed" not "password 'xyz' rejected". |
| `check-config` prints `router.password` field value | Credential exposure on stdout | Print `router.password: <set>` or `router.password: <env:ROUTER_PASSWORD>`, never the actual value |
| CAKE audit results in health endpoint expose router internals | Network topology details visible via health API | Health endpoint is already on 127.0.0.1. Audit results should show "match/mismatch" status, not raw router parameter values. |
| CLI tool runs as root to access `/etc/wanctl/secrets` | Unnecessary privilege escalation | CLI tool should not need secrets for config validation. Only `check-router` needs secrets, and it can run as the `wanctl` user. |

## UX Pitfalls

Common user experience mistakes in validation and audit CLI tools.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Cryptic error messages ("ConfigValidationError: value out of range for continuous_monitoring.download.ceiling_mbps") | Operator has to cross-reference config file | Include the actual value and the valid range: "ceiling_mbps: 0 is invalid. Must be 1-10000 (current production: 940)" |
| Validation passes silently (exit 0, no output) | Operator unsure if it actually ran | Always print a summary: "spectrum.yaml: 47 fields validated, 0 errors, 0 warnings" |
| CAKE audit only reports mismatches, not what it found | Operator cannot verify the comparison is correct | Print the full comparison: "max-limit: config=940Mbps, router=940000000 bps (MATCH)" |
| Exit code 1 for both "config file not found" and "config invalid" | Cannot distinguish in scripts | Exit 1 for invalid config, exit 2 for file not found, exit 0 for success |
| `check-config` validates but `check-cake` requires separate invocation | Operator forgets one step | Document the workflow clearly. Consider a `wanctl check-all` convenience command that runs both. |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Config validation:** Verify it passes with ACTUAL production configs (`/etc/wanctl/spectrum.yaml`, `/etc/wanctl/att.yaml`, `/etc/wanctl/steering.yaml`), not just example configs
- [ ] **Config validation:** Verify it passes with configs containing `${ENV_VAR}` password syntax even when the env var is not set
- [ ] **Config validation:** Verify that adding a new optional field to a config does NOT cause validation failure for configs missing that field
- [ ] **CAKE audit:** Verify it queries BOTH `/queue/tree` (for max-limit, parent) AND `/queue/type` (for cake-bandwidth, cake-rtt, cake-flowmode, etc.)
- [ ] **CAKE audit:** Verify unit conversions: config Mbps -> router bps, CAKE RTT preset names -> ms values
- [ ] **Router probe:** Verify all requests use HTTP GET method. No POST, PATCH, or DELETE.
- [ ] **Router probe:** Verify probe failure does NOT prevent daemon startup
- [ ] **Router probe:** Verify probe timeout is <= 3s, not the default 15s REST timeout
- [ ] **CLI tools:** Verify they work when run by the `wanctl` user (not root) from `/opt/wanctl`
- [ ] **CLI tools:** Verify exit codes: 0=success, 1=validation failure, 2=file not found
- [ ] **Startup budget:** Measure total startup time with all new validation. Must complete within 25s (leaving 5s headroom for 30s WatchdogSec)
- [ ] **Test coverage:** New modules must be >=85% individually and overall project stays >=90%
- [ ] **Both daemons:** Validation must work for autorate AND steering configs. Do not implement for one and forget the other.

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| P1: New validation rejects existing configs | LOW | Remove the offending validation rule. Make it a warning instead of an error. Redeploy. |
| P2: Watchdog timeout during startup | LOW | Move router probes out of startup path to CLI or post-startup async check. |
| P3: Probe modifies router state | HIGH | Audit all probe code for write operations. If router state was changed: restore from backup config or manually reset the queue/mangle rule. |
| P4: Unit mismatch in CAKE audit | LOW | Fix the conversion function. Add a test with real RouterOS response data. |
| P5: Incomplete schema coverage | MEDIUM | Add semantic validation layer on top of schema validation. Requires understanding all _load_specific_fields() branches. |
| P6: Probe blocks startup | LOW | Make probes advisory. Catch all exceptions from probe code, log warning, continue startup. |
| P7: Queue tree vs queue type confusion | MEDIUM | Add second query to `/queue/type`. Requires understanding RouterOS queue model. |
| P8: State file race | LOW | Switch to health endpoint queries. Remove direct state file reads from probe code. |
| P9: Coverage drops below 90% | MEDIUM | Write error path tests for all new modules. Budget 2-3x more test time than implementation time. |
| P10: CLI cannot resolve secrets | LOW | Separate config validation (no secrets needed) from router checks (secrets needed). |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| P1: Config backward compatibility | Config validation (1st phase) | All production configs + examples pass validation unchanged |
| P2: Watchdog budget | Architecture decision (before implementation) | Total startup time <25s measured on production container |
| P3: Read-only probes | Router probe phase | All probe HTTP requests verified as GET in tests |
| P4: Unit mismatch | CAKE audit phase | Comparison tests use real RouterOS REST responses |
| P5: Incomplete schema | Config validation phase | `check-config` catches typos in optional field names |
| P6: Probe blocks startup | Router probe phase | Daemon starts successfully when router is unreachable |
| P7: Queue tree vs type | CAKE audit phase | Audit queries both `/queue/tree` and `/queue/type` |
| P8: State file race | Integration probe phase | No direct state file reads while daemon is running |
| P9: Coverage threshold | Every phase | `pytest --cov` shows >=90% after each phase |
| P10: CLI secrets | CLI tool phase | `check-config` passes with unresolved `${ENV_VAR}` |
| P11: Log noise | Config validation phase | Daemon startup produces <=3 validation log lines at INFO level |
| P12: Hot path audit | CAKE audit phase | Cycle profiling shows zero audit overhead in normal operation |

## Sources

- Codebase: `src/wanctl/config_base.py` -- BaseConfig, validate_schema, validate_field, SCHEMA pattern (HIGH confidence)
- Codebase: `src/wanctl/config_validation_utils.py` -- validate_bandwidth_order, deprecate_param, ConfigValidationError (HIGH confidence)
- Codebase: `src/wanctl/autorate_continuous.py` -- Config class, _load_specific_fields, validate_config_mode, startup sequence, WatchdogSec budget (HIGH confidence)
- Codebase: `src/wanctl/routeros_rest.py` -- REST API client, _request method, GET/POST/PATCH usage, set_queue_limit (HIGH confidence)
- Codebase: `src/wanctl/steering/cake_stats.py` -- CakeStatsReader, queue tree print parsing, delta calculation (HIGH confidence)
- Codebase: `src/wanctl/router_client.py` -- FailoverRouterClient, _resolve_password, clear_router_password (HIGH confidence)
- Codebase: `src/wanctl/storage/maintenance.py` -- run_startup_maintenance, watchdog_fn pattern, max_seconds budget (HIGH confidence)
- Codebase: `systemd/wanctl@.service` -- WatchdogSec=30s, StartLimitBurst=5, EnvironmentFile=/etc/wanctl/secrets (HIGH confidence)
- Codebase: `configs/spectrum.yaml` -- actual production config with ${ROUTER_PASSWORD}, verify_ssl: false (HIGH confidence)
- [MikroTik CAKE documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/196345874/CAKE) -- CAKE parameters: bandwidth, rtt, diffserv, flowmode, overhead (HIGH confidence)
- [MikroTik REST API documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/47579162/REST+API) -- GET is read-only, POST executes commands, 60s timeout (HIGH confidence)
- [MikroTik Queues documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/328088/Queues) -- queue tree vs queue type separation, CAKE as queue type (HIGH confidence)
- [systemd.service documentation](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html) -- WatchdogSec semantics, WATCHDOG_USEC (HIGH confidence)
- [sd_notify documentation](https://www.freedesktop.org/software/systemd/man/latest/sd_notify.html) -- WATCHDOG=1, READY=1 notification protocol (HIGH confidence)

---
*Pitfalls research for: config validation, CAKE qdisc audit, and router integration probes in production dual-WAN controller*
*Researched: 2026-03-12*
