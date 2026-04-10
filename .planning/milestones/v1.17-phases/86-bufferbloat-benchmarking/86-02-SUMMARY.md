---
phase: 86-bufferbloat-benchmarking
plan: 02
subsystem: benchmark
tags: [flent, bufferbloat, cli, subprocess, argparse, grading]

# Dependency graph
requires:
  - phase: 86-bufferbloat-benchmarking
    provides: BenchmarkResult dataclass, compute_grade(), parse_flent_results(), build_result()
provides:
  - check_prerequisites() with apt install instructions for flent/netperf
  - check_server_connectivity() with netperf probe and baseline RTT measurement
  - check_daemon_running() via /run/wanctl/*.lock file detection
  - run_benchmark() orchestrating flent rrul subprocess
  - format_grade_display() with color-coded grade output
  - format_json() for structured JSON output
  - create_parser() with --server, --quick, --json, --no-color
  - main() CLI entry point with exit codes
  - wanctl-benchmark entry point in pyproject.toml
affects: [87-benchmark-storage]

# Tech tracking
tech-stack:
  added: []
  patterns:
    [
      prerequisite-check-with-apt-instructions,
      server-connectivity-probe-via-netperf,
      daemon-detection-via-lock-files,
      grade-color-mapping,
    ]

key-files:
  created: []
  modified:
    - src/wanctl/benchmark.py
    - tests/test_benchmark.py
    - pyproject.toml

key-decisions:
  - "check_prerequisites returns (checks, baseline_rtt) tuple to pass baseline to run_benchmark"
  - "Server connectivity probed via 1s netperf TCP_STREAM (validates server + network path)"
  - "Baseline RTT measured via ping -c 5 -i 0.2 with parse_ping_output from rtt_measurement"
  - "Daemon detection warns but does not block (benchmark results may differ with daemon running)"
  - "run_benchmark timeout = duration + 30s for flent subprocess overhead"
  - "Quick mode note only shown for duration <= 10s"

patterns-established:
  - "Prerequisite check pattern: shutil.which + server probe, print checklist to stderr"
  - "Grade color mapping: A+/A=green(32), B/C=yellow(33), D/F=red(31)"
  - "CLI tool pattern: create_parser(), main() -> int, sys.stderr for status, stdout for results"

requirements-completed: [BENCH-01, BENCH-02, BENCH-03, BENCH-06, BENCH-07]

# Metrics
duration: 14min
completed: 2026-03-13
---

# Phase 86 Plan 02: Benchmark CLI Tool Summary

**Complete wanctl-benchmark CLI with prerequisite checking, flent RRUL orchestration, color-coded grade display, and JSON output**

## Performance

- **Duration:** 14 min
- **Started:** 2026-03-13T20:48:56Z
- **Completed:** 2026-03-13T21:03:05Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- check_prerequisites() detects missing flent/netperf with apt install instructions
- check_server_connectivity() probes via 1s netperf TCP_STREAM, measures baseline RTT with ping
- check_daemon_running() detects live wanctl daemons via lock files, warns but does not block
- run_benchmark() orchestrates flent rrul subprocess with proper timeout and tmpdir cleanup
- format_grade_display() shows prominent color-coded grades with latency percentiles and throughput
- format_json() outputs complete BenchmarkResult as indented JSON
- Full CLI with --server, --quick, --json, --no-color flags and proper exit codes
- wanctl-benchmark entry point registered in pyproject.toml
- 46 new tests (76 total benchmark tests), all passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Prerequisite checks, server connectivity, daemon warning** - `f374535` (feat)
2. **Task 2: CLI orchestration, output formatting, entry point** - `5105191` (feat)

_Note: TDD tasks combined RED+GREEN in single commits since implementation was in same file._

## Files Created/Modified

- `src/wanctl/benchmark.py` - Added check_server_connectivity(), check_prerequisites(), check_daemon_running(), _print_prerequisites(), run_benchmark(), format_grade_display(), format_json(), create_parser(), main()
- `tests/test_benchmark.py` - 46 new tests across 11 test classes (TestServerConnectivity, TestPrerequisites, TestDaemonWarning, TestPrintPrerequisites, TestRunBenchmark, TestQuickMode, TestFormatGradeDisplay, TestFormatJson, TestCreateParser, TestMain)
- `pyproject.toml` - Added wanctl-benchmark entry point

## Decisions Made

- check_prerequisites returns (checks, baseline_rtt) tuple so baseline RTT flows through to run_benchmark without re-measurement
- Server connectivity probed via 1s netperf TCP_STREAM (validates both server availability and network path, not just ICMP)
- Baseline RTT measured via ping -c 5 -i 0.2 using existing parse_ping_output from rtt_measurement module
- Daemon detection warns to stderr but does not block (benchmark results may differ with daemon running but blocking would be too restrictive)
- run_benchmark timeout = duration + 30s to allow flent subprocess overhead
- Quick mode note only shown for duration <= 10s (not other custom durations)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed ruff F821 undefined name in test helper**

- **Found during:** Task 2 verification
- **Issue:** `_make_benchmark_result` return annotation `-> "BenchmarkResult"` caused ruff F821 because BenchmarkResult is imported inside the function
- **Fix:** Removed return type annotation, added `# noqa: ANN201`
- **Files modified:** tests/test_benchmark.py
- **Verification:** ruff check passes clean
- **Committed in:** 5105191 (Task 2 commit)

**2. [Rule 3 - Blocking] Fixed ruff F401 unused import `call` in test file**

- **Found during:** Task 1 verification
- **Issue:** `from unittest.mock import MagicMock, call, patch` -- `call` was imported but not used
- **Fix:** Removed `call` from import
- **Files modified:** tests/test_benchmark.py
- **Verification:** ruff check passes clean
- **Committed in:** f374535 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (2 blocking -- lint failures)
**Impact on plan:** Minor lint fixes. No scope creep.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Complete wanctl-benchmark CLI ready for Phase 87 (benchmark storage & comparison)
- All parsing, grading, and formatting functions available for storage integration
- BenchmarkResult dataclass ready for SQLite persistence
- 76 tests covering all benchmark functionality

## Self-Check: PASSED

- [x] src/wanctl/benchmark.py exists with all functions
- [x] tests/test_benchmark.py exists with 76 tests
- [x] pyproject.toml has wanctl-benchmark entry point
- [x] Commit f374535 exists
- [x] Commit 5105191 exists
- [x] 76/76 benchmark tests passing
- [x] ruff check clean
- [x] mypy clean
- [x] 2999 full suite tests passing

---

_Phase: 86-bufferbloat-benchmarking_
_Completed: 2026-03-13_
