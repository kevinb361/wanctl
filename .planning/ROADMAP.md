# Roadmap: wanctl

## Overview

wanctl is a production CAKE bandwidth controller running on MikroTik RouterOS with dual-WAN steering. The project has achieved 40x performance improvement (2s to 50ms cycle time) and now includes WAN-aware steering that fuses autorate congestion state into failover decisions. Both confidence-based steering and WAN-aware steering are live in production. A TUI dashboard provides real-time operational visibility. Proactive alerting notifies operators of congestion, steering, connectivity, and anomaly events via Discord. Operator-facing CLI tools validate configs offline and audit router queue state.

## Domain Expertise

None

## Milestones

### Active

**v1.17 CAKE Optimization & Benchmarking** (Phases 84-87)

Goal: Automated CAKE queue type parameter optimization via `--fix` flag and bufferbloat benchmarking with A-F grading and before/after comparison.

- [x] **Phase 84: CAKE Detection & Optimizer Foundation** - Detect sub-optimal CAKE queue type parameters via REST API with diff output and link-aware config
- [x] **Phase 85: Auto-Fix CLI Integration** - Apply recommended CAKE parameters to router via `--fix` flag with safety checks and rollback snapshot (completed 2026-03-13)
- [x] **Phase 86: Bufferbloat Benchmarking** - Run RRUL bufferbloat tests via `wanctl-benchmark` wrapping flent with A-F grading (completed 2026-03-13)
- [ ] **Phase 87: Benchmark Storage & Comparison** - Store benchmark results in SQLite and compare before/after optimization

### Completed

- [v1.16 Validation & Operational Confidence](milestones/v1.16-ROADMAP.md) (Phases 81-83) - SHIPPED 2026-03-13
- [v1.15 Alerting & Notifications](milestones/v1.15-ROADMAP.md) (Phases 76-80) - SHIPPED 2026-03-12
- [v1.14 Operational Visibility](milestones/v1.14-ROADMAP.md) (Phases 73-75) - SHIPPED 2026-03-11
- [v1.13 Legacy Cleanup & Feature Graduation](milestones/v1.13-ROADMAP.md) (Phases 67-72) - SHIPPED 2026-03-11
- [v1.12 Deployment & Code Health](milestones/v1.12-ROADMAP.md) (Phases 62-66) - SHIPPED 2026-03-11
- [v1.11 WAN-Aware Steering](milestones/v1.11-ROADMAP.md) (Phases 58-61) - SHIPPED 2026-03-10
- [v1.10 Architectural Review Fixes](milestones/v1.10-ROADMAP.md) (Phases 50-57) - SHIPPED 2026-03-09
- [v1.9 Performance & Efficiency](milestones/v1.9-ROADMAP.md) (Phases 47-49) - SHIPPED 2026-03-07
- [v1.8 Resilience & Robustness](milestones/v1.8-ROADMAP.md) (Phases 43-46) - SHIPPED 2026-03-06
- [v1.7 Metrics History](milestones/v1.7-ROADMAP.md) (Phases 38-42) - SHIPPED 2026-01-25
- [v1.6 Test Coverage 90%](milestones/v1.6-ROADMAP.md) (Phases 31-37) - SHIPPED 2026-01-25
- [v1.5 Quality & Hygiene](milestones/v1.5-ROADMAP.md) (Phases 27-30) - SHIPPED 2026-01-24
- [v1.4 Observability](milestones/v1.4-ROADMAP.md) (Phases 25-26) - SHIPPED 2026-01-24
- [v1.3 Reliability & Hardening](milestones/v1.3-ROADMAP.md) (Phases 21-24) - SHIPPED 2026-01-21
- [v1.2 Configuration & Polish](milestones/v1.2-ROADMAP.md) (Phases 16-20) - SHIPPED 2026-01-14
- [v1.1 Code Quality](milestones/v1.1-ROADMAP.md) (Phases 6-15) - SHIPPED 2026-01-14
- [v1.0 Performance Optimization](milestones/v1.0-ROADMAP.md) (Phases 1-5) - SHIPPED 2026-01-13

## Phase Details

### Phase 84: CAKE Detection & Optimizer Foundation

**Goal**: Operator can see exactly which CAKE queue type parameters are sub-optimal, with severity, rationale, and recommended values
**Depends on**: Nothing (first phase of v1.17; builds on existing `wanctl-check-cake` from v1.16)
**Requirements**: CAKE-01, CAKE-02, CAKE-03, CAKE-04, CAKE-05
**Success Criteria** (what must be TRUE):

1. Running `wanctl-check-cake spectrum.yaml` flags sub-optimal CAKE parameters with severity (ERROR/WARNING/INFO) and human-readable rationale
2. Detection reads queue type parameters from the router via REST `GET /rest/queue/type` (not queue tree) using new `get_queue_type()` method on RouterOSREST
3. Link-independent parameters (flowmode, nat, ack-filter, wash, diffserv) are compared against known-optimal defaults without any additional config
4. Link-dependent parameters (overhead, RTT) are compared against values from a `cake_optimization:` YAML config block -- never auto-detected from WAN name
5. Each sub-optimal parameter shows a diff of current value vs recommended value
   **Plans**: 2 plans

Plans:

- [x] 84-01-PLAN.md -- Router data layer: get_queue_types() method, optimal defaults constants, cake_optimization config extractor
- [x] 84-02-PLAN.md -- Check logic: check_cake_params(), check_link_params(), pipeline wiring, KNOWN_AUTORATE_PATHS update

### Phase 85: Auto-Fix CLI Integration

**Goal**: Operator can apply recommended CAKE parameters to a production router safely with confirmation, rollback snapshot, and daemon coordination
**Depends on**: Phase 84
**Requirements**: FIX-01, FIX-02, FIX-03, FIX-04, FIX-05, FIX-06, FIX-07
**Success Criteria** (what must be TRUE):

1. Running `wanctl-check-cake spectrum.yaml --fix` shows proposed changes as a before/after diff and prompts for confirmation before applying
2. Fix applies changes via REST PATCH to `/rest/queue/type/{id}` using new `set_queue_type_params()` method and reports success/failure per parameter as CheckResult items
3. Fix refuses to proceed when the wanctl daemon is running (lock file check at `/run/wanctl/*.lock`), with a clear message telling operator to stop the daemon first
4. A JSON snapshot of current parameter values is saved to a timestamped file before any changes are applied, enabling manual rollback
5. `--yes` bypasses interactive confirmation and `--json` outputs structured results for scripting
   **Plans**: 2 plans

Plans:

- [ ] 85-01-PLAN.md -- Fix infrastructure: set_queue_type_params() PATCH method, daemon lock check, snapshot persistence, change extraction
- [ ] 85-02-PLAN.md -- Fix orchestration: run_fix() flow, diff table, confirmation, CLI --fix/--yes flags

### Phase 86: Bufferbloat Benchmarking

**Goal**: Operator can run standardized RRUL bufferbloat tests and get an actionable A-F grade for download and upload latency under load
**Depends on**: Nothing (independent of Phases 84-85)
**Requirements**: BENCH-01, BENCH-02, BENCH-03, BENCH-04, BENCH-05, BENCH-06, BENCH-07
**Success Criteria** (what must be TRUE):

1. Running `wanctl-benchmark run` executes an RRUL bufferbloat test via flent subprocess and reports separate download and upload grades (A+ through F)
2. If flent or netperf are not installed, the tool exits with clear install instructions (package names and commands, not a Python traceback)
3. Netperf server connectivity is verified with a 3s timeout before starting the full test -- fast failure instead of waiting 60s
4. `--quick` mode runs a 10-second test for fast iteration during tuning; `--server` overrides the default netperf server host
5. Benchmark output shows latency percentiles (P50/P95/P99) and throughput alongside the letter grade
   **Plans**: 2 plans

Plans:

- [ ] 86-01-PLAN.md -- Data model, grade computation, and flent result parsing (BenchmarkResult, compute_grade, extract functions)
- [ ] 86-02-PLAN.md -- CLI tool, prerequisites, subprocess orchestration, output formatting, entry point

### Phase 87: Benchmark Storage & Comparison

**Goal**: Operator can store benchmark results and compare before/after optimization to prove CAKE tuning worked
**Depends on**: Phase 86
**Requirements**: STOR-01, STOR-02, STOR-03, STOR-04
**Success Criteria** (what must be TRUE):

1. Benchmark results are automatically stored in SQLite (`benchmarks` table) with timestamp, WAN name, grade, latency percentiles, and throughput
2. Running `wanctl-benchmark compare` shows grade delta and latency improvement between two runs (typically before and after CAKE optimization)
3. Running `wanctl-benchmark history` or `wanctl-history --benchmarks` lists past benchmark results with time-range filtering
4. Each stored result includes metadata (netperf server, test duration, daemon running status) so non-comparable runs can be identified
   **Plans**: TBD

Plans:

- [ ] 87-01: TBD
- [ ] 87-02: TBD

## Progress

### Active Milestone: v1.17 CAKE Optimization & Benchmarking

**Execution Order:**
Phases execute in numeric order: 84 -> 85 -> 86 -> 87
(Phase 86 is independent of 84-85 but sequenced after for simplicity)

| Phase                                     | Plans Complete | Status      | Completed  |
| ----------------------------------------- | -------------- | ----------- | ---------- |
| 84. CAKE Detection & Optimizer Foundation | 2/2            | Complete    | 2026-03-13 |
| 85. Auto-Fix CLI Integration              | 2/2 | Complete    | 2026-03-13 |
| 86. Bufferbloat Benchmarking              | 2/2 | Complete   | 2026-03-13 |
| 87. Benchmark Storage & Comparison        | 0/?            | Not started | -          |

### Completed Milestones

| Milestone                            | Phases | Plans | Status   | Shipped    |
| ------------------------------------ | ------ | ----- | -------- | ---------- |
| v1.16 Validation & Op. Confidence    | 81-83  | 4     | Complete | 2026-03-13 |
| v1.15 Alerting & Notifications       | 76-80  | 10    | Complete | 2026-03-12 |
| v1.14 Operational Visibility         | 73-75  | 7     | Complete | 2026-03-11 |
| v1.13 Legacy Cleanup & Feature Grad. | 67-72  | 10    | Complete | 2026-03-11 |
| v1.12 Deployment & Code Health       | 62-66  | 7     | Complete | 2026-03-11 |
| v1.11 WAN-Aware Steering             | 58-61  | 8     | Complete | 2026-03-10 |
| v1.10 Architectural Review Fixes     | 50-57  | 15    | Complete | 2026-03-09 |
| v1.9 Performance & Efficiency        | 47-49  | 6     | Complete | 2026-03-07 |
| v1.8 Resilience & Robustness         | 43-46  | 8     | Complete | 2026-03-06 |
| v1.7 Metrics History                 | 38-42  | 8     | Complete | 2026-01-25 |
| v1.6 Test Coverage 90%               | 31-37  | 17    | Complete | 2026-01-25 |
| v1.5 Quality & Hygiene               | 27-30  | 8     | Complete | 2026-01-24 |
| v1.4 Observability                   | 25-26  | 4     | Complete | 2026-01-24 |
| v1.3 Reliability & Hardening         | 21-24  | 5     | Complete | 2026-01-21 |
| v1.2 Configuration & Polish          | 16-20  | 5     | Complete | 2026-01-14 |
| v1.1 Code Quality                    | 6-15   | 30    | Complete | 2026-01-14 |
| v1.0 Performance Optimization        | 1-5    | 8     | Complete | 2026-01-13 |

**Total:** 83 phases complete, 170 plans across 17 milestones

<details>
<summary>v1.16 Validation & Operational Confidence (Phases 81-83) - SHIPPED 2026-03-13</summary>

**Milestone Goal:** Operator-facing CLI tools that catch misconfigurations before runtime and verify router queue state matches expectations.

- [x] Phase 81: Config Validation Foundation (1/1 plans) -- completed 2026-03-12
- [x] Phase 82: Steering Config + Output Modes (2/2 plans) -- completed 2026-03-13
- [x] Phase 83: CAKE Qdisc Audit (1/1 plans) -- completed 2026-03-13

**Key Results:** `wanctl-check-config` CLI tool with auto-detection (autorate/steering), 6 validation categories, cross-config topology checks, JSON output mode. `wanctl-check-cake` CLI for live router CAKE queue audit (connectivity, queue tree, CAKE type, max-limit diff, mangle rules). 157 new tests (2,666 to 2,823), 16/16 requirements satisfied.

See [milestones/v1.16-ROADMAP.md](milestones/v1.16-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.15 Alerting & Notifications (Phases 76-80) - SHIPPED 2026-03-12</summary>

**Milestone Goal:** Proactive alerting when wanctl detects noteworthy events, delivered via Discord webhook with per-event cooldown suppression.

- [x] Phase 76: Alert Engine & Configuration (2/2 plans) -- completed 2026-03-12
- [x] Phase 77: Webhook Delivery (2/2 plans) -- completed 2026-03-12
- [x] Phase 78: Congestion & Steering Alerts (2/2 plans) -- completed 2026-03-12
- [x] Phase 79: Connectivity & Anomaly Alerts (2/2 plans) -- completed 2026-03-12
- [x] Phase 80: Observability & CLI (2/2 plans) -- completed 2026-03-12

**Key Results:** AlertEngine with per-event cooldown and SQLite persistence, Discord webhook delivery with color-coded embeds, sustained congestion and steering transition alerts, WAN offline/recovery and anomaly detection, health endpoint alerting section and CLI history query. 221 new tests (2,445 to 2,666), 17/17 requirements satisfied.

See [milestones/v1.15-ROADMAP.md](milestones/v1.15-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.14 and earlier (Phases 1-75) - SHIPPED 2026-01-13 to 2026-03-11</summary>

See individual milestone archives in `milestones/` for details:

- [v1.14 Operational Visibility](milestones/v1.14-ROADMAP.md) - TUI dashboard, live monitoring, sparklines
- [v1.13 Legacy Cleanup & Feature Graduation](milestones/v1.13-ROADMAP.md) - Legacy cleanup, feature graduation
- [v1.12 Deployment & Code Health](milestones/v1.12-ROADMAP.md) - Deployment alignment, security, config consolidation
- [v1.11 WAN-Aware Steering](milestones/v1.11-ROADMAP.md) - WAN zone fusion, confidence scoring
- [v1.10 Architectural Review Fixes](milestones/v1.10-ROADMAP.md) - Hot-loop, failover, test quality
- [v1.9 Performance & Efficiency](milestones/v1.9-ROADMAP.md) - icmplib, profiling, telemetry
- [v1.8 Resilience & Robustness](milestones/v1.8-ROADMAP.md) - Error recovery, fail-safe, shutdown
- [v1.7 Metrics History](milestones/v1.7-ROADMAP.md) - SQLite storage, CLI, HTTP API
- [v1.6 Test Coverage 90%](milestones/v1.6-ROADMAP.md) - 743 tests, CI enforcement
- [v1.5 Quality & Hygiene](milestones/v1.5-ROADMAP.md) - Coverage infra, security audit
- [v1.4 Observability](milestones/v1.4-ROADMAP.md) - Steering health endpoint
- [v1.3 Reliability & Hardening](milestones/v1.3-ROADMAP.md) - Failover, safety tests
- [v1.2 Configuration & Polish](milestones/v1.2-ROADMAP.md) - Phase2B dry-run, config docs
- [v1.1 Code Quality](milestones/v1.1-ROADMAP.md) - Refactoring, shared modules
- [v1.0 Performance Optimization](milestones/v1.0-ROADMAP.md) - 40x speed improvement

</details>
