---
id: SEED-008
status: active
selected_for: v1.58
planted: 2026-06-26
planted_during: v1.57 closeout — Phase 260 D-07 cross-check fix + live ready-for-approval re-run
trigger_when: v1.58 milestone planning
scope: Medium-Large
priority: 9
prerequisites:
  - "v1.57 complete: supported read-only RouterOS inspection proven, Phase 260 packet ready-for-approval"
  - ">= 14 consecutive stable cake-autorate days (inherits ROLE-01 gate intent)"
priority_rationale: "First milestone where the whole read-only chain (258 access → 259 inspection → 260 observation) actually produces a ready-for-approval packet against live state. The active route-management canary — wanctl taking the default-route owner role from Netwatch under an explicit reversible operator gate — is the natural next step and the long-standing goal behind the route-ownership line (todo 2026-06-18-route-ownership-netwatch-to-wanctl-failover). It is gated, reversible, and high-value but genuinely mutating, so it earns its own milestone with a real rollback drill."
sources:
  - .planning/phases/260-dry-run-observation-rerun-canary-readiness/evidence/phase260-readiness-packet-d07fix.md
  - .planning/todos/pending/2026-06-18-route-ownership-netwatch-to-wanctl-failover.md
  - "Commit 7a96aa8f (Phase 260 D-07 detector fix) — unblocked the ready verdict"
  - "SAFE-21 (v1.57): active-route canary explicitly declared a separate operator gate, out of scope for v1.57"
---

# SEED-008: Active route-management canary — Netwatch → wanctl default-route ownership

The read-only ownership pipeline is now proven end-to-end: Phase 258 established the supported REST read-only RouterOS path, Phase 259 surfaced live Netwatch + default-route ownership, and Phase 260 (after the D-07 detector fix in commit `7a96aa8f`) produced a genuine **`ready-for-approval`** readiness packet against live cake-shaper state with the D-04 cross-check and the daemon inspector in agreement (both `route_mutating_active_count=4`, `divergences=[]`).

Everything to date has been read-only inspection and dry-run observation. The next step is the first **mutating** action in this line: wanctl actually taking the active default-route owner role from Netwatch, under an explicit, reversible, operator-approved canary. This is what the long-standing `2026-06-18-route-ownership-netwatch-to-wanctl-failover.md` todo has been building toward.

## Why This Matters

Netwatch is the current/interim WAN route owner. Moving ownership to wanctl gives the controller direct, observable, testable control of failover instead of relying on RouterOS Netwatch scripts. The whole v1.55→v1.57 arc built the safety scaffolding (guarded safe/off route-management surface, ownership inspection, dry-run observation, readiness packet) precisely so this flip could be done with eyes open and a rollback path.

## When to Surface

**Trigger:** v1.58 milestone planning. This is the first milestone that can legitimately request the active canary, because v1.57 declared it out of scope (SAFE-21) and only just produced the `ready-for-approval` evidence that the gate consumes.

## Scope / Shape (provisional — for planning, not committed)

**Medium-Large.** A canary milestone, not a single phase. Likely shape:

- **Explicit operator approval gate** consuming the `ready-for-approval` packet — `ready-for-approval` is a verdict, NOT approval (per D-10 / SAFE-21). The milestone must add the human-in-the-loop step.
- **Reversible flip**: bounded, single-route or single-WAN first, with a one-command rollback to Netwatch ownership and a pre-flighted rollback drill (inherits ROLE-01's "one exercised rollback drill" gate).
- **Live observability** of the flip: the route-management health surface (`:9102`) already exposes owner/mode/guard/last-action; the canary must assert these transition cleanly and that Netwatch is cleanly demoted (not fighting wanctl for the route).
- **New cross-cutting safety invariant** (SAFE-22?), narrower than SAFE-21: defines exactly which mutations are now allowed (the gated owner flip) and which remain forbidden (CAKE/qdisc, threshold retuning, Netwatch deletion vs disable, etc.).

## Open Questions for Planning

- Single-route vs single-WAN vs full canary granularity for the first flip.
- How Netwatch is demoted: disabled-but-retained (fast rollback) vs removed (clean but slower revert).
- What automatic abort conditions trip the canary back to Netwatch (and whether the existing circuit-breaker/guard plumbing covers them).
- Whether the deployed route-management surface on cake-shaper needs a real `deploy.sh` reconciliation first (note: one file, `route_ownership_guard.py`, is currently ahead of last full deploy from the v1.57 D-07 fix; behavior-preserving, but a full deploy should reconcile before a mutating milestone).
