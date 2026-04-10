---
phase: 161-adaptive-recovery
reviewed: 2026-04-10T03:01:57Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - src/wanctl/cake_signal.py
  - src/wanctl/queue_controller.py
  - src/wanctl/wan_controller.py
  - tests/test_queue_controller.py
findings:
  critical: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
---

# Phase 161: Code Review Report

**Reviewed:** 2026-04-10T03:01:57Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed the Phase 161 adaptive recovery implementation: exponential probe recovery in QueueController, CAKE signal config extensions (probe_multiplier_factor, probe_ceiling_pct), YAML config parsing for recovery section, and 170+ lines of new test coverage for RECOV-01/02/03. The implementation is solid overall -- probe multiplier resets are correctly wired on all non-GREEN transitions (RED, YELLOW, SOFT_RED, deadband, backlog suppression) in both 3-state and 4-state paths. Config parsing has proper type validation and bounds clamping. Two warnings found related to unbounded probe multiplier growth and asymmetric wiring of probe params to QueueControllers.

## Warnings

### WR-01: Probe multiplier grows without upper bound

**File:** `src/wanctl/queue_controller.py:247-249`
**Issue:** `_probe_multiplier` is multiplied by `_probe_multiplier_factor` (default 1.5) on each recovery step with no upper cap. With step_up=10M and factor=1.5, after 10 consecutive recovery windows the step becomes 384M (1.5^9 * 10M). While `enforce_rate_bounds` clamps the resulting rate at ceiling, and `_probe_ceiling_pct` reverts to linear above 90%, a long sustained GREEN at low rates could produce a single step that overshoots from well below ceiling to ceiling in one jump, potentially causing an oscillation if the link cannot sustain near-ceiling rates.
**Fix:** Cap `_probe_multiplier` at a reasonable maximum (e.g., 10x or 20x step_up) to prevent any single step from being larger than a configurable fraction of the rate range:
```python
def _compute_probe_step(self) -> int:
    if self.current_rate >= self.ceiling_bps * self._probe_ceiling_pct:
        return self.step_up_bps
    step = int(self.step_up_bps * self._probe_multiplier)
    self._probe_multiplier *= self._probe_multiplier_factor
    # Cap multiplier to prevent single-step overshoots
    max_multiplier = max(1.0, (self.ceiling_bps - self.floor_green_bps) / max(1, self.step_up_bps))
    self._probe_multiplier = min(self._probe_multiplier, max_multiplier)
    self._probe_step_count += 1
    return step
```

### WR-02: Probe recovery params wired unconditionally to both DL and UL from single config

**File:** `src/wanctl/wan_controller.py:609-613`
**Issue:** `probe_multiplier_factor` and `probe_ceiling_pct` are wired identically to both download and upload QueueControllers from the same CAKE signal config section. Upload (3-state, UL_ceiling=32Mbps) has very different dynamics than download (4-state, DL_ceiling=940Mbps). With step_up=5M for UL and factor=1.5, the 3rd recovery step is already 11.25M (35% of the 32M ceiling), making exponential probing far more aggressive on upload than intended. The `probe_ceiling_pct=0.9` check (above 28.8M for UL) mitigates this somewhat, but the first few recovery steps below 28.8M would be disproportionately large for upload.
**Fix:** Consider per-direction recovery config, or at minimum validate that the combined effect of probe_multiplier_factor with the smaller UL step_up does not produce oversized steps. Adding a per-direction `recovery` sub-section under `cake_signal.recovery.download` and `cake_signal.recovery.upload` would allow tuning independently. For now, a defensive cap in `_compute_probe_step` (WR-01) would also mitigate this.

## Info

### IN-01: Probe step count counter never resets

**File:** `src/wanctl/queue_controller.py:249`
**Issue:** `_probe_step_count` increments on every call to `_compute_probe_step` but is never reset (not even when `_probe_multiplier` resets to 1.0 on congestion). It is only consumed by the health endpoint, so this is a cumulative diagnostic counter, not a bug. However, the naming could suggest it tracks steps in the current recovery sequence rather than total lifetime steps.
**Fix:** No code change needed. Consider renaming to `_probe_step_count_total` or documenting in the health endpoint schema that this is a cumulative counter. Alternatively, reset it alongside `_probe_multiplier` if per-recovery-sequence counting is more useful for observability.

### IN-02: Test file imports at module scope and mid-file

**File:** `tests/test_queue_controller.py:2556`
**Issue:** `CakeSignalSnapshot` and `TinSnapshot` are imported at line 2556 (mid-file, inside a section header comment block) rather than at the top of the file with the other imports. This works but is inconsistent with the import style in the rest of the file (lines 1-18) and may cause linting tools to flag it.
**Fix:** Move the import to the top of the file alongside the other imports:
```python
from wanctl.cake_signal import CakeSignalSnapshot, TinSnapshot
```

---

_Reviewed: 2026-04-10T03:01:57Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
