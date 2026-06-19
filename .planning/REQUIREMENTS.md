# Requirements: wanctl

**Defined:** 2026-06-19
**Milestone:** v1.54 fping Profiling + Storage Hygiene
**Core Value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.

## v1.54 Requirements

### PROF — fping Profiling

- [x] **PROF-01**: Run fping backend in shadow/read-only mode alongside icmplib on Spectrum, capturing raw RTT samples and cycle p99 timing without touching the control loop or production defaults.
- [x] **PROF-02**: Re-examine Phase 245 AB-03 threshold methodology and rollback_trigger verdict to determine whether fping latency or threshold calibration drove the result.
- [x] **PROF-03**: Produce a comparable p99 RTT distribution for fping vs icmplib over a representative Spectrum production window.
- [x] **PROF-04**: Produce a decision artifact: is fping ready for a future default-flip attempt? If not, what must change?

### FLIP — fping Controlled Canary

- [x] **FLIP-02**: Operator-gated production canary of fping as Spectrum's native wanctl RTT backend under armed rollback and explicit sign-off. Executed and rolled back; do not keep fping/native owner yet.

### GAUGE — Autorate Flat-Gauge Fire-on-Change (SEED-007 Phase A)

- [ ] **GAUGE-01**: Audit per-metric write rates on both WANs via `wanctl-history --ingestion-rate`; identify gauges emitting at ≥2Hz with near-zero value variance.
- [ ] **GAUGE-02**: Apply the steering fire-on-change pattern to each confirmed candidate, one per canary cycle with before/after write-rate measurement.
- [ ] **GAUGE-03**: Unit tests for each changed metric, using the SimpleNamespace-based pattern from `tests/steering/test_steering_metrics_recording.py::TestSteeringEnabledFireOnChange`.

### TIN — CAKE Tin Skip-on-Unchanged (SEED-007 Phase B, gated on consumer audit)

- [ ] **TIN-01**: Audit all consumers of `wanctl_cake_tin_*` across repo, docs, and dashboard queries; classify each as last-value-style vs count-over-window.
- [ ] **TIN-02**: If all consumers are last-value-style, implement per-tin per-direction skip-on-unchanged cache and ship; defer to v1.55 if any consumer needs continuous sampling.
- [ ] **TIN-03**: Before/after write-rate measurement; rollback gate: emission rate regression or downstream consumer query failure.

### SAFE

- [ ] **SAFE-18**: Controller-path zero-diff: fping profiling is shadow-only (no control loop mutation); storage hygiene touches only metric emission. Neither phase mutates `wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, `alert_engine.py`, or fusion logic.

## Future Requirements (post-v1.54)

### fping

- **FLIP-02**: If PROF-04 verdict is positive, operator-gated production flip to fping as default backend under armed rollback and sign-off.
- **FPING-BENCH-01**: Controlled A/B re-run with refined AB-03 thresholds derived from PROF-02/03 profiling evidence.
- **FPING-FRESHNESS-01**: Fix native fping cadence/staleness/fallback behavior before retrying a production canary; Phase 248.1 showed 10s background fping can be treated stale by the 50ms loop, causing repeated TCP fallback and cycle-budget alerts.

### Storage

- **GAUGE-EXT-01**: Extend fire-on-change to additional per-metric candidates discovered post-v1.54 soak.
- **TIN-PHASE-B-DEFER**: CAKE tin skip-on-unchanged deferred from v1.54 if consumer audit (TIN-01) finds a count-over-window consumer that needs fixing first.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Blind production fping default flip | Requires canary evidence and operator keep decision; Phase 248.1 is canary-only, not blind default flip |
| Control-path algorithm changes | SAFE-18 invariant; no controller mutation in this milestone |
| RouterOS / MikroTik mutations | Not in scope for profiling/hygiene work |
| Soak monitor or deploy changes | Unrelated axis; deferred |
| SEED-003/004/005 UL tuning chain | Independent axis; not selected for v1.54 |
| Phase 218 VERIFY-01/02 watch-list | Event-gated on native controller; dormant |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PROF-01 | Phase 247 | Complete |
| PROF-02 | Phase 247 | Complete |
| PROF-03 | Phase 248 | Complete |
| PROF-04 | Phase 248 | Complete |
| FLIP-02 | Phase 248.1 | Complete (rolled back; negative keep verdict) |
| GAUGE-01 | Phase 249 | Pending |
| GAUGE-02 | Phase 249 | Pending |
| GAUGE-03 | Phase 249 | Pending |
| TIN-01 | Phase 250 | Pending |
| TIN-02 | Phase 250 | Pending |
| TIN-03 | Phase 250 | Pending |
| SAFE-18 | Phase 250 (cross-phase, verified at every boundary) | Pending |

**Coverage:**
- v1.54 requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0

---
*Requirements defined: 2026-06-19*
*Last updated: 2026-06-18 — traceability table populated by roadmapper*
