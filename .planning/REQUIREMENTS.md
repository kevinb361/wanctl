# Requirements: wanctl Active Milestones

**Core Value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.

**Active Milestones (parallel):**
- **v1.40 Queue-Primary Signal Arbitration** — current active work (defined 2026-04-23)
- **v1.39 Control-Path Timing & Measurement Accounting** — in closure; Phase 191 ATT weather-rerun + Phase 192 execution remain

---

## v1.40 Requirements (defined 2026-04-23)

### Signal Arbitration (ARB)

- [ ] **ARB-01**: When `cake_signal` is supported and the latest `cake_snapshot` provides a valid `avg_delay_us` and `base_delay_us`, DL distress classification consumes `queue_delay_delta_us = max(0, avg_delay_us - base_delay_us)` as its primary input instead of RTT delta. When `cake_signal` is unsupported, DL classification falls back to the v1.39 RTT-primary path byte-identically.
- [ ] **ARB-02**: DL classification consumes RTT delta only through an `rtt_confidence` scalar in `[0.0, 1.0]` derived from ICMP/UDP agreement and direction agreement with the queue-delay signal. RTT cannot override a queue-GREEN reading unless `rtt_confidence >= 0.6` and queue and RTT agree in direction.
- [ ] **ARB-03**: Fusion healer bypass enters only when queue-delay distress (`queue_delay_delta_us` over its distress threshold) AND RTT distress (`rtt_confidence >= 0.6` with RTT zone at least YELLOW) are both sustained in the same worsening-or-held direction for 6 consecutive cycles. Single-path flips never enter bypass. Magnitude ratios between µs (queue) and ms (RTT) are never used as the alignment metric.
- [ ] **ARB-04**: v1.40 arbitration changes are DL-only. UL distress classification, UL state machine, and UL rate compute remain byte-identical to v1.39.

### Measurement Accounting (MEAS)

- [ ] **MEAS-07**: `queue_delay_delta_us` is computed from the CAKE-provided `base_delay_us` field. No Python-side learned idle baseline, no baseline-freeze state machine, no healthy-idle gate is introduced for the queue-delay path.

### Observability (OBS)

- [ ] **OBS-01**: `/health` per-WAN response contains a `signal_arbitration` block with fields `active_primary_signal` (one of `"queue"`, `"rtt"`, `"none"`), `rtt_confidence` (float 0.0–1.0 or null), `cake_av_delay_delta_us` (int or null), and `control_decision_reason` (short stable-vocabulary string such as `queue_distress`, `rtt_veto`, `healer_bypass`, `green_stable`). The existing `download.state`, `download.state_reason`, `download.hysteresis`, and `upload.*` fields remain byte-compatible with v1.39 consumers; new fields are additive under `signal_arbitration`, not nested under `hysteresis`.
- [ ] **OBS-02**: Per-cycle numeric metrics `wanctl_cake_avg_delay_delta_us`, `wanctl_rtt_confidence`, and `wanctl_arbitration_active_primary` (0=none, 1=queue, 2=rtt) are written to the per-WAN metrics SQLite store at each control cycle. No string labels; all values are numeric and compatible with the existing Prometheus-style exporter schema.

### Control Safety (SAFE)

- [ ] **SAFE-05**: No state-machine rule, EWMA alpha, dwell-cycle count, deadband value, burst detection parameter, or zone threshold is modified during v1.40. Arbitration changes the signal input to classification; classification rules and hysteresis logic remain untouched. Any PR touching state-machine code, EWMA alphas, or hysteresis constants is rejected.

### Verification (VALN)

- [ ] **VALN-04**: v1.40 Phase 196 soak runs sequentially on the same Spectrum deployment: 24h `rtt-blend` (v1.39 behavior, queue-primary disabled) followed by 24h `cake-primary` (v1.40 behavior, queue-primary enabled). No concurrent Spectrum soaks; v1.39 Phase 192 soak must complete before Phase 196 starts.
- [ ] **VALN-05**: Spectrum DL `flent tcp_12down` 30s throughput measured under `cake-primary` behavior recovers to within 90% of the 591 Mbps CAKE-only-static floor established in the 2026-04-23 measurement, verified at least once before Phase 196 shipping. ATT regression canary under `cake-primary` is run only after Phase 191 closure and requires ATT DL `tcp_12down` to not regress more than 5% vs last passing run.

### v1.40 Out of Scope

| Feature | Reason |
|---------|--------|
| UL queue-primary classification | UL is healthy in production; v1.40 scope is DL-only. UL remains RTT-led. |
| Python-learned idle baseline for queue delay | Kernel already provides `base_delay_us`; reusing it avoids a new baseline-freeze state machine that re-introduces the RTT path's fragility (MEAS-07). |
| `peak_delay_us` as primary signal | Too spike-prone for primary control scalar. Remains available as a secondary burst corroborator only. |
| Magnitude ratio between queue-delay µs and RTT ms for healer alignment | Fake precision across different domains. Alignment is categorical direction-over-N-cycles only. |
| Re-enabling fusion on Spectrum or ATT | Fusion workaround state stays as-is. Any re-enable is gated on v1.40 arbitration shipping + separate analysis. |
| Nesting new arbitration telemetry under `download.hysteresis` | Would break `/health` consumer back-compat. New fields live in a dedicated `signal_arbitration` block. |
| Concurrent Spectrum soaks | Attribution-destroying. v1.39 Phase 192 24h soak completes before v1.40 Phase 196 starts. |
| Changing any state-machine, threshold, EWMA, dwell, deadband, or burst-detection value | Locked per SAFE-05. v1.40 changes classification input, not classification rules. |

---

## v1.39 Requirements

### Control-Path Timing (TIME)

- [ ] **TIME-01**: Operators can observe, on the live health endpoint or in production logs, the concurrency overlap between `cake_stats_thread` tc-dump calls and `netlink_cake` tc-change apply calls, including per-call timestamps and elapsed time.
- [ ] **TIME-02**: The `cake_stats_thread` poll cadence is configurable via YAML at daemon start without requiring code changes, with a documented default that preserves current behavior until A/B evidence justifies a change.
- [ ] **TIME-03**: Cycle overrun count per hour, measured over a 24-hour window on both Spectrum and ATT, is strictly lower than the v1.38.0 baseline established in the 2026-04-20 production audit.
- [ ] **TIME-04**: `write_download_ms` and `write_upload_ms` p99 values logged in "Slow CAKE apply" warnings, measured over a 24-hour window, are strictly lower than the v1.38.0 baseline on both WANs.

### Measurement Accounting (MEAS)

- [ ] **MEAS-05**: When a background RTT cycle has zero successful reflectors (all-host blackout), the reflector scorer does not decrement per-host quality scores for any reflector in that cycle.
- [ ] **MEAS-06**: Reflector scores during prolonged carrier ICMP blackout episodes stop sinking to the 0.8 deprioritize threshold for path-wide failures, verified by health-endpoint reflector score trends on Spectrum over a 24-hour window.

### Operational Log Hygiene (OPER)

- [ ] **OPER-02**: "Protocol deprioritization detected" INFO log entries are rate-limited or demoted when fusion is in `disabled` or `healer_suspended` state, reducing Spectrum's 2.5k/day baseline volume while preserving the first occurrence and any state-transition events.

### Control Safety (SAFE)

- [x] **SAFE-03**: No control threshold, EWMA alpha, dwell-cycle count, deadband value, burst detection parameter, or state-machine rule is modified during v1.39. Any PR touching those files is rejected.
- [ ] **SAFE-04**: Immediate rate-decrease latency from congestion detection to `tc change` issuance is not increased by any timing change introduced in this milestone.

### Verification (VALN)

- [x] **VALN-02**: Each timing or scorer change is A/B-compared against the v1.38.0 baseline using at least one RRUL, one tcp_12down, and one VoIP flent run before shipping, with results captured in the phase VERIFICATION.md.
- [ ] **VALN-03**: A 24-hour production soak after merge confirms that TIME-03, TIME-04, and MEAS-06 hold, and that no regression appears in dwell-bypass responsiveness, burst detection trigger count, or fusion state transitions.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Changing any control threshold (state machine, EWMA, dwell, deadband, burst) | Locked per SAFE-03 — this milestone is timing and accounting, not algorithm tuning |
| Re-enabling fusion on Spectrum or ATT | Fusion stays suspended; any change requires separate analysis |
| Steering daemon work | Steering is disabled in production; cycle overruns there are non-operational |
| Asymmetry gate work | ATT asymmetry is stable and characteristic of the link |
| Adding a 4th reflector | Deferred — fix scorer accounting first; 4th reflector only reconsidered if MEAS-06 proves insufficient |
| Atomic DL+UL netlink write batching | High risk, unclear API support, would add latency to rate decreases |
| User-space RTNL lock around netlink calls | Would serialize reads and writes, can delay rate-decrease path |

## Traceability

### v1.39

| Requirement | Phase | Status |
|-------------|-------|--------|
| TIME-01 | Phase 191 | Pending |
| TIME-02 | Phase 191 | Pending |
| TIME-03 | Phase 191 (+ VALN-03 soak) | Pending |
| TIME-04 | Phase 191 (+ VALN-03 soak) | Pending |
| MEAS-05 | Phase 192 | Pending |
| MEAS-06 | Phase 192 (+ VALN-03 soak) | Pending |
| OPER-02 | Phase 192 | Pending |
| SAFE-03 | Phase 191 + Phase 192 (enforced throughout) | Complete |
| SAFE-04 | Phase 191 | Pending |
| VALN-02 | Phase 191 + Phase 192 | Complete |
| VALN-03 | Phase 192 closeout soak | Pending |

### v1.40

| Requirement | Phase | Status |
|-------------|-------|--------|
| ARB-01      | Phase 194 | Pending |
| ARB-02      | Phase 195 | Pending |
| ARB-03      | Phase 195 | Pending |
| ARB-04      | Phase 194 | Pending |
| MEAS-07     | Phase 193 | Pending |
| OBS-01      | Phase 193 | Pending |
| OBS-02      | Phase 193 | Pending |
| SAFE-05     | Phase 193 + Phase 194 + Phase 195 + Phase 196 (enforced throughout) | Pending |
| VALN-04     | Phase 196 | Pending |
| VALN-05     | Phase 196 | Pending |

---
*v1.39 requirements defined: 2026-04-20*
*v1.40 requirements defined: 2026-04-23*
*v1.40 traceability filled: 2026-04-23*
