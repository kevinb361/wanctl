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

# Roadmap: wanctl v1.41 Per-Direction Control Surfaces

**Milestone Goal:** Decouple UL and DL control thresholds so latency-first UL configurations are possible on deployments where UL saturation under DL-shared thresholds causes oscillation. Headline phase resolves the Spectrum UL collapse-to-floor pattern observed in production 2026-04-29 (live UL hysteresis storm visible at 5 → 15 → 31 suppressions/60s while DL=0). Single-phase milestone; v1.41 may grow if Phase 200 surfaces follow-on work.

**Phases:** 1 | **Requirements mapped:** 4/4 ✓

## Phase Summary

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 200 | Per-Direction RTT Bloat Thresholds (Spectrum UL Saturation Containment) | 5/8 | In Progress|  |

---

## Phase 200: Per-Direction RTT Bloat Thresholds (Spectrum UL Saturation Containment)

**Goal:** Add optional `continuous_monitoring.upload.target_bloat_ms` and `continuous_monitoring.upload.warn_bloat_ms` keys so the legacy 3-state UL controller can use thresholds independent of the DL 4-state thresholds. Behavior is byte-identical when the new keys are absent (preserves all non-Spectrum deployments). On Spectrum, adopt the new keys at 42/105 ms and lower the upload ceiling 28→18 Mbps (latency-first gaming-server soak), with operator evidence trail in three `.planning/spectrum-*-2026-04-29.md` notes. Close the validator silent-ignore gap that allowed prod /etc/wanctl/spectrum.yaml to carry 4 unrecognized keys for 3 days. Ship a 10–15 min saturated UL canary as the deploy gate; 24h soak as regression watchdog.

**Requirements addressed:** ARB-05, SAFE-06, VALN-06, DOCS-03

**Depends on:** v1.40 closure (no overlap with queue-primary arbitration paths; DL classification is byte-identical)

**Scope:**
- Add optional UL-specific RTT bloat threshold keys to `autorate_config.py` schema (1–200 ms target, 1–250 ms warn, ordering check)
- Update `wan_controller.py` to seed `target_delta` / `warn_delta` from per-direction config when present, else fall back to global; add per-key explicit-presence flags `_upload_target_bloat_ms_explicit` and `_upload_warn_bloat_ms_explicit` (Codex bug fix: must NOT be value-derived)
- Update `_apply_threshold_param` to gate UL field writes per-flag (each flag protects its own field independently)
- Update `check_config_validators.py` `KNOWN_AUTORATE_PATHS` to register the new keys
- Add SAFE-06: validator rejects (or audibly warns on every startup) any unknown `continuous_monitoring.*` key
- Update `tests/test_phase_195_replay.py::test_safe05_threshold_name_counts_are_unchanged` expected counts (D-13: warn_bloat 4 → 6, target_bloat 4 → 6)
- Spectrum YAML: ceiling_mbps 28 → 18, factor_down_yellow 0.98, target_bloat_ms 42, warn_bloat_ms 105
- Version bump to 1.41.0 in `pyproject.toml`, `src/wanctl/__init__.py`, `docker/Dockerfile`
- CHANGELOG.md entry + `docs/CONFIGURATION.md` migration note (restart-required, SIGUSR1 does not reload these keys)
- Pre-deploy canary: 10–15 min `iperf3 -P4` saturated UL loop at 18 Mbit; predefined rollback to v1.40 binary if UL collapses to floor in any cycle
- 24h Spectrum UL regression soak after canary passes; UL hysteresis suppression rate must drop from current 31/60s to near-zero

**Out of scope (locked):**
- Per-direction DL state-machine threshold split (DL is healthy; v1.41 is UL-only)
- New `/health` per-direction telemetry block (UL is already observable)
- Refactoring `initialize_cake` complexity (C901 noqa stays; control-path refactor risk)
- ATT cake-primary canary (VALN-05b inherited deferral from v1.40)
- Coverage push >90% (pre-existing v1.40 debt; v1.41 tests will likely cross naturally)

**Success Criteria:**
1. The autorate config schema accepts the new optional UL-threshold keys, validates `target < warn` ordering, and falls back to DL globals byte-identically when absent. Verified by 4 new tests in `tests/test_autorate_config.py` (defaults, override, ordering violation) and `tests/test_wan_controller.py` (per-key presence wiring).
2. The validator emits a WARNING log entry on startup when any unknown `continuous_monitoring.*` key is present in the deployment YAML. Verified by a new test that exercises the unknown-key path and asserts the log emission.
3. The 10–15 min saturated `iperf3 -P4` UL canary at 18 Mbit ceiling on Spectrum completes without the UL controller collapsing to the 8 Mbit floor in any cycle. Pre/post idle baselines bookend the run; canary fails if any single cycle reaches floor.
4. The 24h Spectrum UL regression soak after canary passes shows UL hysteresis suppression rate drops below 5/60s on average (down from the current 31/60s degraded state).
5. CHANGELOG.md and `docs/CONFIGURATION.md` carry the migration note specifying that the new keys require a service restart to take effect (SIGUSR1 does not reload these). Verified by greps for the keys in both files.

**Plans:** 5/8 plans executed

---

## v1.41 Ordering Rationale

Single-phase milestone. Phase 200 is the only deliverable; no inter-phase ordering decisions required. Phase 200 has a hard production-state precondition: prod `/etc/wanctl/spectrum.yaml` already carries the new UL keys with no matching deployed code, so production is in a known-degraded state from 2026-04-29 onward. Phase 200 ships in a single sequence: bug-fix the diff (Codex finding D-11) → version bump → CHANGELOG → tests → canary → deploy → 24h soak. Cross-milestone dependency on v1.39 Phase 191 (ATT canary VALN-05b) inherits as deferred; v1.41 does not block on it.

*v1.41 roadmap created: 2026-05-03*

---

# Archived Milestones

- **v1.40 Queue-Primary Signal Arbitration** (shipped 2026-05-03) — see `.planning/milestones/v1.40-ROADMAP.md`
