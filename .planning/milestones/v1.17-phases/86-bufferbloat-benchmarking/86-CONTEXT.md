# Phase 86: Bufferbloat Benchmarking - Context

**Gathered:** 2026-03-13
**Status:** Ready for planning

<domain>
## Phase Boundary

CLI tool (`wanctl-benchmark`) that runs RRUL bufferbloat tests via flent subprocess and reports actionable A-F grades with latency percentiles and throughput. Supports quick mode and custom server. Requirements: BENCH-01 through BENCH-07.

Does NOT include result storage or comparison (Phase 87).

</domain>

<decisions>
## Implementation Decisions

### Output presentation
- Large prominent grade per direction with color (green for good grades, red for bad)
- Grades displayed prominently like a report card, with latency/throughput as supporting detail below
- Latency percentiles shown: P50, P95, P99
- Throughput displayed alongside grades
- `--json` flag for structured JSON output (consistent with check_cake/check_config)
- Grades based on **average latency increase** (mean latency under load minus baseline) — industry standard metric
- Grade thresholds: A+ <5ms, A <15ms, B <30ms, C <60ms, D <200ms, F >=200ms

### Progress & prerequisites
- Checklist-style prerequisite verification before test:
  - `flent` binary found
  - `netperf` binary found
  - Server reachable with measured baseline RTT shown (e.g., "server reachable (23ms baseline)")
- Prerequisite failure: exit with clear Debian/Ubuntu install instructions (`sudo apt install flent netperf`)
- Test progress display: Claude's discretion

### Test defaults & modes
- Default full test duration: 60 seconds
- `--quick` mode: 10 seconds (per BENCH-06)
- Test type: RRUL only (Realtime Response Under Load — 4 TCP up + 4 TCP down + ICMP)
- Default netperf server: `netperf.bufferbloat.net` (public community server)
- `--server` flag overrides default (per BENCH-07)
- Separate download and upload grades (per BENCH-05)

### Error handling & exit codes
- Exit 0: test ran and produced grades (any grade, even F)
- Exit 1: test couldn't run (missing tools, server unreachable, flent crash, etc.)
- No partial results — if flent fails or is interrupted, report error and exit 1
- Partial RRUL data is unreliable (TCP hasn't reached steady state)

### Claude's Discretion
- Data model choice: benchmark-specific BenchmarkResult vs reusing CheckResult/Severity
- Test progress display (countdown, passthrough, or silent)
- Whether to require config file argument or make it standalone
- Whether to warn or block when wanctl daemon is running during benchmark
- Whether to persist flent raw JSON output for debugging
- Internal function decomposition
- Flent output parsing approach

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `create_parser()` + `main()` CLI pattern: used in check_cake.py, check_config.py, history.py, calibrate.py
- `CheckResult` / `Severity` (`check_config.py`): could potentially be reused for prerequisite check results
- `lock_utils.py`: `read_lock_pid()`, `is_process_alive()`, `validate_lock()` — detect running daemon
- `format_results()` / `format_results_json()`: category-grouped output formatting (if reusing CheckResult model)

### Established Patterns
- CLI entry points registered in `pyproject.toml` under `[project.scripts]`
- argparse with create_parser() returning ArgumentParser, main() returning int exit code
- --json, --quiet, --no-color flags established across check tools
- subprocess usage in calibrate.py and rtt_measurement.py for external process invocation
- flent/netperf are system binaries via subprocess (project decision — NOT Python imports)

### Integration Points
- `pyproject.toml [project.scripts]`: register `wanctl-benchmark = "wanctl.benchmark:main"`
- New `src/wanctl/benchmark.py` module (standalone CLI tool)
- Phase 87 will add SQLite storage on top of this — output data model should be storage-friendly
- Lock file path: `/run/wanctl/*.lock` — for daemon detection

</code_context>

<specifics>
## Specific Ideas

- Prerequisite check should show baseline RTT during connectivity test — this becomes the reference for grade calculation
- Install instructions are Debian/Ubuntu specific (`apt install`) — matches LXC container deployment
- RRUL is THE standard bufferbloat test — no need for other test types in this phase
- netperf.bufferbloat.net is the well-known public server; --server allows operator to use their own

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 86-bufferbloat-benchmarking*
*Context gathered: 2026-03-13*
