---
milestone: v1.46
name: Internet Quality Recovery
status: planning
created: 2026-05-27
---

# Milestone v1.46 Requirements: Internet Quality Recovery

**Goal:** Restore user-perceived internet quality by measuring real production behavior, identifying whether conservative upload limits, recovery lag, measurement collapse, steering/version drift, or refractory semantics are causing degraded experience, then reclaim throughput safely with evidence-backed canaries.

**Scope:** Evidence-first quality recovery. Production mutation is gated behind baseline evidence, Snapshot A rollback, one-knob canaries, and explicit operator approval. v1.45 VERIFY-01 remains a carried watch-list item, not a blocker for v1.46 quality work.

**Source:** Operator reassessment on 2026-05-27 during v1.45 production observation: project momentum was stalled on alerting proof while internet quality felt worse than it should. Live read showed Spectrum healthy at configured ceilings, not floor-clamped, but Spectrum upload remains deliberately conservative (`setpoint_mbps: 12`, `ceiling_mbps: 18`) relative to the 40 Mbps plan anchor. ATT/steering deployment-version drift and known `tcp_12down` bad-p99-while-GREEN evidence are explicit investigation inputs.

---

## v1.46 Requirements

### Production Inventory And Drift (DRIFT)

- [x] **DRIFT-01**: Operator can see an exact live inventory of Spectrum, ATT, and steering deployed versions, active health endpoints, service uptime, service status, and health summary state.
- [x] **DRIFT-02**: Operator can distinguish expected staged deployment state from accidental version/config drift; any ATT/steering version mismatch is either upgraded or documented as intentionally held.
- [x] **DRIFT-03**: Operator can verify repo config, deployed `/etc/wanctl/*.yaml`, and live `/health` critical operating points agree without exposing secrets.

### Experience Baseline (BASE)

- [x] **BASE-01**: Operator has a repeatable production baseline runbook for normal browsing, upload, download, RRUL, and `tcp_12down` checks with timestamps, commands, and artifact paths.
- [x] **BASE-02**: Each baseline run captures matching `/health`, CAKE state, SQLite alert counts, current rates, measurement quality, and steering state for the same time window.
- [x] **BASE-03**: Baseline results classify the perceived-quality issue into at least one primary bucket: upload ceiling/setpoint, download recovery lag, measurement collapse, steering drift, refractory semantics, or external ISP conditions.

### Measurement Collapse (MEAS)

- [x] **MEAS-01**: The pending `tcp_12down` investigation is rerun with a bounded matrix across time-of-day and captures p50/p95/p99 latency, throughput, reflector misses, protocol divergence, and controller state.
- [x] **MEAS-02**: If health remains `GREEN` during bad p99 latency, the operator has an explicit explanation of why and a proposed health/degraded-signal change or a documented reason not to add one.
- [x] **MEAS-03**: Any new degraded-measurement signal is observational first unless evidence proves it should affect control decisions.

### Conservative Throughput Reclaim (RECLAIM)

- [x] **RECLAIM-01**: Spectrum upload operating points are evaluated against current production evidence, including `setpoint_mbps: 12`, `ceiling_mbps: 18`, typical plan upload `40 Mbps`, latency, floor-hit counts, suppression counters, and user-perceived upload quality.
- [x] **RECLAIM-02**: At most one upload knob changes per canary cycle, with Snapshot A rollback, explicit success gates, and explicit rollback gates.
- [x] **RECLAIM-03**: Any successful reclaim canary improves operator-relevant throughput or perceived quality without increasing floor-hit cycles, alert spam, or p95/p99 latency beyond approved bounds.

### Recovery And Refractory Semantics (RECOV)

- [ ] **RECOV-01**: The Phase 196 queue-primary refractory semantics thread is closed with a concrete decision: no change, config-only tune, or code design phase.
- [ ] **RECOV-02**: If a code design is approved, it preserves Phase 160 cascade safety while keeping valid queue-delay signal available where needed for queue-primary classification.
- [ ] **RECOV-03**: Recovery lag after transient congestion is measured from production artifacts before changing `green_required`, `step_up`, backlog suppression, or refractory behavior.

### Performance Baseline (PERF)

- [ ] **PERF-01**: The pending post-hotpath production profiling todo is closed or promoted by capturing at least one hour of current production cycle-budget data.
- [ ] **PERF-02**: The profile identifies whether RTT measurement, CAKE stats, router communication, logging/metrics, or storage writes are now the dominant hot-path cost.
- [ ] **PERF-03**: If cycle budget is healthy, performance work is explicitly deprioritized in favor of quality/tuning work.

### Carry-Forward Production Verification (VERIFY)

- [ ] **VERIFY-01**: Operator can close the v1.45 deferred production gate when a natural production flapping event on either WAN produces an alerts row with `details.peak_transition_count > 30`; until then, the watch-list item remains open and must not block v1.46 quality work.
- [ ] **VERIFY-02**: Once VERIFY-01 closes, operator can run the ALERT-03 per-`cooldown_sec` bucket audit against that event and archive the retained v1.45 phase directories if the audit passes.

---

## Future Requirements (deferred)

- **Silicom bypass operational tooling and harness** — retained as SEED-006; not part of the internet-quality recovery spine unless baseline evidence points at bypass/bridge operations.
- **Storage hygiene fire-on-change work** — retained as SEED-007; only pull forward if PERF evidence shows storage/write pressure is quality-relevant.
- **CALIB-02 YAML knob shape evaluation** — gated on throughput-reclaim outcomes and not required for the baseline phases.

## Out of Scope

- **Artificially inducing flapping events** to close v1.45 VERIFY-01.
- **Threshold/floor/ceiling changes without baseline evidence** — no casual tuning of control parameters.
- **Multi-knob canaries** — one change per production canary cycle.
- **Production mutation during inventory/baseline phases** except explicitly approved read-only profiling/test captures.
- **Treating `/health.status == healthy` or state `GREEN` as sufficient proof of good user experience** — v1.46 explicitly tests that assumption.

## Traceability

| REQ-ID     | Phase | Status  |
|------------|-------|---------|
| DRIFT-01   | 212   | Complete |
| DRIFT-02   | 212   | Complete |
| DRIFT-03   | 212   | Complete |
| BASE-01    | 213   | Complete |
| BASE-02    | 213   | Complete |
| BASE-03    | 213   | Complete |
| MEAS-01    | 214   | Complete |
| MEAS-02    | 214   | Complete |
| MEAS-03    | 214   | Complete |
| RECLAIM-01 | 215   | Complete |
| RECLAIM-02 | 215   | Complete |
| RECLAIM-03 | 215   | Complete |
| RECOV-01   | 216   | Pending |
| RECOV-02   | 216   | Pending |
| RECOV-03   | 216   | Pending |
| PERF-01    | 217   | Pending |
| PERF-02    | 217   | Pending |
| PERF-03    | 217   | Pending |
| VERIFY-01  | 218   | Pending |
| VERIFY-02  | 218   | Pending |

**Coverage:** 20/20 v1.46 REQ-IDs mapped. Phase 218 is intentionally a lightweight watch-list/cleanup phase and should only execute when a natural production flapping event exists.
