# Phase 238: RTT-Provenance Verification (Read-Only Entry Gate) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-14
**Phase:** 238-rtt-provenance-verification-read-only-entry-gate
**Areas discussed:** A/B target decision model, A/B decision criteria, Provenance map deliverable, fping egress proof scope, fping egress proof method, Read-only + SAFE-17 entry proof

---

## A/B Target Decision Model

| Option | Description | Selected |
|--------|-------------|----------|
| Evidence first, then I pick | Phase produces map + A-vs-B recommendation with evidence; operator makes binding call at execution. CONTEXT captures criteria, not verdict. | ✓ |
| Lock my leaning now | Commit a leaning into CONTEXT; phase confirms/refutes. | |
| Auto-select via approved rule | Approve a rule now; phase applies it mechanically. | |

**User's choice:** Evidence first, then I pick.
**Notes:** Fits live-reality-first posture and PROV-02's "selected and recorded with evidence."

---

## A/B Target Leaning

| Option | Description | Selected |
|--------|-------------|----------|
| Lean A (revive steering pinger) | Only in-scope way to put seam on live steering path; changes steering to self-measure. | |
| Lean B (autorate/bridge producer) | Producer is upstream bash cake-autorate; wanctl variant needs deferred native autorate. | |
| Genuinely undecided | Let provenance evidence + scope-fit decide; phase presents both. | ✓ |

**User's choice:** Genuinely undecided.
**Notes:** Phase must honestly present both interpretations including the bash-cake-autorate wrinkle.

---

## A/B Decision Criteria (Rubric)

| Option | Description | Selected |
|--------|-------------|----------|
| Scope-reach first, blast-radius tiebreak | Primary: seam on live path within v1.53 scope. Tiebreak: least disruption. | |
| Minimize control-path blast radius | Favor least live-behavior change, conservative SAFE-17 spirit. | |
| Maximize A/B evidence fidelity | Favor most trustworthy icmplib-vs-fping comparison for Phase 245, accepting more change. | ✓ |

**User's choice:** Maximize A/B evidence fidelity.
**Notes:** Prioritizes Phase 245 verdict quality over conservatism; blast-radius still documented as a tradeoff.

---

## Provenance Map Deliverable

| Option | Description | Selected |
|--------|-------------|----------|
| Phase-dir evidence artifact | 238-*/PROVENANCE-MAP.md embedding live /health + code-path trace + bridge identity. | ✓ |
| docs/ operator runbook | docs/RTT-PROVENANCE.md durable reference. | |
| Both — evidence + pointer | Phase-dir artifact + docs/ pointer. | |

**User's choice:** Phase-dir evidence artifact.
**Notes:** Consistent with prior read-only milestones (212/222/225); docs/ runbook deferred.

---

## fping Egress Proof Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Both WANs (Spectrum + ATT) | Prove per-WAN ping_source_ip egress; capture ip rule table. | ✓ |
| WAN-under-test only | Just the eventual A/B WAN. | |
| Both WANs + reflector set | Both WANs across full reflector list. | |

**User's choice:** Both WANs (Spectrum + ATT).
**Notes:** Safe while A/B target undecided; matches both-WANs-in-prod reality.

---

## fping Egress Proof Method

| Option | Description | Selected |
|--------|-------------|----------|
| Committed script, operator runs on prod | scripts/phase238-egress-proof.sh; stdout captured. Reproducible. | ✓ |
| Ad-hoc operator commands | `! ssh …` paste into artifact. | |

**User's choice:** Committed script, operator runs on prod.
**Notes:** Reproducible and re-runnable, consistent with prior phases.

---

## Read-Only + SAFE-17 Entry Proof

| Option | Description | Selected |
|--------|-------------|----------|
| Lightweight git-diff assertion | Empty controller-path diff + no-mutation statement; full verifier in 239. | ✓ |
| Author the SAFE-17 verifier now | Build fail-closed verifier in 238 (arguably 239 scope). | |
| Reuse prior SAFE-16 verifier as-is | Point existing zero-diff verifier at controller path. | |

**User's choice:** Lightweight git-diff assertion.
**Notes:** 238 has no source changes by definition; full verifier + narrowed allowlist authored in Phase 239 per roadmap.

---

## Claude's Discretion

- Exact filenames / section structure of PROVENANCE-MAP.md and egress-proof script output shape.
- Read-only live-capture method (operator `! curl`/`! ssh` vs script-fetched /health); privileged/credentialed reads handed to operator as `! <command>`.

## Deferred Ideas

- NATIVE-AB-01 — stand up native autorate to make interpretation B fully wanctl-owned (deferred out of v1.53).
- docs/RTT-PROVENANCE.md durable operator runbook (kept in phase dir for now).
- Full SAFE-17 fail-closed verifier + narrowed allowlist (Phase 239 scope).
