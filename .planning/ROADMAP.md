# Roadmap: wanctl v1.33 Detection Threshold Tuning

## Overview

A/B validate the v1.32 CAKE detection thresholds under production RRUL load. Three phases: establish idle baseline measurements, sweep all 5 detection/recovery parameters, then confirm winners with a 24h production soak.

## Phases

- [x] **Phase 162: Baseline Measurement** - 24h idle capture of drop rate and backlog before any tuning (completed 2026-04-10)
- [ ] **Phase 163: Parameter Sweep** - A/B test all 5 detection and recovery thresholds under RRUL
- [ ] **Phase 164: Confirmation Soak** - Deploy winning parameters and verify 24h production stability

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
**Goal**: Each detection and recovery threshold is individually A/B tested under RRUL load and confirmed or updated
**Depends on**: Phase 162
**Requirements**: THRESH-01, THRESH-02, THRESH-03, RECOV-04, RECOV-05
**Success Criteria** (what must be TRUE):
  1. drop_rate_threshold has been tested at 2+ values under RRUL with latency and throughput compared (THRESH-01)
  2. backlog_threshold_bytes has been tested at 2+ values under RRUL with latency and throughput compared (THRESH-02)
  3. refractory_cycles has been tested at 20, 40, and 60 under RRUL and the winner selected by p99 latency (THRESH-03)
  4. probe_multiplier_factor has been tested at 1.0, 1.5, and 2.0 under RRUL and the winner selected by recovery speed vs overshoot (RECOV-04)
  5. probe_ceiling_pct has been tested at 0.85, 0.9, and 0.95 under RRUL and the winner selected by throughput ceiling vs latency (RECOV-05)
**Plans:** 3 plans
Plans:
- [ ] 163-01-PLAN.md — Pre-sweep setup + drop_rate_threshold A/B test (THRESH-01)
- [ ] 163-02-PLAN.md — backlog_threshold_bytes + refractory_cycles A/B tests (THRESH-02, THRESH-03)
- [ ] 163-03-PLAN.md — probe_multiplier_factor + probe_ceiling_pct A/B tests (RECOV-04, RECOV-05)

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
- [ ] 164-01-PLAN.md — Deploy final config, start 24h soak, periodic spot checks
- [ ] 164-02-PLAN.md — 24h analysis, baseline comparison, autotuner re-enable

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 162. Baseline Measurement | 1/1 | Complete    | 2026-04-10 |
| 163. Parameter Sweep | 0/3 | Not started | - |
| 164. Confirmation Soak | 0/2 | Not started | - |
