# Requirements: wanctl v1.39 Control-Path Timing & Measurement Accounting

**Defined:** 2026-04-20
**Core Value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.

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

- [ ] **SAFE-03**: No control threshold, EWMA alpha, dwell-cycle count, deadband value, burst detection parameter, or state-machine rule is modified during v1.39. Any PR touching those files is rejected.
- [ ] **SAFE-04**: Immediate rate-decrease latency from congestion detection to `tc change` issuance is not increased by any timing change introduced in this milestone.

### Verification (VALN)

- [ ] **VALN-02**: Each timing or scorer change is A/B-compared against the v1.38.0 baseline using at least one RRUL, one tcp_12down, and one VoIP flent run before shipping, with results captured in the phase VERIFICATION.md.
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

| Requirement | Phase | Status |
|-------------|-------|--------|
| TIME-01 | Phase 191 | Pending |
| TIME-02 | Phase 191 | Pending |
| TIME-03 | Phase 191 (+ VALN-03 soak) | Pending |
| TIME-04 | Phase 191 (+ VALN-03 soak) | Pending |
| MEAS-05 | Phase 192 | Pending |
| MEAS-06 | Phase 192 (+ VALN-03 soak) | Pending |
| OPER-02 | Phase 192 | Pending |
| SAFE-03 | Phase 191 + Phase 192 (enforced throughout) | Pending |
| SAFE-04 | Phase 191 | Pending |
| VALN-02 | Phase 191 + Phase 192 | Pending |
| VALN-03 | Phase 192 closeout soak | Pending |

---
*Requirements defined: 2026-04-20*
