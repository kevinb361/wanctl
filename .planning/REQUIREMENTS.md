# Requirements: wanctl v1.35

**Defined:** 2026-04-12
**Core Value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.

## v1.35 Requirements

Requirements for Storage Health & Stabilization. Fix the 925 MB metrics DB, deploy v1.34 cleanly, investigate the periodic maintenance error, and soak the full observability stack.

### Storage Health

- [ ] **STOR-01**: Metrics DB size is reduced to under the warning threshold through retention tuning or manual cleanup
- [x] **STOR-02**: The periodic maintenance error ("error return without exception set") is diagnosed and fixed so maintenance runs complete cleanly
- [ ] **STOR-03**: Storage pressure stays at `ok` or `warning` (not `critical`) through a 24h production soak

### Deployment

- [ ] **DEPL-01**: A clean `deploy.sh` run deploys v1.35 with version bump, and canary-check.sh returns exit 0 on all services
- [x] **DEPL-02**: `analyze_baseline.py` is deployable and runnable on production (fix import path issue found during UAT)

### Soak Validation

- [ ] **SOAK-01**: The full v1.34 observability stack (alerts, pressure monitoring, summaries, canary) runs cleanly for 24h with zero unexpected restarts and zero unhandled errors

## Out of Scope

- New alerting rules or threshold changes — v1.34 thresholds are validated, let them soak
- Prometheus/Grafana integration — infrastructure not ready
- New features — this is stabilization only

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| STOR-01 | Phase 175 | Pending |
| STOR-02 | Phase 172 | Satisfied |
| STOR-03 | Phase 175 | Pending |
| DEPL-01 | Phase 175 | Pending |
| DEPL-02 | Phase 172 | Satisfied |
| SOAK-01 | Phase 176 | Pending |

---
*Requirements defined: 2026-04-12*
