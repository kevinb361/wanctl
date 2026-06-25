# Phase 260: Dry-Run Observation Rerun + Canary Readiness - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-25
**Phase:** 260-dry-run-observation-rerun-canary-readiness
**Areas discussed:** Authoritative readiness signal, Observation mechanism, Intent-comparison depth, Window + divergence recording

---

## Authoritative readiness signal

| Option | Description | Selected |
|--------|-------------|----------|
| ownership_inspection primary, guard supplementary | ready-for-approval gated by inspector_status=ok AND match=true; old guard must just not be circuit-open/hard-fail | ✓ |
| Both must be fully clean | Require both ownership_inspection and route_management.guard.status=ok | |
| You decide | Let research pick from live :9102/health | |

**User's choice:** ownership_inspection primary, guard supplementary
**Notes:** Aligns with 259-CONTEXT's explicit statement that `match` is Phase 260's primary discrepancy signal. Decouples the verdict from a legacy guard signal that may not have been cleared by 258.

### Follow-up: transient-blip strictness

| Option | Description | Selected |
|--------|-------------|----------|
| Any blip forces not-ready | Every sampled refresh must be status=ok AND match=true; one bad sample → not-ready | ✓ |
| Require clean first+last, tolerate transient | Clean at start/end, record mid-window blips without auto-fail | |
| You decide | Planner picks strictness | |

**User's choice:** Any blip forces not-ready
**Notes:** A transient inspection failure right before a route-owner canary is exactly what must surface. Consistent with prefer-not-ready-when-mixed.

---

## Observation mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Repeatable harness script | scripts/phase260-observation.py (259-proof pattern): validate, sample over window, scan mutation tokens, render packet, emit verdict | ✓ |
| One-shot manual like 257 | Manual split-foreground sleep+sample, hand-written packet | |
| You decide | Planner chooses | |

**User's choice:** Repeatable harness script
**Notes:** Observation recurs before any future canary; Kevin prefers durable procedures. Avoids 257's flaky background-process supervision.

### Follow-up: live-inventory source

| Option | Description | Selected |
|--------|-------------|----------|
| Health + independent RouterOS cross-check | Sample ownership_inspection AND take one allowlist-validated direct read-only RouterOS inventory; assert agreement | ✓ |
| Health endpoint only | Trust ownership_inspection as single live source | |
| You decide | Planner chooses | |

**User's choice:** Health + independent RouterOS cross-check
**Notes:** Defense-in-depth on the pre-canary gate; catches a stale/buggy cached inspector. Reuses the 258-proven REST path.

---

## Intent-comparison depth

| Option | Description | Selected |
|--------|-------------|----------|
| Render standing per-route intent vs live, no forced action | Render active_owner + reconciliation route targets/distances vs live default_routes[]; divergence = per-route mismatch | ✓ |
| Steady-state only (match boolean) | Record last_intended_action=null + match=true only (vacuously clean) | |
| Force a failover scenario | Drive a non-null intended action | |

**User's choice:** Render standing per-route intent vs live, no forced action
**Notes:** Makes OBSERVE-02 meaningful without mutation. Forcing a failover on the production steering host borders SAFE-21 and was rejected.

---

## Window + divergence recording

| Option | Description | Selected |
|--------|-------------|----------|
| Carry forward ~10 min | Match 257's ~636s window (~10 samples at 60s refresh) | ✓ |
| Extend to ~15-20 min | Longer soak for more samples | |
| You decide | Planner picks duration | |

**User's choice:** Carry forward ~10 min
**Notes:** Divergence taxonomy was already settled by Areas 1+3: union of (a) inspector blip, (b) per-route intent mismatch, (c) health/RouterOS cross-check disagreement. Only window length remained open.

## Claude's Discretion

- Exact harness CLI/flags, evidence filenames + timestamp convention, sampling interval within the window, test-slice composition, and per-route comparison rendering — bounded by SAFE-21, D-01, D-02, D-04.

## Deferred Ideas

- Active route-management canary — separate future milestone, gated behind explicit operator approval after ready-for-approval. Out of scope (SAFE-21).
- Netwatch retirement / route-owner flip — out of scope until a successful canary.
- Route-ownership-failover todo (`2026-06-18-...`) — only the readiness/observation slice folded; ownership transfer deferred.
