# Phase 254 Dry-Run Observation Evidence

Captured: 20260620T010412Z

## Command Validation

- validation_artifact: `.planning/phases/254-dry-run-observation-operator-gated-canary-retirement-decisio/evidence/read-only-command-validation-20260620T010314Z.json`
- passed: `true`
- command_count: `7`
- command_file: `.planning/phases/254-dry-run-observation-operator-gated-canary-retirement-decisio/evidence/read-only-commands-20260620T010314Z.txt`

## Issued Commands

```text
COMMAND: /system/identity/print
COMMAND: /tool/netwatch/print detail
COMMAND: /system/script/print detail
COMMAND: /system/script/export hide-sensitive
COMMAND: /ip/route/print detail where dst-address="0.0.0.0/0"
COMMAND: curl -fsS http://127.0.0.1:9102/health
COMMAND: .venv/bin/python -m wanctl.operator_summary http://127.0.0.1:9102/health
```

## Steering Health Route Management

Evidence gap: Health endpoint unavailable or invalid JSON (exit 7): curl: (7) Failed to connect to 127.0.0.1 port 9102 after 0 ms: Couldn't connect to server

Canary progression is blocked until the steering health endpoint exposing `route_management` is reachable from the observation context.

## Operator Summary

Evidence gap: operator summary unavailable (exit 1):

```text
<urlopen error [Errno 111] Connection refused>

```

## RouterOS Read-Only Inventory

Read-only wrapper artifacts:



Command results:

- `/system/identity/print` -> exit `4`
- `/tool/netwatch/print detail` -> exit `4`
- `/system/script/print detail` -> exit `4`
- `/system/script/export hide-sensitive` -> exit `4`
- `/ip/route/print detail where dst-address="0.0.0.0/0"` -> exit `4`
- `curl -fsS http://127.0.0.1:9102/health` -> exit `7`
- `.venv/bin/python -m wanctl.operator_summary http://127.0.0.1:9102/health` -> exit `1`


Relevant sanitized summary lines from artifacts:

## Snapshot-A Drift Check

- status: `blocked-no-routeros-artifacts`
- Snapshot-A: `.planning/phases/251-route-ownership-decision-read-only-inventory/evidence/snapshot-a-20260619T225607Z.json`

RouterOS read-only artifacts were not produced; canary approval is blocked.

## No-Mutation Proof

The scan below inspected only issued command lines prefixed with `COMMAND:`. Raw RouterOS output was not scanned for mutation tokens.


- passed: `true`

- mutation_hits: `[]`


## Raw Command Execution Summary


### COMMAND: /system/identity/print

- kind: `routeros`
- exit: `4`


stdout tail:
```text

PLAY [Run a read-only network device command] **********************************

```


stderr tail:
```text
ERROR! Attempting to decrypt but no vault secrets found

```


### COMMAND: /tool/netwatch/print detail

- kind: `routeros`
- exit: `4`


stdout tail:
```text

PLAY [Run a read-only network device command] **********************************

```


stderr tail:
```text
ERROR! Attempting to decrypt but no vault secrets found

```


### COMMAND: /system/script/print detail

- kind: `routeros`
- exit: `4`


stdout tail:
```text

PLAY [Run a read-only network device command] **********************************

```


stderr tail:
```text
ERROR! Attempting to decrypt but no vault secrets found

```


### COMMAND: /system/script/export hide-sensitive

- kind: `routeros`
- exit: `4`


stdout tail:
```text

PLAY [Run a read-only network device command] **********************************

```


stderr tail:
```text
ERROR! Attempting to decrypt but no vault secrets found

```


### COMMAND: /ip/route/print detail where dst-address="0.0.0.0/0"

- kind: `routeros`
- exit: `4`


stdout tail:
```text

PLAY [Run a read-only network device command] **********************************

```


stderr tail:
```text
ERROR! Attempting to decrypt but no vault secrets found

```


### COMMAND: curl -fsS http://127.0.0.1:9102/health

- kind: `local`
- exit: `7`


stderr tail:
```text
curl: (7) Failed to connect to 127.0.0.1 port 9102 after 0 ms: Couldn't connect to server

```


### COMMAND: .venv/bin/python -m wanctl.operator_summary http://127.0.0.1:9102/health

- kind: `local`
- exit: `1`


stderr tail:
```text
<urlopen error [Errno 111] Connection refused>

```
