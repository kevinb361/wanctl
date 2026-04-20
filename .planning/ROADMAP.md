# Roadmap: wanctl v1.39 Control-Path Timing & Measurement Accounting

**Milestone Goal:** Reduce systemic tail latency in the netlink apply path and fix reflector-scorer blackout misattribution without changing any control algorithms, thresholds, or state machines.

**Phases:** 3 | **Requirements mapped:** 11/11 ✓

## Phase Summary

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 191 | Netlink Apply Timing Stabilization | Instrument and reduce `tc dump` vs `tc change` kernel RTNL contention that spikes netlink apply latency to 10–87 ms | TIME-01, TIME-02, TIME-03, TIME-04, SAFE-03, SAFE-04, VALN-02 | 5 |
| 191.1 | ATT Config Drift Resolution and Phase 191 Closure | 1/3 | In Progress|  |
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
**Plans:** 1/3 plans executed

Plans:
- [x] 191.1-01-att-config-restoration-PLAN.md - restore irtt.server and fusion.enabled to v1.38 values in configs/att.yaml (single coordinated edit per D-03)
- [ ] 191.1-02-validation-rerun-PLAN.md - deploy restored ATT config and capture ATT rrul/tcp_12down/voip plus Spectrum RRUL discriminator via scripts/phase191-flent-capture.sh
- [ ] 191.1-03-closure-artifact-update-PLAN.md - add phase-local SAFE-03 comparator rule and restored-config rerun evidence to 191-VERIFICATION.md and 191-05-SUMMARY.md

## Phase 192: Reflector Scorer Blackout-Awareness + Log Hygiene

**Goal:** Fix the reflector scorer so it recognizes all-host zero-success cycles as blackout events and does not decrement per-host quality windows for those cycles. Rate-limit or demote fusion-suspended "Protocol deprioritization detected" INFO log noise. Close v1.39 with a 24-hour soak confirming no regression.

**Requirements addressed:** MEAS-05, MEAS-06, OPER-02, SAFE-03, VALN-02, VALN-03

**Depends on:** Phase 191.1 (timing closeout and ATT validation path must be resolved before the scorer soak begins)

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

---

## Ordering Rationale

Phase 191 ships before Phase 192 because the timing change affects *both* WANs systemically while the scorer change only affects measurement accounting on Spectrum. Phase 191.1 exists because ATT validation isolated a post-`v1.38` config/runtime drift issue that must be resolved before the scorer soak starts. Separating them also lets the 24-hour soak per change attribute regressions cleanly — if we shipped together, a regression in dwell-bypass could be blamed on either.

*Roadmap created: 2026-04-20*
