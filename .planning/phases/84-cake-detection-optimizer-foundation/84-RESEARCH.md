# Phase 84: CAKE Detection & Optimizer Foundation - Research

**Researched:** 2026-03-13
**Domain:** MikroTik RouterOS CAKE queue type parameter detection via REST API
**Confidence:** HIGH

## Summary

Phase 84 extends the existing `wanctl-check-cake` CLI tool (from v1.16) with two new check categories: "CAKE Params" (link-independent) and "Link Params" (link-dependent). The implementation reads queue type parameters from `/rest/queue/type` via a new `get_queue_type()` method on `RouterOSREST`, compares them against known-optimal defaults and YAML config values, and reports diffs using the existing `CheckResult`/`Severity` model.

The critical unknown -- RouterOS REST API field names for CAKE queue type parameters -- is now resolved. The REST API uses identical field names to the CLI (hyphenated, prefixed with `cake-`). The `GET /rest/queue/type` endpoint returns JSON objects with fields like `cake-flowmode`, `cake-diffserv`, `cake-nat`, `cake-ack-filter`, `cake-wash`, `cake-overhead`, `cake-rtt`, and `cake-rtt-scheme`. All values are returned as strings.

This is a pure extension of existing infrastructure. No new dependencies. No new CLI tools. No new data models. The CheckResult/Severity model, format_results/format_results_json formatting, and run_audit orchestrator pipeline all remain unchanged -- just extended with new check functions injected into the pipeline.

**Primary recommendation:** Add a `get_queue_types()` method to `RouterOSREST` that calls `GET /rest/queue/type?name={type_name}`, then implement `check_cake_params()` and `check_link_params()` functions in `check_cake.py` following the exact pattern of existing `check_queue_tree()`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Optimal CAKE defaults (link-independent): flowmode=triple-isolate, diffserv=diffserv4, nat=yes, ack-filter=yes (mapped to "filter" in RouterOS), wash=direction-dependent (yes for download, no for upload)
- wash=yes on upload queue produces WARNING severity ("sub-optimal: clears your own DSCP marks on egress")
- Direction mapping: follow queue tree -> queue type linkage via `queue` field, direction inherited from queue tree entry
- Output groups checks per-direction: "CAKE Params (download)" and "CAKE Params (upload)"
- cake_optimization YAML config block: overhead and rtt, single value per WAN (not per-direction)
- Config format: `cake_optimization: { overhead: 18, rtt: 100ms }`
- Spectrum: overhead=18 (DOCSIS); ATT: overhead TBD; RTT: 100ms for both WANs
- Missing config behavior: absent cake_optimization section -> skip link-dependent checks, run link-independent only, report INFO
- Severity: link-independent sub-optimal = WARNING, link-dependent sub-optimal = ERROR, matching = PASS
- Diff format: `current_value -> recommended_value` with rationale, using CheckResult message + suggestion fields
- Integration: new categories added to existing run_audit() pipeline, runs after queue tree checks
- Same output formatting, same exit code logic (ERROR->1, WARNING->2, PASS->0)
- JSON output includes new categories via existing format_results_json()

### Claude's Discretion
- Exact RouterOS REST API field names for /rest/queue/type (resolved by research -- see below)
- Internal function decomposition within check_cake.py
- Test fixture design for queue type API responses
- How to handle queue types shared between multiple queue tree entries

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CAKE-01 | Operator can see sub-optimal CAKE queue type parameters flagged with severity and rationale | CheckResult model carries severity + message (diff) + suggestion (rationale). Existing format_results() renders this. New check functions produce CheckResult lists. |
| CAKE-02 | Detection reads queue type params from router via REST API (`GET /rest/queue/type`) | New `get_queue_types()` method on RouterOSREST. REST API returns JSON with cake-* fields as strings. Field names match CLI names exactly. |
| CAKE-03 | Detection compares link-independent params (flowmode, nat, ack-filter, wash, diffserv) against known-optimal defaults | Optimal defaults locked in CONTEXT.md. RouterOS field names: cake-flowmode, cake-diffserv, cake-nat, cake-ack-filter, cake-wash. Values are strings ("yes"/"no", "triple-isolate", etc.). |
| CAKE-04 | Detection compares link-dependent params (overhead, RTT) against values specified in YAML config | New cake_optimization YAML block. RouterOS field names: cake-overhead, cake-rtt. cake-overhead is an integer-as-string, cake-rtt is a time string (e.g., "100ms"). |
| CAKE-05 | Detection shows diff output of current vs recommended values for each sub-optimal parameter | CheckResult.message carries "current -> recommended", CheckResult.suggestion carries rationale. Existing format_results() renders inline. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12 | Runtime | Project standard |
| requests | existing | HTTP client for REST API | Already used by RouterOSREST |
| PyYAML | existing | Config parsing | Already used by check_cake.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | existing | Test framework | All tests |
| unittest.mock | stdlib | Mock router responses | Test fixtures |

### Alternatives Considered
None. This phase uses exclusively existing project infrastructure. Zero new dependencies.

**Installation:**
```bash
# No new packages needed
```

## Architecture Patterns

### Recommended Project Structure
```
src/wanctl/
  check_cake.py          # Extended with check_cake_params() + check_link_params()
  routeros_rest.py       # Extended with get_queue_types() method
tests/
  test_check_cake.py     # Extended with new test classes
configs/
  spectrum.yaml          # Add cake_optimization: section
  att.yaml               # Add cake_optimization: section
```

### Pattern 1: Check Function Pattern (established in v1.16)
**What:** Each check function takes a client + config data, returns `list[CheckResult]`.
**When to use:** Every new check category.
**Example:**
```python
# Source: check_cake.py existing pattern
def check_cake_params(
    queue_type_data: dict,
    direction: str,
) -> list[CheckResult]:
    """Compare CAKE queue type params against optimal defaults.

    Args:
        queue_type_data: JSON response from GET /rest/queue/type
        direction: "download" or "upload" (for wash direction logic)

    Returns:
        List of CheckResult with category "CAKE Params ({direction})"
    """
    results: list[CheckResult] = []
    category = f"CAKE Params ({direction})"

    # Example: flowmode check
    actual = queue_type_data.get("cake-flowmode", "")
    expected = "triple-isolate"
    if actual == expected:
        results.append(CheckResult(category, "flowmode", Severity.PASS,
            f"flowmode: {actual} (optimal)"))
    else:
        results.append(CheckResult(category, "flowmode", Severity.WARN,
            f"flowmode: {actual} -> {expected}",
            suggestion="Per-host + per-flow isolation for multi-device networks"))
    # ... repeat for each param
    return results
```

### Pattern 2: Queue Type Retrieval via REST API
**What:** New method on RouterOSREST that fetches queue type details by name.
**When to use:** Whenever reading queue type parameters from the router.
**Example:**
```python
# Source: routeros_rest.py extension pattern (follows get_queue_stats)
def get_queue_types(self, type_name: str) -> dict | None:
    """Get queue type parameters by name.

    Args:
        type_name: Name of the queue type (e.g., "cake-down-spectrum")

    Returns:
        Dict with queue type params or None if not found
    """
    url = f"{self.base_url}/queue/type"
    try:
        resp = self._request("GET", url, params={"name": type_name}, timeout=self.timeout)
        if resp.ok and resp.json():
            items = resp.json()
            if items:
                return items[0]
        return None
    except requests.RequestException as e:
        self.logger.error(f"REST API error: {e}")
        return None
```

### Pattern 3: Pipeline Extension in run_audit()
**What:** Insert new check step between queue tree and mangle checks.
**When to use:** Adding new audit categories to the existing pipeline.
**Example:**
```python
# Inside run_audit(), after step 3 (queue tree audit):
# 3.5 CAKE queue type parameter checks
# Extract queue type names from queue tree results
# For each direction, fetch queue type and run checks
```

### Pattern 4: YAML Config Extraction
**What:** Pure function to extract cake_optimization values from raw YAML data.
**When to use:** Reading link-dependent params from config.
**Example:**
```python
def _extract_cake_optimization(data: dict) -> dict | None:
    """Extract cake_optimization section from YAML data.

    Returns None if section is absent (triggers skip of link-dependent checks).
    """
    return data.get("cake_optimization")
```

### Anti-Patterns to Avoid
- **Never instantiate Config():** Check tools use SCHEMA class attrs only, never the full Config() constructor. Raw YAML data dict is the input.
- **Never auto-detect link type:** Overhead and RTT come from YAML config only. No guessing from WAN name.
- **Never modify router state:** check_cake.py is strictly read-only. All modifications are Phase 85 scope.
- **Don't duplicate format logic:** Use existing CheckResult/format_results infrastructure. No custom formatting.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Result formatting | Custom print logic | `format_results()` / `format_results_json()` from check_config.py | Already handles color, quiet mode, JSON, category grouping |
| Router communication | Raw HTTP calls | `RouterOSREST` class with `_request()` wrapper | Handles SSL warnings, session management, caching |
| Config type detection | Manual YAML inspection | `detect_config_type()` from check_config.py | Already handles autorate vs steering detection |
| Exit code logic | Custom severity counting | Existing `main()` exit code pattern | 0=pass, 1=error, 2=warning already works |
| Direction mapping | New direction extraction | Existing `_extract_queue_names()` + `check_queue_tree()` output | Already maps queue tree entries to directions |

**Key insight:** Everything in this phase is extension, not creation. The v1.16 infrastructure provides all the patterns. The only genuinely new code is (1) the REST call to `/rest/queue/type`, (2) comparison logic for CAKE params, and (3) the `cake_optimization` YAML extraction.

## Common Pitfalls

### Pitfall 1: RouterOS REST API Returns All Values as Strings
**What goes wrong:** Comparing integer overhead `18` against string `"18"` fails silently.
**Why it happens:** MikroTik REST API serializes ALL values as strings, even numbers and booleans.
**How to avoid:** Always compare as strings, or explicitly convert. `queue_type_data.get("cake-overhead", "")` returns `"18"` not `18`. YAML config values need string conversion before comparison.
**Warning signs:** Tests pass with mock dicts but fail against real router responses.

### Pitfall 2: cake-ack-filter Value Mapping
**What goes wrong:** CONTEXT.md says "ack-filter: yes" but RouterOS uses `"filter"` not `"yes"`.
**Why it happens:** Unlike cake-nat and cake-wash (which use "yes"/"no"), cake-ack-filter uses `"none"`, `"filter"`, or `"aggressive"`.
**How to avoid:** Map the optimal default as `"filter"` (not `"yes"`). The CONTEXT.md decision "ack-filter: yes" means "enabled" which maps to RouterOS value `"filter"`.
**Warning signs:** Every router shows ack-filter as "sub-optimal" even when correctly configured.

### Pitfall 3: Queue Type Shared Between Multiple Queue Tree Entries
**What goes wrong:** Both download and upload queue tree entries may reference the same queue type name, or different names.
**Why it happens:** Router admin may create one CAKE type per direction (cake-down-spectrum, cake-up-spectrum) or share one type.
**How to avoid:** Extract queue type name per-direction from queue tree `queue` field. If both directions use the same type name, the wash check must still evaluate per-direction (same type, different expected wash values).
**Warning signs:** wash check reports optimal for download but the upload check also says optimal (should be opposite).

### Pitfall 4: cake-rtt Format Comparison
**What goes wrong:** YAML config has `rtt: 100ms` but router returns `"100ms"` or possibly just `"100"` or a preset name like `"internet"`.
**Why it happens:** RouterOS may return the RTT as a time string or as the preset keyword.
**How to avoid:** Accept both raw time values and preset equivalents. `"100ms"` matches the `internet` preset. Strip "ms" suffix for numeric comparison if needed. Also handle `cake-rtt-scheme` field which may contain the preset name.
**Warning signs:** RTT shows as sub-optimal even when effectively identical.

### Pitfall 5: Missing Queue Type on Router
**What goes wrong:** `GET /rest/queue/type?name=cake-down-spectrum` returns empty list.
**Why it happens:** Queue tree references a type name that was deleted or renamed on the router.
**How to avoid:** Handle None return from `get_queue_types()` gracefully. Report as ERROR with suggestion to verify queue type exists. Don't crash.
**Warning signs:** Unhandled NoneType errors in production.

### Pitfall 6: KNOWN_AUTORATE_PATHS Not Updated
**What goes wrong:** `wanctl-check-config` reports "unknown key: cake_optimization" warning.
**Why it happens:** New YAML config block `cake_optimization` not added to `KNOWN_AUTORATE_PATHS` set in check_config.py.
**How to avoid:** Add `"cake_optimization"`, `"cake_optimization.overhead"`, `"cake_optimization.rtt"` to `KNOWN_AUTORATE_PATHS`.
**Warning signs:** check-config shows spurious warnings for valid new config keys.

## Code Examples

Verified patterns from existing codebase:

### RouterOS REST API Response Format (queue/type)
```python
# Based on: MikroTik REST API docs - all values are strings
# GET /rest/queue/type?name=cake-down-spectrum
# Expected response (single-item list):
[
    {
        ".id": "*A",
        "name": "cake-down-spectrum",
        "kind": "cake",
        "cake-flowmode": "triple-isolate",
        "cake-diffserv": "diffserv4",
        "cake-nat": "yes",
        "cake-ack-filter": "filter",
        "cake-wash": "yes",
        "cake-overhead": "18",
        "cake-overhead-scheme": "none",
        "cake-rtt": "100ms",
        "cake-rtt-scheme": "internet",
        "cake-bandwidth": "0",
        "cake-autorate-ingress": "no",
        "cake-mpu": "0",
        "cake-atm": "no",
        "cake-memlimit": "0",
    }
]
```

**IMPORTANT:** The exact field names and their default/empty values should be verified against a live router during implementation. The field names above are HIGH confidence (documented in official MikroTik docs), but the default/empty value representations (e.g., `"0"` vs `""` for unset overhead) need live verification.

### Existing CheckResult Usage Pattern
```python
# Source: check_cake.py:273-279
results.append(
    CheckResult(
        "Queue Tree",           # category
        f"{direction}_queue",   # field
        Severity.PASS,          # severity
        f"Queue exists: {queue_name}",  # message
    )
)

# With suggestion (for sub-optimal):
results.append(
    CheckResult(
        "CAKE Type",
        f"{direction}_type",
        Severity.ERROR,
        f"Wrong qdisc type for {direction}: '{qdisc_type}' (expected cake*)",
        suggestion="Set queue type to a CAKE qdisc on router",
    )
)
```

### Existing get_queue_stats Pattern to Follow
```python
# Source: routeros_rest.py:649-672
def get_queue_stats(self, queue_name: str) -> dict | None:
    url = f"{self.base_url}/queue/tree"
    try:
        resp = self._request("GET", url, params={"name": queue_name}, timeout=self.timeout)
        if resp.ok and resp.json():
            items = resp.json()
            if items:
                return items[0]
        return None
    except requests.RequestException as e:
        self.logger.error(f"REST API error: {e}")
        return None
```

### CAKE Params Optimal Defaults (from CONTEXT.md decisions)
```python
# Link-independent optimal defaults
OPTIMAL_CAKE_DEFAULTS = {
    "cake-flowmode": "triple-isolate",
    "cake-diffserv": "diffserv4",
    "cake-nat": "yes",
    "cake-ack-filter": "filter",  # NOTE: "yes" in discussion = "filter" in RouterOS
}

# wash is direction-dependent:
OPTIMAL_WASH = {
    "download": "yes",   # Clear ISP DSCP marks on ingress
    "upload": "no",      # Preserve your own DSCP marks on egress
}
```

### Queue Type Name Extraction from Queue Tree
```python
# Source: check_cake.py check_queue_tree() already extracts queue type name
# at line 283: qdisc_type = stats.get("queue", "")
# This "queue" field contains the queue type name (e.g., "cake-down-spectrum")
# Pass this downstream to the new queue type param checks.
```

## RouterOS REST API Field Reference

**Confidence: HIGH** -- Field names confirmed from official MikroTik CAKE documentation and Queue Type properties table.

| REST API Field | CLI Name | Type | Allowed Values | Default |
|----------------|----------|------|----------------|---------|
| `cake-flowmode` | cake-flowmode | string | flowblind, srchost, dsthost, hosts, flows, dual-srchost, dual-dsthost, triple-isolate | triple-isolate |
| `cake-diffserv` | cake-diffserv | string | besteffort, precedence, diffserv3, diffserv4, diffserv8 | diffserv3 |
| `cake-nat` | cake-nat | string | yes, no | no |
| `cake-ack-filter` | cake-ack-filter | string | none, filter, aggressive | none |
| `cake-wash` | cake-wash | string | yes, no | no |
| `cake-overhead` | cake-overhead | string (int) | -64 to 256 | (unset/0) |
| `cake-overhead-scheme` | cake-overhead-scheme | string | raw, conservative, pppoa-vcmux, pppoe-llc, pppoe-ptm, bridged-ptm, docsis, ethernet, ether-vlan | (none) |
| `cake-rtt` | cake-rtt | string (time) | time value (e.g., "100ms") | 100ms |
| `cake-rtt-scheme` | cake-rtt-scheme | string | datacentre, lan, metro, regional, internet, oceanic, satellite, interplanetary, none | (none) |
| `cake-bandwidth` | cake-bandwidth | string (int) | bandwidth value | 0 |
| `cake-atm` | cake-atm | string | yes, no | no |
| `cake-mpu` | cake-mpu | string (int) | -64 to 256 | 0 |
| `cake-memlimit` | cake-memlimit | string (int) | bytes | 0 |
| `cake-autorate-ingress` | cake-autorate-ingress | string | yes, no | no |

**Critical note:** All values returned as strings per RouterOS REST API convention. The `cake-flowmode` field on the Queues documentation page lists `nat` and `nonat` as flowmode options (in addition to those above), but these appear to be aliases and the canonical boolean is `cake-nat`.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual `queue type print` and visual inspection | Automated comparison via `wanctl-check-cake` | v1.16 (phase 83, 2026-03-13) | Foundation exists; this phase adds parameter-level checks |
| Separate overhead keywords per link type | RouterOS `cake-overhead` numeric + `cake-overhead-scheme` keyword | RouterOS 7.1+ | Must handle both numeric and scheme-based overhead |
| diffserv3 as default | diffserv4 recommended for home networks | Community consensus | diffserv4 gives 4-tier prioritization matching WiFi WMM |

**Deprecated/outdated:**
- None relevant. CAKE in RouterOS has been stable since 7.1 (2021).

## Open Questions

1. **Exact default/empty values for unset cake-overhead**
   - What we know: When no overhead is configured, the field likely returns `"0"` or an empty string
   - What's unclear: The exact string representation needs live router verification
   - Recommendation: Handle both `"0"` and `""` as "unset". Verify during implementation against live router.

2. **cake-rtt-scheme vs cake-rtt precedence**
   - What we know: Both fields exist. `cake-rtt-scheme` sets a named preset, `cake-rtt` is the explicit time value
   - What's unclear: When `cake-rtt-scheme=internet`, does `cake-rtt` return `"100ms"` or does it remain at whatever was explicitly set?
   - Recommendation: Check both fields. If `cake-rtt-scheme` is `"internet"`, treat as equivalent to `cake-rtt=100ms`. Compare YAML config rtt against the effective value.

3. **Queue types shared across directions**
   - What we know: A router could have one CAKE type used by both download and upload queue tree entries
   - What's unclear: Whether Kevin's router has shared or separate types
   - Recommendation: Always check per-direction. If shared type, the wash check will flag it appropriately (wash=yes is optimal for download but sub-optimal for upload).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `.venv/bin/pytest tests/test_check_cake.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CAKE-01 | Sub-optimal params flagged with severity and rationale | unit | `.venv/bin/pytest tests/test_check_cake.py -x -k "TestCakeParamCheck"` | Will extend existing file |
| CAKE-02 | Queue type params read via GET /rest/queue/type | unit | `.venv/bin/pytest tests/test_check_cake.py -x -k "TestQueueTypeRetrieval"` | Will extend existing file |
| CAKE-03 | Link-independent params compared against defaults | unit | `.venv/bin/pytest tests/test_check_cake.py -x -k "TestLinkIndependent"` | Will extend existing file |
| CAKE-04 | Link-dependent params compared against YAML config | unit | `.venv/bin/pytest tests/test_check_cake.py -x -k "TestLinkDependent"` | Will extend existing file |
| CAKE-05 | Diff output of current vs recommended | unit | `.venv/bin/pytest tests/test_check_cake.py -x -k "TestDiffOutput"` | Will extend existing file |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_check_cake.py -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
None -- existing test infrastructure covers all phase requirements. test_check_cake.py exists with comprehensive test patterns. New test classes will be added following the established class-per-category pattern (TestCakeParamCheck, TestLinkDependent, etc.).

## Sources

### Primary (HIGH confidence)
- [MikroTik CAKE Documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/196345874/CAKE) - CAKE parameters, allowed values, defaults
- [MikroTik Queues Documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/328088/Queues) - Queue type properties table with cake-* fields and types
- [MikroTik REST API Documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/47579162/REST+API) - Confirmed field names match CLI names exactly, all values as strings

### Secondary (MEDIUM confidence)
- [Tangentsoft CAKE Configuration Guide](https://tangentsoft.com/mikrotik/wiki?name=CAKE+Configuration) - Verified CAKE queue type CLI commands and parameter values
- [MikroTik Forum: CAKE comments](https://forum.mikrotik.com/t/some-quick-comments-on-configuring-cake/152505) - Community-verified CAKE parameter behavior
- [GitHub Gist: CAKE queue setup](https://gist.github.com/joeywas/f4a5a76e7330ccd486064f09ae8e5c39) - Working RouterOS CAKE config example

### Tertiary (LOW confidence)
- Exact default representation for unset `cake-overhead` (`"0"` vs `""`) - needs live router verification

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - zero new dependencies, all existing infrastructure
- Architecture: HIGH - extending established patterns from v1.16 with identical structure
- RouterOS field names: HIGH - confirmed via official MikroTik documentation (CAKE page + Queues page)
- Pitfalls: HIGH - based on analysis of existing codebase patterns and REST API behavior
- cake-ack-filter value mapping: HIGH - "filter" and "aggressive" confirmed in multiple sources; "none" confirmed as default in Queues docs

**Research date:** 2026-03-13
**Valid until:** 2026-04-13 (stable domain -- CAKE in RouterOS has not changed significantly since 7.1)
