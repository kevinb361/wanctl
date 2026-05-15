---
created: 2026-04-12T06:00:49.224Z
title: Keep ATT feature parity with Spectrum
area: operations
files:
  - /etc/wanctl/spectrum.yaml
  - /etc/wanctl/att.yaml
  - /home/kevin/projects/wanctl/.planning/ROADMAP.md
  - /home/kevin/projects/wanctl/src/wanctl/health_check.py
  - /home/kevin/projects/wanctl/src/wanctl/metrics.py
---

## Problem

Spectrum has been the primary live validation target for several recent observability and tuning changes, while ATT has occasionally lagged in exposed operator surfaces or deploy-time verification. That creates avoidable drift: a feature can look complete in code while one live WAN still lacks the same reachable surface or validation path.

## Solution

Treat ATT/Spectrum feature parity as an explicit acceptance check for future work:
- when a feature is validated live on Spectrum, confirm whether ATT exposes the same behavior or document why not
- keep `/etc/wanctl/att.yaml` and `/etc/wanctl/spectrum.yaml` aligned for shared features unless divergence is intentional and recorded
- make Phase 169 operator-surface work verify parity of reachable health and metrics surfaces across both WANs
- if parity is intentionally broken, record the reason in the phase summary instead of leaving it implicit

## Resolution — FIXED 2026-04-14

The live parity gap was verified and closed.

- ATT was missing the top-level metrics endpoint config that Spectrum already exposed.
- The running ATT autorate service had not been restarted since later health-surface changes, so live ATT `/health` was still missing the `measurement` section even though current code emitted it.
- `/etc/wanctl/att.yaml` was updated to add the missing top-level `metrics` stanza.
- `wanctl@att.service` was restarted cleanly at `2026-04-14 16:36:09 CDT`.

Live verification after restart:
- `http://10.10.110.227:9101/health` includes `wans[0].measurement`
- `http://10.10.110.227:9100/metrics` is reachable
- ATT and Spectrum now expose the same operator surfaces for current health/metrics parity

Future work should still treat ATT/Spectrum parity as an acceptance check, but the concrete gap tracked by this todo is closed.
