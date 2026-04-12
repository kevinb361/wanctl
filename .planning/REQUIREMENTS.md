# Requirements: wanctl v1.34

**Defined:** 2026-04-11
**Core Value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.

## v1.34 Requirements

Requirements for Production Observability and Alerting Hardening. Convert the production lessons from v1.33 into stable operator signals, alerts, and deploy-time validation.

### Latency And Burst Regression Alerts

- [ ] **ALRT-01**: Sustained latency-regression conditions are detectable from existing health/metrics signals without relying on ad hoc flent runs
- [ ] **ALRT-02**: Burst-related regressions and repeated burst-health state changes can trigger bounded operator alerts without chattering under normal load
- [ ] **ALRT-03**: Alert conditions have explicit thresholds, cooldowns, and severity mapping suitable for long-running production use

### Storage And Runtime Pressure Monitoring

- [ ] **OPER-01**: Metrics DB, WAL growth, maintenance failures, and shared-storage pressure are exposed clearly enough to alert before service quality slips
- [ ] **OPER-02**: Memory growth, cycle-budget degradation, and service health drift are exposed through stable operator-visible summaries
- [ ] **OPER-03**: Operator surfaces remain bounded and low-overhead; new observability does not write noisy high-rate telemetry back into SQLite

### Operator Surfaces And Summaries

- [ ] **SURF-01**: `/health`, `/metrics`, and relevant CLI/operator views present the most important production risk signals without log archaeology
- [ ] **SURF-02**: Alert and summary payload shapes stay stable enough for operators and future automation to depend on them

### Deploy Validation And Policy

- [ ] **CANA-01**: A scripted post-deploy canary check validates core health, storage pressure, and basic latency signals after production changes
- [ ] **CANA-02**: The canary path has a clear pass/fail contract and exits non-zero when the production state is unsafe or unclear
- [ ] **POL-01**: Observability thresholds and operator actions are documented in a runbook with clear warn-vs-act-now guidance

## Out of Scope

- Automatic remediation or self-healing deploy rollback — useful, but separate from first-class detection and operator visibility
- New congestion-control algorithms or threshold retuning — v1.34 is about seeing and validating production behavior, not changing core control logic again
- Replacing SQLite or re-architecting storage topology — Phase 165 explicitly kept the shared DB, so v1.34 focuses on monitoring it well

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ALRT-01 | Phase 167 | Pending |
| ALRT-02 | Phase 167 | Pending |
| ALRT-03 | Phase 167 | Pending |
| OPER-01 | Phase 168 | Pending |
| OPER-02 | Phase 168 | Pending |
| OPER-03 | Phase 168 | Pending |
| SURF-01 | Phase 169 | Pending |
| SURF-02 | Phase 169 | Pending |
| CANA-01 | Phase 170 | Pending |
| CANA-02 | Phase 170 | Pending |
| POL-01 | Phase 171 | Pending |

---
*Requirements defined: 2026-04-11*
*Last updated: 2026-04-11 after initial v1.34 definition*
