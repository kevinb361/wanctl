---
created: 2026-06-03T17:40:26Z
title: Retest Spectrum diffserv4 wash after local QoS changes
area: validation
resolves_phase: 227
files:
  - configs/spectrum.yaml
  - docs/BRIDGE_QOS.md
  - .planning/seeds/SEED-001-spectrum-topology-correct-cake-mode.md
  - .planning/PROJECT.md
---

## Problem

Spectrum currently runs CAKE as `920Mbit besteffort wash`, intentionally shipped by v1.44 Phase 209 after the 2026-04-22 flent finding and 24h soak. That decision was documented as topology-correct for DOCSIS because Spectrum/CMTS does not preserve DSCP and the local LAN/WMM path was not consuming DSCP as part of that milestone's scope.

Since then, the surrounding homelab QoS posture changed:

- CRS switches now have hardware QoS maps/trust on uplinks/AP boundaries and selected controlled hosts.
- Ruckus `Tik` has QoS Mirroring enabled and WiFi validation showed marked EF UDP had lower jitter than unmarked UDP.
- cake-shaper bridge QoS rules can classify download flows into EF/AF41/CS1 before CAKE.
- Router/client-originated DSCP may matter for Spectrum upload if Spectrum CAKE is allowed to tin traffic.

This does not invalidate v1.44 by itself, but it makes the old "classification theater" assumption worth re-testing under the current end-to-end QoS topology.

## Required Next Action

When `wanctl` reaches a safe stopping point, run a controlled Spectrum-only A/B. Do not change ATT.

Baseline current production:

```text
Spectrum download: 920Mbit besteffort wash
Spectrum upload:   18Mbit besteffort wash
```

Candidate A/B mode:

```text
Spectrum download: diffserv4 wash
Spectrum upload:   diffserv4 wash
```

Use `wash` first so CAKE can use local/router/bridge DSCP for tinning without changing downstream DSCP propagation semantics. Only consider `diffserv4 nowash` as a separate later experiment if `diffserv4 wash` clearly wins and there is an explicit reason to preserve DSCP beyond cake-shaper.

## Evidence to Capture

Before and after the candidate change:

1. `tc -s qdisc show dev spec-router` and `spec-modem`.
2. CAKE tin counters/drops/backlog/delay under load.
3. Spectrum health/state from wanctl during and after the test.
4. RRUL/flent or equivalent latency-under-load results.
5. A marked-flow plus unmarked-bulk check if practical:
   - EF low-rate UDP vs unmarked UDP
   - unmarked bulk TCP throughput
   - ping/latency distribution, but do not overfit single spikes
6. Restart count and pressure-state/transition-rate deltas.

## Acceptance / Rollback Criteria

Accept `diffserv4 wash` only if it produces a clear latency/jitter or realtime-flow protection win without throughput loss, daemon instability, or extra pressure-state churn.

Rollback immediately to `besteffort wash` if any of these appear:

- RRUL/load p99 latency regression greater than the v1.44 rollback gate tolerance.
- Higher Spectrum daemon restart rate.
- Meaningfully higher pressure-state transitions or flapping alerts.
- Upload stability regression; Spectrum upload is the fragile side.
- Tin counters show no useful non-BestEffort separation, making the change mostly ceremony again.

## Notes

This is a validation todo, not an instruction to mutate production immediately. The historical v1.44 decision remains valid until a fresh A/B under the current CRS/Ruckus/local-DSCP topology proves otherwise.
