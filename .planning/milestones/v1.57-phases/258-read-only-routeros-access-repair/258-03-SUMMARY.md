---
phase: 258-read-only-routeros-access-repair
plan: 03
subsystem: routeros-live-proof
status: complete
tags: [wanctl, routeros, proof, read-only, live]
key-files:
  created:
    - .planning/phases/258-read-only-routeros-access-repair/evidence/258-03-readonly-commands.txt
    - scripts/phase258-readonly-proof.py
    - tests/test_phase258_readonly_proof.py
    - .planning/phases/258-read-only-routeros-access-repair/evidence/258-03-access02-proof.md
  modified:
    - pyproject.toml
requirements-completed:
  - ACCESS-02
  - ACCESS-03
  - SAFE-21
completed: 2026-06-20
---

# Phase 258 Plan 03: Live ACCESS-02 Proof Summary

Created and ran the live read-only proof harness through deployed wanctl code on `cake-shaper`. ACCESS-02 is proved: route, Netwatch, and script reads all returned non-empty parseable JSON through `get_router_client` over the real deployed steering config.

## Accomplishments

- Created `258-03-readonly-commands.txt` with the three validated read-only proof commands.
- Created `scripts/phase258-readonly-proof.py`:
  - loads deployed `/etc/wanctl/steering.yaml` via `SteeringConfig(path)`;
  - obtains the RouterOS client through `get_router_client(config, logger)`;
  - asserts `wanctl.__file__` and `routeros_rest.__file__` resolve under `/opt/wanctl`;
  - validates each command through `readonly_validator` before `run_cmd`;
  - parses full JSON and prints counts/redacted samples;
  - emits `ACCESS02_PROOF_PASS route=<n> netwatch=<n> script=<n>`.
- Added `tests/test_phase258_readonly_proof.py` covering the mock happy path and pre-run mutation rejection.
- Added a narrow Ruff per-file N999 ignore for the plan-mandated hyphenated script name.
- Deployed only the two required source files to `/opt/wanctl` with `sudo install` after a broad rsync preview/attempt proved too wide/noisy.
- Ran the live proof with `PYTHONPATH=/opt`, real config, exported `ROUTER_PASSWORD`, and deployed imports.
- Recorded proof evidence in `258-03-access02-proof.md`.

## Task Commits

| Commit | Description |
|--------|-------------|
| `6c71db79` | add read-only RouterOS proof harness, command file, and mocked tests |

## Live Proof Result

```text
wanctl.__file__=/opt/wanctl/__init__.py
routeros_rest.__file__=/opt/wanctl/routeros_rest.py
config=/etc/wanctl/steering.yaml
config_loader=SteeringConfig transport=rest
ACCESS02_PROOF_PASS route=17 netwatch=3 script=20 samples={"netwatch": {".id": "*1", "disabled": "true", "host": "70.123.241.22", "status": "unknown"}, "route": {".id": "*8000002C", "comment": "Spectrum", "disabled": "false", "dst-address": "0.0.0.0/0", "gateway": "70.123.224.1"}, "script": {".id": "*1", "name": "BackupAndUpdate", "source": "<redacted>"}}
```

Deployment confirmation:

```text
grep -c _handle_script_print /opt/wanctl/routeros_rest.py -> 2
/opt/wanctl/readonly_validator.py present
NRestarts=0
ActiveState=active
```

## Verification

- `.venv/bin/python -m wanctl.readonly_validator .planning/phases/258-read-only-routeros-access-repair/evidence/258-03-readonly-commands.txt`
  - `READONLY_COMMANDS_VALIDATED`
- `.venv/bin/pytest -o addopts='' tests/test_phase258_readonly_proof.py -q`
  - `2 passed`
- `.venv/bin/ruff check scripts/phase258-readonly-proof.py tests/test_phase258_readonly_proof.py pyproject.toml`
  - `All checks passed!`
- Static harness gate passed: `get_router_client`, `SteeringConfig`, `/etc/wanctl/steering.yaml`, `/opt/wanctl`, import-path failure, `validate_command`/`iter_commands`, and `run_proof` all present; no `head -c`, no `-u admin:`, no `:$ROUTER_PASSWORD`.
- Evidence grep/negative gate passed for `258-03-access02-proof.md`.
- After code review hardening of the validator prefix boundary, `/opt/wanctl/readonly_validator.py` was redeployed and the live proof was rerun successfully with the same `ACCESS02_PROOF_PASS route=17 netwatch=3 script=20` verdict.
- Combined phase test slice passed:
  - `.venv/bin/pytest -o addopts='' tests/test_routeros_rest.py tests/test_readonly_validator.py tests/test_route_ownership_guard_rest_integration.py tests/test_phase258_readonly_proof.py -q`
  - `116 passed in 0.73s`

## Deviations

- `deploy.sh --dry-run` showed it would also deploy config/systemd assets, which was broader than this plan's code-only proof goal.
- A direct `rsync --delete src/wanctl/ cake-shaper:/opt/wanctl/` was too broad and failed on ownership/permission/pycache state. I stopped using that path and deployed only `routeros_rest.py` and `readonly_validator.py` via temp-copy + `sudo install`.
- The first proof run used `source /etc/wanctl/secrets` without exporting variables; Python config expansion could not see `ROUTER_PASSWORD` and got REST 401. Diagnostic confirmed `set -a` export semantics; rerun succeeded.

## Self-Check: PASSED

- Live proof used deployed `/opt/wanctl` imports.
- Live proof used real `/etc/wanctl/steering.yaml` via `SteeringConfig(path)`.
- Live proof went through `get_router_client`, not raw curl.
- All three reads returned non-empty parseable JSON.
- ACCESS-03 residual is recorded as procedural enforcement, not RBAC.
- SAFE-21 held: no RouterOS mutation, no Netwatch change, no steering restart.
