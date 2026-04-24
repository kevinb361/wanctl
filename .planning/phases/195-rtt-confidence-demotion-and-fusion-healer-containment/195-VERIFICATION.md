---
phase: 195
slug: rtt-confidence-demotion-and-fusion-healer-containment
verification_date: 2026-04-24
verifier: Codex (Plan 195-03 Task 3)
status: passed
---

# Phase 195 Verification

## Summary

Phase 195 repo-side verification passed for ARB-02, ARB-03, and SAFE-05. The
build now derives live `rtt_confidence`, uses it for the queue-GREEN RTT-veto
gate, contains fusion bypass behind a categorical six-cycle aligned-distress
streak, and replays the Spectrum 2026-04-23 single-path flip without
`rtt_veto`, `healer_bypass`, or DL classifier use of phantom RTT bloat. Phase
196 owns the production soak validation for VALN-04 and VALN-05.

## Requirement Closure

| Requirement | Evidence | Status |
|-------------|----------|--------|
| ARB-02 | `tests/test_phase_195_replay.py::TestPhase195RttVetoGate` covers queue-GREEN low/high confidence, direction disagreement, RTT-below-YELLOW, queue-distress authority, unknown direction, and fallback. | Satisfied |
| ARB-03 | `tests/test_phase_195_replay.py::TestPhase195HealerBypassStreak` covers single-path flip rejection, exact six-cycle trip, held alignment, reset/release, and confidence drop. | Satisfied |
| SAFE-05 | Full hot-path slice passed; textual guards show no threshold/tunable, UL call-site, cross-domain magnitude-ratio, or untouched-source drift. | Satisfied |

## Success Criteria

### SC-1: rtt_confidence observable in /health and SQLite

Evidence: Plan 195-01 health and metrics tests cover pass-through values
`0.0`, `0.5`, `1.0`, `None`, and gated `wanctl_rtt_confidence` emission with
download labels.

Command:
```bash
.venv/bin/pytest -o addopts='' tests/test_wan_controller.py tests/test_health_check.py -q -k "rtt_confidence or arbitration or signal_arbitration or healer_bypass or phase195"
```

Output:
```text
................................................................         [100%]
64 passed, 306 deselected in 0.59s
```

### SC-2: queue-GREEN + RTT spike + confidence < 0.6 does not escalate

Evidence: `TestPhase195RttVetoGate` asserts low-confidence queue-GREEN RTT
spikes return `green_stable` with primary `queue`, while high-confidence,
same-direction spikes are the only `rtt_veto` path.

### SC-3: single-path ICMP/IRTT flip + queue GREEN does not enter healer_bypass

Evidence: `TestPhase195HealerBypassStreak::test_single_path_icmp_flip_never_trips_healer_bypass`
and `TestPhase195Spectrum20260423Replay::test_single_path_flip_never_trips_healer_or_veto`
hold `_fusion_bypass_active is False` and never emit `healer_bypass` across the
single-path flip window.

### SC-4: Spectrum 2026-04-23 replay avoids phantom RTT bloat

Evidence: `TestPhase195Spectrum20260423Replay` replays 25 cycles:
5 steady, 10 ICMP/UDP disagreement spike cycles, and 10 recovery cycles.
Across cycles 6-15 it asserts `_last_rtt_confidence == 0.0`, no
`ARBITRATION_REASON_RTT_VETO`, no `ARBITRATION_REASON_HEALER_BYPASS`, no
`absolute_disagreement`, and classifier load `baseline_rtt + 0.5ms` rather than
`baseline_rtt + 40ms`.

Replay command:
```bash
.venv/bin/pytest -o addopts='' tests/test_phase_193_replay.py tests/test_phase_194_replay.py tests/test_phase_195_replay.py -q
```

Output:
```text
.......................ssssss.........................                   [100%]
48 passed, 6 skipped in 0.51s
```

## Test Evidence

### Hot-path slice

Command:
```bash
.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py tests/test_phase_193_replay.py tests/test_phase_194_replay.py tests/test_phase_195_replay.py -q
```

Output:
```text
610 passed, 6 skipped in 42.06s
```

### Lint

Command:
```bash
.venv/bin/ruff check src/wanctl/wan_controller.py src/wanctl/health_check.py tests/test_wan_controller.py tests/test_health_check.py tests/test_phase_195_replay.py
```

Output:
```text
All checks passed!
```

### Type

Command:
```bash
.venv/bin/mypy src/wanctl/wan_controller.py src/wanctl/health_check.py
```

Output:
```text
Success: no issues found in 2 source files
```

## No-Touch Guards

### SAFE-05

Command:
```bash
git diff -U0 -- src/wanctl/wan_controller.py | grep -E '^[+-].*(factor_down|step_up|dwell_cycles|deadband_ms|warn_bloat|target_bloat|hard_red|burst_threshold|green_required)' || echo "SAFE-05 CLEAN"
```

Output:
```text
SAFE-05 CLEAN
```

### ARB-04

Command:
```bash
git diff -U0 -- src/wanctl/wan_controller.py | grep -E '^[+-].*self\.upload\.adjust\(' || echo "ARB-04 CLEAN"
```

Output:
```text
ARB-04 CLEAN
```

The source regex guard in
`tests/test_phase_195_replay.py::TestPhase195SourceGuards::test_ul_call_site_signature_unchanged`
also passed.

### No cross-domain magnitude ratio

Command:
```bash
grep -E 'max_delay_delta_us.*/|/ *max_delay_delta_us' src/wanctl/wan_controller.py || echo "MAGNITUDE-RATIO CLEAN"
```

Output:
```text
MAGNITUDE-RATIO CLEAN
```

### No absolute_disagreement literal remaining

Command:
```bash
grep '"absolute_disagreement"' src/wanctl/wan_controller.py
```

Output: no matches. The legacy `absolute_disagreement` bypass reason is absent
from production source.

### queue_controller.py / cake_signal.py / fusion_healer.py untouched

Command:
```bash
git diff -- src/wanctl/queue_controller.py src/wanctl/cake_signal.py src/wanctl/fusion_healer.py
```

Output: no diff.

## Deferred to Phase 196

- VALN-04: serialized 2 x 24h Spectrum soak, with rtt-blend before cake-primary
  and no concurrent Spectrum experiments.
- VALN-05: Spectrum DL `tcp_12down` median under cake-primary must reach at
  least 532 Mbps, 90% of the 591 Mbps CAKE-only-static floor from 2026-04-23.
- ATT regression canary remains gated on v1.39 Phase 191 closure.

## Production Risk Notes

- Plan 195-03 found and fixed a stale-confidence edge where the first
  single-path spike cycle could see the previous cycle's high confidence before
  the selector ran. The fix derives current-cycle confidence before arbitration.
- The `0.6` confidence gate and six-cycle healer streak remain locked constants;
  no YAML tuning knobs, classifier thresholds, dwell cycles, deadbands, EWMA
  parameters, or burst settings changed.
- Fusion bypass vocabulary intentionally changes from `absolute_disagreement`
  to `queue_rtt_aligned_distress` when the ARB-03 gate trips.
