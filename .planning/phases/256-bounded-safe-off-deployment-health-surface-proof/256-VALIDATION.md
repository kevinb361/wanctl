---
phase: 256
slug: bounded-safe-off-deployment-health-surface-proof
status: complete
created: 2026-06-20
---

# Phase 256 — Validation Strategy

## Validation Architecture

Phase 256 validation has two branches:

1. If approval is denied/missing, validation passes only for a blocked/no-mutation outcome.
2. If approval is granted, validation must prove rollback anchors, safe/off deploy/restart, route-management health surface, bridge continuity, and no route ownership mutation.

## Required Gates

### Gate 1 — Approval before mutation

Before any privileged read, backup write, config edit, code deploy, or service restart, execution must create:

- `evidence/phase256-approval-record-<timestamp>.md`

Acceptance:

- contains `APPROVED_PHASE256_DEPLOY: true` before mutation; or
- contains `APPROVED_PHASE256_DEPLOY: false` and execution stops with no mutation.

### Gate 2 — Rollback anchors

If approved, execution must create:

- `evidence/phase256-rollback-anchors-<timestamp>.md`

Acceptance:

- current flat `/opt/wanctl` backup path and manifest/checksum exists;
- current `/etc/wanctl/steering.yaml` backup path exists;
- current config parsed/redacted;
- rollback commands are written before deploy/edit.

### Gate 3 — Safe/off deploy/restart transcript

If approved, execution must create:

- `evidence/phase256-deploy-restart-<timestamp>.md`

Acceptance:

- target config is `mode: off` or `mode: dry_run`, never `active`;
- only `steering.service` is restarted;
- no RouterOS, Netwatch, CAKE/qdisc, or route-owner mutation command appears;
- rollback executes if post-restart steering health fails.

### Gate 4 — Route-management health proof

Execution must create:

- `evidence/phase256-health-proof-<timestamp>.md`

Acceptance:

- if no deploy occurred, artifact records blocked/no-health-proof;
- if deploy occurred, `127.0.0.1:9102/health` contains `route_management` fields for owner/mode/guard/last-action/circuit/reconciliation or equivalent route-management health structure;
- bridge health is checked separately on `10.10.110.223:9101` and `10.10.110.227:9101`;
- artifact explicitly states bridge health is not route-management acceptance.

## Automated Planning Checks

```bash
python3 - <<'PY'
from pathlib import Path
import re
phase = Path('.planning/phases/256-bounded-safe-off-deployment-health-surface-proof')
all_text = '\n'.join((phase / name).read_text() for name in ['256-01-PLAN.md', '256-02-PLAN.md'])
for req in ['DEPLOY-02','DEPLOY-03','CONFIG-03','HEALTH-01','HEALTH-02','HEALTH-03','SAFE-20']:
    assert re.search(rf'\b{req}\b', all_text), req
for token in ['CHECKPOINT REQUIRED','APPROVED_PHASE256_DEPLOY','phase256-rollback-anchors','127.0.0.1:9102','10.10.110.223:9101','10.10.110.227:9101','No RouterOS route mutation','No Netwatch disablement','No CAKE/qdisc change']:
    assert token in all_text, token
print('phase256 planning validation passed')
PY

git diff --check
```
