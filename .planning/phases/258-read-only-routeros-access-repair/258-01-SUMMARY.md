---
phase: 258-read-only-routeros-access-repair
plan: 01
subsystem: routeros-access
status: complete
tags: [wanctl, routeros, access, evidence]
key-files:
  created:
    - .planning/phases/258-read-only-routeros-access-repair/evidence/258-01-root-cause.md
    - .planning/phases/258-read-only-routeros-access-repair/evidence/258-01-a1-preflight.md
  modified: []
requirements-completed:
  - ACCESS-01
  - SAFE-21
completed: 2026-06-20
---

# Phase 258 Plan 01: ACCESS-01 Root Cause + A1 Preflight Summary

Documented the v1.56 read-only RouterOS inspection blocker as two distinct failure layers and resolved the A1 REST endpoint gate.

## Accomplishments

- Wrote `258-01-root-cause.md` documenting:
  - daemon-path blocker: `RouterOSREST` lacked `/tool netwatch print` and `/system script print` handlers, so `RouteOwnershipGuard.inspect()` failed closed;
  - manual-evidence-path blocker: nested SSH through `/etc/wanctl/ssh/router.key` failed returncode 255;
  - why `router.key` repair alone would not fix the daemon path;
  - credential facts split into known evidence vs [OPERATOR-VERIFY] live-only facts;
  - chosen supported path: keep REST and add GET-only netwatch + script handlers.
- Ran A1 as a privileged read-only operator-approved probe on `cake-shaper` without printing secrets.
- Confirmed RouterOS REST exposes both endpoints:
  - `A1-NETWATCH-OK entries=3`
  - `A1-SCRIPT-OK entries=20`
- Updated `258-01-a1-preflight.md` from blocked to `A1-confirmed`.

## Task Commits

| Commit | Description |
|--------|-------------|
| `26ab97cd` | record root cause and initial A1 checkpoint |
| `3065edc2` | confirm A1 REST endpoints |

## Verification

- Root-cause grep/negative gates passed: netwatch, system script, router.key/255, known-vs-operator-pending split, no secret/key material.
- `.venv/bin/pytest -o addopts='' tests/test_routeros_rest.py -q` passed before Wave 2.
- A1 privileged read-only probe returned parseable counts for netwatch and script.

## Deviations

- The first nonprivileged A1 attempt could not read `/etc/wanctl/secrets` or `/etc/wanctl/steering.yaml`, returning REST 401. This was correctly recorded as `A1-blocked`, not endpoint failure.
- After explicit operator approval, the same read-only probe was rerun through `sudo bash -s` on `cake-shaper` and confirmed A1.

## Self-Check: PASSED

- Both failure layers are documented.
- A1 is confirmed before Plan 02.
- SAFE-21 held: no RouterOS mutation, no Netwatch change, no service restart.
