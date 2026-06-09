# Requirements: wanctl v1.50 cake-autorate Migration Hardening

**Defined:** 2026-06-09
**Core Value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.
**Milestone Goal:** Make the 2026-06-08 cake-autorate migration reproducible, observable, and provably held — close the deploy/test/monitoring gaps left by the hand-rolled ATT path.

## v1.50 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Deploy Path (DEPLOY)

- [ ] **DEPLOY-01**: Operator can deploy all ATT cake-autorate artifacts (config, qdisc-init, state bridge, both services, silicom watchdog variant) via a `deploy.sh --with-att-cake-autorate` path with the same preflight/validation rigor as the existing `--with-spectrum-cake-autorate` path
- [ ] **DEPLOY-02**: Deployed ATT artifact set matches the live hand-deployed state on cake-shaper (verified diff — repo is the source of truth, no drift)

### Artifact Tests (TEST)

- [ ] **TEST-01**: ATT cake-autorate artifacts covered by repo tests at parity with `test_spectrum_cake_autorate_artifacts.py` (units, `Conflicts=wanctl@att.service`, qdisc-init invariants, bridge env wiring, silicom watchdog variant)
- [ ] **TEST-02**: `deploy.sh` ATT file list validated by test so repo artifacts and the deploy list cannot drift silently

### Monitoring (MON)

- [ ] **MON-01**: soak-monitor error-scan covers the live ATT units (`cake-autorate-att.service`, `cake-autorate-att-state-bridge.service`, silicom watchdog variant) instead of the disabled `wanctl@att.service`
- [ ] **MON-02**: soak-monitor handles ATT external-controller mode at parity with Spectrum (mode detection, bridge-fallback health source) — no Spectrum-only hardcoding in mode detection

### Migration-Held Criteria (SOAK)

- [ ] **SOAK-01**: Formal "migration held" criteria defined and evaluated against live evidence for both WANs (bridge health, metrics DB ingestion, no sustained service errors, qdisc within configured envelope)
- [ ] **SOAK-02**: Rollback to native `wanctl@{wan}` verified — exercised on one WAN (operator-approved) or trivially provable via documented, preflighted procedure with evidence captured

### Documentation (DOCS)

- [ ] **DOCS-04**: Active docs (README, DEPLOYMENT, ARCHITECTURE, CONFIGURATION as applicable) describe both deployment modes correctly; stale claims of native-wanctl ownership of Spectrum/ATT swept

### Safety (SAFE)

- [ ] **SAFE-14**: Controller-path zero-diff invariant — zero source diff across `wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, `alert_engine.py`, fusion at every phase boundary and milestone close

## Future Requirements

Deferred. Tracked but not in current roadmap.

### Native-Controller Role (ROLE)

- **ROLE-01**: Decide native Linux autorate controller retirement/retention after both WANs have soaked under cake-autorate (time/event-gated; `WANCTL_CAKE_AUTORATE_FUTURE.md` "What not to delete yet" governs until then)

### Spectrum Path Quality (TAIL)

- **TAIL-01**: Investigate Spectrum loaded-latency tail (cap sweeps proved it is not a local CAKE knob problem; path/CMTS-shaped evidence milestone)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Native-controller retirement decision | Needs both-WAN soak time — event-gated decision, not buildable work; doc says don't delete until soaked |
| Spectrum loaded-latency tail investigation | Different milestone shape (evidence/investigation, v1.46/v1.47 style); mixing would bloat both |
| SEED-006 Silicom bypass tooling + harness | Excluded at scoping 2026-06-09; ATT watchdog unit coverage rides in TEST-01 |
| SEED-007 storage hygiene | No match to hardening goals |
| Generic `$wan` symmetry refactor | Only parameterize as far as the ATT deploy path requires — premature abstraction otherwise |
| Controller threshold/algorithm changes | SAFE-14 — surface is deploy/test/ops/doc only |
| ATT/Spectrum CAKE parameter retuning | Operating points settled by 2026-06-05/06 trials; not reopened here |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DEPLOY-01 | — | Pending |
| DEPLOY-02 | — | Pending |
| TEST-01 | — | Pending |
| TEST-02 | — | Pending |
| MON-01 | — | Pending |
| MON-02 | — | Pending |
| SOAK-01 | — | Pending |
| SOAK-02 | — | Pending |
| DOCS-04 | — | Pending |
| SAFE-14 | — | Pending |

**Coverage:**
- v1.50 requirements: 10 total
- Mapped to phases: 0
- Unmapped: 10 ⚠️ (roadmap pending)

---
*Requirements defined: 2026-06-09*
*Last updated: 2026-06-09 after initial definition*
