# Requirements: wanctl

**Defined:** 2026-06-20
**Milestone:** v1.56 Route Management Surface Deployment
**Core Value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.

## v1.56 Requirements

### DEPLOY — Production Deployment Shape

- [x] **DEPLOY-01**: Prove the actual cake-shaper deployment shape before changing it: git checkout vs flat rsync, service unit paths, active steering code version, config path, and rollback anchor.
- [x] **DEPLOY-02**: Deploy route-management-capable steering code/config to cake-shaper only through an explicit operator-approved bounded deploy/restart plan with a code rollback path.
- [x] **DEPLOY-03**: Preserve external cake-autorate bridge operation during any steering deploy/restart; Spectrum/ATT state bridges and shaping services remain healthy or rollback fires.

### CONFIG — Safe/Off Runtime Configuration

- [x] **CONFIG-01**: Production route-management config remains safe/off or dry-run only; active route mutation is impossible without a separate explicit approval gate.
- [x] **CONFIG-02**: Production config validation proves route IDs/comments, WAN mappings, guard settings, and mode fields are sane before any service restart. Phase 255 validated the safe/off target offline and recorded that live `/etc/wanctl/steering.yaml` requires explicit operator-approved privileged backup/read before Phase 256 restart.
- [x] **CONFIG-03**: One-command rollback restores the previous steering code/config shape without disabling Netwatch or changing RouterOS route state.

### HEALTH — Steering Health Surface Proof

- [x] **HEALTH-01**: The steering health endpoint scraped from the steering host namespace exposes `route_management` owner/mode/guard/last-action fields after deploy.
- [x] **HEALTH-02**: Health checks distinguish cake-autorate state bridge health (`:9101`) from steering route-management health (`:9102` on cake-shaper localhost).
- [x] **HEALTH-03**: Operator summary/log output exposes route owner mode, guard status, intended action, applied action, and rollback readiness in safe/off or dry-run mode.

### OBSERVE — Dry-Run Observation Readiness

- [x] **OBSERVE-01**: Run a bounded read-only/dry-run observation from cake-shaper proving route-management decisions can be computed and observed without RouterOS route mutation.
- [x] **OBSERVE-02**: Compare intended wanctl route decisions against live Netwatch/default-route state and record divergences as evidence, not automatic mutations.
- [x] **OBSERVE-03**: Produce a canary-readiness decision packet that says either `ready-for-approval` or `not-ready`, with blockers and rollback evidence.

### SAFE

- [x] **SAFE-20**: No live RouterOS route mutation, Netwatch disablement, CAKE/qdisc change, controller threshold retuning, or production default route ownership flip occurs during v1.56; any deploy/restart is bounded, approved, observable, and reversible.

## Future Requirements

### Canary

- **CANARY-04**: Active one-WAN route mutation canary after v1.56 readiness proof, requiring fresh explicit operator approval and Snapshot-A rollback proof.
- **RETIRE-01**: Convert Netwatch to alert-only or retire route-mutating Netwatch entries only after an accepted wanctl active canary.

### Native / RTT Backend

- **FPING-KEEP-01**: Permanent fping/native keep remains deferred until an operator-gated keep canary passes with Phase 248.2–248.4 fixes in place.
- **TIN-SPARSE-01**: CAKE tin sparse-history redesign/acceptance remains separate from route-management deployment.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Active WAN route mutation | v1.56 proves deployment/health/dry-run readiness only; active canary is a future explicit gate. |
| Disabling or retiring Netwatch | Netwatch remains interim owner until wanctl active canary is accepted. |
| RouterOS route/default-distance mutation | The milestone must preserve current route owner and prove no mutation. |
| CAKE shaping/rate/qdisc changes | Separate control surface; v1.56 targets steering route-management deployment only. |
| Permanent fping default flip | Separate RTT-backend canary/benchmark work. |
| Generic deploy refactor | Only change deploy mechanics if required to make the safe/off surface observable and reversible. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DEPLOY-01 | Phase 255 | Complete |
| DEPLOY-02 | Phase 256 | Complete |
| DEPLOY-03 | Phase 256 | Complete |
| CONFIG-01 | Phase 255 | Complete |
| CONFIG-02 | Phase 255 | Complete |
| CONFIG-03 | Phase 256 | Complete |
| HEALTH-01 | Phase 256 | Complete |
| HEALTH-02 | Phase 256 | Complete |
| HEALTH-03 | Phase 256 | Complete |
| OBSERVE-01 | Phase 257 | Complete |
| OBSERVE-02 | Phase 257 | Complete |
| OBSERVE-03 | Phase 257 | Complete |
| SAFE-20 | Phases 255-257 | Complete |

**Coverage:**
- v1.56 requirements: 13 total
- Mapped to phases: 13
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-20*
*Last updated: 2026-06-20 after v1.56 milestone definition*
