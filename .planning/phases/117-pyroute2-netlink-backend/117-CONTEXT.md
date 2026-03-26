# Phase 117: pyroute2 Netlink Backend - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace subprocess `tc` calls in LinuxCakeBackend with pyroute2 netlink for CAKE bandwidth changes (`tc qdisc change`), CAKE initialization (`tc qdisc replace`), parameter validation readback, and per-tin statistics collection. The existing `_run_tc()` dispatch pattern (7 call sites) is the primary integration point. Singleton IPRoute connection for daemon lifetime. Subprocess fallback on netlink failure. Factory registration for config-selectable transport.

</domain>

<decisions>
## Implementation Decisions

### Integration Approach
- **D-01:** Claude's discretion on whether to create a new `NetlinkCakeBackend` class alongside `LinuxCakeBackend` (new transport name) or modify `LinuxCakeBackend` internally (same transport name, transparent). Choose whichever best fits the existing codebase patterns, maintainability, and test surface.

### Fallback Strategy
- **D-02:** Claude's discretion on fallback approach. Options: per-call subprocess fallback, permanent fallback after N failures, or skip-and-continue matching D-09. Choose based on production safety (24/7 network control) and code simplicity. Key constraint: a broken pyroute2 must never cause sustained loss of bandwidth control.

### pyroute2 Version
- **D-03:** Claude's discretion on pyroute2 version (0.7.x synchronous vs 0.9.x async rewrite). Must validate CAKE `tc("change")` and stats decoder work correctly. The proof-of-concept validation on the production VM is mandatory before any hot-loop integration regardless of version choice.

### Stats via Netlink
- **D-04:** Claude's discretion on whether to deliver netlink-based stats reading (NLNK-04) in Phase 117 or defer to a follow-up. The existing `get_queue_stats()` dict contract (D-04/D-05 from Phase 105) must be preserved exactly.

### Carried Forward from Phase 105
- **D-05:** Implements RouterBackend ABC without modifying it (Phase 105 D-01).
- **D-06:** Stats contract returns superset dict with per-tin data (Phase 105 D-04/D-05). Field names match tc JSON output exactly.
- **D-07:** tc failures in hot loop: skip update, log WARNING, continue. No retry (Phase 105 D-09). Netlink failures should follow same philosophy.
- **D-08:** `initialize_cake()` uses `tc qdisc replace` (idempotent), runtime uses `tc qdisc change` (lossless). `validate_cake()` reads back params (Phase 105 D-06/D-07/D-08).

### Claude's Discretion
- Integration structure (new class vs internal modification)
- Fallback degradation strategy
- pyroute2 version selection (must validate via PoC)
- Stats via netlink inclusion vs deferral
- IPRoute singleton lifecycle and reconnect implementation
- Internal class structure, helper methods, error mapping
- Test structure and fixture design for netlink mocking

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Backend Interface
- `src/wanctl/backends/base.py` -- RouterBackend ABC with method signatures
- `src/wanctl/backends/linux_cake.py` -- Current subprocess-based implementation (PRIMARY -- this is what gets modified/replaced)
- `src/wanctl/backends/linux_cake_adapter.py` -- Adapter wiring LinuxCakeBackend to WANController
- `src/wanctl/backends/__init__.py` -- Factory function `get_backend()` with transport dispatch

### Stats Contract
- `src/wanctl/steering/cake_stats.py` -- CakeStatsReader with delta calculation pattern
- `src/wanctl/router_command_utils.py` -- CommandResult type, extract_queue_stats() helper

### Phase 105 Context (predecessor)
- `.planning/phases/105-linuxcakebackend-core/105-CONTEXT.md` -- Original LinuxCakeBackend decisions (D-01 through D-10)

### Research
- `.planning/research/STACK.md` -- pyroute2 0.9.5 confirmed CAKE support, sched_cake.py TCA attributes
- `.planning/research/ARCHITECTURE.md` -- Integration architecture, NetlinkCakeBackend as new subclass recommendation
- `.planning/research/PITFALLS.md` -- IPRoute socket leak, CAKE netlink attribute encoding risks
- `.planning/research/SUMMARY.md` -- Consolidated findings, phase ordering rationale

### Test Reference
- `tests/test_backends.py` -- Existing backend tests
- `tests/test_linux_cake_backend.py` -- LinuxCakeBackend-specific tests (if exists)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `LinuxCakeBackend._run_tc()` at `backends/linux_cake.py:77` -- Central dispatch returning `(returncode, stdout, stderr)`. 7 call sites. This is the primary replacement target.
- `OVERHEAD_KEYWORD_EXPANSION` dict at `backends/linux_cake.py:35` -- Maps overhead keywords to tc args. Reusable for netlink attribute mapping.
- `TIN_NAMES` list at `backends/linux_cake.py:30` -- Per-tin naming convention. Must match netlink stats output.
- `RouterBackend` ABC at `backends/base.py` -- Interface contract to implement.

### Established Patterns
- All backends use `from_config()` classmethod for construction
- Stats returned as plain dicts (not dataclasses) matching `get_queue_stats()` contract
- Error handling: `check_command_success()` helper with structured logging
- subprocess pattern: `subprocess.run(cmd, capture_output=True, text=True, timeout=N)`
- Factory dispatch in `backends/__init__.py` uses transport string to select backend class

### Integration Points
- `backends/__init__.py:get_backend()` -- Add new transport branch (if new class approach)
- `LinuxCakeBackend._run_tc()` -- Replace internals (if modification approach)
- `LinuxCakeAdapter` -- May need no changes (wraps backend, doesn't know about subprocess vs netlink)
- Production config: `/etc/wanctl/{spectrum,att}.yaml` -- `transport: "linux-cake"` currently

### Key Insight: _run_tc is the Seam
All 7 callers of `_run_tc()` parse the `(returncode, stdout, stderr)` return tuple. If the modification approach is chosen, replacing `_run_tc()` internals is sufficient. If new class approach is chosen, the new class can override `_run_tc()` or replace it entirely.

</code_context>

<specifics>
## Specific Ideas

- Benchmarked on production VM (Xeon D-1518, kernel 6.12.74+deb13): subprocess `tc qdisc change` is 3.1ms avg, 6.6ms p99 over 50 samples. Target: <0.5ms via netlink.
- CAKE qdisc is on `ens19` (Spectrum DL) and `ens27`/`ens28` (ATT) -- 4 interfaces total across 2 WANs
- pyroute2 `sched_cake.py` confirmed in source tree with 17 TCA_CAKE attributes and per-tin stats decoder
- Proof-of-concept must validate on the cake-shaper VM BEFORE any hot-loop code is written
- The existing `_run_tc()` return contract `(returncode, stdout, stderr)` must be preserved or cleanly migrated

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 117-pyroute2-netlink-backend*
*Context gathered: 2026-03-26*
