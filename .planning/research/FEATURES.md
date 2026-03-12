# Feature Landscape

**Domain:** Config validation, CAKE qdisc auditing, and router integration probes for dual-WAN controller
**Researched:** 2026-03-12
**Existing codebase:** v1.15.0 (20,140 LOC, 2,666 tests, 16 milestones shipped)

## Table Stakes

Features users expect from a validation/audit milestone. Missing any of these makes the milestone feel incomplete.

| Feature | Why Expected | Complexity | Dependencies |
|---------|--------------|------------|--------------|
| `wanctl check-config <file>` standalone CLI | Operators need to validate configs without starting daemons. Existing `--validate-config` is buried inside `wanctl` daemon binary and lacks steering config support. | Low | config_base.py, config_validation_utils.py |
| Structured error collection (all errors, not just first) | Current `validate_schema()` collects errors already, but Config.__init__ calls validators sequentially and may short-circuit on the first `ConfigValidationError`. Operators need to see ALL issues in one pass. | Low | config_base.py `validate_schema()` (already collects) |
| Cross-field validation (semantic checks beyond schema) | Schema validation catches type/range errors but misses semantic contradictions: e.g., `floor_red > floor_yellow`, threshold ordering, `ceiling < floor_green`, `steer_threshold < recovery_threshold`. Some of these exist in `config_validation_utils.py` but are called ad-hoc, not centrally. | Medium | config_validation_utils.py (existing validators), Config._load_specific_fields() |
| File existence/permission checks | Config references external files (ssh_key, state_file parent, lock_file parent, log directories). A validation tool must verify these exist and are writable before the daemon discovers the problem at runtime. | Low | pathlib.Path checks |
| Environment variable resolution check | REST password uses `${ROUTER_PASSWORD}` pattern. Validation should verify the env var exists (or at least warn) without exposing the value. | Low | router_client.py `_resolve_password()` pattern |
| Exit codes for CI/CD integration | `wanctl check-config` must return 0 on success, non-zero on failure. Existing `validate_config_mode()` already does this. | Low | Trivial |
| Human-readable output with severity levels | Errors (fatal), warnings (deprecated params, missing optional fields), info (computed defaults shown). Not just pass/fail. | Low | Print formatting |
| `wanctl check-cake` router queue audit | Read-only probe comparing router queue tree config (queue type, max-limit, parent) against expected YAML config. This is the core "does my router match my config?" question. | Medium | router_client.py, routeros_rest.py `_handle_queue_tree_print()`, config loading |
| State file consistency check | Verify state files exist, are valid JSON, contain expected keys, and are not stale (mtime). State corruption has been a real issue (v1.10 added safe JSON loading for this reason). | Low | state_utils.py `safe_read_json()` |

## Differentiators

Features that go beyond basic validation and provide real operational confidence. Not strictly expected, but high value.

| Feature | Value Proposition | Complexity | Dependencies |
|---------|-------------------|------------|--------------|
| Router connectivity probe (`check-cake --probe`) | Verify REST/SSH transport actually reaches the router and authenticates, before auditing queues. Uses existing `test_connection()` methods. | Low | routeros_rest.py `test_connection()`, RouterOSSSH equivalent |
| CAKE queue type verification | Beyond max-limit, verify the queue tree entry actually uses CAKE qdisc (not fq_codel or default). RouterOS REST API returns `queue` field (e.g., "cake-rx/cake-tx"). Catches "I configured CAKE in wanctl but forgot to set it on the router." | Low | REST GET /queue/tree returns `queue` field |
| Mangle rule existence check (steering config) | Verify the mangle rule referenced by `mangle_rule.comment` actually exists on the router. Catches "I deleted/renamed my steering rule." | Low | routeros_rest.py `_find_mangle_rule_id()` |
| Config diff: running vs expected | Show side-by-side comparison of what the router currently has vs what the config expects. Output like: `max-limit: 940000000 (expected) vs 500000000 (actual)`. | Medium | Requires parsing both config and router response |
| Steering config cross-validation | Steering config references `topology.primary_wan_config` (a path to the autorate config). Validate that file exists AND its `wan_name` matches `topology.primary_wan`. Cross-config consistency. | Low | Path resolution + Config() loading |
| Deprecated parameter report | Collect all deprecation warnings triggered during config load into a structured list. Currently these go to logging only. A CLI tool should surface them prominently. | Low | deprecate_param() already detects, just needs output routing |
| JSON output mode (`--json`) | Machine-readable output for scripting, monitoring integration, CI pipelines. Follow the pattern of `wanctl-history --json`. | Low | json.dumps formatting |
| Health endpoint integration probe | Verify the health HTTP endpoints (9101/9102) respond correctly from the CLI. Catches "daemon is running but health server failed to bind." | Low | HTTP GET to localhost:port/health |
| SQLite database integrity check | Existing auto-rebuild on corruption (v1.10), but a CLI check that runs `PRAGMA integrity_check` and reports without waiting for runtime discovery. | Low | sqlite3 module, storage config |

## Anti-Features

Features to explicitly NOT build in this milestone.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Config file generation/wizard | The `wanctl-calibrate` tool already does interactive config creation. Adding another generation path creates confusion about which is canonical. | Point users to `wanctl-calibrate` for initial setup; `check-config` is for ongoing validation. |
| Router config modification from CLI | Validation and audit tools MUST be read-only. No queue setting, no mangle rule toggling. This is a core safety principle for a production network controller. | Use clear naming (`check-*`) and document read-only behavior. The existing daemons handle all writes. |
| Auto-fix/auto-repair | Tempting to have `check-config --fix` that patches deprecated params or creates missing dirs. Too risky for production network config. Miscorrections break things worse. | Report problems with specific fix instructions. Let the operator decide. |
| Full network topology discovery | Probing all router interfaces, all queue trees, all mangle rules to build a complete picture. Out of scope -- we only care about the specific queues and rules wanctl manages. | Scope probes to exactly the resources referenced in the config file. |
| Schema migration tool | Config has `schema_version: "1.0"` and a placeholder for future migration. Building migration logic before there is a v2.0 schema is YAGNI. | Keep the version field, document it, but do not build migration machinery yet. |
| Prometheus/OpenTelemetry export from check tools | Check tools run once and exit. They are not long-running processes that need metrics export. | Return exit codes and structured output. Monitoring tools can parse JSON output if needed. |
| Interactive/TUI mode for check tools | The dashboard already provides TUI. Check tools should be simple CLI with text output, suitable for `ssh container 'wanctl check-config ...'`. | Plain text + optional JSON. Keep it pipe-friendly. |

## Feature Dependencies

```
check-config (standalone CLI)
  +-- Schema validation (existing validate_schema)
  +-- Cross-field validation (partially existing in config_validation_utils.py)
  +-- File/permission checks (new)
  +-- Env var resolution check (new, uses existing pattern)
  +-- Deprecated param collection (existing deprecate_param, new output routing)
  +-- Steering config cross-validation (new)

check-cake (router audit CLI)
  +-- Router connectivity probe (uses existing test_connection)
  +-- Queue tree read (uses existing REST GET /queue/tree)
  +-- Queue type verification (CAKE vs other)
  +-- Max-limit comparison (config vs router)
  +-- Mangle rule existence (steering only)
  +-- Config diff output (new formatting)

Both tools share:
  +-- Config loading (BaseConfig subclasses)
  +-- Structured result collection (new: list of Check results with severity)
  +-- Output formatting (text + JSON modes)
  +-- Exit code logic (0=pass, 1=fail, 2=warn-only)
```

## Implementation Notes

### Existing Foundations (leverage, do not rebuild)

1. **`validate_config_mode()`** in autorate_continuous.py -- already does basic config-load-and-print for autorate configs. This is the starting point for `check-config`, but needs: (a) steering config support, (b) structured error collection, (c) cross-field checks, (d) file existence checks, (e) standalone entry point.

2. **`BaseConfig.validate_schema()` + `validate_field()`** -- schema-driven validation already collects all errors before raising. This pattern is good; extend it, do not replace it.

3. **`deprecate_param()`** -- already detects and warns about deprecated params. Route warnings to a collection list instead of (only) to the logger.

4. **`routeros_rest.py` GET /queue/tree** -- already implemented for reading queue data. The `_handle_queue_tree_print()` method returns JSON with all queue fields including `queue` (qdisc type), `max-limit`, `parent`, `name`, `disabled`.

5. **`test_connection()`** -- exists on both RouterOSREST and RouterOSBackend. Use for connectivity probes.

6. **`FailoverRouterClient`** -- check-cake should use the single-transport factory (`get_router_client`) not the failover wrapper, since we want to test the specific transport, not silently fail over.

7. **Contract test pattern** from v1.12 -- parametrize checks from config so adding new queue names or mangle rules auto-creates validation cases.

### New Code Needed

1. **`CheckResult` dataclass** -- severity (ERROR/WARNING/INFO), category, message, context. Shared between both tools.

2. **`wanctl-check-config` entry point** in pyproject.toml -- new console_scripts entry.

3. **`wanctl-check-cake` entry point** -- separate tool, separate entry point. Requires router access (unlike check-config which is offline).

4. **`config_checker.py`** module -- centralized validation logic extracted from daemon-specific validate_config_mode. Takes a config path, returns list of CheckResults.

5. **`router_auditor.py`** module -- read-only router probing. Takes config, queries router, compares expected vs actual.

### RouterOS REST API Details for Queue Audit

The RouterOS REST API GET /queue/tree returns JSON objects with these relevant fields:
- `.id` -- internal ID (e.g., "*1")
- `name` -- queue name (e.g., "WAN-Download-Spectrum")
- `parent` -- parent queue or interface
- `queue` -- qdisc type string (e.g., "cake-rx/cake-tx", "default", "fq-codel-default")
- `max-limit` -- bandwidth limit in bps (string in JSON, even though numeric)
- `disabled` -- "true" or "false" (string)
- `packets`, `bytes`, `dropped`, `queued-packets`, `queued-bytes` -- counters

The `queue` field is critical for CAKE verification. If it does not contain "cake", the queue tree is not using CAKE qdisc.

### CLI Pattern

Follow existing CLI patterns in the project:
- `wanctl-history` uses argparse, tabulate for output, `--json` flag
- `wanctl-dashboard` uses Textual
- `wanctl-calibrate` uses argparse, interactive mode

The check tools should follow the `wanctl-history` pattern (non-interactive, argparse, tabulate, --json).

```
wanctl-check-config /etc/wanctl/spectrum.yaml
wanctl-check-config /etc/wanctl/spectrum.yaml /etc/wanctl/steering.yaml
wanctl-check-config --json /etc/wanctl/*.yaml

wanctl-check-cake --config /etc/wanctl/spectrum.yaml
wanctl-check-cake --config /etc/wanctl/steering.yaml --json
```

## MVP Recommendation

### Phase 1: Config Validation CLI (offline, no router needed)

Prioritize:
1. **Standalone `wanctl-check-config` entry point** -- both autorate and steering config support
2. **Structured error collection** -- all errors surfaced, not just first
3. **Cross-field semantic validation** -- floor ordering, threshold ordering, parameter interactions
4. **File/permission checks** -- ssh_key, log dirs, state file dirs, lock file dirs
5. **Env var resolution check** -- ${ROUTER_PASSWORD} existence
6. **Deprecated param report** -- collected and surfaced prominently
7. **Exit codes** -- 0/1/2 for CI/CD

Defer to Phase 2: JSON output mode, steering cross-validation (needs both config files)

### Phase 2: CAKE Queue Audit (requires router access)

Prioritize:
1. **Router connectivity probe** -- REST/SSH reachability and auth
2. **Queue tree audit** -- queue exists, uses CAKE, max-limit matches
3. **Mangle rule check** (steering config) -- rule exists and matches comment
4. **Config vs router diff output** -- expected vs actual comparison

Defer to Phase 3: Health endpoint probes, SQLite integrity, state file checks

### Phase 3: Integration Probes (end-to-end operational checks)

1. **State file consistency** -- valid JSON, expected keys, freshness
2. **SQLite integrity** -- PRAGMA integrity_check on metrics.db
3. **Health endpoint probes** -- HTTP GET to ports 9101/9102
4. **Cross-config steering validation** -- verify topology references resolve

## Complexity Assessment

| Feature | New Code | Existing Code Reused | Test Effort |
|---------|----------|---------------------|-------------|
| check-config CLI | ~200 LOC | BaseConfig, validate_schema, deprecate_param | ~40 tests |
| Cross-field validation | ~100 LOC | config_validation_utils.py validators | ~30 tests |
| File/permission checks | ~50 LOC | pathlib only | ~15 tests |
| Env var check | ~20 LOC | _resolve_password pattern | ~5 tests |
| check-cake connectivity | ~50 LOC | test_connection() | ~10 tests |
| Queue tree audit | ~150 LOC | REST GET, config loading | ~30 tests |
| Mangle rule check | ~30 LOC | _find_mangle_rule_id() | ~10 tests |
| Config diff output | ~100 LOC | New formatting | ~15 tests |
| State file check | ~50 LOC | safe_read_json() | ~10 tests |
| SQLite integrity | ~30 LOC | sqlite3.connect | ~5 tests |
| **Total estimate** | **~780 LOC** | **Heavy reuse** | **~170 tests** |

## Sources

- Codebase analysis: config_base.py, config_validation_utils.py, router_client.py, routeros_rest.py, autorate_continuous.py (validate_config_mode), steering/daemon.py (SteeringConfig)
- [MikroTik RouterOS REST API documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/47579162/REST+API)
- [MikroTik CAKE documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/196345874/CAKE)
- [MikroTik Queue Tree documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/328088/Queues)
- [Python argparse documentation](https://docs.python.org/3/library/argparse.html)
- [tc-cake(8) Linux manual page](https://www.man7.org/linux/man-pages/man8/tc-cake.8.html)
