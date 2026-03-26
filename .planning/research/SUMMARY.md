# Project Research Summary

**Project:** wanctl v1.23 Self-Optimizing Controller
**Domain:** Production 24/7 Linux CAKE autorate daemon — performance, observability, and adaptive control enhancements
**Researched:** 2026-03-26
**Confidence:** HIGH

## Executive Summary

v1.23 extends a mature, production-running CAKE autorate system with four targeted improvements: replacing subprocess `tc` calls with pyroute2 netlink (10x latency reduction per call), adding automatic fusion healing for ICMP/IRTT correlation divergence, extending the adaptive tuning engine to cover response parameters (step_up, factor_down, green_cycles_required), and exposing metrics via Prometheus for Grafana dashboards. All four features build on infrastructure already present in the codebase — there are no architectural pivots, only carefully bounded additions. Two new runtime dependencies are justified: `pyroute2>=0.9.5` (zero transitive deps, CAKE netlink verified in source tree) and `prometheus_client>=0.21.0` (optional import, for export only).

The recommended approach is strictly additive: new backend class alongside existing subprocess backend, optional Prometheus dependency guarded by ImportError, new RESPONSE_LAYER appended to the existing 4-layer tuning rotation, and configurable retention thresholds parameterizing existing hardcoded constants. The system is production-critical (24/7, 50ms control loop, direct WAN connectivity impact), so implementation policy is unchanged from prior milestones: test coverage, safety bounds, revert detection, and staged deployment. The existing codebase already provides all the scaffolding — safety.py revert detection, tuning_params persistence, LinuxCakeAdapter backend indirection, health endpoint threading model — so each phase is an extension, not a rewrite.

The primary risks concentrate in two phases. The pyroute2 phase requires proof-of-concept validation that CAKE `tc("change")` netlink attribute encoding works correctly before any hot-loop integration — getting TCA_CAKE_BASE_RATE64 encoding wrong silently fails. The adaptive rate step phase has the highest blast radius of any v1.23 feature because step_up, factor_down, and green_cycles_required interact multiplicatively: wrong combination causes oscillation or bandwidth collapse within minutes. Stability constraints — tune only one response parameter per hourly cycle, oscillation lockout that freezes all response params for 24h, tighter max_step_pct (5% vs 10% for detection params) — must be designed before any code is written for that phase.

## Key Findings

### Recommended Stack

The existing stack requires exactly two new package dependencies and no framework changes. `pyroute2>=0.9.5` (pure Python, zero transitive deps, Apache 2.0 / GPL 2.0) provides verified CAKE netlink support — `sched_cake.py` confirmed in `pyroute2/netlink/rtnl/tcmsg/` with TCA_CAKE_BASE_RATE64 and 17 other CAKE TCA attributes, per-tin stats decoder (PR #662, merged 2020), `tc("change")` and `tc("replace")` both in the command_map. `prometheus_client>=0.21.0` (official Prometheus project, zero mandatory deps, Apache 2.0) provides Gauge/Counter types, CustomCollector pattern, start_http_server, and generate_latest. Critically, the Debian 12 system package `python3-pyroute2` is v0.7.2 (too old for reliable CAKE stats support); both packages must be installed into the venv via uv. No Grafana Python library is needed — the dashboard is a committed JSON file.

One open version conflict: STACK.md recommends pyroute2 0.9.5 (latest) while ARCHITECTURE.md recommends pinning to the 0.7.x branch (thread-based, synchronous). This must be resolved at Phase 1 planning by verifying whether pyroute2 0.9.x introduces async behavior in synchronous usage contexts.

**Core technologies:**

- `pyroute2>=0.9.5`: replaces subprocess `tc` in LinuxCakeBackend — eliminates 3ms fork/exec overhead per call, frees ~5ms/cycle (10% of 50ms budget)
- `prometheus_client>=0.21.0`: Prometheus exposition layer — optional import guard preserves zero-dep core; optional dependency in pyproject.toml
- Grafana dashboard JSON: no Python dep — hand-crafted JSON in `grafana/` directory, provisioned via YAML
- Adaptive rate steps, fusion healing, retention strategy: no new libraries — all extend existing modules

### Expected Features

**Must have (table stakes for v1.23):**

- pyroute2 netlink tc calls — reclaims ~10% of cycle budget; subprocess path becomes tech debt at 20Hz
- Auto-fusion healing — ATT WAN has known ICMP/IRTT path divergence; manual SIGUSR1 toggle is ongoing operator burden
- Prometheus/Grafana export — metrics are SQLite-only today; no dashboard capability without manual data extraction
- metrics.db retention strategy — 3.5GB steady state at 7-day retention; aggressive downsampling is safe once Prometheus holds long-term data

**Should have (differentiators):**

- Adaptive rate step tuning — only CAKE controller that tunes its own response parameters; closes the last gap in the self-optimizing vision
- Per-tin Prometheus metrics with labels — enables Grafana panels showing which CAKE traffic class is congested; fixed cardinality (2 WANs x 2 directions x 4 tins = 16 series per metric)
- Fused metrics export (SQLite + Prometheus dual-write) — SQLite remains authoritative for tuning; Prometheus Gauges are in-memory, zero contention

**Defer to v2+:**

- Push-gateway / remote-write bridge — pull model works if Prometheus is on same VLAN; adds complexity without clear benefit
- ML-based bandwidth prediction — statistical tuning is already the adaptive learning system; ML adds complexity with no measurable gain at this scale
- Auto-tuning ceiling_mbps from speed tests — policy decision, not a measurement; saturating the link disrupts latency-sensitive traffic

### Architecture Approach

v1.23 is a set of parallel, non-blocking integration points on the existing architecture. The 50ms hot loop changes only at the tc call site (subprocess -> pyroute2 netlink) and fusion decision point (check heal state before weighting IRTT). Adaptive rate steps extend the hourly tuning engine by appending a RESPONSE_LAYER to the existing 4-layer round-robin — no changes to the scheduler or safety infrastructure. Prometheus export runs in a daemon thread as a CustomCollector that reads WANController attributes on each scrape — zero overhead added to the hot loop. Retention thresholds become configurable YAML rather than hardcoded constants.

**Major components and changes:**

1. `NetlinkCakeBackend` (NEW) — new `RouterBackend` subclass alongside `LinuxCakeBackend`; config selects via transport name; singleton `IPRoute()` instance; reconnect on socket death
2. `WANController._check_protocol_correlation` + `_compute_fused_rtt` (MODIFIED) — add fusion heal state machine (ACTIVE/SUSPENDED/RECOVERING), ~50 lines of new state tracking
3. `TuningEngine` (MODIFIED) — append RESPONSE_LAYER as 5th layer; new `tuning/strategies/response_tuning.py`; `_apply_tuning_to_controller` extended for `dl_`/`ul_`-prefixed step params
4. `PrometheusExporter` (NEW) — daemon thread on port 9103; CustomCollector reads live `WANController` state on each Prometheus scrape
5. `storage/downsampler.py` + `storage/retention.py` (MODIFIED) — accept configurable thresholds from new `storage.retention` YAML section instead of hardcoded constants

### Critical Pitfalls

1. **pyroute2 IPRoute socket leak in the 50ms hot loop** — `with IPRoute()` per call leaks fds at 2,400 socket cycles/minute; create singleton `IPRoute()` at `__init__`, reconnect on EBADF/BrokenPipeError; verify fd count is stable over 1h soak via `lsof -p <pid> | grep netlink | wc -l`

2. **Adaptive rate step tuning creates oscillation or collapse** — step_up, factor_down, and green_cycles interact multiplicatively (combined-gain invariant); tune only one response parameter per hourly cycle; add oscillation lockout (transitions/minute threshold freezes all response params for 24h); use `exclude_params` to make response tuning opt-in; max_step_pct 5% (vs 10% for detection params)

3. **Downsampling deletes data the tuner needs** — if 1m retention shrinks below `tuning.lookback_hours * 3600 seconds`, tuner silently uses sparse data; add config validation enforcing the contract; `measure_congestion_rate()` in safety.py also queries 1m granularity — if that data is gone, revert detection stops working

4. **Prometheus /metrics endpoint blocks the 50ms control loop** — `generate_latest()` acquires a global lock and takes 2-5ms to serialize 30+ metrics; never call `Gauge.set()` from the hot loop; use CustomCollector pattern (read state on scrape, not push from cycle); run on separate port 9103 in its own thread

5. **Auto-fusion healing disables fusion during legitimate ISP path divergence** — low protocol correlation can mean congestion on one path (disable fusion) OR permanent ISP ICMP deprioritization (keep fusion, adjust weights); require 30+ minutes sustained divergence before auto-disable; implement 3-state model (enabled/degraded/suspended); send Discord alert on state change

## Implications for Roadmap

FEATURES.md, ARCHITECTURE.md, and PITFALLS.md independently converge on the same 5-phase structure, ordered by dependency risk and blast radius. All phases are additive — nothing is replaced until the replacement is validated.

### Phase 1: pyroute2 Netlink Backend

**Rationale:** Fully independent of all other v1.23 features; validates the most uncertain integration (kernel netlink CAKE attribute encoding) while all other systems remain unchanged. Architecture research specifies `NetlinkCakeBackend` as a new subclass alongside `LinuxCakeBackend` — zero production risk during development. Must come first because it is the most complex testing challenge.
**Delivers:** `NetlinkCakeBackend` class; singleton `IPRoute()` lifecycle; reconnect logic on socket death; `tc("replace")` for initialize_cake and `tc("change")` for runtime bandwidth; netlink-based `get_queue_stats()` replacing subprocess JSON parse; exception handler matching existing `(returncode, stdout, stderr)` return contract; factory registration for `linux-cake-netlink` transport
**Addresses:** pyroute2 netlink feature (P1 table stake); CAKE per-tin stats via netlink
**Avoids:** IPRoute socket leak (Pitfall 1); CAKE netlink attribute mismatch (Pitfall 2); netlink exception crash loop (Pitfall 3)
**Research flag:** Proof-of-concept validation REQUIRED before hot-loop integration — write standalone script verifying `ipr.tc("change", "cake", ifindex, bandwidth="Nkbit")` actually changes bandwidth and reads back correctly via `tc -j qdisc show`. Also resolve pyroute2 version conflict (0.9.x vs 0.7.x) before starting.

### Phase 2: Metrics.db Retention Strategy

**Rationale:** Small scope, low risk, must be resolved before Prometheus (Prometheus-mode aggressive thresholds depend on this config design). More importantly, must explicitly coordinate retention thresholds with tuner lookback to avoid Pitfall 3. Ship before adaptive tuning and Prometheus so the data availability contract is proven.
**Delivers:** Configurable retention thresholds via `storage.retention` YAML section (raw_age_seconds, aggregate_1m_age_seconds, aggregate_5m_age_seconds); config validation rule enforcing `tuning.lookback_hours * 3600 <= aggregate_1m_age_seconds`; `prometheus_compensated: true` opt-in for aggressive retention; steady-state DB size ~1GB vs current ~3.5GB
**Addresses:** metrics.db retention feature (P1 table stake)
**Avoids:** Downsampling deletes tuner data (Pitfall 3); without this phase, operators reducing retention for Prometheus compatibility would silently break tuner data availability
**Research flag:** Standard patterns — parameterizing existing constants; no new algorithms; skip research-phase

### Phase 3: Auto-Fusion Healing

**Rationale:** Self-contained WANController change; addresses known ATT ICMP/IRTT path divergence production issue; no dependency on other v1.23 phases. Ships after pyroute2 to avoid concurrent system changes during netlink validation.
**Delivers:** Fusion heal state machine (ACTIVE/SUSPENDED/RECOVERING) co-located in `_check_protocol_correlation` and `_compute_fused_rtt`; configurable thresholds (suspend_threshold, recovery_threshold) under `fusion.auto_heal` YAML section; Discord alert on state transitions; `fusion.heal_state` field in health endpoint; auto-re-enable after correlation recovers; parameter lock on `fusion_icmp_weight` in TuningEngine when healer suspends
**Addresses:** Auto-fusion healing feature (P1 table stake)
**Avoids:** Fusion auto-disable false positive (Pitfall 5); auto-fusion vs tuner conflict (integration gotcha — must lock fusion_icmp_weight in tuner when healer suspends)
**Research flag:** Production calibration required — suspend_threshold and recovery_threshold must be validated against actual ATT divergence data before enabling auto-disable; review production logs for correlation ratio distribution during known divergence periods

### Phase 4: Adaptive Rate Step Tuning

**Rationale:** Highest blast radius of any v1.23 feature; requires stable pyroute2 backend (Phase 1 — cycle budget headroom) and proven retention config (Phase 2 — data availability) before adding tuning complexity. Architecture and pitfalls research are explicit: stability constraints must be designed before any code is written. Ships fourth.
**Delivers:** RESPONSE_LAYER as 5th entry in `ALL_LAYERS` tuning rotation; `tuning/strategies/response_tuning.py` with `tune_step_up`, `tune_factor_down`, `tune_green_required`; oscillation lockout that freezes all response params when transitions/minute exceeds threshold; combined-gain invariant validation before any parameter application; `dl_`/`ul_`-prefixed param names in `tuning_params` table; `_apply_tuning_to_controller` extension; `exclude_params` opt-in (response tuning disabled by default)
**Addresses:** Adaptive rate step tuning feature (P2 should-have); closes last gap in self-optimizing vision
**Avoids:** Rate step oscillation/collapse (Pitfall 2 — critical); depends on Phase 2 retention for 1m data availability in strategy lookback
**Research flag:** Strategy logic needs deeper design — objective function for detecting oscillation vs slow recovery from downsampled 1m metrics may require in-process episode tracking rather than SQLite lookback (sub-hour oscillation events are lost at 1m granularity). Budget design iteration time in Phase 4 planning.

### Phase 5: Prometheus/Grafana Export

**Rationale:** Highest dependency count — prometheus_client library, stable metric schema, retention config from Phase 2, all other subsystems stable. Additive observability — existing HealthServer and SQLite remain authoritative. Ships last because it benefits from observing all prior phases in dashboards during development.
**Delivers:** `PrometheusExporter` module; port 9103 daemon thread (same pattern as HealthServer); `WanctlCollector` CustomCollector reading live `WANController` state on scrape; 15 metric families with stable labels (wan, direction, tin); Grafana dashboard JSON (`grafana/dashboards/wanctl-overview.json`); provisioning YAML (`grafana/provisioning/`); optional dependency (`pip install wanctl[prometheus]`); `PROMETHEUS_DISABLE_CREATED_SERIES=True` to reduce metric count
**Addresses:** Prometheus/Grafana export feature (P1 table stake); per-tin metrics with labels (P2 differentiator); enables metrics.db aggressive retention (Phase 2 prometheus_compensated mode)
**Avoids:** Prometheus blocking hot loop (Pitfall 4 — CustomCollector, never Gauge.set() in cycle); label explosion (Pitfall 7 — stable labels reviewed upfront); security exposure (bind 127.0.0.1 or management VLAN, not 0.0.0.0)
**Research flag:** Standard patterns — CustomCollector, start_http_server, daemon thread model all well-documented in prometheus_client; skip research-phase. Review label design against Prometheus naming best practices before writing any metrics.

### Phase Ordering Rationale

- pyroute2 first: fully independent, highest technical uncertainty (kernel netlink encoding), validates before touching tuning or observability
- Retention second: prerequisite config design for Prometheus aggressive mode; forces data availability contract to be solved before adaptive tuning or Prometheus ships; low risk
- Auto-fusion third: low risk, addresses known production pain, independent of other phases; sequential ordering keeps changes isolated during validation windows
- Adaptive rate steps fourth: highest blast radius, benefits from stable cycle budget (Phase 1) and confirmed retention config (Phase 2)
- Prometheus last: purely additive, benefits from all prior phases being observable in dashboards; no phase depends on it

### Research Flags

Phases needing `/gsd:research-phase` during planning:

- **Phase 1:** pyroute2 version conflict (0.9.x vs 0.7.x) must be resolved; proof-of-concept CAKE netlink change required before planning commences; verify `tc("replace")` for initialize_cake via netlink (harder than `tc("change")`) is supported in target version
- **Phase 4:** Adaptive rate step objective function requires design iteration — how to detect oscillation vs slow recovery from 1m granularity data; consider in-process episode tracking as alternative to SQLite lookback for sub-hour patterns

Phases with standard/well-documented patterns (skip research-phase):

- **Phase 2:** Parameterizing existing constants; no new algorithms; internal coordination task only
- **Phase 3:** All building blocks exist in codebase; state machine is ~50 lines; only threshold calibration requires production data review
- **Phase 5:** CustomCollector and start_http_server patterns are standard prometheus_client; label design is a review task, not a research task

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | pyroute2 CAKE support verified in source tree with attribute names; prometheus_client official project confirmed on PyPI; both zero transitive deps; Debian 12 version constraint confirmed; pyroute2 version conflict is a known open question |
| Features | HIGH | Based on direct codebase analysis of existing MetricsRegistry, LinuxCakeBackend._run_tc, _check_protocol_correlation, TuningEngine ALL_LAYERS, storage/downsampler.py; all integration points located in source with file/line references |
| Architecture | HIGH | All touchpoints identified; LinuxCakeAdapter pass-through confirmed; tuning_params table schema confirmed; _apply_tuning_to_controller extension point confirmed; threading model for PrometheusExporter matches existing HealthServer exactly |
| Pitfalls | HIGH | pyroute2 pitfalls grounded in known GitHub issues (#132, #547) and documented fd leak history; Prometheus pitfall grounded in GIL behavior and prometheus_client issue #1114; rate step pitfall grounded in ISA PID control literature and existing revert detection in safety.py |

**Overall confidence:** HIGH

### Gaps to Address

- **pyroute2 CAKE `tc("change")` attribute encoding**: STACK.md and ARCHITECTURE.md both cite the attributes (TCA_CAKE_BASE_RATE64), but neither has a working proof-of-concept against the production VM kernel. This is the highest uncertainty in the milestone. Phase 1 planning must include a standalone validation test before any hot-loop code is written.
- **pyroute2 version conflict**: STACK.md recommends 0.9.5 (latest); ARCHITECTURE.md recommends pinning to 0.7.x (thread-based, synchronous). Resolve at Phase 1 kickoff by verifying 0.9.x synchronous usage behavior. If 0.9.x introduces async surprises, pin to 0.7.12.
- **Adaptive rate step objective function**: FEATURES.md assigns MEDIUM confidence to this feature specifically. How to detect oscillation vs slow recovery from 1m-granularity SQLite data is underspecified. Phase 4 planning should budget design iteration for the strategy implementations.
- **Auto-fusion threshold calibration**: Proposed thresholds (suspend after 30 divergent readings at 10s IRTT cadence = 5 min, recover after 10 readings = 1.5 min) are reasoned estimates. Review production ATT divergence logs before enabling auto-disable on that WAN.

## Sources

### Primary (HIGH confidence)

- pyroute2 GitHub (`pyroute2/netlink/rtnl/tcmsg/sched_cake.py`) — CAKE TCA attributes and stats decoder confirmed present; PR #662 merged 2020
- pyroute2 PyPI — v0.9.5 confirmed, Python >=3.9, zero deps
- pyroute2 changelog — CAKE support since v0.3.17, change/replace since v0.4.14
- prometheus_client PyPI / GitHub — v0.24.1 confirmed, CustomCollector pattern, start_http_server, generate_latest
- Grafana provisioning docs — YAML + JSON dashboard provisioning confirmed stable across Grafana 10-11
- Debian packages.debian.org — `python3-pyroute2` v0.7.2 confirmed (system package too old, venv install required)
- wanctl codebase (direct analysis) — `backends/linux_cake.py`, `autorate_continuous.py`, `tuning/`, `storage/`, `health_check.py`, `metrics.py`

### Secondary (MEDIUM confidence)

- pyroute2 GitHub issues #132, #547 — fd leak behavior under multithreading; `__del__`-based cleanup is non-deterministic
- prometheus_client issue #1114 — CPU regression in 0.22.1 (resolved in 0.22.2); relevant to version floor
- ISA PID tuning best practices — controller gain tuning stability, oscillation risks; grounds rate step pitfall analysis
- sqm-autorate / qosmate (OpenWrt) — competitor analysis confirms fixed step sizes are industry norm; adaptive steps are genuine differentiator

### Tertiary (LOW confidence)

- Netlink socket buffer overflow (SO_RCVBUF) behavior under load — cited in Pitfalls but not directly tested on production hardware; monitor via `lsof` and `overrun_count` during Phase 1 soak test

---

*Research completed: 2026-03-26*
*Ready for roadmap: yes*
