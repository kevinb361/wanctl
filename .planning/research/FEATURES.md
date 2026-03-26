# Feature Research: v1.22 Full System Audit

**Domain:** Production network controller system audit (3 perspectives)
**Researched:** 2026-03-26
**Confidence:** HIGH (codebase analysis, production deployment knowledge, established audit methodologies)

## Audit Landscape

This is not a feature-build milestone. The "features" here are **audit categories** -- what each of three expert perspectives checks, what findings are likely, and where the perspectives overlap vs. provide unique value.

### Table Stakes (Must Check -- Every Production Audit)

Audit areas that are non-negotiable. Missing any of these means the audit is incomplete and findings are unreliable.

#### Network Engineering Perspective

| Audit Area | Why Essential | Complexity | Notes |
|------------|--------------|------------|-------|
| CAKE parameter correctness per WAN type | Wrong overhead/MPU causes throughput loss or packet corruption; DOCSIS and DSL have different encapsulation overhead needs | MEDIUM | Verify `overhead`, `mpu`, `atm`/`noatm`/`ptm` per link. Spectrum=DOCSIS (docsis keyword, or conservative), ATT=VDSL2 (bridged-ptm, overhead 22, atm). Check `tc -j qdisc show` readback on production VM matches intended config. |
| DSCP/diffserv tin alignment end-to-end | Misaligned DSCP marks between RB5009 mangle rules and CAKE tins silently misclassifies traffic. Voice in Bulk tin = latency spike. | MEDIUM | Trace DSCP marking from RB5009 mangle rules through L2 bridge to CAKE diffserv4 tin assignment. Verify EF (46) hits Voice tin, AF41 (34) hits Video, CS1 (8) hits Bulk. Use `tc -s -d qdisc show` per-tin packet counts during known traffic to validate. |
| Bandwidth ceiling/floor sanity vs measured link capacity | Ceiling above actual link rate means CAKE never shapes (bufferbloat returns). Floor too high means unnecessary throttling. | LOW | Compare config ceiling_mbps with recent flent RRUL benchmarks. Check that floor values are achievable during worst-case congestion. Verify `exclude_params` for DOCSIS cable prevents auto-tuner from tightening below jitter floor (~12ms). |
| Reflector selection and latency measurement methodology | Bad reflectors produce noisy baselines; single-reflector failure causes control instability | LOW | Audit reflector IPs/hosts: are they low-latency, geographically appropriate, ICMP-responsive? Verify IRTT reflector (Dallas 104.200.21.31:2112) is stable. Check reflector scoring thresholds (min_score) are appropriate. |
| Steering logic correctness | Wrong steering decisions route latency-sensitive traffic over congested WAN, defeating the purpose | MEDIUM | Audit confidence scoring weights, degrade timers, recovery gates. Verify CAKE-primary invariant (WAN zone alone cannot trigger steering). Check grace period behavior on startup. Test with simulated congestion on each WAN. |
| Baseline RTT management under load | Baseline drift during congestion causes permanent undershoot or overshoot | LOW | Verify baseline only updates when delta < 3ms (frozen during load). Check baseline bounds config. Confirm adaptive tuning baseline_bounds strategy respects `exclude_params`. |

#### Linux Sysadmin Perspective

| Audit Area | Why Essential | Complexity | Notes |
|------------|--------------|------------|-------|
| systemd unit hardening (systemd-analyze security) | Unhardened service units expose attack surface; production daemon running as non-root with CAP_NET_RAW needs minimal privilege | LOW | Run `systemd-analyze security wanctl@spectrum`. Current units have PrivateTmp, ProtectSystem=strict, ProtectHome, NoNewPrivileges. Missing: ProtectKernelTunables, ProtectKernelModules, ProtectKernelLogs, ProtectControlGroups, RestrictSUIDSGID, RestrictNamespaces, SystemCallFilter, MemoryDenyWriteExecute. Target: exposure score < 4.0. |
| File permissions and ownership | Wrong perms on /etc/wanctl (secrets), /var/lib/wanctl (state), /var/log/wanctl lets unauthorized reads/writes | LOW | Audit: secrets file should be 0600 root:wanctl (or 0640). State dir 0750 wanctl:wanctl. Log dir 0750 wanctl:wanctl. Config YAMLs 0644 or 0640. No world-readable secrets. Check /opt/wanctl perms. |
| Log rotation and disk space | Unrotated logs fill /var/log and crash the VM; SQLite WAL can grow unbounded during maintenance windows | LOW | Verify journald MaxRetentionSec and SystemMaxUse. Check if RotatingFileHandler (10MB/3 backups) is active alongside journald (may be redundant). Verify SQLite VACUUM runs in hourly maintenance. Check /var/lib/wanctl/metrics.db growth rate. |
| NIC and bridge persistence across reboot | PCIe passthrough NICs lose CAKE qdiscs and bridge config on reboot; system comes up with broken networking | MEDIUM | Verify systemd-networkd .netdev and .network files create bridges on boot. Confirm CAKE qdisc is applied by wanctl startup (not systemd-networkd -- documented pitfall). Check `rx-udp-gro-forwarding` persistence (currently NOT persistent -- memory note). |
| Backup and recovery procedures | No backup = unable to recover from disk failure, VM corruption, or botched update | MEDIUM | Check: is /etc/wanctl backed up? Is metrics.db backed up? Is there a documented restore procedure? What is the VM snapshot strategy? Can the old containers be brought back if the VM fails? |
| Watchdog and circuit breaker behavior | Watchdog timeout too tight kills healthy daemons under CPU pressure; too loose masks hangs | LOW | WatchdogSec=30s with 50ms cycles gives 600x margin. Verify systemd watchdog ping is in the event loop. StartLimitBurst=5/StartLimitIntervalSec=300 for circuit breaker. Steering unit missing StartLimitBurst/Interval (inconsistency). |
| Resource limits (memory, CPU, open files) | Python memory leaks or SQLite connection leaks cause OOM or fd exhaustion after days of uptime | LOW | Check if systemd units set MemoryMax, TasksMax, LimitNOFILE. Monitor RSS growth over time. Check for deque maxlen bounds, connection pool limits, thread count stability. |

#### Python Developer Perspective

| Audit Area | Why Essential | Complexity | Notes |
|------------|--------------|------------|-------|
| Dead code identification | 28k LOC across 21 milestones = guaranteed dead code. Increases cognitive load, test surface, and confusion. | MEDIUM | Use vulture or pyflakes --unused. Check for: unreachable branches behind feature flags that shipped, methods only called from removed code, test fixtures for deleted features. Previous cleanup in v1.5 and v1.13 found substantial dead code. 21 milestones since then. |
| Type safety audit (mypy strictness) | Current config: `disallow_untyped_defs = false`, `ignore_missing_imports = true`. Untyped code hides type bugs silently. | MEDIUM | Run `mypy --strict` and categorize errors. 733 function definitions, unknown percentage typed. Goal: enable `disallow_untyped_defs = true` on at least core modules (autorate_continuous, state_manager, backends/). Count `# type: ignore` comments and audit whether justified. |
| Exception handling hygiene | 96 `except Exception` catches -- many may swallow real bugs, hide configuration errors, or mask network failures | HIGH | Audit each broad exception catch: is the default_return safe? Is the error logged at appropriate level? Do any swallow TypeError/ValueError that indicate bugs rather than operational errors? The handle_errors decorator centralizes this but parameterization may be wrong. |
| Test quality vs quantity | 3,723 tests at 91%+ coverage -- but coverage does not equal correctness. Flaky tests, over-mocking, and assertion-free tests are common in rapid-iteration codebases. | MEDIUM | Check for: tests that only assert "no exception raised" (assertion-free), over-mocked tests where mock behavior diverges from real behavior, test duplication across files, tests that pass regardless of code changes (tautological). Largest test file: test_steering_daemon.py at 5,743 lines -- likely has maintenance burden. |
| Dependency hygiene | 6 runtime deps, 10 dev deps. Paramiko 4.0+ changed auth semantics. Cryptography pins may lag behind CVEs. | LOW | Run `pip-audit`. Check: is paramiko version compatible with 4.0+ SSH key changes? Is cryptography >= 46.0.5 still current? Are all 6 runtime deps actually imported in production code? Is textual (optional dashboard dep) tested? |
| Complexity hotspots | autorate_continuous.py at 4,282 lines is the largest file -- likely has high cyclomatic complexity functions that resist testing and modification | MEDIUM | Run radon or lizard on src/. Known from v1.5: 11 high-complexity functions documented. Check if count has grown. Files > 500 lines: autorate_continuous (4282), steering/daemon (2384), check_config (1484), check_cake (1251), calibrate (1135). These are extraction candidates. |
| Import structure and circular dependencies | 59 imports in autorate_continuous.py alone. Deep import chains add startup latency and create fragile coupling. | LOW | Map import graph. Check for circular imports (Python handles them but they indicate architecture issues). Verify no import-time side effects (module-level code that runs on import). |

### Differentiators (Catches Subtle Issues)

Audit areas that go beyond table stakes. These are where the 3 perspectives provide unique value that a generic checklist misses.

#### Network Engineering (Unique Finds)

| Audit Area | Value Proposition | Complexity | Notes |
|------------|-------------------|------------|-------|
| CAKE algorithm parameter audit (split-gso, ack-filter, wash) | Suboptimal CAKE params waste bandwidth or introduce latency that the controller then fights against | MEDIUM | Linux CAKE supports params not available on MikroTik: `split-gso` (reduces burst jitter on high-speed links), `ack-filter` (for upload -- reduces ACK-induced bloat on asymmetric links), `wash` (clear DSCP on egress toward ISP). Verify production CAKE has optimal params per-direction per-WAN. |
| Measurement path integrity (ICMP vs TCP vs IRTT) | If measurement path differs from data path, controller optimizes the wrong thing | LOW | Verify ICMP/IRTT probes traverse the same CAKE qdisc as user traffic. On transparent bridge, all traffic shares the same path -- but verify this is actually true (no bypass routes). Check if ICMP deprioritization is still occurring (Spectrum ISP issue from v1.1.0). |
| Congestion state machine timing vs link physics | Threshold timings tuned for one link type may be wrong for another after CAKE offload changed latencies | MEDIUM | Offload reduced control loop latency by ~5ms (local tc vs REST API). Verify GREEN-to-YELLOW threshold, EWMA time constants, and recovery cycle counts still produce correct behavior. The adaptive tuner may have already compensated, but verify. |
| Queue depth and memory pressure analysis | CAKE memory_limit too low drops packets before bandwidth limit triggers; too high adds latency | LOW | Read `tc -j -s` memory_used/memory_limit fields. Compare against traffic volume. Check if CAKE capacity_estimate matches configured bandwidth. This data was not available on MikroTik -- first time it can be audited. |

#### Linux Sysadmin (Unique Finds)

| Audit Area | Value Proposition | Complexity | Notes |
|------------|-------------------|------------|-------|
| Kernel and iproute2 version audit | Wrong kernel version = missing CAKE features or bugs. iproute2 mismatch = silent tc failures. | LOW | Check kernel has sch_cake module loaded. Verify iproute2 version supports all CAKE params in use. The ecn flag removal (v1.21 Phase 110) was caused by iproute2-6.15.0 incompatibility -- are there more lurking? |
| Network namespace and bridge isolation | Transparent bridge can leak traffic between VLANs if misconfigured; bridge firewall rules (br_netfilter) add CPU overhead | MEDIUM | Check `net.bridge.bridge-nf-call-iptables` sysctl (should be 0 for transparent bridge -- no conntrack). Verify no IP address on bridge interfaces (pure L2). Check ARP/NDP behavior through bridge. Audit VLAN 110 management plane isolation. |
| Prometheus-compatible metrics export readiness | When monitoring stack is added, the health endpoint format determines migration effort | LOW | Current health endpoints return JSON. Check if metric names follow Prometheus naming conventions (lowercase, underscores, _total suffix for counters). Not blocking but cheap to fix now vs later. |
| Disaster recovery: container fallback path | If VM fails, can old containers be brought back within minutes? | LOW | Old containers decommissioned. Document: are container images still available? Are MikroTik CAKE configs still valid? What is the rollback procedure and estimated time? |

#### Python Developer (Unique Finds)

| Audit Area | Value Proposition | Complexity | Notes |
|------------|-------------------|------------|-------|
| Singleton and global state audit | MetricsWriter singleton, global loggers, module-level state create hidden coupling and test fragility | MEDIUM | Documented: MetricsWriter needs `_reset_instance()` in tests. Are there other singletons? Check for module-level mutable state (dicts, lists, sets initialized at import time). These cause test ordering dependencies and make parallel test execution impossible. |
| Thread safety audit | 16 files use threading. Lock-free IRTT caching, webhook delivery threads, health server threads. Python GIL does NOT protect against all race conditions. | HIGH | Audit: shared mutable state between threads, proper use of threading.Event for shutdown, daemon thread cleanup. The signal_utils.py threading.Event pattern is documented as "do not change" -- but verify other thread uses follow same discipline. Check for time-of-check-time-of-use (TOCTOU) in state file operations. |
| Error recovery path testing | handle_errors decorator wraps 73+ functions. Are the error paths actually tested, or just the happy paths? | MEDIUM | For each `@handle_errors` usage: is there a test that triggers the exception and verifies the default_return is correct? Do error paths maintain state consistency (e.g., does a failed router update leave `last_applied_dl_rate` in a correct state)? |
| SQLite durability and concurrent access | metrics.db written by autorate + steering + maintenance. WAL mode helps but incorrect locking = corruption. | MEDIUM | Verify: WAL mode enabled, busy_timeout set, no connection sharing across threads. Check maintenance VACUUM timing vs active writes. Verify auto-rebuild on corruption (v1.10 feature) still works. Check SQLite version on Debian 12 for known bugs. |
| Configuration validation completeness | 6 validation categories exist. But do they catch every possible misconfiguration, or are there gaps? | LOW | Systematically test: what happens with missing required fields? Typos in enum values? Numeric fields with string values? Extra unknown fields? Cross-reference config_validation_utils.py validators against CONFIG_SCHEMA.md. |

### Anti-Features (Audit Areas to Explicitly NOT Pursue)

Audit areas that seem valuable but create problems if pursued during this milestone.

| Anti-Feature | Why Tempting | Why Problematic | What to Do Instead |
|--------------|-------------|-----------------|-------------------|
| Full rewrite of autorate_continuous.py | 4,282-line file is the obvious "big target" | Rewrite risk in production 50ms control loop is extreme. Behavioral regressions in the core algorithm could take days to surface. | Identify extraction candidates only. Document which functions could be moved to new modules. Do not execute extraction in this milestone. |
| Migrating to strict mypy globally | Type safety is clearly underenforced | Enabling strict mypy on 28k LOC at once generates 100s of errors, creating a massive changeset that is impossible to review meaningfully. | Enable strict per-module, starting with leaf modules (models, utils). Track progress. Complete in a future milestone. |
| Rewriting tests to remove all mocking | Over-mocking is a real problem but mock removal requires understanding every real dependency's behavior | Removing mocks from network/subprocess tests means tests hit real routers, real tc commands, or real networks -- making them environment-dependent and slow. | Identify tests where mocks diverge from reality. Add targeted integration tests for the riskiest gaps. Keep unit test mocks but fix incorrect mock behavior. |
| Adding Prometheus/Grafana | Monitoring would be valuable for audit findings | Scope creep -- this is infrastructure work that belongs in a separate milestone. The audit should document readiness, not implement it. | Document current metric naming, identify format gaps, recommend changes for future Prometheus compatibility. |
| Performance optimization of the 50ms loop | Profiling will reveal optimization opportunities | The loop already runs within budget (30-40ms of 50ms). Premature optimization during audit scope causes instability. | Document findings from profiling. Flag anything over 40ms. Defer optimization to a focused milestone. |
| Automating all audit checks | Running everything via CI sounds efficient | Many audit findings require human judgment (is this exception handler correct? Is this threshold appropriate for this link type?). Automating the wrong thing gives false confidence. | Automate the mechanical checks (dead code, type errors, dependency versions). Keep the judgment-based audits as documented manual procedures. |

## Audit Area Dependencies

```
[systemd hardening]
    requires--> [file permissions audit]  (hardening changes may affect path access)

[dead code removal]
    requires--> [test quality audit]  (removing code requires knowing if tests catch regressions)
    requires--> [import structure audit]  (understanding what imports what)

[exception handling audit]
    enhances--> [error recovery path testing]  (fixing handlers requires testing the fix)

[CAKE parameter audit]
    requires--> [kernel/iproute2 version audit]  (available params depend on versions)
    enhances--> [DSCP tin alignment]  (CAKE params affect tin behavior)

[NIC/bridge persistence]
    requires--> [kernel/iproute2 audit]  (systemd-networkd behavior depends on kernel)
    conflicts-with--> [CAKE param changes]  (don't change CAKE params while auditing bridge persistence)

[thread safety audit]
    requires--> [singleton/global state audit]  (must know what state is shared before auditing thread safety)

[type safety audit]
    enhances--> [dead code identification]  (mypy errors often flag unreachable code)

[steering logic audit]
    requires--> [CAKE parameter audit]  (steering depends on accurate congestion detection which depends on correct CAKE behavior)
```

### Dependency Notes

- **Dead code removal requires test quality audit:** Cannot safely remove code without knowing whether the tests that cover it are meaningful or tautological.
- **CAKE parameter audit requires kernel version audit:** Some CAKE params (e.g., `split-gso`) are kernel-version-dependent. Must know what the kernel supports before auditing params.
- **Thread safety requires singleton audit:** Cannot reason about thread safety without first mapping all shared mutable state.
- **NIC/bridge persistence conflicts with CAKE param changes:** Do not change CAKE params and bridge config in the same phase -- if something breaks, you cannot isolate the cause.

## Audit Prioritization

### Phase 1: Foundation (Mechanical, Low-Risk)

Audit areas that are safe to execute, produce clear findings, and unblock later phases.

- [ ] Kernel/iproute2 version audit -- unblocks CAKE param audit
- [ ] File permissions and ownership -- quick wins, no code changes
- [ ] Dependency hygiene (pip-audit, version checks) -- mechanical
- [ ] Dead code scan (vulture/pyflakes) -- identification only, no removal yet
- [ ] systemd-analyze security -- produces hardening score and specific recommendations
- [ ] Log rotation and disk space verification -- operational hygiene

### Phase 2: Network Engineering Deep Dive

Requires production access and domain expertise. Benefits from Phase 1 findings.

- [ ] CAKE parameter correctness per-WAN with `tc -j -s qdisc show` readback
- [ ] DSCP/diffserv tin alignment end-to-end trace
- [ ] Measurement path integrity verification
- [ ] CAKE algorithm params (split-gso, ack-filter, wash) optimization review
- [ ] Queue depth and memory pressure analysis
- [ ] Bandwidth ceiling/floor vs measured capacity validation

### Phase 3: Code Quality and Safety

Requires Phase 1 dead code scan results. Produces fixes that must be tested.

- [ ] Exception handling audit (96 broad catches) -- identify, categorize, fix
- [ ] Type safety assessment (mypy --strict dry run, module-by-module plan)
- [ ] Complexity hotspot analysis (radon/lizard on 5 largest files)
- [ ] Import structure and circular dependency check
- [ ] Singleton and global state inventory
- [ ] Thread safety audit (16 threaded files)

### Phase 4: Operational Hardening

Requires findings from all prior phases to prioritize.

- [ ] systemd unit hardening implementation (from Phase 1 findings)
- [ ] NIC and bridge persistence fixes
- [ ] Watchdog and circuit breaker consistency
- [ ] Resource limits (MemoryMax, TasksMax, LimitNOFILE)
- [ ] Backup and recovery documentation
- [ ] Disaster recovery: container fallback path documentation

### Phase 5: Test and Documentation Hygiene

Final phase -- validates all prior changes and documents findings.

- [ ] Test quality audit (assertion-free, over-mocked, tautological)
- [ ] Error recovery path test coverage
- [ ] SQLite durability verification
- [ ] Configuration validation completeness
- [ ] Documentation freshness audit (docs/* dates vs code reality)
- [ ] Audit findings summary and remaining-debt inventory

## Audit Prioritization Matrix

| Audit Area | Risk if Skipped | Effort | Priority | Perspective |
|------------|----------------|--------|----------|-------------|
| CAKE parameter correctness | HIGH (wrong shaping) | MEDIUM | P1 | Network |
| systemd hardening | MEDIUM (attack surface) | LOW | P1 | Sysadmin |
| Dead code identification | LOW (cognitive load) | LOW | P1 | Python |
| Exception handling audit | HIGH (silent failures) | HIGH | P1 | Python |
| DSCP tin alignment | MEDIUM (misclassification) | MEDIUM | P1 | Network |
| File permissions | MEDIUM (security) | LOW | P1 | Sysadmin |
| Thread safety | HIGH (race conditions) | HIGH | P2 | Python |
| NIC/bridge persistence | HIGH (reboot failure) | MEDIUM | P2 | Sysadmin |
| Type safety assessment | LOW (future quality) | MEDIUM | P2 | Python |
| Complexity hotspots | LOW (maintainability) | LOW | P2 | Python |
| Backup/recovery docs | MEDIUM (disaster prep) | LOW | P2 | Sysadmin |
| Steering logic audit | MEDIUM (wrong routing) | MEDIUM | P2 | Network |
| Test quality audit | LOW (false confidence) | HIGH | P3 | Python |
| Prometheus readiness | LOW (future work) | LOW | P3 | Sysadmin |
| Queue depth analysis | LOW (rare issue) | LOW | P3 | Network |
| Measurement path integrity | LOW (likely correct) | LOW | P3 | Network |

**Priority key:**
- P1: Must audit -- production safety or security impact
- P2: Should audit -- prevents future problems
- P3: Nice to audit -- optimization and polish

## Cross-Perspective Overlap and Unique Value

| Area | Network Eng | Sysadmin | Python Dev | Who Leads |
|------|------------|----------|------------|-----------|
| CAKE params | **Primary** (correctness) | Supports (persistence) | -- | Network Eng |
| systemd units | -- | **Primary** (hardening) | -- | Sysadmin |
| Dead code | -- | -- | **Primary** (identification) | Python Dev |
| Thread safety | -- | -- | **Primary** (correctness) | Python Dev |
| Bridge config | Validates (traffic flow) | **Primary** (persistence) | -- | Sysadmin |
| Exception handling | -- | -- | **Primary** (code quality) | Python Dev |
| DSCP alignment | **Primary** (classification) | -- | Supports (config parsing) | Network Eng |
| Watchdog/circuit breaker | -- | **Primary** (reliability) | Supports (implementation) | Sysadmin |
| Steering logic | **Primary** (network correctness) | -- | Supports (code correctness) | Network Eng |
| Metrics/observability | Supports (what to measure) | Supports (retention/export) | **Primary** (implementation) | Python Dev |
| Security (secrets, perms) | -- | **Primary** (OS-level) | Supports (code-level) | Sysadmin |

## Common Findings in Rapid-Development Production Python Systems

Based on wanctl's specific characteristics (21 milestones, 28k LOC, 3,723 tests, single developer, 50ms real-time loop):

| Finding Pattern | Likelihood in wanctl | Why | Where to Look |
|-----------------|---------------------|-----|----------------|
| Dead imports and unused variables | HIGH | Ruff catches most, but conditional imports and test fixtures accumulate | Run vulture across src/ and tests/ |
| Broad exception handlers masking bugs | HIGH | 96 `except Exception` catches. Rapid iteration prioritizes "don't crash" over "crash correctly" | error_handling.py decorator usage sites |
| Configuration drift from documentation | HIGH | 21 milestones of config additions. CONFIG_SCHEMA.md may lag behind actual accepted params. | Diff CONFIG_SCHEMA.md against config_validation_utils.py |
| Test fixtures that no longer match production | MEDIUM | MagicMock guards added reactively. Fixture configs may not match current YAML schema. | conftest.py mock_autorate_config vs real configs |
| Inconsistent error logging levels | MEDIUM | Different milestones used different conventions for warning vs error vs info | Grep for logger.warning vs logger.error on similar failure modes |
| Stale documentation references | HIGH | docs/ has files from Dec 2025 -- Jan 2026. Architecture changed significantly in v1.21. | Check dates on all docs/ files. DOCKER.md may reference old container deployment. |
| Orphaned scripts | HIGH | scripts/ has container_install_*.sh, deploy_clean.sh etc. from container era. scripts/.obsolete/ exists but may not contain all obsolete scripts. | Cross-reference scripts/ with current deployment (VM, not containers) |
| Incomplete cleanup of old architecture | MEDIUM | v1.13 removed legacy modes but v1.21 changed deployment model. Router backend code for REST/SSH may have stale paths for container IPs. | Check routeros_rest.py, routeros_ssh.py for container-era assumptions |
| Module boundary violations | MEDIUM | 4,282-line autorate_continuous.py suggests extracted functions may have been added back over time | Check if state_manager, signal_processing, rate_utils are actually used or if autorate_continuous.py duplicates their logic |
| Missing edge case tests for new features | MEDIUM | Each milestone adds tests for its own features but may not add edge-case tests for interactions with prior features | Check test coverage for cross-feature interactions (e.g., adaptive tuning + signal fusion + steering) |

## Sources

- [tc-cake(8) Linux manual page](https://man7.org/linux/man-pages/man8/tc-cake.8.html) -- CAKE parameter reference
- [systemd service hardening - Linux Audit](https://linux-audit.com/systemd/how-to-harden-a-systemd-service-unit/) -- systemd hardening checklist
- [Ctrl blog - systemd hardening 101](https://www.ctrl.blog/entry/systemd-service-hardening.html) -- incremental hardening approach
- [STX Next - Python code quality audit](https://www.stxnext.com/blog/how-to-audit-the-quality-of-your-python-code) -- Python audit methodology
- [mypy docs - existing codebase](https://mypy.readthedocs.io/en/stable/existing_code.html) -- gradual typing strategy
- [FlagShark - dead code detection](https://flagshark.com/blog/dead-code-detection-codebase-more-than-you-think/) -- dead code patterns
- [Bufferbloat.net - CAKE technical](https://www.bufferbloat.net/projects/codel/wiki/CakeTechnical/) -- CAKE internals
- wanctl codebase analysis (pyproject.toml, src/, tests/, systemd/, scripts/, docs/)

---
*Audit feature research for: wanctl v1.22 Full System Audit*
*Researched: 2026-03-26*
