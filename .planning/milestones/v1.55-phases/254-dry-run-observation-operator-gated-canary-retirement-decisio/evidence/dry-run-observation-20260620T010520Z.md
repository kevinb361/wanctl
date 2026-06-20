# Phase 254 Dry-Run Observation Evidence

Captured: 20260620T010520Z

## Command Validation

- validation_artifact: `.planning/phases/254-dry-run-observation-operator-gated-canary-retirement-decisio/evidence/read-only-command-validation-20260620T010314Z.json`
- passed: `true`
- command_count: `7`
- command_file: `.planning/phases/254-dry-run-observation-operator-gated-canary-retirement-decisio/evidence/read-only-commands-20260620T010314Z.txt`
- retry_note: first wrapper attempt lacked Ansible vault secrets; this artifact reran the same validated logical commands with `--vault-password-file .vault_pass`.

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

- `/home/kevin/projects/infra-ansible/artifacts/network-readonly/20260619_200521/main-router__phase254_20260620T010520Z_cmd01.txt`
- `/home/kevin/projects/infra-ansible/artifacts/network-readonly/20260619_200523/main-router__phase254_20260620T010520Z_cmd02.txt`
- `/home/kevin/projects/infra-ansible/artifacts/network-readonly/20260619_200524/main-router__phase254_20260620T010520Z_cmd03.txt`
- `/home/kevin/projects/infra-ansible/artifacts/network-readonly/20260619_200526/main-router__phase254_20260620T010520Z_cmd04.txt`
- `/home/kevin/projects/infra-ansible/artifacts/network-readonly/20260619_200528/main-router__phase254_20260620T010520Z_cmd05.txt`


Command results:
- `/system/identity/print` -> exit `0`
- `/tool/netwatch/print detail` -> exit `0`
- `/system/script/print detail` -> exit `0`
- `/system/script/export hide-sensitive` -> exit `0`
- `/ip/route/print detail where dst-address="0.0.0.0/0"` -> exit `0`
- `curl -fsS http://127.0.0.1:9102/health` -> exit `7`
- `.venv/bin/python -m wanctl.operator_summary http://127.0.0.1:9102/health` -> exit `1`


Relevant sanitized summary lines from artifacts:

### `/home/kevin/projects/infra-ansible/artifacts/network-readonly/20260619_200521/main-router__phase254_20260620T010520Z_cmd01.txt`

```text
  name: KEV_RO_OFFICE
```


### `/home/kevin/projects/infra-ansible/artifacts/network-readonly/20260619_200523/main-router__phase254_20260620T010520Z_cmd02.txt`

```text
[no lightweight summary lines extracted; inspect artifact]
```


### `/home/kevin/projects/infra-ansible/artifacts/network-readonly/20260619_200524/main-router__phase254_20260620T010520Z_cmd03.txt`

```text
 0   name="BackupAndUpdate" owner="admin"
           /system backup save dont-encrypt=yes name=$backupName
 1   name="HostDown" owner="admin"
 2   name="HostUp" owner="admin"
 3   name="wan-latency-test" owner="admin" policy=read,write,test
 4   name="fetch_att_modem" owner="admin"
 5   name="test_att_tcp" owner="admin"
 6   name="test_spectrum_latency" owner="admin"
 7   name="test_att_latency" owner="admin"
 8   name="temp_export_1765055007" owner="admin"
 9   name="qos-dashboard" owner="admin" policy=read,policy,test
10   name="qos-dashboard-2" owner="admin"
11   name="blizzard-update" owner="admin"
                       /ip firewall address-list add list=$targetList address=$resolved timeout=12h comment=("dyn-" . $d)
                   /ip firewall address-list add list=$targetList address=$net timeout=30d comment="blizzard-range"
12   name="steam-update" owner="admin"
                       /ip firewall address-list add list=$targetList address=$resolved timeout=12h comment=("dyn-" . $d)
                   /ip firewall address-list add list=$targetList address=$addr timeout=30d comment="valve-range"
13   name="script1" owner="admin"
14   name="Disable-Spectrum" owner="admin" policy=read,write,test
       /ip route disable [find comment="Spectrum"]
15   name="Enable-Spectrum" owner="admin" policy=read,write,test
       /ip route enable [find comment="Spectrum"]
16   name="Disable-ATT" owner="admin" policy=read,write,test
       /ip route disable [find comment="ATT"]
       /ip route disable [find comment="Force ATT_OUT to ATT WAN"]
17   name="Enable-ATT" owner="admin" policy=read,write,test
       /ip route enable [find comment="ATT"]
       /ip route enable [find comment="Force ATT_OUT to ATT WAN"]
18   name="game-qos-engine" owner="ai-operator" policy=read,write,test
                                                       /ip firewall address-list add list=$learnList address=$dst timeout=$learnTTL comment="auto-game-detect"
                                                           /ip firewall address-list add list=$promoteList address=$dst timeout=$promoteTTL comment="promoted-game-server"
19   name="test-valid" owner="admin"
```


### `/home/kevin/projects/infra-ansible/artifacts/network-readonly/20260619_200526/main-router__phase254_20260620T010520Z_cmd04.txt`

```text
add dont-require-permissions=no name=BackupAndUpdate owner=admin policy=\
    \n    /system backup save dont-encrypt=yes name=\$backupName\
add dont-require-permissions=yes name=HostDown owner=admin policy=\
add dont-require-permissions=yes name=HostUp owner=admin policy=\
add dont-require-permissions=no name=wan-latency-test owner=admin policy=\
add dont-require-permissions=no name=fetch_att_modem owner=admin policy=\
add dont-require-permissions=no name=test_att_tcp owner=admin policy=\
add dont-require-permissions=no name=test_spectrum_latency owner=admin \
add dont-require-permissions=no name=test_att_latency owner=admin policy=\
add dont-require-permissions=no name=temp_export_1765055007 owner=admin \
add dont-require-permissions=no name=qos-dashboard owner=admin policy=\
add dont-require-permissions=no name=qos-dashboard-2 owner=admin policy=\
add dont-require-permissions=no name=blizzard-update owner=admin policy=\
    \$resolved timeout=12h comment=(\"dyn-\" . \$d)\
    t timeout=30d comment=\"blizzard-range\"\
add dont-require-permissions=no name=steam-update owner=admin policy=\
    \$resolved timeout=12h comment=(\"dyn-\" . \$d)\
    dr timeout=30d comment=\"valve-range\"\
add dont-require-permissions=no name=script1 owner=admin policy=\
add dont-require-permissions=no name=Disable-Spectrum owner=admin policy=\
    \n/ip route disable [find comment=\"Spectrum\"]\
add dont-require-permissions=no name=Enable-Spectrum owner=admin policy=\
    \n/ip route enable [find comment=\"Spectrum\"]\
add dont-require-permissions=no name=Disable-ATT owner=admin policy=\
    \n/ip route disable [find comment=\"ATT\"]\
    \n/ip route disable [find comment=\"Force ATT_OUT to ATT WAN\"]\
add dont-require-permissions=no name=Enable-ATT owner=admin policy=\
    \n/ip route enable [find comment=\"ATT\"]\
    \n/ip route enable [find comment=\"Force ATT_OUT to ATT WAN\"]\
add dont-require-permissions=no name=game-qos-engine owner=ai-operator \
    t add list=\$learnList address=\$dst timeout=\$learnTTL comment=\"auto-gam\
    -list add list=\$promoteList address=\$dst timeout=\$promoteTTL comment=\"\
add dont-require-permissions=no name=test-valid owner=admin policy=\
```


### `/home/kevin/projects/infra-ansible/artifacts/network-readonly/20260619_200528/main-router__phase254_20260620T010520Z_cmd05.txt`

```text
[no lightweight summary lines extracted; inspect artifact]
```

## Snapshot-A Drift Check

- status: `needs-human-review`
- Snapshot-A: `.planning/phases/251-route-ownership-decision-read-only-inventory/evidence/snapshot-a-20260619T225607Z.json`

Expected Netwatch names found: []. Expected route script names found: ['Disable-ATT', 'Disable-Spectrum', 'Enable-ATT', 'Enable-Spectrum']. Raw read-only artifacts: ['/home/kevin/projects/infra-ansible/artifacts/network-readonly/20260619_200521/main-router__phase254_20260620T010520Z_cmd01.txt', '/home/kevin/projects/infra-ansible/artifacts/network-readonly/20260619_200523/main-router__phase254_20260620T010520Z_cmd02.txt', '/home/kevin/projects/infra-ansible/artifacts/network-readonly/20260619_200524/main-router__phase254_20260620T010520Z_cmd03.txt', '/home/kevin/projects/infra-ansible/artifacts/network-readonly/20260619_200526/main-router__phase254_20260620T010520Z_cmd04.txt', '/home/kevin/projects/infra-ansible/artifacts/network-readonly/20260619_200528/main-router__phase254_20260620T010520Z_cmd05.txt']
Lightweight parser did not identify every expected name; inspect raw artifacts before canary.

## No-Mutation Proof

The scan below inspected only issued command lines prefixed with `COMMAND:`. Raw RouterOS output was not scanned for mutation tokens.


- passed: `true`

- mutation_hits: `[]`


## Raw Command Execution Summary


### COMMAND: /system/identity/print

- kind: `routeros`
- exit: `0`


stdout tail:
```text

PLAY [Run a read-only network device command] **********************************

TASK [Require an explicit read-only command] ***********************************
ok: [main-router] => {
    "changed": false,
    "msg": "All assertions passed"
}

TASK [Detect network device platform] ******************************************
ok: [main-router]

TASK [Select read-only credentials without logging secrets] ********************
ok: [main-router]

TASK [Require read-only credentials] *******************************************
ok: [main-router]

TASK [Run read-only network wrapper] *******************************************
ok: [main-router]

TASK [Report artifact path] ****************************************************
ok: [main-router] => {
    "msg": {
        "host": "main-router",
        "output_dir": "/home/kevin/projects/infra-ansible/playbooks/network/../../artifacts/network-readonly/20260619_200522",
        "output_suffix": "phase254_20260620T010520Z_cmd01",
        "platform": "mikrotik"
    }
}

PLAY RECAP *********************************************************************
main-router                : ok=6    changed=0    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0


```


### COMMAND: /tool/netwatch/print detail

- kind: `routeros`
- exit: `0`


stdout tail:
```text

PLAY [Run a read-only network device command] **********************************

TASK [Require an explicit read-only command] ***********************************
ok: [main-router] => {
    "changed": false,
    "msg": "All assertions passed"
}

TASK [Detect network device platform] ******************************************
ok: [main-router]

TASK [Select read-only credentials without logging secrets] ********************
ok: [main-router]

TASK [Require read-only credentials] *******************************************
ok: [main-router]

TASK [Run read-only network wrapper] *******************************************
ok: [main-router]

TASK [Report artifact path] ****************************************************
ok: [main-router] => {
    "msg": {
        "host": "main-router",
        "output_dir": "/home/kevin/projects/infra-ansible/playbooks/network/../../artifacts/network-readonly/20260619_200524",
        "output_suffix": "phase254_20260620T010520Z_cmd02",
        "platform": "mikrotik"
    }
}

PLAY RECAP *********************************************************************
main-router                : ok=6    changed=0    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0


```


### COMMAND: /system/script/print detail

- kind: `routeros`
- exit: `0`


stdout tail:
```text

PLAY [Run a read-only network device command] **********************************

TASK [Require an explicit read-only command] ***********************************
ok: [main-router] => {
    "changed": false,
    "msg": "All assertions passed"
}

TASK [Detect network device platform] ******************************************
ok: [main-router]

TASK [Select read-only credentials without logging secrets] ********************
ok: [main-router]

TASK [Require read-only credentials] *******************************************
ok: [main-router]

TASK [Run read-only network wrapper] *******************************************
ok: [main-router]

TASK [Report artifact path] ****************************************************
ok: [main-router] => {
    "msg": {
        "host": "main-router",
        "output_dir": "/home/kevin/projects/infra-ansible/playbooks/network/../../artifacts/network-readonly/20260619_200525",
        "output_suffix": "phase254_20260620T010520Z_cmd03",
        "platform": "mikrotik"
    }
}

PLAY RECAP *********************************************************************
main-router                : ok=6    changed=0    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0


```


### COMMAND: /system/script/export hide-sensitive

- kind: `routeros`
- exit: `0`


stdout tail:
```text

PLAY [Run a read-only network device command] **********************************

TASK [Require an explicit read-only command] ***********************************
ok: [main-router] => {
    "changed": false,
    "msg": "All assertions passed"
}

TASK [Detect network device platform] ******************************************
ok: [main-router]

TASK [Select read-only credentials without logging secrets] ********************
ok: [main-router]

TASK [Require read-only credentials] *******************************************
ok: [main-router]

TASK [Run read-only network wrapper] *******************************************
ok: [main-router]

TASK [Report artifact path] ****************************************************
ok: [main-router] => {
    "msg": {
        "host": "main-router",
        "output_dir": "/home/kevin/projects/infra-ansible/playbooks/network/../../artifacts/network-readonly/20260619_200527",
        "output_suffix": "phase254_20260620T010520Z_cmd04",
        "platform": "mikrotik"
    }
}

PLAY RECAP *********************************************************************
main-router                : ok=6    changed=0    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0


```


### COMMAND: /ip/route/print detail where dst-address="0.0.0.0/0"

- kind: `routeros`
- exit: `0`


stdout tail:
```text

PLAY [Run a read-only network device command] **********************************

TASK [Require an explicit read-only command] ***********************************
ok: [main-router] => {
    "changed": false,
    "msg": "All assertions passed"
}

TASK [Detect network device platform] ******************************************
ok: [main-router]

TASK [Select read-only credentials without logging secrets] ********************
ok: [main-router]

TASK [Require read-only credentials] *******************************************
ok: [main-router]

TASK [Run read-only network wrapper] *******************************************
ok: [main-router]

TASK [Report artifact path] ****************************************************
ok: [main-router] => {
    "msg": {
        "host": "main-router",
        "output_dir": "/home/kevin/projects/infra-ansible/playbooks/network/../../artifacts/network-readonly/20260619_200529",
        "output_suffix": "phase254_20260620T010520Z_cmd05",
        "platform": "mikrotik"
    }
}

PLAY RECAP *********************************************************************
main-router                : ok=6    changed=0    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0


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
