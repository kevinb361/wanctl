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
| 200 | Per-Direction RTT Bloat Thresholds (Spectrum UL Saturation Containment) | 16/16 | Closed (gaps_found) — ARB-05/SAFE-06/DOCS-03 satisfied; VALN-06 deferred to Phase 201 (inherited blocking requirement) by operator escalation 2026-05-04 | 2026-05-04 |

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
3. The 10–15 min saturated `iperf3 -P4` UL canary at 18 Mbit ceiling on Spectrum completes without the UL controller collapsing to the 8 Mbit floor in any cycle. Pre/post idle baselines bookend the run; canary fails if any single cycle reaches floor. **(Deferred to Phase 201 — see `200-RETRO.md`. Plan 200-14 Attempt 3 reduced loaded-window floor hits from 122 to 4; zero-hit gate not reached; operator escalated 2026-05-04. Inherited as blocking requirement under Phase 201.)**
4. The 24h Spectrum UL regression soak after canary passes shows UL hysteresis suppression rate drops below 5/60s on average (down from the current 31/60s degraded state). **(Deferred to Phase 201 — see `200-RETRO.md`. Soak watchdog never ran because the canary gate failed; deferral is not a measurement claim. Inherited as blocking requirement under Phase 201.)**
5. CHANGELOG.md and `docs/CONFIGURATION.md` carry the migration note specifying that the new keys require a service restart to take effect (SIGUSR1 does not reload these). Verified by greps for the keys in both files.

**Plans:** 16/16 plans complete — Phase 200 closed as `gaps_found` with operator-escalated deferral of VALN-06 to Phase 201 (`docsis-aware-ul-congestion-control`) on 2026-05-04 as an inherited blocking requirement. ARB-05, SAFE-06, and DOCS-03 are satisfied. Plan 200-14 Attempt 3 canary improved loaded-window UL floor hits 122 -> 4 but did not reach zero; the residual failure regime is shaping-headroom dominated and is Phase 201's seeded scope. No second Phase 200 remediation was attempted. Production binary remains v1.40 post-rollback; v1.41 YAML keys remain on prod `/etc/wanctl/spectrum.yaml` and are inactive under v1.40 but MUST be reconciled before any future Spectrum deploy or service restart (Phase 201 predeploy gate is required to inspect the file and either reconcile or fail closed). See `200-VERIFICATION.md` `closure: deferred-to-phase-201`, `200-RETRO.md` `## Final Closure (2026-05-04)`, and direct evidence at `canary/20260504T133207Z/verdict.json`.

---

## v1.41 Ordering Rationale

Single-phase milestone. Phase 200 is the only deliverable; no inter-phase ordering decisions required. Phase 200 has a hard production-state precondition: prod `/etc/wanctl/spectrum.yaml` already carries the new UL keys with no matching deployed code, so production is in a known-degraded state from 2026-04-29 onward. Phase 200 ships in a single sequence: bug-fix the diff (Codex finding D-11) → version bump → CHANGELOG → tests → canary → deploy → 24h soak. Cross-milestone dependency on v1.39 Phase 191 (ATT canary VALN-05b) inherits as deferred; v1.41 does not block on it.

*v1.41 roadmap created: 2026-05-03*

---

# Roadmap: wanctl v1.42 DOCSIS-Aware UL Congestion Control

**Milestone Goal:** Close VALN-06 (inherited blocking from Phase 200) by replacing the rejected per-direction-thresholds hypothesis with a DOCSIS-aware UL control mode that runs a conservative YAML setpoint as the operating point and uses a windowed RTT integral (with CAKE backlog as direction-aligned secondary corroborator) as the headroom probe. YAML opt-in keyed off `continuous_monitoring.upload.docsis_mode: true`; absent or `false` preserves byte-identical legacy behavior for all non-Spectrum deployments (CLAUDE.md NON-NEGOTIABLE: portable controller architecture).

**Phases:** 1 | **Requirements mapped:** 1/1 ✓ (VALN-06 inherited blocking)

## Phase Summary

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 201 | DOCSIS-Aware UL Congestion Control | 16/16 | Closed (gaps_found) — D-19 primary VALN-06 PASS shipped on v1.42.1; D-14 suppression watchdog deferred to v1.43+ as metric_semantics_and_recalibration; Plan 201-12 superseded by Plan 201-16 (17 PLAN.md files materialized total) | 2026-05-06 |

---

## Phase 201: DOCSIS-Aware UL Congestion Control

**Goal:** Ship a DOCSIS-aware UL congestion control mode that holds Spectrum DOCSIS upload off the floor under saturated load. The mode runs a YAML setpoint well below the upload ceiling and uses a windowed RTT integral as the headroom probe (with CAKE backlog as direction-aligned secondary corroborator) to decide when to push toward the ceiling. YAML opt-in; non-DOCSIS deployments stay byte-identical.

**Requirements addressed:** VALN-06 (inherited blocking from Phase 200; closure shape per `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-VERIFICATION.md` `closure: deferred-to-phase-201`, `inherited_as: blocking_requirement`)

**Depends on:** Phase 200 closure (gaps_found 2026-05-04). v1.41 ceiling drop 28→18 Mbit and YAML key registration are orthogonal latency-first decisions and are preserved.

**Scope:**
- New YAML keys under `continuous_monitoring.upload.*`: `docsis_mode: bool` (default `false`), `setpoint_mbps: int|float` (REQUIRED when `docsis_mode: true`; validator fails closed if missing), windowed RTT-integral keys (planner finalizes naming + ordering)
- Register new keys in `KNOWN_AUTORATE_PATHS` (`src/wanctl/check_config_validators.py:28-180`); honor existing ordering-check pattern (`src/wanctl/autorate_config.py:182-194`)
- RTT-integral classifier: replace or augment `_classify_zone_3state()` (`src/wanctl/queue_controller.py:139-182`) with integral-of-RTT-over-baseline metric over a configurable window; planner decides replace vs augment based on RESEARCH.md
- Setpoint clamp pre-classifier integration in `_compute_rate_3state()` (`src/wanctl/queue_controller.py:229-256`); CAKE-backlog corroborator wired through `CakeSignalSnapshot` (`src/wanctl/cake_signal.py:85-123`) at UL cycle invocation (`src/wanctl/wan_controller.py:2978-2984`); push-to-ceiling requires RTT-integral low for sustained window AND CAKE direction-aligned (categorical, never µs/ms magnitude ratio); single-signal flips do not bypass
- Spectrum YAML (`configs/spectrum.yaml`): `docsis_mode: true`, `setpoint_mbps: 12` (60% of ~20 Mbit provisioned upstream — subject to challenge by researcher / planner / cross-AI review against the three Spectrum sweep notes); upload ceiling preserved at 18 Mbit; floor preserved at 8 Mbit
- Predeploy gate that inspects `/etc/wanctl/spectrum.yaml` on deploy target for v1.41-only rejected-hypothesis keys (`target_bloat_ms`, `warn_bloat_ms`, `consecutive_yellow_decay_clamp`, `factor_down_yellow=1.0`) and either reconciles with Phase 201's design or fails closed before the deploy proceeds
- `/health` payload extension: NEW additive fields under `.wans[].upload` (candidates: `setpoint_mbps`, `headroom_mbps`, `rtt_integral_ms_s`, `docsis_state`, `docsis_mode_active`); runtime-state semantics, not config echoes (Phase 200 RETRO lesson); planner finalizes naming
- Restart-required for new keys (SIGUSR1 reload scope stays at dwell/deadband only, `src/wanctl/wan_controller.py:1894-1899`); migration note in `docs/CONFIGURATION.md` and `CHANGELOG.md` mirroring Phase 200 DOCS-03 pattern
- Reuse `scripts/phase200-saturation-canary.sh`; extend preflight YAML cross-check (`scripts/phase200-saturation-canary.sh:314-358`) to also cross-check `docsis_mode: true` and `setpoint_mbps`; add /health probe asserting DOCSIS-mode telemetry block is live before saturation begins; same fail-closed pattern + rollback to v1.40 on any loaded-cycle floor hit
- 24h Spectrum UL regression soak watchdog at `<5/60s` UL hysteresis suppression rate (unchanged from inherited Phase 200 closure shape)
- Version bump to 1.42.0 in `pyproject.toml`, `src/wanctl/__init__.py`, `docker/Dockerfile`
- Codex pre-review before plan implementation AND Codex stop-time review after deploy machinery is in place; both required, not optional (Phase 200 RETRO "high-leverage on production-control work")

**Out of scope (locked):**
- Modem SNMP / DOCSIS HCS counters (D-05 — new transport + firmware dependency; RTT-integral + CAKE corroborator is sufficient on available signals)
- Live-tunable DOCSIS-mode keys via SIGUSR1 (D-08 — restart-required; control-path stability)
- Global default for `setpoint_mbps` (D-07 — setpoint is link-specific; principled defaults not knowable without per-link evidence)
- `setpoint_pct` companion key (D-07 — rejected to keep validator + ordering surface minimal)
- ATT, fiber, DSL, and other non-DOCSIS YAMLs (D-17 — absence of `docsis_mode` preserves legacy 3-state UL behavior verbatim; no edits)
- Tightening soak watchdog below `<5/60s` (D-14 — premature before zero-floor-hit canary first proves the mode; v1.43+ may revisit if Phase 201 soak data supports)
- Per-direction DL state-machine changes (DL is healthy; v1.42 is UL-only, same scope discipline as v1.41)

**Success Criteria:**
1. The autorate config schema accepts `docsis_mode`, `setpoint_mbps`, and the windowed RTT-integral keys; enforces `setpoint_mbps` REQUIRED when `docsis_mode: true` (validator fails closed if missing); preserves byte-identical legacy 3-state UL behavior when `docsis_mode` is absent or `false`. Verified by new tests covering defaults, opt-in, missing-required validator failure, and key ordering.
2. The 10–15 min saturated `iperf3 -P4` UL canary at the deployed Spectrum ceiling completes with `ul_floor_hits_during_load=0` (zero loaded-window floor-hit cycles); pre/post idle baselines bookend the run; canary fails if any single loaded cycle reaches floor; same fail-closed rollback to v1.40 on canary fail. Direct evidence Phase 201 must improve upon: `.planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260504T133207Z/verdict.json` (`verdict: fail`, `ul_floor_hits_during_load: 4`). **(SATISFIED 2026-05-05 — recanary `20260505T122513Z` PASSED with `verdict=pass`, `primary_gate_value=0`, `ul_floor_hits_during_load=0`. Phase-goal D-19 primary VALN-06 closure evidence on v1.42.1.)**
3. The 24h Spectrum UL regression soak after canary passes shows UL hysteresis suppression rate drops below 5/60s on average. Soak watchdog gates closure; failure rolls back. **Plan 201-16 result:** D-19 primary floor-hit delta passed at `0`, but the preserved D-14 secondary watchdog failed with `ul_hysteresis_suppression_rate_per_60s_mean=6.466842364880155`; Phase 201 remains gaps_found pending operator next-action decision. **(Closed Route B 2026-05-06 — operator decision: D-19 primary PASS satisfies the dominant phase-goal proof; D-14 secondary deferred to v1.43+ as `metric_semantics_and_recalibration`. See `201-RETRO.md`.)**
4. The predeploy gate inspects `/etc/wanctl/spectrum.yaml` on the deploy target and either reconciles v1.41-only rejected-hypothesis keys with Phase 201's own design or fails closed before the deploy proceeds. Verified by canary preflight log evidence.
5. `CHANGELOG.md` and `docs/CONFIGURATION.md` carry the migration note specifying that `docsis_mode`, `setpoint_mbps`, and the RTT-integral window keys require a service restart to take effect (SIGUSR1 does not reload these). Verified by greps for the keys in both files.

**Plans:** 16/16 active plans complete (Plan 201-12 superseded by Plan 201-16; 17 PLAN.md files materialized total) — Phase 201 closed as `gaps_found` 2026-05-06 via operator Route B. D-19 primary VALN-06 floor-hit gate PASSED on canary `20260505T122513Z` and 24h soak `20260505T132736Z` (production binary v1.42.1 with rollback evidence at `canary/20260505T122513Z/` and `soak/20260505T132736Z/`). D-14 secondary suppression watchdog FAILED at `6.466842364880155/60s` mean (vs `<5.0`); FAIL is on the YELLOW-edge dwell-hold path (`queue_controller.py:348`), unrelated to the bounded RED decay path Plan 201-14 fixed (`queue_controller.py:361-376`), and the original threshold was never soak-calibrated against the post-fix control surface. D-14 work deferred to v1.43 as four ordered backlog items (`SEED-002`..`SEED-005`). See `201-RETRO.md` and `201-VERIFICATION.md` `closure_route` block.

Plans:
- [x] 201-01-corpus-inspection-and-fixtures-PLAN.md — Wave 0 corpus audit + replay-corpus loader + synthetic-trace fixtures (resolves Open Questions 1 + 2)
- [x] 201-02-test-stubs-PLAN.md — Wave 0 RED scaffolding for all Phase 201 production-code surfaces (14 named test classes across 7 test files)
- [x] 201-03-config-schema-and-validators-PLAN.md — Schema entries + presence flags + required-when-other validation; KNOWN_AUTORATE_PATHS registration; SAFE-05 v1.42 baseline (D-06, SAFE-06, D-03)
- [x] 201-04-controller-core-PLAN.md — QueueController DOCSIS-mode internals: integral, CAKE corroborator, setpoint clamp; Attempt 3 replay revised to RED-heavy floor-hit diagnostic (Plan 201-11 remains VALN-06 gate)
- [x] 201-05-wan-controller-and-health-PLAN.md — WANController constructor wiring + presence flags + INFO log + 5 additive /health runtime-state fields (D-16, D-08)
- [x] 201-06-spectrum-yaml-and-version-PLAN.md — configs/spectrum.yaml R5+R3 keep + R0 strip + setpoint=12; version 1.42.0; CHANGELOG + CONFIGURATION migration (D-09, D-10, RESEARCH §5)
- [x] 201-07-predeploy-gate-PLAN.md — scripts/phase201-predeploy-gate.sh fail-closed against rejected v1.41 keys; deploy.sh integration (D-15)
- [x] 201-08-canary-script-extension-PLAN.md — D-12 preflight extension: env-vs-YAML cross-check + /health DOCSIS-mode probe + WR-02 closure; max_delay_delta_us capture
- [x] 201-09-codex-pre-review-PLAN.md — Cross-AI pre-review checkpoint before Wave 2 implementation (D-18 first leg); verdict BLOCK, amendments required before Wave 1+ continues
- [x] 201-10-codex-stop-time-review-PLAN.md — Cross-AI stop-time review checkpoint before live canary (D-18 second leg); GO WITH FOLLOW-UPS, no HIGH findings
- [x] 201-11-canary-execution-PLAN.md — Live 10-15 min iperf3 -P4 saturated UL canary FAILED at setpoint_mbps=12 (`verdict: fail`, reason `ul_floor_hits_during_load_84_counter_delta_1453`); D-10 rollback restored both binary and YAML; see `201-11-CANARY-VERDICT.md`
- [ ] 201-12-soak-and-closeout-PLAN.md — (superseded) Superseded by revised Plan 201-16 after Plan 201-15 re-canary PASS; do not execute this stale soak path
- [x] 201-13-health-diagnostic-extension-PLAN.md — Additive upload `/health` diagnostics for post-canary root cause: `max_delay_delta_us`, `red_streak`, bounded `zone_trace`, anti-windup counters, and red-decay runtime knob echoes; `sustained_red_cycles` remains absent
- [x] 201-14-control-model-amendment-PLAN.md — Gap-closure control-model amendment with bounded absolute RED decay, integral anti-windup, and red-decay config validators
- [x] 201-15-recanary-PLAN.md — Re-canary PASS after control-model amendment: `primary_gate_value=0`, `ul_floor_hits_during_load=0`, T+0 soak baseline `0`, active-knob proof, two-snapshot rollback evidence, and version/build identity evidence
- [x] 201-16-soak-and-closeout-PLAN.md — 24h Spectrum soak after passing recanary; verdict FAIL because D-19 primary gate passed but D-14 secondary suppression watchdog failed (`soak/20260505T132736Z/soak-summary.json`)
- [x] 201-17-closeout-PLAN.md — Phase 201 closeout per operator Route B 2026-05-06: documentation-state correction (REQUIREMENTS/ROADMAP/STATE/CONTEXT/VERIFICATION), 201-RETRO.md authored, four v1.43 backlog seeds opened in priority order; NO production binary or YAML change


---

## v1.42 Ordering Rationale

Single-phase milestone seeded by Phase 200's operator-escalated VALN-06 deferral on 2026-05-04. Phase 200 RETRO's architectural diagnosis (residual failure regime is shaping-headroom dominated, not threshold dominated) eliminates the spike-first ambiguity that would otherwise apply to a new control mode. Phase 201 ships in a single sequence: research → plan (with cross-AI review) → predeploy gate → canary → deploy → 24h soak.

*v1.42 roadmap created: 2026-05-04*

---

# Archived Milestones

- **v1.40 Queue-Primary Signal Arbitration** (shipped 2026-05-03) — see `.planning/milestones/v1.40-ROADMAP.md`
