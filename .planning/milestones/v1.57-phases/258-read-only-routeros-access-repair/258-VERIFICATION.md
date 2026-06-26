---
phase: 258-read-only-routeros-access-repair
status: passed
verified: 2026-06-20
requirements:
  ACCESS-01: passed
  ACCESS-02: passed
  ACCESS-03: passed
  SAFE-21: passed
---

# Phase 258 Verification

## Verdict

Passed.

Phase 258 achieved its goal: `cake-shaper` now has a supported read-only RouterOS inspection path through wanctl's REST transport, and the path was proven live through deployed `/opt/wanctl` code, real `/etc/wanctl/steering.yaml`, `SteeringConfig(path)`, and `get_router_client`.

## Requirement verification

| Requirement | Status | Evidence |
|-------------|--------|----------|
| ACCESS-01 | Passed | `evidence/258-01-root-cause.md` documents the two failure layers: daemon REST handler gap (`/tool netwatch` + `/system script`) and manual nested-SSH `router.key` returncode 255. `evidence/258-01-a1-preflight.md` records A1-confirmed. |
| ACCESS-02 | Passed | `src/wanctl/routeros_rest.py` has GET-only `_handle_netwatch_print` and `_handle_script_print` handlers and dispatch branches. Live proof returned `ACCESS02_PROOF_PASS route=17 netwatch=3 script=20` through deployed `/opt/wanctl` imports and `get_router_client`. |
| ACCESS-03 | Passed with explicit residual | `src/wanctl/readonly_validator.py` validates route/netwatch/script read commands and rejects mutating verbs, shell metacharacters, unknown objects, embedded-substring bypasses, and prefix-boundary bypasses. Residual is explicit: reused steering credential can write at RouterOS RBAC; read-only is procedural via GET-only handlers + validator. |
| SAFE-21 | Passed | Live work used read-only REST GETs and code install only. No RouterOS route mutation, Netwatch change, CAKE/qdisc change, threshold retuning, route-owner flip, or `steering.service` restart. Post-proof `NRestarts=0`, `ActiveState=active`. |

## Automated checks

```text
.venv/bin/pytest -o addopts='' tests/test_routeros_rest.py tests/test_readonly_validator.py tests/test_route_ownership_guard_rest_integration.py tests/test_phase258_readonly_proof.py tests/test_route_ownership_guard.py tests/test_route_manager.py -q
134 passed in 0.76s
```

```text
.venv/bin/ruff check src/wanctl/routeros_rest.py src/wanctl/readonly_validator.py scripts/phase258-readonly-proof.py tests/test_routeros_rest.py tests/test_readonly_validator.py tests/test_route_ownership_guard_rest_integration.py tests/test_phase258_readonly_proof.py
All checks passed!
```

```text
.venv/bin/mypy src/wanctl/routeros_rest.py src/wanctl/readonly_validator.py
Success: no issues found in 2 source files
```

```text
.venv/bin/python -m wanctl.readonly_validator .planning/phases/258-read-only-routeros-access-repair/evidence/258-03-readonly-commands.txt
READONLY_COMMANDS_VALIDATED
```

```text
.venv/bin/python -m wanctl.readonly_validator --self-test
READONLY_COMMANDS_NEGATIVE_SELF_TEST_PASSED
```

## Live proof

Deployed-code/import/config provenance:

```text
wanctl.__file__=/opt/wanctl/__init__.py
routeros_rest.__file__=/opt/wanctl/routeros_rest.py
config=/etc/wanctl/steering.yaml
config_loader=SteeringConfig transport=rest
```

Proof verdict:

```text
ACCESS02_PROOF_PASS route=17 netwatch=3 script=20
```

Deployment/no-restart check:

```text
grep -c _handle_script_print /opt/wanctl/routeros_rest.py -> 2
/opt/wanctl/readonly_validator.py present
NRestarts=0
ActiveState=active
```

## Code review

`258-REVIEW.md` status: clean.

One warning found and fixed during review: validator prefix matching now requires a boundary after the read-object prefix, preventing `/ip route printfoo` style acceptance.

## Notes / deviations

- `deploy.sh --dry-run` showed config/systemd deployment in addition to source code, so the actual deployment used targeted `sudo install` for only `routeros_rest.py` and `readonly_validator.py`.
- A broad direct rsync was too wide and hit `/opt/wanctl` ownership/pycache permission errors; it was abandoned in favor of targeted install.
- The harness requires exported `ROUTER_PASSWORD`; using `source /etc/wanctl/secrets` alone was insufficient for Python `os.environ`. The successful proof used `set -a; source /etc/wanctl/secrets; set +a` without printing the value.

## Result

Phase 258 is complete and unblocks Phase 259: read-only Netwatch + route-ownership inspection can now use the validated REST path.
