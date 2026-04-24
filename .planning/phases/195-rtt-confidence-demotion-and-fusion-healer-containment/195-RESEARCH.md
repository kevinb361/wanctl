---
phase: 195
slug: rtt-confidence-demotion-and-fusion-healer-containment
status: complete
research_type: implementation
created: 2026-04-24
confidence: high
---

# Phase 195 Research - RTT Confidence Demotion and Fusion-Healer Containment

## Executive Summary

Phase 195 should be implemented entirely inside the existing `WANController`
arbitration layer plus focused tests. Do not modify `QueueController`, CAKE
signal processing, EWMA parameters, state-machine thresholds, dwell/deadband
settings, burst detection, or upload classification.

The correct architecture is:

1. Derive a per-cycle `rtt_confidence` scalar in `WANController` from protocol
   agreement and categorical direction agreement.
2. Keep queue-primary DL classification as the default when CAKE queue signal is
   valid.
3. Allow RTT to veto only a queue-GREEN input when confidence is high and queue
   direction agrees with RTT direction.
4. Replace fusion absolute-disagreement bypass with a Phase 195 alignment gate:
   queue distress and high-confidence RTT distress must be sustained in the same
   worsening-or-held direction for 6 cycles.
5. Publish real non-null `rtt_confidence` in `/health` and in SQLite metrics
   only when derived. Preserve `None`/missing behavior when unavailable.

Important correction for planning: `RTT_CONFIDENCE_NULL_SENTINEL = math.nan`
still exists in `src/wanctl/wan_controller.py`, but commit `663d468` removed
the `wanctl_rtt_confidence` NaN metric rows. Phase 195 must add real
`wanctl_rtt_confidence` metric emission; it cannot rely on a placeholder row
already being emitted.

## Standard Stack

- Python stdlib only: `collections.deque`, `dataclasses` if a tiny immutable
  helper type is useful, and existing project types.
- Existing controller seam: `src/wanctl/wan_controller.py`.
- Existing observability renderer: `src/wanctl/health_check.py`.
- Existing replay harness style: `tests/test_phase_193_replay.py` and
  `tests/test_phase_194_replay.py`.
- Existing focused tests: `tests/test_wan_controller.py`,
  `tests/test_health_check.py`, and a new `tests/test_phase_195_replay.py`.
- Existing metrics writer path: `_run_logging_metrics()` in
  `WANController`; continue using numeric SQLite rows and existing
  `_download_labels`.

No new package or external library is needed.

## Architecture Patterns

### Pattern 1: Controller-Owned Arbitration State

Phase 194 established `WANController` as the owner of the arbitration decision:

- `_select_dl_primary_scalar_ms(dl_cake)` returns `(primary, load_for_classifier, reason)`.
- `_run_congestion_assessment()` passes `load_for_classifier` to
  `download.adjust_4state(...)`.
- `_last_arbitration_primary` and `_last_arbitration_reason` are the source for
  metrics and `/health`.

Phase 195 should extend this pattern, not move logic into `QueueController`.
The state machine should remain blind to why a load scalar was chosen.

### Pattern 2: Compute Direction, Then Decide

Use categorical direction over a short history:

- `queue_direction`: derived from consecutive valid `max_delay_delta_us` samples.
- `rtt_direction`: derived from consecutive `load_rtt - baseline_rtt` or
  filtered RTT delta samples.
- Direction vocabulary should be stable and small: `"worsening"`, `"improving"`,
  `"held"`, `"unknown"`.

Do not compare queue microseconds to RTT milliseconds as a magnitude ratio.
Only compare direction categories.

### Pattern 3: Confidence Is a Scalar, But Inputs Stay Inspectable

The roadmap requires `rtt_confidence` in `[0.0, 1.0]` derived from:

- ICMP/UDP agreement from the existing protocol correlation pipeline.
- Queue/RTT direction agreement over the same cycle window.

Recommended composition:

- Protocol confidence:
  - `1.0` when `_irtt_correlation` is inside the existing normal band
    `0.67 <= ratio <= 1.5`.
  - `0.0` when `_irtt_correlation` is outside that band.
  - `0.5` when `_irtt_correlation is None` and no fresh IRTT evidence exists.
- Direction confidence:
  - `1.0` when queue and RTT are both `"worsening"` or both `"held"` under
    sustained distress context.
  - `0.0` when one worsens while the other improves or stays green/unknown.
  - `0.5` when one side is unknown during warmup.
- Final confidence: conservative minimum or product, not optimistic average.

Prefer `min(protocol_confidence, direction_confidence)` for Phase 195. It is
easy to reason about: any untrusted input can cap RTT authority.

### Pattern 4: Veto Is an Escalation Only

RTT confidence should never demote queue distress. Queue-primary distress stays
authoritative. The only intended RTT veto path is:

- CAKE queue signal is valid.
- Queue-derived input would be `GREEN` / `green_stable`.
- RTT delta would be at least `YELLOW` under the existing thresholds.
- `rtt_confidence >= 0.6`.
- Queue direction and RTT direction agree over the chosen window.

When that fires, pass an RTT-derived load scalar to `adjust_4state()` for that
cycle and set `control_decision_reason = "rtt_veto"`.

### Pattern 5: Healer Bypass Gate Is Above Fusion Math

Current `_compute_fused_rtt()` bypasses fusion on absolute ICMP/IRTT offset
greater than `green_threshold`. Phase 195's roadmap explicitly rejects
single-path flips and cross-domain magnitude ratios.

The containment gate should be represented in `WANController` state, not by
editing `FusionHealer.tick()`:

- `FusionHealer` should continue to manage ICMP/IRTT correlation state.
- `WANController` should decide whether fusion bypass is allowed for this cycle
  using queue distress + high-confidence RTT distress + same direction for
  6 cycles.
- Existing health fields `fusion.bypass_active`, `bypass_reason`,
  `bypass_offset_ms`, and `bypass_count` can remain, but `bypass_reason` should
  use a Phase 195 stable reason like `"queue_rtt_aligned_distress"` when the new
  gate trips.

## Don't Hand-Roll

- Do not build a new state machine. Reuse `QueueController.adjust_4state()` and
  only change the scalar fed into it.
- Do not build a learned queue baseline. `CakeSignalSnapshot.max_delay_delta_us`
  is the authoritative queue scalar from Phase 193/194.
- Do not introduce a new smoothing algorithm or EWMA.
- Do not add YAML tuning knobs for `0.6` or 6 cycles in this phase unless the
  plan explicitly treats them as locked constants, because SAFE-05 forbids
  casual threshold/config expansion.
- Do not modify `FusionHealer`'s Pearson correlation internals.
- Do not add labels or strings to SQLite metrics. `wanctl_rtt_confidence` should
  be a numeric value with existing download labels.

## Common Pitfalls

### Pitfall 1: Treating Phase 194 Reason Vocabulary As Final

`tests/test_phase_194_replay.py` currently asserts Phase 194 never emits
`rtt_veto` or `healer_bypass`. Phase 195 must update or supersede that with new
Phase 195 tests. Do not leave Phase 194's negative assertion as a blocker while
adding the new vocabulary.

### Pitfall 2: Assuming `wanctl_rtt_confidence` Already Exists

It does not currently emit. Commit `663d468` removed nullable sentinel rows.
Plan tasks must add:

- A real confidence stash, e.g. `_last_rtt_confidence: float | None`.
- `/health.signal_arbitration.rtt_confidence` sourced from that stash.
- `wanctl_rtt_confidence` metric row only when confidence is not `None`.

### Pitfall 3: Using `load_rtt` Direction After It Was Already Altered

If the classifier input is changed before direction is computed, the RTT
direction can become self-referential. Capture raw RTT delta direction before
calling `_select_dl_primary_scalar_ms()` or before overwriting any arbitration
stash.

### Pitfall 4: Confusing Input Distress With Classifier State

Phase 194 correctly documents that `queue_distress` is input pressure, not
necessarily the resulting state-machine zone. Phase 195 must preserve that
distinction. The 6-cycle healer gate should count input conditions, not final
zone labels after dwell/hysteresis.

### Pitfall 5: Touching Upload

ARB-04 is still active. UL classification, UL state machine, UL metrics block,
and `upload.adjust(...)` call shape should remain byte-identical.

### Pitfall 6: Re-enabling Fusion

Spectrum/ATT fusion workaround state is out of scope. Phase 195 changes the
bypass gate semantics when fusion is in use; it should not change production
fusion enablement.

## Code Examples

### Example: Confidence Stash Shape

```python
self._last_rtt_confidence: float | None = None
self._last_queue_direction: str = "unknown"
self._last_rtt_direction: str = "unknown"
self._arbitration_alignment_window: deque[bool] = deque(maxlen=6)
```

### Example: Direction Helper

```python
def _classify_direction(self, previous: float | None, current: float) -> str:
    if previous is None:
        return "unknown"
    if current > previous:
        return "worsening"
    if current < previous:
        return "improving"
    return "held"
```

Use a dead-simple helper only if it compares already-derived scalar deltas. Do
not add deadband thresholds unless the plan explicitly proves SAFE-05 compliance.

### Example: Confidence Helper

```python
def _derive_rtt_confidence(self, queue_direction: str, rtt_direction: str) -> float:
    ratio = self._irtt_correlation
    if ratio is None:
        protocol_confidence = 0.5
    elif 0.67 <= ratio <= 1.5:
        protocol_confidence = 1.0
    else:
        protocol_confidence = 0.0

    if "unknown" in (queue_direction, rtt_direction):
        direction_confidence = 0.5
    elif queue_direction == rtt_direction:
        direction_confidence = 1.0
    else:
        direction_confidence = 0.0

    return min(protocol_confidence, direction_confidence)
```

The exact protocol bands are already in `_check_protocol_correlation()`; do not
change them.

### Example: Metrics Cutover

```python
if self._last_rtt_confidence is not None:
    metrics_batch.append(
        (
            ts,
            self.wan_name,
            "wanctl_rtt_confidence",
            float(self._last_rtt_confidence),
            self._download_labels,
            "raw",
        )
    )
```

Do not write a NaN sentinel in Phase 195. The success criterion wants non-null
real floats across production windows.

## Recommended Plan Breakdown

### Plan 195-01: Confidence Derivation and Observability

Goal: derive and publish `rtt_confidence` without changing classifier behavior.

Files:

- `src/wanctl/wan_controller.py`
- `src/wanctl/health_check.py`
- `tests/test_wan_controller.py`
- `tests/test_health_check.py`

Must prove:

- Confidence is `None` when no valid queue snapshot exists.
- Confidence is in `[0.0, 1.0]`.
- Protocol disagreement caps confidence below `0.6`.
- Same-direction agreement with normal protocol correlation yields confidence
  at or above `0.6`.
- `/health.signal_arbitration.rtt_confidence` relays the controller value.
- `wanctl_rtt_confidence` is emitted as a real numeric metric when confidence
  exists and is skipped when unavailable.

### Plan 195-02: RTT Veto and Healer Bypass Containment

Goal: wire confidence into DL arbitration and fusion bypass containment.

Files:

- `src/wanctl/wan_controller.py`
- `tests/test_wan_controller.py`
- `tests/test_phase_195_replay.py`

Must prove:

- Queue distress remains authoritative.
- Queue GREEN + RTT spike + confidence `< 0.6` does not escalate.
- Queue GREEN + RTT spike + confidence `>= 0.6` + same direction can emit
  `rtt_veto`.
- Single-path ICMP/IRTT flip with queue GREEN for 6 cycles never emits
  `healer_bypass`.
- Queue distress + RTT distress + high confidence + same direction for 6 cycles
  emits `healer_bypass` / allows fusion bypass.
- UL parity and SAFE-05 no-touch guards stay green.

### Plan 195-03: Replay Verification and Production Evidence Artifact

Goal: update replay harnesses and produce `195-VERIFICATION.md`.

Files:

- `tests/test_phase_195_replay.py`
- `.planning/phases/195-rtt-confidence-demotion-and-fusion-healer-containment/195-VERIFICATION.md`

Must prove:

- The 2026-04-23 Spectrum event replay does not clamp on RTT-only phantom bloat
  unless queue delta actually grows.
- Phase 194 forced-fallback identity remains true when CAKE is unsupported.
- Phase 195 reason vocabulary includes `queue_distress`, `green_stable`,
  `rtt_veto`, and `healer_bypass`.
- Full focused hot-path slice remains green.

## Verification Strategy

Use these commands during planning/execution:

```bash
.venv/bin/pytest -o addopts='' tests/test_wan_controller.py tests/test_health_check.py -q -k "rtt_confidence or arbitration or healer_bypass"
.venv/bin/pytest -o addopts='' tests/test_phase_193_replay.py tests/test_phase_194_replay.py tests/test_phase_195_replay.py -q
.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py tests/test_phase_193_replay.py tests/test_phase_194_replay.py tests/test_phase_195_replay.py -q
.venv/bin/ruff check src/wanctl/wan_controller.py src/wanctl/health_check.py tests/test_wan_controller.py tests/test_health_check.py tests/test_phase_195_replay.py
```

Add textual no-touch guards:

```bash
git diff -- src/wanctl/queue_controller.py src/wanctl/cake_signal.py
git diff -U0 -- src/wanctl/wan_controller.py | grep -E '^[+-].*(factor_down|step_up|dwell_cycles|deadband_ms|warn_bloat|target_bloat|hard_red|burst_threshold|green_required)'
git diff -U0 -- src/wanctl/wan_controller.py | grep -E '^[+-].*self\.upload\.adjust\('
```

Expected results: no diffs or no matches.

## Open Questions for Planning

1. Should `rtt_confidence` be unavailable (`None`) when no fresh IRTT ratio
   exists, or conservative `0.5`? Research recommendation: use `None` when
   either queue or RTT inputs are missing, but `0.5` only inside helper tests for
   unknown direction during warmup if a valid queue snapshot exists.
2. Should the 6-cycle healer gate use `deque[bool]` or an integer streak?
   Recommendation: use an integer streak for simpler health/debug state and
   lower allocation in the 50ms loop.
3. Should `control_decision_reason="healer_bypass"` be set on the classifier
   decision reason or only fusion health? Roadmap says `signal_arbitration`
   should show it, so the arbitration reason should use it when the gate trips.

## Confidence

High. The insertion points are already present from Phases 193 and 194, and the
Phase 195 scope can be implemented with narrow controller-owned helpers and
replay tests. The main risk is accidentally expanding the control algorithm by
adding new tunable thresholds or touching `QueueController`; plans should make
those no-touch constraints explicit.
