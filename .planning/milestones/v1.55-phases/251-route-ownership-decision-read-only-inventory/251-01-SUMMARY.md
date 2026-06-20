---
phase: "251"
plan: "251-01"
status: complete
completed: 2026-06-19
requirements:
  - OWN-01
  - OWN-02
  - OWN-03
  - INV-01
  - INV-02
  - INV-03
  - SAFE-19
---

# Phase 251 Plan 251-01 — Summary

## Outcome

Phase 251 completed the route ownership decision and read-only RouterOS inventory.

Decision: Netwatch remains the interim route owner. Future wanctl route ownership should live in `steering.service`, but active wanctl route mutation remains forbidden until later phases implement the guarded/off-by-default route manager, dry-run observation, and an explicitly approved canary.

Live read-only inventory found the expected current route-owner shape:

- Router identity: `KEV_RO_OFFICE` via `main-router`.
- `Monitor-Spectrum` exists, is enabled, and calls `Enable-Spectrum` / `Disable-Spectrum`.
- `Monitor-ATT` exists, is enabled, and calls `Enable-ATT` / `Disable-ATT`.
- All four route-mutating scripts exist with `policy=read,write,test`, `dont-require-permissions=no`, owner `admin`, and `run-count=0` at capture time.
- Default routes include `Spectrum`, `ATT`, `Force ATT_OUT to ATT WAN`, and `Backup to Spectrum if ATT fails`.

No production mutation was performed.

## Requirements Closure

- OWN-01: Satisfied by `251-ROUTE-OWNERSHIP-DECISION.md`; it documents Netwatch as interim route owner until wanctl route ownership is implemented, guarded, tested, canaried, and accepted.
- OWN-02: Satisfied by `251-ROUTE-OWNERSHIP-DECISION.md`; it defines the steady-state contract that exactly one component may mutate WAN default routes at a time.
- OWN-03: Satisfied by `251-ROUTE-OWNERSHIP-DECISION.md`; it documents Netwatch coexistence, retirement policy, incident attribution, and migration guard requirements.
- INV-01: Satisfied by `evidence/routeros-route-ownership-inventory-20260619T225607Z.md`; it captures Netwatch entries, route-mutating scripts, default routes, route comments/IDs, distances, enabled/active state, and current owner conclusion.
- INV-02: Satisfied by `evidence/snapshot-a-20260619T225607Z.json`; it provides the machine-readable Snapshot-A rollback anchor.
- INV-03: Satisfied by the `No-mutation proof` in `evidence/routeros-route-ownership-inventory-20260619T225607Z.md` plus the command whitelist/transcript scan.
- SAFE-19: Satisfied. Phase 251 issued only read-only RouterOS `print` and `export hide-sensitive` commands via the infra-ansible read-only wrapper. It did not mutate routes, disable Netwatch, retune controller thresholds, change CAKE qdiscs, or flip production defaults.

## Evidence

Primary artifacts:

- `.planning/phases/251-route-ownership-decision-read-only-inventory/251-ROUTE-OWNERSHIP-DECISION.md`
- `.planning/phases/251-route-ownership-decision-read-only-inventory/evidence/routeros-readonly-commands-20260619T225607Z.txt`
- `.planning/phases/251-route-ownership-decision-read-only-inventory/evidence/routeros-route-ownership-inventory-20260619T225607Z.md`
- `.planning/phases/251-route-ownership-decision-read-only-inventory/evidence/snapshot-a-20260619T225607Z.json`

Raw sanitized read-only wrapper artifacts:

- `/home/kevin/projects/infra-ansible/artifacts/network-readonly/20260619T225607Z-phase251-route-ownership/`

Validation commands passed:

- Phase 251 inventory artifact and command-whitelist assertion.
- Phase 251 no-mutation command whitelist and transcript scan.
- `git diff --check`.

## SAFE-19 Result

PASSED.

The final live command list was:

```text
COMMAND: /system/identity/print
COMMAND: /tool/netwatch/print detail
COMMAND: /tool/netwatch/print detail where name~"Monitor-Spectrum|Monitor-ATT"
COMMAND: /system/script/print detail
COMMAND: /system/script/export hide-sensitive
COMMAND: /ip/route/print detail where dst-address="0.0.0.0/0"
```

All commands were read-only and passed the Phase 251 whitelist before live execution. The infra-ansible wrapper reported `changed=0` for every command.

## Decision

Netwatch remains the interim WAN route owner.

Future wanctl route ownership target: `steering.service`, unless a later phase discovers contrary implementation evidence. Active route mutation by wanctl is blocked while enabled route-mutating Netwatch entries exist, unless a later migration flag and explicit operator approval are present.

## Snapshot-A

Snapshot-A was captured at `2026-06-19T22:56:07Z` in:

- `.planning/phases/251-route-ownership-decision-read-only-inventory/evidence/snapshot-a-20260619T225607Z.json`

It includes:

- router identity,
- exact read-only commands,
- raw artifact hashes,
- Netwatch entries,
- route-mutating scripts,
- default routes,
- script-to-route mapping,
- restore notes,
- redaction notes,
- REST/API support gap for Phase 252.

## Phase 252 Inputs

Implementation inputs discovered in Phase 251:

1. Current `RouterOSREST.run_cmd()` does not support `/tool/netwatch`, `/system/script`, or `/ip/route` CLI-style operations. Phase 252 must implement route/Netwatch/script read operations and route mutation operations through the existing RouterOS integration boundary, not ad hoc shell/SSH.
2. Netwatch route mutation is currently comment-selector based. Scripts target route comments `Spectrum`, `ATT`, and `Force ATT_OUT to ATT WAN`. Phase 252 should decide whether config anchors route IDs, comments, or both, and how to handle comment drift.
3. Guard implementation must detect enabled `Monitor-Spectrum` and `Monitor-ATT` plus their route-mutating up/down scripts.
4. Active wanctl route mutation must fail closed if those enabled Netwatch route-mutating entries are present, unless a later migration flag and explicit operator approval exist.
5. Dry-run/observe mode can warn on Netwatch conflict while still emitting intended actions; active mode must not mutate.
6. Snapshot-A route state should be used as rollback anchor before Phase 254 canary work.

## Deviations

- The originally considered `where comment~...` command and script-name filters containing `Enable`/`Disable` were rejected by the Phase 251 whitelist before live execution. The final live command file used broader read-only `print` / `export hide-sensitive` commands and then embedded only the relevant sanitized route-ownership subset.
- Broad `/system/script/export hide-sensitive` output was collected by the read-only wrapper but not embedded wholesale because it includes unrelated scripts and sensitive-capability policy metadata. Snapshot-A embeds only the four route-mutating script summaries, hashes, and non-secret route-comment actions.

## Self-Check

PASSED.

Decision artifact exists. Inventory evidence exists. Snapshot-A JSON exists. No-mutation proof exists and passed automated command whitelist/transcript scan.
