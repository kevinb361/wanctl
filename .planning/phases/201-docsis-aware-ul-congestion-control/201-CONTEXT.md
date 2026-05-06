# Phase 201: DOCSIS-Aware UL Congestion Control - Context

**Gathered:** 2026-05-04
**Status:** Ready for planning
**Origin:** Phase 200 closed FAIL on 2026-05-03 with the per-direction UL thresholds hypothesis rejected; operator escalated VALN-06 to this phase as an inherited blocking requirement on 2026-05-04. This CONTEXT supersedes the 2026-05-03 seed CONTEXT and reflects decisions made in `/gsd-discuss-phase 201` on 2026-05-04.

<domain>
## Phase Boundary

Ship a DOCSIS-aware UL congestion control mode that holds Spectrum DOCSIS upload off the floor under saturated load. The mode runs a YAML setpoint well below the upload ceiling and uses a windowed RTT integral as the headroom probe (with CAKE backlog as direction-aligned secondary corroborator) to decide when to push toward the ceiling.

**Closes VALN-06** (inherited blocking requirement from Phase 200): Spectrum UL saturation gate canary verdict `pass` with `ul_floor_hits_during_load=0` AND 24h regression soak watchdog with UL hysteresis suppression rate `<5/60s`. Same fail-closed gate as Phase 200 — no relaxation.

**Architectural diagnosis carried forward from Phase 200 RETRO:** the residual failure regime under Phase 200's stack (per-direction thresholds + R5 + R3) is shaping-headroom dominated, not threshold dominated. wanctl's 18 Mbit ceiling on Spectrum is barely below provisioned upstream rate (~20 Mbit), leaving no shaping headroom for wanctl's CAKE qdisc to absorb bufferbloat before the CMTS upstream queue fills. RTT-delta detection cannot react fast enough once the CMTS queue is already deep. The fix is a different control model, not wider thresholds.

**Inherited blocking requirement (verbatim from `200-VERIFICATION.md` and `REQUIREMENTS.md`):**

| Requirement | Inherited From | Closure Shape Under Phase 201 |
|---|---|---|
| **VALN-06** - Spectrum UL saturation gate (10-15 min `iperf3 -P4` saturated upload loop at the deployed UL ceiling completes with zero loaded-window floor-hit cycles, pre/post idle baselines bookend, 24h regression soak as watchdog) | Phase 200 (`200-VERIFICATION.md` `closure: deferred-to-phase-201`, `inherited_as: blocking_requirement`) | Closes when Phase 201's canary verdict is `pass` with `ul_floor_hits_during_load=0` AND 24h soak passes (suppressions <5/60s mean). Phase 201 does NOT inherit Phase 200's specific YAML values (18 Mbit ceiling, 42/105 ms thresholds) - those were the rejected hypothesis-under-test, not part of the requirement. The deployed UL ceiling and setpoint under Phase 201 are Phase 201 design choices (locked below). |

**Direct evidence Phase 201 must improve upon:** `.planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260504T133207Z/verdict.json` (`verdict: fail`, `ul_floor_hits_during_load: 4`, baseline RTT bookends populated). Plan 200-14 Attempt 3 reduced loaded-window floor hits 122 -> 4; Phase 201 must reach zero.

</domain>

<decisions>
## Implementation Decisions

### Phase Shape

- **D-01:** Single phase, signal locked at SPEC time. NOT a `/gsd-spike` first. Phase 200 RETRO already eliminated the architectural ambiguity that would justify a spike (residual regime is shaping-headroom dominated). Cross-AI review (Claude + Codex) catches wrong signal-or-design choices before deploy, mirroring the high-leverage pattern Phase 200 retro flagged.

### Control Model (Seed Option D - Hybrid)

- **D-02:** DOCSIS-aware UL mode runs a **conservative YAML setpoint** as the operating point, well below the upload ceiling. The ceiling becomes a guard rail, not a target. The mode is YAML opt-in keyed off `continuous_monitoring.upload.docsis_mode: true`; absent or `false` preserves byte-identical legacy behavior for all non-Spectrum deployments (CLAUDE.md NON-NEGOTIABLE: portable controller architecture).
- **D-03:** **Headroom probe = windowed RTT integral.** Replace (or augment - planner decides) the existing RTT-delta classifier with an integral-of-RTT-over-baseline metric over a configurable window. Rationale: RTT traverses the CMTS queue, so RTT integral captures CMTS-side queueing that wanctl-local CAKE backlog cannot see. No new transport (RTT samples already gathered).
- **D-04:** **CAKE backlog as direction-aligned secondary corroborator.** Mirror v1.40 queue-primary pattern (Phase 197 dl_cake_for_arbitration semantics): the controller pushes toward ceiling only when RTT integral has been low for a sustained window AND CAKE `backlog_bytes` / `max_delay_delta_us` direction-aligns. Single-signal flips do not bypass. Categorical alignment, never µs/ms magnitude ratio (Phase 200 RETRO 2026-04-23 Codex pushback pattern).
- **D-05:** **Modem SNMP / DOCSIS HCS counters NOT in scope** for Phase 201. Adds a new transport + dependency on modem firmware exposing queue counters; higher implementation risk; the RTT-integral + CAKE-backlog hybrid is sufficient on the available signals.

### YAML Surface (SAFE-06 + Portability Compliant)

- **D-06:** New keys, all under `continuous_monitoring.upload.*`, registered in `KNOWN_AUTORATE_PATHS` (`src/wanctl/check_config_validators.py:28-180`):
  - `docsis_mode: bool` (default `false` - byte-identical fallback)
  - `setpoint_mbps: int|float` (REQUIRED when `docsis_mode: true`; validator fails closed if missing)
  - RTT-integral window keys (planner picks names + ordering; honor existing ordering-check pattern in `src/wanctl/autorate_config.py:182-194`)
- **D-07:** **No global default for `setpoint_mbps`.** Setpoint is link-specific; principled defaults across DOCSIS deployments are not knowable without per-link evidence. No `setpoint_pct` companion key (rejected to keep validator + ordering surface minimal).
- **D-08:** **Restart-required.** New keys are NOT live-tunable via SIGUSR1. SIGUSR1 reload scope stays at dwell/deadband only (`src/wanctl/wan_controller.py:1894-1899`); expanding it for control-mode keys is risky on the control path (CLAUDE.md "stability > safety > clarity > elegance"). Migration note required in `docs/CONFIGURATION.md` and `CHANGELOG.md` mirroring Phase 200 DOCS-03 pattern.

### Spectrum-Specific Setpoint Value (Claude's Discretion)

- **D-09:** **Spectrum `setpoint_mbps: 12`** in `configs/spectrum.yaml`. Rationale: 60% of provisioned upstream rate (~20 Mbit), gives 6 Mbit ceiling-margin and ~8 Mbit provisioned-margin - actual shaping headroom for wanctl's CAKE qdisc to absorb bufferbloat before the CMTS queue does. Phase 200 evidence showed the 2 Mbit gap between 18 Mbit ceiling and ~20 Mbit provisioned was insufficient (122 -> 4 floor hits with the threshold-only approach); 14 Mbit (option 2 in discussion) leaves only 4 Mbit ceiling-margin (22%) which the seed flagged as "tighter; higher risk the canary still hits floor." Open to challenge by researcher / planner / cross-AI review during plan phase if the three Spectrum sweep notes (`spectrum-inline-native-18-upload-test-2026-04-29.md`, `spectrum-upload-ceiling-sweep-2026-04-29.md`, `spectrum-target-bloat-sweep-2026-04-15.md`) point at a different value.
- **D-10:** **Upload ceiling stays at 18 Mbit** in `configs/spectrum.yaml`. The Phase 200 ceiling drop 28 -> 18 Mbit is preserved (it was a latency-first decision orthogonal to the rejected per-direction-thresholds hypothesis). Floor stays at 8 Mbit. Phase 200's `factor_down_yellow=1.0` and `consecutive_yellow_decay_clamp=40` (R5 + R3) MAY be kept, overridden, or removed per Phase 201 design (per `200-RETRO.md` "What Phase 201 does NOT inherit" - planner decides during SPEC).

### VALN-06 Closure: Canary + Soak

- **D-11:** **Reuse `scripts/phase200-saturation-canary.sh`.** The Phase 200 tooling caught real production-only bugs (logger silent-drop, /health field assumption, env-var false-PASS regression) and is now hardened. Forking to a sibling `phase201-*` script would lose that bug-fix history with marginal benefit.
- **D-12:** **Extend canary preflight YAML cross-check** (`scripts/phase200-saturation-canary.sh:314-358`) to also cross-check the new `docsis_mode: true` flag and `setpoint_mbps` value against env vars. Add a /health probe that asserts the new DOCSIS-mode telemetry block is live before saturation begins. Same fail-closed pattern: env-var declared expectation + SSH probe of deployed YAML, ABORT on mismatch (Phase 200 `dd67493 -> 43838f4` regression-fix pattern).
- **D-13:** **Zero-floor-hit gate preserved.** No relaxation. `ul_floor_hits_during_load=0` is the canary verdict pass condition. Same fail-closed rollback (D-10 from Phase 200) on canary fail.
- **D-14:** **24h soak watchdog at `<5/60s` UL hysteresis suppression rate** (unchanged from Phase 200 inherited closure shape). Tighter threshold (`<2/60s`) was discussed and rejected for Phase 201 - DOCSIS-aware mode should produce far less suppression than the rejected hypothesis, but tightening the watchdog before the canary first proves zero-floor-hit is premature. v1.43+ may tighten if Phase 201 soak data supports it.

### Soak Closure Gate (gap-closure path b, 2026-05-05)

- **D-19 (operator-approved gate tightening):** Phase 201 closure adds a STRICTER PRIMARY soak gate beyond the original D-14 secondary watchdog: `floor_hit_cycles_total_delta_soak_window == 0`. Original D-14 `<5/60s` suppression-rate threshold STAYS as SECONDARY gate. Tightening aligns the soak's primary metric with the canary's primary metric. **Operator approval captured pre-soak in `201-16-OPERATOR-APPROVAL-D19.md`** (codex 201-REVIEWS round-2 LOW-CODEX-5: distinct operator-approval checkpoint required, not a planner-written claim in a verdict file).
- **Plan 201-16 outcome (2026-05-06):** D-19 primary gate passed (`delta=0`), but D-14 secondary gate failed (`suppressions_per_min_mean=6.466842364880155` vs `<5.0`). Phase 201 remains `gaps_found`; see `201-16-SOAK-VERDICT.md` and `soak/20260505T132736Z/soak-summary.json`.

### Predeploy Gate (Inherited from Seed - Mandatory)

- **D-15:** Phase 201's PLAN MUST include a predeploy gate that inspects `/etc/wanctl/spectrum.yaml` for v1.41-only keys (`continuous_monitoring.upload.target_bloat_ms`, `warn_bloat_ms`, `consecutive_yellow_decay_clamp`, `factor_down_yellow=1.0` if those values reflect the rejected hypothesis) and either reconciles them with Phase 201's own design choices or fails closed. Action shape (auto-strip vs operator-manual reconcile) is a planner-level decision; seed's "reconcile or fail closed" language gives both flavors latitude.

### /health Payload Extension (Additive Only - CLAUDE.md)

- **D-16:** New DOCSIS-mode telemetry is **additive** to `.wans[].upload`. Candidate fields (planner finalizes naming): `setpoint_mbps`, `headroom_mbps`, `rtt_integral_ms_s`, `docsis_state`, `docsis_mode_active`. NEW fields ONLY; do not modify shape of existing `upload` keys. Per Phase 200 RETRO lesson: `/health.wans[].{download,upload}` carries runtime state only - config values like `setpoint_mbps` and `docsis_mode` get exposed as runtime state (i.e., the value the controller is currently using), not as static config echoes. Smoke check MUST grep a real `/health` endpoint, not a JSON fixture.

### ATT and Non-DOCSIS Deployments

- **D-17:** ATT, fiber, DSL, and other non-DOCSIS deployments stay byte-identical. ATT YAML does not carry the v1.41 per-direction threshold keys (absent-key fallback D-02 from Phase 200 preserves this). Phase 201 does NOT touch ATT YAML; absence of `docsis_mode` in any non-Spectrum YAML preserves legacy 3-state UL behavior verbatim. Validation: SAFE-05 v1.42 count baseline must be re-established once `docsis_mode` / `setpoint_mbps` keys are wired (count uplift on `target_bloat` / `warn_bloat` is unchanged from Phase 200).

### Cross-AI Review

- **D-18:** Codex pre-review before plan implementation, Codex stop-time review after deploy machinery is in place, both kept (Phase 200 RETRO "high-leverage on production-control work"). Plan must include explicit Cross-AI review checkpoints, not optional.

### Claude's Discretion

- **D-09 (setpoint = 12 Mbit Spectrum):** see rationale above. Subject to challenge during research / plan / cross-AI review.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 200 Closure + Direct Evidence

- `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-CONTEXT.md` — Phase 200 design context (DOCSIS-aware UL was deferred from this CONTEXT explicitly)
- `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-RETRO.md` — Phase 200 retrospective with `## Final Closure (2026-05-04)` operator decision and "Lessons for v1.42" subsection
- `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-VERIFICATION.md` — `closure: deferred-to-phase-201`, `inherited_as: blocking_requirement`, and `### Closure Decision (2026-05-04, operator-escalated)` body
- `.planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260504T133207Z/verdict.json` — Attempt 3 canary verdict Phase 201 must improve upon (`ul_floor_hits_during_load: 4`)
- `.planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260503T215734Z/` — Attempt 2 canary evidence (122 collapse events, bimodal distribution analysis)

### Spectrum-Specific Operator Evidence

- `.planning/spectrum-inline-native-18-upload-test-2026-04-29.md` — Step 4 mentions "upload-specific factor_down gentler than 0.90, smaller step_up_mbps"
- `.planning/spectrum-upload-ceiling-sweep-2026-04-29.md` — ceiling sweep evidence relevant to D-09 setpoint challenge
- `.planning/spectrum-target-bloat-sweep-2026-04-15.md` — historical bloat-threshold sweep

### Project-Level Constraints

- `CLAUDE.md` — production network change-policy ("stability > safety > clarity > elegance"); portable controller architecture (NON-NEGOTIABLE); /health payload-shape contract; flash wear protection (last_applied_dl_rate / last_applied_ul_rate)
- `.planning/PROJECT.md` — v1.41 milestone status, Phase 200 closure context
- `.planning/REQUIREMENTS.md` — VALN-06 traceability row reads `Phase 200 (deferred to Phase 201) | Deferred -> Phase 201 (inherited blocking requirement)`
- `.planning/STATE.md` — Phase 200 close + VALN-06 inheritance seal
- `.planning/ROADMAP.md` — v1.41 entry; Phase 201 row to be added under v1.42 (or successor milestone) by `/gsd-new-milestone` flow

### Implementation Surfaces (Code)

- `src/wanctl/queue_controller.py:139-182` — `_classify_zone_3state()` UL classifier reading `target_delta` / `warn_delta`; integration point for RTT-integral classifier
- `src/wanctl/queue_controller.py:229-256` — `_compute_rate_3state()` UL rate decision; setpoint-clamp pre-classifier integration point; `enforce_rate_bounds(floor=self.floor_red_bps, ceiling=self.ceiling_bps)` at line 131
- `src/wanctl/wan_controller.py:402-418` — Upload QueueController constructor (floor / ceiling / thresholds wiring)
- `src/wanctl/wan_controller.py:426-437` — UL `target_delta` / `warn_delta` per-key explicit-presence flags (Phase 200 D-03 pattern; mirror for new keys)
- `src/wanctl/wan_controller.py:2978-2984` — UL cycle invocation `self.upload.adjust(effective_ul_load_rtt, target_delta, warn_delta, ul_cake)`; integration point for new signal feed
- `src/wanctl/wan_controller.py:4510-4511` — `/health` upload payload `"upload": self._ul_cake_snapshot`; D-16 additive-fields integration point
- `src/wanctl/wan_controller.py:1894-1899` — SIGUSR1 reload scope (dwell/deadband only; D-08 keeps narrow)
- `src/wanctl/cake_signal.py:85-123` — `CakeSignalSnapshot` dataclass holding `peak_delay_us` / `avg_delay_us` / `base_delay_us` / `max_delay_delta_us` / `backlog_bytes`; D-04 CAKE corroborator source
- `src/wanctl/cake_signal.py:245-248` — per-tin `max_delay_delta_us` computation
- `src/wanctl/autorate_config.py:182-194` — UL threshold schema; new YAML keys land here with ordering checks
- `src/wanctl/check_config_validators.py:28-180` — `KNOWN_AUTORATE_PATHS` registry (SAFE-06 enforcement; new keys MUST register here)
- `configs/spectrum.yaml:68-77` — current Spectrum upload block (ceiling=18, floor_mbps=8, target_bloat_ms=42, warn_bloat_ms=105, factor_down=0.90, factor_down_yellow=1.0, consecutive_yellow_decay_clamp=40); D-09/D-10 land here

### Canary + Deploy Tooling

- `scripts/phase200-saturation-canary.sh` — D-11 canary tool for reuse; preflight YAML cross-check at lines 314-358 is D-12 extension target
- `scripts/phase200-saturation-canary.env.example` — env template; needs new `PHASE201_SETPOINT_MBPS` (or similar) entry per D-12

### Tests

- `tests/test_queue_controller.py:107` (`test_zone_classification`), 139-182 (3-state zone logic), 229-256 (rate computation) — UL classifier + rate decision tests
- `tests/test_wan_controller.py:71-94`, 96-120, 161-223 — UL threshold-config integration tests including per-key explicit-presence pattern
- `tests/test_autorate_config.py:266-278`, 379-415 — UL threshold ordering invariants

### Architecture / Configuration Docs

- `docs/ARCHITECTURE.md` — control model overview; portable controller architecture
- `docs/CONFIGURATION.md` — YAML key reference; D-08 migration note lands here
- `docs/PERFORMANCE.md` — 50ms cycle budget context

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`CakeSignalSnapshot.backlog_bytes` and `max_delay_delta_us` already populated for upload** (`src/wanctl/cake_signal.py:85-123`, surfaced to controller via `wan_controller.py:2757`). D-04 CAKE-backlog corroborator does NOT need a new signal-collection path.
- **Per-key explicit-presence flag pattern** (Phase 200 D-03, `wan_controller.py:426-437`) is the correct shape for `_docsis_mode_explicit` and `_setpoint_mbps_explicit`. Do NOT make value-derived (Codex pre-review caught this exact regression in Phase 200).
- **Phase 200 saturation canary tool** (`scripts/phase200-saturation-canary.sh`) is hardened by Plan 200-11 (jq path fix), 200-12 (ordering precheck), and the `dd67493 -> 43838f4` env-var-vs-YAML cross-check regression cycle. D-11 reuses; D-12 extends preflight only.
- **v1.40 queue-primary arbitration pattern (Phase 197 dl_cake_for_arbitration semantics)** for direction-aligned categorical signals — mirror for D-04 CAKE corroborator.

### Established Patterns

- **CLAUDE.md NON-NEGOTIABLE: portable controller architecture.** Deployment-specific behavior in YAML, not Python branching. D-06 / D-17 enforce this.
- **CLAUDE.md flash wear protection.** `last_applied_dl_rate` / `last_applied_ul_rate` deduplication of router writes is part of the safety model. Setpoint mode must respect this — only send rate changes to the router when the value changes.
- **CLAUDE.md /health payload contract.** Additive only. New fields are nested under `.wans[].upload.*`, do not modify existing key shapes (D-16).
- **CLAUDE.md control-model invariants.** Rate decreases immediate; rate increases require sustained healthy cycles. D-04 (push-toward-ceiling only when integral has been low for sustained window) preserves this.
- **Phase 200 SAFE-05 invariant.** UL byte-identical when new keys absent. New v1.42 SAFE-05 baseline counts must be re-established for `docsis_mode` / `setpoint_mbps` (count uplift on `target_bloat`/`warn_bloat` unchanged from Phase 200).
- **SAFE-06 unknown-key warnings.** Every new YAML key MUST register in `KNOWN_AUTORATE_PATHS` (`check_config_validators.py:28-180`) or production startup will warn audibly (Phase 200 closed this gap; Phase 201 must not reopen it).

### Integration Points

- **UL classifier seam** (`queue_controller.py:139-182`): RTT-integral classifier replaces or augments `_classify_zone_3state` when `docsis_mode: true`. Decision (replace vs augment) is a planner choice; per-key explicit flag gates the classifier swap.
- **UL rate-decision seam** (`queue_controller.py:229-256`): setpoint clamp lives ABOVE `_compute_rate_3state` so the classifier output is bounded by setpoint when `docsis_mode: true` (ceiling becomes guard rail, setpoint becomes operating point).
- **CAKE corroborator seam** (`wan_controller.py:2978-2984`): UL cycle `self.upload.adjust(...)` already receives `ul_cake` snapshot. D-04 corroborator reads existing fields; no new wiring needed at this seam.
- **Predeploy gate seam** (D-15): plan-level shell tooling, not Python — integrates with `scripts/install.sh` / `scripts/deploy.sh` flow. SSH probe of `/etc/wanctl/spectrum.yaml` mirrors the Phase 200 D-12 pattern.

</code_context>

<specifics>
## Specific Ideas

- **Setpoint = 12 Mbit on Spectrum** (D-09). Justified by "60% of provisioned upstream rate" framing in seed; aligned with the architectural diagnosis that the Phase 200 18-Mbit ceiling left no shaping headroom. Subject to research challenge from the three Spectrum sweep notes.
- **RTT integral as the headroom signal** (D-03), specifically: integral-of-RTT-over-baseline over a planner-chosen window (anchor: Phase 200 control loop is 50ms × 20Hz; the existing `consecutive_yellow_decay_clamp=40` operates on a 2s window, so integral windows in the 1-5s range are the candidate space).
- **CAKE backlog as direction-aligned secondary** (D-04), not an independent classifier. Mirrors v1.40 Phase 197 dl_cake_for_arbitration discipline.
- **Modem SNMP / DOCSIS HCS counter explicitly out** (D-05). Future v1.43+ enhancement only if D-03/D-04 prove insufficient.
- **Zero-floor-hit gate is non-negotiable** (D-13). Phase 200's "materially improved but still failed" closure pattern (122 -> 4) is NOT acceptable for Phase 201 closure.

</specifics>

<deferred>
## Deferred Ideas

### Not in Scope for Phase 201

- **DL queue-primary work** — covered by v1.40 Phases 193-198.
- **Per-direction DL thresholds** — Phase 200 D-02 fallback already preserves DL behavior.
- **ATT-specific UL changes** — Phase 191 / 191.1 territory; Phase 201 stays byte-identical for ATT (D-17).
- **Modem SNMP / DOCSIS HCS counter signal** (D-05) — defer to v1.43+ only if D-03/D-04 hybrid proves insufficient under Phase 201 canary + soak evidence.
- **Tighter soak watchdog `<2/60s`** (D-14 alternative) — defer to v1.43+ once Phase 201 soak data establishes that the steady-state suppression rate is far below 5/60s.
- **DOCSIS-mode auto-tuning of `setpoint_mbps`** — Phase 201 ships static operator-supplied setpoint only. Auto-tuning across deployments is a future research/spike candidate, not Phase 201 scope.
- **Alerting fix for Spectrum YAML severity** — separate quick task `260503-cfs`; Phase 201 must not regress the alerting fix.
- **VALN-05b ATT cake-primary canary** — cross-milestone deferral to v1.39 Phase 191 closure, tracked at `.planning/todos/pending/2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md`. May be consolidated with Phase 201 into v1.42 milestone scope (operator decision at `/gsd-new-milestone` time).

### Future Milestone Scope

- v1.42 milestone home for Phase 201 (per Phase 200 RETRO "Lessons for v1.42"). Whether v1.42 is solo-phase (Phase 201 + closure only) or includes the deferred ATT VALN-05b is a `/gsd-new-milestone` decision, not a Phase 201 decision.

</deferred>

---

*Phase: 201-docsis-aware-ul-congestion-control*
*Context gathered: 2026-05-04*
*Supersedes: 201-CONTEXT.md seed (2026-05-03, written immediately after Phase 200 FAIL closeout)*
*Next step: `/gsd-plan-phase 201` to produce PLAN with research-backed setpoint validation, RTT-integral window sizing, and predeploy-gate action shape*
