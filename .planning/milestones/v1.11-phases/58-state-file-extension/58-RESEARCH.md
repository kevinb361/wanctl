# Phase 58: State File Extension - Research

**Researched:** 2026-03-09
**Domain:** State persistence, dirty-tracking, backward-compatible schema evolution
**Confidence:** HIGH

## Summary

Phase 58 extends the autorate state file to include congestion zone data (`dl_state`, `ul_state`) under a new `congestion` dict key. The implementation touches exactly two production files (`wan_controller_state.py` and `autorate_continuous.py`) and requires careful handling of dirty-tracking exclusion to prevent write amplification at the 20Hz cycle rate.

The existing state persistence infrastructure is well-designed for this extension. The `WANControllerState` class already separates persistence from business logic, uses atomic writes via `atomic_write_json()`, and implements dirty tracking by comparing dicts (not hashing). The `timestamp` field already demonstrates the pattern of "always written but excluded from dirty comparison" -- the `congestion` dict follows this exact pattern. The steering daemon reads the state file via `safe_json_load_file()` and accesses only `state["ewma"]["baseline_rtt"]`, meaning unknown keys are silently ignored -- backward compatibility is inherent.

**Primary recommendation:** Store zones as instance attributes on `WANController` (initialized to `"GREEN"`), add a `congestion` parameter to `WANControllerState.save()`, and exclude `congestion` from `_is_state_changed()` comparison. This requires ~30 lines of production code changes across 2 files.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
None -- all implementation decisions delegated to Claude's discretion.

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

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| STATE-01 | Autorate persists `congestion.dl_state` (GREEN/YELLOW/SOFT_RED/RED) to state file each cycle | `WANControllerState.save()` extended with `congestion` parameter; zone values come from `QueueController.adjust_4state()` and `adjust()` return values already in scope at save call sites |
| STATE-02 | State file extension is backward-compatible (pre-upgrade steering ignores unknown keys) | Steering daemon reads only `state["ewma"]["baseline_rtt"]` via explicit key access; unknown top-level keys like `congestion` are silently ignored by `dict.get()` |
| STATE-03 | Zone field excluded from dirty-tracking comparison to prevent write amplification | `_is_state_changed()` builds comparison dict from explicit fields; `congestion` omitted from comparison dict same as `timestamp` pattern |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| wanctl.wan_controller_state | existing | State persistence manager | Already handles save/load/dirty-tracking; extend, don't replace |
| wanctl.state_utils | existing | `atomic_write_json()`, `safe_json_load_file()` | No changes needed; handles any dict |

### Supporting
No new libraries or dependencies required. This phase modifies only existing code.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Instance attribute zones | Local variable passing | Instance attrs work at all save call sites (including `apply_rate_changes_if_needed` at line 1243 which lacks zone locals); local vars would require threading zones through method signatures |
| `congestion` param on save() | Storing zone in state_manager directly | Parameter approach preserves separation of concerns; state_manager doesn't know about business logic |
| Excluding from dirty dict | Separate dirty-tracking mechanism | Overkill; same pattern as `timestamp` exclusion already works |

## Architecture Patterns

### Current State File Schema (before)
```json
{
  "download": {"green_streak": 5, "soft_red_streak": 0, "red_streak": 0, "current_rate": 100000000},
  "upload": {"green_streak": 3, "soft_red_streak": 0, "red_streak": 0, "current_rate": 20000000},
  "ewma": {"baseline_rtt": 20.0, "load_rtt": 22.0},
  "last_applied": {"dl_rate": 100000000, "ul_rate": 20000000},
  "timestamp": "2026-03-09T12:00:00.000000"
}
```

### Extended State File Schema (after)
```json
{
  "download": {"green_streak": 5, "soft_red_streak": 0, "red_streak": 0, "current_rate": 100000000},
  "upload": {"green_streak": 3, "soft_red_streak": 0, "red_streak": 0, "current_rate": 20000000},
  "ewma": {"baseline_rtt": 20.0, "load_rtt": 22.0},
  "last_applied": {"dl_rate": 100000000, "ul_rate": 20000000},
  "congestion": {"dl_state": "GREEN", "ul_state": "GREEN"},
  "timestamp": "2026-03-09T12:00:00.000000"
}
```

### Pattern 1: Instance Attribute Zone Tracking
**What:** Store `self._dl_zone` and `self._ul_zone` on `WANController`, initialized to `"GREEN"` in `__init__`, updated each cycle after `adjust_4state()`/`adjust()` calls.
**When to use:** Whenever save_state() needs current zone, regardless of call site.
**Why:** Line 1243 (`apply_rate_changes_if_needed`) and line 1394 (freeze mode) call `save_state()` outside the scope where `dl_zone`/`ul_zone` locals exist. Instance attributes solve this cleanly.
```python
# In WANController.__init__:
self._dl_zone: str = "GREEN"  # Fail-safe default
self._ul_zone: str = "GREEN"  # Fail-safe default

# In run_cycle, after adjust calls (lines 1430-1441):
dl_zone, dl_rate, dl_transition_reason = self.download.adjust_4state(...)
ul_zone, ul_rate, ul_transition_reason = self.upload.adjust(...)
self._dl_zone = dl_zone  # Update instance attribute
self._ul_zone = ul_zone
```

### Pattern 2: Dirty-Tracking Exclusion (timestamp pattern)
**What:** `congestion` dict is written to the state file but NOT included in `_is_state_changed()` comparison.
**When to use:** For metadata/signals that piggyback on writes but should never trigger writes.
**Why:** Zone transitions happen ~20x/second at 50ms cycles during congestion. Without exclusion, every zone change triggers a disk write even when no rates/counters changed. This would increase write frequency from "only when state changes" to "every cycle during congestion."
```python
# _is_state_changed compares ONLY these fields:
current = {
    "download": download,
    "upload": upload,
    "ewma": ewma,
    "last_applied": last_applied,
}
# congestion NOT in comparison dict
# timestamp NOT in comparison dict
return current != self._last_saved_state
```

### Pattern 3: Additive Parameter with Default
**What:** Add `congestion` parameter to `save()` with `None` default.
**When to use:** Backward-compatible API extension.
**Why:** `None` default means existing callers (if any) and test code that doesn't pass `congestion` still works. When `congestion` is provided, it's included in the written state dict.
```python
def save(
    self,
    download: dict[str, Any],
    upload: dict[str, Any],
    ewma: dict[str, float],
    last_applied: dict[str, int | None],
    congestion: dict[str, str] | None = None,  # NEW
    force: bool = False,
) -> bool:
    # ...
    state = {
        "download": download,
        "upload": upload,
        "ewma": ewma,
        "last_applied": last_applied,
        "timestamp": datetime.datetime.now().isoformat(),
    }
    if congestion is not None:
        state["congestion"] = congestion
    # ...
```

### Anti-Patterns to Avoid
- **Including congestion in dirty comparison:** Would cause write amplification; zone changes ~20x/sec during congestion events
- **Passing zone as local variables through save_state():** Fails at 2 of 4 call sites where zones aren't in scope (line 1243 rate-limited path, line 1394 freeze path)
- **Storing zone in WANControllerState directly:** Breaks separation of concerns; state manager is persistence-only, business logic stays in WANController
- **Adding congestion to _last_saved_state:** Would break the exclusion -- the comparison would start detecting zone changes as "state changed"

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic file writes | Custom file writing | `atomic_write_json()` | Already handles temp-rename, fsync, permissions, cleanup |
| JSON serialization | Custom serializer | `json.dump()` via `atomic_write_json()` | String zone values ("GREEN") are natively JSON-serializable |
| Backward compat reads | Version checks / migration | `dict.get("congestion", {})` | Missing keys return empty dict; no schema versioning needed |

**Key insight:** The state file is schemaless JSON. Adding a new top-level key is inherently backward-compatible because all consumers use explicit key access (`state["ewma"]["baseline_rtt"]`), not schema validation.

## Common Pitfalls

### Pitfall 1: Zone Not in Scope at All Save Sites
**What goes wrong:** `save_state()` is called from 4 places; 2 of them (line 1243 rate-limited, line 1394 freeze mode) don't have `dl_zone`/`ul_zone` as local variables.
**Why it happens:** Zones are computed mid-cycle in `run_cycle()` (lines 1430-1441), but `apply_rate_changes_if_needed()` is a separate method, and freeze mode exits before zone computation.
**How to avoid:** Store zones as instance attributes (`self._dl_zone`, `self._ul_zone`), updated each cycle. Initialized to `"GREEN"` in `__init__`.
**Warning signs:** `NameError` or wrong zone values in state file.

### Pitfall 2: Congestion in Dirty Comparison = Write Amplification
**What goes wrong:** If congestion dict is included in `_is_state_changed()`, every zone transition triggers a disk write.
**Why it happens:** During congestion events, zone transitions happen frequently (GREEN->YELLOW->SOFT_RED->RED and back). At 50ms cycles, this means up to 20 writes/second.
**How to avoid:** Exclude `congestion` from the comparison dict in `_is_state_changed()`. Also exclude from `_last_saved_state` tracking.
**Warning signs:** Disk I/O spikes during congestion, measurable via `iostat`.

### Pitfall 3: Forgetting _last_saved_state in load()
**What goes wrong:** `load()` initializes `_last_saved_state` for dirty tracking (lines 94-100). If `congestion` were added to `_last_saved_state`, loaded state would include it, causing comparison mismatches.
**Why it happens:** `load()` copies specific keys into `_last_saved_state` for comparison.
**How to avoid:** Do NOT add `congestion` to `_last_saved_state` in `load()`. The load method already only copies the 4 tracked fields.
**Warning signs:** Immediate rewrite on first cycle after restart.

### Pitfall 4: Missing Zone on First Cycle
**What goes wrong:** Before the first RTT measurement, no zone has been computed. If `save_state()` is called (e.g., by rate limiter or freeze mode), `congestion` would have no value.
**Why it happens:** Zones are only computed after successful RTT measurement in `run_cycle()`.
**How to avoid:** Initialize `self._dl_zone = "GREEN"` and `self._ul_zone = "GREEN"` in `__init__`. GREEN is the correct fail-safe (no congestion detected = assume clear).
**Warning signs:** `None` or missing zone in state file.

### Pitfall 5: Test Mock Signature Breakage
**What goes wrong:** Existing tests mock `save_state()` or call `state_manager.save()` without `congestion` parameter.
**Why it happens:** Adding a required parameter would break all callers.
**How to avoid:** Use `congestion: dict[str, str] | None = None` default. Existing test code that doesn't pass `congestion` continues to work.
**Warning signs:** Test failures in unrelated test files.

### Pitfall 6: Shutdown Save Missing Zone
**What goes wrong:** Cleanup at line 2188 calls `save_state(force=True)` on each WAN controller. If instance attributes are used, zones are already available.
**Why it happens:** Shutdown cleanup iterates `controller.wan_controllers` and calls `save_state(force=True)` directly.
**How to avoid:** Instance attributes ensure zone is always available. No special handling needed for shutdown.
**Warning signs:** State file after shutdown missing `congestion` key.

## Code Examples

### Change 1: WANControllerState.save() -- Add congestion parameter
```python
# wan_controller_state.py, save() method
def save(
    self,
    download: dict[str, Any],
    upload: dict[str, Any],
    ewma: dict[str, float],
    last_applied: dict[str, int | None],
    congestion: dict[str, str] | None = None,
    force: bool = False,
) -> bool:
    if not force and not self._is_state_changed(download, upload, ewma, last_applied):
        self.logger.debug(f"{self.wan_name}: State unchanged, skipping disk write")
        return False

    state = {
        "download": download,
        "upload": upload,
        "ewma": ewma,
        "last_applied": last_applied,
        "timestamp": datetime.datetime.now().isoformat(),
    }
    if congestion is not None:
        state["congestion"] = congestion

    atomic_write_json(self.state_file, state)
    self._last_saved_state = {
        "download": download,
        "upload": upload,
        "ewma": ewma,
        "last_applied": last_applied,
    }
    self.logger.debug(f"{self.wan_name}: Saved state to {self.state_file}")
    return True
```

### Change 2: WANController.__init__ -- Initialize zone attributes
```python
# autorate_continuous.py, WANController.__init__
# After state_manager initialization (~line 947):
self._dl_zone: str = "GREEN"  # Congestion zone for state file export
self._ul_zone: str = "GREEN"  # Congestion zone for state file export
```

### Change 3: WANController.run_cycle() -- Update zone attributes
```python
# autorate_continuous.py, run_cycle(), after adjust calls (~line 1436):
dl_zone, dl_rate, dl_transition_reason = self.download.adjust_4state(...)
ul_zone, ul_rate, ul_transition_reason = self.upload.adjust(...)
self._dl_zone = dl_zone  # Update for state file export
self._ul_zone = ul_zone  # Update for state file export
```

### Change 4: WANController.save_state() -- Pass congestion dict
```python
# autorate_continuous.py, save_state() method
def save_state(self, force: bool = False) -> None:
    self.state_manager.save(
        download=self.state_manager.build_controller_state(
            self.download.green_streak,
            self.download.soft_red_streak,
            self.download.red_streak,
            self.download.current_rate,
        ),
        upload=self.state_manager.build_controller_state(
            self.upload.green_streak,
            self.upload.soft_red_streak,
            self.upload.red_streak,
            self.upload.current_rate,
        ),
        ewma={"baseline_rtt": self.baseline_rtt, "load_rtt": self.load_rtt},
        last_applied={
            "dl_rate": self.last_applied_dl_rate,
            "ul_rate": self.last_applied_ul_rate,
        },
        congestion={"dl_state": self._dl_zone, "ul_state": self._ul_zone},
        force=force,
    )
```

### Change 5: WANControllerState docstring -- Update schema
```python
# wan_controller_state.py, class docstring
"""
State Schema:
    {
        "download": {"green_streak", "soft_red_streak", "red_streak", "current_rate"},
        "upload": {"green_streak", "soft_red_streak", "red_streak", "current_rate"},
        "ewma": {"baseline_rtt", "load_rtt"},
        "last_applied": {"dl_rate", "ul_rate"},
        "congestion": {"dl_state", "ul_state"},
        "timestamp": ISO-8601 string
    }
"""
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No zone export | Zone exported via state file | Phase 58 (this phase) | Enables WAN-aware steering in Phase 59 |

**No deprecations:** This is a purely additive change.

## Open Questions

None. The CONTEXT.md discussion resolved all design questions, and code inspection confirms the approach is straightforward.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | `pyproject.toml` ([tool.pytest.ini_options]) |
| Quick run command | `.venv/bin/pytest tests/test_wan_controller_state.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STATE-01 | congestion.dl_state persisted to state file each cycle | unit | `.venv/bin/pytest tests/test_wan_controller_state.py::TestCongestionZoneExport::test_congestion_written_to_state_file -x` | Wave 0 |
| STATE-01 | congestion.ul_state persisted alongside dl_state | unit | `.venv/bin/pytest tests/test_wan_controller_state.py::TestCongestionZoneExport::test_both_zones_written -x` | Wave 0 |
| STATE-01 | save_state passes congestion dict to state_manager | unit | `.venv/bin/pytest tests/test_wan_controller.py::TestSaveState::test_save_state_includes_congestion -x` | Wave 0 |
| STATE-02 | Steering ignores unknown congestion key (backward compat) | unit | `.venv/bin/pytest tests/test_wan_controller_state.py::TestCongestionZoneExport::test_backward_compat_no_congestion -x` | Wave 0 |
| STATE-02 | Steering load_baseline_rtt works with extended state file | unit | `.venv/bin/pytest tests/test_steering_daemon.py -k "baseline" -x` | Existing (already passes -- steering only reads ewma.baseline_rtt) |
| STATE-03 | congestion change alone does NOT trigger write | unit | `.venv/bin/pytest tests/test_wan_controller_state.py::TestCongestionZoneExport::test_zone_change_alone_no_write -x` | Wave 0 |
| STATE-03 | congestion included when other fields trigger write | unit | `.venv/bin/pytest tests/test_wan_controller_state.py::TestCongestionZoneExport::test_zone_included_on_normal_write -x` | Wave 0 |
| STATE-03 | force save includes congestion | unit | `.venv/bin/pytest tests/test_wan_controller_state.py::TestCongestionZoneExport::test_force_save_includes_congestion -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_wan_controller_state.py tests/test_wan_controller.py -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_wan_controller_state.py::TestCongestionZoneExport` -- new test class covering STATE-01, STATE-02, STATE-03
- [ ] `tests/test_wan_controller.py` -- extend `TestSaveState` with congestion parameter tests
- [ ] No framework install needed -- pytest already configured

## Sources

### Primary (HIGH confidence)
- `/home/kevin/projects/wanctl/src/wanctl/wan_controller_state.py` -- Complete state manager source (164 lines), save/load/dirty-tracking implementation
- `/home/kevin/projects/wanctl/src/wanctl/state_utils.py` -- `atomic_write_json()` implementation (179 lines), no changes needed
- `/home/kevin/projects/wanctl/src/wanctl/autorate_continuous.py` -- Lines 834-1568: WANController class, save_state method, all 4 save call sites, zone computation flow
- `/home/kevin/projects/wanctl/src/wanctl/steering/daemon.py` -- Lines 575-618: `load_baseline_rtt()` reads only `ewma.baseline_rtt`, confirming backward compat
- `/home/kevin/projects/wanctl/tests/test_wan_controller_state.py` -- 13 existing tests, all passing (0.16s)
- `/home/kevin/projects/wanctl/tests/test_wan_controller.py` -- Existing save_state tests with mock patterns

### Secondary (MEDIUM confidence)
None needed -- all findings from direct source code inspection.

### Tertiary (LOW confidence)
None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Direct source code inspection; no external libraries involved
- Architecture: HIGH - Pattern follows existing `timestamp` exclusion exactly; all call sites verified
- Pitfalls: HIGH - All 4 save call sites inspected; scope analysis confirmed zone availability issues at lines 1243 and 1394

**Research date:** 2026-03-09
**Valid until:** Indefinite (internal codebase patterns; no external dependency versioning concerns)
