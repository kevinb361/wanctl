# Feature Landscape: v1.18 Measurement Quality

**Domain:** RTT measurement quality improvements for dual-WAN adaptive CAKE controller
**Researched:** 2026-03-16

## Table Stakes

Features expected from a measurement quality improvement milestone. Missing = effort feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Outlier filtering on raw RTT samples | Single spike should not trigger false congestion detection | Low | Hampel filter with rolling MAD, ~20 lines pure Python, stdlib only |
| Jitter tracking (EWMA) | Jitter is a leading indicator of congestion; currently ignored entirely | Low | RFC 3550 EWMA (gain 1/16), 15 lines, no deps |
| Measurement confidence indicator | Operator needs to know if readings are trustworthy | Low | Rolling CI from stdlib statistics module |
| IRTT subprocess wrapper | Core delivery -- supplemental UDP RTT source | Medium | subprocess + json.loads pattern (same as flent in v1.17) |
| IRTT results in health endpoint | Operators expect visibility into measurement diversity | Low | Extend existing /health JSON response |
| YAML config for all new features | Must be opt-in, backward-compatible | Low | Existing config pattern, ships disabled by default |
| Feature disabled by default | Production system -- no behavioral change on upgrade | Low | Established pattern (wan_state, alerting, confidence) |
| Signal quality metrics in SQLite | Track measurement quality trends over time | Low | Existing metrics_storage.py pattern, new type values |
| IRTT fallback to icmplib-only | IRTT server down must not break existing measurement | Low | icmplib stays primary; IRTT is supplemental |

## Differentiators

Features that significantly improve measurement quality beyond expectations.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Upstream vs downstream loss direction | Know WHERE packets are lost (ISP ingress vs egress) -- currently impossible | Low | IRTT provides natively in JSON: `true_up`, `true_down` |
| ICMP vs UDP RTT correlation | Detect ISP ICMP deprioritization (RTT delta between protocols) | Low | Compare icmplib and IRTT median RTTs per measurement cycle |
| IRTT IPDV (per-packet jitter) | Richer jitter signal than manual delta calculation from sequential ICMP pings | Low | IRTT JSON `round_trips[].ipdv.rtt` field, already computed |
| Container networking latency characterization | Quantify veth/bridge overhead -- establish measurement floor | Medium | One-time audit tooling, uses existing icmplib + new IRTT |
| IRTT loss direction in alerting | Alert when upstream/downstream loss exceeds threshold | Low | Integrate with existing AlertEngine from v1.15 |
| One-way delay tracking (relative) | Detect asymmetric congestion (upload saturated but download fine) | Medium | IRTT provides OWD; useful for relative change even without NTP sync |
| RTT variance EWMA | Track measurement stability -- high variance = unreliable path | Low | Parallel EWMA alongside existing load_rtt EWMA |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Replace icmplib with IRTT in hot loop | IRTT subprocess has 5-10ms startup overhead; incompatible with 50ms cycle | Keep icmplib for 20Hz hot loop, IRTT as periodic supplemental (every 5-10s) |
| Machine learning anomaly detection | Massive deps, unpredictable behavior, untestable edge cases | Deterministic: Hampel filter, z-score, RFC 3550 jitter |
| numpy/scipy/pandas for signal processing | 30MB+ deps for 3 trivial functions (median, stdev, MAD) | stdlib statistics + collections.deque |
| Per-cycle IRTT measurement | 5-10ms subprocess overhead consumes 10-20% of cycle budget | Periodic burst every 5-10 seconds in background thread |
| Automatic macvlan migration | Container networking changes are high-risk for production | Audit first, recommend manually, operator decides |
| IRTT server management from wanctl | wanctl should not manage remote server processes | Assume server is running (it is -- Dallas 104.200.21.31) |
| Custom UDP measurement protocol | IRTT handles clock sync, HMAC, IPDV, loss direction | Use IRTT binary |
| NTP-synchronized OWD as authoritative | Clock sync in LXC containers is unreliable; OWD errors compound | Use OWD for relative change detection only, RTT remains authoritative |
| Continuous IRTT background stream | Wastes bandwidth, adds constant UDP traffic | Short burst measurements (5 packets per burst) every 5-10s |
| SmokePing integration | External tool with own data pipeline; wanctl is self-contained | Use IRTT directly |
| Dual-signal fusion for congestion control | High complexity, needs extensive validation before production | Start with observation: report IRTT alongside icmplib, defer fusion to v1.19+ |

## Feature Dependencies

```
Signal Processing Core (no external deps):
    HampelFilter --> RTTMeasurement.measure_rtt() (filter before EWMA update)
    JitterTracker --> RTTMeasurement.measure_rtt() (update after each measurement)
    RTTConfidence --> HampelFilter + JitterTracker (width reflects both)
    VarianceEWMA --> RTTMeasurement.measure_rtt() (parallel to load_rtt EWMA)

IRTT Integration (requires irtt binary):
    irtt binary available --> apt install irtt on containers
    IRTT server running --> Dallas 104.200.21.31:2112 (already done)
    IRTTMeasurement class --> irtt binary + server
    Background thread --> IRTTMeasurement
    IRTT alerting --> IRTTMeasurement + AlertEngine (v1.15)

Container Networking Audit (independent):
    Latency measurement --> icmplib (existing) + IRTT (new)
    No dependency on signal processing features

Observability (depends on above):
    Health endpoint signal_quality --> All signal processing classes + IRTT results
    SQLite metrics --> Same data as health endpoint
    Alerting extensions --> IRTT loss direction data
```

## MVP Recommendation

Prioritize:
1. **Signal processing core** (Hampel, jitter, CI, variance) -- Low complexity, immediate value in every cycle, testable in isolation, zero deps
2. **IRTT integration** -- Medium complexity, provides UDP diversity and loss direction
3. **Health/metrics/alerting extensions** -- Low complexity, leverages established patterns
4. **Container networking audit** -- Independent measurement task, informational only

Defer:
- **Dual-signal fusion**: Start with observation (report both), defer weighted combination to next milestone
- **OWD-based asymmetric congestion**: Useful but requires NTP validation on IRTT server
- **Per-reflector quality scoring**: Interesting but adds complexity to ping_hosts handling

## Sources

- Existing wanctl codebase: rtt_measurement.py, baseline_rtt_manager.py, autorate_continuous.py
- [RFC 3550](https://www.ietf.org/rfc/rfc3550.txt) -- jitter calculation standard
- [IRTT man pages](https://manpages.debian.org/testing/irtt/irtt-client.1.en.html) -- capability documentation
- [Hampel filter](https://towardsdatascience.com/outlier-detection-with-hampel-filter-85ddf523c73d/) -- algorithm reference
- [Container networking performance](https://dl.acm.org/doi/pdf/10.1145/3094405.3094406) -- veth/macvlan comparison
- v1.1 ICMP blackout incident -- motivates UDP measurement diversity

---
*Feature landscape for: wanctl v1.18 Measurement Quality*
*Researched: 2026-03-16*
