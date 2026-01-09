# Codebase Concerns

**Analysis Date:** 2026-01-09

## Tech Debt

**Netperf Integration Disabled:**
- Issue: Netperf server integration (`src/wanctl/config_base.py` references) disabled in favor of CAKE-aware bandwidth estimation
- Files: `src/wanctl/config_base.py`, `docs/SYNTHETIC_TRAFFIC_DISABLED.md`
- Why: Phase 2A validation (2025-12-28) showed CAKE metrics sufficient for bandwidth discovery
- Impact: Binary search bandwidth discovery not available; users must configure bandwidth manually
- Fix approach: Can be re-enabled for on-demand testing if needed; mark as optional feature

**Phase 2B Steering Partially Implemented:**
- Issue: Confidence-based steering logic exists but not fully integrated into main steering daemon
- Files: `src/wanctl/steering/steering_confidence.py` (confidence scoring), `src/wanctl/steering/daemon.py` (daemon uses hysteresis instead)
- Why: Phased implementation - Phase 2B improves on basic phase 2A logic
- Impact: Steering uses simpler hysteresis model instead of confidence thresholds
- Fix approach: Integrate ConfidenceSignals into SteeringDaemon state machine (medium effort)

**EWMA Smoothing Parameters Hardcoded:**
- Issue: EWMA smoothing factors scattered as constants instead of config
- Files: `src/wanctl/steering/daemon.py` (lines 72-74), `src/wanctl/autorate_continuous.py`
- Example: DEFAULT_RTT_EWMA_ALPHA = 0.3, DEFAULT_QUEUE_EWMA_ALPHA = 0.4
- Why: Simplified design - assumed stable parameters for typical ISPs
- Impact: Tuning requires code changes, not configuration
- Fix approach: Move to config schema with validation in config_validation_utils.py

## Known Bugs

**No Currently Identified Critical Bugs**

The codebase is actively maintained with recent fixes:
- W4 fix: Deques handle automatic eviction (steering/daemon.py line 840)
- W7 fix: Ping retry with fallback to last known RTT (steering/daemon.py line ~820)
- W8 fix: Track consecutive CAKE read failures for graceful degradation (steering/daemon.py line ~850)
- C2 fix: Queue name validation prevents command injection (steering/cake_stats.py line ~45)
- C4 fix: Baseline RTT bounds tightened to 10-60ms (steering/daemon.py line 80-84)

## Security Considerations

**Input Validation (Well-Implemented):**
- Risk: Command injection in RouterOS queries
- Current mitigation: Queue names validated via BaseConfig.validate_identifier (`steering/cake_stats.py` line 45)
- Recommendations: Maintain strict validation; audit new config parameters

**Configuration File Permissions:**
- Risk: Credentials in plaintext in `/etc/wanctl/wan.yaml` (username, password, SSH keys)
- Current mitigation: File permissions (600, root-owned assumed by deployer)
- Recommendations: Document secure setup in deployment guide; consider secrets management integration

**RouterOS API Authentication:**
- Risk: REST API password transmitted (over HTTPS, but still plaintext in memory)
- Current mitigation: REST API uses HTTPS (configured in router), SSH uses key-based auth (fallback)
- Recommendations: Prefer SSH; use SSH keys over password authentication

**EWMA Bounds Checking:**
- Risk: Invalid EWMA factors (outside 0-1) cause incorrect smoothing
- Current mitigation: Validation in config_validation_utils.py (validate_alpha function)
- Recommendations: Add unit tests for edge cases (0.0, 1.0)

## Performance Bottlenecks

**RouterOS SSH Latency:**
- Problem: SSH operations are slower than REST
- Measurement: ~150ms per SSH command vs ~50ms for REST
- Files: `src/wanctl/router_client.py` (factory pattern), `src/wanctl/routeros_ssh.py`
- Cause: SSH protocol overhead, authentication handshake per command
- Improvement path: Ensure REST API is preferred (`router_client.py` factory); keep SSH as fallback only

**Ping Measurement Overhead:**
- Problem: 3 pings per measurement cycle (default) add latency
- Measurement: ~100-150ms for 3 ICMP round-trips to remote reflectors
- Files: `src/wanctl/rtt_measurement.py` (ping execution)
- Cause: ICMP timeout for lost packets, multiple reflectors for aggregation
- Improvement path: Consider reducing to 1-2 pings, use faster aggregation strategy (median vs mean)

**CAKE Stats Read Frequency:**
- Problem: Reading CAKE stats from RouterOS every 2 seconds (steering cycle) adds overhead
- Measurement: ~50-100ms per read (via REST API)
- Files: `src/wanctl/steering/cake_stats.py` (CakeStatsReader.read_stats)
- Cause: Frequency of steering cycles
- Improvement path: Cache CAKE stats for 1-2 cycles if no state change needed

## Fragile Areas

**Router Client Factory:**
- Why fragile: REST vs SSH selection happens once at startup; can't switch transports mid-run
- Files: `src/wanctl/router_client.py` (factory function)
- Common failures: Network change (LAN to WAN), REST API becomes unavailable
- Safe modification: Add runtime transport health checks; allow fallback to SSH on REST failure
- Test coverage: Basic unit tests; no integration tests for transport switching

**State Machine State Transitions:**
- Why fragile: Multiple state transitions (good_count, bad_count, state changes) interdependent
- Files: `src/wanctl/steering/daemon.py` (update_state_machine, lines ~630-680)
- Common failures: Hysteresis logic missed, state inconsistency after crash/restart
- Safe modification: Add pre-flight state validation; verify state file before transitions
- Test coverage: Limited - manual testing used

**Baseline RTT Bounds:**
- Why fragile: Baseline validation bounds (10-60ms) hardcoded
- Files: `src/wanctl/steering/daemon.py` (lines 80-84)
- Common failures: ISP changes (moves to lower-latency ISP), bounds too tight/loose
- Safe modification: Make bounds configurable; add logging when baseline out of bounds
- Test coverage: Unit tests in test_baseline_rtt_manager.py

## Missing Critical Features

**Dashboard/Monitoring UI:**
- Problem: No real-time monitoring interface (command-line only)
- Current workaround: Manual log file inspection, JSON state file parsing
- Blocks: Cannot easily observe steering decisions, bandwidth trends
- Implementation complexity: High (requires web UI framework, data visualization)

**Steering Dry-Run Mode:**
- Problem: No way to test steering rules without actually enabling them
- Current workaround: Manual RouterOS mangle rule testing
- Blocks: Cannot safely validate steering configuration before deployment
- Implementation complexity: Low (log steering decisions without applying them)

**Automatic Remediation:**
- Problem: No automated recovery if daemon crashes during steering
- Current workaround: systemd restart, manual mangle rule cleanup
- Blocks: Long-lasting steering states if daemon exits unexpectedly
- Implementation complexity: Medium (require systemd watchdog hooks)

## Test Coverage Gaps

**RouterOS Integration:**
- What's not tested: REST API client with actual RouterOS (only mocked)
- Risk: Authentication failures, API format changes, network timeouts not caught
- Priority: Medium
- Difficulty: High (requires RouterOS test device or mock server)

**State Machine Edge Cases:**
- What's not tested: Rapid state transitions, concurrent state access
- Risk: Race conditions if steering and autorate run simultaneously
- Priority: Medium
- Difficulty: Medium (requires concurrency testing framework)

**Configuration Edge Cases:**
- What's not tested: Very large queue names, special characters in WAN names
- Risk: Command injection or state file corruption
- Priority: Low (input validation in place, but not exhaustively tested)
- Difficulty: Low (add parametrized tests in test_config_validation_utils.py)

---

*Concerns audit: 2026-01-09*
*Update as issues are fixed or new ones discovered*
