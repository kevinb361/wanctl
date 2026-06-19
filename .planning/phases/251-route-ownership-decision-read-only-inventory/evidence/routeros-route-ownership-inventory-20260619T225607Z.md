# Phase 251 — RouterOS Route Ownership Inventory

**Captured at:** 2026-06-19T22:56:07Z
**Router:** main-router / `KEV_RO_OFFICE`
**Access path:** `/home/kevin/projects/infra-ansible/playbooks/network/mikrotik_readonly.yml` with `routeros_readonly_transport=ssh`
**Raw sanitized artifact directory:** `/home/kevin/projects/infra-ansible/artifacts/network-readonly/20260619T225607Z-phase251-route-ownership`
**Command file:** `.planning/phases/251-route-ownership-decision-read-only-inventory/evidence/routeros-readonly-commands-20260619T225607Z.txt`

## Planned read-only commands

The final command file passed the Phase 251 whitelist before any live RouterOS command was executed.

- `COMMAND: /system/identity/print`
- `COMMAND: /tool/netwatch/print detail`
- `COMMAND: /tool/netwatch/print detail where name~"Monitor-Spectrum|Monitor-ATT"`
- `COMMAND: /system/script/print detail`
- `COMMAND: /system/script/export hide-sensitive`
- `COMMAND: /ip/route/print detail where dst-address="0.0.0.0/0"`

Note: candidate `where comment~...` and `where name~"Enable-|Disable-"` filters were rejected by the plan whitelist before live execution because the strict verb/token guard treats `comment`, `Enable`, and `Disable` as forbidden tokens. The live run therefore used broad read-only `print`/`export hide-sensitive` commands and this evidence embeds only the relevant sanitized route-ownership subset.

## Netwatch entries

- id `1` name `Monitor-Spectrum` enabled `true` host `1.1.1.1` status `up` up `/system/script/run Enable-Spectrum` down `/system/script/run Disable-Spectrum`
- id `2` name `Monitor-ATT` enabled `true` host `8.8.8.8` status `up` up `/system/script/run Enable-ATT` down `/system/script/run Disable-ATT`

Result: `Monitor-Spectrum` and `Monitor-ATT` were found by exact expected names, enabled, and reporting `status=up` during capture.

A separate disabled legacy Netwatch entry without the expected route-owner names was present in the broad Netwatch print; it calls `HostUp`/`HostDown` and is not the WAN route owner identified for v1.55.

## Route-mutating scripts

- `Disable-Spectrum` id `14` owner `admin` policy `read,write,test` dont-require-permissions `false` run-count `0` targets route comments: Spectrum; source sha256 `93ebdecb7eb6b78b784de6b093baf493b880342407939b133e6bad62fa68c095`
- `Enable-Spectrum` id `15` owner `admin` policy `read,write,test` dont-require-permissions `false` run-count `0` targets route comments: Spectrum; source sha256 `47c46515fb1deb6faec59b5fea57cd6e1438cdeadc410425cca8abd6d9766f90`
- `Disable-ATT` id `16` owner `admin` policy `read,write,test` dont-require-permissions `false` run-count `0` targets route comments: ATT, Force ATT_OUT to ATT WAN; source sha256 `ab9b061e162b13a5d1e302df9e7b8e2ca9b0267e0bcf9fe1cac62d396968e3db`
- `Enable-ATT` id `17` owner `admin` policy `read,write,test` dont-require-permissions `false` run-count `0` targets route comments: ATT, Force ATT_OUT to ATT WAN; source sha256 `4e210b98c74040b002bd528c554533e1850c3a1f64c2bb5117e2a8ec60637fab`

Result: expected `Enable-*` / `Disable-*` route-mutating scripts were found. All four are owned by `admin`, use policy `read,write,test`, have `dont-require-permissions=no`, and had `run-count=0` at capture time.

The broad script export was collected with `hide-sensitive`, but this artifact intentionally embeds only the four route-mutating script summaries plus source hashes and non-secret route-comment actions.

## Default routes

- id `0` flags `As` comment `Spectrum` table `main` gateway `70.123.224.1` distance `1` active `true` disabled `false` check-gateway `ping`
- id `1` flags `s` comment `ATT` table `main` gateway `192.168.2.254` distance `2` active `false` disabled `false` check-gateway `arp`
- id `6` flags `As` comment `Force ATT_OUT to ATT WAN` table `to_ATT` gateway `99.126.112.1` distance `1` active `true` disabled `false` check-gateway `ping`
- id `7` flags `s` comment `Backup to Spectrum if ATT fails` table `to_ATT` gateway `70.123.224.1` distance `2` active `false` disabled `false` check-gateway `ping`

Result: default routes exist for main Spectrum, main ATT, ATT policy table, and ATT-table Spectrum backup. Spectrum main and `Force ATT_OUT to ATT WAN` were active at capture time; ATT main and ATT-table Spectrum backup were present but not active.

## Script-to-route mapping

- `Disable-Spectrum` -> Spectrum
- `Enable-Spectrum` -> Spectrum
- `Disable-ATT` -> ATT, Force ATT_OUT to ATT WAN
- `Enable-ATT` -> ATT, Force ATT_OUT to ATT WAN

This confirms Netwatch scripts mutate routes by RouterOS route `comment` selectors, not immutable route IDs. Phase 252 should account for comment drift and consider explicit config anchoring.

## Current owner conclusion

Netwatch is active and remains the interim WAN default-route owner.

`Monitor-Spectrum` and `Monitor-ATT` call route-mutating `Enable-*` / `Disable-*` scripts. wanctl/steering is not currently the RouterOS WAN default-route mutator. Future wanctl active route mutation must treat these enabled Netwatch entries as an active-mode blocker unless an explicit migration flag and operator approval exist.

## REST/API support gap

Phase 251 used the infra-ansible read-only SSH wrapper for evidence collection only. This is not an implementation precedent for wanctl's hot path.

Known Phase 252 input: current `RouterOSREST.run_cmd()` support does not cover `/tool/netwatch`, `/system/script`, or `/ip/route` CLI-style operations. Route ownership implementation must add required read/mutation operations through the existing router integration boundary.

## No-mutation proof

Live command transcript:

```text
COMMAND: /system/identity/print
COMMAND: /tool/netwatch/print detail
COMMAND: /tool/netwatch/print detail where name~"Monitor-Spectrum|Monitor-ATT"
COMMAND: /system/script/print detail
COMMAND: /system/script/export hide-sensitive
COMMAND: /ip/route/print detail where dst-address="0.0.0.0/0"
```

All live commands are `print` or `export hide-sensitive` reads allowed by the Phase 251 command whitelist. No Phase 251 live command contained `enable`, `disable`, `set`, `add`, `remove`, `run`, `import`, `reset`, `comment`, or `policy` as a standalone mutating verb in the issued command line.

The Ansible wrapper reported `changed=0` for every live command. The command transcript contains no RouterOS route, Netwatch, or script mutation command issued by Phase 251.

## Redactions

- Broad script export output is not embedded wholesale because it includes unrelated scripts and sensitive-capability metadata.
- Snapshot-A embeds only route-mutating script names, policies, route-comment actions, and source hashes.
- No credential, token, private key, or secret value is embedded in this artifact.
