# Phase 258 Discussion Log

**Phase:** 258 — Read-Only RouterOS Access Repair
**Date:** 2026-06-20
**Mode:** discuss (default)

Human-reference record only. Downstream agents consume `258-CONTEXT.md`, not this file.

## Areas discussed (4 of 4 selected)

### Transport choice
- Options: match steering's live transport / REST explicitly / repair SSH key.
- **Selected:** Match steering's live transport. → D1. SSH-key repair dropped if steering uses REST. Research confirms live transport first.

### Least-privilege creds
- Options: dedicated read-only RouterOS user / reuse steering creds.
- **Selected:** Reuse steering creds. → D2. Accepted consequence: read-only enforced at the Phase-257 allowlist-validator layer, not RouterOS user policy.

### Provisioning method
- Options: operator step + /etc/wanctl/secrets / deploy.sh integration.
- **Selected:** Operator step + /etc/wanctl/secrets. → D3. Operator-at-keyboard for privileged reads; likely minimal if reusing existing steering creds.

### Proof definition
- Options: both route + netwatch parseable / single route read.
- **Selected:** Both /ip/route/print + /tool/netwatch/print, exit 0 + non-empty parseable. → D4. De-risks Phase 259.

## Deferred ideas
- Dedicated least-privilege read-only RouterOS user (mechanical enforcement).
- deploy.sh credential automation.

## Todos reviewed, not folded
- All Phase-258 todo matches were score-0.6 keyword-noise (phase/wanctl); none semantically related to access repair.
