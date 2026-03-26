# Pitfalls Research: v1.22 Full System Audit

**Domain:** Auditing and refactoring a production Python network controller after 21 milestones of rapid development
**Researched:** 2026-03-26
**Confidence:** HIGH (grounded in direct codebase analysis of 28K+ LOC, 80+ source files, 3,700+ tests, and production deployment knowledge across 21 milestones)

## Critical Pitfalls

### Pitfall 1: Removing "Dead Code" That Is Actually a Backend-Specific Path

**What goes wrong:**
The auditor identifies what appears to be duplicated or dead router control code and removes it. The system breaks for one deployment mode (linux-cake vs RouterOS) while appearing to work in the other. Since production currently runs `linux-cake` transport, RouterOS code paths look "unused" but are required for the MikroTik steering daemon and for future fallback.

**Why it happens:**
wanctl has evolved from a single RouterOS-only system to a dual-backend architecture. The evolution left deliberate parallel code paths:

- `autorate_continuous.py` line 1204: `class RouterOS` -- the original RouterOS interface using `get_router_client_with_failover()` and batched queue tree commands. This is NOT redundant with `backends/routeros.py`. The `RouterOS` class is the autorate daemon's transport; `RouterOSBackend` is the abstract backend implementation.
- `autorate_continuous.py` line 3473: conditional `LinuxCakeAdapter` import -- runtime backend selection means only one branch executes per deployment.
- `steering/daemon.py` line 721: `RouterOSController` -- the steering daemon's MikroTik mangle rule controller. This looks redundant with `router_client.py` but serves a completely different purpose (toggling firewall rules, not setting queue limits).
- `routeros_rest.py` and `routeros_ssh.py` -- both are live code used by `router_client.py`'s failover system, even though only REST is typically active.

**Why it happens:**
Static analysis tools (vulture, deadcode, pyflakes) flag code that is only reachable through runtime configuration as "unused." A human auditor sees `RouterOS`, `RouterOSBackend`, `RouterOSREST`, `RouterOSSSH`, and `RouterOSController` -- five classes with similar names -- and concludes there is massive duplication. In reality each serves a distinct purpose in a specific deployment context.

**How to avoid:**
1. Before marking any router/backend code as dead, trace all call paths from BOTH entry points: `wanctl` (autorate_continuous.py:main) AND `wanctl-steering` (steering/daemon.py:main).
2. Check `pyproject.toml` `[project.scripts]` for all 8 entry points -- each may exercise different code paths.
3. Test with BOTH `router_transport: "rest"` AND `router_transport: "linux-cake"` configs to verify reachability.
4. The `LinuxCakeAdapter` exists specifically because autorate's `WANController` calls `router.set_limits(wan, down_bps, up_bps)` -- a different interface from the abstract `RouterBackend.set_bandwidth(queue, rate_bps)`. The adapter bridges these. Removing it breaks linux-cake mode silently.

**Warning signs:**
- Static analysis tool reports `RouterOS` class as unused
- Import graph shows `routeros_ssh.py` as unreferenced (it is referenced via lazy import in `router_client.py`)
- `LinuxCakeAdapter` appears to have no direct callers (it is imported conditionally at runtime in `autorate_continuous.py` line 3474)

**Phase to address:** Any dead code analysis phase MUST cross-reference against all 8 CLI entry points and both transport modes before flagging removals.

---

### Pitfall 2: Refactoring the SIGUSR1 Reload Chain and Breaking Hot-Reload

**What goes wrong:**
The auditor sees multiple `_reload_*_config()` methods scattered across `autorate_continuous.py` (lines 2507, 2568) and `steering/daemon.py` (lines 1091, 1128, 1174) and consolidates them into a single generic reload method. The refactored version misses one reload target (fusion config, tuning config, webhook URL, dry_run flag, or wan_state.enabled), causing that parameter to no longer respond to SIGUSR1. The operator sends `kill -USR1` to change a setting and nothing happens -- a silent failure with no error log.

**Why it happens:**
The SIGUSR1 chain has grown incrementally across milestones v1.11 through v1.20:
- v1.11: `wan_state.enabled` reload
- v1.13: `dry_run` flag reload
- v1.15: `webhook_url` reload
- v1.19: fusion config reload
- v1.20: tuning config reload

Each reload method re-reads a specific YAML section and updates a specific runtime attribute. The chain is coordinated through `signal_utils.py`'s thread-safe `_reload_event` (a `threading.Event`), and the actual reload methods are called from the main event loop (autorate line 4169-4176, steering daemon's equivalent). Breaking any link in this chain silently disables that hot-reload capability.

**How to avoid:**
1. Document the complete SIGUSR1 reload chain before touching it. There are currently 5 distinct reload targets across 2 daemons.
2. If consolidating, ensure the consolidated method calls ALL existing reload targets.
3. Add a test that sends SIGUSR1 and verifies each parameter actually changes -- currently, individual reload methods are tested but the full chain from signal to runtime change may not have E2E coverage.
4. The `threading.Event` pattern in `signal_utils.py` is READ-ONLY in CLAUDE.md for good reason -- it is the thread-safe coordination mechanism between signal handlers (which run in the main thread) and the event loop.

**Warning signs:**
- Reload methods have no callers in static analysis (they are called via the generic `_reload_event.is_set()` check in the event loop)
- The `_reload_signal_handler` in `signal_utils.py` looks like it does nothing (it just sets an event flag)
- Multiple `_reload_*` methods with similar patterns look "consolidatable"

**Phase to address:** Signal handling audit phase must catalog the full SIGUSR1 chain before any refactoring. Integration test coverage for the full chain should be added before changes.

---

### Pitfall 3: Breaking the Inter-Process State File Contract

**What goes wrong:**
The auditor "cleans up" the state file schema -- renaming fields, removing "unused" fields like `congestion.dl_state`/`congestion.ul_state`, or changing the atomic write mechanism. The autorate daemon and steering daemon can no longer communicate. Steering loses WAN congestion awareness, makes bad decisions, or crashes reading the state file.

**Why it happens:**
wanctl has TWO daemons that communicate via the filesystem:
- `wanctl@spectrum` writes `/var/lib/wanctl/spectrum_state.json` every cycle (50ms)
- `wanctl-steering` reads it to get WAN congestion zones for steering decisions

The state file is a contract between processes. The `congestion` field was added in v1.11 with backward compatibility (unknown keys ignored, stale zone defaults to GREEN). An auditor examining only the autorate code might see `congestion.dl_state`/`congestion.ul_state` written but never read internally and conclude it is dead -- not realizing the steering daemon in a completely separate process reads it.

Additionally:
- `wan_controller_state.py` deliberately excludes `congestion` from dirty tracking (line 32) to avoid write amplification. This looks like a bug ("why is congestion not tracked?") but it is intentional -- congestion zone changes every cycle and should not trigger a full state write.
- `atomic_write_json()` in `state_utils.py` uses temp+fsync+rename. Replacing this with a simple `json.dump()` causes data corruption under 20Hz write frequency.

**How to avoid:**
1. Map ALL consumers of each state file before modifying its schema. Use `grep -r "state.json\|state_file\|safe_json_load" src/`.
2. The `congestion` exclusion from dirty tracking is documented in `wan_controller_state.py` line 32 -- read the comment before "fixing" it.
3. State file changes MUST be tested with both daemons running simultaneously (integration test).
4. The atomic write pattern (temp file + fsync + rename) is a POSIX safety guarantee for 20Hz concurrent read/write. Never simplify it.

**Warning signs:**
- Fields in state JSON that appear to be written but never read within the same file
- Dirty tracking exclusion that looks like a bug
- `atomic_write_json` that looks over-engineered for "just writing JSON"

**Phase to address:** State management audit must map the complete producer-consumer topology before any schema changes. Integration tests exercising both daemons should exist before modifications.

---

### Pitfall 4: "Cleaning Up" Flash Wear Protection as Unnecessary on Linux

**What goes wrong:**
The auditor notices `last_applied_dl_rate`/`last_applied_ul_rate` tracking in `autorate_continuous.py` (lines 1661-1662, 2293, 2336-2337) and state persistence in `wan_controller_state.py`. Since the system now runs on a Linux VM (not MikroTik NAND flash), the auditor removes the "flash wear protection" as obsolete. This causes the controller to send `tc qdisc change` commands to the kernel on EVERY 50ms cycle (20 calls/second) even when the rate has not changed.

**Why it happens:**
The variable names and comments reference "flash wear" from the MikroTik era. On Linux, the protection serves a different but equally critical purpose: avoiding 20Hz unnecessary kernel syscalls and netlink round-trips. Each `tc qdisc change` call takes ~1-3ms even when the rate does not change. Sending it every cycle would consume 20-60ms per second of CPU time and generate unnecessary netlink traffic. At 50ms cycle budget, this could push cycle utilization above 100%.

**How to avoid:**
1. Rename the concept from "flash wear protection" to "no-op write suppression" or "rate change deduplication" during the audit -- but do NOT remove the logic.
2. The `last_applied_*` tracking in `autorate_continuous.py` and the dirty tracking in `wan_controller_state.py` serve the same purpose from different angles -- both must stay.
3. Add a comment explaining the linux-cake rationale alongside the existing MikroTik rationale.

**Warning signs:**
- Comments mentioning "flash" or "NAND" on a system that runs on a VM with SSD storage
- `last_applied_dl_rate == dl_rate` guard that looks like premature optimization
- State persistence code that seems redundant with the backend's own state

**Phase to address:** Code cleanup phase should update comments and documentation to reflect the Linux rationale, not remove the mechanisms.

---

### Pitfall 5: Removing Container-Era Code That Supports Multi-Deployment

**What goes wrong:**
The auditor identifies container-specific scripts (`container_install_spectrum.sh`, `container_install_att.sh`, `container_network_audit.py`) and Dockerfile artifacts as dead code from the pre-v1.21 era and deletes them. The system loses the ability to redeploy in container mode as a fallback, and reference material for future deployments is destroyed.

**Why it happens:**
wanctl migrated from LXC containers to a Proxmox VM in v1.21. The container scripts, Dockerfiles, and container-specific deployment code are no longer used in production. However:
- Container deployment is still a valid fallback if the VM architecture fails
- `scripts/container_network_audit.py` contains measurement methodology that applies to any deployment
- The `Dockerfile` documents the Python dependency chain and system package requirements
- Other users might deploy wanctl in containers (open source consideration)

**How to avoid:**
1. Archive container-era code (move to `.archive/` with a README explaining why it is preserved) rather than deleting it.
2. `.archive/` already exists with `systemd-legacy/` and `configs-production/` -- follow the established pattern.
3. Scripts in `scripts/` that reference containers should be moved to `.archive/container-scripts/` with clear labels.
4. The existing `.obsolete/` pattern in `scripts/` provides precedent for this approach.

**Warning signs:**
- Scripts referencing "container" or "LXC" that appear unused
- Dockerfile that does not match the current deployment model
- Install scripts for hosts that no longer exist

**Phase to address:** Infrastructure audit phase should archive (not delete) container-era artifacts. A manifest file in `.archive/` documenting what each archived item is and why it is preserved.

---

### Pitfall 6: Improving the 4,282-Line autorate_continuous.py God Object

**What goes wrong:**
The auditor correctly identifies `autorate_continuous.py` (4,282 lines) as the largest file and attempts to refactor it by extracting classes into separate modules. The extraction breaks subtle initialization ordering, shared state between methods, or the carefully sequenced event loop. Production crashes on the next cycle.

**Why it happens:**
`autorate_continuous.py` contains:
- `Config` class (config loading and validation, ~200 lines)
- `RouterOS` class (MikroTik transport, ~50 lines)
- `ContinuousAutoRate` class (daemon orchestration, ~300 lines)
- `WANController` class (core control loop, ~2,500 lines)
- Signal handling, startup/shutdown, maintenance scheduling

Many of these classes share state through constructor injection and method calls that assume co-location. For example:
- `WANController` directly accesses `config` attributes set during `ContinuousAutoRate.__init__`
- The `_reload_fusion_config()` and `_reload_tuning_config()` methods are called from `ContinuousAutoRate.run_cycle()` which iterates `self.wan_controllers`
- The singleton `MetricsWriter` is initialized once and assumed available everywhere

Extracting `WANController` to its own module is the most tempting refactoring target and also the most dangerous. It requires moving all of: the state machine logic, the EWMA calculations, the signal processing chain, the tuning integration, the metrics recording, the baseline management, the fusion config, and the rate application -- all of which have cross-references.

**How to avoid:**
1. Do NOT attempt to refactor `autorate_continuous.py` during the audit. Instead, document the current structure and annotate which sections could be extracted in a FUTURE milestone.
2. If extraction is attempted, it must be done one class at a time with the full test suite (3,700+ tests) passing after each extraction.
3. The CLAUDE.md explicitly says "Never refactor core logic, algorithms, thresholds, or timing without approval" -- this applies to structural refactoring too.
4. Any extraction must preserve the exact same initialization order and test with a real 50ms cycle timer to detect timing regressions.

**Warning signs:**
- "Just move this class to its own file" proposals for WANController
- Refactoring that changes import order in a way that affects singleton initialization
- Extraction that splits the `run_cycle()` hot path across module boundaries

**Phase to address:** Code complexity audit should document the structure of autorate_continuous.py and steering/daemon.py (2,384 lines) as known complexity, not attempt to fix it. Extraction planning belongs in a future milestone with dedicated testing phases.

---

## Moderate Pitfalls

### Pitfall 7: Tightening Type Annotations That Break MagicMock Test Patterns

**What goes wrong:**
The auditor adds strict type annotations or changes `isinstance()` guards to satisfy mypy, and tests start failing because MagicMock objects no longer pass through the guards. Production code works fine, but the test suite loses coverage because mocked paths are blocked by type checks that production objects would pass.

**Why it happens:**
wanctl has an established pattern documented in MEMORY.md: `if value and isinstance(value, str)` before `Path(value)` for mock safety. This pattern protects against MagicMock objects being passed to `Path()` constructors during testing. Adding `type: ignore` comments or changing these guards to strict typing breaks the test safety net.

Similarly, `isinstance(stats, dict)` guards protect against MagicMock objects in `_build_cycle_budget()`. These look like unnecessary runtime type checks but they are actually test infrastructure safety mechanisms.

**How to avoid:**
1. Search for the pattern `isinstance.*MagicMock\|isinstance.*str.*Path\|isinstance.*dict` before adding type annotations that would change guard behavior.
2. Run the full test suite after ANY type annotation changes -- not just mypy.
3. The `MetricsWriter._reset_instance()` method exists solely for testing. Do not remove it as "dead code."

**Warning signs:**
- `isinstance()` checks that look redundant for production code
- `_reset_instance()` methods with no production callers
- Type guards that seem to duplicate what mypy would catch

**Phase to address:** Type safety audit must run the full test suite and verify test count does not decrease after changes.

---

### Pitfall 8: Consolidating "Duplicate" State Managers

**What goes wrong:**
The auditor finds `StateManager` in `state_manager.py`, `SteeringStateManager` in the same file, and `WANControllerState` in `wan_controller_state.py` and concludes these should be merged. The merge breaks because these serve fundamentally different processes with different schemas, different write frequencies, and different error recovery strategies.

**Why it happens:**
- `StateManager` (base class): Generic state persistence with schema validation, corruption recovery, and backup
- `SteeringStateManager` (subclass): Steering daemon state with confidence scores, timer states, and WAN zone tracking. Written every 5 seconds (steering cycle).
- `WANControllerState`: Autorate daemon state with EWMA values, streak counters, and last-applied rates. Written every 50ms (autorate cycle) with dirty tracking to suppress no-op writes.

These look similar but have critical differences:
- WANControllerState has dirty tracking; SteeringStateManager does not need it (5s vs 50ms write frequency)
- SteeringStateManager has legacy schema migration; WANControllerState does not
- They operate in different processes with different filesystem paths

**How to avoid:**
1. Document the intentional separation before suggesting consolidation.
2. If consolidation is desired, it belongs in a future milestone with dedicated testing, not in an audit.
3. The different write frequencies alone justify separate implementations.

**Warning signs:**
- Three classes with "State" in the name that look similar
- `atomic_write_json` called from multiple places
- Base class that looks underutilized

**Phase to address:** Architecture documentation phase should annotate the state management hierarchy, not refactor it.

---

### Pitfall 9: Deleting "Obsolete" Deprecation Code After Config Migration

**What goes wrong:**
The auditor finds `deprecate_param()` in `config_validation_utils.py` with 8 legacy parameter translations and decides these are no longer needed because "all production configs have been migrated." The deprecation warnings are removed. A future config restore from backup or a new deployment using documented examples (which reference old parameter names) silently uses wrong defaults instead of warning and translating.

**Why it happens:**
v1.13 migrated away from legacy config parameters but kept `deprecate_param()` as a compatibility bridge. The 8 translated parameters include steering config names, EWMA alpha parameters, and timing intervals. Since production configs are already using modern names, the deprecation code never triggers in normal operation and looks dead.

**How to avoid:**
1. Deprecation bridges should be kept for at least 2 major versions (we are at v1.20, these were introduced in v1.13).
2. If removing, first verify that ALL documentation, example configs, and backup configs use modern parameter names.
3. The `check_config.py` validation tool has a "deprecated params" check category (line 18) that depends on this code.
4. Consider adding a "removed in v1.X" timeline rather than silent removal.

**Warning signs:**
- `deprecate_param()` calls that never trigger in production logs
- Config validation code that references parameter names not in current configs
- `check_config.py` validation categories that seem unused

**Phase to address:** Config audit phase should verify all documentation and example configs are current, then add removal timeline comments to deprecation code rather than deleting it.

---

### Pitfall 10: Upgrading Dependencies That Break Subtle Behavior

**What goes wrong:**
The auditor runs `pip-audit` or `uv pip compile`, finds outdated packages, and upgrades them. A dependency behavior change causes subtle production failures:
- `icmplib` update changes the default timeout or socket behavior, breaking RTT measurement accuracy
- `paramiko` update changes SSH key negotiation, breaking the REST-to-SSH failover path
- `requests` update changes SSL verification defaults, breaking RouterOS REST API calls
- `cryptography` update drops support for older cipher suites used by MikroTik's REST API

**Why it happens:**
wanctl's dependencies are pinned minimally (`>=` versions in pyproject.toml) and the real production behavior depends on exact versions deployed. The RTT measurement chain (`icmplib` raw sockets -> signal processing -> EWMA) is extremely sensitive to timing changes. A 1ms change in ICMP socket timeout behavior cascades through the entire control loop.

**How to avoid:**
1. Pin exact versions in production deployment (`uv pip freeze` output) separately from the development `pyproject.toml` minimum versions.
2. After ANY dependency upgrade, run `wanctl-benchmark` to verify bufferbloat grading has not regressed.
3. Test the REST-to-SSH failover path explicitly after `paramiko` or `requests` upgrades.
4. The `cryptography` package is a transitive dependency through `paramiko` -- upgrades to `paramiko` implicitly upgrade `cryptography`.
5. Never upgrade `icmplib` without measuring raw RTT accuracy against a known reflector.

**Warning signs:**
- `pip-audit` suggesting security updates for `cryptography` (frequent, usually safe but test anyway)
- `icmplib` major version bumps (rare but dangerous for timing-sensitive code)
- `requests` session behavior changes (keep-alive, timeout defaults)

**Phase to address:** Dependency audit phase should create a `requirements-production.txt` lock file and test the full benchmark suite after any upgrade.

---

### Pitfall 11: Removing the Singleton Pattern From MetricsWriter

**What goes wrong:**
The auditor identifies the `MetricsWriter` singleton (thread-safe with `_instance_lock`) as an anti-pattern and refactors to dependency injection or module-level instance. The refactored version creates multiple SQLite connections from different threads, causing database locking errors under the 20Hz write frequency.

**Why it happens:**
The singleton pattern is genuinely problematic in most Python code, and modern best practices favor dependency injection. However, `MetricsWriter` is a thread-safe singleton for a specific reason: the autorate daemon has a main event loop thread, an IRTT measurement thread, a health check HTTP server thread, and a metrics Prometheus server thread -- all of which write metrics to the same SQLite database. The singleton ensures a single WAL-mode connection with proper locking.

**How to avoid:**
1. If replacing the singleton, ensure the replacement maintains a single SQLite connection shared across all threads.
2. The `_reset_instance()` method is required for test isolation -- any replacement must provide an equivalent.
3. SQLite in WAL mode supports concurrent readers but only one writer. Multiple connections would degrade under 20Hz writes.
4. The `__enter__`/`__exit__` context manager deliberately does NOT close the connection (line 242-243) -- this is intentional singleton persistence, not a resource leak.

**Warning signs:**
- Context manager `__exit__` that does not close its resource
- `_reset_instance()` class method that looks like test pollution
- Thread lock on instance creation that looks like over-engineering

**Phase to address:** Architecture audit should document the MetricsWriter singleton rationale, not refactor it. If DI is desired, it belongs in a future milestone.

---

### Pitfall 12: Auditing Systemd Integration Without Testing on the Live VM

**What goes wrong:**
The auditor reviews the systemd unit files (`wanctl@.service`, `steering.service`), identifies "improvements" (different restart policies, tighter security settings, capability changes), applies them, and the daemon fails to start or loses critical capabilities.

**Why it happens:**
The systemd unit files have been tuned for production over 21 milestones:
- `CAP_NET_RAW` (line 39) is required for `icmplib` raw ICMP sockets. Removing it = no ping = no congestion detection = no bandwidth control.
- `ProtectSystem=strict` with `ReadWritePaths` (lines 43-45) is the security boundary. Adding more restrictions (like `ProtectNetwork=yes`) would break all network operations.
- `WatchdogSec=30s` is tuned for the 50ms cycle. Tightening it causes spurious restarts; loosening it delays failure detection.
- `StartLimitBurst=5` / `StartLimitIntervalSec=300` is the circuit breaker (documented in CLAUDE.md). Changing these values alters the failure recovery behavior.
- The `PYTHONPATH=/opt` environment variable is required because wanctl is deployed to `/opt/wanctl/` without pip install.

**How to avoid:**
1. Test ALL systemd changes on the cake-shaper VM (10.10.110.223) before committing.
2. After any unit file change, run `systemd-analyze verify wanctl@spectrum.service` to check syntax.
3. After any capability change, verify with `capsh --print` inside the service context.
4. The circuit breaker values are documented in CLAUDE.md -- read that section before changing them.

**Warning signs:**
- Unit file changes that look like "security improvements"
- Capability restrictions that seem safe but break ICMP
- Watchdog timing changes without measuring actual cycle time

**Phase to address:** Systemd audit phase must test every change on the production VM with actual service start/stop/restart cycles.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Leaving RouterOS class inline in autorate_continuous.py | No risk of extraction bugs | 4,282-line god file, hard to navigate | Acceptable during audit -- extraction is a separate milestone |
| Container scripts in active scripts/ dir | No effort to move them | Confusing to new contributors, looks like current deployment | Move to .archive/ during audit |
| "Flash wear" comments on Linux system | No effort to update | Misleading to future auditors, false obsolescence signal | Update comments to dual-rationale during audit |
| Separate state manager implementations | No consolidation risk | Three similar-looking classes, cognitive load | Acceptable -- different write frequencies justify separation |
| Lazy imports in router_client.py | Avoid circular imports | Static analysis tools cannot trace the dependency | Acceptable -- document in module docstring |
| MetricsWriter singleton | Thread-safe shared DB access | Testing complexity, global state | Acceptable until DI framework is introduced |

## Integration Gotchas

Common mistakes when modifying cross-component boundaries.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Autorate <-> Steering (state file) | Modifying state schema without updating both daemons | Map all producers AND consumers before schema changes |
| WANController <-> LinuxCakeAdapter | Changing set_limits() signature | The adapter exists to bridge interface differences -- changes must maintain both RouterOS.set_limits() and LinuxCakeAdapter.set_limits() |
| Signal processing chain | Reordering Hampel -> Fusion -> EWMA pipeline | The order is deliberate: outlier removal before fusion before smoothing. Reordering changes control behavior. |
| SIGUSR1 reload chain | Adding a new reload target without wiring it into the event loop | Follow the pattern: add _reload_X_config() method, call it from the SIGUSR1 handling block in run_cycle() |
| Health endpoint <-> Metrics | Assuming health data comes from metrics DB | Health endpoints serve LIVE state from memory; metrics DB stores HISTORICAL data. Different sources, different freshness. |
| Tuning <-> WANController | Modifying tuning parameter names | Tuning params persist in SQLite (tuning_params table). Renaming a param without migration loses learned values. |
| Config <-> check_config CLI | Adding new config fields | check_config.py has an explicit allowlist of known keys (line ~110-180). New keys not in the allowlist trigger "unknown key" warnings. |
| Steering <-> MikroTik | Changing mangle rule comment format | The steering daemon parses mangle rule output text (line 753: `if "ADAPTIVE" in line`). Changing the rule comment on the router breaks detection. |

## Performance Traps

Patterns that work at low frequency but fail at 20Hz.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Removing no-op write suppression (last_applied_*) | Cycle budget >100%, watchdog timeout | Keep rate change deduplication even on Linux | Immediately at 20Hz -- 20 unnecessary tc calls/sec |
| Adding logging in the hot path | Log rotation I/O stalls cycle | Use DEBUG level only, never INFO in per-cycle code | At 20Hz with file logging, stalls appear after hours |
| Replacing atomic_write_json with json.dump | Corrupted state files under concurrent read/write | Keep temp+fsync+rename pattern | Under sustained load when reader and writer race |
| Adding type() checks in WANController.run_cycle() | Measurable overhead at 50ms granularity | Use isinstance() which is C-optimized, not type() | Marginal at 20Hz but accumulates across all checks |
| Synchronous HTTP calls in cycle path | Cycle timeout when endpoint is slow | All HTTP (health, metrics, Discord) is async or fire-and-forget | When external service latency spikes |
| Full config re-parse every cycle | 1-2ms overhead per cycle compounds | Config is parsed once at startup, reloaded only on SIGUSR1 | If someone adds config.load() inside run_cycle() |

## Security Mistakes

Domain-specific security issues for a network controller audit.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Logging router passwords during audit debugging | Credentials in journal logs, potentially backed up | Password scrubbing is already implemented (v1.12). Verify scrubbing works before adding new log statements. |
| Relaxing ProtectSystem=strict for debugging | Daemon can write anywhere on filesystem | Debug on a test VM, never relax production systemd security |
| Exposing health endpoint on 0.0.0.0 | Network-accessible rate/congestion data | Health binds to 127.0.0.1 only. Verify this after any health server changes. |
| Storing secrets in config YAML instead of EnvironmentFile | Secrets readable by any user who can read /etc/wanctl/ | Keep EnvironmentFile=-/etc/wanctl/secrets pattern with 600 permissions |
| Upgrading cryptography without testing MikroTik TLS | RouterOS REST API may use older TLS -- newer cryptography lib may reject it | Test REST API connectivity after any cryptography upgrade |

## "Looks Dead But Isn't" Checklist

Things that appear unused/dead but are critical production code.

- [ ] **RouterOS class in autorate_continuous.py:** Only used when `router_transport != "linux-cake"` -- still needed for RouterOS deployments
- [ ] **routeros_ssh.py:** Lazy-imported by router_client.py only during REST failover -- appears unreferenced in import graph
- [ ] **LinuxCakeAdapter:** Conditional import at runtime (line 3474) -- invisible to static analysis
- [ ] **_reload_*_config() methods:** Called from event loop via threading.Event flag check, not direct call -- no static caller
- [ ] **MetricsWriter._reset_instance():** Only called by tests -- removing it breaks test isolation
- [ ] **congestion.dl_state/ul_state in state JSON:** Written by autorate, read by steering (separate process) -- looks dead within autorate
- [ ] **dirty tracking exclusion for congestion field:** Intentional write amplification prevention, not a bug
- [ ] **Context manager __exit__ that does not close:** MetricsWriter singleton persistence, not a resource leak
- [ ] **deprecate_param() translations:** Never trigger in current production but protect against old configs/backups
- [ ] **container_install_*.sh scripts:** Pre-v1.21 deployment -- still valid as fallback reference
- [ ] **scripts/verify_steering.sh and verify_steering_new.sh:** May look duplicated but test different verification approaches
- [ ] **CAP_NET_RAW in systemd unit:** Required for icmplib ICMP raw sockets -- looks like excessive privilege
- [ ] **isinstance(stats, dict) guard:** MagicMock safety for tests, not redundant runtime check
- [ ] **exclude_params in tuning config:** DOCSIS-specific feature -- looks like dead config on non-cable links but is production-active
- [ ] **PYTHONPATH=/opt in systemd unit:** Required because wanctl is deployed without pip install -- looks like a misconfiguration

## False Positive Patterns

Audit findings that look like problems but are intentional design decisions.

| Finding | Why It Looks Wrong | Why It Is Correct |
|---------|-------------------|-------------------|
| Two RouterOS classes (RouterOS + RouterOSController) | Looks like duplication | Different purposes: queue limits vs. mangle rule toggling |
| Three state manager classes | Looks like failed abstraction | Different write frequencies (50ms vs 5s) and schemas |
| LinuxCakeAdapter wrapping LinuxCakeBackend | Looks like unnecessary indirection | Bridges two different interfaces (set_limits vs set_bandwidth) |
| Five _reload methods instead of one | Looks like copy-paste | Each reloads a different YAML section with different validation |
| atomic_write_json for a simple JSON file | Looks over-engineered | Required for POSIX safety at 20Hz concurrent read/write |
| sleep(0.001) in test fixtures | Looks like timing hack | Thread synchronization in concurrent test scenarios |
| `if value and isinstance(value, str)` | Looks like redundant check | MagicMock guard pattern for test safety |
| Importing inside functions (lazy imports) | Looks like poor module structure | Avoids circular imports in router_client.py |

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Dead code removal breaks a backend | MEDIUM | `git revert` the commit. Verify both transport modes. Add integration test for the removed code path. |
| SIGUSR1 chain broken | LOW | `git revert`. Send SIGUSR1 to verify all 5 reload targets respond. Restart service if needed. |
| State file contract broken | HIGH | Stop both daemons. Restore state files from `.backup` suffix. Fix schema. Restart autorate first, then steering. |
| Flash wear protection removed | MEDIUM | `git revert`. Monitor cycle budget in health endpoint. If cycles are over budget, restart to apply reverted code. |
| Dependency upgrade breaks RTT | HIGH | Pin back to working versions in production. Run `wanctl-benchmark` to verify RTT accuracy restored. May need state file reset if learned tuning params are corrupted. |
| Systemd capability removed | LOW | `systemctl edit wanctl@spectrum` to add back capability. `systemctl daemon-reload && systemctl restart wanctl@spectrum`. |
| MetricsWriter singleton broken | MEDIUM | `git revert`. Check SQLite DB integrity with `sqlite3 metrics.db "PRAGMA integrity_check"`. May need `_reset_instance()` in test cleanup. |
| God object extraction gone wrong | HIGH | `git revert`. The 4,282-line file is ugly but STABLE. Resist the urge to re-attempt immediately. |

## Pitfall-to-Phase Mapping

How v1.22 audit phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Dead backend code removal | Dead code analysis | Run tests with both `linux-cake` and `rest` transport configs; all 8 CLI entry points exercised |
| SIGUSR1 chain breakage | Signal handling audit | Send SIGUSR1 and verify all 5 parameters reload; add E2E test if missing |
| State file contract break | State management audit | Map complete producer-consumer topology; integration test both daemons |
| Flash wear protection removal | Performance audit | Verify `last_applied_*` dedup still active; measure cycle budget before/after |
| Container code deletion | Infrastructure audit | Archive to `.archive/` with manifest; verify no broken references |
| God object extraction | Code complexity audit | Document structure only; defer extraction to future milestone |
| MagicMock guard removal | Type safety audit | Full test suite count must not decrease; run `pytest --tb=short` |
| State manager consolidation | Architecture audit | Document intentional separation; no consolidation during audit |
| Deprecation code removal | Config audit | Verify all docs use modern params; add removal timeline, do not delete |
| Dependency upgrade regression | Dependency audit | Create production lock file; run `wanctl-benchmark` after upgrades |
| Singleton refactoring | Architecture audit | Document thread safety rationale; defer DI to future milestone |
| Systemd misconfiguration | Infrastructure audit | Test every change on production VM; `systemd-analyze verify` |

## Sources

- Direct codebase analysis: 80+ source files in `src/wanctl/`, 28,629 LOC
- Direct codebase analysis: 121 test files, 68,360 LOC, 3,723 tests
- Project history: CLAUDE.md, MEMORY.md, PROJECT.md spanning v1.0-v1.21
- [Meta Engineering: Automating Dead Code Cleanup](https://engineering.fb.com/2023/10/24/data-infrastructure/automating-dead-code-cleanup/) -- false positive management at scale
- [Vulture: Find dead Python code](https://github.com/jendrikseipp/vulture) -- Python dynamic dispatch limitations in dead code detection
- [Tembo: Code Refactoring Mistakes](https://www.tembo.io/blog/code-refactoring) -- mixing refactoring with bug fixes
- [Real Python: Refactoring Python Applications](https://realpython.com/python-refactoring/) -- small safe steps
- [Refactoring Guru: Singleton in Python](https://refactoring.guru/design-patterns/singleton/python/example) -- thread safety considerations
- [systemd Watchdog Configuration](https://oneuptime.com/blog/post/2026-03-02-how-to-configure-systemd-watchdog-for-service-health-checks-on-ubuntu/view) -- watchdog timing requirements
- Production deployment experience: 21 milestones, 111 phases, 227 plans

---
*Pitfalls research for: v1.22 Full System Audit of wanctl production network controller*
*Researched: 2026-03-26*
