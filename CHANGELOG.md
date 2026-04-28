# Changelog

All notable changes to wanctl are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- v1.40 queue-primary signal arbitration work from Phases 193-197: additive `/health.signal_arbitration` surfacing, queue-delay arbitration metrics, DL queue-primary distress classification, RTT-confidence demotion, and fusion-healer containment.
- Phase 197 refractory arbitration observability, including `queue_during_refractory` and `rtt_fallback_during_refractory` reason values plus the `wanctl_arbitration_refractory_active` metric.
- Phase 198 Spectrum cake-primary B-leg rerun evidence workflow started against the Phase 197 build.

### Changed

- DL CAKE handling now separates refractory-masked detection input from live arbitration input so Phase 160 cascade safety can coexist with queue-primary arbitration during refractory windows.

### Known Gaps

- v1.40 remains unreleased: `.planning/v1.40-MILESTONE-AUDIT.md` records `VALN-04` and `VALN-05` as unsatisfied, with Phase 196 blocked by Spectrum throughput failure and ATT canary gating on Phase 191 closure.
- `wanctl_rtt_confidence` metric emission is still gated on non-`None` confidence, which differs from the v1.40 OBS-02 wording that described per-cycle emission.

## [1.39.0] - 2026-04-24

### Added

- Phase 192 additive `/health` surfacing for `download.hysteresis.dwell_bypassed_count`.
- Portable `scripts/phase192-soak-capture.sh` helper for D-08 dwell, burst, fusion transition, and protocol-deprioritization evidence.
- Phase 192 waiver and soak verification artifacts for proceeding despite the unresolved Phase 191 ATT RRUL comparator blocker.

### Fixed

- Guarded `WANController.measure_rtt()` so only real `RTTCycleStatus` objects enter the zero-success blackout path, preserving compatibility with existing background-thread test doubles.

## [1.38.0] - 2026-04-15

### Added

- Explicit measurement-health contract for degraded RTT conditions, including machine-readable reflector quorum and stale/current cycle status on the health surface.
- Replayable operator verification and traceability artifacts for correlating measurement degradation with controller behavior.

### Fixed

- Zero-success cached-RTT honesty gap: current-cycle RTT status now reflects degraded measurement without overwriting cached RTT or changing the existing stale-cache fallback cutoff.

### Verified

- `.planning/v1.38-MILESTONE-AUDIT.md` records 8/8 requirements, 5/5 phases, 5/5 integration checks, and 4/4 flows complete, with only non-blocking validation-document debt.

## [1.37.0] - 2026-04-14

### Added

- Dashboard History tab source framing for endpoint-local HTTP history, translated `metadata.source` detail, and an immutable merged-CLI handoff.
- Regression coverage for success, fetch-error, source-missing, mode-missing, and db-paths-missing history states.

### Changed

- Deployment, runbook, and getting-started docs now use the same endpoint-local HTTP versus authoritative merged CLI history wording.

### Verified

- `.planning/v1.37-MILESTONE-AUDIT.md` records 5/5 requirements, 3/3 phases, 4/4 integration checks, and 4/4 flows passed with no tech debt.

## [1.36.0] - 2026-04-14

### Added

- Repeatable operator proof path for DB inventory, `storage.status`, and merged CLI history checks.
- Explicit documentation of CLI merged history versus endpoint-local `/metrics/history` reader roles.

### Changed

- Per-WAN retention and storage-maintenance flow aligned with the actual production DB topology without changing controller semantics.

### Fixed

- Startup/watchdog regression caused by heavy pre-health storage work during footprint-reduction rollout.
- ATT per-WAN footprint reduced from about `5.08 GB` to about `202 MB`, satisfying `STOR-06` after the ATT-only compaction run.

### Verified

- `.planning/v1.36-MILESTONE-AUDIT.md` records 5/5 requirements, 6/6 phases, 5/5 integration checks, and 5/5 flows complete, with dashboard history source surfacing carried as non-blocking debt.

## [1.35.0] - 2026-04-13

### Added

- Storage, deploy, canary, operator-summary, and soak-flow evidence coverage for Spectrum, ATT, and `steering.service`.
- Deployment and soak documentation aligned to the active service-based production flow.

### Fixed

- Per-WAN metrics storage handling, periodic SQLite maintenance, and production `analyze_baseline` deploy path issues from the v1.34 storage fallout.

### Verified

- Clean production deploy through the active service flow, passing canary coverage, healthy operator surfaces, and 24-hour soak closeout with no critical requirement or end-to-end flow gaps.
- `.planning/v1.35-MILESTONE-AUDIT.md` records 6/6 requirements, 5/5 phases, 4/4 integration checks, and 3/3 flows complete, with only non-blocking Nyquist/documentation debt.

## [1.34.0] - 2026-04-12

### Added

- Bounded latency-regression, burst-churn, storage-pressure, and runtime-pressure visibility on existing autorate/operator surfaces.
- Compact operator summary surfaces and a post-deploy canary script with offline fixture coverage.
- Operator threshold runbook for alert interpretation, health summaries, canary exit codes, and escalation guidance.

### Fixed

- Storage-status false positive found during live canary validation.

## [1.33.0] - 2026-04-11

### Added

- Production threshold sweep based on a 24-hour idle baseline instead of anecdotal load behavior.
- Storage-contention observability for autorate and steering while preserving the shared SQLite topology.

### Changed

- Five CAKE detection and recovery parameters were A/B tested under RRUL and deployed together after a 24-hour production soak.
- Burst-aware clamp behavior and health/Prometheus observability were retuned to bring `tcp_12down` p99 out of the multi-second range without regressing `rrul_be`.

## [1.32.0] - 2026-04-10

### Added

- CAKE-aware zone classification with dwell bypass on elevated drop rate and green-streak suppression on elevated backlog.
- Refractory-period anti-oscillation with CAKE snapshot wiring, YAML threshold parsing, and health endpoint detection state.
- Exponential rate recovery probing with CAKE signal guards.

### Fixed

- MagicMock JSON serialization leak identified in the milestone accomplishments.

## [1.29.0] - 2026-04-08

### Added

- Dead-code, dependency-import, config-key, AST boundary, parallel-test, and brittleness gates across CI/developer workflows.
- Runtime-checkable protocol definitions and public facade APIs for controller/module boundaries.

### Changed

- Decomposed the autorate monolith into focused controller/config/router modules, extracted `WANController`, split CLI tool modules, and reduced major lifecycle/health functions into smaller helpers.
- Moved storage, tuning, steering, backend, and dashboard tests into mirrored package structures with shared fixtures.

### Fixed

- Ruff, mypy, MagicMock, router config, and private-boundary violations surfaced by the v1.29 cleanup work.

## [1.28.0] - 2026-04-05

### Added

- Bridge QoS with nftables DSCP classification into CAKE diffserv4 Voice, Bulk, and BestEffort tins on Spectrum and ATT bridges.
- Infrastructure IRQ, netdev, SFP+, and ZeroTier binding optimizations for the cake-shaper VM.

### Changed

- Spectrum bridge IRQ load split across CPU0 and CPU2, switch IRQ load rebalanced, and netdev budget doubled.

### Fixed

- ZeroTier wireguard binding issue that caused sustained TX errors; restricting binding to WAN/LAN interfaces reduced the error rate to zero.

## [1.27.0] - 2026-04-03

### Added

- `run_cycle` sub-timers and health endpoint subsystem breakdown for cycle-budget diagnosis.
- Background RTT measurement thread with persistent `ThreadPoolExecutor` and atomic latest-sample handoff.
- Cycle-budget health status and Discord alerting for sustained overruns.
- Per-tin CAKE packet validation for DSCP mark survival.
- Windowed suppression counter and alerting during congestion.

### Changed

- RTT measurement moved out of the hot control loop, eliminating the measured 42ms blocking I/O source from the 50ms cycle path.

## [1.26.0] - 2026-04-03

**Tuning Validation** - Re-tested all tuning parameters on linux-cake transport after
REST-to-linux-cake backend switch. 49 RRUL flent runs across 5 phases. Confirmation pass
caught 1 interaction effect (target_bloat flipped due to CAKE rtt change).

### Changed

- **CAKE rtt** from 50ms to 40ms (tested 25/35/40/50/100ms, 40ms dominated all metrics)
- **DL green_required** from 5 to 3 (faster feedback loop needs fewer confirmation cycles)
- **DL step_up_mbps** from 15 to 10 (smaller steps recover more smoothly on linux-cake)
- **DL factor_down** from 0.90 to 0.85 (more aggressive RED backoff works with faster loop)
- **DL warn_bloat_ms** from 45 to 60 (wider YELLOW-SOFT_RED band with faster reaction)
- **DL hard_red_bloat_ms** from 60 to 100 (wider SOFT_RED band, healthy 60-100ms range)
- **UL step_up_mbps** from 1 to 2 (linux-cake loop fast enough for larger UL steps)

### Confirmed (unchanged from REST transport)

- DL factor_down_yellow=0.92, dwell_cycles=5, deadband_ms=3.0, target_bloat_ms=9
- UL factor_down=0.85, green_required=3

### Added

- **Pre-tuning gate check script** (`scripts/check-tuning-gate.sh`) - Reusable 5-point
  verification: CAKE qdiscs, no router CAKE, rate change visibility, transport, health

## [1.25.0] - 2026-04-02

**Reboot Resilience** - Ensures cake-shaper VM fully self-configures after reboot.
NIC tuning (ring buffers, GRO forwarding, IRQ affinity) applied automatically before
wanctl starts via idempotent shell script and systemd dependency ordering.
Phase 125: 2 plans, 4/4 requirements addressed (reboot test deferred to Phase 126).

### Added

- **NIC tuning shell script** (Phase 125-01) - Idempotent optimization of 4 bridge NICs
  - Ring buffers rx/tx 4096, rx-udp-gro-forwarding, IRQ affinity (Spectrum->CPU0, ATT->CPU1)
  - Journal logging via `logger -t wanctl-nic-tuning`, graceful missing-NIC handling
  - Always exits 0 (availability over strictness)
- **Ordered boot chain** (Phase 125-02) - Explicit systemd dependencies
  - `wanctl@.service` includes `After=` and `Wants=wanctl-nic-tuning.service`
  - Boot sequence: bridges -> NIC tuning -> wanctl (CAKE) -> recovery timer
- **deploy.sh NIC tuning support** (Phase 125-02) - Deploys script to `/usr/local/bin/`

### Changed

- `deploy/systemd/` established as canonical systemd unit location
- Old `systemd/` directory removed (was diverged/unhardened duplicate)
- `wanctl-nic-tuning.service` calls shell script instead of 10 inline ExecStart lines

### Tuned (RRUL A/B Validated)

14 back-to-back 5-minute RRUL soaks on Spectrum cable link (2026-04-02). Each parameter
tested independently, one variable at a time.

- `green_required`: 3 → **5** (DL and UL, tested independently) — p99 latency -40% (DL),
  UL throughput +14% (UL). Conservative recovery prevents premature ramp-up oscillation.
- `dwell_cycles`: 3 (default) → **5** — median latency -13%, UL throughput +19%. DOCSIS
  scheduling jitter needs 250ms filter, not 150ms.
- `factor_down` (RED): 0.85 → **0.90** — max latency -39%. Gentler RED decay avoids
  overshooting the floor during severe spikes.
- `factor_down_yellow`: **0.92** confirmed — 0.97 (cable guide default) doubled median
  latency with zero throughput gain.
- `step_up_mbps`: **15** confirmed — 10 tripled max latency. Faster ramp exploits brief
  TCP congestion avoidance dips.
- `deadband_ms`: **3.0** confirmed — 5.0 trapped system in YELLOW 43% vs 29%, worsening
  latency. Dwell_cycles=5 already handles jitter filtering.
- `target_bloat_ms`: 12 → **9** — p99 latency -33% (174 → 116ms). Tighter detection is
  safe with dwell_cycles=5 filtering DOCSIS jitter. CRITICAL: coupled with dwell_cycles.
- `warn_bloat_ms`: **45** confirmed — 30 too aggressive (21% SOFT_RED), 60 allows queue
  buildup (2.4s max latency).
- `hard_red_bloat_ms`: 80 → **60** — faster SOFT_RED floor clamp. RED state never fires
  with current tuning (YELLOW decay handles everything).
- `fusion.enabled`: set to **false** in YAML — was accidentally re-enabling on SIGUSR1
  reload with Pearson correlation at 0.61 (unsafe).

Net result (23 RRUL soaks, all parameters tested): every tunable A/B validated for this
Spectrum DOCSIS cable link. See `docs/CABLE_TUNING.md` for full data tables.

## [1.24.0] - 2026-03-31

**EWMA Boundary Hysteresis** - Eliminates GREEN/YELLOW flapping at the EWMA threshold boundary
during prime-time DOCSIS load. Dwell timer + deadband margin on both download and upload state
machines, YAML-configurable with SIGUSR1 hot-reload, health endpoint observability.
4 phases (121-124), 5 plans, 11/11 requirements satisfied. ~3,940+ tests.

### Added

- **Dwell timer on state transitions** (Phase 121) - Require N consecutive above-threshold cycles
  before GREEN->YELLOW transition, preventing single-cycle EWMA jitter from triggering rate clamping
  - `dwell_cycles` parameter (default 3, range 0-20) in `continuous_monitoring.thresholds`
  - Counter resets to zero when delta drops below threshold, ensuring only sustained congestion triggers
  - Applied to both download (4-state) and upload (3-state) machines identically
- **Deadband margin on recovery transitions** (Phase 121) - YELLOW->GREEN requires delta dropping below
  (target_bloat_ms - deadband_ms), preventing oscillation at the exact threshold boundary
  - `deadband_ms` parameter (default 3.0, range 0.0-20.0) in `continuous_monitoring.thresholds`
  - Split threshold: higher to enter YELLOW, lower to exit back to GREEN
- **Hysteresis configuration** (Phase 122) - YAML config with sensible defaults and SIGUSR1 hot-reload
  - Parameters under `continuous_monitoring.thresholds`: `dwell_cycles`, `deadband_ms`
  - SIGUSR1 reloads hysteresis params alongside existing dry_run/fusion/wan_state chain
  - Defaults work without config changes; `dwell_cycles: 0` disables hysteresis (escape hatch)
- **Hysteresis observability** (Phase 123) - Health endpoint exposure and suppression logging
  - Health endpoint `/health` includes `hysteresis` sub-dict per direction: `dwell_counter`,
    `dwell_cycles`, `deadband_ms`, `transitions_suppressed` count
  - DEBUG log on each suppressed cycle: `[HYSTERESIS] DL transition suppressed, dwell N/M`
  - INFO log on confirmed transitions: `[HYSTERESIS] DL dwell expired, GREEN->YELLOW confirmed`

### Fixed

- **Spike detector confirmation counter** - Require `accel_confirm_cycles` (default 3) consecutive
  spike cycles before forcing RED state, eliminating false positives from DOCSIS cable jitter
  - Root cause: `accel_threshold_ms: 12` triggered on single-sample RTT jitter (9,225 false
    positives/hr during idle on Spectrum cable at prime-time). Real congestion produces zero
    spike triggers — it builds gradually through the EWMA.
  - Fix: `_spike_streak` counter tracks consecutive spike cycles. Only forces RED after 3
    consecutive cycles (150ms at 50ms/cycle). Single-sample jitter resets counter to zero.
  - New config param `accel_confirm_cycles` (int, default 3, range 1-10) in
    `continuous_monitoring.thresholds`. No YAML changes needed — default takes effect.
  - Production validation (44h, 3 prime-time windows, 2026-03-28/30):
    36 flapping alert pairs / 54h → 3 pairs / 44h (92% reduction).
- **deploy.sh config validation** - Config check and validate-deployment.sh now use `sudo` to
  read `/etc/wanctl/*.yaml`, fixing false "config not found" warnings during deployment

### Analysis Record (2026-03-30, autotuner convergence)

- **Autotuner status:** Converged. 14 total changes (12 active, 2 reverted), zero safety reverts.
  No changes in 38 hours across 3 prime-time windows + RRUL stress test.
- **Spectrum diurnal RTT profile (2026-03-28/29, 3-day observation):**
  Night: p50=22.3 p95=25.5 p99=32.6 | jitter p50=1.8 p95=2.6
  Afternoon: p50=23.1 p95=33.5 p99=47.7 | jitter p50=2.7 p95=6.9
  Prime-time: p50=23.7 p95=42.7 p99=65.4 | jitter p50=4.5 p95=15.4 max=37.1
- **ATT profile (stable):** p50=28.3 p95=28.9 p99=29.7 | jitter p50=0.4 p95=0.6
- **Pre-hysteresis flapping baseline:** 1-3 alert pairs per prime-time evening from EWMA boundary
  oscillation at baseline+12ms during peak DOCSIS load

## [1.23.0] - 2026-03-27

**Self-Optimizing Controller** - Completes the tuner's vision with response parameter tuning,
auto-fusion healing, pyroute2 netlink, and configurable metrics retention. 4 phases, 8 plans,
18/22 requirements satisfied (4 OBSV deferred to v1.24). ~3,800+ tests.

### Added

- **pyroute2 netlink backend** (Phase 117) - Kernel netlink for CAKE tc operations
  - `NetlinkCakeBackend` subclass with per-call subprocess fallback via `super()`
  - Singleton `IPRoute(groups=0)` connection with automatic reconnect on socket death
  - Per-tin CAKE stats via netlink TCA_STATS2 decoder (no subprocess tc -j)
  - Factory registration: `transport: "linux-cake-netlink"` config option
  - pyroute2 as optional dependency (`pip install wanctl[netlink]`)
- **Configurable metrics retention** (Phase 118) - Per-granularity retention thresholds
  - `storage.retention` YAML section: `raw_age_seconds`, `aggregate_1m_age_seconds`, `aggregate_5m_age_seconds`
  - Cross-section validation: rejects configs where 1m retention < tuner `lookback_hours * 3600`
  - `prometheus_compensated` mode: shortens 5m tier to 48h when Prometheus TSDB available
  - Backward-compatible `deprecate_param()` migration from `storage.retention_days`
  - SIGUSR1 reload for retention config changes without restart
- **Auto-fusion healing** (Phase 119) - Automatic fusion state management
  - `FusionHealer` standalone module: incremental rolling Pearson correlation (3.3us/cycle)
  - 3-state machine: ACTIVE → SUSPENDED → RECOVERING → ACTIVE
  - Asymmetric hysteresis: 60s suspend window, 300s recovery window
  - Operator SIGUSR1 override with configurable grace period (default 30 min)
  - Parameter locking: `fusion_icmp_weight` locked via `float('inf')` sentinel during SUSPENDED
  - Discord alerts on all state transitions via AlertEngine
  - Health endpoint: `fusion.heal_state`, `fusion.pearson_correlation`, `fusion.heal_grace_active`
- **Adaptive rate step tuning** (Phase 120) - Response parameter self-optimization
  - 3 response strategies: `tune_step_up`, `tune_factor_down`, `tune_green_required`
  - Episode detection from `wanctl_state` 1m time series (congestion/recovery pattern analysis)
  - 6 tuneable parameters: DL/UL variants of step_up_mbps, factor_down, green_required
  - 5th RESPONSE_LAYER in tuning rotation (5-hour full cycle)
  - Oscillation lockout: freezes all 6 response params for 2h + Discord alert
  - Disabled by default via `exclude_params` (RTUN-05 graduation pattern)

### Changed

- Tuning rotation expanded from 4-layer to 5-layer (signal → EWMA → threshold → advanced → response)
- `get_storage_config()` returns full retention dict instead of flat `retention_days`
- `cleanup_old_metrics()` now performs per-granularity deletion (separate age per tier)
- `run_startup_maintenance()` accepts `retention_config` dict for config-driven thresholds
- `downsample_metrics()` accepts optional `thresholds` parameter for config-driven age thresholds
- `_apply_tuning_to_controller()` extended for QueueController response parameters (Mbps→bps conversion)

### Deferred

- Phase 121: Prometheus/Grafana Export — infrastructure not yet deployed, moved to v1.24

## [1.20.0] - 2026-03-19

**Adaptive Tuning** - Self-optimizing controller that learns optimal parameters from production
metrics via percentile-based derivation with conservative safety bounds. 6 phases, 10 plans,
30/30 requirements satisfied, 3,723 tests.

### Added

- **Tuning framework** (Phase 98) - Pluggable tuning engine with safety bounds
  - `TuningConfig`, `TuningState`, `SafetyBounds` data models in `wanctl.tuning.models`
  - `TuningAnalyzer` orchestrates strategy functions with per-parameter bounds clamping
  - SQLite persistence of tuning decisions in `tuning_params` table
  - Health endpoint `tuning` section with state, last run, parameter locks
  - Ships disabled by default (`tuning.enabled: false`)
- **Congestion threshold calibration** (Phase 99) - Auto-derive thresholds from RTT distribution
  - `calibrate_target_bloat` from p25 of GREEN-state RTT deltas with margin
  - `calibrate_warn_bloat` from p75 of RTT deltas with margin
  - Requires 60+ minutes of GREEN-state data before proposing changes
- **Safety and revert detection** (Phase 100) - Automatic rollback on degradation
  - Congestion rate monitoring after parameter changes (observation period)
  - Auto-revert to previous values if congestion rate increases post-adjustment
  - Parameter locks with cooldown to prevent thrashing
- **Signal processing tuning** (Phase 101) - Optimize Hampel and EWMA parameters per-WAN
  - `tune_hampel_sigma` adjusts sigma toward 5-15% target outlier rate range
  - `tune_hampel_window` maps jitter level to window size via linear interpolation
  - `tune_alpha_load` outputs `load_time_constant_sec` (0.5-10s), applier converts to alpha
  - 3-layer → 4-layer round-robin: signal → EWMA → threshold → advanced
- **Advanced tuning** (Phase 102) - Cross-signal parameter adaptation
  - `tune_fusion_weight` adapts ICMP/IRTT fusion ratio from per-signal reliability scoring
  - `tune_reflector_min_score` adjusts deprioritization threshold from signal confidence proxy
  - `tune_baseline_bounds_min`/`max` auto-adjust from p5/p95 of baseline history
  - `wanctl-history --tuning` CLI displays tuning adjustment history with filtering

### Fixed

- **Fusion baseline deadlock** (Phase 103) - Phase 96 regression where fused RTT contaminated
  baseline EWMA updates, preventing baseline convergence when IRTT and ICMP measured different
  network paths (ATT: IRTT 43ms to Dallas vs ICMP 29ms to CDN)
  - Signal path split: fused RTT feeds `load_rtt` EWMA, ICMP-only `filtered_rtt` feeds baseline
  - Freeze gate delta changed from `load_rtt - baseline_rtt` to `icmp_rtt - baseline_rtt`
  - `_update_baseline_if_idle` parameter renamed `measured_rtt` → `icmp_rtt`
  - Existing `update_ewma()` method preserved for backward compatibility (~50 test call sites)

## [1.19.0] - 2026-03-18

**Signal Fusion** - Graduated observation-mode signals into active congestion control inputs
through weighted dual-signal fusion, reflector quality scoring, OWD asymmetric detection,
and IRTT loss alerting. 5 phases, 10 plans, 15/15 requirements satisfied, 3,458 tests.

### Added

- **Dual-signal fusion** (Phases 96-97) - Weighted ICMP + IRTT RTT combination for congestion control
  - `fusion.icmp_weight: 0.7` (default) blends 20Hz ICMP with 0.1Hz IRTT UDP measurements
  - Ships disabled by default (`fusion.enabled: false`) for safe production rollout
  - SIGUSR1 zero-downtime toggle: `kill -USR1` enables/disables fusion without daemon restart
  - First SIGUSR1 reload in autorate daemon (extends proven steering daemon pattern)
  - Health endpoint `fusion` section shows enabled state, weights, active source, and RTT values
  - Multi-gate fallback: IRTT unavailable/stale/invalid silently falls back to ICMP-only
- **Reflector quality scoring** (Phase 93) - Rolling quality scores for ping_host reflectors
  - Success-rate scoring with configurable `reflector_quality.min_score` threshold (default 0.8)
  - Low-scoring reflectors auto-deprioritized, periodic probe recovery (default 30s interval)
  - Graceful degradation: 3+ active = median, 2 = average, 1 = single, 0 = force best
  - Health endpoint `reflector_quality` section with per-host scores and status
- **OWD asymmetric detection** (Phase 94) - Upstream vs downstream congestion detection
  - Analyzes IRTT burst-internal `send_delay` vs `receive_delay` (no NTP dependency)
  - Direction attribute: "upstream", "downstream", "symmetric", or "unknown"
  - Persisted to SQLite for trend analysis with asymmetry ratio
- **IRTT loss alerts** (Phase 95) - Discord notifications for sustained packet loss
  - Separate `irtt_loss_upstream` and `irtt_loss_downstream` alert types
  - Default 5% threshold, 60s sustained duration, per-event cooldown
  - Recovery alert (`irtt_loss_recovered`) with direction and outage duration

### Changed

- **WAN-aware steering graduated to production** (Phase 72)
  - `wan_state.enabled: true` on cake-spectrum (WAN zone signal active in confidence scoring)
  - SIGUSR1 hot-reload extended to toggle `wan_state.enabled` without restart
  - Grace period re-triggers on re-enable (30s safe ramp-up)
  - Degradation validated: stale zone falls back to GREEN, missing state file skips WAN weight
  - Operational runbook added to `docs/STEERING.md`
- **Confidence-based steering graduated from dry-run to live mode** (Phase 71)
  - `configs/steering.yaml` now ships with `dry_run: false` (confidence scoring drives routing decisions)
  - Multi-signal confidence scoring (0-100 scale) replaces binary RED-triggers-steer model
  - SIGUSR1 hot-reload enables toggling dry_run without daemon restart
  - Rollback procedure documented in `docs/STEERING.md` (edit YAML + `kill -USR1`)
  - WAN-aware steering remains at its current enabled state (`wan_state.enabled: true`)
- **Tuned `accel_threshold_ms`** - Reduced from 15ms to 12ms for faster spike detection
  - A/B testing showed 19% reduction in average RTT under load (48ms → 39ms)
  - 11% reduction in peak latency spikes (83ms → 74ms avg peak)
  - 50% reduction in 100ms+ spike frequency (40% → 20% of test runs)
  - Lower values (10ms) caused over-correction; higher values (15ms) missed spikes
- **Legacy config parameter deprecation (Phase 69)** - 8 deprecated params warn and auto-translate on load
  - `alpha_baseline` / `alpha_load` -> `baseline_time_constant_sec` / `load_time_constant_sec` (auto-translated)
  - `cake_state_sources.spectrum` -> `cake_state_sources.primary` (identity rename)
  - `cake_queues.spectrum_download` / `spectrum_upload` -> `primary_download` / `primary_upload`
  - `mode.cake_aware` retired (CAKE three-state model always active, logs warning and ignores)
  - `bad_samples` / `good_samples` removed from `validate_sample_counts()` API
  - Calibration tool now generates `baseline_time_constant_sec` and `load_time_constant_sec` in output configs
  - `deprecate_param()` helper added for consistent warn+translate pattern across config loaders

### Documentation

- Updated `cable.yaml.example` with modern EWMA time constants and `accel_threshold_ms`
- Updated `CONFIG_SCHEMA.md` with modern parameter names and deprecated parameters table

## [1.1.0] - 2026-01-14

**First stable release** - Adaptive CAKE bandwidth control for MikroTik RouterOS.

This release represents 18+ days of production validation with 231,000+ autorate cycles
and 604,000+ steering assessments. Comprehensive test coverage (594 tests), enterprise-grade
observability, and validated 50ms cycle interval for sub-second congestion response.

### Highlights

- **50ms Cycle Interval** - 40x faster than original 2s baseline, sub-second congestion detection
- **594 Unit Tests** - Comprehensive test coverage, all passing
- **Flash Wear Protection** - 99.7% reduction in router writes
- **Fallback Connectivity** - Graceful degradation reduces false-positive restarts
- **REST API Transport** - 2x faster than SSH (~50ms vs ~150ms latency)
- **Production Validated** - Stability score 9.0/10 from comprehensive analysis

### Performance

| Metric               | Value                  |
| -------------------- | ---------------------- |
| Cycle Interval       | 50ms (20Hz polling)    |
| Congestion Detection | 50-100ms response time |
| Router CPU (idle)    | 0%                     |
| Router CPU (load)    | 45% peak               |
| Flash Wear Reduction | 99.7%                  |

### Features

#### Adaptive Bandwidth Control

- **Continuous RTT Monitoring** - 50ms control loop measures latency and adjusts bandwidth in real-time
- **4-State Download Model** - GREEN/YELLOW/SOFT_RED/RED state machine with per-state floor enforcement
- **3-State Upload Model** - GREEN/YELLOW/RED (upload is less latency-sensitive)
- **EWMA Smoothing** - Exponential weighted moving average for stable RTT and rate tracking
- **Baseline RTT Protection** - Baseline only updates when connection is idle (delta < 3ms)
- **Asymmetric Rate Changes** - Fast backoff on congestion, slow recovery (requires 5 consecutive GREEN cycles)
- **Flash Wear Protection** - Only writes queue changes to router when values actually change

#### State Machine Behavior

| State    | RTT Delta | Action                                             | Floor Example |
| -------- | --------- | -------------------------------------------------- | ------------- |
| GREEN    | ≤15ms     | Slowly increase rate (+1 Mbps/cycle after 5 GREEN) | 550 Mbps      |
| YELLOW   | 15-45ms   | Hold steady, monitor                               | 350 Mbps      |
| SOFT_RED | 45-80ms   | Clamp to floor, no steering                        | 275 Mbps      |
| RED      | >80ms     | Aggressive backoff, steering eligible              | 200 Mbps      |

#### Multi-WAN Traffic Steering

- **Multi-Signal Detection** - RTT delta + CAKE drops + queue depth (not RTT alone)
- **Asymmetric Hysteresis** - 2 RED samples to enable steering, 15 GREEN to disable
- **Latency-Sensitive Routing** - Steers VoIP, DNS, gaming, SSH to healthier WAN
- **New Connections Only** - Existing flows never rerouted mid-session

#### Router Transports

- **REST API (Recommended)** - ~50ms latency, 2x faster than SSH
- **SSH Transport** - Paramiko-based with persistent connections

#### Observability

- **Health Check Endpoint** - `http://127.0.0.1:9101/health` with JSON response
- **Prometheus Metrics** - Optional metrics on port 9100
- **Structured Logging** - JSON format via `WANCTL_LOG_FORMAT=json`

#### Safety & Reliability

- **Rate Limiting** - Max 10 router changes per 60 seconds
- **Lock File Management** - PID-based validation with stale lock cleanup
- **Watchdog Integration** - Systemd watchdog with degradation tracking
- **State File Recovery** - Automatic backup and corruption recovery
- **Fallback Connectivity** - TCP/gateway checks when ICMP fails

### CLI Tools

```bash
# Main controller
wanctl --config /etc/wanctl/wan1.yaml

# Calibration wizard
wanctl-calibrate --wan-name NAME --router HOST

# Traffic steering
wanctl-steering --config /etc/wanctl/steering.yaml
```

### Deployment

```
/opt/wanctl/           # Application code
/etc/wanctl/           # Configuration files
/var/lib/wanctl/       # State files
/var/log/wanctl/       # Logs
/run/wanctl/           # Lock files
```

### System Requirements

- Python 3.11+ (3.12 recommended)
- MikroTik RouterOS 7.x with CAKE queues
- Linux host with systemd (Debian 12, Ubuntu 22.04+)

### Dependencies

- `requests>=2.31.0` - REST API transport
- `pyyaml>=6.0.1` - Configuration parsing
- `paramiko>=3.4.0` - SSH transport
- `pexpect>=4.9.0` - SSH command execution

---

## Pre-Release History

### Development Milestones

- **v1.0.0-rc8** (2026-01-12) - Fallback connectivity checks
- **v1.0.0-rc7** (2026-01-10) - Health endpoints, rate limiting, 474 tests
- **v1.0.0-rc5** (2026-01-08) - Interactive setup wizard
- **v1.0.0-rc4** (2026-01-08) - REST API transport (2x faster)
- **v1.0.0-rc3** (2026-01-07) - Open source release, package rename

### Earlier Development (Pre-Open Source)

- **v4.x** (Dec 2025) - CAKE-aware steering, 4-state model
- **v3.x** (Nov 2025) - Binary search calibration
- **v2.x** (Nov 2025) - Config-driven, EWMA smoothing
- **v1.x** (Oct 2025) - Initial implementation

---

## Acknowledgments

### Dave Taht (1965-2025) - In Memoriam

This project stands on the shoulders of **Dave Taht**, pioneer of the bufferbloat movement
and lead developer of CAKE. His work benefits millions of internet users.

### Projects

- [CAKE](https://www.bufferbloat.net/projects/codel/wiki/Cake/) - The qdisc that makes this work
- [LibreQoS](https://libreqos.io/) - Inspiration for CAKE-based QoS
- [Flent](https://flent.org/) - Latency measurement methodology
- [sqm-autorate](https://github.com/sqm-autorate/sqm-autorate) - OpenWrt automatic SQM tuning

### AI Transparency

This project was developed with assistance from **Claude** (Anthropic).
The architecture, algorithms, and documentation were created collaboratively
between a human sysadmin and AI.

---

## License

GPL-2.0 - See [LICENSE](LICENSE) for details.

[1.1.0]: https://github.com/kevinb361/wanctl/releases/tag/v1.1.0
