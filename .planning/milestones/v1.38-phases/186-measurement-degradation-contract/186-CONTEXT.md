# Phase 186: Measurement Degradation Contract - Context

**Gathered:** 2026-04-15
**Status:** Ready for planning
**Owns requirements:** MEAS-01, MEAS-03

<domain>
## Phase Boundary

Define and expose an explicit, machine-readable measurement-health contract on
autorate `/health` that distinguishes healthy current RTT from degraded or
stale reflector measurement. The phase delivers the contract surface only —
it does not change controller behavior on degraded measurement (that is
Phase 187) and does not run operator verification (that is Phase 188).

Scope in:
- Audit of the current measurement-collapse path (plan 186-01)
- New health fields that expose reflector quorum and staleness (plan 186-02)
- Contract-level regression tests for the new surface (plan 186-03)

Scope out:
- Any change to how the controller reacts to degraded measurement
- Any change to background RTT cache behavior (Phase 187)
- Any CAKE threshold retuning (out of scope for v1.38 milestone)
- Operator runbook updates (Phase 188)

</domain>

<decisions>
## Implementation Decisions

### State Taxonomy (MEAS-01)

- **D-01:** The contract exposes three fields inside the existing
  `wan_health[wan].measurement` block:
  - `state: "healthy" | "reduced" | "collapsed"` — named bucket for
    downstream pattern-matching
  - `successful_count: int` — raw count of reflectors that produced a
    successful measurement in the most recent background RTT cycle
  - `stale: bool` — orthogonal flag for measurement age vs cadence
- **D-02:** State boundaries assume the production 3-reflector configuration
  and are derived from `successful_count`:
  - `healthy` when `successful_count == 3`
  - `reduced` when `successful_count == 2`
  - `collapsed` when `successful_count <= 1`
  Treating `1` as `collapsed` matches the live `tcp_12down` evidence where a
  single surviving reflector produced wildly divergent RTT samples. A single
  reflector is not a quorum.
- **D-03:** The three fields are independent. `state` is derived only from
  the current cycle's success count. `stale` is derived only from age vs
  cadence. A measurement can be `state="healthy"` and `stale=true`
  simultaneously (stale healthy quorum) — downstream code must handle the
  cross-product, not assume a single-axis severity.

  **Cross-product cardinality:** There are exactly **6 legal contract
  combinations** — 3 states × 2 stale values. The `successful_count`
  boundary over `{0, 1, 2, 3}` is a **separate boundary partition** (not a
  third axis): `count == 0` and `count == 1` both map to `state="collapsed"`
  per D-02, so they are partitions within the `collapsed` state, not
  distinct contract combinations. Downstream tests should cover the 6
  cross-product combinations explicitly AND separately parameterize over
  the 4-value `successful_count` boundary. Conflating the two is a
  terminology error that will propagate into test naming.
- **D-04:** The named `state` buckets are intentionally coarse (3 states,
  not 4). Splitting `reduced` from `degraded` is deferred until Phase 187
  proves it needs the distinction for controller branching. The raw
  `successful_count` is always present for consumers that want finer
  granularity without waiting on a contract revision.

### Staleness Rule (MEAS-03)

- **D-05:** `stale` is `true` when the age of the last raw RTT sample
  exceeds `3 × rtt_cadence_sec`. The multiplier matches the existing
  fusion-staleness pattern in `src/wanctl/health_check.py:475`
  (`_age <= _cadence * 3`) — the contract reuses the project's existing
  "missed three expected cycles" convention.
- **D-06:** No new YAML tunable is added for the staleness threshold.
  Deriving from cadence keeps the contract self-adjusting and matches the
  v1.38 milestone constraint that no new tuning surfaces be introduced.
- **D-07:** The `stale` flag uses the existing `staleness_sec` age source
  (`time.monotonic() - _last_raw_rtt_ts` at `src/wanctl/wan_controller.py:3375`).
  Semantics of `staleness_sec` itself are unchanged — see D-11.
- **D-13:** Cadence value is sourced from the WAN controller's existing
  `_cycle_interval_ms / 1000.0` when building `health_data["measurement"]`
  — NOT by adding a new public accessor on `BackgroundRTTThread`. This is
  a correction from review feedback: `src/wanctl/rtt_measurement.py` must
  NOT be modified. The controller already owns cadence (it is constructor
  input), so threading cadence through the existing `health_data` dict at
  `src/wanctl/wan_controller.py:3373` keeps the change surface limited to
  `health_check.py` and `wan_controller.py`. Widening the
  `BackgroundRTTThread` public API for a read-only value the controller
  already has is unnecessary change surface in a stability-first system.
- **D-14:** If cadence is unavailable or non-positive at the moment
  `_build_measurement_section` runs (e.g., startup before the first
  background RTT cycle, or thread failure), the `stale` field defaults
  to `true` — NOT `false`. Rationale: an unknown cadence means the
  freshness window cannot be computed, which is itself a degraded
  measurement signal. Defaulting to `false` would silently mask
  startup-window or post-failure conditions. This is an explicit
  contract decision per review feedback, not an implementation fallback.
- **D-15:** `successful_count` is documented in the contract as
  `int >= 0`, with the current 3-reflector deployment implying a
  practical range of `[0, 3]`. The range is NOT enforced by `_build_...`
  — it is derived from `len(successful_reflector_hosts)` and trusts the
  producer. Tests cover `range(0, 4)` as the practical deployment
  boundary, but the contract itself permits any non-negative integer so
  that future N-reflector configurations do not require a contract
  revision.

  **Current code behavior under `count >= 4`:** The 186-02 state mapping
  uses `if count == 3: healthy; elif count == 2: reduced; else: collapsed`.
  Under the current 3-reflector deployment, `count >= 4` cannot occur,
  so this fallback is unreachable in practice. If a future deployment
  increases the reflector pool to 4+, the current `else` branch would
  silently map `count == 4` to `collapsed`, which is semantically wrong
  (more successful reflectors, not fewer). This is an **accepted
  implementation posture under today's deployment assumption**, not a
  forward-compatible invariant. A future milestone that adds a 4th
  reflector MUST amend this phase's contract (either extend the state
  taxonomy or redefine the mapping) before landing the deployment
  change. Tests do not cover `count >= 4` because exercising unreachable
  code would lock in wrong semantics.
- **D-16:** `_build_measurement_section` MUST be resilient to
  `successful_reflector_hosts=None` (and to the key being absent). The
  implementation coerces a missing or `None` value to an empty list
  before computing `successful_count`, producing `successful_count=0`
  and `state="collapsed"`. This aligns the stated threat-model claim
  ("malformed `health_data` does not raise") with actual code behavior.
  A contract test in 186-03 pins this coercion.

### Payload Placement

- **D-08:** The new fields are added to the existing
  `wan_health[wan].measurement` block built by
  `_build_measurement_section` at `src/wanctl/health_check.py:383`. No new
  sibling section is created. One section continues to own all
  measurement-domain fields, and existing dashboards/alerts keep reading
  the same path.
- **D-09:** `reflector_quality` (built by `_build_reflector_section`,
  `src/wanctl/health_check.py:396`) stays unchanged. It exposes per-host
  scoring for operator drill-down; it is orthogonal to the new cycle-level
  quorum contract and must not be overloaded with collapse semantics.

### Backwards Compatibility

- **D-10:** All existing fields in the `measurement` block are preserved
  verbatim with unchanged semantics:
  `available`, `raw_rtt_ms`, `staleness_sec`, `active_reflector_hosts`,
  `successful_reflector_hosts`. The new contract is strictly additive.
- **D-11:** `staleness_sec` continues to mean "age since last raw RTT
  sample" and is NOT redefined as "age since last successful quorum."
  Redefinition would silently break any dashboard or alert currently
  reading the field. The new `stale` boolean subsumes the health signal
  without touching existing semantics.
- **D-12:** The existing `available` field is intentionally kept but will
  be noted in docs/comments as coarser than `state`. Deprecation, if any,
  is not part of this phase and must be proposed as its own milestone
  decision. No consumer-visible changes.

</decisions>

<claude_discretion>
## Claude's Discretion

The user chose to defer these to planner/researcher judgment. Planner must
adopt the positions below unless research surfaces a specific reason to
deviate, in which case the deviation must be documented in the plan.

- **Audit deliverable shape (plan 186-01).** The audit is captured inline
  in `186-01-PLAN.md` as an explicit "Collapse Path Audit" section that
  enumerates each call site where raw reflector success is counted, where
  `staleness_sec` is surfaced, and where the current code silently reuses
  stale RTT as healthy. No separate AUDIT.md file. The audit section is
  the plan's first task, and its output locks the exact code paths plan
  186-02 must modify. Keeping the audit inside the plan avoids an extra
  artifact to maintain and keeps the audit findings version-pinned to the
  plan that consumes them.

- **Contract test scope (plan 186-03).** Tests are pure and layered in
  this order:
  1. Unit tests on `_build_measurement_section` that drive it with a
     crafted `health_data` fixture covering all **six** legal
     `(state × stale)` contract combinations (3 states × {stale, fresh})
     and assert exact field values. Parametrization is encouraged for
     clarity. The cross-product cardinality is exactly 6 per the D-03
     amendment; any additional tests for `successful_count` variants
     within `collapsed` belong in the boundary partition (item 2), not
     in this cross-product matrix.
  2. Boundary partition tests that verify `successful_count == 3 → "healthy"`,
     `== 2 → "reduced"`, `== 1 → "collapsed"`, `== 0 → "collapsed"`,
     and that the taxonomy is exhaustive over `range(0, 4)`. This is
     a partition WITHIN `collapsed` (count 0 and 1 both map to the same
     state), not a third axis of the cross-product.
  3. One focused test that staleness flips exactly at
     `age == 3 * cadence` (open/closed interval matching existing
     fusion behavior — inclusive lower, exclusive upper per
     `health_check.py:475`).
  4. Defensive tests per D-14 (stale=True on missing/non-positive
     cadence) and D-16 (None-coerced host lists → count=0, state=collapsed).
  End-to-end HTTP fetch tests are NOT added — existing
  `tests/test_health_check.py` coverage already proves the HTTP wiring and
  payload round-trip; adding another layer would duplicate coverage
  without raising confidence in the new contract fields specifically.

- **Staleness reference point.** The `stale` flag is computed from the
  same `_last_raw_rtt_ts` timestamp that already backs `staleness_sec`.
  This is consistent with D-11 (existing field semantics preserved) and
  avoids introducing a second "age of last successful quorum" timestamp
  that 187 may or may not want. If Phase 187 decides it needs the
  quorum-age timestamp, it can add it additively without breaking the
  186 contract.

</claude_discretion>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Definition

- `.planning/ROADMAP.md` — Phase 186 entry (goal, plan outline, depends-on
  chain into Phases 187 and 188)
- `.planning/REQUIREMENTS.md` — MEAS-01 (reflector quorum machine-readable)
  and MEAS-03 (explicit degraded surfacing on `/health`)
- `.planning/PROJECT.md` — milestone vision and v1.38 scope
- `.planning/STATE.md` — current milestone position

### Source Files (read before modifying)

- `src/wanctl/health_check.py:383` — `_build_measurement_section`, the
  exact function that plan 186-02 augments
- `src/wanctl/health_check.py:396` — `_build_reflector_section`, MUST
  stay untouched (D-09)
- `src/wanctl/health_check.py:475` — existing `_age <= _cadence * 3`
  fusion-staleness pattern that D-05 reuses verbatim
- `src/wanctl/wan_controller.py:3360-3382` — source data for the
  measurement block (`_last_raw_rtt`, `_last_raw_rtt_ts`,
  `_last_active_reflector_hosts`, `_last_successful_reflector_hosts`)
- `src/wanctl/wan_controller.py:858` — `start_background_rtt` wiring
  into `BackgroundRTTThread`; cadence is passed in from
  `self._cycle_interval_ms / 1000.0`. Per D-13, cadence is sourced HERE
  (controller side) when threading into `health_data["measurement"]`.
  `src/wanctl/rtt_measurement.py` and `src/wanctl/interfaces.py` must
  NOT be modified to expose a `cadence_sec` accessor on the thread.

### Test Surface

- `tests/test_health_check.py` — existing coverage of HTTP wiring and
  payload contract; new unit tests in plan 186-03 should match its
  fixture style
- `tests/test_wan_controller.py` — reference for mocking
  `_last_*_reflector_hosts` state when crafting fixtures

### Prior Context

- `.planning/phases/185-verification-and-operator-alignment/185-CONTEXT.md`
  — prior-phase pattern for contract-style phases (layered regression,
  repo-side closeout)

</canonical_refs>

<specifics>
## Specific Ideas

- The live `tcp_12down` reproduction is the single load-bearing evidence
  for the D-02 "collapsed includes count == 1" boundary. Any research
  agent looking for threshold justification should trace back to the
  original investigation rather than re-deriving from first principles.
- The `state` field name is deliberately `state` (not
  `measurement_state` or `health`) to keep the additive field short
  under the existing `measurement` block. Full qualified path is
  `wan_health[wan].measurement.state`.

</specifics>

<deferred>
## Deferred Ideas

- **ALRT-01** (dedicated alert path for sustained measurement-quality
  collapse) — explicitly deferred in REQUIREMENTS.md as a v2 follow-on.
  Phase 186 must NOT add alert routing; that is post-milestone work
  contingent on v1.38 proving the passive surface is insufficient.
- **ANLY-01** (richer historical reporting for reflector-collapse
  episodes) — v2 follow-on. Out of scope.
- **Four-state taxonomy** (splitting `reduced` from `degraded`) —
  considered and rejected for 186 (D-04). Reopen if Phase 187 branching
  requires it.
- **Audit deliverable as a standalone AUDIT.md** — considered and
  rejected in favor of inline plan section.
- **End-to-end HTTP fetch tests for the new contract** — considered and
  rejected; existing `test_health_check.py` HTTP coverage is sufficient.
- **Redefinition of `staleness_sec` semantics** — explicitly rejected
  (D-11) because it would silently break existing consumers.

</deferred>

---

*Phase: 186-measurement-degradation-contract*
*Context gathered: 2026-04-15 via /gsd-discuss-phase*
