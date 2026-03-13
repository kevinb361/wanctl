# Requirements: wanctl v1.17 CAKE Optimization & Benchmarking

**Defined:** 2026-03-13
**Core Value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.

## v1.17 Requirements

### CAKE Parameter Detection

- [x] **CAKE-01**: Operator can see sub-optimal CAKE queue type parameters flagged with severity and rationale
- [x] **CAKE-02**: Detection reads queue type params from router via REST API (`GET /rest/queue/type`)
- [x] **CAKE-03**: Detection compares link-independent params (flowmode, nat, ack-filter, wash, diffserv) against known-optimal defaults
- [x] **CAKE-04**: Detection compares link-dependent params (overhead, RTT) against values specified in YAML config
- [x] **CAKE-05**: Detection shows diff output of current vs recommended values for each sub-optimal parameter

### CAKE Auto-Fix

- [ ] **FIX-01**: Operator can apply recommended CAKE parameters to router via `--fix` flag
- [x] **FIX-02**: Fix applies changes via REST API PATCH to `/rest/queue/type/{id}` (not queue tree)
- [ ] **FIX-03**: Fix shows before/after diff and requires confirmation (unless `--yes`)
- [x] **FIX-04**: Fix refuses to apply if wanctl daemon is running (lock file check)
- [x] **FIX-05**: Fix saves parameter snapshot (current values) to JSON before applying changes
- [ ] **FIX-06**: Fix results reported as CheckResult items with success/failure per parameter
- [ ] **FIX-07**: Fix supports `--json` output mode for scripting

### Bufferbloat Benchmarking

- [ ] **BENCH-01**: Operator can run RRUL bufferbloat test via `wanctl-benchmark` CLI wrapping flent
- [ ] **BENCH-02**: Benchmark checks prerequisites (flent, netperf installed) with clear install instructions on failure
- [ ] **BENCH-03**: Benchmark checks netperf server connectivity before starting full test
- [ ] **BENCH-04**: Benchmark grades results A+ through F using industry-standard latency-increase thresholds
- [ ] **BENCH-05**: Benchmark reports separate download and upload bufferbloat grades
- [ ] **BENCH-06**: Benchmark supports `--quick` mode for fast 10s iteration during tuning
- [ ] **BENCH-07**: Benchmark supports `--server` flag to specify netperf server host

### Benchmark Storage & Comparison

- [ ] **STOR-01**: Benchmark results stored in SQLite with timestamp, WAN name, grade, latency percentiles, throughput
- [ ] **STOR-02**: Operator can compare before/after results showing grade delta and latency improvement
- [ ] **STOR-03**: Operator can query benchmark history with time-range filtering
- [ ] **STOR-04**: Benchmark results include metadata (server, duration, daemon status) for comparability

## Future Requirements

### Integration & Polish

- **INTG-01**: Combined audit+benchmark workflow (`wanctl-check-cake --fix` then `wanctl-benchmark` in one session)
- **INTG-02**: Health endpoint benchmark summary (last grade, last run timestamp)
- **INTG-03**: Per-WAN benchmark profiles with configurable SLA thresholds

## Out of Scope

| Feature                        | Reason                                                                                                             |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| Graphical plots/charts         | Adds matplotlib dependency, not useful in CLI/SSH context. Use flent's own plotting or feed JSON to external tools |
| Continuous benchmark daemon    | Benchmarks saturate the link — cannot run alongside production traffic shaping                                     |
| Auto-schedule benchmarks       | Risk of running during production hours, saturating link                                                           |
| Modify queue tree entries      | Queue tree max-limit is dynamically managed by wanctl daemon. Only modify queue TYPE parameters                    |
| Create/delete queue types      | Destructive. Assumes queue types already exist from initial router setup                                           |
| Import flent as Python library | Unstable internal API, pulls heavy GUI deps (matplotlib, PyQt5)                                                    |
| Built-in netperf server        | Must run on a DIFFERENT machine to measure the link                                                                |
| Auto-detect link type          | Violates portable controller architecture. Link-dependent params must come from YAML config                        |
| Auto-tune bandwidth ceiling    | Requires iterative testing over hours/days, false precision                                                        |

## Traceability

| Requirement | Phase    | Status   |
| ----------- | -------- | -------- |
| CAKE-01     | Phase 84 | Complete |
| CAKE-02     | Phase 84 | Complete |
| CAKE-03     | Phase 84 | Complete |
| CAKE-04     | Phase 84 | Complete |
| CAKE-05     | Phase 84 | Complete |
| FIX-01      | Phase 85 | Pending  |
| FIX-02      | Phase 85 | Complete |
| FIX-03      | Phase 85 | Pending  |
| FIX-04      | Phase 85 | Complete |
| FIX-05      | Phase 85 | Complete |
| FIX-06      | Phase 85 | Pending  |
| FIX-07      | Phase 85 | Pending  |
| BENCH-01    | Phase 86 | Pending  |
| BENCH-02    | Phase 86 | Pending  |
| BENCH-03    | Phase 86 | Pending  |
| BENCH-04    | Phase 86 | Pending  |
| BENCH-05    | Phase 86 | Pending  |
| BENCH-06    | Phase 86 | Pending  |
| BENCH-07    | Phase 86 | Pending  |
| STOR-01     | Phase 87 | Pending  |
| STOR-02     | Phase 87 | Pending  |
| STOR-03     | Phase 87 | Pending  |
| STOR-04     | Phase 87 | Pending  |

**Coverage:**

- v1.17 requirements: 23 total
- Mapped to phases: 23
- Unmapped: 0

---

_Requirements defined: 2026-03-13_
_Last updated: 2026-03-13 after roadmap creation_
