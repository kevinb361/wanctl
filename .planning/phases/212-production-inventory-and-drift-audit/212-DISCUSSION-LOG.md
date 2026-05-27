# Phase 212: Production Inventory And Drift Audit - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-27
**Phase:** 212-production-inventory-and-drift-audit
**Areas discussed:** Todo folding, delegated gray-area defaults

---

## Todo Folding

| Option | Description | Selected |
|--------|-------------|----------|
| Steering restart only | Fold the steering `SPECTRUM_DEGRADED` clean-restart todo into Phase 212 because it directly affects drift/state inventory. | Yes |
| All matched todos | Fold tcp_12down, steering, profiling, flapping verification, and ATT canary into Phase 212 despite later phase mappings. | |
| None | Treat Phase 212 as pure inventory/drift audit and leave all matched todos to later phases. | |
| Pick individually | Choose a custom subset to fold into Phase 212. | |

**User's choice:** `you decide, Steering restart only`
**Notes:** Folded only `.planning/todos/pending/2026-04-17-investigate-steering-degraded-on-clean-restart.md`. Other matched todos remain mapped to later v1.46 phases.

---

## Delegated Gray-Area Defaults

| Area | Default Decision | Selected |
|------|------------------|----------|
| Drift handling | Classify-only by default; no silent production mutation; explicit operator gate if alignment is required. | Yes |
| Inventory surfaces | Treat systemd, `/health`, deployed YAML, repo configs, and steering state as primary; RouterOS readback optional and read-only. | Yes |
| Secret redaction | Redact secret-bearing values aggressively while preserving proof-relevant non-secret settings. | Yes |
| Report shape | Optimize for operator decision table with raw evidence pointers and downstream constraints. | Yes |

**User's choice:** `you decide.`
**Notes:** Defaults chosen conservatively for a production network-control system.

---

## Claude's Discretion

- Exact audit command sequence, evidence filenames, and plan split are left to planner discretion.
- The read-only/default-no-mutation boundary is locked.
- The final artifact should be operator-decision-oriented, not just a raw command transcript.

## Deferred Ideas

- tcp_12down bad-p99 investigation remains Phase 214.
- Post-hotpath profiling remains Phase 217.
- v1.45 flapping peak live verification remains Phase 218.
- ATT cake-primary canary remains deferred until recovery/refractory and ATT canary context make it relevant.
