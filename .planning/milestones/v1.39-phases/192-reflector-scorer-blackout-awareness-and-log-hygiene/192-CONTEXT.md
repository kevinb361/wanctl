# Phase 192: Reflector Scorer Blackout-Awareness + Log Hygiene — Context

**Gathered:** 2026-04-23
**Status:** Ready for planning
**Decision-maker:** Codex (delegated via user directive "you make decisions with codex"). Claude adjudicated D-08 follow-up (labeling error) and verified health-metric paths against the codebase.

<domain>
## Phase Boundary

Two narrow accounting/observability fixes in the Spectrum measurement pipeline, plus one soak gate:

1. Stop the per-host reflector scorer from decrementing quality windows during all-host zero-success (blackout) cycles. The bug is at the caller boundary in `wan_controller.py`, not in scorer logic.
2. Reduce `Protocol deprioritization detected` INFO log volume on Spectrum when fusion is not actionable (`disabled` or `healer_suspended`), while preserving first-occurrence and real protocol-ratio transition events.
3. 24-hour post-merge soak verifies no regression in three Phase-192-adjacent subsystems: dwell-bypass path, burst detection, fusion healer.

No control-path behavior change. No threshold/alpha/dwell/deadband/burst-detection/state-machine edits (SAFE-03). Cached-RTT fallback semantics preserved verbatim.

</domain>

<decisions>
## Implementation Decisions

### Scorer Blackout Accounting

- **D-01: Caller-side blackout gate.** The fix lives in `wan_controller.py` at the two sites that feed the scorer (L973 `_measure_rtt_background`, L1065 `_measure_rtt_blocking`). When `cycle_status.successful_count == 0`, skip the `self._reflector_scorer.record_results(...)` call entirely. Scorer API, blocking path, and probe path remain untouched.
  **Why:** The bug is at the seam — the background thread intentionally reuses the stale `RTTSnapshot` on zero-success cycles, which means the current unconditional `record_results` call is actually feeding *previous-cycle* per-host data back into the rolling windows. Gating at the caller fixes it exactly where the staleness originates.

- **D-02: Strict blackout definition.** Blackout = `RTTCycleStatus.successful_count == 0` for the current cycle, full stop. No broader heuristics, no "zero among non-deprioritized" edge cases.
  **Why:** `BackgroundRTTThread` publishes `RTTCycleStatus` every cycle (Phase 187) specifically to distinguish a current-cycle all-fail collapse from the cached snapshot. Anything broader would silently change scoring behavior and mask partial-failure evidence we still want to see.

- **D-03: Probe results still count.** `maybe_probe()` outcomes continue to score normally, including failures, during an active path blackout.
  **Why:** Probe traffic is fresh, per-host evidence generated after deprioritization — it is the scorer's recovery-validation mechanism. Suppressing it would weaken an already-conservative safety model. Blackout suppression applies only to the stale-cached-snapshot replay path.

### Log Hygiene

- **D-04: Fusion-aware cooldown.** Add a separate, long cooldown branch for the `Protocol deprioritization detected` INFO emission that activates only when fusion is effectively not actionable. Leave the existing normal-mode cooldown unchanged. Do *not* demote the log level globally.
  **Why:** Demoting INFO→DEBUG would hide real transitions when fusion *is* active; stretching the single global cooldown would blunt useful logs in active-fusion windows. A fusion-aware branch attacks the Spectrum flood without touching thresholds, dwell, or normal observability.

- **D-05: Direct fusion-state read at log site.** The log emission in `wan_controller.py:1564` reads `self._fusion_healer.state` (and `_fusion_enabled`) inline to decide which cooldown to apply. No cached mirror attribute.
  **Why:** The state is already an in-memory enum lookup. Caching it would add synchronization surface for zero operational benefit in a 50ms loop.

- **D-06: Preserve ratio-crossing semantics for the protocol log.** The protocol-correlation log latch is driven only by protocol-ratio threshold crossings (deprioritized ↔ normal). FusionHealer state transitions emit their own separate logs and must *not* reset the protocol latch.
  **Why:** Coupling healer transitions into the protocol latch would create duplicate narratives and let fusion oscillation re-arm the INFO spam path — defeating the whole point.

### Test Strategy

- **D-07: Unit tests + one integration test at the seam.** Keep the scope-listed scorer unit tests (all-host-fail, partial-success, recovery after blackout, mixed quality drops). Add one integration test that wires `WANController.measure_rtt()` with a real `ReflectorScorer` and a synthetic `RTTCycleStatus(successful_count=0)` to prove a zero-success cached cycle does not mutate per-host windows.
  **Why:** The regression is a cross-object interaction (controller stale-replay × scorer decrement), not a scorer-logic-in-isolation bug. A seam-level test is the stable guardrail. Also: add/extend a unit test on the fusion-aware log cooldown path (normal cooldown vs suspended cooldown vs state-transition).

### Soak Gate (VALN-03, 24h post-merge)

- **D-08: Three-category regression guard with operator-captured baselines.** Baselines are not yet recorded in the repo — the operator captures a 24h `pre` window at soak start and the 24h `post` window becomes the pass/fail input.

  **Category 1 — Dwell-bypass responsiveness.** Metric: `/health` field `download.hysteresis.dwell_bypassed_count` per WAN (24h delta). Pass bar: within ±20% of operator-captured pre-merge baseline per WAN per 24h window.

  **Category 2 — Burst detection trigger count.** Metric: `/health` field `download.burst.trigger_count` per WAN (24h delta); corroborate with the same counter on `upload.burst.trigger_count`. Pass bar: within ±20% of operator-captured pre-merge baseline per WAN per 24h window.

  **Category 3 — Fusion state transitions.** Metric: structured-log count of FusionHealer transition lines (e.g. `grep 'Fusion healer.*->' journal`) plus `/health` `fusion.heal_state` spot checks. Pass bar: no more than 3 transitions per WAN per 24h *and* within ±20% of baseline if baseline is nonzero.

  **Why:** Each category now maps to the actual emitting subsystem (queue_controller dwell path, burst_detection module, fusion_healer) rather than to the protocol-deprioritization INFO stream, which is what Phase 192 is suppressing — the original metric would have made the regression guard self-invalidating. Health paths verified against `health_check.py` (L729 for burst, queue_controller.py L490 for dwell).

### Claude's Discretion

- Exact placement of the fusion-aware cooldown constants (new attrs on WANController vs. YAML-driven) — planner decides based on `config_validation_utils.py` conventions already in use.
- Whether to split Phase 192 into 2 or 3 plans (scorer fix / log hygiene / soak) or fold soak into verification — planner decides based on standard plan decomposition.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — MEAS-05, MEAS-06, OPER-02, SAFE-03, VALN-02, VALN-03 definitions; `## Out of Scope` section for locked-out items.
- `.planning/ROADMAP.md` §"Phase 192" — Phase boundary, scope, out-of-scope, success criteria (4 items).

### Prior-phase artifacts (dependencies)
- `.planning/phases/191-netlink-apply-timing-stabilization/191-VERIFICATION.md` — Phase 191 closure state; Phase 192 soak begins only after Phase 191 closeout per dependency.
- `.planning/phases/191.1-att-config-drift-resolution-and-phase-191-closure/191.1-03-*.md` — ATT config drift closure plans (precondition for soak per roadmap dependency).

### Implementation surfaces
- `src/wanctl/reflector_scorer.py` — target module; public API unchanged per D-01.
- `src/wanctl/wan_controller.py` §`_measure_rtt_background` (L940-1039) and `_measure_rtt_blocking` (L1041-1095) — two caller sites where the blackout gate lands (D-01).
- `src/wanctl/wan_controller.py` §protocol-deprioritization log block (L1540-1591) — log-hygiene target (D-04, D-05, D-06).
- `src/wanctl/rtt_measurement.py` §`BackgroundRTTThread._run` (L470-529) — already publishes `RTTCycleStatus` every cycle including zero-success (Phase 187); D-01 depends on this being honored.

### Observability contract (soak gate metrics)
- `src/wanctl/health_check.py` L645-746 — `/health` JSON shape for `download.hysteresis.*`, `download.burst.*`, `fusion.heal_state`.
- `src/wanctl/queue_controller.py` L490 — `dwell_bypassed_count` counter source.

### Test references
- `tests/test_reflector_scorer.py` (if exists; planner confirms path) — existing scorer unit tests to extend.
- `tests/test_wan_controller.py` — home for the new seam-level integration test per D-07.

### Baselines (operator-captured at soak start — not in repo)
- 2026-04-20 production baseline for Spectrum protocol-log volume (2.5k/day) — cited in ROADMAP success-criteria #3 and #4; soak run must capture equivalent pre-merge counters for the three D-08 categories.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `RTTCycleStatus` dataclass (`rtt_measurement.py`) — already carries `successful_count`, `active_hosts`, `successful_hosts`, `cycle_timestamp`. D-01 consumes the existing type; no schema change.
- Existing zero-success handling pathway in `wan_controller.py:978-1030` (blackout detect → cached-RTT reuse → recovery log) is the pattern to mirror for the scorer gate. Same `cycle_status.successful_count == 0` predicate.
- `_irtt_deprioritization_logged` latch + `_irtt_deprioritization_log_cooldown_sec` at protocol-log site — extend with a fusion-aware branch rather than replace.
- `_persist_reflector_events()` remains wired identically — blackout gate skipping `record_results` naturally skips the event generation path.

### Established Patterns
- Caller-side gating of control-path side-effects when measurement is stale (matches `_record_live_rtt_snapshot` using `snapshot.timestamp` not `time.monotonic()` — D-01 follows the same "honor measurement liveness at the seam" convention).
- Cooldown-guarded INFO + DEBUG fallback already used for protocol deprio and zero-success blackout logging (wan_controller.py L991-1007). Fusion-aware cooldown (D-04) is an extension of this pattern, not a new one.
- Health payload shape is append-only / backward-compatible — D-08 reads existing fields, adds no new ones.

### Integration Points
- Two call sites in `wan_controller.py` (L973, L1065) — both need the same 2-line guard. Factor to a helper if duplication gets ugly; otherwise inline.
- Log site at `wan_controller.py:1564` — single-file edit for D-04/D-05/D-06.
- FusionHealer state read: `self._fusion_healer.state` (FusionHealerState enum) + `self._fusion_enabled`. Both already referenced in `_init_fusion_healer` and the controller.

</code_context>

<specifics>
## Specific Ideas

- Soak metric capture can reuse the `scripts/soak-monitor.sh` pattern referenced in CLAUDE.md; no new tooling required for D-08.
- If planner wants a helper, one internal method `_should_skip_scorer_update(cycle_status)` on WANController captures the D-01 gate with a single point of truth.
- The ±20% tolerance in D-08 is intentionally loose — DOCSIS / DSL baselines have inherent jitter (per memory: suppression rate ~35/min on DOCSIS is inherent, not tunable). Tighter bars would produce false regressions.

</specifics>

<deferred>
## Deferred Ideas

- 4th reflector — explicitly deferred in ROADMAP "Out of Scope" until MEAS-06 proves insufficient after Phase 192.
- Any Python-side learned idle baseline or baseline-freeze for queue delay — belongs to v1.40 Phase 193, not here.
- Richer health schema for scorer blackout state (e.g., expose `in_blackout: bool` under `reflector_quality`) — nice-to-have, not required by Phase 192 success criteria; defer unless operator flags a gap during soak.

</deferred>

---

*Phase: 192-reflector-scorer-blackout-awareness-and-log-hygiene*
*Context gathered: 2026-04-23*
*Decision delegate: Codex (via codex:codex-rescue agent)*
