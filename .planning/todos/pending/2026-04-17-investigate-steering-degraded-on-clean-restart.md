---
created: 2026-04-18T02:11:13.000Z
title: Investigate steering SPECTRUM_DEGRADED on clean restart
area: steering
resolves_phase: 223
files:
  - src/wanctl/steering/daemon.py
  - src/wanctl/state_manager.py
  - /var/lib/wanctl/steering_state.json
---

## Problem

During the 2026-04-17 debug-log restart at 21:05:27, the steering daemon's very first cycle loaded `state['current_state'] = 'SPECTRUM_DEGRADED'` even though the link was healthy (it resolved to `SPECTRUM_GOOD` within ~28s). That means DEGRADED was persisted to `steering_state.json` from the prior run and loaded on fresh start.

Noticed because fire-on-change debug log showed `val=1.0` on cycle 1, which confused the emission-rate audit. Steering auto-recovered fine, so zero production impact, but the state-persistence path may be saving transient degradation events that shouldn't survive a restart — or steering was genuinely DEGRADED right before the restart for a duration too short for any alert to fire.

## Solution

- Inspect `/var/lib/wanctl/steering_state.json` contents just before and just after a controlled restart to confirm DEGRADED persists.
- Check `SteeringStateManager.save()` call sites in `steering/daemon.py` — is it called mid-transition or only on stable state changes?
- Decide whether current_state should only persist GOOD (and always reload in GOOD), or whether preserving DEGRADED is intentional (e.g. to resume steering after a crash mid-degradation). Current behavior may be intentional — worth confirming, not fixing blind.
- If behavior is unintentional, add a health-check gate in daemon startup that reloads DEGRADED only if measurement confirms it.

Low priority. Understanding-level work, not a bug report.

## Spot Check — 2026-05-26

Live snapshot of `/var/lib/wanctl/steering_state.json` at 2026-05-26: `current_state":"SPECTRUM_GOOD","good_count":0`. State file is in healthy `GOOD` at observation moment — no active DEGRADED persistence to inspect right now. Cannot passively verify the restart-DEGRADED hypothesis without a controlled restart while the daemon is in `SPECTRUM_DEGRADED`, which is rare and operator-disruptive to stage.

Keeping as low-pri observation work. Closes either when (a) we happen to catch a restart during a real DEGRADED period and capture state-file pre/post, or (b) someone explicitly stages the test.

## PROOF-02 Closure (Phase 223)

- **Closure date:** 2026-06-02
- **Outcome:** `reproduced-bug`
- **Rationale:** effective_steering remained true during recovery-window cycles [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13] from pre-enabled boot rule; this violates the binary-on/off + autorate-baseline-authoritative spine contract because persisted DEGRADED kept traffic effectively steered before fresh GOOD-consistent measurements recovered the daemon at cycle 14.
- **Evidence:** `.planning/phases/223-staging-proof-clean-restart-reproduction/evidence/clean-restart-reproduction.md`
- **Corpus row:** `.planning/phases/223-staging-proof-clean-restart-reproduction/evidence/replay-results.md`
- **Closure status:** Resolved by Phase 223 PROOF-02 annotation; todo remains in `pending/` for operator-controlled archival.
- **Fix held against Phase 224 pre-canary gate or follow-up phase — NOT landing in v1.48 Phase 223.**
