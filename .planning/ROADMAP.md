# Roadmap: wanctl v1.39 Control-Path Timing & Measurement Accounting

**Milestone Goal:** Reduce systemic tail latency in the netlink apply path and fix reflector-scorer blackout misattribution without changing any control algorithms, thresholds, or state machines.

**Phases:** 3 | **Requirements mapped:** 11/11 ✓

## Phase Summary

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 191 | Netlink Apply Timing Stabilization | Instrument and reduce `tc dump` vs `tc change` kernel RTNL contention that spikes netlink apply latency to 10–87 ms | TIME-01, TIME-02, TIME-03, TIME-04, SAFE-03, SAFE-04, VALN-02 | 5 |
| 191.1 | ATT Config Drift Resolution and Phase 191 Closure | 3/3 | Complete   | 2026-04-20 |
| 192 | Reflector Scorer Blackout-Awareness + Log Hygiene | Stop misattributing path-wide ICMP blackouts to individual reflectors; trim fusion-suspended log noise | MEAS-05, MEAS-06, OPER-02, SAFE-03, VALN-02, VALN-03 | 4 |

---

## Phase 191: Netlink Apply Timing Stabilization

**Goal:** Add instrumentation to make `tc dump` vs `tc change` overlap measurable in production, then tune `cake_stats_thread` cadence (or add post-apply backoff) based on that evidence to reduce Slow CAKE apply p99 and cycle overrun rate on both Spectrum and ATT — without changing any control algorithm.

**Requirements addressed:** TIME-01, TIME-02, TIME-03, TIME-04, SAFE-03, SAFE-04, VALN-02

**Depends on:** —

**Scope:**
- Add timestamp + elapsed instrumentation to `cake_stats_thread` tc-dump path and `netlink_cake` tc-change apply path
- Expose overlap evidence in `/health` (or structured logs if health-endpoint surface is too expensive) so operators can see dump-vs-change concurrency without attaching a debugger
- Make `cake_stats_thread` cadence YAML-configurable, default preserving current 50 ms behavior until data justifies change
- Optionally add post-apply backoff (skip next 1–2 reads after a `tc change`) if instrumentation shows that pattern helps more than cadence reduction
- Run flent A/B (RRUL, tcp_12down, VoIP) vs v1.38.0 baseline before shipping

**Out of scope (locked):**
- Any change to state machine, EWMA alphas, dwell cycles, deadband, burst detection, or thresholds (SAFE-03)
- User-space locks around netlink calls (can delay rate-decrease path, violates SAFE-04)
- Atomic DL+UL write batching (unclear API, high risk)
- Reflector scorer work (Phase 192)
- Log hygiene (Phase 192)

**Success Criteria:**
1. Health endpoint or structured log surface exposes per-call timestamps and elapsed time for tc-dump and tc-change, enabling operators to identify overlap episodes without additional tooling.
2. `cake_stats_thread.poll_cadence_ms` is readable from YAML; restarting the daemon with a different value changes the observed stats-read interval.
3. Cycle overrun count per hour on both Spectrum and ATT drops measurably over a 24-hour post-merge window vs the 2026-04-20 baseline (107 Spectrum / 240 ATT cumulative, normalized to uptime).
4. `write_download_ms` and `write_upload_ms` p99 logged in Slow CAKE apply warnings drop measurably on both WANs over the same window.
5. Flent RRUL, tcp_12down, and VoIP A/B runs show no regression in bufferbloat grade, p99 latency, or VoIP jitter vs v1.38.0 baseline, captured in VERIFICATION.md.

**Plans:** 5 plans

Plans:
- [ ] 191-01-PLAN.md — NetlinkCakeBackend apply-side overlap timestamps (TIME-01)
- [ ] 191-02-PLAN.md — BackgroundCakeStatsThread dump-side OverlapSnapshot (TIME-01)
- [ ] 191-03-PLAN.md — YAML cake_stats_cadence_sec knob + WANController wiring (TIME-02)
- [ ] 191-04-PLAN.md — WANController overlap compute + /health rendering + slow-apply log enrichment (TIME-01, TIME-04, SAFE-03, SAFE-04)
- [ ] 191-05-PLAN.md — Regression slice, SAFE-03/SAFE-04 diff proofs, flent A/B vs v1.38.0 (VALN-02)


---

### Phase 191.1: ATT config drift resolution and Phase 191 closure (INSERTED)

**Goal:** Restore the two proven-drifted ATT config keys (`irtt.server=104.200.21.31`, `fusion.enabled=true`) to the `v1.38` baseline together, make the phase-local SAFE-03 comparator the explicit Phase 191 closure rule, and capture a narrow ATT+Spectrum rerun so Phase 191 can close honestly (per D-11) before Phase 192 begins.
**Requirements**: SAFE-03, VALN-02
**Depends on:** Phase 191
**Plans:** 3/3 plans complete

Plans:
- [x] 191.1-01-att-config-restoration-PLAN.md - restore irtt.server and fusion.enabled to v1.38 values in configs/att.yaml (single coordinated edit per D-03)
- [x] 191.1-02-validation-rerun-PLAN.md - deploy restored ATT config and capture ATT rrul/tcp_12down/voip plus Spectrum RRUL discriminator via scripts/phase191-flent-capture.sh
- [x] 191.1-03-closure-artifact-update-PLAN.md - add phase-local SAFE-03 comparator rule and restored-config rerun evidence to 191-VERIFICATION.md and 191-05-SUMMARY.md

## Phase 192: Reflector Scorer Blackout-Awareness + Log Hygiene

**Goal:** Fix the reflector scorer so it recognizes all-host zero-success cycles as blackout events and does not decrement per-host quality windows for those cycles. Rate-limit or demote fusion-suspended "Protocol deprioritization detected" INFO log noise. Close v1.39 with a 24-hour soak confirming no regression.

**Requirements addressed:** MEAS-05, MEAS-06, OPER-02, SAFE-03, VALN-02, VALN-03

**Depends on:** Phase 191.1, waived for Phase 192 only by `192-PRECONDITION-WAIVER.md` after repeated restored-config reruns narrowed the blocker to the old ATT RRUL comparator. Phase 191 remains open.

**Scope:**
- Modify `reflector_scorer.py` so per-host score-update paths consume the same zero-success blackout gate that `rtt_measurement.py` already uses
- Preserve existing cached-RTT fallback semantics verbatim — scorer change must not alter what the controller sees
- Add unit tests covering: all-host-fail cycle (no score decrement), partial-success cycle (normal scoring), recovery after blackout, mixed quality drops that should still deprioritize
- Demote or rate-limit `Protocol deprioritization detected` INFO logs when `fusion.state` is `disabled` or `healer_suspended`; preserve first occurrence + state transitions
- Flent A/B before ship; 24-hour production soak after merge

**Out of scope (locked):**
- Adding a 4th reflector (deferred until MEAS-06 proves insufficient)
- Any control threshold / state machine change (SAFE-03)
- Changing fusion behavior itself
- Any work covered by Phase 191

**Success Criteria:**
1. Unit test demonstrates that a zero-success cycle (all reflectors fail) leaves individual reflector scores unchanged for that cycle.
2. Spectrum reflector scores in `/health` over a 24-hour window no longer repeatedly sink to the 0.8 deprioritize threshold during blackout episodes, verified against baseline log evidence from 2026-04-20.
3. Spectrum "Protocol deprioritization detected" log volume over 24 hours drops meaningfully vs the 2.5k/day baseline, with first-occurrence and state-transition events still recorded.
4. 24-hour post-merge soak confirms no regression in dwell-bypass responsiveness, burst detection trigger count, or fusion state transitions — captured in VERIFICATION.md.

**Plans:** 3/3 plans complete

Plans:
- [x] 192-01-PLAN.md — Caller-side blackout gate + scorer/seam tests (MEAS-05, MEAS-06, SAFE-03, VALN-02)
- [x] 192-02-PLAN.md — Fusion-aware log cooldown for protocol-deprio INFO + tests (OPER-02, SAFE-03, VALN-02)
- [x] 192-03-PLAN.md — /health additive field, soak-capture script, live soak verification, and v1.39.0 bump under waiver (MEAS-06, OPER-02, SAFE-03, VALN-02, VALN-03)

---

## Ordering Rationale

Phase 191 ships before Phase 192 because the timing change affects *both* WANs systemically while the scorer change only affects measurement accounting on Spectrum. Phase 191.1 exists because ATT validation isolated a post-`v1.38` config/runtime drift issue that must be resolved before the scorer soak starts. Separating them also lets the 24-hour soak per change attribute regressions cleanly — if we shipped together, a regression in dwell-bypass could be blamed on either.

*Roadmap created: 2026-04-20*

---

# Roadmap: wanctl v1.40 Queue-Primary Signal Arbitration

**Milestone Goal:** Replace RTT-primary DL congestion classification with kernel-local CAKE queue delay (`avg_delay_us - base_delay_us`) as the primary signal under load, demote RTT to a confidence-gated secondary, and tighten the fusion healer bypass gate so single-path flips no longer destabilize the control path. Restore Spectrum DOCSIS throughput without making the controller vulnerable to carrier ICMP/UDP deprioritization. DL-only scope — UL classification stays byte-identical to v1.39.

**Phases:** 4 | **Requirements mapped:** 10/10 ✓

## Phase Summary

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 193 | Queue Signal Contract and Arbitration Telemetry | 1/3 | In Progress|  |
| 194 | Download Queue-Primary Distress Classification | 2/2 | Complete    | 2026-04-24 |
| 195 | RTT Confidence Demotion and Fusion-Healer Containment | 3/3 | Complete    | 2026-04-24 |
| 196 | Spectrum A/B Soak and ATT Regression Canary | 6/8 | In Progress|  |

---

## Phase 193: Queue Signal Contract and Arbitration Telemetry

**Goal:** Expose the CAKE fields needed for queue-primary arbitration (`avg_delay_us`, `base_delay_us`) through the signal pipeline, publish a new `/health` `signal_arbitration` block, and persist matching numeric per-cycle metrics to the SQLite store. Zero control-behavior change: after this phase ships, v1.39 controller behavior must remain byte-identical because classification still reads RTT delta exclusively. This phase is observability-only and establishes the data contract Phase 194 will consume.

**Requirements addressed:** MEAS-07, OBS-01, OBS-02, SAFE-05

**Depends on:** —

**Scope:**
- Extend `cake_signal.py` (or equivalent CAKE snapshot carrier) to surface `avg_delay_us` and `base_delay_us` alongside existing `peak_delay_us`; wire them from the tc-stats reader through the signal chain to the controller's per-cycle view.
- Add the `signal_arbitration` per-WAN block to the `/health` payload with fields `active_primary_signal` (string in `{"queue","rtt","none"}` — set to `"rtt"` for this phase since classification is unchanged), `rtt_confidence` (float 0.0–1.0 or null — null allowed this phase), `cake_av_delay_delta_us` (int or null), and `control_decision_reason` (stable-vocabulary short string). Additive only — existing `download.state`, `download.state_reason`, `download.hysteresis`, and `upload.*` remain byte-compatible with v1.39 consumers.
- Persist numeric per-cycle metrics per OBS-02 (`wanctl_cake_avg_delay_delta_us`, `wanctl_rtt_confidence`, `wanctl_arbitration_active_primary` as `0=none`, `1=queue`, `2=rtt`) into the per-WAN metrics SQLite store using the existing Prometheus-style exporter schema. No string labels.
- No change to `_classify_zone_4state`, `QueueController`, the EWMA pipeline, dwell, deadband, burst detection, or rate compute. The queue-delta field is computed and observed; it is not yet consumed by classification.

**Out of scope (locked):**
- Any change to classification rules, EWMA alphas, dwell cycles, deadband, burst detection, thresholds, or rate compute (SAFE-05).
- Python-side learned idle baseline or baseline-freeze state machine for queue delay — `base_delay_us` is consumed as provided by the kernel (MEAS-07).
- Nesting new arbitration fields under `download.hysteresis` — new fields live only under `signal_arbitration`.
- Any UL pipeline changes.
- Consuming `peak_delay_us` as primary — remains available only as a secondary burst corroborator.

**Success Criteria:**
1. Operator can curl `/health` on both Spectrum and ATT and see a `signal_arbitration` block per WAN with `active_primary_signal`, `rtt_confidence`, `cake_av_delay_delta_us`, and `control_decision_reason` fields present and well-formed, with `active_primary_signal == "rtt"` because classification is unchanged.
2. After this phase ships with cake_signal-supported transports, `cake_av_delay_delta_us` is observed moving non-null through load events in production traces, while existing v1.39 `/health` fields (`download.state`, `download.state_reason`, `download.hysteresis`, all `upload.*`) remain byte-compatible with v1.39 consumers.
3. Per-cycle queries against the metrics SQLite store return numeric values for `wanctl_cake_avg_delay_delta_us`, `wanctl_rtt_confidence`, and `wanctl_arbitration_active_primary` (with `active_primary == 2` for "rtt" throughout this phase) under real load.
4. Offline replay of a v1.38/v1.39 production trace through the Phase 193 build produces byte-identical classifier transitions and rate-apply sequences to the pre-Phase-193 build, proving SAFE-05 — classification input unchanged, classification output unchanged.

**Plans:** 1/3 plans executed

Plans:
- [x] 193-01-PLAN.md — Extend CakeSignalSnapshot/TinSnapshot with avg_delay_us + base_delay_us; wire cold-start + steady-state construction sites (MEAS-07, SAFE-05)
- [ ] 193-02-PLAN.md — Add /health signal_arbitration block + extend DL CAKE metrics batch (OBS-01, OBS-02, SAFE-05)
- [ ] 193-03-PLAN.md — SAFE-05 replay-equivalence harness + 193-VERIFICATION.md (SAFE-05)

---

## Phase 194: Download Queue-Primary Distress Classification

**Goal:** Change DL distress classification so it consumes `queue_delay_delta_us = max(0, avg_delay_us - base_delay_us)` as its primary input when `cake_signal` is supported and a valid snapshot is present. RTT still participates but only as the confidence-gated secondary introduced in Phase 195 — in this phase, RTT path enters classification unchanged for cycles where queue signal is unavailable (preserving the v1.39 code path byte-identically for that fallback). UL distress classification, UL state machine, and UL rate compute are untouched and byte-identical to v1.39.

**Requirements addressed:** ARB-01, ARB-04, SAFE-05

**Depends on:** Phase 193

**Scope:**
- Add a DL classification input selector driven by cake_signal availability: when cake_signal is supported and the latest cake_snapshot carries valid `avg_delay_us` and `base_delay_us`, use `queue_delay_delta_us` as the primary distress scalar; when cake_signal is unsupported (or snapshot invalid), fall back to the v1.39 RTT-primary code path byte-identically.
- Update `signal_arbitration.active_primary_signal` in `/health` and `wanctl_arbitration_active_primary` in metrics to reflect the selection per cycle (`1=queue` when queue primary is active, `2=rtt` on fallback, `0=none` when neither path has a valid reading).
- Set `signal_arbitration.control_decision_reason` using the stable vocabulary (`queue_distress`, `green_stable`, `rtt_veto` — the last reserved for Phase 195 interaction but left wired as `queue_distress` or `green_stable` during Phase 194 since RTT cannot yet override queue).
- No change to state-machine thresholds, EWMA alphas, dwell cycles, deadband values, burst detection parameters, zone transition rules, or hysteresis constants. Only the scalar fed into classification changes, and only on DL.
- UL path remains byte-identical — including UL EWMA, UL state machine, UL burst detection, and UL rate compute.

**Out of scope (locked):**
- `rtt_confidence` derivation and RTT veto logic (Phase 195).
- Fusion healer bypass gate changes (Phase 195).
- UL queue-primary classification (v1.40 Out of Scope; UL stays RTT-led).
- Any change to state-machine rules, EWMA alphas, dwell, deadband, burst detection, or thresholds (SAFE-05).
- Python-learned idle baseline for queue delay (MEAS-07).
- `peak_delay_us` as primary scalar.

**Success Criteria:**
1. On a cake_signal-supported WAN (Spectrum linux-cake backend), DL distress zone transitions are driven by `queue_delay_delta_us` under load — a traced load event where `avg_delay_us` grows past `base_delay_us` produces a DL zone transition with the correct timing relative to queue-delta growth (≤1 cycle lag) without any RTT delta involvement for that cycle.
2. On a cake_signal-unsupported path (forced fallback, e.g., REST transport or stub), DL classification path is byte-identical to v1.39 — offline replay of a v1.39 trace produces the same DL zone transitions and rate-apply sequence through the fallback path.
3. `/health` shows `signal_arbitration.active_primary_signal == "queue"` on the Spectrum linux-cake deployment during a DL load event and `"rtt"` on the forced-fallback path, matching the metric `wanctl_arbitration_active_primary` value per cycle.
4. UL `/health` (`upload.*`) and UL SQLite metrics are byte-identical between pre-Phase-194 and Phase-194 traces on the same recorded input, proving ARB-04.

**Plans:** 2/2 plans complete

Plans:
- [x] 194-01-PLAN.md — DL primary-signal selector + per-cycle stash + arbitration-aware /health and metrics rewiring (ARB-01, SAFE-05)
- [x] 194-02-PLAN.md — SAFE-05 / ARB-04 / ARB-01 deterministic replay harness reusing Phase 193 scaffolding (ARB-04, SAFE-05, ARB-01)

---

## Phase 195: RTT Confidence Demotion and Fusion-Healer Containment

**Goal:** Introduce `rtt_confidence` as a scalar in `[0.0, 1.0]` derived from ICMP/UDP agreement and queue-direction agreement with the active queue-delay signal, and wire it into DL classification so RTT cannot override a queue-GREEN reading unless `rtt_confidence >= 0.6` and queue and RTT agree in direction. Tighten the fusion healer bypass gate so bypass enters only when queue-distress AND RTT-distress are both sustained in the same worsening-or-held direction for 6 consecutive cycles — single-path flips never bypass. Magnitude ratios between queue µs and RTT ms are never used as the alignment metric; alignment is categorical direction-over-N-cycles only. The healer remains scoped to its existing ICMP/IRTT relationship; arbitration sits above it.

**Requirements addressed:** ARB-02, ARB-03, SAFE-05

**Depends on:** Phase 194, v1.39 Phase 192 (requires the corrected blackout-aware reflector scorer so `rtt_confidence` input is not polluted by blackout-misattributed per-host score decay; without Phase 192, ICMP agreement inputs would be biased and `rtt_confidence` would read falsely low during carrier blackouts)

**Scope:**
- Derive `rtt_confidence` per cycle from: (a) ICMP/UDP agreement (existing protocol correlation pipeline, now feeding a scalar instead of only a log line), and (b) direction agreement with `queue_delay_delta_us` trend (queue direction over the same cycles RTT is moving). Publish `rtt_confidence` into `/health` `signal_arbitration.rtt_confidence` and the existing `wanctl_rtt_confidence` metric (both already wired in Phase 193 as nullable / stub).
- Update DL classification so that when queue primary is active, RTT can only veto a queue-GREEN reading (escalating DL zone) if `rtt_confidence >= 0.6` AND RTT and queue agree in direction over the last N cycles. When queue primary is inactive (fallback path), Phase 194 behavior holds — RTT path is v1.39 code unchanged.
- Change fusion healer bypass gate: bypass enters only when queue-distress (`queue_delay_delta_us` over its distress threshold — same threshold Phase 194 uses) AND RTT-distress (`rtt_confidence >= 0.6` AND RTT zone at least YELLOW) are both sustained in the same worsening-or-held direction for 6 consecutive cycles. Single-path flips never enter bypass. The alignment metric is categorical (same direction / held for N cycles), never a µs/ms magnitude ratio.
- Set `signal_arbitration.control_decision_reason` to `rtt_veto` when RTT demoted-secondary escalates a queue-GREEN, `healer_bypass` when the 6-cycle alignment trips the healer gate, `queue_distress` when queue drives distress on its own, and `green_stable` otherwise.
- No change to state-machine rules, EWMA alphas, dwell, deadband, burst detection, thresholds, or rate compute. Arbitration changes what feeds the classifier and how the healer decides bypass — it does not change classification rules themselves.

**Out of scope (locked):**
- UL classification changes (v1.40 DL-only, ARB-04).
- Any state-machine / EWMA / dwell / deadband / burst / threshold change (SAFE-05).
- Re-enabling fusion on Spectrum or ATT — fusion workaround state stays as-is.
- Magnitude ratio between queue µs and RTT ms as alignment metric (explicitly rejected).
- Python-learned idle baseline for queue delay (MEAS-07).
- Changes to reflector scorer — that is v1.39 Phase 192's scope and is consumed as-is.

**Success Criteria:**
1. `rtt_confidence` is observed in `/health` and in the metrics SQLite store as a non-null float in `[0.0, 1.0]` across a 1-hour production window on cake_signal-supported WANs, with values tracking ICMP/UDP agreement and queue direction agreement in operator-inspectable ways.
2. A traced scenario where queue reads GREEN but RTT spikes with `rtt_confidence < 0.6` (protocol disagreement) does NOT escalate DL zone — operator can verify via `control_decision_reason != "rtt_veto"` and zone transitions absent in that window.
3. A traced single-path flip (e.g., ICMP-only anti-correlation event with queue GREEN for 6 cycles) does NOT enter healer bypass — `control_decision_reason` never shows `healer_bypass` in that window, matching the direction-alignment gate.
4. A replay of the 2026-04-23 Spectrum production event (ICMP/UDP ratio flipping 1.96→0.54, fusion.healer suspending, wanctl clamping on phantom bloat in v1.39) through the Phase 195 build produces queue-primary distress only where the kernel queue-delta actually grew — not on RTT-only phantom bloat — and healer bypass does not trip on the single-path flip.

**Plans:** 3/3 plans complete

Plans:
- [x] 195-01-PLAN.md — Confidence derivation + observability (SAFE-05)
- [x] 195-02-PLAN.md — RTT veto + 6-cycle healer bypass containment (ARB-02, ARB-03, SAFE-05)
- [x] 195-03-PLAN.md — Replay harness + 2026-04-23 Spectrum event + 195-VERIFICATION.md (ARB-02, ARB-03, SAFE-05)

---

## Phase 196: Spectrum A/B Soak and ATT Regression Canary

**Goal:** Close v1.40 with production validation. Run sequential 24-hour soaks on the same Spectrum deployment: first 24h at `rtt-blend` (v1.39 arbitration behavior — queue-primary code paths disabled via feature gate), then 24h at `cake-primary` (v1.40 arbitration fully enabled). Validate that DL `tcp_12down` throughput under cake-primary recovers to within 90% of the 591 Mbps CAKE-only static floor measured on 2026-04-23, without regressing RTT-distress behavior compared to the rtt-blend leg. Run the ATT regression canary only after v1.39 Phase 191 closure, requiring ATT DL `tcp_12down` to not regress more than 5% vs the last passing ATT run.

**Requirements addressed:** VALN-04, VALN-05, SAFE-05

**Depends on:** Phase 195, v1.39 Phase 192 (Phase 192 24h Spectrum soak must complete first — serialized Spectrum soak calendar, no concurrent Spectrum experiments, VALN-04), v1.39 Phase 191 closure (ATT canary only — ATT weather-rerun must land before any ATT cake-primary regression testing)

**Scope:**
- Schedule and execute 24h Spectrum soak at `rtt-blend` (feature gate disabled, v1.39 behavior path) — this is the A baseline leg. Capture: `tcp_12down` throughput median + p99 latency, RRUL grade and latency percentiles, VoIP jitter, RTT-distress event counts, burst detection trigger counts, dwell-bypass responsiveness, fusion state transitions, `/health` `signal_arbitration` block and `wanctl_arbitration_active_primary` metric over the full 24h.
- Schedule and execute 24h Spectrum soak at `cake-primary` (feature gate enabled, v1.40 arbitration fully live) — this is the B leg. Capture the same measurement set.
- Validate VALN-05 Spectrum acceptance: DL `tcp_12down` 30s median throughput under cake-primary ≥ 532 Mbps (90% of 591 Mbps CAKE-only-static floor from 2026-04-23). Captured at least once before Phase 196 ships.
- Validate non-regression vs rtt-blend leg: burst detection trigger count, dwell-bypass responsiveness, and fusion state transitions are at least as healthy on cake-primary as on rtt-blend. RTT-distress event counts on cake-primary do not grow beyond rtt-blend leg — arbitration must not create new RTT-distress signals, it should reduce phantom ones.
- After v1.39 Phase 191 closes, run the ATT regression canary: one ATT `tcp_12down` run under cake-primary. Acceptance: ATT DL `tcp_12down` throughput ≥ 95% of the last passing ATT `tcp_12down` baseline. If ATT regresses >5%, do not ship ATT cake-primary enablement — roll ATT back to `rtt-blend` and record a follow-up phase.
- No concurrent Spectrum experiments during either soak leg — Spectrum soak calendar is strictly serialized (VALN-04).
- No state-machine, threshold, EWMA, dwell, deadband, or burst-detection changes in this phase (SAFE-05); this phase only validates Phase 193-195 output.

**Out of scope (locked):**
- Any tuning parameter change during or after the soak. If a failure mode is discovered, follow-up is a new phase, not an inline tweak.
- Concurrent Spectrum soaks / overlapping experiments (VALN-04).
- ATT cake-primary canary before v1.39 Phase 191 closure.
- Re-enabling fusion on Spectrum or ATT — fusion workaround stays as-is, independent of v1.40 shipping.
- Python-learned idle baseline for queue delay (MEAS-07).
- Any v1.39 Phase 192 work — Phase 192 is a dependency, not in-scope for Phase 196.

**Success Criteria:**
1. Spectrum 24h `rtt-blend` soak completes with `/health`, SQLite metrics, and `tcp_12down` / RRUL / VoIP capture intact, serving as the A baseline leg. `signal_arbitration.active_primary_signal == "rtt"` throughout this leg on Spectrum.
2. Spectrum 24h `cake-primary` soak completes under VALN-04 serialization — no concurrent Spectrum experiments ran, and v1.39 Phase 192 soak completed before this leg started. `signal_arbitration.active_primary_signal == "queue"` is observed across the cake-primary leg on Spectrum under load, matching `wanctl_arbitration_active_primary == 1` in metrics.
3. Spectrum DL `tcp_12down` 30s median throughput under cake-primary is ≥ 532 Mbps (90% of 591 Mbps floor from 2026-04-23), captured at least once before Phase 196 ships. Burst detection trigger count, dwell-bypass responsiveness, and fusion state transitions on the cake-primary leg are at least as healthy as on the rtt-blend leg.
4. After v1.39 Phase 191 closure, the ATT `tcp_12down` canary under cake-primary runs and either (a) passes at ≥95% of last passing ATT baseline, clearing ATT for cake-primary enablement, or (b) fails and ATT is rolled back to rtt-blend with a recorded follow-up phase — no silent ATT regression reaches production.

**Plans:** 6/8 plans executed

Plans:
- [x] 196-01-PLAN.md — Preflight, mode-gate validation, capture tooling, and verification scaffold (VALN-04, VALN-05, SAFE-05)
- [x] 196-02-PLAN.md — Spectrum 24h `rtt-blend` A-leg baseline with full-window primary-signal audit (VALN-04, SAFE-05)
- [x] 196-03-PLAN.md — Spectrum 24h `cake-primary` B-leg, throughput acceptance, and A/B comparison (VALN-04, VALN-05, SAFE-05)
- [x] 196-04-PLAN.md — ATT canary gate, optional ATT `cake-primary` canary, rollback/follow-up, and closeout (VALN-05, SAFE-05)
- [x] 196-05-PLAN.md — Spectrum reversible mode gate proof and preflight reopen (VALN-04, SAFE-05)
- [x] 196-06-PLAN.md — Spectrum `rtt-blend` A-leg finish audit and flent baseline (VALN-04 partial, SAFE-05)
- [ ] 196-07-PLAN.md — Spectrum `cake-primary` B-leg and A/B comparison (VALN-04, VALN-05, SAFE-05)
- [ ] 196-08-PLAN.md — ATT canary closeout after Phase 191 closure (VALN-05, SAFE-05)

Closeout status: Phase 196 is in progress. Spectrum `rtt-blend` A-leg evidence
now passes after 28.2311h with zero non-RTT arbitration samples, but the
`cake-primary` B-leg/A-B comparison and ATT canary remain pending. VALN-04 is
partial, VALN-05 remains blocked, and SAFE-05 remains complete.

---

## Ordering Rationale

Phase 193 ships first because it is observability-only and carries zero control-behavior risk — it lets Phase 194's classification change land on a proven data contract. Phase 194 precedes Phase 195 because DL queue-primary classification is a prerequisite for RTT demotion to have meaning: `rtt_confidence` is only useful if queue-primary is already driving distress. Phase 195 depends on v1.39 Phase 192 because the corrected blackout-aware reflector scorer is an input to the ICMP agreement side of `rtt_confidence` — without Phase 192, `rtt_confidence` would read falsely low during carrier blackouts and the new healer bypass gate would be calibrated on a polluted signal. Phase 196 runs last and is serialized against v1.39 Phase 192's 24h Spectrum soak (VALN-04: no concurrent Spectrum experiments) and against v1.39 Phase 191 closure (ATT canary only). Spectrum A/B ordering (rtt-blend then cake-primary) lets the same deployment provide the baseline and the comparison leg, and separating ATT behind Phase 191 closure keeps ATT weather-confounded reruns from contaminating v1.40 attribution.

*v1.40 roadmap created: 2026-04-23*
