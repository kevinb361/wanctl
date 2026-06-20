# Phase 258-03 ACCESS-02 Live Proof Evidence

## Verdict

ACCESS-02 PROVED.

The live proof ran through wanctl's supported RouterOS client path against deployed code on `cake-shaper`, loaded the real deployed steering config, validated each command through `readonly_validator`, and returned non-empty parseable JSON for all three required reads:

- `/ip route print`
- `/tool netwatch print`
- `/system script print`

## A1 provenance

A1 was resolved in Plan 01 and recorded in `258-01-a1-preflight.md`:

```text
A1-NETWATCH-OK entries=3
A1-SCRIPT-OK entries=20
```

No SSH fallback fork was used.

## Deployed-code confirmation

The first broad rsync attempt was intentionally abandoned after it tried to touch wider `/opt/wanctl` ownership/pycache state and failed with permission errors. The actual deploy was narrowed to only the two files required by this proof:

- `/opt/wanctl/routeros_rest.py`
- `/opt/wanctl/readonly_validator.py`

Deployment command shape:

```text
scp src/wanctl/routeros_rest.py src/wanctl/readonly_validator.py cake-shaper:/tmp/
ssh cake-shaper 'sudo install -o root -g root -m 0644 /tmp/routeros_rest.py /opt/wanctl/routeros_rest.py && sudo install -o root -g root -m 0644 /tmp/readonly_validator.py /opt/wanctl/readonly_validator.py && grep -c _handle_script_print /opt/wanctl/routeros_rest.py && test -f /opt/wanctl/readonly_validator.py && echo DEPLOYED_TARGETED_FILES'
```

Confirmation output:

```text
2
DEPLOYED_TARGETED_FILES
```

Post-proof deployed state check:

```text
NRestarts=0
ExecMainStartTimestamp=Fri 2026-06-19 22:42:33 CDT
ActiveState=active
2
readonly_validator_present
```

No `steering.service` restart occurred.

## Transport, import-path, and real-config provenance

The proof harness was staged to `/tmp/phase258-readonly-proof.py` and run from `/opt/wanctl` with `PYTHONPATH=/opt`. It printed the deployed import paths:

```text
wanctl.__file__=/opt/wanctl/__init__.py
routeros_rest.__file__=/opt/wanctl/routeros_rest.py
config=/etc/wanctl/steering.yaml
config_loader=SteeringConfig transport=rest
```

This proves the proof used the deployed `/opt/wanctl` package, not the repo checkout or a stray copy. It loaded the real deployed `/etc/wanctl/steering.yaml` through `SteeringConfig(path)` and obtained the RouterOS client through `get_router_client(config, logger)`, not raw curl or a bespoke client.

Credential-loading note: the first harness run used `source /etc/wanctl/secrets` without export and failed with REST 401 because Python `${ROUTER_PASSWORD}` expansion reads `os.environ`. A diagnostic confirmed `set -a; source /etc/wanctl/secrets; set +a` exports the variable without printing it. The successful proof used that export form.

After the code-review hardening pass added an explicit allowed-prefix boundary to `readonly_validator`, `/opt/wanctl/readonly_validator.py` was redeployed and the proof was rerun. It again returned `ACCESS02_PROOF_PASS route=17 netwatch=3 script=20`.

## Validated command file

Command file: `.planning/phases/258-read-only-routeros-access-repair/evidence/258-03-readonly-commands.txt`

Validation output:

```text
READONLY_COMMANDS_VALIDATED
```

Commands:

```text
COMMAND: /ip route print
COMMAND: /tool netwatch print
COMMAND: /system script print
```

## Live proof output

Successful proof verdict:

```text
ACCESS02_PROOF_PASS route=17 netwatch=3 script=20 samples={"netwatch": {".id": "*1", "disabled": "true", "host": "70.123.241.22", "status": "unknown"}, "route": {".id": "*8000002C", "comment": "Spectrum", "disabled": "false", "dst-address": "0.0.0.0/0", "gateway": "70.123.224.1"}, "script": {".id": "*1", "name": "BackupAndUpdate", "source": "<redacted>"}}
```

Counts:

- route: 17
- netwatch: 3
- script: 20

All outputs were full JSON parsed by the harness before the verdict. Script source was redacted in the recorded sample.

## ACCESS-03 residual

ACCESS-03 is enforced procedurally, not by RouterOS RBAC. The reused steering credential can write at the RouterOS permission layer. The mitigations in this phase are:

- transport handlers added by Plan 02 are GET-only for netwatch and script reads;
- the live proof command file is validated by `readonly_validator` before execution;
- `readonly_validator` rejects mutating verbs, shell metacharacters, unknown objects, and embedded-substring bypasses.

This residual is accepted by D2 and remains explicit for later phases.

## SAFE-21

SAFE-21 held:

- no RouterOS route mutation;
- no Netwatch disablement or change;
- no CAKE/qdisc change;
- no threshold retuning;
- no production default route-owner flip;
- no `steering.service` restart.
