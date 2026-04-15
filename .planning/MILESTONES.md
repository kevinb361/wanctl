# Project Milestones: wanctl

## v1.38 Measurement Resilience Under Load (Shipped: 2026-04-15)

**Phases completed:** 5 phases, 12 plans, 26 tasks

**Key accomplishments:**

- Defined and shipped an explicit measurement-health contract so reflector quorum and stale/current RTT status are machine-readable.
- Fixed the zero-success cached-RTT honesty gap without retuning congestion thresholds or disturbing existing outage fallback behavior.
- Added regression coverage across controller behavior, health payloads, fallback safety, and producer-side RTT status publication.
- Aligned runbook, deployment, and replayable verification evidence with the new measurement-resilience contract.
- Backfilled Phase 186 verification and closed the final traceability drift so all eight v1.38 requirements are now satisfied and archive-ready.

---

## v1.37 Dashboard History Source Clarity (Shipped: 2026-04-14)

**Phases completed:** 3 phases, 8 plans, 23 tasks

**Key accomplishments:**

- Locked the dashboard-facing source contract so endpoint-local HTTP history, merged CLI proof, and degraded-source behavior are explicit and stable.
- Surfaced endpoint-local framing, translated source detail, and an immutable merged-CLI handoff in the History tab without changing backend history semantics.
- Added focused regressions for success, fetch-error, source-missing, mode-missing, and db-paths-missing history states.
- Aligned deployment, runbook, and getting-started docs to the same endpoint-local HTTP versus authoritative merged CLI history rule.
- Closed all five milestone requirements and refreshed the milestone audit to `passed` after validation backfill and integration re-check.

---

## v1.36 Storage Retention And DB Footprint (Shipped: 2026-04-14)

**Phases completed:** 6 phases, 17 plans, 33 tasks

**Key accomplishments:**

- Identified the real production DB topology and explained why the per-WAN footprint stayed multi-GB.
- Tightened per-WAN retention and aligned history-reader/operator docs to the authoritative storage layout without changing controller logic.
- Closed `OPER-04` with a repeatable operator proof path for DB inventory, storage status, and merged CLI history checks.
- Repaired the startup/watchdog regression caused by heavy pre-health storage work during footprint-reduction rollout.
- Finished the ATT-only compaction pass and reduced `metrics-att.db` from about `5.08 GB` to about `202 MB`, closing `STOR-06`.

---

## v1.35 Storage Health & Stabilization (Shipped: 2026-04-13)

**Phases completed:** 5 phases, 16 plans, 23 tasks

**Key accomplishments:**

- Rebounded v1.34 storage fallout by fixing per-WAN metrics storage handling, hardening periodic SQLite maintenance, and repairing the production `analyze_baseline` deploy path.
- Deployed v1.35.0 cleanly through the active service flow and validated Spectrum, ATT, and steering with a passing canary.
- Closed the 24-hour production soak with non-critical storage, healthy operator surfaces, and zero err-level journal entries for the WAN services.
- Backfilled the missing verification and audit evidence so all six v1.35 requirements are now phase-verified and traceable.
- Aligned deploy/install/operator-summary/soak documentation and helper scripts with the actual production flow, including steering-aware evidence coverage.

---

## v1.34 Production Observability and Alerting Hardening (Shipped: 2026-04-12)

**Phases completed:** 5 phases, 9 plans, 2 tasks

**Key accomplishments:**

- Added bounded latency-regression and burst-churn alerts to the existing autorate alert path without touching the control algorithm.
- Validated that the new alert rules stay quiet on the live autorate service and are ready for production use.
- Added bounded storage and runtime pressure visibility to the existing operator surfaces without touching controller thresholds or adding a new persistence path.
- Validated that the new storage and runtime pressure signals are healthy, readable, and low-noise on the live host.
- Added compact operator summary surfaces on top of the existing bounded health contract and locked the shape with focused regression coverage.
- Validated the new compact summary contract on live services and confirmed ATT/Spectrum parity in the operator-facing view.
- Built the post-deploy canary script and covered its classification contract with offline pytest fixtures.
- Validated the canary on live services, fixed a storage-status false positive, and added deploy guidance so operators run the canary after restart.
- Operator-facing threshold runbook for v1.34 alerts, health summaries, canary exit codes, and escalation guidance

---

## v1.33 Detection Threshold Tuning (Shipped: 2026-04-11)

**Phases completed:** 5 phases, 10 plans, 14 milestone requirements

**Key accomplishments:**

- 24-hour idle baseline captured before any tuning, giving the threshold sweep a real production reference instead of anecdotal load behavior
- Five CAKE detection and recovery parameters A/B tested under RRUL, with the winning set deployed together and confirmed in a 24-hour production soak
- Production runtime hardened during the milestone: metrics-history performance, steering health, retention cadence, and shared SQLite maintenance coordination all improved on the live host
- Storage contention observability added to autorate and steering, and the explicit live decision was to keep the shared SQLite topology for now
- Burst-aware clamp behavior plus health/Prometheus observability added, then retuned to bring `tcp_12down` p99 back out of the multi-second range without regressing `rrul_be`

---

## v1.32 CAKE-Aware Congestion Detection (Shipped: 2026-04-10)

**Phases completed:** 3 phases, 5 plans, 9 tasks

**Key accomplishments:**

- 1. [Rule 1 - Bug] MagicMock leaking into JSON serialization
- CAKE-aware zone classification with dwell bypass on elevated drop rate and green_streak suppression on elevated backlog
- Refractory period anti-oscillation with CAKE snapshot wiring through congestion assessment, YAML threshold parsing, and health endpoint detection state
- Exponential rate recovery probing with 1.5x multiplier, 90% ceiling linear fallback, and 9-path multiplier reset via CAKE signal guards

---

## v1.29 Code Health & Cleanup (Shipped: 2026-04-08)

**Phases completed:** 9 phases, 28 plans, 59 tasks

**Key accomplishments:**

- Vulture dead code detection configured with 90+ whitelist entries covering framework, protocol, and test-only false positives; 8 ruff lint errors fixed in tests; make dead-code CI target enforcing ongoing detection
- Removed 10 dead code items across 8 files and deleted 2 orphaned modules with tests, achieving zero vulture findings and zero ruff F401 violations with 4,177 tests passing
- make check-deps target verifying all 8 runtime pip dependencies are imported in src/wanctl/, integrated into make ci
- Bidirectional config key audit: ~50 missing paths added to KNOWN_AUTORATE_PATHS, 6 example files cleaned of dead/deprecated keys, undocumented keys added as commented-out sections
- Corrected stale docstrings (is_ok/is_err, wrong path), synced CONFIG_SCHEMA.md with 5 new/updated sections (storage.retention, owd_asymmetry, fusion.healing, ping_source_ip, deprecated table), and fixed alpha_baseline/alpha_load references in ARCHITECTURE.md and CONFIGURATION.md
- Extracted QueueController, Config, and RouterOS from 5,218-LOC monolith into 3 focused modules, reducing autorate_continuous.py by 1,558 lines
- Extracted WANController (~2,396 LOC) and _apply_tuning_to_controller (~93 LOC) to wan_controller.py, completing the monolith decomposition into 5 modules
- Split 4 CLI tool modules (check_config, check_cake, calibrate, benchmark) into 8 focused modules, extracting validators, fix infrastructure, measurements, and comparison logic
- Split check_config_validators.py (1026 eff LOC) into autorate-only (569 eff LOC) and steering-only (478 eff LOC) validator modules, closing the SC1 gap
- Extracted WANController's 3 largest functions (408+447+102 LOC) into 22 focused private methods with AST verification script
- main() decomposed from 612 to 47 lines via 23 lifecycle helpers; __init__() from 81 to 13 lines; all 32 functions under 50 lines
- Extracted 5 mega-functions (run_cycle 220, main 158, _load_alerting_config 108, __init__ 88, _load_wan_state_config 88 LOC) into 21 focused private helpers, all under 50 lines
- Extracted _get_health_status() in both health handlers into section-builder assembler pattern (347->40 LOC autorate, 212->25 LOC steering)
- Extracted 12 functions (100-167 LOC) across 8 files into ~35 focused helpers, plus proactive medium-function cleanup in target files
- 1. [Rule 3 - Blocking] Fixed _apply_tuning_to_controller C901 violation (not in original plan)
- Deleted 18 stale phase tests, extracted shared helpers, moved 9 steering and 4 backends test files into mirrored subdirectories with dedicated conftest.py files
- Moved 6 storage + 16 tuning test files into mirrored subdirectories and renamed test_dashboard to dashboard, with shared fixture extraction
- TestCLI.test_main_connectivity_error_returns_1
- 4 runtime-checkable Protocol definitions in interfaces.py plus AST boundary check script with 109-violation allowlist and CI integration
- Public facade API on WANController (13 methods/properties) eliminating all 35+ cross-module private accesses from autorate_continuous.py, plus public properties on 4 component classes
- One-liner:
- SteeringDaemon.get_health_data() facade + zero cross-module violations with empty allowlist and enhanced AST boundary checker
- Fix 46 steering test failures from Phase 147 interface promotion, add _make_health_data() test helper, delete ghost duplicate file
- pytest-xdist parallel execution with 2s timeout, CI brittleness gate, and 7 MagicMock test failures fixed via typed return values
- Eliminated 21 real time.sleep() calls from tests via mocked time, tightened brittleness to 0, verified xdist isolation with randomized ordering -- 74.5% speed improvement vs baseline
- 1. [Rule 3 - Blocking] TypedDict not compatible with dict[str, Any] in mypy 1.19
- 1. [Rule 1 - Bug] routeros.py accessed config.router attribute not on BaseConfig

---

## v1.28 Infrastructure Optimization (Shipped: 2026-04-05)

**Phases completed:** 4 phases, 5 plans, 9 tasks

**Key accomplishments:**

- 3-core IRQ affinity splits Spectrum bridge across CPU0+CPU2, netdev_budget doubled to 600, RRUL load avg drops 23% (1.13 to 0.87)
- SFP+ switched to multi-queue mq-pfifo eliminating 404K TX queue drops; heaviest switch IRQ (36) pinned from cpu2 to cpu1 for load rebalancing
- ZeroTier binding to wireguard1 caused 850K+ TX errors (43K/day); restricting ZT to WAN/LAN interfaces reduced error rate to 0
- nftables bridge forward rules with conntrack marks classifying download traffic into CAKE diffserv4 Voice/Bulk/BestEffort tins on both Spectrum and ATT bridges
- Bridge QoS deployed to cake-shaper VM with nftables DSCP classification active on both bridges -- ATT tin separation verified, Spectrum showing 1.8M Voice + 95K Bulk packets, RRUL validation pending after ceiling sweep

---

## v1.27 Performance & QoS (Shipped: 2026-04-03)

**Phases completed:** 6 phases, 11 plans, 12 tasks

**Key accomplishments:**

- 6 sub-timers added to run_cycle hot path + health endpoint subsystems breakdown for identifying 138% cycle budget overrun sources
- RTT measurement consumes 84.6% of 50ms cycle budget under RRUL load (42ms avg, p99=116ms); SQLite hypothesis disproven at 6.6%; Phase 132 to optimize ICMP path + non-blocking I/O
- Decoupled RTT measurement from control loop via BackgroundRTTThread with persistent ThreadPoolExecutor and GIL-protected atomic swap, eliminating 42ms blocking I/O from hot path
- Health endpoint gains ok/warning/critical status field from rolling utilization vs configurable threshold (80%), with AlertEngine cycle_budget_warning after 60 consecutive overruns and SIGUSR1 hot-reload
- check_tin_distribution() validates per-tin CAKE packet counts via local tc subprocess with PASS/WARN verdicts for DSCP mark survival
- 60s windowed suppression counter in QueueController with health endpoint exposure and periodic INFO logging during congestion
- Discord alert fires via AlertEngine when windowed suppression rate exceeds configurable threshold during congestion, with SIGUSR1 hot-reload for threshold

---

## v1.26 Tuning Validation (Shipped: 2026-04-03)

**Phases completed:** 5 phases, 5 plans, 31 tasks

**Key accomplishments:**

- Reusable bash gate script validates 5 pre-tuning conditions on production cake-shaper VM -- all 5/5 pass, environment confirmed ready for linux-cake A/B testing
- 9 DL parameters A/B tested on linux-cake transport via RRUL flent -- 6 of 9 changed from REST-validated values, revealing transport-dependent tuning shift toward gentler response and wider thresholds
- 3 UL parameters A/B tested on linux-cake transport -- step_up_mbps changed from 1 to 2, factor_down=0.85 and green_required=3 confirmed
- CAKE rtt=40ms validated (5-way test), confirmation pass caught target_bloat_ms interaction flip from 15 back to 9 -- final linux-cake config has 7 total changes from REST baseline
- Verified all 13 tuning parameters on production cake-shaper match linux-cake A/B winners, updated example config and CHANGELOG v1.26.0 with per-parameter metrics

---

## v1.25 Reboot Resilience (Shipped: 2026-04-02)

**Phases completed:** 1 phase (125), 2 plans, 4 tasks

**Key accomplishments:**

- Idempotent NIC tuning shell script with ring buffers (4096), rx-udp-gro-forwarding, and IRQ affinity for 4 bridge NICs with journal logging
- systemd dependency wiring (After= + Wants=) ensuring wanctl waits for NIC tuning completion
- deploy.sh updated to deploy NIC tuning script and service alongside wanctl code
- Dry-run validated on production: script idempotent, dependencies verified, services unaffected

**Known gaps (deferred to v1.26):**

- BOOT-04: Full reboot E2E test (requires physical access)
- VALN-01/VALN-02: Boot validation CLI tool (Phase 126 scope)

---

## v1.24 EWMA Boundary Hysteresis (Shipped: 2026-04-02)

**Phases completed:** 8 phases, 14 plans, 20 tasks

**Key accomplishments:**

- NetlinkCakeBackend with pyroute2 netlink for CAKE bandwidth control, singleton IPRoute lifecycle, and per-call subprocess fallback
- Netlink-based per-tin CAKE stats via pyroute2 TCA_STATS2 decoder with factory dispatch for linux-cake-netlink transport
- Per-granularity retention thresholds in YAML config with cross-section tuner validation and prometheus_compensated mode
- Per-granularity retention wired into both daemons with SIGUSR1 reload, cross-section validation at startup, and config-driven downsample thresholds
- Standalone FusionHealer with incremental rolling Pearson correlation, 3-state machine (ACTIVE/SUSPENDED/RECOVERING), AlertEngine alerts, parameter locking, and SIGUSR1 grace period
- FusionHealer wired into WANController with per-cycle delta feeding, state-transition-driven fusion toggling, SIGUSR1 grace period, and heal state in health endpoint
- 3 pure-function response tuning strategies (step_up, factor_down, green_required) with episode detection infrastructure analyzing wanctl_state 1m time series for congestion-recovery patterns
- RESPONSE_LAYER wired as 5th rotation layer with oscillation lockout, 6-param controller mapping, and RTUN-05 default-exclude graduation pattern
- Dwell timer (3-cycle gate) and deadband margin (3ms hysteresis band) on QueueController GREEN/YELLOW boundary for both upload and download state machines
- YAML config wiring for dwell_cycles and deadband_ms with schema validation, sensible defaults (3/3.0), and QueueController pass-through
- SIGUSR1 hot-reload for dwell_cycles and deadband_ms with bounds validation, old->new logging, and E2E chain integration
- Per-direction suppression counter and health endpoint hysteresis sub-dict with dwell_counter, dwell_cycles, deadband_ms, transitions_suppressed; DEBUG/INFO logging on suppressed and confirmed transitions

---

## v1.23 Self-Optimizing Controller (Shipped: 2026-03-27)

**Phases completed:** 4 phases, 8 plans, 12 tasks

**Key accomplishments:**

- NetlinkCakeBackend with pyroute2 netlink for CAKE bandwidth control, singleton IPRoute lifecycle, and per-call subprocess fallback
- Netlink-based per-tin CAKE stats via pyroute2 TCA_STATS2 decoder with factory dispatch for linux-cake-netlink transport
- Per-granularity retention thresholds in YAML config with cross-section tuner validation and prometheus_compensated mode
- Per-granularity retention wired into both daemons with SIGUSR1 reload, cross-section validation at startup, and config-driven downsample thresholds
- Standalone FusionHealer with incremental rolling Pearson correlation, 3-state machine (ACTIVE/SUSPENDED/RECOVERING), AlertEngine alerts, parameter locking, and SIGUSR1 grace period
- FusionHealer wired into WANController with per-cycle delta feeding, state-transition-driven fusion toggling, SIGUSR1 grace period, and heal state in health endpoint
- 3 pure-function response tuning strategies (step_up, factor_down, green_required) with episode detection infrastructure analyzing wanctl_state 1m time series for congestion-recovery patterns
- RESPONSE_LAYER wired as 5th rotation layer with oscillation lockout, 6-param controller mapping, and RTUN-05 default-exclude graduation pattern

---

## v1.22 Full System Audit (Shipped: 2026-03-27)

**Phases completed:** 14 phases, 33 plans, 55 tasks

**Key accomplishments:**

- All 4 target NICs (2x i210, 2x i350) confirmed in separate single-device IOMMU groups on odin -- PCIe passthrough feasible, Phase 109 unblocked
- LinuxCakeBackend implementing RouterBackend ABC with tc subprocess calls for CAKE bandwidth control, per-tin stats parsing, and qdisc initialization/validation
- Direction-aware CakeParamsBuilder with upload ack-filter, download ingress+ecn, overhead keyword validation, and readback-to-numeric conversion
- Extended initialize_cake with overhead_keyword standalone tc token support, elif priority over numeric fallback, and build_cake_params integration tests
- get_backend() factory routes linux-cake transport to LinuxCakeBackend with direction-parameterized from_config reading cake_params interfaces
- validate_linux_cake() added to wanctl-check-config: validates cake_params structure, interfaces, overhead keywords, and tc binary with 14 TDD tests
- Transport-aware CakeStatsReader delegates to LinuxCakeBackend for linux-cake transport with per-tin CAKE stats in health endpoint
- Per-tin CAKE observability pipeline: 4 metrics registered in STORED_METRICS, batch writes in daemon gated on linux-cake transport, --tins flag in wanctl-history with pivoted table display
- VFIO passthrough active on odin: 4 NICs (2x i210, 2x i350) bound to vfio-pci, management X552 unaffected
- VM 206 (cake-shaper) running Debian 13 with 4 VFIO passthrough NICs: ens16/ens17 (i210 Spectrum), ens27/ens28 (i350 ATT)
- Two transparent L2 bridges (br-spectrum, br-att) configured via systemd-networkd with STP disabled, verified across reboot
- wanctl deployed to cake-shaper with CAKE qdiscs verified on ens17 (Spectrum) and ens28 (ATT) — JSON stats parseable
- linux-cake configs created for both WANs, baseline RRUL benchmarks captured: Spectrum 696 Mbps avg download (MikroTik ceiling to beat)
- ATT migrated to Linux CAKE on cake-shaper: +8.5% download, +97% upload, -3.8% latency vs MikroTik baseline
- Rollback proven organically during ATT cutover — bridge forwards L2 without CAKE, MikroTik queues re-enableable
- Full production cutover complete: both WANs on Linux CAKE, steering active, grade A bufferbloat
- Fixed 60x outlier rate underestimate in SIGP-01 via time-gap-aware normalization, updated MAX_WINDOW to 21, widened 4 config bounds stuck at limits
- pip-audit zero critical CVEs, 2 unused deps removed (cryptography + pyflakes), 8 orphaned fixtures cataloged, log rotation verified at 10MB/3 backups
- File permissions verified (31 items, 0 FAIL) and systemd exposure scores documented (8.4 EXPOSED for 3 runtime services) with prioritized hardening roadmap for Phase 115
- Enabled 8 new ruff categories (C901/SIM/PERF/RET/PT/TRY/ARG/ERA), resolved 839 findings via autofix + manual fix + triage, established complexity baseline for Phase 114
- Vulture 2.16 scan of 28,629 LOC identifying 0 true dead items at 80% confidence after whitelisting all 15 PITFALLS.md false positive patterns
- CAKE parameters verified correct for 4 qdiscs across 2 WANs; DSCP classification chain traced end-to-end from MikroTik mangle through transparent bridge to CAKE diffserv4 tins
- Confidence scoring audit with all 10 weights documented, timer match verified, CAKE-primary invariant confirmed; signal chain traced from reflector selection through Hampel/Fusion/EWMA to delta, with IRTT/ICMP/TCP paths and reflector scoring validated against production config
- Production CAKE queue statistics baseline: 0-60.9% memory across 4 qdiscs, zero backlog in GREEN state, 32mb memlimit confirmed appropriate
- Triaged all 96 except Exception catches: 88 safety nets, 5 bug-swallowing catches fixed with DEBUG logging
- MyPy strictness probe (5/5 leaf modules pass), complexity hotspot analysis with 8 extraction recommendations for v1.23, and import graph audit finding 2 safe TYPE_CHECKING-guarded cycles
- Thread safety audit of 10 files (24 shared state instances, 0 high-severity races) plus SIGUSR1 reload chain catalog with 10 E2E tests covering all 5 reload targets
- Hardened all 4 systemd units on production VM -- wanctl@ scored 2.1 OK and steering 1.9 OK (down from 8.4 EXPOSED), with circuit breaker config made consistent across all 3 runtime services
- Production dependency lock from live VM pip freeze (28 pinned packages) plus comprehensive backup/recovery runbook covering configs, metrics.db, VM snapshots, and Phase 115 rollback procedures
- Resource limits (MemoryMax/MemoryHigh/TasksMax/LimitNOFILE) applied to all runtime services from production observation, NIC tuning persistence confirmed across full VM reboot with all 4 services healthy post-boot
- AST-scanned 126 test files (3,888 tests), found 20 assertion-free tests (4 fixed), 0 tautological, 9 over-mocked (documented only)
- CONFIG_SCHEMA.md aligned with 6 missing config sections (storage, cake_params, fallback_checks, linux-cake transport, logging rotation, cake_optimization), 12 docs updated for VM architecture, container audit script archived
- Capstone v1.22 audit document aggregating 15 findings files across 5 phases: 87 findings identified, 34 resolved, 38 remaining debt (0 P0, 4 P1, 11 P2, 9 P3, 14 P4) with v1.23 recommendations

---

## v1.20 Adaptive Tuning (Shipped: 2026-03-19)

**Delivered:** Self-optimizing controller that learns optimal parameters from production metrics via 4-layer tuning rotation, with safety revert detection, signal processing optimization, and fusion baseline deadlock fix.

**Phases completed:** 98-103 (13 plans total)

**Key accomplishments:**

- Self-optimizing tuning engine with per-WAN analysis, SIGUSR1 toggle, SQLite persistence, and health endpoint visibility (Phase 98)
- Congestion threshold calibration deriving target/warn bloat from GREEN-state RTT delta percentiles with convergence detection (Phase 99)
- Safety & revert system monitoring post-adjustment congestion rate with automatic rollback and hysteresis locks (Phase 100)
- Signal processing tuning: Hampel sigma/window and EWMA alpha optimized per-WAN via 4-layer round-robin rotation (Phase 101)
- Advanced tuning: fusion weight, reflector min_score, baseline bounds auto-adjusted from signal reliability (Phase 102)
- Fusion baseline deadlock fix: signal path split — fused RTT for load EWMA, ICMP-only for baseline EWMA (Phase 103)

**Stats:**

- 6 phases, 13 plans
- 112 commits, 41 files changed
- +8,534 / -184 lines changed
- ~265 new tests (3,458 to ~3,723)
- 28,629 LOC Python (src/)
- 3 days (2026-03-18 to 2026-03-20)

**Git range:** `v1.19..v1.20`

**What's next:** v1.21 planning.

---

## v1.19 Signal Fusion (Shipped: 2026-03-18)

**Delivered:** Dual-signal fusion engine combining ICMP and IRTT RTT measurements for congestion control, with reflector quality scoring, OWD asymmetric congestion detection, IRTT loss alerting, and zero-downtime SIGUSR1 toggle.

**Phases completed:** 93-97 (9 plans total)

**Key accomplishments:**

- Reflector quality scoring with rolling deques, automatic deprioritization of unreliable ping_hosts, and periodic recovery probes with graceful degradation (3/2/1/0 active hosts)
- OWD asymmetric congestion detection from IRTT burst-internal send_delay vs receive_delay ratios (no NTP dependency), with SQLite persistence
- IRTT sustained loss alerting (upstream/downstream) via AlertEngine with per-event cooldown and Discord notifications
- Dual-signal fusion engine: weighted ICMP+IRTT average (\_compute_fused_rtt) as congestion control input, with multi-gate fallback (thread/result/freshness/validity)
- Fusion safety gate: ships disabled by default (fusion.enabled: false) with SIGUSR1 zero-downtime toggle — first reload capability in autorate daemon
- Full health endpoint fusion visibility (enabled/disabled state, active weights, signal sources, fused RTT values)

**Stats:**

- 5 phases, 9 plans
- 40 commits, 86 files changed
- +6,437 / -8,547 lines changed
- ~202 new tests (3,256 to ~3,458)
- 26,098 LOC Python (src/)
- ~18 hours (2026-03-17 to 2026-03-18)

**Git range:** `docs(95): capture phase context` to `docs: add config sections`

**What's next:** v1.19 deploy + fusion graduation, then v1.20 planning.

---

## v1.18 Measurement Quality (Shipped: 2026-03-17)

**Delivered:** RTT signal quality improvements with Hampel outlier filtering, IRTT UDP measurements via background thread, protocol correlation, container networking audit, and full observability.

**Phases completed:** 88-92 (10 plans total)

**Key accomplishments:**

- Hampel outlier filter with jitter/variance EWMA and confidence scoring in observation mode
- IRTT UDP RTT measurement via subprocess wrapper with JSON parsing and graceful fallback
- Background IRTT daemon thread with lock-free caching (frozen dataclass + GIL atomic swap)
- ICMP vs UDP protocol correlation with deprioritization detection
- Container networking audit confirmed 0.17ms overhead (negligible, report-only closure)
- Health endpoint signal_quality + irtt sections with SQLite persistence for both
- 363 new tests (2,893 to 3,256), 21/21 requirements satisfied

---

## v1.17 CAKE Optimization & Benchmarking (Shipped: 2026-03-16)

**Delivered:** Automated CAKE queue type parameter detection and optimization via `wanctl-check-cake --fix`, plus RRUL bufferbloat benchmarking with A-F grading, SQLite storage, and before/after comparison.

**Phases completed:** 84-87 (8 plans total)

**Key accomplishments:**

- Sub-optimal CAKE parameter detection via REST API (`GET /rest/queue/type`) with severity, rationale, and diff output for link-independent and link-dependent params
- Auto-fix CAKE parameters via `--fix` flag with daemon lock check, JSON snapshot rollback, interactive confirmation, and REST PATCH to `/rest/queue/type/{id}`
- RRUL bufferbloat benchmarking via `wanctl-benchmark` wrapping flent with A+-F grading, P50/P95/P99 latency percentiles, and throughput reporting
- Benchmark result storage in SQLite with auto-store, before/after comparison (`wanctl-benchmark compare`), and history with time-range filtering
- Full operator loop validated in production: check-cake → fix → benchmark → compare on both Spectrum and ATT WANs
- CAKE params optimized on both WANs (nat, ack-filter, wash), ATT overhead corrected (pppoe-ptm → bridged-ptm)

**Stats:**

- 4 phases, 8 plans
- 59 commits, 87 files changed
- +20,534 / -1,135 lines changed
- 70 new tests (2,823 to 2,893)
- 24,056 LOC Python (src/)
- 3 days (2026-03-13 to 2026-03-16)

**Git range:** `v1.16..v1.17`

**What's next:** v1.18 Measurement Quality — IRTT integration, container networking optimization, RTT signal quality improvements.

---

## v1.16 Validation & Operational Confidence (Shipped: 2026-03-13)

**Delivered:** Operator-facing CLI tools that catch misconfigurations before runtime and verify router queue state matches expectations.

**Phases completed:** 81-83 (4 plans total)

**Key accomplishments:**

- `wanctl-check-config` CLI tool for offline config validation with 6 categories (schema, cross-field, unknown keys, paths, env vars, deprecated params)
- Auto-detection of config type (autorate vs steering) from YAML contents without `--type` flag
- Steering-specific validation with cross-config topology checks (primary_wan_config path existence, wan_name match)
- JSON output mode (`--json`) for CI/scripting integration with structured category/severity/suggestion output
- `wanctl-check-cake` CLI tool for live router CAKE queue audit (connectivity, queue tree, CAKE type, max-limit diff, mangle rules)
- Reusable CheckResult/Severity data model shared between both CLI tools

**Stats:**

- 3 phases, 4 plans
- 32 commits
- 157 new tests (2,666 to 2,823)
- 22,180 LOC Python (src/)
- 2 days (2026-03-12 to 2026-03-13)

**Git range:** `v1.15..v1.16`

**What's next:** Next milestone planning.

---

## v1.15 Alerting & Notifications (Shipped: 2026-03-12)

**Delivered:** Proactive alerting system with Discord webhook delivery, per-event cooldown suppression, and 7 alert types covering congestion, steering, connectivity, and anomaly events.

**Phases completed:** 76-80 (10 plans total)

**Key accomplishments:**

- AlertEngine embedded in both daemons with per-event (type, WAN) cooldown suppression and SQLite persistence, disabled by default
- Discord webhook delivery with color-coded severity embeds (red/yellow/green), retry with exponential backoff, and extensible AlertFormatter Protocol
- Sustained congestion detection with independent DL/UL timers, zone-dependent severity (RED=critical, SOFT_RED=warning), and recovery gate
- Steering transition alerts tracking activation/recovery with duration, confidence score, and WAN context
- WAN offline/recovery detection, baseline RTT drift alerts (>25% deviation), and congestion zone flapping detection (6+ transitions in 5min)
- Health endpoint alerting section (enabled, fire_count, active_cooldowns) and `wanctl-history --alerts` CLI with time-range filtering

**Stats:**

- 5 phases, 10 plans
- 31 commits
- 221 new tests (2,445 to 2,666)
- 20,140 LOC Python (src/)
- 1 day (2026-03-12)

**Git range:** `v1.14..v1.15`

**What's next:** Next milestone planning.

---

## v1.14 Operational Visibility (Shipped: 2026-03-11)

**Delivered:** Full TUI dashboard (`wanctl-dashboard`) for real-time monitoring and historical analysis of both WAN links with adaptive layout and terminal compatibility.

**Phases completed:** 73-75 (7 plans total)

**Key accomplishments:**

- Full TUI dashboard with live per-WAN panels showing color-coded congestion state, DL/UL rates, RTT baseline/load/delta, and router connectivity
- Async dual-poller engine with independent endpoint backoff and offline isolation for multi-container WAN monitoring
- Sparkline trend widgets (DL/UL with green-to-yellow gradient, RTT delta with green-to-red) using bounded deques for constant memory
- Cycle budget gauge showing 50ms utilization percentage from health endpoint data
- Historical metrics browser with time range selector (1h/6h/24h/7d), DataTable, and client-side summary stats (min/max/avg/p95/p99)
- Responsive layout: side-by-side at >=120 cols, stacked below, with 0.3s resize hysteresis
- Terminal compatibility: --no-color, --256-color CLI flags, tmux/SSH verified

**Stats:**

- 3 phases, 7 plans
- 51 commits, 71 files changed
- +10,425 / -1,247 lines changed
- 145 new dashboard tests (2,300 to 2,445)
- 1,289 LOC dashboard module, 18,393 LOC total (src/)
- 1 day (2026-03-11)

**Git range:** `v1.13..v1.14`

**What's next:** Next milestone planning.

---

## v1.13 Legacy Cleanup & Feature Graduation (Shipped: 2026-03-11)

**Delivered:** Legacy code removal, config fallback retirement with deprecation warnings, and graduation of both confidence-based steering and WAN-aware steering from dry-run/disabled to production-live.

**Phases completed:** 67-72 (10 plans total)

**Key accomplishments:**

- Production config audit confirmed all active configs use modern parameters exclusively — zero legacy fallbacks exercised
- Dead code eliminated: cake_aware mode branching removed (119 lines), 7 obsolete ISP-specific config files deleted, CAKE three-state is now sole code path
- Centralized `deprecate_param()` helper with warn+translate for 8 legacy config parameters — old names produce clear deprecation warnings
- SIGUSR1 generalized hot-reload: single signal toggles both `dry_run` and `wan_state.enabled` without daemon restart
- Confidence-based steering graduated from dry-run to live mode with production-verified SIGUSR1 rollback path
- WAN-aware steering enabled in production with 4-step degradation verification (stale fallback, SIGUSR1 rollback, grace period re-trigger)

**Stats:**

- 6 phases, 10 plans
- 53 commits, 57 files changed
- +6,408 / -715 lines changed
- 37 new tests (2,263 to 2,300)
- 17,095 LOC Python (src/)
- 1 day (2026-03-11)

**Git range:** `v1.12..v1.13`

**What's next:** Next milestone planning.

---

## v1.12 Deployment & Code Health (Shipped: 2026-03-11)

**Delivered:** Deployment alignment, dead code removal, security hardening, fragile area stabilization, and infrastructure consolidation for production hygiene.

**Phases completed:** 62-66 (7 plans total)

**Key accomplishments:**

- Deployment artifacts (Dockerfile, install.sh, deploy.sh) aligned with pyproject.toml as single source of truth, version bumped to 1.12.0
- Dead code removed: pexpect dependency eliminated, dead subprocess import and stale timeout_total API cleaned from RTT measurement
- Security hardened: router password cleared after client construction, SSL warnings scoped per-request, safe fallback gateway default, integration test hosts parameterized
- Fragile areas stabilized: state file schema contract tests catch key renames, check_flapping side-effect contract documented, WAN config warnings at proper level
- Config boilerplate consolidated: 6 common fields extracted to BaseConfig, eliminating duplicate YAML-to-attribute loading across both daemons
- Infrastructure validated: RotatingFileHandler for log rotation (10MB/3 backups), 17 Dockerfile/dependency contract tests parametrized from pyproject.toml

**Stats:**

- 5 phases, 7 plans
- 53 new tests (2,210 to 2,263)
- 16,993 LOC Python (src/)
- 2 days (2026-03-10 to 2026-03-11)

**Git range:** `v1.11..v1.12`

**What's next:** Next milestone planning.

---

## v1.11 WAN-Aware Steering (Shipped: 2026-03-10)

**Delivered:** WAN-aware steering that fuses autorate congestion zone into confidence scoring, with fail-safe defaults, YAML configuration, and full observability.

**Phases completed:** 58-61 (8 plans total)

**Key accomplishments:**

- Autorate state file exports congestion zone (dl_state/ul_state) with dirty-tracking exclusion preventing write amplification
- WAN zone fused into confidence scoring (WAN_RED=25, WAN_SOFT_RED=12) — CAKE-primary invariant enforced (WAN alone < steer_threshold)
- Fail-safe defaults at every boundary: stale zone (>5s) defaults GREEN, autorate unavailable skips WAN weight, 30s startup grace period
- YAML `wan_state:` configuration with warn+disable graceful degradation, ships disabled by default
- Full observability: health endpoint `wan_awareness` section, 3 SQLite metrics (zone/weight/staleness), WAN context in steering transition and degrade timer logs

**Stats:**

- 16 files modified
- +2,437 / -78 lines changed
- 4 phases, 8 plans, 56 commits
- 101 new tests (2,109 to 2,210)
- 16,880 LOC Python (src/)
- 2 days (2026-03-09 to 2026-03-10)

**Git range:** `v1.10..v1.11`

**What's next:** Next milestone planning.

---

## v1.10 Architectural Review Fixes (Shipped: 2026-03-09)

**Delivered:** Hot-loop fixes, steering reliability, operational resilience, codebase audit, and test quality improvements from senior architectural review.

**Phases completed:** 50-57 (14 plans executed, 1 superseded)

**Key accomplishments:**

- Hot-loop blocking delays eliminated (sub-cycle retries, 50ms max per attempt)
- Self-healing transport failover with periodic primary REST re-probe (30-300s backoff)
- SSL verify_ssl=True default across all layers, SQLite corruption auto-recovery, disk space monitoring
- Daemon duplication consolidated (daemon_utils.py, perf_profiler.py), systematic codebase audit
- Test fixture consolidation (-481 lines), 24 new behavioral/integration tests
- 27/27 requirements satisfied, 6/6 E2E flows verified

---

## v1.9 Performance & Efficiency (Shipped: 2026-03-07)

**Delivered:** Profiling-driven cycle optimization with icmplib raw ICMP sockets, per-subsystem telemetry, and health endpoint cycle budget visibility.

**Phases completed:** 47-49 (6 plans total)

**Key accomplishments:**

- Instrumented both daemons with per-subsystem PerfTimer hooks and OperationProfiler accumulation (8 labeled timers)
- Replaced subprocess.run(["ping"]) with icmplib raw ICMP sockets, reducing Spectrum avg cycle by 3.4ms (8.3%) and ATT by 2.1ms (6.8%)
- Added structured DEBUG logging with per-subsystem timing and rate-limited overrun detection
- Exposed cycle_budget telemetry (avg/P95/P99, utilization %, overrun count) in both health endpoints via shared \_build_cycle_budget() helper
- Updated profiling analysis pipeline for 50ms budget context with P50 percentile and --budget CLI flag

**Stats:**

- 16 files modified
- +2,532 / -538 lines changed
- 3 phases, 6 plans, 39 commits
- 97 new tests (1,881 to 1,978)
- 16,136 LOC Python (src/)
- 1 day (2026-03-06)

**Git range:** `feat(47-01)` → `docs(phase-49)`

**What's next:** Next milestone planning.

---

## v1.8 Resilience & Robustness (Shipped: 2026-03-06)

**Delivered:** Error recovery, fail-safe behavior, and graceful shutdown for production reliability.

**Phases completed:** 43-46 (8 plans total, Phase 46 deferred)

**Key accomplishments:**

- Router error detection and reconnection with 6 failure categories and rate-limited logging
- Fail-closed rate queuing with 60s stale threshold and monotonic timestamps
- Watchdog continues on router failures, stops on auth failures
- Graceful shutdown with bounded cleanup deadlines and state persistence
- Coverage recovery to 91%+ after test pollution fix

**Stats:**

- 4 phases (including 44.1 inserted), 8 plans
- 154 new tests (1,727 to 1,881)
- ~1 month (2026-01-29 to 2026-03-06)

**Git range:** `feat(43-01)` → `docs(phase-45)`

**What's next:** v1.9 Performance & Efficiency milestone.

---

## v1.7 Metrics History (Shipped: 2026-01-25)

**Delivered:** SQLite metrics storage with automatic downsampling, CLI tool, and HTTP API for historical metrics access.

**Phases completed:** 38-42 (8 plans total)

**Key accomplishments:**

- SQLite storage layer (8 modules, 1,038 lines) with schema versioning
- Both daemons record metrics each cycle (<5ms overhead)
- `wanctl-history` CLI tool for querying metrics
- `/metrics/history` HTTP API endpoint
- Automatic startup maintenance (cleanup, downsample)

**Stats:**

- 5 phases, 8 plans
- 237 new tests (1,490 to 1,727)
- 1 day (2026-01-25)

**Git range:** `feat(38-01)` → `docs(42)`

**What's next:** v1.8 Resilience & Robustness milestone.

---

## v1.6 Test Coverage 90% (Shipped: 2026-01-25)

**Delivered:** Comprehensive test coverage from 45.7% to 90.08% with CI enforcement.

**Phases completed:** 31-37 (17 plans total)

**Key accomplishments:**

- Coverage increased from 45.7% to 90.08% (target: 90%)
- 743 new tests added (747 to 1,490 total)
- CI enforcement via fail_under=90 in pyproject.toml
- All major modules tested: backends, state, metrics, controllers, CLI tools

**Stats:**

- 7 phases, 17 plans
- 743 new tests
- 2 days (2026-01-25)

**Git range:** `feat(31-01)` → `docs(37)`

**What's next:** v1.7 Metrics History milestone.

---

## v1.5 Quality & Hygiene (Shipped: 2026-01-24)

**Delivered:** Code quality infrastructure with test coverage measurement, security scanning, and documentation verification.

**Phases completed:** 27-30 (8 plans total)

**Key accomplishments:**

- Established test coverage infrastructure (pytest-cov, 72% baseline, HTML reports, README badge)
- Verified codebase cleanliness (zero dead code, zero TODOs, complexity analysis for 11 functions)
- Standardized documentation to v1.4.0 (6 files updated, 14 doc issues fixed)
- Achieved security posture (zero CVEs, 4 security tools, `make security` target)

**Stats:**

- 20+ files modified
- ~13,273 lines of Python (src/)
- 4 phases, 8 plans
- 747 tests, 72% coverage
- 1 day (2026-01-24)

**Git range:** `chore(27-01)` → `docs(30): complete`

**What's next:** Next milestone planning.

---

## v1.4 Observability (Shipped: 2026-01-24)

**Delivered:** HTTP health endpoint for steering daemon enabling external monitoring and container orchestration.

**Phases completed:** 25-26 (4 plans total)

**Key accomplishments:**

- Created steering daemon HTTP health endpoint on port 9102 with JSON responses
- Implemented 200/503 status codes for Kubernetes probe compatibility
- Exposed live steering state: confidence scores, congestion states, decision timestamps
- Integrated health server lifecycle with daemon (start/stop automatically)
- Added 28 tests covering all 14 requirements (HLTH-_, STEER-_, INTG-\*)
- Achieved 100% requirement coverage with zero tech debt

**Stats:**

- 14 files modified
- +2,375 lines changed
- 2 phases, 4 plans
- 28 new tests (725 → 752)
- 1 day (2026-01-24)

**Git range:** `feat(25-01)` → `docs(26-02)`

**What's next:** Deploy to production, integrate with monitoring dashboards.

---

## v1.3 Reliability & Hardening (Shipped: 2026-01-21)

**Delivered:** Safety invariant test coverage, deployment validation, and production wiring for REST-to-SSH failover.

**Phases completed:** 21-24 (5 plans total)

**Key accomplishments:**

- Implemented FailoverRouterClient with automatic REST-to-SSH failover (16 tests)
- Proved baseline RTT freeze invariant under 100+ cycles of sustained load (5 tests)
- Proved state file corruption recovery across 12 distinct failure scenarios
- Created 423-line deployment validation script (config, router, state checks)
- Hardened deploy.sh with fail-fast on missing steering.yaml
- Wired safety features into all 3 production entry points

**Stats:**

- 11 files modified
- +1,526 lines changed
- 4 phases, 5 plans
- 54 new tests (671 → 725)
- 1 day (2026-01-21)

**Git range:** `test(21-01)` → `docs(24): complete`

**What's next:** Monitor production failover behavior, consider Phase2BController enablement.

---

## v1.2 Configuration & Polish (Shipped: 2026-01-14)

**Delivered:** Phase2B confidence-based steering enabled in dry-run mode, configuration documentation and validation improvements.

**Phases completed:** 16-20 (5 plans total)

**Key accomplishments:**

- Fixed Phase2B timer interval to use cycle_interval instead of hardcoded 2s
- Documented baseline_rtt_bounds in CONFIG_SCHEMA.md with validation
- Added deprecation warnings for legacy steering params (bad_samples, good_samples)
- Added 77 edge case tests for config validation (boundary lengths, Unicode attacks, numeric boundaries)
- Enabled Phase2B confidence scoring in production with dry_run=true for safe validation

**Stats:**

- 9 commits
- ~22,065 lines of Python
- 5 phases, 5 plans
- 77 new tests (594 → 671)
- 1 day (2026-01-14)

**Git range:** `fix(phase2b)` → `docs(20-01)`

**What's next:** Monitor Phase2B dry-run validation (1 week), then set dry_run=false for live confidence-based steering.

---

## v1.1 Code Quality (Shipped: 2026-01-14)

**Delivered:** Systematic code quality improvements through refactoring, consolidation, and documentation while preserving production stability.

**Phases completed:** 6-15 (34 plans total)

**Key accomplishments:**

- Created signal_utils.py and systemd_utils.py shared modules, eliminating ~110 lines of duplicated code
- Consolidated 4 redundant utility modules (~350 lines removed), reducing module fragmentation
- Documented 12 refactoring opportunities in CORE-ALGORITHM-ANALYSIS.md with risk assessment and protected zones
- Refactored WANController (4 methods extracted) and SteeringDaemon (5 methods extracted) from run_cycle()
- Unified state machine methods (CAKE-aware + legacy) in SteeringDaemon
- Integrated Phase2BController confidence scoring with dry-run mode for safe production validation

**Stats:**

- 100 commits
- ~20,960 lines of Python
- 10 phases, 34 plans
- 120 new tests (474 → 594)
- 1 day (2026-01-13 to 2026-01-14)

**Git range:** `feat(06-01)` → `docs(15-06)`

**What's next:** Production validation of Phase2BController confidence scoring, then next milestone planning.

---

## v1.0 Performance Optimization (Shipped: 2026-01-13)

**Delivered:** 40x performance improvement (2s → 50ms cycle time) through interval optimization and event loop architecture.

**Phases completed:** 1-5 (8 plans total, 2 skipped/pre-implemented)

**Key accomplishments:**

- Profiled measurement infrastructure: discovered 30-41ms cycles (2-4% of budget), not ~200ms as assumed
- Converted timer-based execution to persistent event loop architecture
- Reduced cycle interval from 2s to 50ms (40x faster congestion response)
- Preserved EWMA time constants via alpha scaling
- Validated 50ms interval under RRUL stress testing
- Documented findings in PRODUCTION_INTERVAL.md

**Stats:**

- Phases 1-3 active, Phases 4-5 pre-implemented
- 352,730 profiling samples analyzed
- Sub-second congestion detection (50-100ms response)
- 0% router CPU at idle, 45% peak under load

**Git range:** `feat(01-01)` → `docs(03-02)`

**What's next:** v1.1 Code Quality milestone (systematic refactoring).

---
