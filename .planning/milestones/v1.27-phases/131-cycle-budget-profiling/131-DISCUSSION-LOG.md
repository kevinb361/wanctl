# Phase 131: Cycle Budget Profiling - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-02
**Phase:** 131-cycle-budget-profiling
**Areas discussed:** Profiling Granularity, Profiling Methodology, Load Generation & Test Plan, Output & Recommendation Format

---

## Profiling Granularity

| Option | Description | Selected |
|--------|-------------|----------|
| Split into 5-7 sub-timers | Break state_management into signal processing, EWMA, congestion, hysteresis, tuning, alerts. Reuses PerfTimer pattern. | |
| Full per-function py-spy flamegraph | Use py-spy to sample running daemon. Zero code changes, shows exact hot functions. Requires root. | |
| Both: sub-timers + one py-spy capture | Sub-timers for ongoing monitoring, py-spy for one-shot deep analysis. Belt and suspenders. | ✓ |

**User's choice:** Both approaches -- sub-timers for permanent monitoring + py-spy for deep analysis
**Notes:** None

### Follow-up: Sub-timer activation

| Option | Description | Selected |
|--------|-------------|----------|
| Always active | PerfTimer logs at DEBUG, OperationProfiler uses bounded deques. Negligible overhead. Matches existing pattern. | ✓ |
| Gated behind --profile | Only active when profiling enabled. Saves microseconds but loses production visibility. | |
| You decide | Claude picks approach | |

**User's choice:** Always active
**Notes:** None

---

## Profiling Methodology

| Option | Description | Selected |
|--------|-------------|----------|
| py-spy record --pid | Attach to running wanctl via PID, record 30-60s during RRUL, generate SVG flamegraph | ✓ |
| py-spy top --pid | Live top-like view. Interactive but harder to capture. | |
| cProfile wrapper script | Run wanctl with cProfile. More invasive. | |

**User's choice:** py-spy record --pid
**Notes:** None

### Follow-up: Installation location

| Option | Description | Selected |
|--------|-------------|----------|
| cake-shaper VM only | Install via pipx on cake-shaper | |
| Both dev + cake-shaper | Dev for analysis, cake-shaper for live capture | ✓ |

**User's choice:** Both machines
**Notes:** None

---

## Load Generation & Test Plan

| Option | Description | Selected |
|--------|-------------|----------|
| flent RRUL from dev | Same proven v1.26 methodology. 60s runs against Dallas netperf. | ✓ |
| iperf3 only | Pure bandwidth saturation, lighter setup, less representative. | |
| Both flent + iperf3 | flent for representative, iperf3 for max stress. | |

**User's choice:** flent RRUL from dev machine (same as v1.26)
**Notes:** None

### Follow-up: Number of runs

| Option | Description | Selected |
|--------|-------------|----------|
| 3 runs | 1 idle baseline + 2 loaded. py-spy during one loaded run. | ✓ |
| 5 runs | 1 idle + 4 loaded with py-spy on 2. More confidence. | |
| 1 run + py-spy | Quick but less reproducible. | |

**User's choice:** 3 runs
**Notes:** None

---

## Output & Recommendation Format

| Option | Description | Selected |
|--------|-------------|----------|
| Health endpoint + analysis doc | Enhanced health with per-subsystem breakdown. Analysis doc with measurements and recommendation. | ✓ |
| Health endpoint only | All data in health JSON. Analysis in Phase 132 planning. | |
| Dedicated profiling report script | New CLI tool for formatted reports. | |

**User's choice:** Health endpoint + analysis document
**Notes:** None

### Follow-up: Permanent visibility

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, always in health endpoint | Extend cycle_budget with per-subsystem breakdown. Feeds PERF-03. | ✓ |
| Only when --profile enabled | Health stays clean, sub-timers gated. | |

**User's choice:** Always visible in health endpoint
**Notes:** Feeds directly into PERF-03 regression indicator requirement

## Claude's Discretion

- Exact sub-timer boundaries within run_cycle()
- py-spy sampling rate and recording duration
- Analysis document format and structure

## Deferred Ideas

None -- discussion stayed within phase scope
