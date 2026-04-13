# Requirements: wanctl v1.36

**Defined:** 2026-04-13
**Core Value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.

## v1.36 Requirements

Requirements for Storage Retention And DB Footprint. Explain current production DB growth, remove legacy storage ambiguity, and reduce retained metrics size without changing controller decisions or operator-facing contracts.

### Storage Investigation

- [ ] **STOR-04**: Active production metrics databases and their dominant storage contributors are identified clearly enough to explain the current 5+ GB per-WAN footprint
- [x] **STOR-05**: The runtime role of legacy `/var/lib/wanctl/metrics.db` is explicitly closed out as either active, ignored, or archived/retired

### Storage Reduction

- [ ] **STOR-06**: Active per-WAN metrics DB footprint is materially reduced from the 2026-04-13 baseline without breaking health, canary, soak-monitor, operator-summary, or history workflows
- [x] **STOR-07**: Retention/downsampling/maintenance settings remain bounded and production-safe after the footprint reduction change

### Verification

- [x] **OPER-04**: Operators have a documented and repeatable way to verify which DB files are active, what storage status means, and whether the footprint reduction actually held in production

## Out of Scope

- Changing congestion thresholds, recovery timing, or control-state semantics
- Replacing SQLite with another storage system
- Broad observability redesign unrelated to the production DB footprint

## Traceability

| Requirement | Planned Phase | Status |
|-------------|---------------|--------|
| STOR-04 | Phase 180 | Pending |
| STOR-05 | Phase 178 | Satisfied |
| STOR-06 | Phase 181 | Pending |
| STOR-07 | Phase 178 | Satisfied |
| OPER-04 | Phase 179 | Satisfied |

---
*Requirements defined: 2026-04-13*
