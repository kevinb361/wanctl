---
phase: 244
reviewers: [codex]
review_cycle: 2
reviewed_at: 2026-06-18T21:34:45Z
plans_reviewed:
  - 244-01-safe17-and-contract-scaffold-PLAN.md
  - 244-02-autorate-attribution-PLAN.md
  - 244-03-steering-attribution-PLAN.md
  - 244-04-bridge-attribution-PLAN.md
cycle1_high: 2
cycle2_high_unresolved: 0
---

# Cross-AI Plan Review — Phase 244 (Cycle 2)

> Single external reviewer: **Codex** (`--codex`, codex-cli 0.141.0). Gemini not installed;
> Claude skipped for independence (review invoked from inside Claude Code). Codex is a
> distinct CLI, so the independence requirement is satisfied.
>
> **Cycle 2 re-review.** Cycle 1 raised 2 HIGH concerns; the plans were revised to address
> them. This cycle judges whether those HIGHs are genuinely closed and whether the revisions
> introduced any new HIGH. Codex verdict: **both cycle-1 HIGHs FULLY RESOLVED, zero remaining
> or newly-introduced HIGHs.** Orchestrator independently verified the load-bearing codebase
> facts before the review (see Verification Notes).

## Codex Review

### Summary

No remaining or newly introduced HIGH concerns. The revised plans genuinely close both
cycle-1 HIGHs at the design level, with explicit guardrails and tests for the two attribution
failure modes. The remaining issues are execution-quality concerns: tighten one steering test
instruction so it cannot false-pass via a health-builder-only path, and make the autorate
contract snapshot unambiguously pin all existing measurement keys.

### HIGH-1 Verdict: FULLY RESOLVED

The revised 244-03 plan fixes the steering misattribution risk.

Evidence:

- Steering attribution is derived from the actual `rtt_source.current`, not stamped globally
  (244-03 truths, line 16).
- `_WANCTL_BACKEND_RTT_SOURCES` is an empty pre-245 frozenset, so existing sources
  `autorate_health`, `autorate_irtt`, `history_fallback`, `unknown`, `unavailable` all emit
  null attribution (244-03 line 17, line 112).
- The derivation rule only emits `producer="wanctl-backend"` inside the seam-source branch
  (244-03 line 121).
- The negative test covers all pre-245 source strings even when `_rtt_source_ip` and
  `_rtt_backend_active` are non-null (244-03 line 280).
- The positive monkeypatched sentinel proves the gate is live, not dead code (244-03 line 287).

Local source facts match the premise: current steering source strings are autorate/history/
unavailable only (daemon.py:1756); the `/health` `rtt_source` block is built from
`_current_rtt_source` (daemon.py:1425).

### HIGH-2 Verdict: FULLY RESOLVED

The revised 244-02 plan fixes the nonexistent-handle-field bug.

Evidence:

- The plan explicitly forbids `getattr(rtt_backend_status, "source_ip", None)` and requires
  `rtt_backend_status.controller_measurement.source_ip` (244-02 line 56).
- The implementation task repeats the correct accessor under a None-handle guard (244-02 line 154).
- The verify step greps for the correct accessor and rejects the bad pattern (244-02 line 181).

Local source confirms the premise: `RttBackendHandle` has no `source_ip` field
(rtt_backend_factory.py:90); `RTTMeasurement.source_ip` is real (rtt_measurement.py:172).

### Remaining Concerns

- **MEDIUM — Tighten the HIGH-1 negative test wording so it must exercise daemon
  `get_health_data()`.** 244-03's acceptance criteria are strong, but the action text also
  allows "the `_make_health_data + builder path`" (244-03 line 302). A builder-only test could
  miss a daemon-side unconditional stamp. Require the negative test to set `_current_rtt_source`,
  `_rtt_source_ip`, and `_rtt_backend_active` on a daemon/path object and assert the output of
  daemon `get_health_data()` *before* the health.py pass-through.

- **MEDIUM — Autorate contract snapshot wording is inconsistent about "exact existing
  measurement keys."** 244-01 says exact keys/order are pinned, but the autorate task lists only
  six fields (244-01 line 280). The actual builder returns additional existing keys —
  `active_reflector_hosts`, `successful_reflector_hosts`, `state`, `successful_count`, `stale`
  (health_check.py:520). Plan 02's interface already knows the full list (244-02 lines 116-118),
  so align Plan 01's acceptance to pin the full existing key list.

- **LOW — Autorate no-handle fallback can still produce a backend-looking value.** 244-02 sets
  the new `backend` to `backend_active`, which defaults to `"icmplib"` when `_rtt_backend_status`
  is None. Production `autorate_continuous` does pass the handle, so this is not a production
  HIGH. For strict attribution, consider emitting `backend=None` when the handle is absent while
  preserving the existing `backend_active` default for compatibility.

### Risk Assessment

Overall risk is **low-to-medium** and acceptable for execution. The important spoofing risks are
addressed: steering cannot label autorate/history RTT as `wanctl-backend`, autorate gets
`source_ip` from the real measurement object, and the bridge emits an honest non-A/B producer /
null backend. The main risk is implementation drift from ambiguous test wording, not a remaining
design flaw.

---

## Verification Notes (orchestrator, pre-review)

Before invoking Codex, the orchestrator confirmed the load-bearing codebase facts the two fixes
depend on, against current source:

- `RttBackendHandle` (rtt_backend_factory.py:90-101) fields are `backend, controller_measurement,
  backend_active, fell_back, fallback_count, fping_cadence_sec, _logger, _wan_key` — **no
  `source_ip`** (HIGH-2 premise true). `controller_measurement` is an `RTTMeasurement` whose
  `.source_ip` is set at construction (rtt_measurement.py:172) — the 244-02 accessor is real.
- Steering `rtt_source.current` literals are exactly `autorate_health` / `autorate_irtt` /
  `history_fallback` / `unavailable` / `unknown` (daemon.py:1159-1166, 1760, 1764, 1799); none
  route through the wanctl `RttBackend` seam (HIGH-1 premise true).
- `_create_steering_components` computes `source_ip` locally (daemon.py:2555) and drops it at the
  4-tuple return (daemon.py:2571) — the 244-03 carry-spine targets the real discard point.

The empty `_WANCTL_BACKEND_RTT_SOURCES` frozenset structurally bars every pre-245 current source
from the `wanctl-backend` bucket — the fix is structural, not merely a runtime guard.

---

## Consensus Summary

Single reviewer (Codex); "consensus" reflects Codex findings weighted against the locked
Phase 244 design decisions (D-01..D-05) and the orchestrator's source verification.

### Cycle-1 → Cycle-2 HIGH resolution

| Cycle-1 HIGH | Cycle-2 verdict |
|---|---|
| HIGH-1 — steering attribution could mislabel bridge/autorate/history RTT as `wanctl-backend` | **FULLY RESOLVED** — empty `_WANCTL_BACKEND_RTT_SOURCES` seam-gate + negative test + live-gate positive test; orchestrator-verified premise |
| HIGH-2 — autorate `source_ip` read from non-existent `RttBackendHandle.source_ip` | **FULLY RESOLVED** — reads `controller_measurement.source_ip`; anti-pattern grep-forbidden; orchestrator-verified premise |

### Agreed Strengths

- Attribution derived from the actual current source / real measurement object, not stamped —
  `backend` structurally never lies (D-02 upheld on all three surfaces).
- Negative + positive (monkeypatched-sentinel) tests prove the steering gate is correct AND live.
- Verifier-first Wave 0 sequencing; SAFE-17 anchor `49fb1393`; narrow additive file scope, no
  controller algorithm/timing edits.

### Remaining Concerns (none HIGH)

1. **MEDIUM** — HIGH-1 negative test should be pinned to daemon `get_health_data()`, not a
   builder-only path (244-03 line 302).
2. **MEDIUM** — Plan 01 autorate contract snapshot should pin the FULL existing measurement key
   list (not just six), matching health_check.py:520 / 244-02 lines 116-118.
3. **LOW** — Optionally emit autorate `backend=None` on the no-handle path instead of the
   `backend_active="icmplib"` default (non-production, strict-attribution nicety).

### Divergent Views

None — single reviewer.

### Recommended Action

No HIGH concerns remain. The two MEDIUMs are minor plan-wording tightenings (test-path pinning,
full key-list pinning) that the executor can fold without re-planning; the LOW is optional. Phase
244 is **clear to execute**. Folding the two MEDIUMs via `/gsd:plan-phase 244 --reviews` (or
directly during execution) is recommended but not blocking.
