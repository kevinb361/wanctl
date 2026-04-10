# Phase 97: Fusion Safety & Observability - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Gate the Phase 96 fusion engine behind a disabled-by-default `fusion.enabled` flag with SIGUSR1 zero-downtime toggle and health endpoint fusion visibility. This is the final phase of v1.19 -- it makes fusion safe to deploy and observable in production. This phase does NOT change fusion computation, weights, or fallback logic -- those are locked from Phase 96.

</domain>

<decisions>
## Implementation Decisions

### Enable/disable gating
- Config key: `fusion.enabled: false` (default) -- matches wan_state.enabled, alerting.enabled, irtt.enabled patterns
- Disabled means **completely skipped** -- no observation mode, no compute-and-log. Pass-through in `_compute_fused_rtt`: early return of `filtered_rtt` when `self._fusion_enabled` is False
- `_fusion_enabled` read once in `__init__` from `config.fusion_config["enabled"]`, updated by SIGUSR1 reload
- No grace period on enable -- fusion is a weighted average, not a threshold-based feature. Staleness gate in `_compute_fused_rtt` already protects against stale IRTT

### SIGUSR1 reload in autorate daemon
- **First SIGUSR1 reload feature in the autorate daemon** -- autorate already registers the handler via `register_signal_handlers()` but never checks `is_reload_requested()` in its main loop
- Add `is_reload_requested()` check at **top of while loop, before `run_cycle()`** -- same position as steering daemon (line 2089)
- Loop iterates over all `wan_controllers` and calls `_reload_fusion_config()` on each WANController
- `_reload_fusion_config()` reloads **both** `enabled` and `icmp_weight` -- operators can tune weights in production without restart
- Follows steering daemon pattern: read fresh YAML, validate, log old->new transitions, update instance variables
- Log format: `[FUSION] Config reload: enabled=false->true, icmp_weight=0.7 (unchanged)`
- **Scope: fusion reload only** -- do not add webhook_url or other reloads to autorate in this phase

### Health endpoint fusion section
- New **always-present `fusion` section** in health response (peer to signal_quality, irtt, reflector_quality)
- **When enabled and active** (IRTT contributing): show enabled, icmp_weight, irtt_weight, active_source="fused", fused_rtt_ms, icmp_rtt_ms, irtt_rtt_ms
- **When enabled but IRTT unavailable** (fallback): show **configured** weights (not effective 1.0/0.0), active_source="icmp_only", fused_rtt_ms=null, irtt_rtt_ms=null
- **When disabled**: minimal `{"enabled": false, "reason": "disabled"}` -- matches irtt unavailable pattern
- **No SQLite persistence** for fusion state -- input signals (ICMP RTT, IRTT RTT) are already persisted, fused_rtt is derivable

### Production rollout
- Deploy v1.19 with `fusion.enabled: false` on both containers
- Health verify: confirm fusion section shows `{"enabled": false, "reason": "disabled"}`
- Enable Spectrum first: edit spectrum.yaml, `kill -USR1 $(pidof wanctl@spectrum)`
- Monitor health endpoint for active_source, fused_rtt values
- If stable, enable ATT container
- No Discord alert on SIGUSR1 toggle -- operator action, INFO logging is sufficient
- Disable path: edit YAML + SIGUSR1 to revert immediately

### Claude's Discretion
- Whether `_reload_fusion_config` reads YAML via existing `_read_yaml()` helper or opens the file directly
- Exact positioning of fusion section in health response dict relative to other sections
- Test structure and fixture design for mocking fusion enabled/disabled states
- How to expose last fused_rtt from WANController to health endpoint (new attribute vs method)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Fusion engine (Phase 96 -- DO NOT MODIFY computation logic)
- `src/wanctl/autorate_continuous.py` lines 2078-2109 -- `_compute_fused_rtt()` method. Phase 97 adds enabled guard at top, does not change computation.
- `src/wanctl/autorate_continuous.py` lines 1518-1521 -- `_fusion_icmp_weight` and `_fusion_enabled` initialization in `__init__`
- `src/wanctl/autorate_continuous.py` lines 905-931 -- `_load_fusion_config()` with warn+default validation. Phase 97 adds `enabled` field here.

### SIGUSR1 pattern (model for autorate implementation)
- `src/wanctl/steering/daemon.py` lines 2089-2097 -- Steering daemon SIGUSR1 check in main loop (template pattern)
- `src/wanctl/steering/daemon.py` lines 1084-1164 -- `_reload_dry_run_config()` and `_reload_wan_state_config()` methods (template for `_reload_fusion_config`)
- `src/wanctl/signal_utils.py` lines 49-166 -- `_reload_event`, `is_reload_requested()`, `reset_reload_state()` (shared infrastructure)

### Autorate main loop (where SIGUSR1 check goes)
- `src/wanctl/autorate_continuous.py` line 3323 -- `register_signal_handlers()` call (already registers SIGUSR1)
- `src/wanctl/autorate_continuous.py` lines 3352-3415 -- Main while loop where SIGUSR1 check needs to be added

### Health endpoint (where fusion section goes)
- `src/wanctl/health_check.py` lines 191-274 -- Existing signal_quality, irtt, reflector_quality sections (pattern template)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `signal_utils.is_reload_requested()` / `reset_reload_state()`: Thread-safe SIGUSR1 detection, already used by steering daemon
- `_load_fusion_config()`: Already validates icmp_weight with warn+default -- Phase 97 adds `enabled` field to same method
- `health_check.py` section builder pattern: always-present sections with availability flags

### Established Patterns
- **SIGUSR1 reload chain**: check -> log -> call `_reload_*_config()` per WANController -> `reset_reload_state()`
- **Old->new transition logging**: `"Config reload: field=old->new"` format with `(unchanged)` suffix
- **Health section disabled pattern**: `{"available": false, "reason": "disabled"}` for irtt; fusion uses `{"enabled": false, "reason": "disabled"}`
- **Read-once init**: Performance-sensitive values (`_fusion_icmp_weight`) loaded in `__init__`, not per-cycle

### Integration Points
- `WANController.__init__()`: Add `_fusion_enabled` from `config.fusion_config["enabled"]`
- `WANController._compute_fused_rtt()`: Add `if not self._fusion_enabled: return filtered_rtt` guard at top
- `WANController._load_fusion_config()`: Add `enabled` field parsing with default False
- `autorate_continuous.py` main while loop: Add `is_reload_requested()` check before `run_cycle()`
- `health_check.py`: Add fusion section reading `_fusion_enabled`, `_fusion_icmp_weight`, and last fused/icmp/irtt RTT values

</code_context>

<specifics>
## Specific Ideas

No specific requirements -- follow existing patterns exactly. The SIGUSR1 pattern from steering daemon and health endpoint patterns from v1.18 are well-established templates.

</specifics>

<deferred>
## Deferred Ideas

- Autorate webhook_url SIGUSR1 reload (parity with steering daemon) -- future phase
- Discord alert on fusion toggle -- not needed for single-operator system

</deferred>

---

*Phase: 97-fusion-safety-observability*
*Context gathered: 2026-03-18*
