---
created: 2026-04-18T02:11:13.000Z
title: Monitor flapping peak_transition_count on next real DOCSIS event
area: alerting
resolves_phase: 218
files:
  - src/wanctl/wan_controller.py
  - src/wanctl/alert_engine.py
---

## Problem

Commit f26a232 added `peak_transition_count` to the flapping_dl/flapping_ul alert payload. The design thesis: during a real 30-min DOCSIS oscillation event, the peak counter should report a value meaningfully higher than the threshold (30), revealing actual oscillation intensity that was invisible before.

This was only integration-tested with simulated transitions. Real behavior under production DOCSIS MAP-cycle events is untested. The 2026-04-16 22:26-22:55 CDT event produced 8 back-to-back alerts at exactly `transition_count=30` — once the new code is exposed to a similar event, alerts should show `peak_transition_count > 30` if the thesis is correct.

## Solution

After the next Spectrum flapping event (likely peak hours, weeknight):

1. Query the alerts table for `flapping_dl` and `flapping_ul` rows in that event window
2. Inspect `details.peak_transition_count` vs `details.transition_count`
3. Confirm the peak is actually higher than the threshold. If it's always equal, the reset logic may be clearing peak before the alert is fired.
4. If peak is consistently >30, no action — the signal is live and useful.
5. If peak is always 30 (equal to trigger), revisit the code: the peak counter is being tracked correctly, but the reset-after-fire may be happening at the wrong moment, or the peak is being sampled just at the threshold moment.

Observation-only todo. Closes once we see one real event with meaningful peak data.

## Production Findings — 2026-05-26

No longer observation-pending. Production alerts table over the last 30 days shows:

- **Spectrum** `metrics-spectrum.db`: 20+ `flapping_ul` events from 2026-05-21 → 2026-05-25
- **ATT** `metrics-att.db`: 3 `flapping_dl` events (2026-04-27, 2026-04-29, 2026-05-10)

**Every event reports `transition_count=30, peak_transition_count=30`** — the bug-mode hypothesis from this todo's original diagnostic guidance is confirmed: "If peak is always 30 (equal to trigger), revisit the code: the reset-after-fire may be happening at the wrong moment."

## Root Cause

`src/wanctl/wan_controller.py:4307-4323` (DL) and `4338-4354` (UL):

```python
self._dl_peak_transitions = max(self._dl_peak_transitions, len(self._dl_zone_transitions))  # 4307
if len(self._dl_zone_transitions) >= flap_threshold:
    self.alert_engine.fire(..., {"peak_transition_count": self._dl_peak_transitions, ...})  # 4316
    self._dl_zone_transitions.clear()   # 4322  <-- destroys window state
    self._dl_peak_transitions = 0       # 4323  <-- destroys peak state
```

At the moment `len >= threshold`:
- `peak == max(peak, len) == 30` by construction (line 4307 ran immediately before)
- alert fires with `peak == 30`
- deque + peak are wiped → next cycle starts at 0

The peak counter **never gets a chance to climb above threshold** because the deque is cleared the moment threshold is hit. The deque is already windowed by the `flap_window=120s` prune at line 4305 and would self-manage; `alert_engine.fire()` has its own `cooldown_sec` mechanism that handles fire-rate dedup.

## Fix Direction (revised after Codex peer review, 2026-05-26)

**Initial proposal — "just remove the clear" — is incomplete.** Three issues identified by Codex review:

1. **Cooldown terminology was wrong in earlier draft.** The alert dedup mechanism is `cooldown_sec` (per-rule, see `alert_engine.py:50,68,181-184,229`), not `min_hold_sec`. `min_hold_sec` is a separate dwell filter at `wan_controller.py:4288-4292` (1.0s default). Don't reference `min_hold_sec` as the fire-storm guard.

2. **Removing the clear without resetting peak leaves peak monotonic.** `peak = max(peak, len(deque))` grows indefinitely if peak is never reset and the deque keeps cycling. Without a reset boundary, peak would report a value rising over the entire daemon uptime rather than per-window intensity.

3. **Existing tests assert clear-after-fire semantics** (`tests/test_alert_engine.py:1615-1649` — `TestFlappingDequeClear`). Any fix that removes the clear will break those tests and must encode the new semantics there.

### Design Options

**Option A — Track peak via a separate windowed accumulator (recommended).**
- Add a per-direction ring buffer or scalar sampled every cycle: `_dl_peak_in_window`
- Each cycle, update with `len(deque)` BEFORE the fire branch
- Reset only when the deque windowed prune (line 4305 / 4336) drops the deque back to 0 (i.e., 120s of no transitions)
- Keep the deque clear-after-fire to preserve "alert once per oscillation episode" semantics
- Peak now reflects true max-len-over-window even if oscillation pushes len well above threshold between fires
- Test impact: `TestFlappingDequeClear` still passes; add new tests asserting `peak > threshold` when transitions exceed threshold during cooldown

**Option B — Reframe `peak_transition_count` as `transition_count_at_fire`.**
- Acknowledge the metric is misnamed; rename in payload and operator docs
- Zero code change required to detection logic
- Loses the intensity-above-threshold signal that motivated the metric in the first place

**Option A preferred** because the metric exists specifically to reveal oscillation intensity beyond the trigger threshold (per original 2026-04-17 thesis). Option B is the honest fallback if the implementation cost of A turns out higher than expected.

### Risk to Validate

- Confirm `alert_engine.fire()` `cooldown_sec` suppression behaves correctly when called every cycle for a sustained event (no log spam, dashboard counters increment correctly)
- Verify the windowed peak-accumulator decays correctly when oscillation subsides (peak resets when deque drains)
- Update `TestFlappingDequeClear` to cover the new peak-tracking semantics rather than just deque-clear

## Status

Confirmed bug, root cause identified. Scope estimate (revised per Codex round-2 review): Option A is **not** a 4-line change. Implementation requires a new per-direction windowed peak accumulator with proper reset semantics, updates to `TestFlappingDequeClear` (and likely new tests asserting `peak > threshold` during sustained oscillation), and a small payload/docs update. Realistic scope: **small v1.45 phase** with PLAN + EXEC tasks (controller change, test rewrite, verification against production flapping event). Not a quick-task. Option B (rename metric) is a sub-day change but loses the intensity signal.

Not closing this todo yet because the fix itself hasn't shipped — keep open until the corrective change lands and a subsequent production flapping event shows `peak > 30` (Option A) or the payload is renamed and operator docs updated (Option B).
