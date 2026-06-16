# Phase 242: Backend Factory + Loud Fallback - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-15
**Phase:** 242-backend-factory-loud-fallback
**Areas discussed:** Steering wiring scope, Fallback trigger boundary, /health attribution split, What the factory returns

---

## Steering Wiring Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Route construction only | Factory is single construction site for both autorate:145 + steering:2554; steering pinger stays dead (still consumes /health), live consumption revival deferred to 245 under rollback anchor; source_ip designed correctly now | ✓ |
| Revive consumption now | Factory + steering consumes its own RTTMeasurement live in 242; front-loads risk, contradicts 238's staging | |
| Autorate only, skip steering | Wire only autorate:145; reads Criterion 3's conditional as unsatisfied — but 238 DID route it there, so under-delivers | |

**User's choice:** Route construction only (Recommended)
**Notes:** Mirrors 240's "wire both consumers now so the next phase only flips, tighter per-phase SAFE-17 surface." 238 flagged daemon.py:2554 passes no source_ip — factory designs the binding correctly here so 245 inherits it.

---

## Fallback Trigger Boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Construction-time which() | One-time build-time decision: backend==fping and which('fping') absent → construct icmplib loudly; runtime burst failures stay 241's FpingThread | ✓ |
| Also runtime demotion | Factory also owns ongoing hot-swap to icmplib after N runtime fping deaths; new stateful machinery, larger SAFE-17 surface, overlaps 241 | |

**User's choice:** Construction-time which() (Recommended)
**Notes:** Clean separation — factory owns "is fping installable," thread owns "did this burst fail." Matches FALL-01's literal "binary is unavailable."

---

## /health Attribution Split

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal fallback signal | 242 adds additive keys for observability (active backend + fallback flag/counter); full per-sample backend/source_ip attribution stays 244; 3 existing fields byte-preserved | ✓ |
| Land full attribution now | 242 absorbs 244's HEALTH-01; collapses 242/244 boundary, byte-preservation risk | |
| Counter + log only, no /health | WARN + in-process counter via logs/metrics only, zero /health; under-delivers FALL-02's named "/health attribution" pillar | |

**User's choice:** Minimal fallback signal (Recommended)
**Notes:** FALL-02 pillars map to WARN-once (log) + counter (here) + /health attribution (minimal slice; 244 enriches). The three steering-consumed fields (available/raw_rtt_ms/staleness_sec) stay byte-preserved per 238's mandate.

---

## What the Factory Returns

| Option | Description | Selected |
|--------|-------------|----------|
| Backend + thread bundle | Factory returns backend AND its pre-wired driver thread (icmplib→BackgroundRTTThread, fping→FpingThread w/ cadence); call sites = `backend, thread = build_rtt_backend(...)`, zero backend-type branching | ✓ |
| Backend object only | Returns just probe()-implementer; each consumer wires its own thread → backend-type branching leaks to both call sites | |
| You decide (planner) | Lock behavior, leave exact return shape to planner | |

**User's choice:** Backend + thread bundle (Recommended)
**Notes:** The two thread classes aren't interchangeable and cadence differs per backend, so the factory hides all divergence — strongest reading of "single construction site." Exact return shape (tuple vs dataclass) left to planner.

---

## Claude's Discretion

- Exact factory module location + signature (config/source_ip/shutdown_event/logger), provided single construction site for both consumers and SAFE-17-allowlisted.
- WARN-once scoping (per-process vs per-WAN) and fallback-counter location (in-process vs persisted); "loud + observable, never silent" is the only hard constraint.
- Exact return shape of the backend+thread bundle (tuple vs dataclass/handle).
- Exact additive /health key names/nesting for the minimal fallback signal.
- icmplib fallback uses the existing RTTMeasurement + BackgroundRTTThread construction; fping sub-params simply don't apply on that path.

## Deferred Ideas

- Reviving steering's pinger to CONSUME its own RTT live — Phase 245 under rollback anchor.
- Full per-sample /health backend/source_ip attribution (HEALTH-01) — Phase 244.
- Runtime backend hot-swap / stateful demotion watcher — rejected for 242 (new controller-path machinery, larger SAFE-17 surface); runtime recovery stays 241's FpingThread.
- Conditional production default flip to fping — Phase 246.
- irtt as a selectable backend (IRTT-MIG-01) — future milestone.
