# Phase 83: CAKE Qdisc Audit - Research

**Researched:** 2026-03-13
**Domain:** MikroTik RouterOS queue tree audit via REST/SSH, CLI tool design
**Confidence:** HIGH

## Summary

Phase 83 builds a new CLI tool `wanctl-check-cake` that connects to the live MikroTik router and audits CAKE queue tree configuration against what the wanctl config expects. The tool is strictly read-only (GET requests only) and reports results in the same category-grouped format as `wanctl-check-config`.

The codebase already contains every building block needed. The check_config.py module provides the data model (Severity, CheckResult), output formatters (format_results, format_results_json), and CLI pattern (create_parser, main). The router_client.py module provides transport factory and password resolution. The routeros_rest.py module already handles queue tree GET queries (returning JSON with fields like `name`, `queue`, `max-limit`, `.id`) and mangle rule queries by comment. No new dependencies are needed.

**Primary recommendation:** Create a single `check_cake.py` module that imports Severity/CheckResult/formatters from check_config.py, builds a lightweight config-like object from parsed YAML (without instantiating Config/SteeringConfig), creates a router client, and runs category-based validators that return `list[CheckResult]`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Accept any wanctl YAML config file, auto-detect type using same detection logic as check-config (topology -> steering, continuous_monitoring -> autorate)
- Type-adaptive checks: autorate checks connectivity + queue audit + CAKE type; steering additionally checks mangle rule existence
- Queue names come solely from config (queues.download/upload for autorate, cake_queues.primary_download/upload for steering)
- `--type` override flag for explicit type selection
- Identical flags to check-config: `--json`, `--no-color`, `-q/--quiet`
- Same exit codes: 0=pass, 1=errors, 2=warnings-only
- Same category-grouped output with checkmark/warning/X symbols per check
- Same create_parser() + main() CLI entry point pattern
- Reuse Severity enum and CheckResult dataclass from check_config.py
- Inline per-check results showing expected vs actual (not separate summary table)
- CAKE type verification: pass if queue field starts with "cake", fail otherwise
- Router unreachable: ERROR in Connectivity category, skip remaining checks, exit code 1
- Missing queue: ERROR
- Wrong qdisc type (not CAKE): ERROR
- Missing mangle rule (steering only): ERROR
- Simple single transport -- read from config, no failover
- Fail early on unresolved env vars before attempting connection
- Single connectivity check combining reachability + auth
- Use config's existing timeout values (timeouts.ssh_command)

### Claude's Discretion
- Expected values for ceiling-vs-max-limit comparison (considering max-limit changes dynamically during congestion)
- Internal architecture of check_cake.py (validator structure, code sharing with check_config.py)
- How to instantiate router client without triggering daemon side effects
- Router API call structure for queue tree enumeration and mangle rule queries
- How to handle partial failures (e.g., download queue exists but upload doesn't)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CAKE-01 | `wanctl-check-cake` probes router connectivity (REST/SSH reachability and auth) | RouterOSREST.test_connection() does GET /system/resource; for SSH, run_cmd with a simple command tests auth+reachability. Password resolution via _resolve_password(). |
| CAKE-02 | Queue tree audit verifies queues exist with expected names and max-limit values | GET /rest/queue/tree?name=X returns list of matching queue objects with name, queue, max-limit, .id fields. Empty list = queue not found. |
| CAKE-03 | CAKE qdisc type verification confirms queues use CAKE | Queue tree response includes `queue` field (e.g., "cake-down-spectrum"). Check `queue.startswith("cake")`. |
| CAKE-04 | Config-vs-router diff shows expected vs actual values | Ceiling (from config) is the expected max-limit. Actual max-limit may differ during congestion. Use ceiling_mbps * 1_000_000 as expected value with explanatory note. |
| CAKE-05 | Mangle rule existence check verifies steering mangle rule exists on router | GET /rest/ip/firewall/mangle?comment=X returns matching rules. Empty list = rule not found. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| check_config.py (internal) | N/A | Severity, CheckResult, format_results, format_results_json, detect_config_type | Already established data model and output format |
| router_client.py (internal) | N/A | _resolve_password, transport selection | Password resolution and client creation |
| routeros_rest.py (internal) | N/A | GET /queue/tree, GET /ip/firewall/mangle, test_connection | Existing REST API methods for all needed queries |
| routeros_ssh.py (internal) | N/A | SSH transport fallback | SSH client for routers using SSH transport |
| yaml | stdlib-adjacent | YAML config parsing | Already used everywhere |
| argparse | stdlib | CLI argument parsing | Same pattern as check_config |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| json | stdlib | JSON output mode | When --json flag passed |
| os | stdlib | Environment variable resolution | Password ${ROUTER_PASSWORD} check |
| requests | existing dep | HTTP requests for REST API | Only via RouterOSREST (not direct) |
| paramiko | existing dep | SSH connections | Only via RouterOSSSH (not direct) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Direct RouterOSREST instantiation | get_router_client() factory | Factory requires Config object; direct instantiation gives more control for a CLI tool |
| Full Config() instantiation | Lightweight dict-based config extraction | Config() triggers _load_specific_fields which calls validate_bandwidth_order etc. -- too heavy for a read-only CLI tool |

**Installation:**
```bash
# No new dependencies needed -- everything is already in pyproject.toml
```

## Architecture Patterns

### Recommended Project Structure
```
src/wanctl/
├── check_cake.py          # NEW: Router audit CLI tool
├── check_config.py        # Existing: Offline config validator (imports from here)
├── router_client.py       # Existing: Transport factory, password resolution
├── routeros_rest.py       # Existing: REST API client
└── routeros_ssh.py        # Existing: SSH client
```

### Pattern 1: Lightweight Config Extraction (No Config() Instantiation)

**What:** Parse YAML and extract only the fields needed for router communication and queue name lookup, without instantiating Config or SteeringConfig (which trigger validation side effects).

**When to use:** CLI tools that need config values but must not trigger daemon initialization code.

**Why:** Config.__init__() calls _load_specific_fields() which calls validate_bandwidth_order(), validate_threshold_order(), etc. These may raise errors for configs that are technically valid but have edge cases. The check_cake tool should not duplicate or depend on these validation chains.

**Example:**
```python
def _extract_router_config(data: dict) -> dict:
    """Extract router connection fields from raw YAML data.

    Returns a dict with keys needed to create a router client:
    router_host, router_user, router_transport, router_password,
    router_port, router_verify_ssl, ssh_key, timeout_ssh_command.
    """
    router = data.get("router", {})
    timeouts = data.get("timeouts", {})
    return {
        "router_host": router.get("host", ""),
        "router_user": router.get("user", "admin"),
        "router_transport": router.get("transport", "rest"),
        "router_password": router.get("password", ""),
        "router_port": router.get("port", 443),
        "router_verify_ssl": router.get("verify_ssl", True),
        "ssh_key": router.get("ssh_key", ""),
        "timeout_ssh_command": timeouts.get("ssh_command", 15),
    }
```

A simple SimpleNamespace or small dataclass can wrap this dict so it looks like a config object to get_router_client() / RouterOSREST.from_config().

### Pattern 2: Category Validators Returning list[CheckResult]

**What:** Each audit category is a function that returns `list[CheckResult]`. The main function collects all results and formats them.

**When to use:** Same pattern as check_config.py validators.

**Example:**
```python
def check_connectivity(client, transport: str, host: str, port: int) -> list[CheckResult]:
    """Test router reachability and authentication."""
    results = []
    try:
        if hasattr(client, 'test_connection'):
            ok = client.test_connection()
        else:
            # SSH: try a simple command
            rc, _, _ = client.run_cmd("/system/resource/print", capture=True, timeout=5)
            ok = rc == 0

        if ok:
            results.append(CheckResult(
                "Connectivity", "router",
                Severity.PASS,
                f"Router connectivity ({transport}, {host}:{port})"
            ))
        else:
            results.append(CheckResult(
                "Connectivity", "router",
                Severity.ERROR,
                f"Router connectivity failed ({transport}, {host}:{port}): authentication or access denied"
            ))
    except Exception as e:
        results.append(CheckResult(
            "Connectivity", "router",
            Severity.ERROR,
            f"Router connectivity failed ({transport}, {host}:{port}): {e}"
        ))
    return results
```

### Pattern 3: Early Termination on Connectivity Failure

**What:** If the connectivity check fails, skip all remaining router-dependent checks and append "Skipped: router unreachable" results for each.

**When to use:** Required by the locked decision -- router unreachable means skip all remaining checks.

**Example:**
```python
connectivity_results = check_connectivity(client, transport, host, port)
results.extend(connectivity_results)

# Check if connectivity failed
if any(r.severity == Severity.ERROR for r in connectivity_results):
    # Add skip notes for remaining categories
    for category in remaining_categories:
        results.append(CheckResult(
            category, "skipped", Severity.ERROR,
            f"Skipped: router unreachable"
        ))
    return results

# Continue with queue tree audit, CAKE type check, etc.
```

### Pattern 4: Direct REST/SSH API Calls for Queue Audit

**What:** Use RouterOSREST.get_queue_stats() or a targeted GET /rest/queue/tree?name=X query to fetch queue details. For SSH, use run_cmd with capture=True.

**When to use:** For CAKE-02 and CAKE-03 (queue existence and qdisc type verification).

**RouterOS REST API response for GET /rest/queue/tree?name=WAN-Download-Spectrum:**
```json
[
  {
    ".id": "*1",
    "name": "WAN-Download-Spectrum",
    "parent": "bridge1",
    "queue": "cake-down-spectrum",
    "max-limit": "940000000",
    "limit-at": "0",
    "priority": "8",
    "disabled": "false",
    "packets": "184614358",
    "bytes": "272603902153",
    "dropped": "0",
    "queued-packets": "0",
    "queued-bytes": "0",
    "rate": "0",
    "packet-rate": "0"
  }
]
```

**Key fields for audit:**
- `name`: Queue name (should match config)
- `queue`: Qdisc type (should start with "cake")
- `max-limit`: Current bandwidth limit in bps (string)
- Empty list `[]`: Queue does not exist

### Pattern 5: Mangle Rule Query for Steering

**What:** For steering configs, query GET /rest/ip/firewall/mangle?comment=X to check if the steering mangle rule exists.

**When to use:** CAKE-05 -- only for steering config type.

**Example:**
```python
def check_mangle_rule(client, mangle_comment: str, transport: str) -> list[CheckResult]:
    """Verify steering mangle rule exists on router."""
    results = []
    # For REST: GET /rest/ip/firewall/mangle?comment=<comment>
    # For SSH: /ip firewall mangle print where comment~"<comment>"
    # ... check if result is non-empty
    return results
```

### Anti-Patterns to Avoid
- **Instantiating Config() or SteeringConfig():** These trigger full validation chains, load logging config, and have side effects. Only access SCHEMA class attributes if needed.
- **Using FailoverRouterClient:** The check tool uses a single transport. If it fails, report the error. No failover.
- **Modifying router state:** The tool must be strictly GET-only. Never PATCH/POST.
- **Ignoring partial failures:** If download queue exists but upload queue doesn't, report both results independently, not bail out.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Output formatting | Custom formatter | check_config.format_results() / format_results_json() | Already handles colors, quiet mode, JSON, category grouping |
| Config type detection | New detection logic | check_config.detect_config_type() | Already handles topology vs continuous_monitoring detection |
| Password resolution | Custom env var expansion | router_client._resolve_password() or manual os.environ | Existing function handles ${VAR} pattern |
| Queue stats fetching | Custom HTTP calls | RouterOSREST.get_queue_stats() or ._handle_queue_tree_print() | Already parses name-filtered queue tree queries |
| CLI argument parsing | Custom arg handling | Copy create_parser() pattern from check_config | Ensures identical flags |

**Key insight:** This phase is primarily integration work. Every component exists; the task is wiring them together in a new module with the right error handling for a CLI context rather than a daemon context.

## Common Pitfalls

### Pitfall 1: Config Instantiation Side Effects
**What goes wrong:** Calling Config(config_path) triggers BaseConfig.__init__ which validates schema, loads all fields, calls validate_bandwidth_order, etc. This can fail on valid configs if there are environment-dependent paths (lock_file, state_file).
**Why it happens:** The Config classes were designed for daemon startup, not read-only CLI tools.
**How to avoid:** Extract only needed fields from raw YAML dict. Create a lightweight SimpleNamespace or dataclass for the router client factory.
**Warning signs:** Import errors, ConfigValidationError from unexpected fields.

### Pitfall 2: SSH Transport Has No test_connection()
**What goes wrong:** RouterOSSSH does not have a test_connection() method (confirmed by grep -- no matches). Code that calls `client.test_connection()` will fail with AttributeError for SSH transport.
**Why it happens:** RouterOSREST has test_connection() (GET /system/resource), but RouterOSSSH was designed for persistent daemon connections that auto-reconnect.
**How to avoid:** For SSH connectivity check, run a simple command like `/system/resource/print` and check return code == 0. Use hasattr() or transport type check before calling test_connection().
**Warning signs:** AttributeError on SSH transport.

### Pitfall 3: max-limit Is Dynamic During Congestion
**What goes wrong:** The `max-limit` field on the router reflects the current dynamically-adjusted rate, not the configured ceiling. During congestion, autorate reduces max-limit. Comparing config ceiling to current max-limit will often show a "diff" that is expected behavior, not a misconfiguration.
**Why it happens:** wanctl continuously adjusts max-limit via queue tree set commands.
**How to avoid:** Use ceiling_mbps as the "expected initial max-limit" but frame the check result carefully. Something like: "queue max-limit: 500000000 (current), ceiling: 940000000 (config). Note: max-limit changes dynamically during congestion."
**Warning signs:** False positives where a working system always shows "diff" in max-limit.

### Pitfall 4: REST API Returns All Values as Strings
**What goes wrong:** RouterOS REST API returns all values as strings (confirmed by MikroTik docs: "In JSON replies all object values are encoded as strings"). Comparing `max-limit` to integer ceiling without string conversion causes type mismatches.
**Why it happens:** RouterOS REST API design.
**How to avoid:** Always convert REST API response values with `int()` or `str()` before comparison.
**Warning signs:** Comparison failures, type errors.

### Pitfall 5: Steering Config Queue Names Have Defaults
**What goes wrong:** The steering config may not have explicit `cake_queues` section. The _load_cake_queues() method derives defaults from primary_wan: `WAN-Download-{primary_wan.capitalize()}`.
**Why it happens:** Configs like steering.yaml may omit cake_queues entirely.
**How to avoid:** When extracting queue names for steering configs, replicate the same defaulting logic: read cake_queues.primary_download or default to `WAN-Download-{topology.primary_wan.capitalize()}`.
**Warning signs:** KeyError when accessing cake_queues in steering config YAML.

### Pitfall 6: Password Env Var Check Must Happen Before Client Creation
**What goes wrong:** If ${ROUTER_PASSWORD} env var is unset, RouterOSREST gets empty password, connection fails with unhelpful auth error.
**Why it happens:** _resolve_password() silently returns "" for unset env vars.
**How to avoid:** Check for unresolved env vars before creating the router client. If password starts with "${" and the env var is not set, report a clear ERROR: "ROUTER_PASSWORD environment variable not set".
**Warning signs:** "401 Unauthorized" errors that should be "env var not set" errors.

## Code Examples

### Queue Name Extraction from Config Data
```python
# Source: src/wanctl/autorate_continuous.py:282-285 and steering/daemon.py:211-236

def _extract_queue_names(data: dict, config_type: str) -> dict[str, str]:
    """Extract expected queue names from raw YAML data.

    Returns dict with 'download' and 'upload' keys.
    """
    if config_type == "autorate":
        queues = data.get("queues", {})
        return {
            "download": queues.get("download", ""),
            "upload": queues.get("upload", ""),
        }
    else:  # steering
        topology = data.get("topology", {})
        primary_wan = topology.get("primary_wan", "wan1")
        cake_queues = data.get("cake_queues", {})
        default_dl = f"WAN-Download-{primary_wan.capitalize()}"
        default_ul = f"WAN-Upload-{primary_wan.capitalize()}"
        return {
            "download": cake_queues.get("primary_download", default_dl),
            "upload": cake_queues.get("primary_upload", default_ul),
        }
```

### Ceiling Extraction from Config Data
```python
# Source: src/wanctl/autorate_continuous.py:305, MBPS_TO_BPS=1_000_000

def _extract_ceilings(data: dict, config_type: str) -> dict[str, int | None]:
    """Extract expected ceiling values (bps) from raw YAML data.

    Returns dict with 'download' and 'upload' keys (None if not found).
    For autorate: continuous_monitoring.download.ceiling_mbps * 1_000_000
    For steering: no ceiling in steering config (steering doesn't set limits)
    """
    if config_type == "autorate":
        cm = data.get("continuous_monitoring", {})
        dl = cm.get("download", {})
        ul = cm.get("upload", {})
        dl_ceiling = dl.get("ceiling_mbps")
        ul_ceiling = ul.get("ceiling_mbps")
        return {
            "download": int(dl_ceiling * 1_000_000) if dl_ceiling else None,
            "upload": int(ul_ceiling * 1_000_000) if ul_ceiling else None,
        }
    else:  # steering has no ceiling config
        return {"download": None, "upload": None}
```

### Router Client Creation Without Config Object
```python
# Source: router_client.py, routeros_rest.py:141-175

from types import SimpleNamespace

def _create_audit_client(router_cfg: dict):
    """Create a router client from extracted config dict.

    Uses SimpleNamespace to satisfy the config interface expected by
    RouterOSREST.from_config() and RouterOSSSH.from_config().
    """
    ns = SimpleNamespace(**router_cfg)
    logger = logging.getLogger("wanctl.check_cake")

    transport = router_cfg["router_transport"]
    if transport == "rest":
        from wanctl.routeros_rest import RouterOSREST
        return RouterOSREST.from_config(ns, logger)
    elif transport == "ssh":
        from wanctl.routeros_ssh import RouterOSSSH
        return RouterOSSSH.from_config(ns, logger)
    else:
        raise ValueError(f"Unsupported transport: {transport}")
```

### Mangle Rule Comment Extraction
```python
# Source: configs/steering.yaml:33-34, steering/daemon.py:199-200

def _extract_mangle_comment(data: dict) -> str | None:
    """Extract mangle rule comment from steering config data."""
    mangle = data.get("mangle_rule", {})
    return mangle.get("comment")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual SSH to check queues | Automated CLI audit tool | Phase 83 (now) | Operators get one-command verification |
| Only offline config validation | Offline (check-config) + live router audit (check-cake) | Phase 83 (now) | Complete validation coverage |

**Deprecated/outdated:**
- `cake_queues.spectrum_download` / `spectrum_upload`: Deprecated in favor of `primary_download` / `primary_upload`. The deprecate_param() helper translates old names. check_cake should handle both.

## Open Questions

1. **Ceiling vs max-limit comparison for CAKE-04**
   - What we know: max-limit changes dynamically during congestion (autorate adjusts it every 50ms). Config ceiling_mbps is the initial/maximum value.
   - What's unclear: Should the diff be a WARN or just informational? Should we compare ceiling or skip the comparison?
   - Recommendation: For autorate configs, compare ceiling to max-limit. If they differ, report as PASS with an informational note showing both values (current max-limit vs config ceiling). This is expected behavior, not a problem. Only ERROR if the queue has a completely wrong max-limit (e.g., 0 or negative). For steering configs, there is no ceiling config -- skip max-limit comparison entirely.

2. **Steering config has no ceiling to compare against**
   - What we know: Steering daemon reads CAKE stats but does not set max-limit. Only autorate sets limits.
   - Recommendation: For steering configs, the queue audit checks existence + CAKE type only. No max-limit comparison.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (already configured) |
| Config file | pyproject.toml [tool.pytest] |
| Quick run command | `.venv/bin/pytest tests/test_check_cake.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CAKE-01 | Router connectivity probe (REST + SSH) | unit | `.venv/bin/pytest tests/test_check_cake.py -k connectivity -x` | No -- Wave 0 |
| CAKE-02 | Queue tree audit (exist + name + max-limit) | unit | `.venv/bin/pytest tests/test_check_cake.py -k queue_audit -x` | No -- Wave 0 |
| CAKE-03 | CAKE qdisc type verification | unit | `.venv/bin/pytest tests/test_check_cake.py -k cake_type -x` | No -- Wave 0 |
| CAKE-04 | Config-vs-router diff (expected vs actual) | unit | `.venv/bin/pytest tests/test_check_cake.py -k diff -x` | No -- Wave 0 |
| CAKE-05 | Mangle rule existence (steering only) | unit | `.venv/bin/pytest tests/test_check_cake.py -k mangle -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_check_cake.py -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_check_cake.py` -- all CAKE-01 through CAKE-05 tests
- [ ] Test fixtures for mock router responses (queue tree JSON, mangle rule JSON)
- [ ] Test fixtures for minimal autorate and steering config dicts
- [ ] No new framework install needed -- pytest already configured

## Sources

### Primary (HIGH confidence)
- `src/wanctl/check_config.py` -- Severity, CheckResult, format_results, format_results_json, detect_config_type, create_parser, main patterns
- `src/wanctl/routeros_rest.py` -- REST API client: test_connection(), get_queue_stats(), _handle_queue_tree_print(), _handle_mangle_rule(), _find_mangle_rule_id()
- `src/wanctl/routeros_ssh.py` -- SSH client: no test_connection() method (confirmed)
- `src/wanctl/router_client.py` -- get_router_client(), _resolve_password(), transport factory
- `src/wanctl/autorate_continuous.py` -- Config class, SCHEMA, queue names (queues.download/upload), ceiling_mbps, MBPS_TO_BPS
- `src/wanctl/steering/daemon.py` -- SteeringConfig class, SCHEMA, _load_cake_queues(), _load_mangle_config(), mangle_rule_comment
- `src/wanctl/steering/cake_stats.py` -- CakeStatsReader._parse_json_response() shows REST API response field names
- `configs/spectrum.yaml` -- Production autorate config (queue names, ceiling values)
- `configs/steering.yaml` -- Production steering config (mangle rule comment, topology)
- `pyproject.toml` -- console_scripts entry point pattern

### Secondary (MEDIUM confidence)
- [MikroTik REST API docs](https://help.mikrotik.com/docs/spaces/ROS/pages/47579162/REST+API) -- All JSON values are strings, query parameter filtering

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all code is internal, no external research needed
- Architecture: HIGH -- follows established check_config pattern exactly
- Pitfalls: HIGH -- identified from reading actual codebase (SSH missing test_connection, dynamic max-limit, REST string values, steering defaults)

**Research date:** 2026-03-13
**Valid until:** 2026-04-13 (stable -- internal codebase patterns unlikely to change)
