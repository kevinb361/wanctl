# Phase 105: LinuxCakeBackend Core - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

A complete RouterBackend implementation (`LinuxCakeBackend`) that controls CAKE via local `tc` commands on a Linux bridge VM. Handles bandwidth updates (`tc qdisc change`), statistics collection (`tc -j -s qdisc show`), CAKE initialization (`tc qdisc replace`), parameter validation (readback), and per-tin statistics parsing. No config integration (Phase 107), no steering wiring (Phase 108), no VM setup (Phase 109).

</domain>

<decisions>
## Implementation Decisions

### Interface Design
- **D-01:** LinuxCakeBackend implements the existing RouterBackend ABC in `backends/base.py` without modifying the ABC.
- **D-02:** Mangle rule methods (`enable_rule`, `disable_rule`, `is_rule_enabled`) use no-op stubs: `enable_rule` returns True, `disable_rule` returns True, `is_rule_enabled` returns None. These are never called in the Linux CAKE flow — steering handles mangle rules through its separate RouterOSController (Phase 108).
- **D-03:** No ABC refactoring. Splitting into BandwidthBackend/RuleBackend protocols is deferred unless the ABC becomes a real integration bottleneck.

### Stats Contract
- **D-04:** `get_queue_stats()` returns a superset dict — the existing 5 fields (`packets`, `bytes`, `dropped`, `queued_packets`, `queued_bytes`) PLUS new fields: `tins` (list of per-tin dicts), `memory_used`, `memory_limit`, `ecn_marked`, `capacity_estimate`. Consumers that only read old fields work unchanged.
- **D-05:** Per-tin dicts contain: `sent_bytes`, `sent_packets`, `dropped_packets`, `ecn_marked_packets`, `backlog_bytes`, `peak_delay_us`, `avg_delay_us`, `base_delay_us`, `sparse_flows`, `bulk_flows`, `unresponsive_flows`. Field names match tc JSON output exactly.

### CAKE Initialization
- **D-06:** LinuxCakeBackend owns CAKE initialization via `initialize_cake()` method using `tc qdisc replace`. Called at daemon startup. This is required because systemd-networkd silently drops CAKE params if a qdisc already exists (systemd issue #31226).
- **D-07:** `validate_cake()` reads back params via `tc -j qdisc show` and verifies diffserv mode, overhead, bandwidth, and other parameters match expectations. Called after `initialize_cake()`.
- **D-08:** Runtime bandwidth updates use `set_bandwidth()` → `tc qdisc change dev <iface> root cake bandwidth <rate>kbit`. Only bandwidth changes — other CAKE params persist from initialization.

### Error Handling
- **D-09:** tc command failures in the 50ms control loop: skip the update, log at WARNING level, continue to next cycle. No retry — tc is local (~2ms), failures indicate system issues (module unloaded, permissions) not transient network blips. Next cycle retries naturally.
- **D-10:** `test_connection()` verifies both `tc` binary availability and CAKE qdisc presence on the configured interface.

### Claude's Discretion
- Internal class structure (helper methods, dataclasses for stats)
- subprocess.run timeout values
- Log message formatting and levels
- Test structure and fixture design

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Backend Interface
- `src/wanctl/backends/base.py` — RouterBackend ABC with method signatures (set_bandwidth, get_bandwidth, get_queue_stats, enable_rule, disable_rule, is_rule_enabled, test_connection, from_config)
- `src/wanctl/backends/routeros.py` — RouterOSBackend reference implementation (how existing backend implements ABC)
- `src/wanctl/backends/__init__.py` — get_backend() factory function (currently only supports routeros)

### Stats Parsing Reference
- `src/wanctl/steering/cake_stats.py` — CakeStatsReader with delta calculation pattern (reference for stats contract)
- `src/wanctl/router_command_utils.py` — CommandResult type, extract_queue_stats() helper

### Research
- `.planning/research/STACK.md` — tc command reference, JSON output format, subprocess approach
- `.planning/research/OPENSOURCE-CAKE.md` — tc command patterns from sqm-scripts/cake-autorate/LibreQoS, exact JSON schema
- `.planning/research/FEATURES.md` — LinuxCakeBackend feature mapping

### Test Reference
- `tests/test_backends.py` — Existing backend tests (RouterBackend ABC, RouterOSBackend mocked tests)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `RouterBackend` ABC at `backends/base.py` — implement this interface exactly
- `CommandResult` dataclass at `router_command_utils.py` — use for type-safe error handling from tc commands
- `extract_queue_stats()` at `router_command_utils.py` — reference for stats dict structure
- `CakeStatsReader._calculate_stats_delta()` — delta pattern for cumulative counters

### Established Patterns
- All backends use `from_config()` classmethod for construction
- Stats are returned as plain dicts (not dataclasses) — matches `get_queue_stats()` contract
- Error handling uses `check_command_success()` helper with structured logging
- subprocess usage pattern: `subprocess.run(cmd, capture_output=True, text=True, timeout=N)`

### Integration Points
- `backends/__init__.py:get_backend()` — add `"linux-cake"` branch (Phase 107 scope)
- WANController and SteeringDaemon do NOT use RouterBackend yet — they use legacy wrappers. Integration is Phase 107/108 scope.
- LinuxCakeBackend is self-contained in Phase 105 — no existing code changes needed.

### Key Insight: Backend Layer is Decoupled
The RouterBackend ABC exists but is NOT wired into WANController or SteeringDaemon. They use legacy `RouterOS` and `RouterOSController` wrappers via `FailoverRouterClient`. Phase 105 creates the backend; Phase 107 wires it into the factory; Phase 108 wires steering.

</code_context>

<specifics>
## Specific Ideas

- File location: `src/wanctl/backends/linux_cake.py`
- tc commands execute locally (no SSH/REST) — subprocess.run with shell=False
- tc JSON output confirmed on Debian 12 (iproute2 6.1.0-3) — see OPENSOURCE-CAKE.md for exact schema
- `tc qdisc change` only modifies bandwidth — all other CAKE params persist from `tc qdisc replace`
- Per-tin order in JSON `tins[]` array: index 0=Bulk, 1=BestEffort, 2=Video, 3=Voice (diffserv4)

</specifics>

<deferred>
## Deferred Ideas

- ABC refactoring into BandwidthBackend/RuleBackend protocols — revisit if interface mismatch causes real problems
- pyroute2 netlink backend — deferred requirement PERF-01, only if subprocess tc proves too slow
- "Investigate LXC container network optimizations" todo — out of scope, relates to old container topology

</deferred>

---

*Phase: 105-linuxcakebackend-core*
*Context gathered: 2026-03-24*
