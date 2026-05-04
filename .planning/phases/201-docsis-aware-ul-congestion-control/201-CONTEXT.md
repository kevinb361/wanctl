# Phase 201: DOCSIS-Aware Upload Congestion Control — CONTEXT (seed)

**Status:** Pre-spec seed. Use `/gsd-spec-phase` or `/gsd-discuss-phase` to take this from seed → SPEC.md → PLAN.
**Origin:** Phase 200 closed FAIL on 2026-05-03 with the per-direction UL thresholds hypothesis rejected. This phase is the gap-closure direction recommended by Plan 06 Task 3 FAIL branch.

> **This file is a seed, not a spec.** It captures the failure evidence and design direction options. Operator should run `/gsd-discuss-phase` next to clarify scope and constraints before any implementation planning.

## Why Phase 201 Exists

Phase 200 tested the hypothesis that per-direction UL `target_bloat_ms=42` and `warn_bloat_ms=105` (vs DL globals 15/75) would prevent UL collapse-to-floor on Spectrum DOCSIS upload at saturation. Production canary on 2026-05-03 recorded **122 UL collapse-to-floor events in 900s** of saturated load (≈1 every 7.4s). Hypothesis REJECTED.

Evidence: `.planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260503T215734Z/`

Sample distribution (886 samples, 1Hz over 900s loaded window):
- **18.0 Mbps ceiling: 470 samples (53%)**
- **8.0 Mbps floor: 122 samples (14%)** — explicit collapse events
- 8.2-17.9 Mbps intermediate decay: 294 samples (33%)

State distribution: GREEN 35%, YELLOW 59%, RED 7%. Bimodal oscillation — controller cycles ceiling ↔ floor rather than settling at an intermediate equilibrium.

## Root Cause Hypothesis (to refine in /gsd-discuss-phase)

UL queue delay during DOCSIS saturation routinely exceeds 200-500 ms regardless of wanctl-imposed shaping rate, because:

1. wanctl's 18 Mbit ceiling is barely below the actual provisioned upstream rate (~20 Mbit), leaving no shaping headroom.
2. The CMTS-side queue (modem upstream) fills before wanctl's CAKE qdisc has a chance to absorb the bufferbloat — wanctl shapes at line rate but the bottleneck is upstream of the wanctl interface.
3. RTT-delta-driven distress detection cannot react fast enough: by the time RTT delta exceeds 105 ms, queue depth at the CMTS is already in the 300-500 ms range; the controller drops to YELLOW or RED, decays to floor, then climbs back to ceiling, repeating the cycle.

The control model assumes shaping rate < link capacity by enough margin that wanctl's qdisc absorbs bufferbloat instead of the modem's queue. **On DOCSIS this margin is too thin** — and getting "thinner" margin (i.e., lower ceiling) sacrifices peak throughput; getting wider thresholds doesn't address the cause.

## Candidate Design Directions

### A. DOCSIS-aware UL congestion mode with low setpoint

**Treat ceiling as guard rail, not target.** Run a setpoint well below ceiling (e.g., 12 Mbit on an 18 Mbit ceiling, 60% of provisioned rate) and only allow ceiling-approach excursions when CMTS queue depth signals headroom. Requires a queue-depth signal, which `/health` doesn't currently expose for upload.

- **Pros:** addresses root cause (insufficient shaping margin); cosistent with how DSL/cable-modem-friendly shapers like SQM handle DOCSIS UL.
- **Cons:** requires operator to accept lower peak UL throughput; adds a new control variable (setpoint).
- **Open questions:** what queue-depth signal? Modem-side (SNMP/HSCD?) or wanctl-side derived from RTT integral?

### B. Substantially lower ceiling

Drop Spectrum UL ceiling 18 → 12-14 Mbit, sacrificing peak throughput for stable latency.

- **Pros:** trivial to implement (YAML-only).
- **Cons:** peak UL drops by 22-33%; still uses RTT-delta which has the latency lag problem; doesn't address the control model.
- **Likely outcome:** reduces collapse frequency but doesn't eliminate it; may oscillate at lower amplitude.

### C. Time-weighted RTT integral instead of RTT delta

Replace the current RTT-delta classifier with an integral-of-RTT-over-time metric to react earlier to slow queue buildup.

- **Pros:** reduces lag without changing the control variable.
- **Cons:** doesn't address the root cause (insufficient shaping margin); risks false positives during legitimate transient RTT excursions.

### D. Hybrid (most likely correct): A + token of B

DOCSIS-aware mode (A) with a YAML-configurable setpoint defaulting somewhere conservative. Operator controls the throughput-vs-latency tradeoff per WAN. Cable modem deployments enable DOCSIS mode; fiber/DSL deployments stay on the existing per-direction-threshold model (which v1.41 made available).

## Constraints to Carry Forward

- **CLAUDE.md "stability > safety > clarity > elegance"**: any new control mode must be guarded by an explicit YAML opt-in flag with a backwards-compatible default. Existing non-Spectrum deployments must remain byte-identical.
- **Portable controller architecture (CLAUDE.md NON-NEGOTIABLE):** new mode lives in YAML, not in Python branching. Code path differences keyed off a config flag.
- **/health payload shape**: do not break existing `.wans[].upload` shape. New fields are additive (operator-driven smoke checks must validate this against real `/health`, per Phase 200 retrospective lesson #1).
- **D-07/D-10 deploy gate**: any new shaping behavior must be testable by a saturation canary with a verdict file. Reuse the Phase 200 canary tooling (now correctly env-var-driven for floor/ceiling).
- **Plan 05 retrospective bugs**: smoke checks for new INFO log lines must include a real-journal grep, not just a JSON fixture; any new env var must be in `phase200-saturation-canary.env.example` + documented in `--help`.

## Pre-Spec Questions for /gsd-discuss-phase

1. Is the right next step a single phase (DOCSIS mode + canary) or a research spike first (`/gsd-spike` to instrument queue-depth signal options)?
2. Is the queue-depth signal source a hard problem? If yes, the spike is required first.
3. Setpoint default: 60% of ceiling, 80%, operator-supplied? What's the principled choice?
4. Does ATT have the same UL bufferbloat pathology, or is this Spectrum-only? The current ATT YAML doesn't carry the v1.41 per-direction threshold keys, so absent-key fallback (D-02) preserves byte-identical ATT behavior. Phase 201 should not regress ATT.
5. Soak strategy: 24h soak after canary PASS, like Plan 07 was supposed to do? Or shorter regression watchdog given DOCSIS oscillation can be sub-hour?

## Inputs Available for /gsd-discuss-phase

- Failure evidence: `.planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260503T215734Z/`
- Phase 200 RETRO: `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-RETRO.md`
- Phase 200 CONTEXT: `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-CONTEXT.md` (DOCSIS-aware UL was deferred from this CONTEXT explicitly)
- Spectrum-specific operator notes:
  - `.planning/spectrum-inline-native-18-upload-test-2026-04-29.md` (Step 4 mentions "upload-specific factor_down gentler than 0.90, smaller step_up_mbps")
  - `.planning/spectrum-upload-ceiling-sweep-2026-04-29.md`
  - `.planning/spectrum-target-bloat-sweep-2026-04-15.md`

## Not in Scope for Phase 201

- DL queue-primary work (covered by v1.40 Phases 193-198).
- Per-direction DL thresholds (Phase 200 D-02 fallback already preserves DL behavior).
- ATT-specific UL changes (Phase 191/191.1 territory).
- Alerting fix for Spectrum YAML severity (separate quick task `260503-cfs`).

## Inherited Requirements

This phase inherits the following Phase 200 requirement under the 2026-05-04 operator-escalation deferral. **VALN-06 is an inherited blocking requirement** — Phase 201's eventual SPEC and PLAN must carry it forward and cannot silently drop it during 201 scoping. Future Phase 201 planning that fails to enumerate VALN-06 in its requirements list must be treated as a planning defect.

| Requirement | Inherited From | Reason | Closure Shape Under Phase 201 |
|---|---|---|---|
| **VALN-06** — Spectrum UL saturation gate (10-15 min `iperf3 -P4` saturated upload loop at the deployed UL ceiling completes with zero loaded-window floor-hit cycles, pre/post idle baselines bookend, 24h regression soak as watchdog) | Phase 200 (`200-VERIFICATION.md` `closure: deferred-to-phase-201`, `inherited_as: blocking_requirement`) | Phase 200's per-direction-thresholds hypothesis was diagnosed insufficient by its own RETRO; residual failure regime is shaping-headroom dominated, not threshold dominated. Plans 200-09..200-14 improved loaded-window floor hits 122 -> 4 but the deploy gate is fail-closed at zero. Operator escalated to Phase 201's DOCSIS-aware control model on 2026-05-04 rather than running a second Phase 200 gap-closure cycle. | VALN-06 closes when Phase 201's canary verdict is `pass` with `ul_floor_hits_during_load=0` AND its 24h soak watchdog passes (suppressions <5/60s mean). The same fail-closed gate applies. Phase 201 must NOT inherit Phase 200's specific YAML values (18 Mbit ceiling, 42/105 ms thresholds) — those were the rejected hypothesis-under-test, not part of the requirement. The deployed UL ceiling under Phase 201 is a Phase 201 design choice (likely paired with a DOCSIS-aware setpoint per option D in this CONTEXT). |

### Direct evidence

`.planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260504T133207Z/verdict.json` — Attempt 3 verdict (`verdict: fail`, `ul_floor_hits_during_load: 4`, `ul_floor_threshold_hit: true`, `pre_baseline_rtt_ms: 21.7`, `post_baseline_rtt_ms: 22.23`, `duration_sec: 1022`, `rollback_protocol_recorded: true`). This is the canonical Attempt 3 evidence Phase 201 must improve upon to close VALN-06.

### Inheritance trail

- **Operator decision artifact:** `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-RETRO.md` `## Final Closure (2026-05-04)`.
- **Verification seal:** `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-VERIFICATION.md` frontmatter `closure: deferred-to-phase-201`, `inherited_as: blocking_requirement`, and the `### Closure Decision (2026-05-04, operator-escalated)` body subsection.
- **Requirements ledger:** `.planning/REQUIREMENTS.md` v1.41 traceability row reads `VALN-06 | Phase 200 (deferred to Phase 201) | Deferred -> Phase 201 (inherited blocking requirement) (...)`.
- **State seal:** `.planning/STATE.md` `## Blockers` first bullet records VALN-06 inheritance and the "MUST be reconciled before any future Spectrum deploy/restart" YAML language.

### Required predeploy gate

Phase 201's eventual PLAN MUST include a predeploy gate that inspects `/etc/wanctl/spectrum.yaml` for v1.41-only keys (`continuous_monitoring.upload.target_bloat_ms`, `warn_bloat_ms`, `consecutive_yellow_decay_clamp`, `factor_down_yellow=1.0`, `ceiling_mbps=18` if those values reflect the rejected hypothesis) and either reconciles them with Phase 201's own design choices or fails closed. This is non-optional: the v1.41 YAML keys are currently inactive under the rolled-back v1.40 binary, but a future Phase 201 binary that re-recognizes them would reactivate rejected-hypothesis state silently.

### What Phase 201 does NOT inherit

- Any specific YAML threshold values from Phase 200 (those were the hypothesis-under-test and were rejected).
- Phase 200's specific R5 (`factor_down_yellow=1.0`) and R3 (`consecutive_yellow_decay_clamp=40`) Spectrum-side YAML decisions — Phase 201 may keep, override, or remove them based on its own design.
- Phase 200's `200-REVIEW.md` advisory items (WR-01, WR-02, IN-01) — those are documentation/script hygiene and not on the VALN-06 critical path.

### What Phase 201 DOES inherit (process)

- The fail-closed deploy-gate model (D-07): saturation canary as primary gate, 24h soak as watchdog, predefined rollback (D-10) on canary fail.
- The verified canary tooling: `scripts/phase200-saturation-canary.sh` and its env template are reusable; the Plan 200-11 jq fix and the Plan 200-12 ordering precheck are now part of that tooling.
- The cross-AI review pattern (Codex + Claude) before any production-control change — flagged by Phase 200 as high-leverage and worth keeping for v1.42.

---
*Phase: 201-docsis-aware-ul-congestion-control*
*Seed written: 2026-05-03 (immediately after Phase 200 FAIL closeout)*
*Next step: /gsd-discuss-phase 201 to refine root cause + design direction*
