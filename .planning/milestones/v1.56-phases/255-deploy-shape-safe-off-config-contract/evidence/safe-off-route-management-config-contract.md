# Phase 255 Safe/Off Route-Management Config Contract

Timestamp: 2026-06-20T03:28:00Z

## Target Mode

Accepted target for Phase 256 production deploy/restart proposal:

- `route_management.enabled: true` with `route_management.mode: "dry_run"`, or `route_management.enabled: false` with `route_management.mode: "off"` if the deploy only exposes health/config shape.
- `route_management.migration_acknowledged: false` for v1.56 safe/off deployment.
- Active route mutation remains out of scope for v1.56 and requires a future explicit operator approval gate.
- Under this target, active route mutation impossible by config contract and validator behavior.

## Required Config Shape

Minimum safe/off or dry-run shape for production steering config:

```yaml
route_management:
  enabled: true
  mode: "dry_run"
  migration_acknowledged: false
  routes:
    spectrum:
      comment: "Spectrum"
    att:
      comment: "ATT"
    att_policy:
      comment: "Force ATT_OUT to ATT WAN"
```

Allowed alternative for a code-only/health-surface smoke deploy:

```yaml
route_management:
  enabled: false
  mode: "off"
  migration_acknowledged: false
  routes:
    spectrum:
      comment: "Spectrum"
    att:
      comment: "ATT"
    att_policy:
      comment: "Force ATT_OUT to ATT WAN"
```

Source-of-truth validation behavior from `src/wanctl/check_steering_validators.py`:

- `route_management.enabled` must be boolean.
- `route_management.mode` must be one of `off`, `dry_run`, `active`.
- `route_management.migration_acknowledged` must be boolean.
- `mode: active` requires explicit migration/ownership acknowledgement.
- `enabled: true` requires at least one configured route.
- Each configured route requires a non-empty `comment` or `id` anchor.

Future active-only fields/state:

- `mode: "active"`
- `migration_acknowledged: true`
- any live RouterOS route enable/disable action
- any Netwatch disable/retirement action

Those are not allowed in Phase 255 or Phase 256 safe/off deployment.

## Offline Validation

Focused test command run:

```text
.venv/bin/pytest -o addopts='' tests/test_check_config.py -k 'route_management' -q
```

Result:

```text
.........                                                                [100%]
9 passed, 133 deselected in 0.38s
```

Temp production-shaped dry-run config validation command run:

```text
.venv/bin/python - <<'PY'
from pathlib import Path
import copy, yaml, json
from wanctl.check_steering_validators import validate_steering_cross_fields, check_steering_unknown_keys
from wanctl.check_config import Severity
base = yaml.safe_load(Path('configs/steering.yaml').read_text())
base['route_management'] = {
    'enabled': True,
    'mode': 'dry_run',
    'migration_acknowledged': False,
    'routes': {
        'spectrum': {'comment': 'Spectrum'},
        'att': {'comment': 'ATT'},
        'att_policy': {'comment': 'Force ATT_OUT to ATT WAN'},
    },
}
unknown = check_steering_unknown_keys(base)
cross = validate_steering_cross_fields(base)
errors = [r for r in unknown + cross if r.severity == Severity.ERROR]
active = copy.deepcopy(base)
active['route_management']['mode'] = 'active'
active['route_management']['migration_acknowledged'] = False
active_errors = [r for r in validate_steering_cross_fields(active) if r.severity == Severity.ERROR]
assert not errors
assert any('migration' in r.message.lower() or 'ownership' in r.message.lower() for r in active_errors)
PY
```

Result:

```json
{
  "tmp_config": ".planning/phases/255-deploy-shape-safe-off-config-contract/evidence/tmp-steering-route-management-dry-run.yaml",
  "dry_run_error_count": 0,
  "dry_run_errors": [],
  "active_without_ack_error_count": 1,
  "active_without_ack_errors": [
    "route_management.mode active requires explicit migration/ownership acknowledgement"
  ]
}
```

Validation verdict: pass. Dry-run shape validates with zero route-management errors; unsafe active mode without migration acknowledgement fails closed.

## Live Config Delta Proposal

Observed live `/etc/wanctl/steering.yaml` on `cake-shaper` has no `route_management` block per read-only grep in `deploy-shape-proof-20260620T032542Z.md`.

Phase 256 proposed delta is adding only the safe/off or dry-run `route_management` block above to the live steering config after creating a dated backup and before a bounded `steering.service` restart. This artifact is documentation only; Phase 255 did not write `/etc/wanctl/steering.yaml`.

The preferred Phase 256 target is dry-run if the deployed code exposes route-management health while making no RouterOS route changes:

- `enabled: true`
- `mode: "dry_run"`
- `migration_acknowledged: false`

If Phase 256 wants a lower-risk code-only smoke deploy first, use:

- `enabled: false`
- `mode: "off"`
- `migration_acknowledged: false`

## Safety Assertions

- active route mutation impossible under the Phase 256 safe/off or dry-run target.
- Netwatch remains active route owner.
- No RouterOS route mutation is authorized by this contract.
- No Netwatch disablement is authorized by this contract.
- No CAKE/qdisc change is authorized by this contract.
- No controller threshold retuning is authorized by this contract.
- Phase 256 deploy/restart must be explicitly operator-approved before execution.
- Any future active mode requires a separate canary approval record and Snapshot-A rollback proof.
