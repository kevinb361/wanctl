# Requirements: wanctl v1.37

**Defined:** 2026-04-14
**Core Value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.

## v1.37 Requirements

Requirements for Dashboard History Source Clarity. Make the dashboard history consumer reflect the current history contract so operators can distinguish endpoint-local HTTP history from merged CLI history without changing backend control or storage behavior.

### Dashboard Contract Clarity

- [x] **DASH-01**: The dashboard history tab makes it explicit that `/metrics/history` is an endpoint-local HTTP surface, not the authoritative merged cross-WAN history reader
- [x] **DASH-02**: The dashboard history tab surfaces source context from the HTTP payload, including `metadata.source`, in a way operators can understand during normal use
- [x] **DASH-03**: The dashboard gives operators a clear path to the authoritative merged history view when they need cross-WAN proof

### Verification And Safety

- [x] **DASH-04**: Dashboard regressions cover the narrowed history contract, including source labeling, endpoint-local semantics, and failure handling
- [x] **OPER-05**: Operator-facing docs and workflow guidance stay aligned with the dashboard behavior and the existing CLI-vs-HTTP history split

## Out of Scope

- Changing congestion thresholds, recovery timing, or control-state semantics
- Reworking storage retention, compaction, or DB topology
- Reintroducing merged cross-WAN semantics into `/metrics/history`

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DASH-01 | Phase 184 | Complete |
| DASH-02 | Phase 184 | Complete |
| DASH-03 | Phase 184 | Complete |
| DASH-04 | Phase 185 | Complete |
| OPER-05 | Phase 185 | Complete |
