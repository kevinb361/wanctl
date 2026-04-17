---
phase: 187
reviewers: [codex]
reviewed_at: 2026-04-15T00:00:00Z
plans_reviewed: [187-04-PLAN.md]
scope: gap_closure_only
---

# Cross-AI Plan Review — Phase 187 Gap Closure (187-04)

**Scope note:** Only `187-04-PLAN.md` was reviewed. Plans 187-01, 187-02, and 187-03 are shipped and verified (4/5 truths passed in VERIFICATION.md); this review targets the gap-closure plan that closes Truth #5.

## Codex Review

### Summary

`187-04-PLAN.md` is narrowly scoped and, on its face, closes Truth #5: it adds producer-side regression coverage in `tests/test_rtt_measurement.py`, exercises `BackgroundRTTThread._run()` rather than mocking `get_cycle_status()`, and covers all three missing verification items: pre-cycle `None`, zero-success status publication without overwriting `_cached`, and successful-cycle status reflection. Main caveat: a few assertion details look slightly underspecified or brittle — treat this as a good plan that needs minor tightening rather than a finished one.

### Strengths

- Tests live in `tests/test_rtt_measurement.py`, the producer-side contract that VERIFICATION says is missing.
- Plan explicitly forbids mocking `get_cycle_status()` and direct assignment to `_last_cycle_status`, preserving authenticity.
- Calling `thread._run()` is the correct target — exact site where `_last_cycle_status` is published.
- Zero-success case explicitly protects the Phase 132 invariant that stale cache is preserved on failed cycles.
- "Before first cycle" test closes the first-cycle `None` sentinel gap directly instead of inferring it indirectly.
- Scope discipline is good: tests-only, single file, no fixture churn, no source edits.
- `depends_on: [187-01]` is correct — the gap exists at the producer layer introduced in 187-01, does not logically depend on 187-02 / 187-03.

### Concerns

- **MEDIUM** — Successful-cycle test says `successful_hosts == {...}`. The contract field is a tuple, so a set comparison is either wrong or too vague. Test should pin either exact tuple order or compare `set(status.successful_hosts)` intentionally.
- **MEDIUM** — The cross-check `status.active_hosts == thread.get_latest().active_hosts` may be weaker or more brittle than necessary. If `RTTSnapshot` does not expose `active_hosts` in that exact shape, this becomes accidental fragility unrelated to Truth #5.
- **LOW** — The `patch("wanctl.rtt_measurement.concurrent.futures.wait") + wait_then_stop` harness is legitimate for a one-iteration `_run()` test, but only if the stop happens after the publish site. If the helper is poorly implemented, the loop could terminate before a full cycle and create a misleading test shape.
- **LOW** — Plan only uses an all-success example for the successful path. Satisfies the stated verification gap but does not specifically prove `successful_hosts` and `successful_count` remain accurate on partial success.
- **LOW** — Zero-success test says `_cached is known_snap`. Good, but should also ensure the old snapshot is non-`None` and structurally distinguishable from the cycle under test so the preservation claim is unambiguous.

### Suggestions

- Tighten successful-cycle assertions to exact contract checks:
  - `status.successful_hosts == (...)` or `set(status.successful_hosts) == {...}` explicitly
  - Avoid relying on `thread.get_latest().active_hosts` unless already an established test surface.
- In the zero-success test, assert both `thread._cached is known_snap` AND `thread.get_latest() is known_snap` — makes the non-overwrite guarantee explicit at the public accessor too.
- Optional hardening: make the "successful cycle" scenario partial success (`2/3`) instead of `3/3`. Better proves the producer publishes current-cycle fields rather than mirroring the input host list.
- Spell out in the plan that one cycle executes fully before `shutdown_event` is observed on the next loop boundary — removes ambiguity about whether the publish site can be skipped.

### Risk Assessment

**LOW** — Conservative tests-only plan with the right file, right class, right execution path. Only meaningful risk is test-quality drift from imprecise assertions or a slightly opaque one-iteration harness. Tighten those details and the plan should fully close the verification gap without hidden source-file risk.

---

## Consensus Summary

Single reviewer (Codex). Verdict: **LOW RISK, minor tightening recommended**. Plan closes all three VERIFICATION.md `missing:` items and respects the no-source-edit constraint. Key actionable items (all MEDIUM or lower severity):

### Recommended tightening before execution

1. **MEDIUM — Clarify `successful_hosts` comparison type.** The plan uses `set(status.successful_hosts) == {...}` followed by `len(...)` — acceptable but should be explicitly intentional. Either pin tuple order or keep the set-based comparison with a comment.
2. **MEDIUM — Reconsider `status.active_hosts == snap.active_hosts` cross-check.** `RTTSnapshot` must actually expose `active_hosts` as a tuple for this to be non-brittle. Verify against live source; if not stable, drop the cross-check (the direct `status.active_hosts == ("8.8.8.8", ...)` assertion already carries the contract).
3. **LOW — Add `thread.get_latest() is known_snap` witness** to the zero-success test alongside the existing `thread._cached is known_snap` — tightens the non-overwrite guarantee at the public accessor.
4. **LOW (optional) — Partial-success variant.** Consider a `2/3` variant of the successful-cycle test to better distinguish "publisher mirrors hosts_fn input" from "publisher reflects cycle outcome."

### Non-actionable (plan already handles)

- Producer authenticity (no mocking of `get_cycle_status()`) — enforced by acceptance criteria.
- Tests-only scope (`git diff src/wanctl/` empty) — enforced by acceptance criteria.
- Dependency correctness (`depends_on: [187-01]`) — confirmed correct.
- Gap completeness (all 3 missing items addressed) — confirmed.

### Divergent views

N/A (single reviewer).

---

**Next step:** Either execute as-is (low risk) or run `/gsd-plan-phase 187 --reviews` to have the planner incorporate the MEDIUM concerns above into a revised 187-04-PLAN.md before execution.
