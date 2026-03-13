# Phase 85: Auto-Fix CLI Integration - Context

**Gathered:** 2026-03-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Operator can apply recommended CAKE parameters to a production router via `wanctl-check-cake spectrum.yaml --fix` with safety checks (daemon lock file), confirmation prompt, rollback snapshot, and structured output. Extends existing `wanctl-check-cake` tool with write capability. Requirements: FIX-01 through FIX-07.

Does NOT include benchmarking (Phase 86-87) or new detection logic (Phase 84, complete).

</domain>

<decisions>
## Implementation Decisions

### Snapshot storage
- Save JSON snapshots to `/var/lib/wanctl/snapshots/`
- Auto-prune oldest snapshots when count exceeds threshold (keep last N)
- Naming convention and snapshot path printing: Claude's discretion

### Fix scope
- `--fix` applies ALL sub-optimal parameters at once (all-or-nothing)
- No selective per-param or per-direction flags — single `--fix` applies everything found
- Whether link-dependent params (overhead, rtt) are included in fix scope: Claude's discretion
- Handling of "nothing to fix" (all params already optimal): Claude's discretion

### Confirmation UX
- Before/after diff shown as a **table format**: Parameter | Current | Recommended columns
- Confirmation prompt: "Apply N changes to {queue-type-name}? [y/N]"
- `--yes` bypasses interactive confirmation (for scripting)
- Combined vs per-direction confirmation: Claude's discretion

### Post-apply verification
- After applying changes, **re-read queue type data from router** and verify params actually changed
- Success output: re-run the full audit showing all PASS results (same familiar format, now all green)

### Claude's Discretion
- Partial failure handling: batch PATCH vs individual per-param, stop-on-failure vs continue, rollback mechanism
- Whether to include `--rollback <snapshot-file>` flag or keep manual-only rollback
- Combined vs separate confirmation for download + upload queue types
- Snapshot file naming convention and when to print the path
- "Nothing to fix" exit behavior

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `set_queue_limit()` (`routeros_rest.py:614-647`): Shows exact PATCH pattern — find ID, PATCH to `/queue/tree/{id}`. New `set_queue_type_params()` follows same pattern but targets `/queue/type/{id}`
- `get_queue_types()` (`routeros_rest.py:674-702`): Already fetches queue type data for reading — fix needs the write counterpart
- `check_cake_params()` / `check_link_params()` (`check_cake.py:385-527`): Return CheckResult items with `current → recommended` diffs — fix extracts the param changes from these
- `OPTIMAL_CAKE_DEFAULTS` / `OPTIMAL_WASH` (`check_cake.py:43-57`): Constants defining target values — fix applies these as PATCH payloads
- `lock_utils.py`: Full PID-based lock validation — `read_lock_pid()`, `is_process_alive()`, `validate_lock()` — check if daemon is running without acquiring lock
- `run_audit()` (`check_cake.py:610-720`): Existing orchestrator — fix mode adds a step after audit completes

### Established Patterns
- PATCH pattern: find item ID via GET with name filter, then PATCH to `/{resource}/{id}` with JSON body (`set_queue_limit` precedent)
- CheckResult carries category, field, severity, message, suggestion — fix results use same model
- SimpleNamespace wraps router config for client creation
- `_create_audit_client()` factory for REST/SSH client creation
- Lock file path convention: `/run/wanctl/{wan_name}.lock` (from `config_base.py:331`)

### Integration Points
- `RouterOSREST` class: Add `set_queue_type_params()` method alongside existing `get_queue_types()`
- `check_cake.py main()`: Add `--fix`, `--yes` flags to `create_parser()`
- `run_audit()` or new `run_fix()`: Orchestrate snapshot → confirm → apply → verify flow
- Lock file check: Read `/run/wanctl/*.lock` to detect running daemon (read-only check, don't acquire)

</code_context>

<specifics>
## Specific Ideas

- Requirements mandate `set_queue_type_params()` on RouterOSREST — PATCH to `/rest/queue/type/{id}` (not queue tree)
- Lock file path pattern is `/run/wanctl/{wan_name}.lock` — glob `/run/wanctl/*.lock` to check if ANY daemon is running
- Success output re-runs the same audit pipeline to show verified results, giving operator confidence that changes took effect
- Table diff format provides scannable before/after view before confirmation

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 85-auto-fix-cli-integration*
*Context gathered: 2026-03-13*
