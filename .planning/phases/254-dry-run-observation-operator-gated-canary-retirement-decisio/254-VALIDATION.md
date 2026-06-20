---
phase: 254
slug: dry-run-observation-operator-gated-canary-retirement-decisio
status: complete
created: 2026-06-20
---

# Phase 254 — Validation Strategy

## Validation Architecture

Phase 254 is production-ish and safety-gated. Verification must prove two different things:

1. Planning/execution artifacts are complete and traceable.
2. Any live inspection or canary activity obeys the read-only / operator-approval boundaries.

## Required Gates

### Gate 1 — Read-only command preflight

Before live inspection, execution must create `evidence/read-only-commands-<timestamp>.txt` and validate it into `evidence/read-only-command-validation-<timestamp>.json`.

Acceptance:

- validation artifact reports `passed: true`;
- no live transcript exists before validation passes;
- command file contains only allowed read-only RouterOS print/export/health/operator-summary reads;
- mutation-shaped actions are rejected.

### Gate 2 — Dry-run evidence bundle

Execution must create `evidence/dry-run-observation-<timestamp>.md`.

Acceptance:

- includes command validation, issued commands, route-management health, operator summary, RouterOS read-only inventory, Snapshot-A drift check, and no-mutation proof;
- issued live command lines are prefixed with `COMMAND:`;
- no-mutation proof scans only `COMMAND:` lines;
- `last_applied_action` remains absent/unchanged during dry-run, or canary progression is blocked.

### Gate 3 — Pre-canary approval packet

Execution must create `evidence/pre-canary-approval-packet.md`.

Acceptance:

- includes Snapshot-A rollback path, stop criteria, rollback procedure, operator approval checklist, and final decision options;
- recommendation either asks for explicit approval or keeps Netwatch interim owner;
- no active mutation occurs in Wave 1.

### Gate 4 — Operator approval checkpoint

Wave 2 must stop before mutation unless `evidence/canary-approval-record-<timestamp>.md` records `APPROVED_ACTIVE_CANARY: true`.

Acceptance:

- no ambiguous approval counts;
- declined/missing approval routes to `keep-netwatch` or `rollback-to-netwatch` without mutation;
- approved canary names exact one-WAN scope and rollback evidence.

### Gate 5 — Canary observation / rollback / final decision

If approved, execution must create `evidence/canary-observation-<timestamp>.md`. Regardless of approval, execution must create `evidence/route-ownership-final-decision.md`.

Acceptance:

- canary observation records before/during/after health, operator summary, route/Netwatch state, stop criteria, rollback action, and result;
- final decision contains exactly one of `keep-netwatch`, `keep-wanctl-for-approved-scope`, `retire-or-alert-only-netwatch`, `rollback-to-netwatch`;
- final decision states route owner after phase close, rollback state after phase close, and SAFE-19 outcome.

## Automated Planning Checks

Run during plan closeout:

```bash
python3 - <<'PY'
from pathlib import Path
import re
phase = Path('.planning/phases/254-dry-run-observation-operator-gated-canary-retirement-decisio')
plans = [phase/'254-01-PLAN.md', phase/'254-02-PLAN.md']
all_text = '\n'.join(p.read_text() for p in plans)
for req in ['CB-02','OBS-02','CANARY-01','CANARY-02','CANARY-03','SAFE-19']:
    assert re.search(rf'\b{req}\b', all_text), req
assert 'COMMAND:' in all_text
assert 'CHECKPOINT REQUIRED' in all_text
assert 'APPROVED_ACTIVE_CANARY' in all_text
print('phase254 planning validation passed')
PY

git diff --check
```

## Live Execution Checks

Run during execute-phase only, after artifacts exist:

- command validation artifact passed;
- no-mutation proof over `COMMAND:` lines passed;
- approval record exists before any mutation;
- canary observation exists if approval true;
- final decision exists in all outcomes.
