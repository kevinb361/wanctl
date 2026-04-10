# Phase 83: CAKE Qdisc Audit - Context

**Gathered:** 2026-03-13
**Status:** Ready for planning

<domain>
## Phase Boundary

New CLI tool `wanctl-check-cake` that connects to the live MikroTik router and audits CAKE queue tree configuration, qdisc types, max-limit values, and mangle rules against what the wanctl config expects. Strictly read-only -- never modifies router state. Reports results in the same category-grouped format as `wanctl-check-config`.

</domain>

<decisions>
## Implementation Decisions

### Config input & auto-detection
- Accept any wanctl YAML config file, auto-detect type (autorate vs steering) using the same detection logic as check-config (topology key -> steering, continuous_monitoring key -> autorate)
- Type-adaptive checks: autorate config checks connectivity + queue audit + CAKE type; steering config additionally checks mangle rule existence
- Queue names come solely from config (queues.download/upload for autorate, cake_queues.primary_download/upload for steering) -- no CLI override flags
- `--type` override flag for explicit type selection (same as check-config)

### Output format & flags
- Identical flags to check-config: `--json`, `--no-color`, `-q/--quiet`
- Same exit codes: 0=pass, 1=errors, 2=warnings-only
- Same category-grouped output with checkmark/warning/X symbols per check
- Same `create_parser()` + `main()` CLI entry point pattern
- Reuse Severity enum and CheckResult dataclass from check_config.py

### Diff presentation (CAKE-04)
- Inline per-check results showing expected vs actual: `X FAIL  queue max-limit: expected 940000000, actual 500000000`
- Same CheckResult pattern -- expected/actual values embedded in the message string
- No separate summary table -- consistent with check-config's single-format approach

### Expected values for diff
- Claude's Discretion: determine best approach for ceiling-vs-max-limit comparison, considering that max-limit changes dynamically during congestion

### CAKE type verification (CAKE-03)
- Pass if the queue's `queue` field starts with "cake" (catches cake-down, cake-up, cake-diffserv4, etc.)
- Fail if fq_codel, default, pcq, or any non-CAKE qdisc type

### Severity boundaries
- Router unreachable: ERROR in Connectivity category, skip all remaining checks with "Skipped: router unreachable" note. Exit code 1.
- Missing queue: ERROR (wanctl cannot function without it)
- Wrong qdisc type (not CAKE): ERROR (bufferbloat control model won't work)
- Missing mangle rule (steering only): ERROR (steering cannot function without it)

### Transport & authentication
- Simple single transport -- read transport type from config, create one client (REST or SSH). No failover. If configured transport fails, report the error directly.
- Fail early on unresolved env vars: check ${ROUTER_PASSWORD} resolution before attempting connection. Clear error message, not confusing auth failure.
- Single connectivity check combining reachability + auth: "PASS Router connectivity (REST, 10.10.99.1:443)" or "FAIL Router connectivity: 401 Unauthorized"
- Use config's existing timeout values (timeouts.ssh_command) -- no --timeout CLI flag

### Claude's Discretion
- Internal architecture of check_cake.py (how to structure validators, whether to share code with check_config.py)
- How to instantiate router client without triggering daemon side effects (similar constraint as check-config accessing SCHEMA)
- Router API call structure for queue tree enumeration and mangle rule queries
- How to handle partial failures (e.g., download queue exists but upload doesn't)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `check_config.py`: Severity enum, CheckResult dataclass, format_results(), format_results_json(), create_parser() pattern, color/quiet/json handling -- all reusable or extractable
- `RouterOSREST._handle_queue_tree_print()`: GET /queue/tree with name filter -- returns queue details including `queue` (qdisc type) and `max-limit`
- `RouterOSREST._handle_mangle_rule()`: GET /ip/firewall/mangle -- can query by comment
- `RouterOSREST.test_connection()`: GET /system/resource -- verifies auth+reachability
- `router_client.get_router_client()`: Factory for single-transport client (no failover)
- `detect_config_type()` in check_config.py: Already implements auto-detection logic
- `_resolve_password()` in router_client.py: Env var resolution for ${ROUTER_PASSWORD}

### Established Patterns
- CLI entry points in pyproject.toml console_scripts (wanctl-check-config, wanctl-history, wanctl-dashboard)
- Category validators return `list[CheckResult]` -- new router audit validators follow same signature
- Config SCHEMA access via class attribute (Config.SCHEMA, SteeringConfig.SCHEMA) without instantiation
- validate_identifier() for safe RouterOS identifiers (queue names, interface names)

### Integration Points
- New `wanctl-check-cake` entry point in pyproject.toml console_scripts
- New module: `src/wanctl/check_cake.py`
- Imports from check_config.py (Severity, CheckResult, format_results, format_results_json, detect_config_type)
- Imports from router_client.py (get_router_client, _resolve_password)
- Imports from routeros_rest.py / routeros_ssh.py (run_cmd, test_connection)

</code_context>

<specifics>
## Specific Ideas

- Output should feel identical to wanctl-check-config -- operators learn one pattern for both offline validation and live router audit
- Zero new dependencies -- reuse existing router client, check_config data model, YAML parsing
- Tool is strictly read-only -- GET requests only, never PATCH/POST to router
- Password resolution check catches the most common "why won't it connect" issue before even trying

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 83-cake-qdisc-audit*
*Context gathered: 2026-03-13*
