# Phase 84: CAKE Detection & Optimizer Foundation - Context

**Gathered:** 2026-03-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Operator can see exactly which CAKE queue type parameters are sub-optimal, with severity, rationale, and recommended values. Extends existing `wanctl-check-cake` tool with new "CAKE Params" and "Link Params" check categories. Requirements: CAKE-01 through CAKE-05.

Builds on existing v1.16 `wanctl-check-cake` infrastructure (CheckResult/Severity model, format_results, run_audit orchestrator). Does NOT include auto-fix (Phase 85) or benchmarking (Phase 86-87).

</domain>

<decisions>
## Implementation Decisions

### Optimal CAKE defaults (link-independent)

- `flowmode`: triple-isolate (per-host + per-flow isolation for multi-device home network)
- `diffserv`: diffserv4 (4-tier: Bulk / Best Effort / Video / Voice)
- `nat`: yes (NAT-aware host isolation — required behind NAT)
- `ack-filter`: yes (compress TCP ACKs to save upload bandwidth)
- `wash`: **direction-dependent** — yes for upload (CAKE classifies BEFORE washing; ISP ignores your DSCP marks anyway), no for download (preserve your own DSCP marks for LAN/WiFi WMM)
- wash=no on an upload queue → WARNING severity ("sub-optimal: sends DSCP marks to ISP that ignores them; wash is safe because CAKE classifies before stripping")
- wash=yes on a download queue → WARNING severity ("sub-optimal: clears your own DSCP marks before LAN devices see them")

### Direction mapping for queue types

- Follow queue tree → queue type linkage: read queue tree entry's `queue` field to get queue type name, then GET /rest/queue/type for that type's params
- Direction inherited from queue tree entry (existing `_extract_queue_names()` already maps download/upload)
- Output groups checks per-direction: "CAKE Params (download)" and "CAKE Params (upload)"

### cake_optimization YAML config block

- Two link-dependent parameters: `overhead` and `rtt`
- Single value per WAN (not per-direction — encapsulation is symmetric)
- Config format:
  ```yaml
  cake_optimization:
    overhead: 18 # DOCSIS link
    rtt: 100ms # CAKE shaper RTT hint
  ```
- Spectrum: overhead=18 (DOCSIS preset equivalent)
- ATT: overhead TBD (user will verify VDSL2 PTM vs PPPoE)
- RTT: 100ms for both WANs (CAKE default, safe for cable + DSL)
- Accept raw numbers OR named preset equivalents when comparing (research agent must verify actual REST API field format)

### Missing config behavior

- If `cake_optimization:` section is absent → skip link-dependent checks, run link-independent only
- Report as INFO: "No cake_optimization config — add cake_optimization: section to check overhead and rtt"
- Link-independent checks (flowmode, nat, ack-filter, wash, diffserv) always run when router is reachable

### Severity classification

- Link-independent sub-optimal params: all **WARNING** (sub-optimal but network still functions)
- Link-dependent sub-optimal params (overhead, rtt): **ERROR** (wrong overhead actively wastes bandwidth or causes incorrect shaping)
- Matching params: **PASS**
- wash direction mismatch (wash=no on upload, wash=yes on download): **WARNING**

### Diff output format

- Inline format: `current_value → recommended_value` with rationale on next line
- Matching params show value + "(optimal)"
- Uses existing CheckResult model — message field carries the `current → recommended` text, suggestion field carries rationale
- Example:
  ```
  ⚠ CAKE Params  flowmode     dual-src-host → triple-isolate
                              Per-flow isolation prevents single-flow hogging
  ✔ CAKE Params  nat          yes (optimal)
  ✘ Link Params  overhead     44 → 18
                              DOCSIS link should use overhead=18
  ```

### Integration into existing tool

- New categories ("CAKE Params (download)", "CAKE Params (upload)", "Link Params") added to existing run_audit() pipeline
- Runs after queue tree checks (needs queue tree data for direction mapping)
- Same output formatting — category-grouped, same exit code logic (ERROR→1, WARNING→2, PASS→0)
- JSON output includes new categories via existing format_results_json()

### Claude's Discretion

- Exact RouterOS REST API field names for /rest/queue/type (must verify with live router or documentation)
- Internal function decomposition within check_cake.py
- Test fixture design for queue type API responses
- How to handle queue types shared between multiple queue tree entries

</decisions>

<specifics>
## Specific Ideas

- RouterOS REST API: queue type params are on `/rest/queue/type` endpoint (NOT `/rest/queue/tree`)
- New `get_queue_type()` method on RouterOSREST class (separate from existing `get_queue_stats()`)
- The existing `check_queue_tree()` already reads queue tree entries — extend that flow to also extract queue type names from the `queue` field, then pass to new queue type checks
- Known issue from STATE.md: "RouterOS REST JSON field names for `/rest/queue/type` CAKE parameters need live router verification during Phase 84"

</specifics>

<code_context>

## Existing Code Insights

### Reusable Assets

- `CheckResult` / `Severity` (`check_config.py:39-55`): Output data model, already imported by check_cake.py
- `format_results()` / `format_results_json()` (`check_config.py`): Category-grouped formatting with color, quiet mode, JSON
- `_extract_router_config()` (`check_cake.py:41-59`): Router connection dict extraction from YAML
- `_create_audit_client()` (`check_cake.py:490-509`): REST/SSH client factory with SimpleNamespace wrapping
- `run_audit()` (`check_cake.py:397-482`): Env→Connect→Queue Tree→Mangle pipeline — extend with new checks
- `check_queue_tree()` (`check_cake.py:225-329`): Already reads queue tree entries, extracts `queue` field (qdisc type name) — this is the linkage point

### Established Patterns

- Never instantiate Config() in check tools — use SCHEMA class attrs only
- SimpleNamespace wraps router config for RouterOSREST.from_config() compatibility
- CheckResult carries category, field, severity, message, suggestion — message for diff, suggestion for rationale
- Max-limit diff is informational PASS (dynamic value) — same pattern may apply to some queue type params

### Integration Points

- `RouterOSREST` class (`routeros_rest.py:51`): Add `get_queue_type()` method alongside existing `get_queue_stats()`
- `run_audit()` orchestrator: Add step 3.5 (after queue tree, before mangle) for queue type param checks
- `check_queue_tree()`: Extract queue type name from `stats.get("queue")` and pass downstream
- YAML config files (`configs/spectrum.yaml`, `configs/att.yaml`): Will need `cake_optimization:` section added

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

_Phase: 84-cake-detection-optimizer-foundation_
_Context gathered: 2026-03-13_
