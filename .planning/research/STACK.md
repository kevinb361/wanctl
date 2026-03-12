# Technology Stack: v1.16 Validation & Operational Confidence

**Project:** wanctl v1.16
**Researched:** 2026-03-12
**Overall confidence:** HIGH

## Recommendation: Zero New Dependencies

This milestone requires no new runtime or dev dependencies. The existing codebase already has every building block needed for config validation, CAKE qdisc auditing, and read-only router integration probes. The research below explains what already exists, what to build on top of it, and why adding libraries would be counterproductive.

---

## Existing Stack (Already Sufficient)

### Config Validation Infrastructure

| Existing Component | Location | What It Provides |
|---|---|---|
| `BaseConfig` | `config_base.py` | Schema-driven validation with `BASE_SCHEMA` + subclass `SCHEMA`. `validate_schema()` aggregates errors. `validate_field()` handles type/range/choices. `validate_identifier()` / `validate_comment()` / `validate_ping_host()` for security. |
| `ConfigValidationError` | `config_base.py` | Custom exception with multi-error formatting (`"N error(s):\n - ..."`) |
| `validate_field()` | `config_base.py` | Single-field validation: type, required, min/max, choices, dot-notation path traversal |
| `validate_schema()` | `config_base.py` | Multi-field batch validation: collects all errors before raising |
| `validate_bandwidth_order()` | `config_validation_utils.py` | 4-state floor ordering: `floor_red <= floor_soft_red <= floor_yellow <= floor_green <= ceiling` |
| `validate_threshold_order()` | `config_validation_utils.py` | Threshold ordering: `target < warn < hard_red` |
| `validate_alpha()` | `config_validation_utils.py` | EWMA alpha range validation |
| `validate_baseline_rtt()` | `config_validation_utils.py` | RTT sanity bounds (10-60ms) |
| `validate_rtt_thresholds()` | `config_validation_utils.py` | RTT threshold ordering with defaults |
| `validate_sample_counts()` | `config_validation_utils.py` | Sample count reasonableness |
| `deprecate_param()` | `config_validation_utils.py` | Legacy parameter warn+translate |
| `Config(BaseConfig)` | `autorate_continuous.py` | Autorate-specific config with SCHEMA |
| `SteeringConfig(BaseConfig)` | `steering/daemon.py` | Steering-specific config with SCHEMA |

**Assessment:** The validation framework is mature. `validate_schema()` already collects errors, `validate_field()` handles type coercion (int-to-float), and `BaseConfig.__init__()` chains base + subclass schema validation. The gap is not infrastructure -- it is coverage (many config fields bypass schema validation and are loaded with raw `.get()` calls).

### Router Communication Infrastructure

| Existing Component | Location | What It Provides |
|---|---|---|
| `RouterOSREST` | `routeros_rest.py` | REST API client with session, caching, queue/mangle operations. `get_queue_stats()` returns full queue properties. `test_connection()` hits `/system/resource`. |
| `RouterOSSSH` | `routeros_ssh.py` | SSH client via paramiko. Persistent connection. `run_cmd()` with capture. |
| `FailoverRouterClient` | `router_client.py` | REST-primary with SSH fallback, auto-restore. |
| `RouterOSBackend` | `backends/routeros.py` | Abstract backend implementation. `get_queue_stats()`, `get_bandwidth()`, `test_connection()`. |
| `CakeStatsReader` | `steering/cake_stats.py` | Reads CAKE queue stats via `/queue/tree print stats detail`. Parses both JSON (REST) and text (SSH). |
| `RouterConnectivityState` | `router_connectivity.py` | Failure tracking, classification, outage duration. |
| `CommandResult[T]` | `router_command_utils.py` | Typed result with `ok()`/`err()`, `unwrap()`, `map()`. |

**Assessment:** Everything needed for read-only router probes exists. `RouterOSREST` can already do `GET /rest/queue/tree`, `GET /rest/queue/type`, and `GET /rest/system/resource`. The gap is that there is no method to query queue types (CAKE parameters) specifically -- only queue tree entries. A simple `_request("GET", "/rest/queue/type", ...)` call is needed.

### Test Infrastructure

| Existing Component | Location | What It Provides |
|---|---|---|
| `pytest.mark.integration` | `tests/integration/conftest.py` | Registered marker for integration tests |
| `pytest.mark.slow` | `tests/integration/conftest.py` | Registered marker for slow tests |
| `--with-controller` | `tests/integration/conftest.py` | CLI option for SSH controller monitoring |
| `--integration-output` | `tests/integration/conftest.py` | Output directory for integration results |
| `check_dependencies` | `tests/integration/conftest.py` | Session fixture checking external tool availability |
| Contract test pattern | `test_deployment_contracts.py` | Parametrize from `pyproject.toml` for auto-generated test cases |

**Assessment:** The integration test framework exists but is oriented toward load testing (flent/netperf). For read-only router probes, we need a new marker (`pytest.mark.router` or `pytest.mark.probe`) and a fixture that provides a live `RouterOSREST` client from config. This is configuration, not library work.

---

## Why NOT Add New Libraries

### Pydantic (REJECTED)

| Criterion | Assessment |
|---|---|
| **Current state** | `BaseConfig` + `validate_schema()` already provides typed validation with error aggregation |
| **What Pydantic adds** | Automatic type coercion, nested model validation, JSON Schema export |
| **What it costs** | ~10MB install, C extension (pydantic-core), new dep for production containers |
| **Why reject** | The validation framework is complete. Adding Pydantic would require rewriting `BaseConfig`, `Config`, and `SteeringConfig` -- a massive refactor for no functional gain. The existing `validate_schema()` with `validate_field()` does the same thing Pydantic models do, just declaratively via dicts instead of classes. The project constraint ("No breaking changes") makes this a non-starter. |

**Confidence:** HIGH -- The existing validation framework handles every case needed for v1.16. Pydantic would be a rewrite, not an improvement.

### Cerberus (REJECTED)

| Criterion | Assessment |
|---|---|
| **What it adds** | Schema-based validation without type classes |
| **Why reject** | `validate_schema()` in `config_base.py` is already a Cerberus-like schema validator. Adding Cerberus would duplicate existing functionality with a different API. |

### JSON Schema / jsonschema library (REJECTED)

| Criterion | Assessment |
|---|---|
| **What it adds** | Standards-based schema validation |
| **Why reject** | YAML config validation with runtime type coercion (YAML parses `10` as int, not float) is poorly served by JSON Schema. The existing `validate_field()` already handles int-to-float coercion. JSON Schema adds complexity without solving the actual problem. |

---

## What to Build (Using Existing Stack)

### 1. Config Validator CLI (`wanctl check-config`)

**Technology:** stdlib `argparse` (consistent with `wanctl-history`), existing `BaseConfig` / `Config` / `SteeringConfig` classes.

**Approach:** Instantiate the appropriate config class (which triggers validation in `__init__`), catch `ConfigValidationError`, format results for CLI output. Add cross-field validations that currently happen at runtime (e.g., queue names reference valid queue types, state file paths are writable, ping hosts are reachable).

**New validation areas to cover using existing `validate_field()`:**

| Config Section | Current State | What to Add |
|---|---|---|
| `queues.download` / `queues.upload` | Loaded via `.get()`, no schema | Add to SCHEMA with `validate_identifier()` |
| `continuous_monitoring.download.*` | Ad-hoc validation in `Config.__init__` | Formalize via SCHEMA entries |
| `continuous_monitoring.thresholds.*` | Partial (threshold ordering validated) | Complete the SCHEMA coverage |
| `timeouts.*` | Loaded via `.get()` | Add min/max range to SCHEMA |
| `state_file` / `state.file` | Loaded as raw string | Validate path writability |
| `ping_hosts` | Loaded as list, `validate_ping_host()` exists | Iterate and validate each host |
| `topology.*` | Loaded via `.get()` | Add to SteeringConfig SCHEMA |
| `confidence.*` | Loaded via `.get()` with defaults | Add range validation to SCHEMA |
| `wan_state.*` | Has runtime warn+disable | Formalize as SCHEMA entries |
| `alerting.*` | Loaded via `.get()` | Add to SCHEMA |

### 2. CAKE Qdisc Audit (`wanctl check-cake`)

**Technology:** Existing `RouterOSREST` client (or `FailoverRouterClient`).

**RouterOS REST API endpoints to query:**

| Endpoint | Method | Purpose | Response |
|---|---|---|---|
| `GET /rest/queue/tree?name=<queue>` | GET | Get queue tree entry | JSON array with `queue` (type reference), `max-limit`, `parent`, etc. |
| `GET /rest/queue/type?name=<type>` | GET | Get queue type definition | JSON array with CAKE params: `cake-bandwidth`, `cake-flowmode`, `cake-diffserv`, `cake-rtt`, `cake-overhead`, etc. |
| `GET /rest/system/resource` | GET | Router identity/version check | JSON with `version`, `board-name`, etc. |

**CAKE parameters to audit (from RouterOS `/queue/type`):**

| Parameter | Expected For Cable (Spectrum) | Expected For DSL (ATT) | Why Check |
|---|---|---|---|
| `cake-overhead-scheme` | `docsis` or `ethernet` | `pppoe-ptm` or `pppoe-llc` | Wrong overhead causes throughput errors |
| `cake-flowmode` | `triple-isolate` (default) | `triple-isolate` | Wrong mode affects fairness |
| `cake-diffserv` | `diffserv3` or `diffserv4` | `diffserv3` or `diffserv4` | Mismatched diffserv wastes tins |
| `cake-rtt` or `cake-rtt-scheme` | `internet` (~100ms) | `internet` | Wrong RTT causes AQM timing errors |
| `cake-ack-filter` | depends on asymmetry | depends | Missing on asymmetric links hurts upload |
| `cake-nat` | `true` if behind NAT | `true` if behind NAT | Missing NAT breaks per-flow fairness |
| Queue `max-limit` | Matches `ceiling_mbps` from config | Matches config | Config/router mismatch = silent degradation |

**Implementation:** New method on `RouterOSREST` to `GET /rest/queue/type` (trivial -- same pattern as `get_queue_stats()`). Compare returned CAKE parameters against expected values from wanctl config. Report mismatches.

### 3. Integration Probes

**Technology:** pytest with new `@pytest.mark.router` marker, existing router client infrastructure.

**New marker and fixtures (in `tests/integration/conftest.py`):**

```python
# New marker
config.addinivalue_line(
    "markers",
    "router: marks tests that probe a live router (deselect with '-m \"not router\"')",
)

# New CLI option
parser.addoption(
    "--router-config",
    type=str,
    default=None,
    help="Path to wanctl config YAML for router probe tests",
)

# New fixture
@pytest.fixture(scope="session")
def router_client(request):
    """Provide a live RouterOSREST client from config."""
    config_path = request.config.getoption("--router-config")
    if config_path is None:
        pytest.skip("--router-config not provided")
    # ... create client from config
```

**Probes to implement (all read-only):**

| Probe | What It Tests | Router Command |
|---|---|---|
| REST connectivity | Can we reach the router REST API? | `GET /rest/system/resource` |
| Queue tree exists | Do configured queues exist on router? | `GET /rest/queue/tree?name=<queue>` |
| Queue type is CAKE | Is the queue type actually CAKE? | `GET /rest/queue/type?name=<type>` |
| CAKE params match | Do CAKE params match expected config? | `GET /rest/queue/type?name=<type>` |
| Mangle rule exists | Does the steering mangle rule exist? | `GET /rest/ip/firewall/mangle?comment=<comment>` |
| State file readable | Can we read the state file? | Local filesystem |
| State file valid JSON | Is the state file valid? | `json.loads()` |

---

## New Entry Points

```toml
# pyproject.toml additions
[project.scripts]
wanctl-check-config = "wanctl.check_config:main"
wanctl-check-cake = "wanctl.check_cake:main"
```

**Pattern:** Follow existing `wanctl-history` CLI pattern: `argparse` for argument parsing, config path as required argument, structured text output with exit codes (0=pass, 1=warnings, 2=errors).

---

## Version Compatibility

No new packages. All existing dependencies remain at current pinned versions.

| Package | Current Pin | Milestone Use |
|---|---|---|
| `pyyaml>=6.0.1` | Config loading for validation | No change |
| `requests>=2.31.0` | RouterOS REST API for CAKE audit | No change |
| `paramiko>=3.4.0` | RouterOS SSH fallback for probes | No change |
| `tabulate>=0.9.0` | CLI output formatting for check results | No change |
| `pytest>=8.0.0` | Integration probe test framework | No change |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|---|---|---|---|
| Config validation | Extend existing `validate_schema()` | Pydantic BaseModel rewrite | Rewrite of 3 config classes for no functional gain. Production risk. |
| Config validation | Extend existing `validate_schema()` | Cerberus schema library | Duplicates existing `validate_schema()` with different API. |
| Config validation | Extend existing `validate_schema()` | JSON Schema / jsonschema | Poor YAML type coercion handling. Adds dependency. |
| CAKE querying | Extend `RouterOSREST` with `get_queue_type()` | New library (routeros-api) | Project already has REST + SSH clients. Adding a third is waste. |
| CLI framework | stdlib `argparse` | Click / Typer | Consistent with existing CLIs (`wanctl-history`). Simple subcommands. |
| CLI output | `tabulate` (existing dep) | Rich console | tabulate is already a dep, sufficient for check results. |
| Integration probes | pytest markers + fixtures | Standalone probe script | pytest infrastructure exists, markers/fixtures compose naturally. |

---

## What NOT to Add

| Avoid | Why | Use Instead |
|---|---|---|
| pydantic | Requires rewriting BaseConfig/Config/SteeringConfig. No functional gain. | Extend existing `validate_schema()` + `validate_field()` |
| cerberus | Duplicates existing validation framework | Existing `validate_schema()` |
| jsonschema | Poor YAML type coercion | Existing `validate_field()` with int-to-float handling |
| routeros-api / librouteros | Third router client alongside REST + SSH | Extend `RouterOSREST` with one new GET method |
| click / typer | Inconsistent with existing CLIs | `argparse` (stdlib) |
| pytest-docker | Overkill for read-only probes against existing router | Live router fixture with `--router-config` |
| rich (explicit) | Not needed for CLI tools | `tabulate` (existing dep) for structured output |

---

## Confidence Assessment

| Area | Level | Reason |
|---|---|---|
| Config validation approach | HIGH | Existing framework is mature (validate_schema, validate_field, BaseConfig). Just extending coverage. |
| CAKE qdisc querying | HIGH | RouterOS REST API pattern is identical to existing `get_queue_stats()`. GET /rest/queue/type follows same endpoint structure. Verified via official MikroTik docs. |
| Integration probes | HIGH | pytest marker/fixture infrastructure exists. New marker + fixture is configuration, not novel code. |
| Zero new deps | HIGH | Every capability needed exists in the codebase or stdlib. |
| RouterOS REST response format | MEDIUM | MikroTik docs confirm JSON response with string-encoded values and `.id` field. Exact CAKE parameter names in REST JSON response should be verified against live router (names may use hyphens vs underscores). |

---

## Sources

- [MikroTik CAKE Documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/196345874/CAKE) -- CAKE parameters: cake-bandwidth, cake-flowmode, cake-diffserv, cake-rtt, cake-overhead-scheme, etc.
- [MikroTik Queue Tree Documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/328088/Queues) -- Queue tree properties: name, parent, queue (type reference), max-limit, statistics fields
- [MikroTik REST API Documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/47579162/REST+API) -- GET/POST/PATCH patterns, JSON response format, filtering
- [Queue Tree Properties Reference](https://mikrotikdocs.fyi/queues/queue-tree/) -- Full property list including read-only statistics
- Direct codebase analysis: `config_base.py`, `config_validation_utils.py`, `routeros_rest.py`, `routeros_ssh.py`, `router_client.py`, `steering/cake_stats.py`, `backends/routeros.py`, `tests/integration/conftest.py`

---
*Stack research for: wanctl v1.16 Validation & Operational Confidence*
*Researched: 2026-03-12*
