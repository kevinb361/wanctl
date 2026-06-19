# Phase 244: Health-Payload Attribution Metadata - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-18
**Phase:** 244-health-payload-attribution-metadata
**Areas discussed:** Attribution surfaces, `backend` key semantics, `source_ip` semantics, SAFE-17 proof

---

## Attribution Surfaces

| Option | Description | Selected |
|--------|-------------|----------|
| Steering /health only | Add fields only to steering/health.py — the A/B measurement path (Selection A). Minimal blast radius. | ✓ |
| Steering + autorate | Also enrich autorate health_check.py (where backend_active already lives). | ✓ |
| Include state-bridge | Also add to deploy/scripts/cake-autorate-*-state-bridge (RTT from cake-autorate EWMA, not the wanctl seam). | ✓ |

**User's choice:** All three surfaces.
**Notes:** Kevin wants attribution everywhere. Because the bridge's RTT comes from upstream
cake-autorate (not the wanctl backend seam, per 238 D-04), CONTEXT records a mandatory
honesty caveat (D-02): the bridge's `backend` must reflect the real producer
(`"cake-autorate"`-class label), never claim icmplib/fping from the seam. Bridge `source_ip`
availability flagged as a research item.

---

## `backend` key semantics

| Option | Description | Selected |
|--------|-------------|----------|
| New per-sample backend | `backend` = backend that produced the current sample (RttSample.backend); keep `backend_active` = factory-selected. | ✓ (Claude) |
| Alias to backend_active | Treat `measurement.backend` as the same value as `backend_active`. | |

**User's choice:** "you decide" → Claude's discretion.
**Notes:** Chose new per-sample `backend` (D-03) — after a loud fallback, selected vs
producing backend can differ; both maximize A/B fidelity.

---

## `source_ip` semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Configured intended, null if unset | Report per-WAN configured `-S`/source= IP; null when none configured / pre-first-sample. | ✓ (Claude) |
| Observed bound, null if unknown | Report the IP observed on the last sample; null until first real sample. | |

**User's choice:** "you decide" → Claude's discretion.
**Notes:** Chose configured-intended with null (D-04) — the phase must be attributable
*before* the A/B; on Selection A the steering pinger is dead pre-245, so observed-only would
be null exactly when needed. Matches 242 D-01a.

---

## SAFE-17 proof

| Option | Description | Selected |
|--------|-------------|----------|
| Snapshot test + advance anchor | Pin existing measurement keys/types, assert additive-only, advance SAFE-17 anchor past 242-close. | |
| Let planner decide | Defer verification mechanics to research/planning. | ✓ |

**User's choice:** Let planner decide.
**Notes:** CONTEXT (D-05) records the snapshot-test+anchor-advance approach as the
recommended default for the planner to weigh; notes this is the first intentional
controller-path health-shape change of v1.53, so the SAFE-17 allowlist/anchor must be
updated, not merely passed.

## Claude's Discretion

- `backend` key semantics (D-03)
- `source_ip` semantics (D-04)
- SAFE-17 / byte-preservation mechanics (D-05, deferred to planner)

## Deferred Ideas

- Live A/B execution / flipping steering consumption → Phase 245 (AB-01).
- Native autorate producer (Interpretation B wanctl variant) → NATIVE-AB-01, deferred from v1.53.
- State-bridge learning per-WAN `ping_source_ip` (env wiring) → research item under D-02.
