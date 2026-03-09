# Phase 50: Critical Hot-Loop & Transport Fixes - Context

**Gathered:** 2026-03-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix blocking delays in the 50ms autorate hot loop, resolve transport config contradictions between config defaults and factory defaults, add failover re-probe to restore primary transport after fallback, and replace time.sleep with shutdown_event.wait for signal responsiveness. Requirements: LOOP-01, LOOP-02, LOOP-03, LOOP-04, CLEAN-04.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion

User reviewed all gray areas and determined requirements are specific enough for Claude to handle implementation decisions. Key areas at Claude's discretion:

- **Transport default resolution (CLEAN-04):** Config defaults to "ssh" (autorate_continuous.py:451) but factory `get_router_client_with_failover()` defaults primary to "rest" (router_client.py:222). REST is 2x faster and recommended. Resolve the contradiction so `config.router_transport` is authoritative.
- **Re-probe strategy (LOOP-03):** After falling back to SSH, how often to re-probe REST, backoff on repeated failure, whether re-probe runs within cycle budget. Currently `_using_fallback = True` is permanent until close().
- **Retry scope (LOOP-01):** The `@retry_with_backoff(max_attempts=3, initial_delay=1.0, backoff_factor=2.0)` decorator is on `RouterOSSSH.run_cmd` (routeros_ssh.py:188) and `RouterOSREST.run_cmd` (routeros_rest.py:152). These block 1s+2s in the hot loop. Need sub-cycle delays (max 50ms initial, 1 retry) without breaking non-hot-loop callers (calibrate, steering).

</decisions>

<specifics>
## Specific Ideas

No specific requirements -- open to standard approaches. Requirements from architectural review are prescriptive:
- LOOP-01: max 50ms initial delay, single retry
- LOOP-02: `config.router_transport` controls primary transport
- LOOP-03: Periodic re-probe of primary after fallback
- LOOP-04: `shutdown_event.wait()` replaces `time.sleep()` in main loop

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `retry_with_backoff` decorator (retry_utils.py:82): Configurable max_attempts, initial_delay, backoff_factor, max_delay, jitter, on_retry callback -- can be parameterized differently per callsite
- `FailoverRouterClient` (router_client.py:117): Already has `_using_fallback` flag, `_primary_client`/`_fallback_client` slots -- natural place to add re-probe logic
- `get_shutdown_event()` / `signal_utils.py`: shutdown_event already used in steering daemon loop (daemon.py:1524-1525) -- same pattern applies to autorate

### Established Patterns
- Steering daemon already uses `shutdown_event.wait(timeout=sleep_time)` at daemon.py:1525 -- autorate should match
- Config loading via `_load_router_transport_config()` at autorate_continuous.py:448 and steering `_load_router_transport()` at daemon.py:162 -- both default to "ssh"
- Factory `get_router_client_with_failover()` hardcodes `primary="rest"` -- contradicts config defaults

### Integration Points
- `RouterOS.__init__` (autorate_continuous.py:549): `self.ssh = get_router_client_with_failover(config, logger)` -- where transport selection happens for autorate
- `CakeStatsCollector.__init__` (steering/cake_stats.py:53): Same factory call for steering
- `SteeringDaemon._build_clients` (steering/daemon.py:455): Same factory call
- Main loop sleep at autorate_continuous.py:2098-2100: The `time.sleep` to replace

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 50-critical-hot-loop-transport-fixes*
*Context gathered: 2026-03-07*
