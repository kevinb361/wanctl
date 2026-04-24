---
created: 2026-04-24T21:01:58Z
title: Resolve ATT cake-primary canary after Phase 196
area: validation
files:
  - .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/196-VERIFICATION.md
  - .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/att-canary/att-canary-gate.md
  - .planning/phases/191-netlink-apply-timing-stabilization/191-VERIFICATION.md
  - .planning/phases/191.1-att-config-drift-resolution-and-phase-191-closure/191.1-rerun-results.json
---

## Problem

Phase 196 ATT status: ATT canary blocked by Phase 191.

Plan 196-04 created `soak/att-canary/att-canary-gate.md` with
`phase_191_status: blocked` and
`decision: blocked-do-not-run-att-canary`. Because the gate stayed blocked, no
ATT `cake-primary` mode switch, ATT soak capture, ATT flent load, mode proof,
or ATT throughput verdict was produced.

The Phase 191 blocker remains the restored-config ATT closure evidence. The
latest `2026-04-24` rerun recorded ATT RRUL `70.95 Mbps` against the old
`74.38 Mbps` lower bound; `191-VERIFICATION.md` still records Phase 191 open,
and `192-PRECONDITION-WAIVER.md` explicitly does not close Phase 191.

## Required Next Action

Close Phase 191 first, then rerun the ATT `tcp_12down` cake-primary canary.

After Phase 191 closure is recorded, reopen the Phase 196 ATT gate and run only
the narrow ATT canary path:

```bash
scripts/phase191-flent-capture.sh --label phase196_att_cake_primary_tcp12 --wan att --local-bind 10.10.110.226 --host dallas --duration 30 --output-dir "$HOME/flent-results/phase196" --tests tcp_12down
```

Accept the canary only if ATT `tcp_12down` is at least 95% of the last passing
ATT baseline and mode proof shows `active_primary_signal == "queue"` with
`wanctl_arbitration_active_primary == 1`. If the canary fails, roll ATT back to
`rtt-blend` and keep VALN-05 blocked.
