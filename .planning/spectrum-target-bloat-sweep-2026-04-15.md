# Spectrum Target Bloat Sweep (2026-04-15)

## Goal

Find the best `target_bloat_ms` for Spectrum that preserves good bandwidth under RRUL while keeping latency inflation under control.

## Method

- Host: `cake-shaper`
- Deploy flow: `./scripts/deploy.sh spectrum kevin@10.10.110.223 --with-steering`
- Validation after each change:
  - `.venv/bin/pytest -o addopts='' tests/test_check_config.py -q`
  - `./scripts/canary-check.sh --ssh kevin@10.10.110.223`
- Workloads:
  - `flent rrul -H 104.200.21.31 -l 120`
  - `flent rrul -H 104.200.21.31 -l 120 --test-parameter tcp_streams=12`

## Results

| target_bloat_ms | Standard RRUL ping avg | Standard RRUL down | 12tcp ping avg | 12tcp down | Read |
| --- | ---: | ---: | ---: | ---: | --- |
| 12 | 31.75 ms | 511.81 Mbps | 31.55 ms | 510.02 Mbps | Large improvement over `9`, but still leaves bandwidth on the table |
| 13 | 38.12 ms | 438.72 Mbps | 38.74 ms | 381.52 Mbps | Clearly worse |
| 14 | 29.41 ms | 615.23 Mbps | 33.57 ms | 546.04 Mbps | Close, but weaker than `15` on heavy load |
| 15 | 29.47 ms | 618.81 Mbps | 26.75 ms | 679.79 Mbps | Best overall balance |
| 16 | 38.39 ms | 450.47 Mbps | 30.70 ms | 576.21 Mbps | Regression / inconsistent |
| 17 | 31.10 ms | 674.78 Mbps | 30.07 ms | 536.66 Mbps | Helps standard RRUL, hurts 12tcp balance |
| 18 | 29.61 ms | 705.73 Mbps | 28.02 ms | 633.69 Mbps | More bandwidth, but standard RRUL tail got too ugly |

## Conclusion

Production should stay at `target_bloat_ms: 15` for Spectrum.

Why `15`:

- It materially outperforms `12` without taking on the rough tail behavior seen at `18`.
- It beats `14` and `17` on the heavier `12tcp` case, which has been the more revealing stress test for Spectrum.
- `16` was not a smooth continuation upward; it regressed, which means this surface is not monotonic and does not justify further blind threshold fiddling.

## Follow-Up Hypotheses

If Spectrum still needs improvement, the next pass should not be another `target_bloat_ms` micro-sweep. Better candidates:

1. Inspect backlog suppression and recovery-hold behavior on Spectrum around green re-entry.
2. Add RRUL-focused observability for why some runs regress despite a looser target.
3. Consider recovery/hysteresis tuning before accepting more latency budget.

## Production State

- Final deployed setting: `target_bloat_ms: 15`
- ATT stayed isolated and healthy throughout the sweep
- Canary passed after restoring `15`
