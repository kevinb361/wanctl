# Phase 258-01 A1 Preflight

## Status

A1-confirmed

## What A1 checks

A1 is the blocking preflight for Phase 258: does the live RouterOS at `10.10.99.1` expose `/rest/tool/netwatch` as a readable REST GET endpoint from `cake-shaper` using the steering credential path?

This must be resolved before Plan 02 code is written. If A1 is confirmed, Plan 02 proceeds with REST netwatch and script read handlers. If A1 fails because the REST netwatch endpoint is absent, this phase stops and a separate SSH fallback phase is planned; SSH is not improvised inside Plan 03.

## Agent-side read-only attempt

The agent ran only read-only checks:

- `ssh cake-shaper 'grep -E "^\s*(transport|host|port|verify_ssl):" /etc/wanctl/steering.yaml; systemctl show steering.service --property=ExecStart --property=User --property=Environment --no-pager'`
- `ssh cake-shaper 'source /etc/wanctl/secrets; curl -fsS -k --netrc-file <(...) https://10.10.99.1/rest/tool/netwatch ...; curl -fsS -k --netrc-file <(...) https://10.10.99.1/rest/system/script ...'`

Observed output:

```text
grep: /etc/wanctl/steering.yaml: Permission denied
ExecStart={ path=/usr/bin/python3 ; argv[]=/usr/bin/python3 -m wanctl.steering.daemon --config /etc/wanctl/steering.yaml ; ... }
Environment=PYTHONPATH=/opt WANCTL_STATE_DIR=/var/lib/wanctl WANCTL_LOG_DIR=/var/log/wanctl WANCTL_RUN_DIR=/run/wanctl
User=wanctl
bash: line 1: /etc/wanctl/secrets: Permission denied
curl: (22) The requested URL returned error: 401
curl: (22) The requested URL returned error: 401
A1-NETWATCH-FAIL rc=22
A1-SCRIPT-FAIL rc=22
```

Interpretation: this is not an A1 endpoint failure. The agent session could not read the deployed config or secret nonprivileged, so REST auth failed with 401. The preflight remains blocked on the operator-at-keyboard privileged read-only command required by D3.

## Required operator command

Run this read-only command from the workstation. It sources the password on `cake-shaper`, passes it through a netrc fd, prints counts only, removes temp files, and does not mutate RouterOS:

```bash
ssh cake-shaper 'source /etc/wanctl/secrets; tmpn=$(mktemp); tmps=$(mktemp); rc_n=0; rc_s=0; curl -fsS -k --netrc-file <(printf "machine 10.10.99.1 login admin password %s\n" "$ROUTER_PASSWORD") https://10.10.99.1/rest/tool/netwatch >"$tmpn" || rc_n=$?; curl -fsS -k --netrc-file <(printf "machine 10.10.99.1 login admin password %s\n" "$ROUTER_PASSWORD") https://10.10.99.1/rest/system/script >"$tmps" || rc_s=$?; python3 - "$tmpn" "$tmps" "$rc_n" "$rc_s" <<"PY"
import json, sys
netwatch_path, script_path, rc_n, rc_s = sys.argv[1:5]
if rc_n != "0":
    print(f"A1-NETWATCH-FAIL rc={rc_n}")
else:
    data = json.load(open(netwatch_path))
    print(f"A1-NETWATCH-OK entries={len(data)}")
if rc_s != "0":
    print(f"A1-SCRIPT-FAIL rc={rc_s}")
else:
    data = json.load(open(script_path))
    print(f"A1-SCRIPT-OK entries={len(data)}")
PY
rm -f "$tmpn" "$tmps"'
```

## Decision rules

- A1-confirmed: `A1-NETWATCH-OK entries=<N>` with parseable JSON. Proceed to Plan 02. Script endpoint count should also be recorded because Plan 02/259 require the guard's script read.
- A1-failed: netwatch endpoint returns 404 or other endpoint absence after valid auth. STOP — REST netwatch endpoint absent; write a separate SSH fallback phase per D1; do not improvise SSH inside Plan 03.
- A1-blocked: auth/config/permission issue prevents the GET from reaching RouterOS with valid credentials. Resolve the operator environment first; do not treat this as endpoint absence.

## Operator-confirmed result

After explicit operator approval, the privileged read-only probe was rerun through `sudo bash -s` on `cake-shaper` so `/etc/wanctl/secrets` could be sourced without printing the secret value. The RouterOS REST GETs returned parseable JSON counts:

```text
A1-NETWATCH-OK entries=3
A1-SCRIPT-OK entries=20
```

## Current decision

A1-confirmed. Proceed to Plan 02 with the REST netwatch + script handler implementation. The SSH fallback fork is not used.
