# Phase 243: Cycle-Budget Benchmark Gate - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-16
**Phase:** 243-cycle-budget-benchmark-gate
**Areas discussed:** Benchmark vehicle + host, Comparison basis, Load generation, Pre-registered gate thresholds

---

## Benchmark Vehicle + Host

| Option | Description | Selected |
|--------|-------------|----------|
| Throwaway unit, dev .226 | Transient unit runs real controller loop w/ each backend on Spectrum dev host | |
| Throwaway unit, dev .233 ATT | Same approach on the ATT dev host | |
| Revive wanctl@ + ExecStart override | Phase 217 method; entangles with prod state (wanctl@ disabled, prod=cake-autorate) | |
| Both dev WANs | Run on both .226 and .233; gate covers both egress paths / reflector sets | ✓ |

**User's choice:** Both dev WANs (implies throwaway transient unit, not wanctl@ revive)
**Notes:** Hard requirement is "real systemd unit, not TTY" — TTY-vs-pipe is the STALL fingerprint. Throwaway unit satisfies that, is reversible, avoids prod-state entanglement. Running both WANs widens egress/reflector coverage. → D-01, D-01a, D-01b.

---

## Comparison Basis

| Option | Description | Selected |
|--------|-------------|----------|
| Same-run icmplib arm primary + historical anchor | Gate on fping vs same-host same-run icmplib delta; 2.85/6.9 as representativeness sanity check | ✓ |
| Same-run icmplib arm only | Pure head-to-head; drops historical anchor | |
| Historical baseline only | Gate fping directly vs 2.85/6.9; conflates dev-host drift with backend cost | |

**User's choice:** Same-run icmplib arm primary + historical anchor
**Notes:** Controls for dev-host CPU/kernel drift vs prod-historical numbers while keeping the roadmap-named external anchor as a representativeness check. → D-02.

---

## Load Generation

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse flent/netperf established path | flent RRUL over each WAN's netperf target (Spectrum→Dallas Linode 104.200.21.31; ATT→established) | ✓ |
| iperf3 saturation | Diverges from netperf methodology; memory flags netperf→iperf swap as needing approval | |
| Synthetic / no real WAN load | Doesn't reproduce real bufferbloat contention; weakens gate validity | |

**User's choice:** Reuse flent/netperf established path
**Notes:** "Under load" = real WAN saturation so controller is in active CAKE adjustment while fping bursts contend. Matches historical-baseline conditions, respects the no-iperf-swap memory constraint. → D-03.

---

## Pre-Registered Gate Thresholds

| Option | Description | Selected |
|--------|-------------|----------|
| Relative delta + absolute ceiling | ≤20% regression on avg/p99 vs same-run icmplib AND p99 < 10ms absolute ceiling + CPU% delta bound | ✓ |
| Relative delta only | Pure fping-vs-icmplib delta; no absolute ceiling | |
| Absolute ceiling only | Fixed p99/avg ceilings; ignores the controlled icmplib comparison | |
| Tighter relative (10%) + ceiling | Stricter 10% bound; higher false-fail risk on tail noise | |

**User's choice:** Relative delta + absolute ceiling
**Notes:** Both layers wanted — catch relative regression AND any absolute blowup. fping is off-loop so p99 tail contention is the real risk, not avg. Companion defaults ratified in the framing (subprocess hygiene: zombies=0, fd flat, Tasks bounded; STALL: zero >100ms cycle gaps; sample floor: ≥30min AND ≥10k cycles/arm). → D-04, D-04a/b/c.

---

## Claude's Discretion

- Benchmark harness shape (`systemd-run` transient vs committed `wanctl-bench@.service`); controller launch/teardown — must keep stdout on journal pipe (not TTY) and stay inside SAFE-17 allowlist.
- Pre-registration artifact format/location (e.g. `243-BENCHMARK-PREREGISTRATION.md` + evidence JSON + recorded verdict).
- Exact CPU% delta figure; fd/zombie/Tasks sampling mechanism and trend test.
- ATT's exact netperf load target.

## Deferred Ideas

- Phase 245: the live A/B itself (this gate is its precondition).
- Phase 244: full per-sample `/health` backend/source_ip attribution.
- Phase 246: conditional production default flip to fping.
- Runtime backend hot-swap / demotion watcher — rejected in 242, not revisited.
