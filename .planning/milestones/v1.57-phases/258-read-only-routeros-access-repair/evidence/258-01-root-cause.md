# Phase 258-01 ACCESS-01 Root Cause

## Verdict

The v1.56 `not-ready` blocker is two distinct broken layers, not one:

1. Daemon path: production steering uses the RouterOS REST client, and that client can read routes but does not currently handle the two additional read objects required by `RouteOwnershipGuard`: `/tool netwatch print detail` and `/system script print detail`.
2. Manual evidence path: the v1.56 operator evidence command used nested SSH with `/etc/wanctl/ssh/router.key` and failed with returncode 255 because that key path was inaccessible from `cake-shaper` for that evidence path.

The daemon-path REST gap is the real inspection blocker for the running steering service. Repairing only `router.key` would not clear the daemon guard path.

## Daemon path: REST guard read fails closed

Live deployed steering service evidence from `cake-shaper`:

- `systemctl show steering.service --property=ExecStart --property=User --property=Environment --no-pager` returned `ExecStart=/usr/bin/python3 -m wanctl.steering.daemon --config /etc/wanctl/steering.yaml`.
- The same output showed `User=wanctl` and `Environment=PYTHONPATH=/opt WANCTL_STATE_DIR=/var/lib/wanctl WANCTL_LOG_DIR=/var/log/wanctl WANCTL_RUN_DIR=/run/wanctl`.
- A direct nonprivileged read of `/etc/wanctl/steering.yaml` from this agent session returned `Permission denied`, so the exact live `transport:` value remains [OPERATOR-VERIFY]. The service path and prior v1.56 evidence still show this is the deployed steering config that must be verified live, not inferred from repo defaults.

Repo code confirms why the daemon path fails today:

- `src/wanctl/routeros_rest.py::_execute_single_command` dispatches `/ip route print` to `_handle_route_print`, but has no `/tool netwatch print` branch and no `/system script print` branch.
- Unsupported commands fall through to `self.logger.warning(f"Unsupported command for REST API: {cmd}")` and return `None`.
- `RouterOSREST.run_cmd()` turns a `None` handler result into `(1, "", "Command failed")`.
- `src/wanctl/steering/route_ownership_guard.py::inspect()` reads `NETWATCH_PRINT = "/tool netwatch print detail"` first and then `SCRIPT_PRINT = "/system script print detail"`.
- Each read goes through `_read_json_list`; any non-zero rc returns `RouteOwnershipGuardResult(status="error", active_allowed=False, owner="unknown")`.

Therefore adding only a netwatch handler is insufficient. It would move the failure from "failed to read RouterOS netwatch: Command failed" to "failed to read RouterOS script: Command failed". Both `_handle_netwatch_print` and `_handle_script_print` are required to clear the guard path.

The Phase 257 summary records the observed daemon symptom: route-management health stayed dry-run-only with `guard.status=error`, `reconciliation.status=ok`, `active_owner=netwatch`, and `active_allowed=false`.

## Manual evidence path: SSH key failure is parallel and now avoidable

The Phase 257 operator inventory path was a nested SSH evidence command using `/etc/wanctl/ssh/router.key` on `cake-shaper` to ask RouterOS for Netwatch state. That failed with returncode 255.

That SSH-key failure is real, but it is not how the steering daemon talks to RouterOS in the current selected path. It is a parallel manual-evidence surface. If REST is confirmed viable by A1, the SSH-key repair is dropped for this phase per D1. `router.key` can remain a configured SSH-fallback credential, but it is not the read-only inspection path being repaired here.

## ACCESS-01 credential fact split

### Known from evidence

- The configured SSH fallback/evidence key path is `/etc/wanctl/ssh/router.key`.
- The Phase 257 nested-SSH evidence path failed with returncode 255.
- The Phase 257 readiness packet stayed `not-ready`; Netwatch remained owner and no active canary was approved.
- The steering service is launched on `cake-shaper` as `wanctl` via `/usr/bin/python3 -m wanctl.steering.daemon --config /etc/wanctl/steering.yaml` with `PYTHONPATH=/opt`.
- The daemon REST client has route-print support but lacks netwatch and script print support.

### Operator-pending (live-only)

- [OPERATOR-VERIFY] Deployed steering config values from `/etc/wanctl/steering.yaml`: `transport`, `host`, `port`, and `verify_ssl`. Suggested read-only command: `! ssh cake-shaper 'sudo grep -E "^\s*(transport|host|port|verify_ssl):" /etc/wanctl/steering.yaml'`.
- [OPERATOR-VERIFY] `/etc/wanctl/secrets` readability by the service/proof path and presence of `ROUTER_PASSWORD` without printing its value. Suggested read-only command: `! ssh cake-shaper 'sudo test -r /etc/wanctl/secrets && echo SECRETS_READABLE; sudo grep -c ROUTER_PASSWORD /etc/wanctl/secrets'`.
- [OPERATOR-VERIFY] `/etc/wanctl/ssh/router.key` presence, owner, group, and mode. Suggested read-only command: `! ssh cake-shaper 'sudo ls -l /etc/wanctl/ssh/router.key 2>&1; sudo stat -c "%U %G %a" /etc/wanctl/ssh/router.key 2>&1'`.

ACCESS-01 is not fully closed until each operator-pending field is filled or formally scoped non-blocking. Because D1 drops `router.key` as the inspection path when REST is confirmed, its owner/mode facts are non-blocking for the REST repair path, but they should remain documented as the v1.56 manual-evidence failure surface.

## Chosen supported path

The chosen supported path is to keep the steering REST transport and add read-only GET handlers in `RouterOSREST` for:

- `/tool netwatch print` via `GET /rest/tool/netwatch`
- `/system script print` via `GET /rest/system/script`

This fixes the daemon-path blocker. A `router.key` chmod/chown alone would not fix the running guard path because `RouteOwnershipGuard.inspect()` would still hit missing REST handlers.

## A1 preflight dependency

A1 asks whether the live RouterOS exposes `/rest/tool/netwatch`. The agent-side nonprivileged probe could not resolve A1 because `/etc/wanctl/secrets` was not readable and the REST GETs returned 401. That is a credential-read limitation of this session, not proof that RouterOS lacks the endpoint.

A1 remains a blocking operator checkpoint before Plan 02. If the operator run returns `A1-confirmed`, proceed to Plan 02. If it returns `A1-failed` because the REST netwatch endpoint is absent, stop this phase and write a separate SSH fallback phase per D1; do not improvise SSH inside Plan 03.

## SAFE-21 / negative-content check

This document records evidence and proposed read-only checks only. It contains no secret values and no key material. The selected implementation path is read-only GET for netwatch and script inspection, plus command-file validation before live proof commands.
