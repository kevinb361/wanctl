# Phase 121: Core Hysteresis Logic - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-03-31
**Phase:** 121-core-hysteresis-logic
**Areas discussed:** Rate behavior during dwell, Dwell scope on higher transitions

---

## Rate Behavior During Dwell

| Option | Description | Selected |
|--------|-------------|----------|
| Hold steady (Recommended) | Stay at current rate, no decay. Matches spike detector pattern. Prevents unnecessary rate drops from transient jitter. | Yes |
| Gentle preemptive decay | Apply factor_down_yellow during dwell as a hedge. Risk: decays rates during false positives. | |
| You decide | Claude picks based on codebase patterns | |

**User's choice:** Hold steady (Recommended)
**Notes:** Consistent with spike detector pattern. 150ms dwell at 50ms/cycle is short enough that genuine congestion triggers YELLOW quickly.

---

## Dwell Scope on Higher Transitions

| Option | Description | Selected |
|--------|-------------|----------|
| GREEN->YELLOW only (Recommended) | Keep RED immediate, SOFT_RED with own sustain counter. Dwell only prevents oscillation at target_bloat boundary. | Yes |
| All upward transitions from GREEN | Require dwell for all upward transitions. More conservative but adds latency. | |
| You decide | Claude picks based on production data | |

**User's choice:** GREEN->YELLOW only (Recommended)
**Notes:** Flapping is exclusively at the target_bloat boundary. Heavy congestion (SOFT_RED/RED) should bypass dwell for fast response.

---

## Claude's Discretion

- Implementation details of counter variable naming and method signatures
- Whether to extract hysteresis logic into helper or keep inline

## Deferred Ideas

None
