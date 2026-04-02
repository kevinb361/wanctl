# Phase 126: Pre-Test Gate - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-02
**Phase:** 126-pre-test-gate
**Areas discussed:** Router CAKE cleanup, Gate verification method, Pre-test checklist scope

---

## Router CAKE Cleanup

| Option | Description | Selected |
|--------|-------------|----------|
| REST API commands | Use MikroTik REST API to check /queue/type and /queue/tree, disable via API if found. Scriptable and documentable. | ✓ |
| Manual via Winbox | Check and disable interactively through Winbox GUI. Quick but not reproducible. | |
| wanctl-check-cake --fix | Existing tool can audit router CAKE. May need modification to disable rather than optimize. | |

**User's choice:** REST API commands
**Notes:** User wants to "disable everything but fully clean it up.. no deletions!" — preserve entries for rollback capability.

### Follow-up: What to check on router

| Option | Description | Selected |
|--------|-------------|----------|
| Queue tree + queue type | Check both, disable queue tree entries, leave type defs alone. | |
| Full cleanup | Check queue tree, queue type, AND mangle rules. Remove all three layers. | |
| You decide | Claude determines scope based on existing wanctl-check-cake knowledge. | |

**User's choice:** Other — "I just want to disable everything but fully clean it up.. no deletions!"
**Notes:** Disable all CAKE-related entries (queue tree, queue type, mangle) but preserve for re-enablement.

---

## Gate Verification Method

| Option | Description | Selected |
|--------|-------------|----------|
| SSH manual checks | SSH + manual tc commands, visually confirm. Quick, operator-driven. | |
| Checklist script | Write bash script that runs all gate checks and reports pass/fail. Reusable. | ✓ |
| Mix: manual + document | Run manually but document exact commands and expected output. | |

**User's choice:** Checklist script
**Notes:** Script should be stored in repo for reuse in future test sessions.

### Follow-up: How to trigger GATE-03 rate change

| Option | Description | Selected |
|--------|-------------|----------|
| SIGUSR1 + config edit | Temporarily lower max rate in spectrum.yaml, SIGUSR1 reload, check tc. Revert after. | ✓ |
| Wait for congestion | Run bandwidth test to naturally trigger rate change. More realistic but slower. | |
| Direct tc command | Run tc qdisc change manually. Tests CAKE, not full loop. | |

**User's choice:** SIGUSR1 + config edit

---

## Pre-test Checklist Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Include both extras | Add transport config check and health endpoint version. Cheap, catches misconfigurations. | ✓ |
| Skip extras | 3 requirements sufficient — CAKE active implies correct transport. | |

**User's choice:** Include both extras (5 total checks)

---

## Claude's Discretion

- Gate script naming and location
- REST API endpoints and payloads for disabling router CAKE
- Script output format

## Deferred Ideas

None — discussion stayed within phase scope.
