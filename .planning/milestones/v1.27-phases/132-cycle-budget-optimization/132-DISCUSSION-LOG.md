# Phase 132: Cycle Budget Optimization - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-03
**Phase:** 132-cycle-budget-optimization
**Areas discussed:** RTT measurement strategy, ThreadPool lifecycle, Regression indicator, Target budget & fallback

---

## RTT Measurement Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Non-blocking measurement | Decouple ICMP from control loop: dedicated background thread pings continuously, control loop reads latest RTT from shared state (<1ms). Eliminates 42ms blocking I/O. Phase 131 Option D. | ✓ |
| Optimize current blocking path | Keep blocking design but tighten: reduce ICMP timeout, reuse ThreadPoolExecutor, reduce hosts. Targets ~10-15ms reduction. Phase 131 Option A. | |
| Both in sequence | Start with blocking optimizations, then refactor to non-blocking in same phase. | |

**User's choice:** Non-blocking measurement
**Notes:** Straight to the architectural fix rather than incremental patches.

### Follow-up: RTT Delivery Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Shared atomic variable | Background thread writes latest RTT to thread-safe shared value. Control loop reads each cycle. Fits signal_utils pattern. | ✓ |
| Queue-based handoff | Push RTT samples to queue, control loop drains latest. Adds complexity for no clear benefit at 20Hz. | |

**User's choice:** Shared atomic variable

### Follow-up: Ping Host Count

| Option | Description | Selected |
|--------|-------------|----------|
| Keep 3-host median | Background thread still pings 3 reflectors concurrently, takes median. Since no longer blocking, measurement quality stays high. | ✓ |
| Reduce to 2 hosts | Average-of-2, slightly less robust. Speed gain less valuable when non-blocking. | |
| Configurable host count | YAML config control. Probably unnecessary. | |

**User's choice:** Keep 3-host median

### Follow-up: Staleness Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Staleness timeout with fallback | If RTT data older than ~500ms/10 cycles, warn + use last-known-good. If stale >5s, treat as measurement failure. | ✓ |
| Always use latest available | No staleness check. Simpler but risks stale decisions. | |

**User's choice:** Staleness timeout with fallback

---

## ThreadPool Lifecycle

| Option | Description | Selected |
|--------|-------------|----------|
| Persistent pool | Create ThreadPoolExecutor once at startup (max_workers=3), reuse across all measurement cycles. Eliminates per-cycle thread creation/teardown. | ✓ |
| Single-threaded sequential | Background thread pings hosts sequentially. Simpler but 3x slower, reduces measurement freshness. | |

**User's choice:** Persistent pool
**Notes:** Eliminates the 16.4% CPU overhead seen in py-spy flamegraph.

---

## Regression Indicator

| Option | Description | Selected |
|--------|-------------|----------|
| Utilization threshold + status field | Configurable warning_threshold_pct (default 80%). Health endpoint adds status: ok/warning/critical. | ✓ |
| Windowed trend detection | Sliding window utilization trend. More sophisticated but harder to configure. | |
| Simple boolean flag | Just overbudget true/false. Minimal, doesn't catch creeping degradation. | |

**User's choice:** Utilization threshold + status field

### Follow-up: Discord Alert Integration

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, with AlertEngine | New cycle_budget_warning alert type. Fires on sustained threshold exceedance. Reuses existing Discord + rate limiting. | ✓ |
| Health endpoint only | Expose in health JSON, operator checks manually. Lower noise. | |

**User's choice:** Yes, with AlertEngine

---

## Target Budget & Fallback

| Option | Description | Selected |
|--------|-------------|----------|
| Under 50ms avg, <80% utilization | Target <40ms on 50ms cycle. With RTT moved to background, control loop should drop to well under 10ms. | ✓ |
| Under 50ms avg (no utilization target) | Just get avg below interval. Doesn't account for p95/p99 spikes. | |
| Under 75% utilization | Stricter 37.5ms target. May require optimizing secondary consumers too. | |

**User's choice:** Under 50ms avg, <80% utilization

### Follow-up: Interval Fallback

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, 75ms as documented fallback | If non-blocking + persistent pool can't hit <80%, widen interval as last resort. | |
| No, optimize further first | Keep 50ms non-negotiable. Optimize secondary consumers before widening. | |
| You decide after measurement | Implement optimization, measure, then decide. Don't pre-commit. | ✓ |

**User's choice:** Decide after measurement
**Notes:** Data-driven decision -- no pre-commitment to fallback path.

---

## Claude's Discretion

- Background thread sleep interval between measurement cycles
- Exact threading primitives for shared RTT value
- AlertEngine consecutive-check threshold for cycle_budget_warning
- Whether to optimize secondary consumers if headroom allows

## Deferred Ideas

None -- discussion stayed within phase scope
