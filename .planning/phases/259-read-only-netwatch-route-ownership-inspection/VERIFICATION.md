# Phase 259 Verification

## Automated phase slice

Command:

```bash
.venv/bin/pytest -o addopts='' tests/test_route_ownership_inspector.py tests/test_route_ownership_inspector_rest.py tests/test_phase259_ownership_proof.py tests/test_health_check.py tests/test_route_ownership_guard.py tests/test_routeros_rest.py tests/test_readonly_validator.py -q
```

Result, 2026-06-25T01:42:55Z:

```text
332 passed in 40.71s
```

Command:

```bash
.venv/bin/ruff check src/wanctl/steering/route_ownership_inspector.py src/wanctl/steering/health.py src/wanctl/steering/daemon.py tests/test_route_ownership_inspector.py tests/test_route_ownership_inspector_rest.py tests/test_phase259_ownership_proof.py tests/test_health_check.py scripts/phase259-ownership-proof.py pyproject.toml
```

Result:

```text
All checks passed!
```

Command:

```bash
git diff --check
```

Result: clean.

## Live proof on cake-shaper

Deployment method: per-file `sudo install` into `/opt/wanctl`, with backup captured at `/opt/wanctl/.phase259-backup-20260625T014037Z`.

Installed files:

- `/opt/wanctl/steering/route_ownership_inspector.py`
- `/opt/wanctl/steering/daemon.py`
- `/opt/wanctl/steering/health.py`
- `/opt/wanctl/scripts/phase259-ownership-proof.py`
- `/etc/wanctl/phase259-readonly-commands.txt` with read-only `COMMAND:` lines only.

Remote compile proof:

```text
py_compile_ok
```

Initial proof attempt without loading `/etc/wanctl/secrets` failed closed with RouterOS REST 401. Retried with the same deployed harness under the service-equivalent secret environment (`/etc/wanctl/secrets`), without printing secret values.

Live verdict:

```text
INSPECT_PROOF_PASS observed_owner=netwatch configured_owner=netwatch match=True netwatch_entries=3 route_mutating_active=4 total_routes=17 default_routes=4
```

## Steering service restart + health proof

Command:

```bash
sudo systemctl restart steering.service
```

Result:

```text
Active: active (running) since Wed 2026-06-24 20:41:46 CDT
Main PID: 704525 (python3)
Tasks: 3
```

Health proof from `http://127.0.0.1:9102/health`:

```text
status=healthy
steering=SPECTRUM_GOOD
ownership_inspection_present=True
observed_owner=netwatch
configured_owner=netwatch
match=True
inspector_status=ok
netwatch_entries=3
route_mutating_active=4
total_routes=17
default_routes=4
route_management_keys=enabled,mode,active_owner,active_allowed,blocked_reason,guard,reconciliation,circuit_breaker,last_intended_action,last_applied_action,rollback_ready,last_event
```

## SAFE-21 notes

- No RouterOS route mutation commands were executed by the harness.
- Proof harness validates read-only commands before any `run_cmd` call; mutation-rejection tests cover the fail-closed path.
- Live mutation performed: `steering.service` restart only, as required to load deployed Python code.
- No CAKE/qdisc change, Netwatch disablement, threshold retuning, or production route-owner flip was performed.
