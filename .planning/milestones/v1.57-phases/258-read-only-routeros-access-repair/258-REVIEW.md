---
phase: 258-read-only-routeros-access-repair
status: clean
reviewed: 2026-06-20
scope:
  - src/wanctl/routeros_rest.py
  - src/wanctl/readonly_validator.py
  - scripts/phase258-readonly-proof.py
  - tests/test_routeros_rest.py
  - tests/test_readonly_validator.py
  - tests/test_route_ownership_guard_rest_integration.py
  - tests/test_phase258_readonly_proof.py
  - pyproject.toml
---

# Phase 258 Code Review

## Verdict

Clean after one local hardening fix.

The advisory subagent review returned several unverified/inaccurate claims (for example: hardcoded credentials in `phase258-readonly-proof.py`, duplicate `pyproject.toml` sections, and missing timeouts in a non-existent `execute_command` path). Those were checked against the actual diff and not accepted as findings.

## Findings

### Critical

None.

### Warning

- Validator prefix boundary was too permissive: the first implementation used `startswith` directly, which would accept strings such as `/ip route printfoo`. Fixed by adding `_starts_with_read_object()` so the allowed read-object prefix must be followed by end-of-string, a space, or `/`. Added regression coverage in `tests/test_readonly_validator.py`.

### Info

- `scripts/phase258-readonly-proof.py` has a hyphenated filename because the plan requires that operator-facing harness name. This matches existing repo precedent for phase scripts; `pyproject.toml` now has a narrow per-file `N999` ignore.
- The proof harness intentionally runs with privileged file-read access on `cake-shaper` to load `/etc/wanctl/steering.yaml` and `/etc/wanctl/secrets`, but it does not place the password on the command line or print it. The successful run required `set -a` so Python could see `ROUTER_PASSWORD` in `os.environ`.

## Safety review

- New RouterOSREST handlers are GET-only:
  - `/rest/tool/netwatch`
  - `/rest/system/script`
- No RouterOS mutation handlers were added.
- The validator rejects mutating verbs, shell metacharacters, unknown objects, embedded-substring bypasses, and now prefix-boundary bypasses.
- The live proof went through deployed `/opt/wanctl`, real `/etc/wanctl/steering.yaml`, `SteeringConfig(path)`, and `get_router_client`.
- `steering.service` was not restarted (`NRestarts=0`).

## Verification

- `.venv/bin/pytest -o addopts='' tests/test_routeros_rest.py tests/test_readonly_validator.py tests/test_route_ownership_guard_rest_integration.py tests/test_phase258_readonly_proof.py -q` passed.
- `.venv/bin/pytest -o addopts='' tests/test_route_ownership_guard.py tests/test_route_manager.py -q` passed.
- `.venv/bin/ruff check ...` passed for changed source/test/script files.
- `.venv/bin/mypy src/wanctl/routeros_rest.py src/wanctl/readonly_validator.py` passed.
- `.venv/bin/python -m wanctl.readonly_validator --self-test` passed.
- Live proof after validator redeploy passed: `ACCESS02_PROOF_PASS route=17 netwatch=3 script=20`.
