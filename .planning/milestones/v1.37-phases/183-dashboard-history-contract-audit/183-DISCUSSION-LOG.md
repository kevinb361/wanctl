# Phase 183: Dashboard History Contract Audit - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-14T09:07:52-05:00
**Phase:** 183-dashboard-history-contract-audit
**Areas discussed:** Labeling language, Source metadata contract, Operator handoff path, Failure and degraded cases, Audit deliverables

---

## Labeling Language

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit endpoint-local wording | State plainly that the history tab is endpoint-local and not authoritative merged history | ✓ |
| Soft clarification | Keep generic history wording with a smaller note or hint | |
| Minimal wording | Avoid strong copy and rely on docs/tests only | |

**User's choice:** Delegated to the agent.
**Notes:** Locked to explicit endpoint-local wording because prior phases and docs already narrowed the operator truth, and the current ambiguity is the main milestone driver.

---

## Source Metadata Contract

| Option | Description | Selected |
|--------|-------------|----------|
| Require source context in the UI contract | Treat `metadata.source` as mandatory context for the dashboard history tab | ✓ |
| Best-effort source context | Show source metadata when convenient but allow silent omission | |
| Raw diagnostic-only exposure | Keep source metadata as backend/test detail only | |

**User's choice:** Delegated to the agent.
**Notes:** Locked to requiring source context because the backend already exposes `metadata.source` and the dashboard currently drops the main signal operators need.

---

## Operator Handoff Path

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit merged-proof handoff | Give operators a clear path from the history tab to the authoritative merged CLI workflow | ✓ |
| Passive documentation reference | Mention docs only, without a concrete operator proof-path cue | |
| No in-tab handoff | Keep dashboard local-only and require operators to already know the CLI path | |

**User's choice:** Delegated to the agent.
**Notes:** Locked to an explicit handoff because `DASH-03` requires a clear path, and current docs already define the authoritative CLI/module route.

---

## Failure And Degraded Cases

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit degraded-state contract | Missing source metadata or fetch failures must be surfaced as ambiguity/degradation | ✓ |
| Generic fetch-failure contract | Only handle request failure, not missing source context | |
| No added contract | Preserve the current generic “No data” behavior | |

**User's choice:** Delegated to the agent.
**Notes:** Locked to explicit degraded-state handling so the UI cannot silently imply merged semantics when source context is absent or broken.

---

## Audit Deliverables

| Option | Description | Selected |
|--------|-------------|----------|
| Audit plus concrete source contract | Produce ambiguity findings and a dashboard-facing contract that later phases implement and test | ✓ |
| Audit only | Record gaps, leave the contract to later planning | |
| UI proposal only | Skip explicit ambiguity findings and move straight to UI ideas | |

**User's choice:** Delegated to the agent.
**Notes:** Locked to both audit and contract outputs so Phase 184 and Phase 185 can implement against a precise target instead of rediscovering ambiguity.

---

## the agent's Discretion

- Exact copywriting details for the eventual dashboard labels and guidance.
- Exact widget placement for source context and CLI handoff UI.
- Exact regression structure for later phases.

## Deferred Ideas

- Reintroducing merged cross-WAN semantics into `/metrics/history`
- Storage or retention changes tied to history topology
- Broader dashboard redesign beyond this history-source contract
