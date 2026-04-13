# Phase 178 Retention Change Record

Date: 2026-04-13
Phase: 178-retention-tightening-and-legacy-db-cleanup
Plan: 178-02
Requirements: STOR-06, STOR-07

## Scope

This plan tightens the active per-WAN autorate retention profile in `configs/spectrum.yaml`
and `configs/att.yaml` to reduce the live SQLite footprint without changing controller logic,
maintenance cadence, or tuning lookback requirements.

## Baseline Versus Applied Retention

| Setting | Previous shipped value | New shipped value | Change |
| ------- | ---------------------- | ----------------- | ------ |
| `raw_age_seconds` | `86400` (24h) | `3600` (1h) | reduce raw retention by 23h |
| `aggregate_1m_age_seconds` | `86400` (24h) | `86400` (24h) | unchanged |
| `aggregate_5m_age_seconds` | `604800` (7d) | `604800` (7d) | unchanged |
| `maintenance_interval_seconds` | `900` (15m) | `900` (15m) | unchanged |

This profile is applied identically to both shipped per-WAN configs:

- `configs/spectrum.yaml`
- `configs/att.yaml`

## Why This Should Reduce DB Size Materially

Phase 177 showed the 5+ GB per-WAN databases were dominated by live retained content rather
than WAL growth or reclaimable slack. The highest-volume tier is raw data, because it stores
the finest-granularity samples before they are downsampled into 1-minute aggregates.

Reducing `raw_age_seconds` from 24 hours to 1 hour removes roughly 95.8% of the shipped raw
retention window while leaving the aggregate tiers unchanged. That makes raw retention the
smallest single settings change that should still materially reduce the active DB footprint.

## Why This Is Considered Safe

- The tuning safety contract is preserved because `aggregate_1m_age_seconds` remains at
  `86400`, which still matches the shipped `tuning.lookback_hours: 24` requirement in both
  active WAN configs and the existing retention/tuner validation logic.
- The longer operator-facing history remains available through the aggregate tiers:
  24 hours of 1-minute data and 7 days of 5-minute data are unchanged.
- Maintenance cadence is unchanged at `900` seconds, so this plan does not alter background
  cleanup/downsampling frequency or watchdog-facing maintenance bounds.
- The new raw window matches the documented schema default for non-Prometheus-compensated
  deployments, which keeps the shipped production profile inside already-supported retention
  behavior instead of introducing a new storage mode.

## Safety Boundary

This plan intentionally does not change:

- controller thresholds or timing
- downsampling logic
- tuning lookback
- `aggregate_1m_age_seconds`
- `aggregate_5m_age_seconds`
- `maintenance_interval_seconds`

The change is limited to shipped per-WAN raw retention.
