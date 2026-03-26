# Phase 117: pyroute2 Netlink Backend - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-03-26
**Phase:** 117-pyroute2-netlink-backend
**Areas discussed:** Structure, Fallback, Version, Stats scope

---

## New class vs modify existing

| Option | Description | Selected |
|--------|-------------|----------|
| New NetlinkCakeBackend class | Separate class, new transport name. Both coexist. Clean separation. | |
| Modify LinuxCakeBackend internally | Same class, same transport. Netlink first, subprocess fallback. Transparent. | |
| You decide | Claude chooses based on codebase patterns | ✓ |

**User's choice:** Claude's discretion
**Notes:** Research recommended new class approach. Phase 105 context shows _run_tc() as the central seam with 7 call sites.

---

## Fallback strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Per-call subprocess fallback | Each failed netlink call retries via subprocess. Maximum resilience. | |
| Permanent fallback after N failures | Switch to subprocess permanently after N failures. Restart to retry. | |
| Skip-and-continue (match D-09) | Same as tc failure: skip, log, try again next cycle. No subprocess fallback. | |
| You decide | Claude chooses based on safety and simplicity | ✓ |

**User's choice:** Claude's discretion
**Notes:** Key constraint: broken pyroute2 must never cause sustained bandwidth control loss. 24/7 production system.

---

## pyroute2 version & proof-of-concept

| Option | Description | Selected |
|--------|-------------|----------|
| Start with 0.7.x (safe) | Pin to 0.7.12. Synchronous, thread-based, known stable. | |
| Start with 0.9.x (latest) | Use 0.9.5. Async rewrite, more features, higher risk. | |
| PoC determines version | Run both on VM, empirical data decides. | |
| You decide | Claude evaluates and picks | ✓ |

**User's choice:** Claude's discretion
**Notes:** Research flagged version conflict between STACK.md (0.9.5) and ARCHITECTURE.md (0.7.x). PoC validation on VM is mandatory regardless.

---

## Stats via netlink scope

| Option | Description | Selected |
|--------|-------------|----------|
| Full scope (change + stats) | Both netlink bandwidth changes AND stats in Phase 117. | |
| Split: change now, stats later | Bandwidth changes only. Stats stays subprocess. Lower risk. | |
| You decide | Claude evaluates complexity and decides | ✓ |

**User's choice:** Claude's discretion
**Notes:** NLNK-04 requires netlink stats. pyroute2 CAKE stats decoder exists (PR #662) but needs empirical verification against existing get_queue_stats() contract.

## Claude's Discretion

All four areas delegated to Claude's discretion:
- Integration structure (new class vs internal modification)
- Fallback degradation strategy
- pyroute2 version selection
- Stats via netlink inclusion vs deferral

## Deferred Ideas

None -- discussion stayed within phase scope
