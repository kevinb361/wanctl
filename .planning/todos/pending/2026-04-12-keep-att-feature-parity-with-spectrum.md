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
