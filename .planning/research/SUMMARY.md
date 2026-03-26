# Project Research Summary

**Project:** wanctl v1.22 Full System Audit
**Domain:** Multi-perspective production audit — Python network controller (28,629 LOC, 3,723 tests, 21 milestones)
**Researched:** 2026-03-26
**Confidence:** HIGH

## Executive Summary

wanctl v1.22 is a full-system audit milestone for a production Python controller that has grown across 21 milestones without a comprehensive cross-cutting review. The system is now mature enough — and the codebase large enough — that accumulated technical debt (dead code, permissive type checking, 96 broad exception catches, orphaned scripts, stale docs, and unverified systemd hardening) warrants systematic treatment. The audit spans three expert perspectives: network engineering (CAKE parameter correctness, DSCP tin alignment, steering logic), Linux sysadmin (systemd hardening, file permissions, NIC persistence, operational resilience), and Python developer (dead code, type safety, exception hygiene, complexity hotspots, test quality).

The recommended execution approach is bottom-up by dependency layer: audit foundation utilities and shared infrastructure first, then communication and signal layers, then subsystems, and finally the two daemon cores. This ordering ensures findings in shared modules immediately reveal their blast radius — both daemons are affected — and the hardest code (autorate_continuous.py at 4,282 LOC and steering/daemon.py at 2,384 LOC) is audited last when all dependencies are understood. Tool selection is mostly zero-install: ruff rule expansion (C901, SIM, PERF, RET, PT, TRY, ARG, ERA) plus five one-shot pip installs (vulture, radon, complexipy, deptry, pytest-deadfixtures). No architectural rebuilds belong in this milestone.

The dominant risk is misidentifying live code as dead. The codebase has 15+ patterns that static analysis flags as unused but are critical: the RouterOS class active only in non-linux-cake deployments, lazy-imported routeros_ssh.py, the LinuxCakeAdapter bridging interface differences, SIGUSR1 reload methods called via threading.Event flags rather than direct call, the MetricsWriter singleton context manager that deliberately does not close its connection, and state file congestion fields written by autorate and read by the steering daemon in a separate process. Every finding must be validated against all 8 CLI entry points and both transport configurations before any removal.

## Key Findings

### Recommended Stack

The project already has a strong toolchain (ruff, mypy, pytest-cov, bandit, pip-audit, detect-secrets, pip-licenses). The audit gaps are in eight dimensions not yet covered: dead function/class/method detection, cyclomatic complexity ranking, cognitive complexity, unused dependencies, unused test fixtures, and several ruff rule categories not enabled. All can be addressed with minimal new tooling.

**Core technologies:**
- ruff (rule expansion: C901/SIM/PERF/RET/PT/TRY/ARG/ERA): zero-install config change — covers simplification opportunities, complexity gating, pytest style consistency, unused arguments, commented-out code
- vulture 2.16: dead functions/classes/methods/unreachable branches — catches what ruff F rules miss; no external dependencies
- radon 6.0.1: cyclomatic complexity ranked reports, maintainability index per file — directly actionable for refactoring prioritization
- complexipy 5.2.0: cognitive complexity (how hard to understand, not just branch count) — Rust-native, fast on 28K LOC
- deptry 0.25.1: unused/missing/transitive dependency hygiene — reads pyproject.toml natively, Rust core
- pytest-deadfixtures 2.2.1: orphaned test fixtures — 21 milestones guarantees fixture rot in 3,723 tests
- mypy (incremental strictness): disallow_untyped_defs, warn_return_any, no_implicit_optional — probe one flag at a time on targeted modules, not --strict globally

**What NOT to install:** pylint (ruff covers it 100x faster), flake8 (ruff replaces ecosystem), safety (pip-audit covers same CVEs), SonarQube (overkill for single-maintainer), wily (radon snapshot is sufficient).

### Expected Features

Research reframes "features" as audit categories across three perspectives with defined priority levels.

**Must have — P1 (production safety or security impact):**
- CAKE parameter correctness per WAN type (DOCSIS overhead for Spectrum, VDSL2/bridged-ptm for ATT, diffserv4 tin mapping)
- DSCP/diffserv tin alignment end-to-end (RB5009 mangle rules through CAKE tins — EF=Voice, AF41=Video, CS1=Bulk)
- Exception handling audit (96 `except Exception` catches — identify which swallow real bugs vs. which are legitimate safety nets)
- systemd unit hardening (systemd-analyze security score; add ProtectKernelTunables, RestrictNamespaces, SystemCallFilter where safe)
- File permissions (/etc/wanctl/secrets must be 0600 root:wanctl; state and log dirs 0750)
- Dead code identification (vulture scan — identification only, no removal without validation)

**Should have — P2 (prevents future problems):**
- Thread safety audit (16 files use threading; shared mutable state between autorate, IRTT thread, health server, webhook delivery)
- NIC and bridge persistence across reboot (rx-udp-gro-forwarding not persistent — known gap from MEMORY.md)
- Type safety assessment (mypy strictness probe module by module, starting with leaf modules)
- Complexity hotspot analysis (5 files over 1,000 LOC: autorate_continuous, steering/daemon, check_config, check_cake, calibrate)
- Backup and recovery documentation (is /etc/wanctl backed up? metrics.db? VM snapshot strategy? rollback to old containers?)
- Steering logic correctness (confidence scoring weights, degrade timers, CAKE-primary invariant, grace period behavior)
- Production dependency lock file (uv pip freeze output — separate from pyproject.toml minimum versions)

**Defer — P3 (optimization and polish):**
- Prometheus/Grafana integration (document metric naming readiness only — implementation is a separate milestone)
- Test assertion quality / mutation testing (mutmut is hours-long on 28K LOC — run only on critical modules if at all)
- autorate_continuous.py extraction plan (document which classes could be extracted — execution is a future milestone)
- import-linter architectural boundary enforcement (post-audit enforcement, not during audit)

**Anti-features — explicitly out of scope:**
- Rewriting autorate_continuous.py (behavioral regressions in 50ms control loop take days to surface)
- Global strict mypy migration (produces unreviable changeset; module-by-module only)
- Removing all mocking from tests (would make tests environment-dependent and slow)
- Performance optimization of the 50ms loop (already within budget; premature optimization causes instability)
- Prometheus/Grafana implementation (scope creep — document readiness only)

### Architecture Approach

The audit follows the dependency graph of ~80 Python modules across six functional layers. The daemon cores (13,700 LOC combined) are deliberately audited last when all dependencies are understood. Cross-cutting concerns — error swallowing, type safety gaps, dead code, hardcoded values, logging hygiene — are tracked as running observations throughout all phases. Findings use a structured template (FINDING / SEVERITY P0-P4 / MODULES / ROOT CAUSE / IMPACT / FIX / TEST).

**Major components by audit layer:**
1. Foundation (path_utils, timeouts, daemon_utils, signal_utils, error_handling, state_utils) — ~1,800 LOC; audit first
2. Data layer (config_base, state_manager, storage subsystem, backends/base) — ~3,200 LOC; audit second
3. Communication (routeros_rest/ssh, router_client, LinuxCakeBackend, retry_utils) — ~3,100 LOC; audit third
4. Signal and measurement (rtt_measurement, irtt, signal_processing, baseline, cake_params) — ~2,600 LOC; audit fourth
5. Subsystems (tuning, steering sub-packages, alert_engine, webhook, metrics, health_check) — ~5,400 LOC; audit fifth
6. Daemon cores and CLI (autorate_continuous, steering/daemon, check_config, check_cake, dashboard) — ~13,700 LOC; audit last

**Key patterns to audit (not change in this milestone):**
- MetricsWriter singleton: deliberate thread-safe single SQLite connection — document rationale, do not refactor
- TYPE_CHECKING circular import avoidance in health_check.py and steering/health.py — fragile attribute access; flag, do not restructure
- Flash wear protection / no-op write suppression — still required on Linux for 20Hz tc syscall avoidance despite MikroTik-era naming
- State file IPC contract (autorate writes, steering reads) — atomic_write_json is correct; map all consumers before touching schema
- SIGUSR1 reload chain (5 distinct targets, 2 daemons) — must be fully cataloged before any consolidation attempt

### Critical Pitfalls

1. **Removing backend code that only runs in non-linux-cake deployments** — vulture and import graphs flag RouterOS class (autorate_continuous.py line 1204), routeros_ssh.py (lazy-imported in router_client.py), and LinuxCakeAdapter (conditional runtime import line 3474) as dead. All three are live. Before any removal, trace from all 8 CLI entry points with both `router_transport: "linux-cake"` and `router_transport: "rest"` configs.

2. **Breaking the SIGUSR1 hot-reload chain** — Five reload targets added incrementally across v1.11-v1.20 (wan_state.enabled, dry_run, webhook_url, fusion config, tuning config). The `_reload_*_config()` methods have no static callers — they are invoked via `threading.Event` flag check in the event loop. Consolidation without a complete catalog silently disables hot-reload for one or more parameters.

3. **Breaking the inter-process state file contract** — `congestion.dl_state`/`ul_state` in the state JSON appears dead within autorate but is read by the steering daemon in a separate process. The dirty-tracking exclusion for congestion fields is intentional (prevents 20Hz write amplification). Map all consumers before any schema change.

4. **Removing flash wear protection as obsolete on Linux** — `last_applied_dl_rate`/`ul_rate` guards prevent 20 unnecessary `tc qdisc change` syscalls per second. At 50ms cycle budget (30-40ms used), removing them pushes utilization above 100%. Update comments to reflect Linux rationale; do not remove the mechanism.

5. **Systemd hardening that drops CAP_NET_RAW or breaks ProtectSystem=strict** — CAP_NET_RAW is required for icmplib raw ICMP sockets. Removing it silently disables all congestion detection. Test every unit file change on the production VM (10.10.110.223) with actual service start/stop cycles; use `systemd-analyze verify` before applying.

## Implications for Roadmap

FEATURES.md (5-phase audit prioritization), ARCHITECTURE.md (6-phase bottom-up dependency order), and PITFALLS.md (pitfall-to-phase safety mapping) independently converge on the same phase structure. The ordering is driven by three principles: (1) mechanical/safe work first, (2) dependencies flow downward through layers, (3) the most dangerous work (dead code removal, state schema changes, systemd changes) only happens after prerequisites are verified.

### Phase 1: Foundation Scan

**Rationale:** Produces findings that unblock all later phases with near-zero production risk. Kernel/iproute2 version data is a prerequisite for Phase 2. Dead code inventory is a prerequisite for Phase 3.
**Delivers:** Dependency CVE status (pip-audit), unused dependencies (deptry), file permission report, systemd hardening score (systemd-analyze security), dead code inventory (vulture — identification only, no removals), log rotation verification, kernel/iproute2 version record, ruff ERA scan for commented-out code, orphaned fixture list (pytest-deadfixtures).
**Addresses:** Dependency hygiene, file permissions, log rotation, dead code identification (P1 audit areas that are safe to execute without production risk).
**Avoids:** Acting on dead code findings before transport validation; changing systemd units before understanding directive semantics.

### Phase 2: Network Engineering Deep Dive

**Rationale:** Requires production VM access and kernel/iproute2 data from Phase 1. CAKE parameter audit must precede DSCP audit (CAKE params affect tin behavior). Network engineering findings are independent of code quality findings in Phase 3.
**Delivers:** Verified CAKE parameters per WAN with `tc -j -s qdisc show` readback (DOCSIS overhead, diffserv4 tin mapping, ack-filter, split-gso validity), DSCP end-to-end trace from RB5009 mangle rules to CAKE tin counters, queue depth/memory pressure baseline, bandwidth ceiling vs measured capacity confirmation, steering logic correctness audit.
**Addresses:** CAKE parameter correctness, DSCP tin alignment, measurement path integrity, CAKE algorithm optimization params, queue depth analysis, steering logic (all P1/P2 network audit areas).
**Avoids:** Changing CAKE params and bridge persistence in the same phase — if something breaks, isolation is impossible.

### Phase 3: Code Quality and Safety

**Rationale:** Requires dead code inventory from Phase 1 — cannot safely remove code without knowing test quality first. Exception handling fixes must be tested, which requires stable test infrastructure. Thread safety requires singleton/global state map first (cannot reason about thread safety without knowing what state is shared).
**Delivers:** Exception handling audit with categorized dispositions (96 broad catches triaged by risk level), type safety probe with module-by-module plan (starting with leaf modules), complexity hotspot report for 5 largest files with extraction recommendations (document only — no execution), import graph with circular dependency check, complete singleton and global state inventory, thread safety findings (16 threaded files), SIGUSR1 reload chain catalog with E2E test if missing.
**Addresses:** Exception handling audit, type safety assessment, complexity hotspots, thread safety, singleton audit (P1-P2 Python audit areas).
**Avoids:** Removing MagicMock isinstance guards (test count must not decrease), consolidating state managers, extracting from autorate_continuous.py.

### Phase 4: Operational Hardening

**Rationale:** Requires findings from all prior phases to prioritize hardening correctly. Thread safety findings from Phase 3 inform which resource limits are appropriate. All systemd changes require production VM testing.
**Delivers:** Hardened systemd units (ProtectKernelTunables, MemoryDenyWriteExecute, SystemCallFilter, RestrictNamespaces where compatible with CAP_NET_RAW and network daemon requirements), verified NIC/bridge persistence across reboot (rx-udp-gro-forwarding persistent solution), consistent circuit breaker config across all three service units, resource limits (MemoryMax, TasksMax, LimitNOFILE), production dependency lock file (requirements-production.txt from uv pip freeze), backup/recovery documentation, disaster recovery procedure.
**Addresses:** systemd hardening, NIC/bridge persistence, watchdog/circuit breaker consistency, resource limits, backup/recovery, disaster recovery (P1-P2 sysadmin areas).
**Avoids:** Tightening hardening in a way that drops CAP_NET_RAW; changing watchdog timing without cycle budget measurement; running systemd changes without `systemd-analyze verify` first.

### Phase 5: Test and Documentation Hygiene

**Rationale:** Final phase — validates all prior changes and documents residual debt. Test quality audit is most meaningful after code quality changes are made. Cannot audit documentation freshness until architecture changes are confirmed complete.
**Delivers:** Test quality audit (assertion-free, over-mocked, tautological tests identified — with targeted fixes for highest-risk cases), error recovery path coverage for handle_errors decorator usages, SQLite durability verification (WAL mode, busy_timeout, concurrent access, integrity check), config validation completeness (CONFIG_SCHEMA.md vs config_validation_utils.py vs accepted params), documentation freshness review (docs/* dates vs current architecture — DOCKER.md, PRODUCTION_INTERVAL.md, PORTABLE_CONTROLLER_ARCHITECTURE.md), orphaned script archiving to .archive/container-scripts/ with manifest, deprecate_param() removal timeline comments, audit findings summary with remaining debt inventory.
**Addresses:** Test quality, error recovery coverage, SQLite durability, config validation, documentation hygiene, container script archiving (P2-P3 areas).
**Avoids:** Deleting container-era scripts (archive to .archive/ instead); removing deprecate_param() bridges (add removal timeline comments instead); attempting autorate_continuous.py extraction (document recommendations only).

### Phase Ordering Rationale

- Phase 1 is a prerequisite for both Phase 2 (kernel version data) and Phase 3 (dead code inventory).
- Phase 2 and Phase 3 have no dependency on each other and could run in parallel — sequential is safer given production VM access requirements.
- Phase 3 precedes Phase 4: thread safety and singleton findings inform appropriate resource limits.
- Phase 4 precedes Phase 5: hardening changes must stabilize before writing test coverage for them.
- Phase 5 is last: test and documentation quality audit only meaningful after prior changes are complete.

### Research Flags

Phases likely needing `/gsd:research-phase` during planning:
- **Phase 2:** CAKE parameter details differ between DOCSIS (Spectrum) and VDSL2 (ATT); iproute2-6.15.0 ecn flag removal was one known compatibility break — verify whether other CAKE params have similar version-specific behavior on the Debian 12 kernel; DSCP mangle rule text format on RouterOS 7.x needs verification.
- **Phase 4:** Specific systemd security directives compatible with CAP_NET_RAW + ProtectSystem=strict + network daemon constraints need verification against the systemd version shipped with Debian 12 bookworm (systemd 252).

Phases with standard/well-documented patterns (skip research-phase):
- **Phase 1:** All tools are well-documented and already partially in use; execution is purely mechanical.
- **Phase 3:** Python code quality methodology is well-established; tool outputs are self-explanatory; judgment calls are codebase-specific.
- **Phase 5:** Documentation and script archiving require no external research; all judgment calls are internal.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All tools verified against PyPI on 2026-03-26; existing toolchain fully understood; clear rationale for each addition and each skip |
| Features | HIGH | Based on direct codebase analysis of 80+ source files; three-perspective audit methodology is internally consistent; prioritization matrix grounded in production risk assessment |
| Architecture | HIGH | Full import graph extracted via AST analysis; module LOC counts verified; dependency heat map confirms coupling observations; data flows traced through actual code |
| Pitfalls | HIGH | Grounded in direct codebase analysis across 21 milestones of history; 15+ "looks dead but isn't" patterns documented with exact line numbers; false positive patterns cataloged |

**Overall confidence:** HIGH

### Gaps to Address

- **radon Python 3.12 compatibility:** radon 6.0.1 was released ~12 months ago and Python 3.12 compatibility is not explicitly confirmed. Run `uv pip install radon` and verify it imports cleanly before relying on it. Fallback: ruff C901 for complexity gating, complexipy for cognitive complexity.
- **systemd directive compatibility on Debian 12 bookworm:** ProtectKernelTunables, RestrictNamespaces, and MemoryDenyWriteExecute behavior varies by systemd version. Use `systemd-analyze verify wanctl@spectrum.service` and test on production VM before committing unit file changes.
- **SIGUSR1 E2E test coverage:** Individual reload methods are tested but the full chain from signal delivery to runtime parameter change may not have E2E coverage. Verify during Phase 3 before any signal handling changes are made.
- **rx-udp-gro-forwarding persistence mechanism:** The correct persistence approach (systemd-networkd ExecPost hook, udev rule, or other) needs determination during Phase 4. Current state: not persistent across reboot.
- **Exact scope of 96 broad exception catches:** FEATURES.md cites this count; the specific locations, risk levels, and whether default_returns are safe have not yet been mapped. Phase 3 begins with this enumeration.

## Sources

### Primary (HIGH confidence)
- Ruff rules documentation (docs.astral.sh/ruff/rules/) — full rule catalog, verified 2026-03-26
- vulture GitHub (jendrikseipp/vulture) — v2.16 confirmed via PyPI
- deptry documentation (deptry.com) — v0.25.1, actively maintained, Rust core
- complexipy GitHub (rohaquinlop/complexipy) — v5.2.0, Rust-based, Python 3.8-3.13
- tc-cake(8) Linux manual page (man7.org) — CAKE parameter reference
- mypy command line documentation (mypy.readthedocs.io) — strict mode flags and incremental adoption
- wanctl codebase (src/wanctl/, tests/, systemd/, scripts/, docs/) — direct AST analysis of all 80 modules

### Secondary (MEDIUM confidence)
- radon documentation (radon.readthedocs.io) — v6.0.1; last release ~12 months ago, Python 3.12 compat not explicitly confirmed
- systemd hardening guides (linux-audit.com, ctrl.blog) — directive recommendations; must verify against Debian 12 systemd 252
- STX Next Python code quality audit methodology — general framework applied to wanctl-specific findings
- Bufferbloat.net CAKE technical (bufferbloat.net) — CAKE algorithm background

### Tertiary (LOW confidence)
- Semgrep community rules — cited as optional Tier 3 tool in STACK.md; not recommended for this milestone; pipx install only
- mutmut documentation — mutation testing deferred to optional P3; hours-long run on 28K LOC

---
*Research completed: 2026-03-26*
*Ready for roadmap: yes*
