# Phase 58: State File Extension - Context

**Gathered:** 2026-03-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Autorate persists its computed congestion zone (dl_zone, ul_zone) to the existing state file each cycle, with backward compatibility and no write amplification. This is the foundation for all WAN-aware steering in v1.11 -- every subsequent phase depends on this data being available.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion

All implementation decisions delegated to Claude, informed by research findings:

**Zone field scope:**
- Export both `dl_state` and `ul_state` -- minimal cost, future-proofs for FUTURE-01
- Download uses 4-state (GREEN/YELLOW/SOFT_RED/RED), upload uses 3-state (GREEN/YELLOW/RED)
- Steering Phase 59 will only consume `dl_state` initially; `ul_state` is available but unused

**State file structure:**
- Nest under `congestion` dict: `{"congestion": {"dl_state": "GREEN", "ul_state": "GREEN"}}`
- Consistent with existing nested structure (`download`, `upload`, `ewma`, `last_applied`)
- Steering reads via `state.get("congestion", {}).get("dl_state", None)` for backward compat

**Dirty-tracking exclusion:**
- `congestion` dict excluded from `_is_state_changed()` comparison
- Zone is written to state file whenever a write occurs (triggered by other field changes or force saves)
- Zone changes alone do NOT trigger writes -- prevents 20x amplification at 50ms cycle rate

**Edge case behavior:**
- Startup (before first RTT): write `"GREEN"` -- fail-safe default, no congestion detected yet
- ICMP failure / freeze mode: write last known zone -- zone reflects state before failure
- Shutdown: zone included in force save -- captures final state for crash recovery
- Invalid/missing zone: downstream consumers treat None as "no signal" (skip WAN weight)

</decisions>

<specifics>
## Specific Ideas

No specific requirements -- open to standard approaches. Research findings provide clear guidance on all implementation choices.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `WANControllerState.save()` at `wan_controller_state.py:104-148`: Add `congestion` parameter
- `WANControllerState._is_state_changed()` at `wan_controller_state.py:51-72`: Exclude `congestion` from comparison dict
- `atomic_write_json()` at `state_utils.py:20-66`: No changes needed, handles any dict
- `build_controller_state()` at `wan_controller_state.py:74-102`: Pattern for building state subdicts

### Established Patterns
- State file schema defined at `wan_controller_state.py:26-33` -- extend with `congestion` key
- Dirty tracking compares dicts directly (not hashing) -- exclude new key from comparison
- `timestamp` is always written but never compared for dirty tracking -- same pattern for `congestion`
- `force=True` bypasses dirty check entirely -- zone always included in force saves

### Integration Points
- `WANController.save_state()` at `autorate_continuous.py:1619-1638`: Pass `dl_zone` and `ul_zone` as new `congestion` parameter
- `dl_zone` computed at `autorate_continuous.py:1428-1436` via `adjust_4state()` -- already in scope
- `ul_zone` computed at `autorate_continuous.py:1438-1445` via `adjust_3state()` -- already in scope
- Save call sites: lines 1243, 1394, 1549, 1552, 2188 -- all need `congestion` parameter
- Tests: `test_wan_controller_state.py:151-247` (TestDirtyStateTracking) -- extend with zone exclusion tests

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope.

</deferred>

---

*Phase: 58-state-file-extension*
*Context gathered: 2026-03-09*
