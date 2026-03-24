# Phase 106: CAKE Optimization Parameters - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-24
**Phase:** 106-cake-optimization-parameters
**Areas discussed:** Parameter storage, Overhead keywords, rtt tuning

---

## Parameter Storage Location

Claude recommended dual-layer: hardcoded defaults for boolean flags + YAML config for tunable values. User accepted.

---

## Overhead Keywords vs Values

Claude recommended tc keywords (docsis, bridged-ptm) — self-documenting, canonical. User accepted.

---

## rtt Parameter Tuning

Claude recommended configurable in YAML with 100ms default, declared as adaptive tuning candidate. User accepted.

---

## Claude's Discretion

- YAML config schema structure
- Param builder function design
- Test patterns
- Per-direction helper construction

## Deferred Ideas

- Adaptive tuning of rtt — v1.20 infrastructure exists, integration deferred
- diffserv8 mode — needs mangle rule expansion
- Per-tin bandwidth allocation tuning
