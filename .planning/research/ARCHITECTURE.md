# Architecture Patterns

**Domain:** Config validation, CAKE qdisc audit, router integration probes for dual-WAN controller
**Researched:** 2026-03-12
**Overall confidence:** HIGH (all patterns derived from existing codebase analysis)

## Current Architecture Summary

The existing system has five layers:

```
CLI Tools          wanctl-history, wanctl-dashboard, wanctl-calibrate
                       |
Daemons           autorate_continuous (ContinuousAutoRate)
                  steering/daemon (SteeringDaemon)
                       |
Config            BaseConfig -> Config (autorate) / SteeringConfig (steering)
                  config_validation_utils.py (domain validators)
                       |
Router Comm       router_client.py -> FailoverRouterClient
                  routeros_rest.py / routeros_ssh.py
                       |
State/Storage     state_utils.py, storage/ (SQLite), health_check.py
```

Key patterns already established:
- **BaseConfig + SCHEMA**: Declarative schema validation at config load time
- **validate_schema()**: Collects all errors before raising
- **ConfigValidationError**: Single exception type for all config failures
- **CLI entry points**: `pyproject.toml [project.scripts]` mapping to `module:main`
- **Router queries**: `client.run_cmd()` returning `(rc, stdout, stderr)` tuples
- **Health endpoints**: JSON HTTP on ports 9101/9102

## Recommended Architecture for v1.16

### Principle: Validation Is a Library, Not a Daemon

The new features are **read-only inspection tools** that reuse existing infrastructure. They do NOT run as daemons. They are CLI one-shot commands that load config, optionally probe the router, report findings, and exit.

### New Module Map

```
src/wanctl/
  config_base.py          [MODIFY] Add structured validation result type
  config_validation_utils.py  [MODIFY] Add cross-field validators if needed
  check_config.py         [NEW] wanctl-check-config CLI entry point
  check_cake.py           [NEW] wanctl-check-cake CLI entry point + CAKE audit logic
  validation/             [NEW, optional] Only if check_config.py exceeds ~300 lines
    __init__.py
    config_checker.py     Config validation orchestrator
    cake_auditor.py       CAKE qdisc comparison logic
    router_prober.py      Read-only router probes
```

**Recommendation:** Start flat (check_config.py, check_cake.py at top level) and only extract a `validation/` subpackage if complexity warrants it. The existing codebase keeps CLI tools as single modules (history.py, calibrate.py) and this should follow the same pattern.

### Component Boundaries

| Component | Responsibility | Communicates With | New/Modified |
|-----------|---------------|-------------------|-------------|
| `check_config.py` | CLI: load config, run all validators, report | BaseConfig, config_validation_utils | NEW |
| `check_cake.py` | CLI: query router CAKE qdiscs, compare to config | router_client, BaseConfig | NEW |
| `config_base.py` | Add `ValidationResult` dataclass, structured errors | (self-contained) | MODIFY |
| `config_validation_utils.py` | Add cross-field and semantic validators | config_base | MODIFY (minor) |
| `autorate_continuous.py` Config.__init__ | Call enhanced validation at startup | config_base | MODIFY (minor) |
| `steering/daemon.py` SteeringConfig.__init__ | Call enhanced validation at startup | config_base | MODIFY (minor) |

### Data Flow: `wanctl check-config`

```
CLI args (--config path)
    |
    v
YAML load (yaml.safe_load)
    |
    v
Schema validation (validate_schema with BASE_SCHEMA + SCHEMA)
    |
    v
Cross-field validation (floor ordering, threshold ordering, etc.)
    |
    v
File/path validation (log dirs exist, state dirs writable, SSH key readable)
    |
    v
Optional: router connectivity probe (--probe flag)
    |
    v
ValidationReport (list of ValidationResult: pass/warn/fail per check)
    |
    v
Console output (colored table or plain text)
    |
    v
Exit code (0 = all pass, 1 = any fail, 2 = warnings only)
```

### Data Flow: `wanctl check-cake`

```
CLI args (--config path)
    |
    v
Load config (reuse BaseConfig subclass or raw YAML + minimal validation)
    |
    v
Create router client (get_router_client or get_router_client_with_failover)
    |
    v
Query queue tree: /queue/tree/print where name="<queue_name>"
    |
    v
Parse response: extract queue-type, max-limit, parent, etc.
    |
    v
Compare against config expectations:
  - Queue exists?
  - Queue type is CAKE variant?
  - Max-limit matches ceiling_mbps from config?
  - Parent hierarchy correct?
    |
    v
CakeAuditReport (list of checks with expected vs actual)
    |
    v
Console output + exit code
```

### Data Flow: Startup Validation (Enhanced)

```
Daemon starts (autorate or steering)
    |
    v
BaseConfig.__init__ (existing path, unchanged)
    |
    v
_load_specific_fields() (existing path, unchanged)
    |
    v
[NEW] _validate_environment()
  - Log directory exists and is writable
  - State file directory exists and is writable
  - Lock file directory exists
  - SSH key file exists (if SSH transport)
    |
    v
[NEW] _validate_cross_field()
  - floor_red <= floor_soft_red <= floor_yellow <= floor_green <= ceiling
    (already done in _load_download_config, but consolidate)
  - threshold ordering (already done, consolidate)
    |
    v
On failure: log structured errors + sys.exit(1) [fail-fast]
On success: continue to daemon loop (existing behavior)
```

## Patterns to Follow

### Pattern 1: ValidationResult Dataclass

Structured validation results that can be collected, filtered, and displayed.

**What:** A simple result type that replaces ad-hoc string error collection.
**When:** All validation checks should return this instead of raising immediately.
**Why:** The CLI tools need to collect ALL problems and display them together, not stop at the first error.

```python
from dataclasses import dataclass
from enum import Enum

class CheckStatus(Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"

@dataclass(frozen=True, slots=True)
    """Single validation check result."""
    category: str      # "schema", "file", "router", "cake"
    check: str         # Human-readable check name
    status: CheckStatus
    message: str       # Detail message
    expected: str = "" # What was expected (for comparison displays)
    actual: str = ""   # What was found

    @property
    def passed(self) -> bool:
        return self.status in (CheckStatus.PASS, CheckStatus.SKIP)
```

**Integration note:** This lives in `config_base.py` alongside `ConfigValidationError`. The existing `validate_schema()` continues to raise for daemon startup (fail-fast). The CLI tools use a parallel path that collects `ValidationResult` objects.

### Pattern 2: CLI Tool as Single Module

Follow the history.py and calibrate.py pattern: one module with `create_parser()` and `main()`.

**What:** Each CLI tool is a standalone module registered in `pyproject.toml`.
**When:** Every new CLI command.

```python
# check_config.py
def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wanctl-check-config",
        description="Validate wanctl configuration files",
    )
    parser.add_argument("config", help="Path to YAML config file")
    parser.add_argument("--probe", action="store_true",
                       help="Test router connectivity (requires network)")
    parser.add_argument("--json", action="store_true",
                       help="Output results as JSON")
    return parser

def main() -> int:
    parser = create_parser()
    args = parser.parse_args()
    # ... validation logic ...
    return 0 if all_passed else 1
```

pyproject.toml addition:
```toml
[project.scripts]
wanctl-check-config = "wanctl.check_config:main"
wanctl-check-cake = "wanctl.check_cake:main"
```

### Pattern 3: Reuse Router Client for Read-Only Probes

The existing `get_router_client_with_failover()` and `RouterOSREST` already handle connection, auth, and failover. CAKE audit just needs to issue `/queue/tree/print` commands.

**What:** Create a temporary router client, query, close. No daemon loop.
**When:** `wanctl check-cake` and `wanctl check-config --probe`.

```python
from wanctl.router_client import get_router_client

# Minimal config loading for router connection
client = get_router_client(config, logger)
try:
    # Read-only probe: system identity
    rc, out, err = client.run_cmd("/system/identity/print", capture=True)
    if rc == 0:
        results.append(ValidationResult("router", "connectivity", CheckStatus.PASS, ...))

    # Read-only probe: queue tree listing
    rc, out, err = client.run_cmd(
        f'/queue/tree/print detail where name="{queue_name}"', capture=True
    )
    # Parse and compare...
finally:
    client.close()
```

**Important:** Use `get_router_client()` (not `get_router_client_with_failover()`) for CLI tools. Failover adds complexity meant for long-running daemons. A one-shot probe should try the configured transport and report clearly if it fails.

### Pattern 4: Collect-Then-Report (Not Fail-Fast)

For CLI validation, collect ALL results before reporting. This is different from daemon startup where fail-fast via `ConfigValidationError` is correct.

**What:** Run every check, accumulate results, then display summary.
**When:** `wanctl check-config` and `wanctl check-cake`.
**Why:** Users want to see ALL problems at once, not fix one, re-run, find another.

```python
def check_config(config_path: str, probe: bool = False) -> list[ValidationResult]:
    results: list[ValidationResult] = []

    # Phase 1: YAML parse
    results.extend(_check_yaml_syntax(config_path))
    if any(r.status == CheckStatus.FAIL for r in results):
        return results  # Can't continue if YAML is broken

    # Phase 2: Schema validation
    results.extend(_check_schema(data))

    # Phase 3: Cross-field validation
    results.extend(_check_cross_field(data))

    # Phase 4: Environment checks
    results.extend(_check_environment(data))

    # Phase 5: Optional router probe
    if probe:
        results.extend(_check_router_connectivity(data))

    return results
```

### Pattern 5: Config Type Detection

The CLI tool needs to determine whether a config file is for autorate or steering, since they have different schemas.

**What:** Detect config type from content, then apply appropriate schema.
**When:** `wanctl check-config` needs to validate any config file.

```python
def detect_config_type(data: dict) -> str:
    """Detect config type from YAML content.

    Returns "autorate" or "steering" based on distinctive keys.
    """
    if "topology" in data or "mangle_rule" in data:
        return "steering"
    if "continuous_monitoring" in data or "queues" in data:
        return "autorate"
    return "unknown"
```

This avoids requiring users to specify `--type autorate` on the command line.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Modifying Daemon Startup to Use New Validation Path

**What:** Refactoring daemon Config.__init__ to use the new ValidationResult-based validation.
**Why bad:** The daemon path is battle-tested and uses fail-fast (raise ConfigValidationError). Changing it risks production regressions. The CLI validation and daemon validation serve different purposes.
**Instead:** The CLI tool uses its own collect-then-report validation path that calls the same underlying validators (validate_field, validate_bandwidth_order, etc.) but wraps results differently. Daemon startup keeps its existing raise-on-first-error behavior.

### Anti-Pattern 2: Creating a RouterProber That Wraps RouterClient

**What:** Building an abstraction layer on top of the existing router client just for read-only queries.
**Why bad:** Unnecessary indirection. The existing `client.run_cmd()` is already the right interface.
**Instead:** Call `run_cmd()` directly in the check functions. Parse responses inline.

### Anti-Pattern 3: Interactive Validation (Prompt to Fix)

**What:** Having `wanctl check-config` offer to fix problems interactively.
**Why bad:** Complexity explosion, hard to test, not useful in containers/CI.
**Instead:** Report problems with clear fix instructions. User edits config manually.

### Anti-Pattern 4: Making CAKE Audit Part of Daemon Startup

**What:** Running CAKE qdisc checks every time the daemon starts.
**Why bad:** Adds latency to startup, requires router connectivity before daemon can run, creates chicken-and-egg with FailoverRouterClient.
**Instead:** CAKE audit is a separate CLI tool run on-demand or during deployment verification.

## Integration Points: New vs Modified

### New Files

| File | Purpose | Dependencies |
|------|---------|-------------|
| `src/wanctl/check_config.py` | CLI: `wanctl-check-config` | config_base, config_validation_utils |
| `src/wanctl/check_cake.py` | CLI: `wanctl-check-cake` | config_base, router_client, routeros_rest |

### Modified Files

| File | Change | Risk |
|------|--------|------|
| `pyproject.toml` | Add 2 script entry points | LOW - additive only |
| `config_base.py` | Add ValidationResult, CheckStatus | LOW - additive, no existing behavior changed |
| `autorate_continuous.py` | Add `_validate_environment()` call in Config | LOW - new method, called after existing load |
| `steering/daemon.py` | Add `_validate_environment()` call in SteeringConfig | LOW - same pattern |

### Unchanged Files (Reused As-Is)

| File | How Reused |
|------|-----------|
| `config_validation_utils.py` | All existing validators called by check_config |
| `router_client.py` | `get_router_client()` for CAKE audit probes |
| `routeros_rest.py` | Queue tree queries via existing REST client |
| `routeros_ssh.py` | Fallback transport (if user config says SSH) |
| `router_command_utils.py` | `extract_field_value()` for parsing router output |

## CAKE Qdisc Audit: Router Query Details

The RouterOS REST API returns queue tree entries with these relevant fields:

```json
{
    ".id": "*1",
    "name": "WAN-Download-Spectrum",
    "queue": "cake-down-spectrum",
    "max-limit": "940000000",
    "parent": "global",
    "disabled": "false",
    "packets": "...",
    "bytes": "..."
}
```

The `queue` field references the queue type (CAKE variant). The audit compares:

| Check | Expected (from config) | Actual (from router) |
|-------|----------------------|---------------------|
| Queue exists | `queues.download` | `/queue/tree/print` returns entry |
| Queue type is CAKE | `cake-{down\|up}-{wan}` | `queue` field |
| Max-limit in range | `floor_red_mbps..ceiling_mbps` | `max-limit` field |
| Queue not disabled | `disabled: false` | `disabled` field |

For the upload queue, same checks with upload config values.

Additionally, the mangle rule check (for steering configs):

| Check | Expected | Actual |
|-------|----------|--------|
| Rule exists | `mangle_rule.comment` | `/ip/firewall/mangle/print` |
| Rule is disabled at rest | `disabled: yes` (steering off) | rule flags |

## Suggested Build Order

Based on dependency analysis:

### Phase 1: Config Validation Foundation
1. Add `ValidationResult` and `CheckStatus` to `config_base.py`
2. Build `check_config.py` with YAML parse + schema validation
3. Add to `pyproject.toml` as `wanctl-check-config`
4. Test: validate example configs, detect misconfigurations

**Rationale:** No router dependency, all local. Validates the collect-then-report pattern.

### Phase 2: Enhanced Config Validation + Startup Guards
1. Add environment checks (directories, file permissions, SSH key)
2. Add config type auto-detection (autorate vs steering)
3. Add startup validation hooks to daemon Configs (`_validate_environment()`)
4. Test: invalid paths, missing directories, permission errors

**Rationale:** Still no router dependency. Adds fail-fast to daemon startup.

### Phase 3: CAKE Qdisc Audit
1. Build `check_cake.py` with router query + comparison logic
2. Add `--probe` flag to `check_config.py` for optional router connectivity test
3. Add to `pyproject.toml` as `wanctl-check-cake`
4. Test: mock router responses, verify comparison logic

**Rationale:** Requires router communication. Depends on Phase 1 for ValidationResult.

### Phase 4: Integration Probes + Polish
1. Add state file consistency checks to `check_config.py`
2. Add mangle rule verification to `check_cake.py` (for steering configs)
3. Add JSON output format for CI/scripting
4. Test: end-to-end with real configs (no real router needed if mocked)

**Rationale:** Polish and integration. Depends on Phases 1-3.

## Scalability Considerations

Not applicable. These are one-shot CLI tools that query a single router. Performance is not a concern. The router probes add at most 100-200ms of REST API calls.

## Sources

- Codebase analysis: `config_base.py` (BaseConfig, validate_schema, SCHEMA pattern)
- Codebase analysis: `config_validation_utils.py` (domain validators, deprecate_param)
- Codebase analysis: `router_client.py` (get_router_client, FailoverRouterClient)
- Codebase analysis: `routeros_rest.py` (REST queue tree operations)
- Codebase analysis: `backends/routeros.py` (RouterOSBackend.test_connection)
- Codebase analysis: `history.py`, `calibrate.py` (CLI tool patterns)
- Codebase analysis: `alert_engine.py` (recent integration pattern reference)
- Codebase analysis: `pyproject.toml` (entry point registration)
- Codebase analysis: `steering.yaml.example`, `cable.yaml.example` (config structure)
- Confidence: HIGH -- all patterns derived from existing code, no external research needed
