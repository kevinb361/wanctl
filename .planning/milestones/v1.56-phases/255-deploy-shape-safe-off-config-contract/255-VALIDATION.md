---
phase: 255
slug: deploy-shape-safe-off-config-contract
status: complete
created: 2026-06-20
---

# Phase 255 — Validation Strategy

## Validation Architecture

Phase 255 verification must prove two things:

1. The live-deploy inspection stayed read-only and produced enough evidence to plan Phase 256 safely.
2. The proposed route-management config contract is safe/off or dry-run only and cannot imply active mutation.

## Required Gates

### Gate 1 — Read-only live command preflight

Execution must create:

- `evidence/deploy-shape-readonly-commands-<timestamp>.txt`
- `evidence/deploy-shape-command-validation-<timestamp>.json`

Acceptance:

- validation artifact reports `passed: true` before any live transcript/proof artifact exists;
- command file contains only read-only SSH/service/config/process/health inspection commands;
- command file rejects live mutation actions: `systemctl restart|reload|enable|disable|start|stop|daemon-reload`, `sudo tee`, redirection writes, `rsync`, `scp`, `git pull|reset|checkout|clean|merge|rebase`, package-manager install/remove, RouterOS route/Netwatch/script mutation, CAKE/qdisc mutation.

### Gate 2 — Deploy-shape proof artifact

Execution must create:

- `evidence/deploy-shape-proof-<timestamp>.md`

Acceptance:

- artifact includes service unit path/content summary, `ExecStart`, process argv, Python/venv path, code path, config path, config route-management presence/absence, health binding, bridge-health baseline, and rollback anchor;
- every issued live command line starts with `COMMAND:`;
- no-mutation proof scans only `COMMAND:` lines and reports `passed: true`.

### Gate 3 — Safe/off config contract

Execution must create:

- `evidence/safe-off-route-management-config-contract.md`

Acceptance:

- states exact allowed production mode: disabled/off or dry-run/observe only;
- says active mutation requires future explicit approval outside Phase 255;
- names validation source: `src/wanctl/check_steering_validators.py` and `configs/examples/steering.yaml.example`;
- records offline validation command/result, or blocks Phase 256 if validation cannot be run.

### Gate 4 — Phase 256 deploy/restart proposal

Execution must create:

- `evidence/phase256-deploy-restart-proposal.md`

Acceptance:

- includes explicit operator approval gate before any deploy/restart;
- separates code rollback, config rollback, service rollback/stop criteria, bridge-health checks, steering-health checks, and route-owner/no-mutation checks;
- states Netwatch remains route owner and no RouterOS route/Netwatch/CAKE/qdisc mutation is allowed by the proposal itself.

## Automated Planning Checks

Run during plan closeout:

```bash
python3 - <<'PY'
from pathlib import Path
import re
phase = Path('.planning/phases/255-deploy-shape-safe-off-config-contract')
plan = phase / '255-01-PLAN.md'
text = plan.read_text()
for req in ['DEPLOY-01','CONFIG-01','CONFIG-02','SAFE-20']:
    assert re.search(rf'\b{req}\b', text), req
for token in ['deploy-shape-readonly-commands', 'deploy-shape-command-validation', 'COMMAND:', 'safe-off-route-management-config-contract', 'phase256-deploy-restart-proposal']:
    assert token in text, token
for forbidden in ['systemctl restart', 'systemctl reload', 'RouterOS route mutation', 'Netwatch disablement', 'CAKE/qdisc mutation']:
    assert forbidden in text, forbidden
print('phase255 planning validation passed')
PY

git diff --check
```

## Live Execution Checks

Run during execute-phase only, after artifacts exist:

- command validation passed;
- deploy-shape proof exists and identifies live shape or records blocker;
- no-mutation proof over `COMMAND:` lines passed;
- config contract is safe/off/dry-run only;
- Phase 256 proposal exists and contains approval/rollback gates.
