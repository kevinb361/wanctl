# Requirements: wanctl v1.18 Measurement Quality

**Defined:** 2026-03-16
**Core Value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.

## v1.18 Requirements

Requirements for measurement quality milestone. Each maps to roadmap phases.

### Signal Processing

- [ ] **SIGP-01**: Outlier RTT samples are identified and replaced using rolling Hampel filter before EWMA update
- [ ] **SIGP-02**: Jitter is tracked per cycle using RFC 3550 EWMA calculation from consecutive RTT measurements
- [ ] **SIGP-03**: Measurement confidence interval is computed per cycle indicating RTT reading reliability
- [ ] **SIGP-04**: RTT variance is tracked via EWMA alongside existing load_rtt smoothing
- [ ] **SIGP-05**: Signal processing uses only Python stdlib (zero new package dependencies)
- [ ] **SIGP-06**: Signal processing operates in observation mode — metrics and logs only, no congestion control input changes

### IRTT

- [ ] **IRTT-01**: IRTT client subprocess is wrapped with JSON output parsing for RTT, loss, and IPDV
- [ ] **IRTT-02**: IRTT measurements run in background daemon thread on configurable cadence (default 10s)
- [ ] **IRTT-03**: Main control loop reads latest cached IRTT result each cycle with zero blocking
- [ ] **IRTT-04**: IRTT configuration via YAML section (server, port, cadence, enabled) disabled by default
- [ ] **IRTT-05**: IRTT unavailability (server down, binary missing) has zero impact on controller behavior
- [ ] **IRTT-06**: Upstream vs downstream packet loss direction is tracked per IRTT measurement burst
- [ ] **IRTT-07**: ICMP vs UDP RTT correlation detects protocol-specific deprioritization
- [ ] **IRTT-08**: IRTT binary installed on production containers via apt

### Container Networking

- [ ] **CNTR-01**: Container veth/bridge networking overhead is measured and quantified
- [ ] **CNTR-02**: Jitter contribution from container networking is characterized
- [ ] **CNTR-03**: Audit report documents measurement floor with quantified overhead

### Observability

- [ ] **OBSV-01**: Health endpoint exposes signal quality section (jitter, confidence, variance, outlier count)
- [ ] **OBSV-02**: Health endpoint exposes IRTT measurement section (RTT, loss direction, IPDV, server status)
- [ ] **OBSV-03**: Signal quality metrics are persisted in SQLite for trend analysis
- [ ] **OBSV-04**: IRTT metrics are persisted in SQLite for trend analysis

## Future Requirements

Deferred to v1.19+. Tracked but not in current roadmap.

### Signal Fusion

- **FUSE-01**: Dual-signal fusion — weighted combination of IRTT + icmplib for congestion control input
- **FUSE-02**: OWD-based asymmetric congestion detection (requires NTP validation on IRTT server)
- **FUSE-03**: Per-reflector quality scoring for ping_hosts selection

### Alerting Extensions

- **ALRT-01**: IRTT loss direction integrated into AlertEngine for upstream/downstream loss alerts

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Replace icmplib with IRTT in hot loop | 5-10ms subprocess overhead incompatible with 50ms cycle budget |
| ML anomaly detection | Massive deps, unpredictable behavior, untestable edge cases |
| numpy/scipy/pandas for signal processing | 30MB+ deps for trivial functions — stdlib sufficient |
| Automatic macvlan migration | High-risk production change — audit first, recommend manually |
| IRTT server management from wanctl | Separate concern — assume server running |
| NTP-synchronized OWD as authoritative | Clock sync unreliable in LXC containers |
| SmokePing integration | External tool — wanctl is self-contained |
| Dual-signal fusion for congestion control | Needs production data from both signals — deferred to v1.19+ |
| Continuous IRTT background stream | Wastes bandwidth — short burst measurements every 5-10s |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SIGP-01 | — | Pending |
| SIGP-02 | — | Pending |
| SIGP-03 | — | Pending |
| SIGP-04 | — | Pending |
| SIGP-05 | — | Pending |
| SIGP-06 | — | Pending |
| IRTT-01 | — | Pending |
| IRTT-02 | — | Pending |
| IRTT-03 | — | Pending |
| IRTT-04 | — | Pending |
| IRTT-05 | — | Pending |
| IRTT-06 | — | Pending |
| IRTT-07 | — | Pending |
| IRTT-08 | — | Pending |
| CNTR-01 | — | Pending |
| CNTR-02 | — | Pending |
| CNTR-03 | — | Pending |
| OBSV-01 | — | Pending |
| OBSV-02 | — | Pending |
| OBSV-03 | — | Pending |
| OBSV-04 | — | Pending |

**Coverage:**
- v1.18 requirements: 21 total
- Mapped to phases: 0
- Unmapped: 21

---
*Requirements defined: 2026-03-16*
*Last updated: 2026-03-16 after initial definition*
