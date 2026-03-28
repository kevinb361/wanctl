# Changelog

All notable changes to wanctl are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **Spike detector confirmation counter** - Require `accel_confirm_cycles` (default 3) consecutive
  spike cycles before forcing RED state, eliminating false positives from DOCSIS cable jitter
  - Root cause: `accel_threshold_ms: 12` triggered on single-sample RTT jitter (9,225 false
    positives/hr during idle on Spectrum cable at prime-time). Real congestion produces zero
    spike triggers — it builds gradually through the EWMA.
  - DOCSIS cable jitter profile (idle, DL=940M): p90=21ms, p95=28ms, p99=44ms cycle-to-cycle
    delta at 50ms resolution. No single threshold eliminates false positives without also
    missing genuine events.
  - Fix: `_spike_streak` counter tracks consecutive spike cycles. Only forces RED after 3
    consecutive cycles (150ms at 50ms/cycle). Single-sample jitter resets counter to zero.
  - New config param `accel_confirm_cycles` (int, default 3, range 1-10) in
    `continuous_monitoring.thresholds`. No YAML changes needed — default takes effect.
  - Production impact: 36 flapping alert pairs in 54 hours → expected zero from jitter.
    Awaiting prime-time validation (DOCSIS node load peaks ~9 PM).

### Analysis Record (2026-03-28)

- **Autotuner status (60h in):** 6 parameter changes across both WANs, zero reverts. Signal
  and advanced layers active; EWMA, threshold, and response layers have not produced changes.
  Response layer needs congestion episodes to analyze (none at 3 AM).
- **Pegged parameters — no action needed:**
  - `hampel_window_size` at max (15/21): Off by 1 sample on Spectrum (750ms vs 800ms window),
    diminishing returns on ATT. Bounds set from Phase 101 jitter-based analysis.
  - `baseline_rtt_max` at min (25.1): Security bound rejecting corrupted baselines, not a
    tuning constraint. Baseline EWMA (tc=50s) rarely exceeds 24ms even at prime-time.
  - `load_time_constant_sec` (0.10) below tuner bounds [0.5, 10]: Intentional expert override
    for cable's fast RTT dynamics. Tuner has not attempted to change it in 60 hours.
- **Spectrum RTT profile (2h nighttime sample, 82K cycles):**
  p5=19.4 p50=22.4 p95=27.1 p99=37.5ms | jitter p50=2.2 p95=4.6ms | baseline=21.8ms
- **ATT RTT profile (2h nighttime sample, 75K cycles):**
  p5=27.8 p50=28.3 p95=28.9 p99=29.6ms | jitter p50=0.4 p95=0.6ms | baseline=28.3ms

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
