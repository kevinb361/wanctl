---
created: 2026-04-14T21:10:13.999Z
title: Track steering RTT source and fallback usage
area: performance
files:
  - src/wanctl/steering/daemon.py:989
  - src/wanctl/steering/daemon.py:1683
  - src/wanctl/wan_controller.py:3347
  - src/wanctl/health_check.py:380
  - docs/STEERING.md:33
---

## Problem

Steering now prefers the primary autorate daemon's live ICMP measurement feed and only falls back to its legacy self-probe path when the autorate measurement is missing or stale. This removed the duplicate steering-side ping retry noise during live production RRUL validation on 2026-04-14, but the current operator surfaces do not make that source selection explicit.

After the soak, we still need a direct way to answer basic production questions without re-reading code or grepping logs:
- Is steering currently using autorate RTT or fallback self-probe?
- How often did fallback activate during the soak window?
- Was a bad steering decision caused by stale autorate health, missing measurement data, or a real congestion event?

This is distinct from the existing overrun investigation. The control path is now working correctly; the gap is observability around the RTT source contract and fallback frequency.

## Solution

Add explicit steering observability around RTT source selection without changing thresholds, timers, or congestion logic.

Focus areas:
- Expose the current RTT source in steering health, for example `autorate_health` vs `self_probe_fallback`.
- Add counters or bounded history for fallback activations so a soak review can quantify how often the fallback path was needed.
- Emit a clear warning when steering enters fallback mode, while keeping steady-state autorate-feed use quiet.
- Keep the new fields additive so existing health consumers are not broken.
- Add narrow regression tests around any new steering health/log surfaces.

This should stay scoped to observability and soak-readiness, not a control-plane behavior change.

## Resolution — FIXED 2026-04-14

The steering RTT source contract is now observable in both the repo and production.

- Steering health now exposes an additive `rtt_source` section with:
  - current source
  - last successful source
  - last RTT value and measurement age
  - counts for `autorate_health`, `autorate_irtt`, and `history_fallback`
- Steering source order was simplified to:
  - autorate live ICMP measurement
  - autorate IRTT
  - bounded historical RTT fallback
- The legacy steering self-probe fallback was removed from steady-state operation.
- Production `/health` now shows source usage directly, which makes soak review straightforward.

This closed the original observability gap. Any future work in this area should be about follow-on polish or source-specific alerting, not the missing source contract itself.
