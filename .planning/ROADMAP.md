# Roadmap: wanctl v1.33 Detection Threshold Tuning

## Overview

A/B validate the v1.32 CAKE detection thresholds under production RRUL load. The core milestone flow is baseline measurement, parameter sweep, and a 24h confirmation soak. During execution, two follow-on phases were added to capture shared-storage observability work and the planned post-soak burst-control follow-up without losing traceability in the active milestone.

## Phases

- [x] **Phase 162: Baseline Measurement** - 24h idle capture of drop rate and backlog before any tuning (completed 2026-04-10)
- [x] **Phase 163: Parameter Sweep** - A/B test all 5 detection and recovery thresholds under RRUL (completed 2026-04-11)
- [ ] **Phase 164: Confirmation Soak** - Deploy winning parameters and verify 24h production stability
- [x] **Phase 165: Storage Write Contention Observability And DB Topology Decision** - Add shared-DB observability and record an explicit keep-shared-db decision (completed 2026-04-11)
- [ ] **Phase 166: Burst Detection And Multi-Flow Ramp Control For tcp_12down p99 Spikes** - Planned post-soak follow-up for fast burst clamp behavior and operator-visible telemetry

## Phase Details

### Phase 162: Baseline Measurement
**Goal**: Establish ground-truth idle drop rate and backlog so A/B results have a clean reference point
**Depends on**: Nothing (first phase of v1.33)
**Requirements**: VALID-02
**Success Criteria** (what must be TRUE):
  1. Health endpoint reports drop_rate and backlog_bytes at idle for a full 24h window
  2. Baseline values are recorded (mean, p50, p99) and available for comparison during the parameter sweep
  3. No CAKE detection state changes fire during idle (confirming thresholds are not too sensitive at rest)
**Plans**: 1 plan (complete)

### Phase 163: Parameter Sweep
**Goal**: Each detection and recovery threshold is individually A/B tested under RRUL and confirmed or updated
**Depends on**: Phase 162
**Requirements**: THRESH-01, THRESH-02, THRESH-03, RECOV-04, RECOV-05
**Success Criteria** (what must be TRUE):
  1. drop_rate_threshold has been tested at 2+ values under RRUL with latency and throughput compared (THRESH-01)
  2. backlog_threshold_bytes has been tested at 2+ values under RRUL with latency and throughput compared (THRESH-02)
  3. refractory_cycles has been tested at 20, 40, and 60 under RRUL and the winner selected by p99 latency (THRESH-03)
  4. probe_multiplier_factor has been tested at 1.0, 1.5, and 2.0 under RRUL and the winner selected by recovery speed vs overshoot (RECOV-04)
  5. probe_ceiling_pct has been tested at 0.85, 0.9, and 0.95 under RRUL and the winner selected by throughput ceiling vs latency (RECOV-05)
**Plans:** 3/3 plans complete
Plans:
- [x] 163-01-PLAN.md — Pre-sweep setup + drop_rate_threshold A/B test (THRESH-01)
- [x] 163-02-PLAN.md — backlog_threshold_bytes + refractory_cycles A/B tests (THRESH-02, THRESH-03)
- [x] 163-03-PLAN.md — probe_multiplier_factor + probe_ceiling_pct A/B tests (RECOV-04, RECOV-05)

### Phase 164: Confirmation Soak
**Goal**: All parameter changes from the sweep are deployed together and proven stable in production
**Depends on**: Phase 163
**Requirements**: VALID-01
**Success Criteria** (what must be TRUE):
  1. Production config updated with all winning parameter values from Phase 163
  2. wanctl service running for 24h with zero unexpected restarts
  3. Health endpoint shows CAKE detection metrics within expected ranges (no sustained false positives or missed detections)
  4. Latency and throughput under real-world load are equal to or better than pre-tuning baseline
**Plans**: 2 plans
Plans:
- [x] 164-01-PLAN.md — Deploy final config, start 24h soak, periodic spot checks
- [ ] 164-02-PLAN.md — 24h analysis, baseline comparison, autotuner re-enable

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 162. Baseline Measurement | 1/1 | Complete    | 2026-04-10 |
| 163. Parameter Sweep | 3/3 | Complete   | 2026-04-11 |
| 164. Confirmation Soak | 1/2 | In Progress|  |
| 165. Storage Write Contention Observability And DB Topology Decision | 2/2 | Complete | 2026-04-11 |
| 166. Burst Detection And Multi-Flow Ramp Control For tcp_12down p99 Spikes | 0/2 | Planned |  |

### Phase 165: Storage write contention observability and DB topology decision

**Goal**: Measure real write contention on the current shared SQLite topology, expose low-overhead operator visibility, and make any DB-topology follow-on contingent on explicit decision-gate evidence
**Requirements**: PH165-OBS-01, PH165-OBS-02, PH165-OBS-03, PH165-DEC-04
**Depends on:** Phase 164
**Success Criteria** (what must be TRUE):
  1. Shared SQLite write paths record bounded in-memory contention telemetry for duration, success/failure, queue pressure, and maintenance/checkpoint outcomes without changing write semantics (PH165-OBS-01, PH165-OBS-02)
  2. Autorate and steering health/operator surfaces expose storage contention status without adding observability writes back into SQLite or breaking existing payload contracts (PH165-OBS-03)
  3. A tested decision helper/report can evaluate measured data and classify the next step as keep shared DB, reduce write pressure further, or plan a later split-DB phase (PH165-DEC-04)
  4. Any production/topology decision is made only after a clearly marked measurement checkpoint; per-WAN DB migration is not executed by default in this phase
**Plans:** 2/2 plans complete

Plans:
- [x] 165-01-PLAN.md — Instrument shared-DB write contention in writer, deferred queue, steering, and maintenance paths with tests (PH165-OBS-01, PH165-OBS-02)
- [x] 165-02-PLAN.md — Surface storage contention in health/operator outputs, add decision helper tests, and run a manual measurement gate (PH165-OBS-03, PH165-DEC-04)

### Phase 166: Burst detection and multi-flow ramp control for tcp_12down p99 spikes

**Goal**: Reduce tcp_12down multi-flow ramp p99 latency spikes by adding burst-aware detection and a faster, bounded clamp path that reacts before queues are floor-trapped
**Requirements**: BURST-01, BURST-02, BURST-03
**Depends on:** Phase 165
**Success Criteria** (what must be TRUE):
  1. Controller can detect rapid multi-flow RTT/backlog burst signatures and move to an aggressive download clamp path faster than the current gradual YELLOW descent (BURST-01)
  2. Burst mitigation is bounded by sustain/guardrail logic so it does not false-trigger under ordinary RRUL or normal evening jitter (BURST-02)
  3. Health/metrics output exposes burst trigger evidence clearly enough to evaluate tcp_12down and RRUL A/B results without log archaeology (BURST-03)
**Plans:** 2 plans

Plans:
- [ ] 166-01-PLAN.md — Add burst-signal detection and bounded aggressive clamp behavior with unit coverage (BURST-01, BURST-02)
- [ ] 166-02-PLAN.md — Expose burst telemetry, wire config/health surfaces, and validate tcp_12down vs RRUL behavior (BURST-02, BURST-03)
