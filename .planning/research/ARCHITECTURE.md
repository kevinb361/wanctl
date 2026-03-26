# Architecture Research: v1.22 Full System Audit

**Domain:** Audit methodology for production Python dual-WAN controller
**Researched:** 2026-03-26
**Confidence:** HIGH (codebase fully explored, dependency graph mapped, tooling verified)

## System Overview (Audit Baseline)

```
                         wanctl System Architecture
                         ~~~~~~~~~~~~~~~~~~~~~~~~~~

  ┌─────────────────────────────────────────────────────────────────┐
  │                     CLI Tools (offline)                         │
  │  wanctl-check-config  wanctl-check-cake  wanctl-benchmark      │
  │  wanctl-history       wanctl-calibrate   wanctl-dashboard      │
  └─────────────────┬───────────────────────────────┬───────────────┘
                    │ imports shared modules         │
  ┌─────────────────┴───────────────────┐  ┌────────┴──────────────┐
  │  Autorate Daemon (50ms loop)        │  │  Steering Daemon      │
  │  autorate_continuous.py (4,282 LOC) │  │  steering/daemon.py   │
  │  ContinuousAutoRate                 │  │  (2,384 LOC)          │
  │    WANController                    │  │  SteeringDaemon       │
  │    QueueController                  │  │  RouterOSController   │
  │    Config                           │  │  BaselineLoader       │
  │                                     │  │  CakeStatsReader      │
  ├─────────────────────────────────────┤  │  ConfidenceController │
  │  Signal Pipeline                    │  └───────────┬───────────┘
  │  rtt_measurement -> signal_proc ->  │              │
  │  reflector_scorer -> fusion ->      │              │
  │  asymmetry_analyzer                 │              │
  ├─────────────────────────────────────┤              │
  │  Tuning Subsystem                   │              │
  │  tuning/{analyzer,applier,safety}   │              │
  │  strategies/{signal,threshold,adv}  │              │
  └────────────┬────────────────────────┘              │
               │                                       │
  ┌────────────┴───────────────────────────────────────┴───────────┐
  │                    Shared Infrastructure                        │
  │  backends/{base,routeros,linux_cake,linux_cake_adapter}        │
  │  storage/{writer,reader,schema,downsampler,retention,maint}    │
  │  config_base, config_validation_utils, state_manager           │
  │  health_check, metrics, alert_engine, webhook_delivery         │
  │  router_client, routeros_rest, routeros_ssh                    │
  │  signal_utils, systemd_utils, daemon_utils, lock_utils         │
  │  error_handling, retry_utils, logging_utils, path_utils        │
  │  perf_profiler, rate_utils, timeouts, pending_rates            │
  └────────────────────────────────────────────────────────────────┘
               │                              │
  ┌────────────┴──────────┐    ┌──────────────┴───────────────────┐
  │  Linux CAKE (tc)      │    │  MikroTik Router (REST/SSH)      │
  │  LinuxCakeBackend     │    │  RouterOSBackend                 │
  │  (cake-shaper VM)     │    │  FailoverRouterClient            │
  └───────────────────────┘    └──────────────────────────────────┘
```

### Module Inventory by Layer

| Layer | Module Count | Total LOC | Largest Module |
|-------|-------------|-----------|----------------|
| Daemon cores | 2 | 6,666 | autorate_continuous.py (4,282) |
| Signal pipeline | 5 | 1,326 | signal_processing.py (312) |
| Tuning subsystem | 8 | 1,540 | strategies/signal_processing.py (387) |
| Steering subpackage | 5 | 3,615 | steering/daemon.py (2,384) |
| Backend abstraction | 4 | 1,050 | linux_cake.py (457) |
| Storage subsystem | 7 | 1,505 | reader.py (430) |
| Router communication | 5 | 2,217 | routeros_rest.py (781) |
| Config/validation | 3 | 2,366 | check_config.py (1,484) |
| CLI tools | 4 | 3,613 | check_config.py (1,484) |
| Shared utilities | 12 | 3,424 | retry_utils.py (353) |
| Dashboard (Textual) | 8 | 1,264 | app.py (418) |
| **Total** | **~80 .py files** | **~29,848** | |

### Dependency Heat Map (Import Count)

Modules ordered by how many OTHER modules depend on them (most-imported first):

| Module | Depended On By | Role |
|--------|---------------|------|
| `config_base` | autorate, steering, cake_params, check_config, config_validation | Foundation config class |
| `storage.writer` | alert_engine, health_check, history, webhook, benchmark, storage/* | Metrics persistence singleton |
| `tuning.models` | analyzer, applier, safety, all 4 strategies, autorate | Tuning data structures |
| `rtt_measurement` | autorate, steering, calibrate, benchmark, reflector_scorer | RTT probing |
| `signal_utils` | autorate, steering, calibrate | Signal handling |
| `perf_profiler` | autorate, steering, health_check | Cycle timing |
| `lock_utils` | autorate, steering, check_cake, benchmark | Lock file management |
| `retry_utils` | routeros_rest, routeros_ssh, steering | Retry with backoff |
| `path_utils` | logging_utils, state_utils | Path resolution |
| `backends.base` | routeros, linux_cake | Backend ABC |

**Key coupling observation:** `autorate_continuous.py` imports from 38 internal modules -- it is the single most coupled module. `steering/daemon.py` imports from ~25 internal modules. Both are "god modules" that orchestrate everything.

## Audit Methodology: Recommended Approach

### Strategy: Bottom-Up by Dependency Layer

Audit from the leaves of the dependency graph inward toward the daemon cores. This ensures:

1. Foundation modules are verified clean before auditing code that depends on them
2. Findings in shared modules reveal impact scope immediately (anything importing them is affected)
3. The hardest, most coupled code (daemon cores) is audited last, when all its dependencies are understood

### Audit Order (6 Phases)

```
Phase 1: Foundation Layer (zero or minimal internal deps)
         path_utils, timeouts, pending_rates, daemon_utils,
         systemd_utils, signal_utils, logging_utils, lock_utils,
         error_handling, state_utils
         ~10 modules, ~1,800 LOC

Phase 2: Data Layer (depends only on foundation)
         config_base, config_validation_utils, state_manager,
         storage/{schema,writer,reader,retention,downsampler,
                  config_snapshot,maintenance}
         backends/base
         ~11 modules, ~3,200 LOC

Phase 3: Communication Layer (depends on foundation + data)
         routeros_rest, routeros_ssh, router_client,
         router_command_utils, router_connectivity, retry_utils,
         backends/{routeros,linux_cake,linux_cake_adapter}
         ~8 modules, ~3,100 LOC

Phase 4: Signal & Measurement Layer (depends on foundation + data)
         rtt_measurement, irtt_measurement, irtt_thread,
         signal_processing, reflector_scorer, asymmetry_analyzer,
         baseline_rtt_manager, rate_utils, cake_params
         ~9 modules, ~2,600 LOC

Phase 5: Subsystems (depends on all lower layers)
         tuning/{models,analyzer,applier,safety},
         tuning/strategies/{base,signal,threshold,advanced},
         steering/{congestion_assessment,cake_stats,
                   steering_confidence,health},
         alert_engine, webhook_delivery, metrics, health_check,
         perf_profiler, steering_logger, wan_controller_state
         ~17 modules, ~5,400 LOC

Phase 6: Daemon Cores + CLI + Dashboard
         autorate_continuous.py, steering/daemon.py,
         check_config, check_cake, calibrate, benchmark, history,
         dashboard/{app,config,poller,widgets/*}
         ~18 modules, ~13,700 LOC
```

### Why This Order (Not Hot-Path First)

Hot-path-first sounds appealing ("audit the 50ms loop first") but is wrong for this codebase because:

1. **autorate_continuous.py (4,282 LOC) imports 38 modules** -- auditing it without understanding its dependencies means you cannot distinguish "bug in autorate" from "bug inherited from config_base"
2. **Shared module bugs have amplified impact** -- a flaw in `state_utils.atomic_write_json()` affects both daemons, all CLI tools, and state persistence. Finding it in Phase 1 immediately scopes the blast radius.
3. **Foundation modules are fast to audit** -- Phase 1 is ~1,800 LOC of utility code, completable quickly, building momentum and establishing patterns to watch for in later phases.

### Cross-Cutting Concerns (Audit Throughout)

These span all phases and should be tracked as running observations:

| Concern | What to Look For | Where It Appears |
|---------|-----------------|------------------|
| Error swallowing | `except: pass` or `except Exception` without logging | All modules |
| Type safety gaps | `Any` return types, `# type: ignore` without explanation | All modules |
| Dead code | Unreachable branches, unused imports, vestigial functions | All modules |
| Test coverage gaps | Modules/functions with <90% branch coverage | Cross-reference with coverage report |
| Hardcoded values | Magic numbers that should be config parameters | Daemon cores, signal pipeline |
| Logging hygiene | Missing context in error logs, excessive DEBUG noise | All modules |

## Data Flow: The 50ms Autorate Cycle

```
ContinuousAutoRate.run_cycle()
    |
    |-- WANController.measure_rtt()
    |     |-- RTTMeasurement.measure() [icmplib raw ICMP]
    |     |-- SignalProcessor.process() [Hampel -> EWMA]
    |     |-- ReflectorScorer.update()
    |     |-- WANController._compute_fused_rtt() [ICMP + IRTT fusion]
    |     '-- IRTTThread.get_latest() [background UDP RTT]
    |
    |-- WANController.update_ewma(measured_rtt)
    |     |-- BaselineRTTManager._update_baseline_if_idle()
    |     '-- EWMA delta calculation
    |
    |-- QueueController.adjust_4state(delta)
    |     |-- GREEN/YELLOW/SOFT_RED/RED state machine
    |     |-- rate = enforce_rate_bounds(new_rate)
    |     '-- PendingRateChange tracking
    |
    |-- WANController.apply_rate_changes_if_needed(dl_rate, ul_rate)
    |     |-- RateLimiter.allow_change()
    |     |-- RouterOS/LinuxCakeBackend.set_bandwidth()
    |     '-- Flash wear protection (skip if unchanged)
    |
    |-- WANController.save_state() [periodic, dirty-tracking]
    |-- WANController._record_profiling() [PerfTimer subsystem]
    |-- MetricsWriter.record() [SQLite per-cycle]
    |-- AlertEngine checks (congestion, loss, connectivity, drift, flapping)
    |-- TuningAnalyzer (hourly, 4-layer rotation)
    '-- systemd_utils.notify_watchdog()
```

**Hot path audit targets** (executed every 50ms = 20 times/second):
- `rtt_measurement.py` -- ICMP socket management
- `signal_processing.py` -- Hampel filter, EWMA
- `autorate_continuous.py::QueueController.adjust_4state()` -- state machine
- `backends/linux_cake.py::set_bandwidth()` -- tc subprocess call
- `rate_utils.py` -- bounds enforcement
- `perf_profiler.py` -- timing overhead

## Steering Daemon Cycle (2s loop)

```
SteeringDaemon.run_cycle()
    |
    |-- measure_current_rtt() [same RTTMeasurement as autorate]
    |-- update_baseline_rtt()
    |-- calculate_delta()
    |-- collect_cake_stats() [CakeStatsReader -> LinuxCakeBackend]
    |-- update_ewma_smoothing()
    |
    |-- update_state_machine(signals: CongestionSignals)
    |     |-- assess_congestion_state() [3-state: GREEN/YELLOW/RED]
    |     '-- _update_state_machine_unified()
    |           |-- _handle_good_state() or _handle_degraded_state()
    |           '-- _apply_confidence_decision()
    |                 '-- ConfidenceController.evaluate()
    |
    |-- execute_steering_transition()
    |     |-- RouterOSController.enable_steering() / disable_steering()
    |     '-- [REST API to MikroTik -- mangle rule enable/disable]
    |
    |-- State persistence, metrics, alerting, watchdog
    '-- BaselineLoader reads autorate state file (cross-daemon IPC)
```

## Component Boundaries and Integration Points

### Internal Boundaries

| Boundary | Communication | Audit Concern |
|----------|---------------|---------------|
| autorate <-> steering | State file on disk (JSON) | Stale read, schema drift, race conditions |
| autorate <-> storage | MetricsWriter singleton (SQLite) | Thread safety, WAL mode, connection handling |
| autorate <-> backends | set_bandwidth()/get_stats() | Error propagation, subprocess timeout |
| autorate <-> tuning | _apply_tuning_to_controller() hourly | Parameter bounds, revert safety |
| steering <-> router | REST/SSH mangle rule toggle | Idempotency, error recovery |
| autorate <-> IRTT | IRTTThread (background, lock-free cache) | Thread lifecycle, stale data |
| health_check <-> autorate | TYPE_CHECKING import (avoids circular) | Attribute access fragility |
| steering/health <-> daemon | TYPE_CHECKING import | Same concern |

### External Boundaries

| External System | Integration | Audit Focus |
|----------------|-------------|-------------|
| MikroTik Router | REST API (routeros_rest.py) + SSH (routeros_ssh.py) | Timeout handling, password management, error codes |
| Linux CAKE (tc) | subprocess via LinuxCakeBackend | Command injection safety, parse errors, tc failures |
| IRTT Server (Dallas) | UDP via subprocess `irtt client` | Process lifecycle, timeout, parse JSON |
| Discord Webhooks | HTTPS POST (requests library) | Rate limiting, retry backoff, error isolation |
| systemd | notify_watchdog() via socket | Watchdog timeout vs cycle budget |
| SQLite (metrics.db) | MetricsWriter singleton, WAL mode | Corruption recovery, disk full, concurrent access |
| Filesystem | state files, lock files, logs | Permissions, atomic writes, tmpfs race |

## Architectural Patterns to Audit

### Pattern 1: Singleton MetricsWriter

**What:** `MetricsWriter` in `storage/writer.py` uses a module-level singleton. Tests must call `_reset_instance()`.

**Audit concern:** Verify singleton is properly thread-safe. Check that all callers get the same instance. Confirm `_reset_instance()` is only called in tests, never in production code.

### Pattern 2: TYPE_CHECKING Circular Import Avoidance

**What:** `health_check.py` imports `ContinuousAutoRate` only under `TYPE_CHECKING`. At runtime, the controller is passed as `Any`.

**Audit concern:** No compile-time type checking on the actual object. Attribute access on the controller could silently break if method signatures change. Same pattern exists in `steering/health.py`.

### Pattern 3: Flash Wear Protection (Write Deduplication)

**What:** `last_applied_dl_rate` / `last_applied_ul_rate` tracking prevents sending unchanged values to the router/CAKE.

**Audit concern:** Verify all paths through rate application check these guards. Confirm reset behavior on daemon restart.

### Pattern 4: State File Cross-Daemon IPC

**What:** Autorate writes `{wan}_state.json` with congestion zone. Steering reads it via `BaselineLoader`. No locking -- autorate writes atomically, steering tolerates stale reads.

**Audit concern:** Verify atomic_write_json uses temp+fsync+rename correctly. Check staleness timeout (5s). Confirm schema compatibility between writer (autorate) and reader (steering).

### Pattern 5: Daemon Duplication

**What:** Both `autorate_continuous.py` and `steering/daemon.py` contain similar patterns: argparse setup, lock acquisition, health server start, signal handling, main loop with watchdog, cleanup.

**Audit concern:** `daemon_utils.py` partially consolidated this in v1.10, but significant duplication remains. The `main()` functions are ~130 and ~120 lines respectively with parallel structure. Not a bug, but a maintenance burden.

## Anti-Patterns to Flag

### Anti-Pattern 1: God Module (autorate_continuous.py)

**What:** 4,282 lines, 4 classes, ~8 top-level functions, imports from 38 internal modules. Houses Config (960 lines), RouterOS (50 lines), QueueController (240 lines), WANController (1,800 lines), ContinuousAutoRate (120 lines), plus main() and helpers.

**Why problematic:** Config alone is 960 lines of schema validation that could be its own module. WANController at 1,800 lines handles measurement, fusion, tuning, alerting, state persistence, and profiling -- at least 4 distinct responsibilities.

**Audit action:** Flag as complexity hotspot. Do NOT refactor in audit -- document recommendations only. Splitting Config into `autorate_config.py` and extracting alert-checking methods from WANController are the highest-value changes.

### Anti-Pattern 2: RouterOS Class Bypasses Backend Abstraction

**What:** `autorate_continuous.py` contains a `RouterOS` class (line 1204) that wraps `FailoverRouterClient` directly. The `RouterBackend` ABC in `backends/base.py` was created for abstraction, and `LinuxCakeBackend` properly implements it. But the autorate hot path does NOT go through `RouterBackend` when using RouterOS transport -- it uses its own `RouterOS` class.

**Why problematic:** Two parallel abstractions for the same operation. The `LinuxCakeAdapter` bridges this gap for linux-cake transport, but the RouterOS path is outside the abstraction.

**Audit action:** Document the divergence. It works correctly but creates confusion about where router interaction lives.

### Anti-Pattern 3: Deployment Script Sprawl

**What:** `scripts/` contains 20+ shell scripts, many dating from container-era deployment (pre-v1.21). An `.obsolete/` subdirectory exists but some non-obsolete scripts may also be stale.

**Audit action:** Inventory every script, check last meaningful use, archive anything not needed for cake-shaper VM deployment.

## Prioritization Framework for Findings

### Severity Classification

| Severity | Definition | Action Timing | Example |
|----------|-----------|---------------|---------|
| **P0 - Production Risk** | Could cause daemon crash, data loss, or network disruption | Fix immediately | Unhandled exception in hot loop, SQLite corruption path |
| **P1 - Correctness** | Wrong behavior under edge conditions | Fix in audit milestone | Stale baseline not detected, rate bounds bypass |
| **P2 - Security** | Hardening gap, credential exposure risk | Fix in audit milestone | systemd directives missing, log scrubbing gap |
| **P3 - Maintainability** | Dead code, excessive complexity, poor naming | Fix if low risk | Unused imports, CC > 15 functions, dead branches |
| **P4 - Documentation** | Stale docs, missing docstrings, wrong comments | Fix as encountered | Outdated architecture doc, wrong version refs |

### Cross-Module Finding Template

When a finding spans multiple modules, document it as:

```
FINDING: [Short description]
SEVERITY: P0/P1/P2/P3/P4
MODULES: [list of affected files]
ROOT CAUSE: [which module is the source]
IMPACT: [what breaks or degrades]
FIX: [concrete recommendation]
TEST: [how to verify the fix]
```

## Audit Tooling

### Automated Analysis (Run Before Manual Audit)

| Tool | What It Finds | Command |
|------|--------------|---------|
| `vulture` | Dead code (functions, imports, variables) | `vulture src/wanctl/ --min-confidence 80` |
| `radon cc` | Cyclomatic complexity per function | `radon cc src/wanctl/ -s -n C` (show grade C and worse) |
| `radon mi` | Maintainability index per file | `radon mi src/wanctl/ -s -n B` |
| `ruff check` | Lint violations (already in CI) | `.venv/bin/ruff check src/ --select ALL` (temporary, broader ruleset) |
| `mypy --strict` | Type safety gaps (stricter than CI) | `.venv/bin/mypy src/wanctl/ --strict` (compare to current) |
| `bandit` | Security issues (already in CI) | `.venv/bin/bandit -r src/ -c pyproject.toml` |
| `pytest --cov` | Coverage gaps (branch-level) | `.venv/bin/pytest --cov=src --cov-branch --cov-report=html` |
| `systemd-analyze security` | Service hardening score | `systemd-analyze security wanctl@spectrum` |
| `tc -s -j qdisc show` | Live CAKE parameter verification | On cake-shaper VM |
| `pip-audit` | Dependency CVEs (already in CI) | `.venv/bin/pip-audit` |

### Manual Audit Focus Areas

Beyond what tools catch, human review should focus on:

1. **Algorithmic correctness** in the state machine (QueueController.adjust_4state, SteeringDaemon._update_state_machine_unified) -- tools cannot verify control logic
2. **Timing assumptions** -- 50ms cycle budget, watchdog timeout margins, EWMA time constant preservation
3. **Error recovery paths** -- what happens when the router is unreachable for 60 seconds? When SQLite is corrupt? When /var/lib/wanctl runs out of space?
4. **Configuration interaction** -- do all config parameters actually affect behavior? Are any ignored? Do defaults match documentation?
5. **CAKE parameter correctness** -- diffserv4 tin mapping, ack-filter, overhead values for DOCSIS vs DSL

## Scaling Considerations (Not Applicable)

This is a single-host, single-user production system. There are no multi-tenant or horizontal scaling concerns. The relevant "scaling" dimensions are:

| Dimension | Current | Audit Concern |
|-----------|---------|---------------|
| Cycle frequency | 50ms (20Hz) | CPU budget per cycle (30-40ms used of 50ms available) |
| SQLite growth | ~months of metrics | Retention/downsampling working? Disk growth rate? |
| Module count | 80 files, 29K LOC | Comprehension ceiling for one developer |
| Config complexity | ~200 YAML parameters across 3 configs | Validation coverage, unused parameters |

## Production Deployment Context

### cake-shaper VM (v1.21+)

```
Host: VM 206 on Proxmox (odin)
OS: Debian 12
NICs: 4x PCIe passthrough (2x i210, 2x i350)
Bridges: br-spectrum (nic0+nic1), br-att (nic2+nic3)
Services: wanctl@spectrum, wanctl@att, wanctl-steering
User: wanctl (dedicated service account)
Config: /etc/wanctl/{spectrum,att,steering}.yaml
State: /var/lib/wanctl/
Logs: /var/log/wanctl/ + journald
Secrets: /etc/wanctl/secrets (EnvironmentFile)
```

### Audit Points for Deployment

| Item | What to Check |
|------|--------------|
| systemd unit files | Security directives completeness (compare to `systemd-analyze security` output) |
| File permissions | /etc/wanctl/secrets readable only by wanctl user? |
| NIC tuning | rx-udp-gro-forwarding persistence across reboot |
| Log rotation | RotatingFileHandler (10MB/3 backups) -- is this sufficient? |
| Bridge configuration | systemd-networkd managing bridges, NOT CAKE qdiscs |
| CAKE init | tc qdisc replace on service start (idempotent) |
| CAKE runtime | tc qdisc change (lossless rate adjustment) |

## Sources

- Codebase analysis: full import graph extraction via AST parsing of all 80 modules
- Module line counts: `wc -l` across src/wanctl/
- [Radon documentation: cyclomatic complexity metrics](https://radon.readthedocs.io/en/latest/intro.html)
- [Vulture: dead Python code detection](https://github.com/jendrikseipp/vulture)
- [import-linter: architecture enforcement](https://import-linter.readthedocs.io/)
- [systemd service hardening guide](https://linux-audit.com/systemd/how-to-harden-a-systemd-service-unit/)
- [tc-cake(8) man page](https://man7.org/linux/man-pages/man8/tc-cake.8.html)
- [Python code quality tools beyond linting](https://dev.to/ldrscke/python-code-quality-tools-beyond-linting-42d8)

---
*Architecture research for: wanctl v1.22 Full System Audit*
*Researched: 2026-03-26*
