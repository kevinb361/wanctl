# Codebase Concerns

**Analysis Date:** 2026-01-21

## Tech Debt

**Configuration Naming Inconsistency:**
- Issue: `steering_config.yaml` exists in repo but deployment script expects `steering.yaml`
- Files: `configs/steering_config.yaml`, `scripts/deploy.sh:354-361`
- Impact: Steering daemon deployed with generic template instead of production config, silently fails for 3+ days
- Fix approach: Rename `steering_config.yaml` → `steering.yaml` to match deploy script expectations, update deployment checklist with pre/post verification

**Generic Template Fallback Too Permissive:**
- Issue: Deploy script falls back to generic example template without explicit confirmation, deployment succeeds with placeholder values
- Files: `scripts/deploy.sh:354-361`, `configs/examples/steering.yaml.example`
- Impact: Wrong configuration deployed silently (discovered via debug logs, not monitoring)
- Fix approach: Make deploy script fail-fast if production config missing, add validation before deployment starts

**Missing Deployment Config Validation:**
- Issue: Deploy script accepts mismatched configs without validating referenced files/queues exist
- Files: `scripts/deploy.sh`, `scripts/install-systemd.sh`
- Impact: Steering daemon references nonexistent state files (`/run/wanctl/wan1_state.json` instead of `spectrum_state.json`), cannot function
- Fix approach: Add config validation step before deployment that checks state files, queue names, router IP reachability

## Known Issues

**Spectrum WAN Watchdog Restarts (Active):**
- Symptoms: cake-spectrum service restarts 3-5 times per day, each lasting 30-40 seconds
- Root cause: Spectrum ISP cable network experiences brief outages (all ping targets fail simultaneously for 6+ seconds), daemon intentionally stops watchdog to trigger systemd restart as safety mechanism
- Files: `src/wanctl/autorate_continuous.py` (3-consecutive-failure threshold), `/etc/systemd/system/wanctl@.service` (WatchdogSec=30s)
- Workaround: Service auto-recovers within 5 seconds via systemd restart; state preserved so rates resume correctly
- Status: Documented in `docs/SPECTRUM_WATCHDOG_RESTARTS.md` as accepted cable network behavior (Option 1); monitor frequency for escalation if >5/day

**ICMP Blackout Handling (RESOLVED v1.1.0):**
- Symptoms: Prior to v1.1.0, ICMP blocking by Spectrum ISP caused watchdog false-positive restarts
- Resolution: Implemented TCP RTT fallback during connectivity checks via `src/wanctl/rtt_measurement.py`
- Files: `src/wanctl/rtt_measurement.py` (measure_rtt_with_fallback), `src/wanctl/autorate_continuous.py` (used in connectivity loop)
- Current state: Fallback active; system provides accurate latency measurements even during ICMP outages
- Test coverage: Integration tests in `tests/integration/test_latency_control.py`

**Steering Configuration Mismatch (Temporary Fix Applied):**
- Symptoms: Steering daemon logs "Primary WAN state file not found: /run/wanctl/wan1_state.json" every 2 seconds
- Root cause: Generic template deployed with placeholder values instead of production config
- Files: `/etc/wanctl/steering.yaml` (deployed config), `docs/STEERING_CONFIG_MISMATCH_ISSUE.md` (full analysis)
- Workaround: Manual fix applied 2026-01-11 with correct values (spectrum_state.json, WAN-Download-Spectrum, 10.10.99.1)
- Fix approach: Rename `configs/steering_config.yaml` → `configs/steering.yaml` per Option 1 in issue doc
- Status: Awaiting permanent repo fix; production manually patched

## Security Considerations

**SSH Host Key Validation:**
- Risk: Without host key verification, MITM attacker could intercept SSH traffic and modify CAKE bandwidth limits or mangle rules
- Files: `src/wanctl/routeros_ssh.py` (paramiko.RejectPolicy()), `docs/SECURITY.md`
- Current mitigation: SSH client configured with `paramiko.RejectPolicy()` requiring host key in known_hosts; deployment docs require one-time host key registration
- Deployment checklist: Must add router host key via `ssh-keyscan -H <ip> >> /var/lib/wanctl/.ssh/known_hosts` as wanctl service user before deployment
- Recommendations: Document in deployment guide that this is critical pre-requisite; verify in post-deployment checklist

**Password Handling (Externalized):**
- Risk: REST API transport requires password authentication; if hardcoded, exposes credentials
- Files: `src/wanctl/routeros_rest.py:136-140` (env var support), `src/wanctl/autorate_continuous.py:443`, `src/wanctl/steering/daemon.py:179`
- Current mitigation: Code uses environment variable substitution for password (e.g., `${ROUTER_PASSWORD}`); never embedded in config files
- Deployment approach: Password stored in `/etc/wanctl/secrets` (environment file sourced by systemd)
- Recommendations: Verify `/etc/wanctl/secrets` has 600 permissions; audit deployment scripts ensure no password logging

**Input Validation:**
- Risk: Queue names and mangle rule comments may not be validated before sending to RouterOS
- Files: `src/wanctl/router_command_utils.py` (427 lines), `src/wanctl/backends/routeros.py` (239 lines)
- Current state: Config validation in `src/wanctl/config_validation_utils.py` but unclear if runtime routing rule inputs are sanitized
- Recommendations: Audit `router_command_utils.py` and `backends/routeros.py` for shell injection risks in mangle rule generation

## Performance Bottlenecks

**Cycle Interval at Production Minimum:**
- Problem: 50ms cycle interval (20Hz) is 40x faster than original 2s baseline; system runs 60-80% CPU utilization per cycle
- Files: `src/wanctl/autorate_continuous.py:75` (CYCLE_INTERVAL_SECONDS = 0.05), `docs/PRODUCTION_INTERVAL.md` (validation analysis)
- Cause: Each 50ms cycle performs: RTT measurement (~80ms for 3 ping samples), CAKE stats read (~50ms), RouterOS update (~45ms)
- Current headroom: 30-40ms execution time vs 50ms interval = 20-40% margin; no room for network jitter or router CPU spikes
- Improvement path: Phase 2 could implement connection pooling/keep-alive for REST API (~30-50% reduction), parallel ping measurement (~20-40% reduction)

**Profiling Instrumentation Overhead:**
- Problem: Timing measurements logged to disk every cycle (50ms default = 1440 measurements/hour per daemon)
- Files: `src/wanctl/perf_profiler.py` (profiling hooks), logs written to `/var/log/wanctl/`
- Cause: Sub-millisecond profiling accuracy requires high-frequency measurements; JSON logging adds disk I/O
- Current state: Timing data logged at DEBUG level per `docs/PROFILING.md`, log rotation expected (~7 days per doc)
- Risk: If DEBUG logging enabled in production, 1440 extra log lines/hour × 2 daemons = 2880 lines/hour disk writes
- Mitigation: Recommend INFO log level for production (timing data still available via metrics), DEBUG only for troubleshooting

**Router Communication Latency:**
- Problem: REST API transport 2x faster than SSH (~50ms vs ~150-200ms), but still 50% of cycle budget
- Files: `src/wanctl/routeros_rest.py:100-150` (REST client), `src/wanctl/routeros_ssh.py` (SSH client), `docs/TRANSPORT_COMPARISON.md`
- Current state: REST recommended but not enforced; SSH available as fallback
- Impact: SSH deployments already at edge of cycle window; any router load spikes risk exceeding 50ms cycle
- Improvement path: HTTP/2 multiplexing, persistent connections, local caching of frequently-read values

## Fragile Areas

**Baseline RTT Freezing Logic:**
- Files: `src/wanctl/baseline_rtt_manager.py` (266 lines), `src/wanctl/autorate_continuous.py:800-850`
- Why fragile: Baseline RTT must remain frozen during load to prevent drift, but updates when delta < 3ms. Architecture invariant: any baseline update during sustained load invalidates control model.
- Safe modification: Never change baseline update threshold without re-running full validation suite; threshold derived from EWMA mathematical model
- Test coverage: `tests/test_wan_controller_state.py` covers state transitions but unclear if baseline freezing tested under load
- Risk: If threshold tuned incorrectly, control loop becomes unstable (baseline drifts, rate increases during congestion)

**State File Corruption Recovery:**
- Files: `src/wanctl/state_manager.py` (677 lines), `src/wanctl/state_utils.py` (backup/restore logic)
- Why fragile: State files (`spectrum_state.json`, `att_state.json`) persistent across restarts; corruption silently reverts to defaults
- Safe modification: State schema validation happens via `StateSchema` validators; adding new fields requires backwards-compatible migration
- Test coverage: State recovery tested in unit tests but unclear if corruption scenarios tested
- Risk: If state file becomes corrupted (partial write during crash), daemon may lose baseline RTT and restart with cold-start behavior

**Rate Limiter Sliding Window:**
- Files: `src/wanctl/rate_utils.py:160-220` (RateLimiter class), `src/wanctl/autorate_continuous.py:600-650` (invoked in control loop)
- Why fragile: Rate limiter prevents >10 router changes per 60s; sliding window maintained in memory, not persisted
- Safe modification: Don't add additional rate limits without understanding interaction with CAKE state transitions
- Test coverage: Unit tests check rate limiting enforcement but unclear if edge cases tested (e.g., rapid cycle restarts)
- Risk: If rate limiter incorrectly resets on daemon restart, could allow burst of changes exceeding router capacity

**EWMA Smoothing Parameters:**
- Files: `src/wanctl/autorate_continuous.py:200-250` (EWMA constants), `src/wanctl/steering/daemon.py:88-90` (alternative EWMA alphas)
- Why fragile: EWMA time constants (alpha factors) calibrated for specific cycle interval (50ms); changing interval without recalibrating alphas breaks smoothing
- Safe modification: EWMA formula documented in code but time-constant preservation rules must be understood before changes
- Test coverage: Integration tests validate behavior under load but unclear if EWMA math validated independently
- Risk: If cycle interval changed without recalibrating EWMA, control loop becomes over-responsive or sluggish

## Scaling Limits

**Flash Wear Protection Word Limit:**
- Current capacity: 99.7% reduction in router writes via `last_applied_dl_rate`/`last_applied_ul_rate` tracking
- Limit: MikroTik flash limited to ~100k-1M write cycles depending on hardware; current 50ms cycle = 1440 writes/hour = ~12.6M writes/year at old interval, 99.7% reduction = ~37k writes/year (well within limits)
- Scaling path: Increase cycle frequency or add more queues - track applied rates per queue to prevent redundant writes

**State History Size:**
- Current: Steering daemon maintains MAX_TRANSITIONS_HISTORY=50 transition records (line 93 in daemon.py)
- Limit: In-memory deque holds 50 states; minimal memory impact (~1KB), but history too short for root-cause analysis of multi-day issues
- Scaling path: Implement rolling window state logging to disk for post-incident analysis; rotate logs weekly

**Metrics Collection:**
- Current: Prometheus metrics optional on port 9100; IF enabled, additional per-cycle overhead
- Limit: Each cycle records 10-15 metrics via `record_autorate_cycle()` etc.; no batching, direct writes to Prometheus client
- Scaling path: Batch metrics writes or implement in-process aggregation with periodic flush

**Multi-WAN Support:**
- Current: System designed for dual-WAN (Spectrum + ATT); tested with 2 controllers
- Limit: Config references `primary_wan` and `alternate_wan` (binary steering). Third WAN would require architectural change.
- Scaling path: Generalize state machine to N-way routing with per-WAN congestion scores; implement traffic shaping priority queue

## Dependencies at Risk

**paramiko>=3.4.0 (SSH Transport):**
- Risk: SSH transport slower than REST API (150-200ms vs 50ms); dependency adds complexity if rarely used
- Impact: If REST API unavailable, system falls back to SSH with reduced responsiveness
- Migration plan: Mark SSH as deprecated in v1.2, remove in v2.0; encourage REST-only deployments

**pexpect>=4.9.0 (SSH Shell Interaction):**
- Risk: Pexpect is legacy pattern matching library; may not receive updates if paramiko changes SSH protocol
- Impact: SSH routing may break if MikroTik SSH server changes prompt format
- Migration plan: Evaluate dropping pexpect dependency if SSH deprecated; REST API doesn't require pexpect

**requests>=2.31.0 (REST API Client):**
- Risk: Well-maintained but large dependency; if vulnerability discovered, requires urgent patching
- Impact: REST API calls any remote endpoint - credentials transmitted in HTTP auth header (mitigated by HTTPS)
- Migration plan: Regular dependency updates; consider urllib3-only fallback for minimal deployments

## Missing Critical Features

**Monitoring and Observability Gaps:**
- What's missing: No alerting on steering daemon failures (discovered via logs, not alerts)
- Blocks: Production deployments can't verify steering is functioning without manual log monitoring
- Fix approach: Add health check endpoint for steering daemon (similar to autorate), expose via `/health` port 9101; implement external monitoring via Prometheus alerts

**Deployment Validation Automation:**
- What's missing: No automated pre-deployment checks for config validity, no post-deployment verification
- Blocks: Config mismatches (steering example) discovered days later during debug analysis
- Fix approach: Add validation script invoked by deploy.sh that checks: state files exist, queues reachable, router IP accessible

**Multi-Site Deployment Patterns:**
- What's missing: Single-site deployment documented; scaling to multiple locations requires manual config duplication
- Blocks: Adding second router requires copying/editing 4-5 config files and 2 systemd units
- Fix approach: Implement template + variable substitution per Option 4 in steering config doc, or provide deployment cookbook with example playbooks

## Test Coverage Gaps

**Untested Area: SSH Transport Failover:**
- What's not tested: REST API connection failure → automatic fallback to SSH
- Files: `src/wanctl/router_client.py` (get_router_client function), `src/wanctl/routeros_rest.py` (exception handling)
- Risk: If REST API fails in production, fallback path may not work (not exercised in tests)
- Priority: High - SSH fallback is critical safety feature

**Untested Area: State File Corruption Recovery:**
- What's not tested: Partial JSON write during crash, corrupted state file recovery
- Files: `src/wanctl/state_manager.py`, `src/wanctl/state_utils.py:safe_json_load_file`
- Risk: If state file partially written during daemon crash, recovery logic may not restore properly
- Priority: High - state persistence is architectural invariant

**Untested Area: Rate Limit Edge Cases:**
- What's not tested: Rate limiter behavior during rapid daemon restarts, window boundary conditions
- Files: `src/wanctl/rate_utils.py:RateLimiter`, invoked every cycle
- Risk: Sliding window implementation may allow brief bursts exceeding limit
- Priority: Medium - rate limiter is safety mechanism but not critical to core functionality

**Untested Area: Baseline RTT Freezing Under Load:**
- What's not tested: Baseline freezing logic under sustained congestion, EWMA interaction
- Files: `src/wanctl/baseline_rtt_manager.py`, `src/wanctl/autorate_continuous.py:800-850`
- Risk: If baseline incorrectly updates during load, control loop destabilizes
- Priority: High - baseline freezing is architectural invariant documented in CLAUDE.md

**Untested Area: ICMP Fallback Fallback:**
- What's not tested: TCP RTT measurement failure → what happens? Does steering still work?
- Files: `src/wanctl/rtt_measurement.py:measure_rtt_with_fallback`, fallback strategy unclear
- Risk: If both ICMP and TCP fail, measurement returns stale/None, control loop may hang or use invalid delta
- Priority: Medium - fallback already deployed but edge case behavior not documented

---

## Monitoring Recommendations

**Short-Term Actions:**

1. **Steering daemon health checks** - Add endpoint at `/health` with steering-specific status (currently only autorate health endpoint exists)
2. **Deployment validation script** - Create `scripts/validate-deployment.sh` to verify configs before systemd start
3. **Log aggregation alerts** - Parse steering logs for "ERROR" patterns, alert on >1 error per minute sustained

**Long-Term Actions:**

1. **Config validation in deploy.sh** - Check state files, queue names, router reachability before deployment
2. **Rename steering config** - Move `steering_config.yaml` → `steering.yaml` to match deploy script expectations
3. **Profiling metrics dashboard** - Expose cycle timing via Prometheus; alert if p99 > 40ms (trend toward cycle miss)

---

## Related Files

**Active Issues:**
- `docs/SPECTRUM_WATCHDOG_RESTARTS.md` - Cable network instability causing 3-5 restarts/day
- `docs/STEERING_CONFIG_MISMATCH_ISSUE.md` - Generic template deployed instead of production config
- `docs/SECURITY.md` - SSH host key validation requirements

**Core Architecture:**
- `src/wanctl/autorate_continuous.py` (1793 lines) - Main control loop
- `src/wanctl/steering/daemon.py` (1665 lines) - Traffic steering
- `src/wanctl/baseline_rtt_manager.py` (266 lines) - Baseline freezing logic
- `src/wanctl/state_manager.py` (677 lines) - State persistence

**Configuration:**
- `configs/steering_config.yaml` - Production steering config (TO BE RENAMED)
- `configs/examples/steering.yaml.example` - Generic template

**Deployment:**
- `scripts/deploy.sh:354-361` - Deploy script with config lookup logic

---

## Decision Log

| Date | Issue | Status | Notes |
|------|-------|--------|-------|
| 2026-01-11 | Spectrum watchdog restarts | Documented | Accepted as cable network behavior per Option 1; monitoring only |
| 2026-01-11 | Steering config mismatch | Temporary fix applied | Manual correction deployed; awaiting repo rename |
| 2026-01-21 | Security: SSH host keys | Documented | Required for deployment; included in SECURITY.md |
| 2026-01-21 | Performance: 50ms cycle at limit | Documented | Headroom 20-40%; Phase 2 optimizations planned |

---

**Concerns audit: 2026-01-21**
