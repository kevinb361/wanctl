# v1.22 Full System Audit -- Findings Summary

**Milestone:** v1.22 Full System Audit
**Phases:** 112 (Foundation Scan) through 116 (Test & Documentation Hygiene)
**Date:** 2026-03-26
**Status:** Complete

## Executive Summary

The v1.22 Full System Audit examined the entire wanctl codebase and production deployment across 5 phases covering dependency hygiene, network engineering, code quality, operational hardening, and test/documentation hygiene. A total of 15 findings files were produced by 16 plans across 5 phases. The audit identified **87 distinct findings**, resolved **34 during the audit itself**, and documented **53 remaining as technical debt** categorized by severity. No P0 (critical) issues were found -- the system is production-healthy.

## Resolved in v1.22

### Phase 112: Foundation Scan

- **Removed unused dependency:** `cryptography` from direct deps (transitive via paramiko, never directly imported)
- **Removed redundant dev dep:** `pyflakes` (superseded by ruff F rules)
- **Expanded ruff rules:** Added 8 rule categories (C901, SIM, PERF, RET, PT, TRY, ARG, ERA); auto-fixed 138 violations, manually fixed 17
- **Created vulture whitelist:** `.vulture_whitelist.py` with 68 entries covering all 15 PITFALLS.md false positive patterns
- **Cataloged dead code:** 0 true dead code at 80% confidence; 4 likely dead items identified at 60%
- **Verified log rotation:** Production logs healthy (95 MB total, 3 backups per service, RotatingFileHandler configured correctly)
- **Audited file permissions:** 31 items checked, 18 PASS, 13 NOTE (minor defense-in-depth), 0 FAIL
- **Baselined systemd security:** Documented all 4 unit files with hardening opportunity catalog

### Phase 113: Network Engineering Audit

- **Verified all CAKE parameters:** Both WANs (Spectrum docsis + ATT bridged-ptm) match config YAML -- 100% parameter match on diffserv, overhead, atm, ack-filter, split-gso, ingress, memlimit, rtt
- **Documented complete DSCP chain:** End-to-end trace from MikroTik mangle rules through transparent bridge to CAKE diffserv4 tin classification (4-stage pipeline: wash, classify, mark, priority)
- **Confirmed CAKE-primary invariant:** Steering is correctly unidirectional (Spectrum primary -> ATT fallback)
- **Verified measurement methodology:** Signal chain documented (ICMP -> Hampel -> Fusion -> EWMA -> Baseline -> Delta -> 4-state FSM)
- **Baselined queue depth and memory:** Zero backlog in GREEN state, memory usage 1.6%-60.9% across 4 qdiscs, 32 MB memlimit confirmed appropriate
- **Confirmed measurement traffic classification:** ICMP/IRTT correctly in CS0/Best Effort (not prioritized -- essential for accurate autorate readings)

### Phase 114: Code Quality & Safety

- **Triaged all 93 exception catches:** 74 safety nets with logging, 3 cleanup-then-reraise, 3 intentional silent (nosec B110), 5 UI widget catches (acceptable), 5 bug-swallowing (documented for fix)
- **Verified MyPy strictness:** 5/5 leaf modules pass `disallow_untyped_defs` with zero errors
- **Analyzed complexity hotspots:** 16 functions >complexity 15 documented with extraction recommendations
- **Built import graph:** 82 modules, 137 edges, 0 runtime circular deps (2 TYPE_CHECKING guarded only)
- **Cataloged thread safety:** 24 shared mutable state instances, 17 protected, 7 GIL-safe unprotected, 0 high-severity race conditions
- **Documented full SIGUSR1 chain:** 5 reload targets across 2 daemons, all with error handling, 100% test coverage (unit + E2E)
- **Created E2E SIGUSR1 test suite:** `test_sigusr1_e2e.py` covering complete signal-to-reload chain for both daemons

### Phase 115: Operational Hardening

- **Hardened systemd units:** wanctl@ from 8.4 EXPOSED to 2.1 OK, steering from 8.4 to 1.9 OK (kernel protection, capability bounding, syscall filtering, namespace restrictions)
- **Applied resource limits:** MemoryMax/MemoryHigh/TasksMax/LimitNOFILE on all runtime services, sized from production observation
- **Confirmed NIC tuning persistence:** Full VM reboot verified all 4 services start cleanly with ring buffers and GRO forwarding
- **Made circuit breaker consistent:** StartLimitBurst=5/StartLimitIntervalSec=300 on all 3 runtime units (was missing from steering.service)
- **Created backup/recovery runbook:** 6-section procedure covering configs, metrics.db, VM snapshots, Phase 115 rollback, verification
- **Captured production dependency lock:** `requirements-production.txt` from live VM pip freeze (28 pinned packages)
- **Created deploy/systemd/ directory:** Version-controlled source of truth for production unit files

### Phase 116: Test & Documentation Hygiene

- **Fixed 4 HIGH-risk assertion-free tests:** Added meaningful assertions to tests that gave false confidence (argparse tests, storage disabled test, dry run recovery test)
- **Scanned all 126 test files:** AST-based quality audit of 3,888 tests; 0 tautological tests found
- **Aligned CONFIG_SCHEMA.md:** Added 6 missing config sections (storage, cake_params, cake_optimization, fallback_checks, linux-cake transport, logging rotation)
- **Updated 12 docs for VM architecture:** Replaced container/LXC references with VM/bridge/CAKE-on-Linux throughout docs/
- **Archived container-era scripts:** container_network_audit.py moved to .archive/ with manifest documenting all archived and previously-removed scripts

## Remaining Debt

### P0 -- Critical (fix before next feature work)

No P0 findings. The system is production-healthy with no correctness or data-loss risks identified.

### P1 -- High (fix in next milestone)

| # | Finding | Source Phase | Description | Recommended Milestone |
|---|---------|-------------|-------------|----------------------|
| 1 | 5 bug-swallowing exception catches | 114 | Silent `except Exception: pass` in router_client.py (2), rtt_measurement.py (1), benchmark.py (1), calibrate.py (1) -- errors swallowed without any logging | v1.23 |
| 2 | requests 2.32.3 below minimum on production | 115 | Production VM has requests 2.32.3 but pyproject.toml requires >=2.33.0 (CVE-2026-25645 fix) | v1.23 deployment |
| 3 | 3 medium-severity thread race conditions | 114 | `_parameter_locks` dict iteration in health_check, `state_mgr.state` dict reads in steering health, `_get_connection()` without lock in storage/writer -- all GIL-safe under CPython but not portable | v1.23 |
| 4 | `main()` complexity 68 in autorate_continuous.py | 114 | Highest complexity function in codebase; argument parsing + 3 modes + daemon loop + shutdown in single function | v1.23 |

### P2 -- Medium (fix when convenient)

| # | Finding | Source Phase | Description | Recommended Milestone |
|---|---------|-------------|-------------|----------------------|
| 5 | 4 likely dead code items | 112 | `_create_transport()` (superseded), `SteeringLogger` (unused class), `_ul_last_congested_zone` (orphaned attr), `_last_tuning_ts` (orphaned attr) -- ~270 lines total | v1.23 |
| 6 | 9 dead code items needing investigation | 112 | `BaselineRTTManager`, `update_ewma()`, `RouterOSController` (steer), abstract backend methods, Result pattern methods, `safe_parse_output()`, `handle_command_error()`, `set_queue_limit()` | v1.23 |
| 7 | 33 ERA001 commented-out code instances | 112 | Across 20 files, largest in test_check_cake.py (8), test_fusion_reload.py (3) -- need manual review to distinguish documentation from dead code | v1.23 |
| 8 | 16 high-complexity functions (>15) | 112/114 | 4 functions >complexity 20 (main:68, run_cycle:30, _get_health_status:24, steering main:23); 12 functions at 15-20 | v1.23 |
| 9 | autorate_continuous.py is 4,342 LOC | 114 | Config class (1,046 LOC), WANController (1,901 LOC), main() (548 LOC) -- extraction candidates documented | v1.23 |
| 10 | steering/daemon.py is 2,411 LOC | 114 | SteeringConfig (563 LOC), main() (240 LOC) -- extraction candidates documented | v1.23 |
| 11 | 8 orphaned test fixtures | 112 | sample_config_data, with_controller, integration_output_dir, memory_db, mock_controller, controller, sample_steering_response, sample_autorate_response | v1.23 |
| 12 | 9 over-mocked tests (>4 @patch) | 116 | All in benchmark.py (8) and calibrate.py (1) CLI tool tests -- valid pattern but fragile | backlog |
| 13 | metrics.db files are 0644 (world-readable) | 112 | Performance metrics exposed; directory permissions (0750) provide adequate protection but UMask=0027 now in systemd would fix new files | v1.23 |
| 14 | Log files are 0644 (world-readable) | 112 | Same UMask fix applies; directory 0750 prevents external access | v1.23 |
| 15 | wanctl-check-cake does not support linux-cake transport | 113 | Tool exits with error for linux-cake; tc readback is the correct method but CLI tool could be extended | backlog |

### P3 -- Low (backlog)

| # | Finding | Source Phase | Description | Recommended Milestone |
|---|---------|-------------|-------------|----------------------|
| 16 | metrics.db.corrupt (284 MB) on production VM | 112 | Dead weight in /var/lib/wanctl/ -- safe to delete | v1.23 deployment |
| 17 | autorate_continuous.py.bak (178 KB) on production VM | 112 | Dead backup file in /opt/wanctl/ -- safe to delete | v1.23 deployment |
| 18 | 2 spectrum.yaml.bak files on production VM | 112 | Old config backups in /etc/wanctl/ -- safe to delete after confirming no rollback need | v1.23 deployment |
| 19 | 18 PERF401 manual list comprehension findings suppressed | 112 | Ruff performance optimization suggestions deferred | backlog |
| 20 | 6 fixtures named test_* (naming convention) | 116 | Fixtures starting with `test_` are confusing but functional | backlog |
| 21 | storage.writer imported by 8 modules (high fan-in) | 114 | DEFAULT_DB_PATH import could be extracted to reduce coupling | backlog |
| 22 | autorate_continuous imports 37 wanctl modules | 114 | Expected for orchestrator but signals opportunity for responsibility extraction | v1.23 |
| 23 | ATT qdiscs: 32 MB memlimit significantly oversized | 113 | ATT upload uses 1.6%, ATT download 4.4% -- but harmless (kernel allocates on demand) | backlog |
| 24 | wanctl-nic-tuning.service score 7.5 EXPOSED | 115 | Root oneshot for hardware access; limited further hardening possible | backlog |

### P4 -- Informational (no action needed)

| # | Finding | Source Phase | Description | Notes |
|---|---------|-------------|-------------|-------|
| 25 | Pygments CVE-2026-4539 (low) | 112 | ReDoS in AdlLexer; transitive dev dep only, no fix available | Accepted risk |
| 26 | `systemd` not in pyproject.toml deps | 112 | python3-systemd is apt package, not pip; import wrapped in try/except | Correct behavior |
| 27 | `rich` and `urllib3` as transitive deps | 112 | rich via textual (dashboard), urllib3 via requests -- stable transitive chains | Acceptable |
| 28 | 53 test-only functions flagged by vulture | 112 | Public API surface exercised only by tests; intentionally kept for API completeness | Acceptable |
| 29 | 2 TYPE_CHECKING circular imports | 114 | autorate <-> health_check, steering/daemon <-> steering/health -- standard Python pattern, no runtime cycle | Correct pattern |
| 30 | GIL-dependent health endpoint reads | 114 | 15+ WANController attributes read by health thread without locks; safe under CPython, documented dependency | Acceptable for CPython |
| 31 | IRTT server is single point of failure | 113 | Dallas 104.200.21.31:2112 -- no SLA, no redundancy; fusion falls back to ICMP-only if IRTT unavailable | Known limitation |
| 32 | Spectrum download memory usage 60.9% | 113 | Highest of 4 qdiscs at 19.49 MB / 32 MB; appropriate for 940 Mbit * 100ms BDP | Healthy range |
| 33 | Spectrum upload 21.2% apparent drop rate | 113 | 99.9% are ack-filter drops (TCP ACK thinning); true loss rate 0.074% | Expected behavior |
| 34 | ECN marking low on download direction | 113 | Ingress shaping limits ECN effectiveness; drops dominate -- this is inherent to ingress CAKE | Expected behavior |
| 35 | 16 MEDIUM-risk "should not raise" tests | 116 | Assertion-free but valid defensive pattern; pytest catches unhandled exceptions | Acceptable pattern |
| 36 | secrets file 0640 (not 0600) | 112 | wanctl group needs read access via EnvironmentFile; 0640 is correct | Intentional |
| 37 | Production dry_run=False (differs from code default True) | 113 | Code defaults to safe (True); production explicitly set to live (False) | Intentional |
| 38 | DOCKER.md preserved with deprecation notice | 116 | Historical reference for container-era deployment; not deleted per doc hygiene policy | Intentional |

## Debt by Category

| Category | P0 | P1 | P2 | P3 | P4 | Total |
|----------|----|----|----|----|-----|-------|
| Dependencies | 0 | 1 | 0 | 0 | 3 | 4 |
| Code Quality | 0 | 1 | 6 | 2 | 1 | 10 |
| Network/CAKE | 0 | 0 | 1 | 1 | 4 | 6 |
| Security | 0 | 1 | 2 | 0 | 1 | 4 |
| Testing | 0 | 0 | 2 | 1 | 1 | 4 |
| Documentation | 0 | 0 | 0 | 0 | 1 | 1 |
| Operations | 0 | 1 | 0 | 5 | 3 | 9 |
| **Total** | **0** | **4** | **11** | **9** | **14** | **38** |

## Audit Coverage

| Phase | Focus | Plans | Findings Files | Key Tools Used |
|-------|-------|-------|----------------|----------------|
| 112 | Foundation Scan | 4 | 4 | pip-audit, deptry, vulture, ruff, radon, deadfixtures, systemd-analyze |
| 113 | Network Engineering | 3 | 3 | tc -j qdisc show, MikroTik REST API, DSCP trace, queue depth stats |
| 114 | Code Quality & Safety | 3 | 6 | mypy, radon/mccabe, import graph DFS, thread safety review, SIGUSR1 catalog |
| 115 | Operational Hardening | 3 | 1 | systemd-analyze security, ethtool, pip freeze, Proxmox snapshots |
| 116 | Test & Doc Hygiene | 3 | 1 | AST-based test scanner, pytest, grep, config_validation_utils.py diff |
| **Total** | | **16** | **15** | |

## Recommendations for v1.23

1. **Fix 5 bug-swallowing exception catches (P1-1):** Add debug-level logging to 5 silent `except Exception: pass` blocks in router_client.py, rtt_measurement.py, benchmark.py, and calibrate.py. Estimated effort: 30 minutes.

2. **Deploy requests CVE fix (P1-2):** Update production VM's requests package from 2.32.3 to >=2.33.0 to resolve CVE-2026-25645. Estimated effort: 5 minutes (pip install on VM).

3. **Extract Config classes from daemon files (P2-8/9/10):** Move AutorateConfig (1,046 LOC) and SteeringConfig (563 LOC) into dedicated modules. Reduces the two largest files by 23-24% each. Low risk, mechanical move with import updates. Estimated effort: 2-4 hours.

4. **Clean up production VM dead files (P3-16/17/18):** Delete metrics.db.corrupt (284 MB), autorate_continuous.py.bak, and spectrum.yaml.bak files. Estimated effort: 5 minutes.

5. **Remove 4 likely dead code items (P2-5):** After transport validation, remove `_create_transport()`, `SteeringLogger`, `_ul_last_congested_zone`, and `_last_tuning_ts`. Estimated effort: 1 hour with test verification.
