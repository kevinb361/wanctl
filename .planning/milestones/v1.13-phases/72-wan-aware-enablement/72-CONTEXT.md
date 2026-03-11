# Phase 72: WAN-Aware Enablement - Context

**Gathered:** 2026-03-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Enable WAN-aware steering in production on cake-spectrum with validated graceful degradation. The feature code is complete (v1.11) — this phase activates it, validates degradation paths under real conditions, and documents operational procedures. No new feature code; extends SIGUSR1 hot-reload and adds operational docs.

</domain>

<decisions>
## Implementation Decisions

### Hot-Reload Extension
- Extend SIGUSR1 handler to reload `wan_state.enabled` in addition to `dry_run`
- When `wan_state.enabled` is toggled true via SIGUSR1, re-trigger the 30s grace period (consistent with startup behavior, safe ramp-up)
- Rollback becomes: `sed` toggle + `kill -USR1` — no restart needed, matching Phase 71 dry_run pattern

### Degradation Validation
- Validate stale zone fallback by briefly stopping autorate service (~10s), observing health endpoint shows `stale=true` and WAN weight drops to 0
- Validate autorate-unavailable path as part of the same test sequence
- Validation is a documented runbook (step-by-step commands with expected output), not an automated script

### Rollback Procedure
- Primary rollback: edit `wan_state.enabled: false` in steering.yaml, then `kill -USR1 $(pgrep -f "wanctl.*steering")`
- Instant disable, no restart needed, consistent with dry_run rollback from Phase 71

### Example Config
- Example configs/steering.yaml in repo stays `wan_state.enabled: false` (safe default for new deployments)
- Production enablement is a deliberate operational step, not a default

### Claude's Discretion
- Whether SIGUSR1 reload scope includes weight parameters (red_weight, grace_period_sec, staleness_threshold_sec) or only enabled flag
- Code structure: generalize `_reload_dry_run_config()` to `_reload_config()` vs separate `_reload_wan_state_config()`
- Rollback criteria (health endpoint signals that indicate problems)
- Soak observation approach (health endpoint check vs timed soak)
- Degradation runbook location (docs/WAN_AWARE_OPERATIONS.md vs appending to existing docs)
- Autorate-unavailable test approach (rename state file vs stop + delete)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_reload_dry_run_config()` in daemon.py — direct pattern to extend for wan_state reload
- `_get_effective_wan_zone()` — single gating point (enabled + grace), already handles disabled state
- `_is_wan_grace_period_active()` — uses `self._startup_time`, needs reset mechanism for SIGUSR1 re-trigger
- Health endpoint `wan_awareness` section — already shows enabled, zone, effective_zone, staleness, confidence_contribution
- Phase 71 rollback docs — template for WAN-aware rollback procedure

### Established Patterns
- SIGUSR1 reload: `is_reload_requested()` → handler method → `reset_reload_state()` (signal_utils.py)
- Grace period: `(time.monotonic() - self._startup_time) < self._wan_grace_period_sec`
- Warn+disable for invalid config — wan_state section already does this
- Zone gating: `_get_effective_wan_zone()` returns None when disabled/grace active

### Integration Points
- `daemon.py` SIGUSR1 handler block (~line 1796) — add wan_state reload call
- `_startup_time` attribute — needs reset on wan_state re-enable for grace period re-trigger
- `self._wan_state_enabled` — toggled by reload method
- Health endpoint reads `self.daemon._wan_state_enabled` — auto-reflects reload changes
- Production config: `/etc/wanctl/steering.yaml` on cake-spectrum (SSH edit)

</code_context>

<specifics>
## Specific Ideas

- Follow Phase 71's exact graduation pattern: config edit → SIGUSR1 → health endpoint verify
- Grace period re-trigger on re-enable prevents stale WAN data from immediately influencing decisions after a disable/enable cycle
- Runbook should include expected health endpoint JSON output at each step (enable, verify, degrade test, rollback)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 72-wan-aware-enablement*
*Context gathered: 2026-03-11*
