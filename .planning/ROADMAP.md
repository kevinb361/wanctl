# Roadmap: wanctl v1.34 Production Observability and Alerting Hardening

## Overview

Turn the production lessons from v1.33 into stable operator visibility. The milestone focuses on making latency regressions, burst anomalies, storage pressure, and post-deploy risk visible early through bounded alerts, summary surfaces, and repeatable canary checks.

## Phases

- [x] **Phase 167: Latency And Burst Regression Alerts** - Add stable alerting rules for sustained latency drift, burst-health churn, and alert cooldown/severity policy
- [x] **Phase 168: Storage And Runtime Pressure Monitoring** - Surface DB/WAL pressure, maintenance failures, memory growth, and cycle-budget degradation with bounded operator signals
- [x] **Phase 169: Operator Summary Surfaces** - Tighten `/health`, `/metrics`, and CLI/operator summaries around the highest-value production risk signals
- [x] **Phase 170: Post-Deploy Canary Checks** - Add a scripted canary path that validates health, storage pressure, and baseline latency signals after deploys
- [ ] **Phase 171: Threshold Policy And Runbooks** - Document warn-vs-act-now thresholds and operator response flow based on the live signals introduced in v1.34

## Phase Details

### Phase 167: Latency and burst regression alerts
**Goal**: Detect the production regressions that mattered in v1.33 without relying on manual flent checks
**Depends on**: Phase 166
**Requirements**: ALRT-01, ALRT-02, ALRT-03
**Success Criteria** (what must be TRUE):
  1. Alert logic can detect sustained latency-regression patterns from existing health/metrics signals (ALRT-01)
  2. Burst-related regression signals are bounded with cooldowns and do not chatter under normal production load (ALRT-02)
  3. Alert thresholds and severities are explicit, documented in code/config, and suitable for 24/7 production operation (ALRT-03)
**Plans**: 2 plans
Plans:
- [x] 167-01-PLAN.md — Define latency/burst alert thresholds and wire bounded alert emission
- [x] 167-02-PLAN.md — Validate alert behavior under healthy and degraded scenarios

### Phase 168: Storage and runtime pressure monitoring
**Goal**: Make DB, WAL, memory, and cycle-budget pressure visible before they degrade service quality
**Depends on**: Phase 167
**Requirements**: OPER-01, OPER-02, OPER-03
**Success Criteria** (what must be TRUE):
  1. Storage pressure signals cover DB/WAL growth, maintenance failures, and relevant contention outcomes (OPER-01)
  2. Runtime pressure signals cover memory growth, cycle-budget degradation, and service-health drift (OPER-02)
  3. The added observability stays bounded and low-overhead rather than creating new high-rate persistence load (OPER-03)
**Plans**: 2 plans
Plans:
- [x] 168-01-PLAN.md — Add storage/runtime pressure summaries and metrics
- [x] 168-02-PLAN.md — Validate boundedness and production usefulness of the new signals

### Phase 169: Operator summary surfaces
**Goal**: Present the most important production risk signals in the places operators already look
**Depends on**: Phase 168
**Requirements**: SURF-01, SURF-02
**Success Criteria** (what must be TRUE):
  1. `/health`, `/metrics`, and relevant operator tooling expose the key risk signals without requiring log archaeology (SURF-01)
  2. The summary payloads are stable enough for operators and future automation to depend on them (SURF-02)
**Plans**: 2 plans
Plans:
- [x] 169-01-PLAN.md — Refine health/metrics summary surfaces around production-risk signals
- [x] 169-02-PLAN.md — Add or update CLI/operator summaries that consume the same signals

### Phase 170: Post-deploy canary checks
**Goal**: Replace ad hoc post-deploy validation with a repeatable scripted pass/fail workflow
**Depends on**: Phase 169
**Requirements**: CANA-01, CANA-02
**Success Criteria** (what must be TRUE):
  1. A scripted canary validates core health, storage pressure, and basic latency signals after deploys (CANA-01)
  2. The canary path exits with an explicit pass/fail contract when production state is unsafe or unclear (CANA-02)
**Plans**: 2 plans
Plans:
- [x] 170-01-PLAN.md — Build scripted canary checks against live operator signals
- [x] 170-02-PLAN.md — Validate the canary contract and deployment workflow integration

### Phase 171: Threshold policy and runbooks
**Goal**: Turn the new signals into clear operational policy instead of tribal knowledge
**Depends on**: Phase 170
**Requirements**: POL-01
**Success Criteria** (what must be TRUE):
  1. Operators have a documented runbook that explains warn-vs-act-now thresholds and what actions to take for each major signal class (POL-01)
**Plans**: 1 plan
Plans:
- [ ] 171-01-PLAN.md — Write and verify the observability threshold policy and runbook updates

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 167. Latency And Burst Regression Alerts | 2/2 | Complete | 2026-04-11 |
| 168. Storage And Runtime Pressure Monitoring | 2/2 | Complete | 2026-04-11 |
| 169. Operator Summary Surfaces | 2/2 | Complete | 2026-04-12 |
| 170. Post-Deploy Canary Checks | 2/2 | Complete | 2026-04-12 |
| 171. Threshold Policy And Runbooks | 0/1 | Planned |  |
