---
phase: 158-parameter-re-validation
plan: 02
status: complete
started: 2026-04-09T16:44:00-05:00
completed: 2026-04-09T16:58:00-05:00
commits:
  - "tune(158): warn_bloat_ms 60→75 — A/B validated + confirmation pass"
deviations: []
key-files:
  created:
    - .planning/phases/158-parameter-re-validation/158-02-SUMMARY.md
  modified:
    - configs/spectrum.yaml
---

## Summary

Confirmation pass validated warn_bloat_ms=75 (the only individual winner that changed). Final config deployed via deploy.sh, adaptive tuning re-enabled, 24h soak started.

## Confirmation Pass Results

| Config | Run | ICMP Median | ICMP p99 | DL Sum | UL Sum |
|--------|-----|-------------|----------|--------|--------|
| Winners (warn=75) | 1 | 47.1ms | 94.9ms | 606.9 | 10.4 |
| Winners | 2 | 44.3ms | 97.2ms | 626.2 | 13.1 |
| Winners | 3 | 43.6ms | 78.1ms | 630.5 | 9.8 |
| **Winners avg** | | **45.0ms** | **90.1ms** | **621.2** | **11.1** |
| Original (warn=60) | 1 | 43.6ms | 93.5ms | 607.1 | 8.6 |
| Original | 2 | 46.5ms | 98.4ms | 575.5 | 9.0 |
| Original | 3 | 44.9ms | 102.6ms | 613.1 | 23.3 |
| **Original avg** | | **45.0ms** | **98.2ms** | **598.6** | **13.6** |

**Decision: KEEP WINNERS**
- Median: identical (45.0ms both configs)
- p99: winners 8.2% better (90.1ms vs 98.2ms)
- No interaction effects (only 1 param changed)

## Final Validated Config

| Parameter | Pre-Phase | Post-Phase | Changed? |
|-----------|-----------|------------|----------|
| step_up_mbps | 10 | 10 | No (re-confirmed) |
| warn_bloat_ms | 60 | **75** | **Yes** |
| hard_red_bloat_ms | 100 | 100 | No (re-confirmed) |

## Deployment

- Local configs/spectrum.yaml updated with p158 validation comments
- deploy.sh ran successfully (94 Python files + config)
- Service restarted: active, v1.31.0, GREEN/GREEN
- Adaptive tuning re-enabled: restored 3 persisted params
- Production config matches local config

## 24h Soak

- **Start:** 2026-04-09 16:58 CDT (21:58 UTC)
- **Due:** 2026-04-10 16:58 CDT
- Checks: uptime, alerts, health, circuit breaker, tuning layer

## Self-Check: PASSED
