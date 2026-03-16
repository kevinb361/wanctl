# Research Summary: v1.18 Measurement Quality

**Domain:** IRTT integration, container networking audit, RTT signal processing
**Researched:** 2026-03-16
**Overall confidence:** HIGH

## Executive Summary

v1.18 improves RTT measurement quality through three capabilities: (1) IRTT as a supplemental UDP RTT source alongside existing icmplib ICMP probes, (2) container networking latency characterization to quantify veth/bridge overhead, and (3) signal processing improvements including outlier filtering (Hampel), jitter tracking (RFC 3550 EWMA), and measurement confidence intervals.

The critical architectural constraint is the 50ms cycle budget. IRTT cannot run inside the hot loop (subprocess overhead is 5-10ms startup + 250ms measurement). Instead, IRTT runs in a background daemon thread on a 5-10 second cadence, and the main loop reads the latest cached result each cycle with zero blocking. The icmplib ICMP measurement remains the authoritative control signal at 20Hz; IRTT is strictly supplemental -- its absence must have zero impact on the controller's behavior.

All signal processing (Hampel filter, RFC 3550 jitter, confidence intervals) is implementable with Python stdlib (`statistics.median`, `collections.deque`, `math.sqrt`). Zero new Python package dependencies. One new system binary: `irtt` (available in Ubuntu 24.04 repos as `apt install irtt`, version 0.9.0). The IRTT server on Dallas (104.200.21.31:2112) is already running.

The container networking audit will likely confirm that veth/bridge overhead is negligible (10-50 microseconds, 0.03-0.15% of 30ms+ WAN RTT). The audit produces documentation, not necessarily an optimization. If overhead is <0.5ms, the phase closes with a report.

## Key Findings

**Stack:** Zero new Python deps. One system binary (irtt via apt). All signal processing with stdlib.
**Architecture:** IRTT in background thread (never in hot loop). Signal processing is pure-function classes. icmplib stays authoritative.
**Critical pitfall:** IRTT subprocess in hot loop would blow cycle budget. Hampel filter with aggressive thresholds masks real congestion.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **Signal Processing Core** - Build HampelFilter, JitterTracker, RTTConfidence, VarianceEWMA
   - Addresses: Outlier filtering, jitter tracking, confidence intervals (table stakes)
   - Avoids: Pitfall 6 (filter degrades detection) by shipping in observation mode first
   - Rationale: Pure Python, zero deps, testable in isolation, immediate value every cycle

2. **IRTT Foundation** - IRTTMeasurement wrapper, JSON parsing, config, container install
   - Addresses: UDP measurement diversity, loss direction (differentiator)
   - Avoids: Pitfall 1 (hot loop blocking) by establishing background thread from the start
   - Rationale: Binary must be installed and validated before daemon integration

3. **IRTT Daemon Integration** - Background thread wired into autorate daemon, health endpoint, metrics
   - Addresses: IRTT data in production, observability (table stakes)
   - Avoids: Pitfall 3 (signal fusion oscillation) by keeping IRTT as observation-only (no congestion input)
   - Rationale: Depends on Phase 2 wrapper. Ships disabled by default.

4. **Container Networking Audit** - Measure veth/bridge overhead and jitter contribution
   - Addresses: Measurement floor characterization (differentiator)
   - Avoids: Pitfall 8 (over-engineering negligible overhead) by defining exit criteria upfront
   - Rationale: Independent of other phases, informational output, can run in parallel

**Phase ordering rationale:**
- Signal processing first: pure Python, zero external dependencies, immediately testable. Provides the observation infrastructure that IRTT integration will use.
- IRTT foundation before integration: binary must be installed and wrapper validated before wiring into daemon.
- Container audit independent: measurement task with clear exit criteria, can run early or late.
- Dual-signal fusion DEFERRED to v1.19+: v1.18 establishes observation. Fusion requires production data from both signals to design correctly.

**Research flags for phases:**
- Phase 1 (Signal Processing): Well-understood algorithms, should NOT need additional research. Test with production RTT traces.
- Phase 2 (IRTT Foundation): May need one-time verification of IRTT JSON output format against live measurement (documented in STACK.md).
- Phase 3 (IRTT Integration): Background thread pattern established in v1.15 (WebhookDelivery). Standard.
- Phase 4 (Container Audit): May need targeted investigation of container networking config format (LXC-specific).

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Zero new Python deps confirmed. IRTT in Ubuntu repos verified via apt-cache. All signal processing algorithms are stdlib-only. |
| Features | HIGH | Table stakes derived from measurement science fundamentals. IRTT capabilities verified via official man pages. |
| Architecture | HIGH | Background thread pattern proven in v1.15 (WebhookDelivery). Signal processing as pure functions is a standard pattern. |
| Pitfalls | HIGH | IRTT cycle budget impact quantified from production profiling data. Hampel filter sensitivity documented in signal processing literature. |

## Gaps to Address

- **IRTT JSON field names:** Documented from man pages but should be verified with one live measurement during Phase 2
- **Container networking configuration details:** LXC-specific veth/bridge config format for cake-spectrum and cake-att containers
- **Optimal Hampel parameters per WAN:** Default sigma=3.0/window=7 is conservative; may need per-WAN tuning from production data
- **IRTT server reliability:** Single server (Dallas) with no SLA. Multi-server support deferred; monitor reliability
- **Dual-signal fusion algorithm:** Deferred to v1.19+. v1.18 collects data; fusion design requires production dual-signal experience

## Sources

### Primary (HIGH confidence)
- [IRTT GitHub Repository](https://github.com/heistp/irtt) -- v0.9.1, Go binary, JSON output, HMAC
- [IRTT Client Man Page](https://manpages.debian.org/testing/irtt/irtt-client.1.en.html) -- CLI flags, JSON schema
- [RFC 3550](https://www.ietf.org/rfc/rfc3550.txt) -- jitter EWMA calculation (gain 1/16)
- Ubuntu apt-cache -- irtt 0.9.0-2ubuntu0.24.04.3 confirmed available
- Existing wanctl codebase -- rtt_measurement.py, baseline_rtt_manager.py, autorate_continuous.py
- Python 3.12 stdlib -- statistics, collections.deque, math modules

### Secondary (MEDIUM confidence)
- [Hampel Filter](https://towardsdatascience.com/outlier-detection-with-hampel-filter-85ddf523c73d/) -- algorithm description
- [Container Networking Performance (ACM)](https://dl.acm.org/doi/pdf/10.1145/3094405.3094406) -- veth vs macvlan comparison
- [Container Latency Evaluation (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S0166531624000476) -- LXC optimization approaches
- [cake-autorate](https://github.com/lynxthecat/cake-autorate) -- IRTT + ICMP dual measurement patterns

---
*Research completed: 2026-03-16*
*Ready for roadmap: yes*
