# Requirements: wanctl v1.35

**Defined:** 2026-04-12
**Core Value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.

## v1.35 Requirements

Requirements for Storage Health & Stabilization. Fix the 925 MB metrics DB, deploy v1.34 cleanly, investigate the periodic maintenance error, and soak the full observability stack.

### Storage Health

- [x] **STOR-01**: Metrics DB size is reduced to under the warning threshold through retention tuning or manual cleanup
- [x] **STOR-02**: The periodic maintenance error ("error return without exception set") is diagnosed and fixed so maintenance runs complete cleanly
- [x] **STOR-03**: Storage pressure stays at `ok` or `warning` (not `critical`) through a 24h production soak

### Deployment

- [x] **DEPL-01**: A clean `deploy.sh` run deploys v1.35 with version bump, and canary-check.sh returns exit 0 on all services
- [x] **DEPL-02**: `analyze_baseline.py` is deployable and runnable on production (fix import path issue found during UAT)

### Soak Validation

- [x] **SOAK-01**: The full v1.34 observability stack (alerts, pressure monitoring, summaries, canary) runs cleanly for 24h with zero unexpected restarts and zero unhandled errors

## Out of Scope

- New alerting rules or threshold changes — v1.34 thresholds are validated, let them soak
- Prometheus/Grafana integration — infrastructure not ready
- New features — this is stabilization only

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| STOR-01 | Phase 172 (re-verified Phase 175) | Satisfied |
| STOR-02 | Phase 172 | Satisfied |
| STOR-03 | Phase 174 (verified Phase 175) | Satisfied |
| DEPL-01 | Phase 173 (verified Phase 175) | Satisfied |
| DEPL-02 | Phase 172 | Satisfied |
| SOAK-01 | Phase 174 (verified Phase 175) | Satisfied |

_Traceability closed by Phase 175 on 2026-04-13T19:26:13Z. No milestone requirement is orphaned from verification._

---
*Requirements defined: 2026-04-12*
