# Phase 241: fping Backend (Offline) + Reflector Quality - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-15
**Phase:** 241-fping-backend-offline-reflector-quality
**Areas discussed:** Output mode, Reflector-scoring feed, Fixture capture, Scheduling/lifecycle, Burst geometry, Loss→fail threshold, Cadence/timeout

---

## Gray-area selection

User selected ALL four offered areas: fping invocation + output mode,
Reflector-scoring feed (REFL-01), Offline fixture capture strategy,
Scheduling + stall/death lifecycle.

---

## fping Output Mode

| Option | Description | Selected |
|--------|-------------|----------|
| `-C count` (per-ping) | Per-target timestamped; `-` loss tokens counted for exact per-reflector loss; never reads loss as 0ms; richest fixture target | ✓ |
| `-c count` (summary) | fping pre-aggregates loss%/avg per target; simpler parse but hides per-ping nuance and is where bad parses silently turn loss into a number | |

**User's choice:** `-C count` (per-ping)
**Notes:** Drives parser shape (FPING-04) and per-reflector loss derivation (REFL-01).

---

## Reflector-Scoring Feed (REFL-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Threshold loss%→bool, reuse `record_results()` | Map burst to success/fail, feed existing `dict[str,bool]`; scorer internals untouched; smallest SAFE-17 surface | ✓ |
| Extend scorer for loss fractions | Ingest 0.0–1.0 loss fraction; richer but widens the controller-path exception into scoring math | |

**User's choice:** Threshold loss%→bool, reuse `record_results()`
**Notes:** The one explicitly-accepted SAFE-17 controller-path touch; kept minimal (call-site only).

---

## Offline Fixture Source

| Option | Description | Selected |
|--------|-------------|----------|
| Build capture script, you run on live host | Phase ships capture helper; operator captures 6 scenarios on real host; commit as fixtures; genuinely "real 5.1" | ✓ |
| You already have captured samples | Point to existing captured output | |
| I synthesize from known 5.1 format | Hand-written fixtures; fastest but not "captured real" per FPING-04 | |

**User's choice:** Build capture script, operator runs on live host
**Notes:** Operator-in-the-loop step; must be flagged in the plan so it isn't skipped. Capture must not mutate production routing.

---

## Scheduling + Stall/Death Lifecycle

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse `BackgroundRTTThread`, one-shot per cadence, mirror irtt | Same thread drives fping `probe()`; bounded timeout < cadence; TimeoutExpired→log→None; recover-and-continue | ✓ |
| New fping-specific thread/loop | Dedicated scheduler or long-lived `fping -l`; more control but new lifecycle + bigger SAFE-17 surface | |

**User's choice:** Reuse `BackgroundRTTThread`, mirror `irtt_measurement.py`
**Notes:** fping is a second `RttBackend.probe()` implementation; no new scheduler.

---

## Burst Geometry (sub-decision)

| Option | Description | Selected |
|--------|-------------|----------|
| `-C 5 -p 200ms` (~1s burst) | 20%-resolution per-burst loss; real REFL-01 signal smoothed by scorer window; YAML knob | ✓ |
| `-C 3 -p 300ms` (~0.9s) | Leaner, 33%-resolution | |
| `-C 1` (match icmplib) | Per-burst loss collapses to 0/100%; adds little over scorer window | |

**User's choice:** `-C 5 -p 200ms`
**Notes:** Fanout is single-process so burst duration is independent of reflector count. Geometry exposed as YAML knob (Phase 243 benchmarks the load).

---

## Loss→Fail Mapping (sub-decision)

| Option | Description | Selected |
|--------|-------------|----------|
| Any loss = fail; partial still contributes RTT | Strict scoring; flaky-but-alive reflector penalized but its received-ping RTT still used | ✓ |
| Loss ≥ 50% = fail; partial still contributes RTT | Tolerant; slower to flag degradation | |
| You decide / planner discretion | Planner picks from REFL-01 intent + scorer semantics | |

**User's choice:** Any loss = fail; partial still contributes RTT
**Notes:** Scoring and sample-usability decoupled. Threshold exposed as a YAML knob (default any loss > 0%). fping-gated.

---

## Cadence + Timeout (sub-decision)

| Option | Description | Selected |
|--------|-------------|----------|
| Own `cadence_sec` knob (~10s, irtt-style); timeout = C×p + grace | Independent cadence, not bound to fast control interval; timeout < cadence so bursts never pile | ✓ |
| Bind cadence to controller interval (icmplib-style) | Uniform with icmplib but fights the bursty-subprocess model | |
| You decide | Planner picks from irtt precedent + chosen burst duration | |

**User's choice:** Own `cadence_sec` knob (~10s, irtt-style)
**Notes:** Mirrors `autorate_continuous.py:484` irtt cadence precedent.

---

## Claude's Discretion

- Exact extra fping flags (`-q`, per-ping `-t`, `-e`), provided `-C` per-ping
  output is preserved and fixtures match the exact invocation.
- Capture-script loss-induction method (blackhole IP for total loss, lossy/distant
  target for partial, mid-burst kill for process-death), kept safe/non-mutating.
- New backend module name (allowlist: `fping_measurement.py`) and the REFL-01
  boolean-conversion call-site location, fping-gated and inside SAFE-17.
- YAML key names/nesting for the fping knobs, consistent with the 240
  `measurement:` block and `/health` naming.
- Reuse of `RTTAggregationStrategy.MEDIAN` for per-host and cross-host aggregation.

## Deferred Ideas

- Backend factory + loud runtime fallback (FALL-01) — Phase 242.
- `/health` backend/source_ip attribution (HEALTH-01) — Phase 244.
- Live A/B under rollback anchor — Phase 245.
- Conditional default flip to fping — Phase 246.
- Extending `ReflectorScorer` to ingest loss fractions — rejected for this phase
  (larger SAFE-17 surface); revisit only if the binary feed proves too coarse.
- `irtt` as a selectable backend (IRTT-MIG-01) — future milestone.
