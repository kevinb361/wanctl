# Project Research Summary

**Project:** wanctl v1.17 CAKE Optimization & Benchmarking
**Domain:** CAKE qdisc parameter optimization and bufferbloat benchmarking for production dual-WAN controller
**Researched:** 2026-03-13
**Confidence:** HIGH

## Executive Summary

v1.17 adds two independent capabilities to the existing wanctl toolchain: (1) automated CAKE queue type parameter optimization via a `--fix` flag extension to `wanctl-check-cake`, and (2) a new `wanctl-benchmark` CLI tool that wraps flent/netperf to run RRUL bufferbloat tests and grade results A through F. Both features build entirely on existing infrastructure — zero new Python package dependencies. The `--fix` feature extends the existing `RouterOSREST` client with two new methods targeting `/rest/queue/type` (a distinct RouterOS resource from the `/rest/queue/tree` already supported), and the benchmark tool promotes already-written integration test framework code (`FlentGenerator`, `NetperfGenerator`, `SLAChecker`) to a user-facing CLI backed by SQLite storage following the existing `MetricsWriter` pattern.

The most critical architectural constraint is the RouterOS two-level queue model: CAKE parameters (diffserv, flowmode, nat, ack-filter, wash, rtt, overhead) live on the **queue type** object at `/rest/queue/type`, not on queue tree entries. The existing codebase only touches `/rest/queue/tree`. Every implementation path for the auto-fix feature must go through new `get_queue_type()` / `set_queue_type_params()` methods, never through the existing queue tree PATCH code. Additionally, link-dependent parameters (overhead scheme, RTT target) must come from YAML config — auto-detection from WAN name violates the portable controller architecture and will break non-standard deployments.

The primary operational risk is the interaction between the running autorate daemon and benchmark traffic. The daemon runs at 20Hz with sub-second congestion detection; an RRUL test that saturates the link will trigger immediate rate reduction, producing results that are neither shaped nor unshaped. The benchmark tool must document two distinct modes: effectiveness testing (daemon active, measures latency control quality) and capacity testing (daemon paused, measures raw link capacity). The second major risk is applying CAKE fixes to a live router while the daemon writes queue tree entries every 50ms — the fix tool must check for the daemon lock file and refuse or warn before modifying queue types.

## Key Findings

### Recommended Stack

Both features add zero Python package dependencies to the project. The CAKE auto-fix uses `requests` (existing) for REST API PATCH calls, `PyYAML` (existing) for config loading, and the existing `RouterOSREST._find_resource_id()` pattern extended with a `_queue_type_id_cache`. The benchmark tool invokes `flent` and `netperf` as external system binaries via `subprocess.Popen` (existing pattern from `load_generator.py`), stores results via SQLite (existing `MetricsWriter` pattern), and uses `gzip` + `json` (stdlib) to parse flent's `.flent.gz` output. The only system-level change is adding `flent` to the Dockerfile; `netperf` is already present.

**Core technologies:**
- Python 3.12 (existing) — runtime, no version changes required
- requests >=2.31.0 (existing) — RouterOS REST API PATCH to `/rest/queue/type/{id}`
- subprocess stdlib (existing pattern from `load_generator.py`) — invoke flent/netperf binaries; flent must NOT be imported as a Python module (unstable internal API, pulls heavy GUI deps)
- SQLite stdlib (existing `MetricsWriter` pattern) — benchmark result storage; adds `benchmarks` table to existing schema
- flent 2.2.0 (system binary, NOT pip) — RRUL test orchestration; `apt install flent` on containers that need benchmarking
- netperf 2.6+ (already in Dockerfile) — TCP stream generation for RRUL tests
- PyYAML >=6.0.1 (existing) — optional `cake_optimization:` config block loading

### Expected Features

**Must have (table stakes):**
- CAKE parameter detection — read `/rest/queue/type`, compare against optimal, report sub-optimal settings as `CheckResult` items
- Show diff before applying fixes — safety requirement on a production router
- `--fix` flag that applies optimal CAKE parameters via REST PATCH — core purpose of optimization feature
- `--dry-run` mode for `--fix` — required; show what would change without applying; should be the default behavior
- RRUL bufferbloat test via `wanctl-benchmark run` — core purpose of benchmark feature
- A-F grade based on latency increase under load — makes results actionable for non-experts
- SQLite result storage — essential for before/after comparison
- `wanctl-benchmark compare` — before/after delta to prove CAKE optimization worked
- Netperf server pre-flight connectivity check (3s timeout) — fail fast before 30-60s test run

**Should have (differentiators):**
- Link-type-aware CAKE profiles in YAML (`cake_optimization:` config block with per-direction settings for overhead, flowmode, diffserv, nat, ack-filter, rtt)
- Parameter snapshot to JSON before applying fix — enables manual rollback
- `wanctl-benchmark history` — track bufferbloat grade over time in SQLite
- JSON output mode (`--json`) for all operations — CI/scripting integration following existing pattern
- Quick benchmark mode (`--quick`, 10s instead of 60s) — fast iteration during tuning sessions
- Separate DL/UL bufferbloat grades — some links have good DL but bad UL control
- `--benchmarks` subcommand in `wanctl-history` — unified history view across metrics and benchmarks

**Defer to v2+:**
- Auto-schedule benchmarks — risk of running during peak hours, saturating production link
- Health endpoint benchmark summary — low priority, adds coupling between daemon and CLI tool
- Graphical plots — requires matplotlib, not useful in SSH/CLI context; users can feed JSON to external tools

### Architecture Approach

Both features follow the established "extend, don't restructure" principle. The CAKE auto-fix adds a new `cake_optimizer.py` module containing the optimization logic and a `OPTIMAL_CAKE_PARAMS` lookup table, while `check_cake.py` gains `--fix`/`--yes` CLI flags and wires the optimizer into `main()` after the existing audit completes. The benchmark tool is a fully independent new `benchmark.py` module with zero coupling to `check_cake.py` or the autorate daemon. All output uses the existing `CheckResult`/`Severity` model and `format_results()` for consistency. All router access uses the `SimpleNamespace` config wrapping pattern established in v1.16 (never instantiate `Config()` in CLI tools — daemon constructors create lock files and set up log directories).

**Major components:**
1. `cake_optimizer.py` (NEW) — `CakeRecommendation` dataclass, `OPTIMAL_CAKE_PARAMS` lookup table for link-independent CAKE defaults, `LINK_DEPENDENT_PARAMS` set distinguishing config-driven parameters, `analyze_queue_types()`, `apply_recommendations()`
2. `routeros_rest.py` (MODIFY) — add `get_queue_type()`, `set_queue_type_params()`, and `_queue_type_id_cache` targeting `/rest/queue/type`; follows exact same `_find_resource_id()` pattern as existing queue tree lookups
3. `check_cake.py` (MODIFY) — add `--fix`/`--yes` flags, wire optimizer analysis after audit, add `_extract_queue_type_names()` helper that reads the `queue` field from queue tree entries
4. `benchmark.py` (NEW) — `FlentRunner` subprocess wrapper, `BenchmarkResult` dataclass, `grade_result()` A-F grading, `BenchmarkStorage` SQLite persistence, argparse CLI with `run`/`compare`/`history` subcommands
5. `storage/schema.py` (MODIFY) — add `benchmarks` table with indexes on `timestamp` and `wan_name`
6. `storage/reader.py` (MODIFY) — add `query_benchmarks()` following `query_metrics()` read-only connection + WHERE builder pattern

### Critical Pitfalls

1. **Writing CAKE params to `/rest/queue/tree` instead of `/rest/queue/type`** — queue tree PATCH silently ignores CAKE parameters (RouterOS ignores unknown fields); the fix appears to succeed but nothing changes on the router. No code in the current codebase queries `/queue/type`. Must add new `get_queue_type()`/`set_queue_type_params()` targeting the correct endpoint. Address in the optimizer foundation phase before any fix logic is written.

2. **Benchmark triggers autorate controller, invalidating results** — the daemon running at 20Hz will detect RRUL load as congestion within 50-100ms and reduce CAKE limits via `factor_down: 0.85`, potentially cutting throughput 50%+ within the first 2 seconds. The benchmark CLI must check daemon status, document two modes (effectiveness test = daemon active measures latency control quality; capacity test = daemon paused measures raw throughput), and never report throughput figures without noting daemon state.

3. **Applying wrong overhead scheme to ATT VDSL2 link** — `pppoe-ptm` (overhead 30) vs `bridged-ptm` (overhead 22) depends on BGW320 provisioning mode; cannot be auto-detected from the wanctl side. The overhead scheme must be a required YAML config parameter. No auto-detection based on WAN name or any heuristic — this violates the portable controller architecture that is a non-negotiable constraint.

4. **Modifying queue type while daemon actively writes queue tree at 50ms cycles** — RouterOS may briefly flush queue state during type modification, causing `CakeStatsReader` delta calculation to go negative and triggering false steering decisions. The `--fix` tool must check the daemon lock file (`/run/wanctl/spectrum.lock`) and refuse to proceed or require `--force`. Standard procedure: stop daemon, apply fix, benchmark to verify, start daemon.

5. **Non-comparable benchmark results** — ISP congestion varies by time of day; cable DOCSIS can add 20-30ms of baseline RTT at peak hours. Single-sample RRUL runs are inherently noisy. Store full metadata per run (server, duration, WAN name, daemon status, timestamp). Require minimum 3 runs for official grade assignment; single-run shows "preliminary" with explicit warning. Support `--server` override and warn when comparing runs that used different servers.

## Implications for Roadmap

Based on the research, three phases are appropriate. The optimizer foundation must precede the auto-fix CLI integration because it establishes the correct `/rest/queue/type` data model. The benchmarking feature is fully independent and can be built in parallel with Phase 2 or sequentially after it.

### Phase 1: Optimizer Foundation

**Rationale:** The queue type API methods and `cake_optimizer.py` module must exist before any fix CLI can call them. Building this as a standalone module with comprehensive tests establishes the correct `/rest/queue/type` endpoint usage first and prevents the most dangerous pitfall (writing to the wrong endpoint) from infecting later phases. Tests written here — with mock router responses that have CAKE params on queue type objects, not queue tree entries — lock in the correct data model.

**Delivers:** `cake_optimizer.py` with `CakeRecommendation` dataclass, `OPTIMAL_CAKE_PARAMS` table, `LINK_DEPENDENT_PARAMS` set, `analyze_queue_types()`, `apply_recommendations()`. Two new methods on `RouterOSREST`: `get_queue_type()` and `set_queue_type_params()`. YAML config schema for `cake_optimization:` block with per-direction override parameters. Unit tests covering all CAKE parameter detection cases with realistic mock router responses.

**Addresses:** CAKE parameter detection (table stakes), link-type-aware optimization profiles (differentiator)

**Avoids:** Pitfall 1 (wrong endpoint — locked in by tests that verify requests go to `/queue/type`), Pitfall 3 (overhead from config not hardcoded — config schema defined here), Pitfall 4 (read/analyze only in this phase, no writes)

### Phase 2: Auto-Fix CLI Integration

**Rationale:** Depends on Phase 1 optimizer module. Extends `check_cake.py` with `--fix`/`--yes` flags, wires optimizer output into the CLI, implements the daemon lock check, and delivers the diff + confirmation flow. This is the most operationally sensitive phase — it writes to a production router — so it follows the optimizer module rather than being built together with it.

**Delivers:** `wanctl-check-cake spectrum.yaml --fix` workflow with dry-run display of proposed changes, interactive confirmation prompt, `--yes` bypass for scripting, parameter snapshot to timestamped JSON for rollback, before/after diff output per parameter, daemon lock file check that refuses writes when daemon is running.

**Uses:** `cake_optimizer.py` (Phase 1), `routeros_rest.py` additions (Phase 1), `SimpleNamespace` config wrapping pattern, `CheckResult`/`Severity` output model

**Implements:** `check_cake.py` CLI extension with `--fix`/`--yes`, `_extract_queue_type_names()` helper

**Avoids:** Pitfall 4 (daemon coordination via lock file check), Pitfall 3 (overhead from config, not derived from WAN name), security mistake of silent router writes without diff

### Phase 3: Bufferbloat Benchmarking CLI

**Rationale:** Fully independent of Phases 1-2. Zero coupling to optimization code — shares only the SQLite storage pattern and `CheckResult` output model. The main implementation risks are daemon interaction (Pitfall 2, addressed with runtime status check and clear mode documentation) and netperf server reliability (Pitfall 7, addressed with pre-flight check and `--server` flag).

**Delivers:** `wanctl-benchmark` CLI with `run`/`compare`/`history` subcommands. `FlentRunner` subprocess wrapper with `check_prerequisites()` and clear install guidance. `BenchmarkResult` dataclass with A+ through F grading (A+ <5ms, A <15ms, B <30ms, C <60ms, D <200ms, F >=200ms). `benchmarks` SQLite table with full metadata per run. `query_benchmarks()` reader. `--benchmarks` in `wanctl-history`. `--check-deps` flag for dependency validation. Netperf pre-flight check (3s timeout). Runtime daemon status check with mode documentation.

**Uses:** `subprocess.Popen` pattern from `load_generator.py`, `MetricsWriter` SQLite pattern, `gzip`+`json` stdlib for `.flent.gz` parsing, existing RRUL profiles from `tests/integration/profiles/`

**Implements:** `benchmark.py`, `storage/schema.py` addition, `storage/reader.py` addition, `history.py` extension, `pyproject.toml` new entry point `wanctl-benchmark`

**Avoids:** Pitfall 2 (daemon interaction documented and flagged at runtime), Pitfall 5 (SQLite storage with metadata, multi-run grading, preliminary warning for single runs), Pitfall 6 (dependency checks with install guidance in error messages), Pitfall 7 (pre-flight netperf connectivity check, `--server` flag)

### Phase Ordering Rationale

- Phase 1 before Phase 2: the `cake_optimizer.py` module and REST API methods are hard dependencies for the fix CLI — they must exist before `check_cake.py` can call them
- Phase 3 fully independent: benchmark shares no code with optimization; can be developed concurrently with Phase 2 if desired or built sequentially after it
- YAML config schema (`cake_optimization:`) defined in Phase 1 so Phase 2 can read link-dependent parameters from config rather than guessing or hardcoding
- Daemon lock check implemented in Phase 2 (not deferred) because it is a safety requirement for any production router write — never deferred past the first phase that writes to the router
- SQLite schema additions in Phase 3 follow the existing migration pattern in `storage/schema.py` — no special handling needed beyond adding `CREATE TABLE IF NOT EXISTS` block

### Research Flags

Phases with well-documented patterns (skip additional research):
- **Phase 1 (Optimizer Foundation):** RouterOS REST API is fully documented; `_find_resource_id()` pattern is proven in the existing codebase. `OPTIMAL_CAKE_PARAMS` table is directly derivable from MikroTik CAKE documentation. The `CakeRecommendation` dataclass follows the existing `CheckResult` pattern exactly.
- **Phase 3 (Benchmarking):** `FlentGenerator`/`NetperfGenerator` code already exists and is tested in `tests/integration/framework/`. SQLite storage pattern is established in `MetricsWriter`. Flent's gzipped JSON output format is documented and parseable with stdlib `gzip`+`json`.

Phases that may benefit from targeted investigation during planning:
- **Phase 2 (Auto-Fix):** The RouterOS PATCH response format for `/rest/queue/type` should be verified against a live router before finalizing success/failure detection logic. Confirm that PATCHing a queue type while the queue is actively handling traffic behaves the same as patching at idle. Verify exact CAKE parameter names in RouterOS REST responses (e.g., `cake-ack-filter` vs `cake-ack-filter-mode`) against a live device to avoid silent no-ops.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Zero new dependencies confirmed. Every needed capability mapped to an existing file and method. Flent subprocess pattern already implemented in codebase. RouterOS REST PATCH pattern verified in `routeros_rest.py`. |
| Features | HIGH | Table stakes and differentiators derived from existing codebase capabilities and well-documented RRUL/CAKE domain. Grading thresholds from Waveform/DSLReports (MEDIUM on exact cutoffs, HIGH on A-F structure). |
| Architecture | HIGH | Extend-don't-restructure principle has 16 milestones of validation. Component boundaries are clear. Queue type vs queue tree distinction is the critical constraint — well-evidenced by codebase analysis showing no existing code touches `/queue/type`. |
| Pitfalls | HIGH | All 7 critical pitfalls grounded in codebase analysis (not inference). The queue tree/type confusion is the most dangerous — verified that no existing code queries `/queue/type`. The daemon-benchmark interaction is documented from direct analysis of the autorate control loop timing. |

**Overall confidence:** HIGH

### Gaps to Address

- **Exact RouterOS response format for `/rest/queue/type`:** Research documents expected fields from MikroTik documentation, but actual JSON key names returned by a live RouterOS 7.x instance for CAKE parameters (hyphenated vs underscored, presence of units in string values like `"100ms"` vs `100`) should be verified during Phase 1 by capturing a live response and using it as the canonical test fixture.
- **ATT BGW320 passthrough mode:** Whether the ATT connection uses `bridged-ptm` or `pppoe-ptm` depends on BGW320 configuration. The YAML config schema must require this as an explicit field with a comment directing the operator to verify their passthrough mode. Resolve by examining BGW320 admin UI or capturing a packet trace during Phase 2.
- **Bufferbloat grading thresholds:** A+/A/B/C/D/F cutoffs are from Waveform/DSLReports (industry consensus, not a published standard). Treat as configurable defaults in the grading function, not immutable constants, so they can be adjusted without a code change.
- **Alert suppression during benchmark:** RRUL tests will trigger congestion alerts (v1.15 alerting engine) and potentially steering transitions (v1.11). The benchmark tool should either warn the operator ("Expect congestion alerts during benchmark. This is normal.") or provide an optional `--suppress-alerts` mechanism. Decision deferred to Phase 3 implementation.

## Sources

### Primary (HIGH confidence)

- MikroTik CAKE Documentation — CAKE parameters, overhead keywords, queue type options; RTT preset values (internet=100ms, regional=30ms, metro=10ms)
- MikroTik Queue Types Documentation — queue type vs queue tree separation, CAKE kind properties
- MikroTik REST API Documentation — PATCH method, URL structure (`/rest/queue/type/{id}`), JSON body format
- Existing codebase: `check_cake.py`, `routeros_rest.py`, `check_config.py`, `autorate_continuous.py`, `steering/cake_stats.py` — current capabilities and integration points (verified directly)
- Existing codebase: `tests/integration/framework/load_generator.py`, `tests/integration/profiles/` — FlentGenerator, NetperfGenerator, RRUL profiles (verified directly)
- Existing codebase: `metrics_storage.py`, `storage/schema.py`, `storage/reader.py` — SQLite patterns to follow (verified directly)
- Flent Official Documentation — test descriptions, CLI options (`-H`, `-l`, `-o`, `-f`), output formats (`.flent.gz` gzipped JSON)
- Bufferbloat.net RRUL Specification — 8-stream bidirectional test design, simultaneous latency measurement methodology

### Secondary (MEDIUM confidence)

- Waveform Bufferbloat Test — grading thresholds (A+ <5ms, A <15ms, B <30ms, C <60ms, D <200ms, F >=200ms); proprietary but widely cited and cross-confirmed
- DSLReports Bufferbloat FAQ — grade scale confirmation; community standard for bufferbloat scoring
- VDSL2 overheads and CAKE (allysmith.uk) — PTM 64/65 encoding factor, PPPoE vs bridged overhead byte counts
- cake-autorate project (GitHub) — reference implementation for CAKE auto-tuning on OpenWrt; confirms optimal parameter choices for home WAN use

### Tertiary (LOW confidence — verify during implementation)

- Netperf server availability (netperf.bufferbloat.net, 104.200.21.31) — community servers with no SLA; operators should self-host for reliable benchmarking
- RouterOS REST JSON field names for `/rest/queue/type` CAKE parameters — documentation reviewed but exact GET response format needs live router confirmation before finalizing mock fixtures

---
*Research completed: 2026-03-13*
*Ready for roadmap: yes*
