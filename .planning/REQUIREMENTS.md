# Requirements: wanctl

**Defined:** 2026-06-19
**Milestone:** v1.55 Route Ownership / Netwatch Retirement
**Core Value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.

## v1.55 Requirements

### OWN — Route Ownership Decision

- [x] **OWN-01**: Document the route ownership decision: Netwatch remains interim owner until wanctl route ownership is implemented, guarded, tested, canaried, and explicitly accepted.
- [x] **OWN-02**: Define the authoritative route owner contract for steady state: exactly one component may mutate WAN default routes at a time.
- [x] **OWN-03**: Document Netwatch coexistence/retirement policy, including allowed interim state, alert-only option, disable/restore procedure, and incident attribution rules.

### INV — Live Read-Only Inventory

- [x] **INV-01**: Capture a read-only live inventory of RouterOS Netwatch entries, route-mutating scripts, target default routes, route comments/IDs, distances, and current enabled/disabled state.
- [x] **INV-02**: Produce a Snapshot-A rollback anchor for route ownership: the commands/data needed to restore Netwatch route ownership and current default-route state without guessing.
- [x] **INV-03**: Prove no live route mutation occurred during inventory and design phases.

### CFG — Safe Configuration Surface

- [ ] **CFG-01**: Add a config-gated wanctl route-management mode with safe/off default.
- [ ] **CFG-02**: Support dry-run/observe mode before active mutation; dry-run must emit the intended decision/action without changing RouterOS route state.
- [ ] **CFG-03**: Validate route-management config fail-closed for malformed route IDs/comments, missing WAN mappings, impossible thresholds, and unsafe active-mode combinations.

### API — RouterOS Route Boundary

- [ ] **API-01**: Implement route enable/disable/read operations through the existing RouterOS integration boundary; no ad hoc shell/SSH route mutation in the hot path.
- [ ] **API-02**: Route operations are idempotent and comment/ID anchored; repeated enable/disable decisions must not churn RouterOS state or logs.
- [ ] **API-03**: Router API failures fail closed with visible logs/alerts and do not leave wanctl believing a route state changed when it did not.

### GUARD — Ownership Guard

- [ ] **GUARD-01**: Detect route-mutating Netwatch entries/scripts before active wanctl route mutation.
- [ ] **GUARD-02**: Refuse active wanctl route mutation while route-mutating Netwatch entries are enabled unless an explicit migration flag is present and documented.
- [ ] **GUARD-03**: Expose ownership/guard status in logs and health/operator output so the active owner is visible during incidents.

### HEALTH — Failover Decision Logic

- [ ] **HEALTH-01**: Route failover/failback decisions use multi-signal WAN health and consecutive-failure/recovery thresholds; no single-target one-sample replacement for Netwatch.
- [ ] **HEALTH-02**: Hysteresis prevents route flapping during transient RTT/loss/health noise.
- [ ] **HEALTH-03**: Startup reconciliation reads current route state and prior decision state before making any active mutation.

### CB — Circuit Breaker and Rollback

- [ ] **CB-01**: If wanctl loses RouterOS API access, crashes, or restarts, routes must not remain in a surprising disabled state without an alert and rollback path.
- [ ] **CB-02**: A clear rollback procedure disables wanctl route mutation and restores/re-enables Netwatch route ownership.
- [ ] **CB-03**: Tests cover ownership guard, threshold behavior, RouterOS API failure, idempotent route operations, dry-run behavior, and startup reconciliation.

### OBS — Observability and Operator Feedback

- [ ] **OBS-01**: Route disable/enable decisions emit structured logs and alerts containing the evidence that caused the decision.
- [ ] **OBS-02**: Dry-run and active modes both expose enough operator evidence to compare intended decisions against live Netwatch behavior.
- [ ] **OBS-03**: Health/operator summary surfaces route-owner mode, guard status, last intended action, last applied action, and rollback readiness.

### CANARY — Operator-Gated Live Validation

- [ ] **CANARY-01**: Before any live route mutation, run a dry-run observation window proving decisions are sane against current Netwatch/live state.
- [ ] **CANARY-02**: Any active one-WAN canary requires explicit operator approval, Snapshot-A rollback proof, and bounded observation.
- [ ] **CANARY-03**: Netwatch route mutation is disabled/retired only after wanctl route ownership is proven and accepted; otherwise Netwatch remains the route owner.

### SAFE

- [x] **SAFE-19**: No live RouterOS route mutation, Netwatch disablement, controller threshold retuning, CAKE qdisc change, or production default flip occurs outside an explicitly approved canary phase.

## Future Requirements (post-v1.55)

### fping

- **FPING-KEEP-01**: Permanent fping/native keep remains deferred until an operator-gated keep canary passes with the Phase 248.2 freshness, Phase 248.3 parity, and Phase 248.4 startup-readiness fixes in place.
- **FPING-BENCH-01**: Controlled A/B re-run with refined AB-03 thresholds derived from v1.54 profiling evidence.

### Storage

- **TIN-SPARSE-01**: CAKE tin sparse-history redesign/acceptance: either upgrade consumers to sparse last-value-before-window semantics or explicitly reject sparse emission.
- **GAUGE-EXT-01**: Extend fire-on-change to additional per-metric candidates only if fresh stable-window evidence finds candidates.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Immediate live route mutation during planning/design | Route control is production routing; canary requires explicit operator approval and rollback anchor |
| Disabling or retiring Netwatch before wanctl route ownership is proven | Netwatch is the current sane interim route owner |
| Ad hoc RouterOS shell/SSH route mutation in hot path | Must use existing RouterOS integration boundary for inspectability and tests |
| Threshold tuning based solely on this milestone | Route failover thresholds need recorded WAN health evidence and canary proof |
| CAKE shaping/rate/controller behavior changes | Different control surface; keep v1.55 focused on route ownership |
| Permanent fping default flip | Separate operator-gated canary/benchmark follow-up |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| OWN-01 | Phase 251 | Complete |
| OWN-02 | Phase 251 | Complete |
| OWN-03 | Phase 251 | Complete |
| INV-01 | Phase 251 | Complete |
| INV-02 | Phase 251 | Complete |
| INV-03 | Phase 251 | Complete |
| CFG-01 | Phase 252 | Pending |
| CFG-02 | Phase 252 | Pending |
| CFG-03 | Phase 252 | Pending |
| API-01 | Phase 252 | Pending |
| API-02 | Phase 252 | Pending |
| API-03 | Phase 252 | Pending |
| GUARD-01 | Phase 253 | Pending |
| GUARD-02 | Phase 253 | Pending |
| GUARD-03 | Phase 253 | Pending |
| HEALTH-01 | Phase 253 | Pending |
| HEALTH-02 | Phase 253 | Pending |
| HEALTH-03 | Phase 253 | Pending |
| CB-01 | Phase 253 | Pending |
| CB-02 | Phase 254 | Pending |
| CB-03 | Phase 253 | Pending |
| OBS-01 | Phase 253 | Pending |
| OBS-02 | Phase 254 | Pending |
| OBS-03 | Phase 253 | Pending |
| CANARY-01 | Phase 254 | Pending |
| CANARY-02 | Phase 254 | Pending |
| CANARY-03 | Phase 254 | Pending |
| SAFE-19 | Phases 251-254 | Complete |

**Coverage:**
- v1.55 requirements: 28 total
- Mapped to phases: 28
- Unmapped: 0

---
*Requirements defined: 2026-06-19*
*Last updated: 2026-06-19 — Phase 251 route ownership decision and read-only inventory complete*
