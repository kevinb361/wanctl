# Phase 86: Bufferbloat Benchmarking - Research

**Researched:** 2026-03-13
**Domain:** CLI subprocess orchestration (flent/netperf), result parsing, grading system
**Confidence:** HIGH

## Summary

Phase 86 builds a standalone CLI tool (`wanctl-benchmark`) that wraps the `flent` RRUL test via subprocess, parses the gzipped JSON output, computes per-direction bufferbloat grades (A+ through F), and presents results with latency percentiles and throughput. The tool follows established wanctl CLI patterns (argparse, `create_parser()` / `main()` returning int, `--json` / `--no-color` flags) and introduces zero new Python dependencies -- flent and netperf are system binaries invoked via `subprocess.run()`.

The core technical challenge is parsing flent's gzipped JSON data format, which contains time-series arrays keyed by data series names like `"Ping (ms) ICMP"`, `"TCP download sum"`, and `"TCP upload sum"`. The ping time series represents latency under load; subtracting the pre-test baseline ping from the loaded-ping average yields the "latency increase" that maps to the A+/A/B/C/D/F grade thresholds.

**Primary recommendation:** Create a single `src/wanctl/benchmark.py` module following the `check_cake.py` CLI pattern, with a `BenchmarkResult` dataclass (not reusing `CheckResult` -- different domain), prerequisite checklist on stderr, grade display on stdout, and `--json` for scripting.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Large prominent grade per direction with color (green for good grades, red for bad)
- Grades displayed prominently like a report card, with latency/throughput as supporting detail below
- Latency percentiles shown: P50, P95, P99
- Throughput displayed alongside grades
- `--json` flag for structured JSON output (consistent with check_cake/check_config)
- Grades based on **average latency increase** (mean latency under load minus baseline) -- industry standard metric
- Grade thresholds: A+ <5ms, A <15ms, B <30ms, C <60ms, D <200ms, F >=200ms
- Checklist-style prerequisite verification before test (flent binary, netperf binary, server reachable with baseline RTT)
- Prerequisite failure: exit with clear Debian/Ubuntu install instructions (`sudo apt install flent netperf`)
- Default full test duration: 60 seconds
- `--quick` mode: 10 seconds
- Test type: RRUL only (4 TCP up + 4 TCP down + ICMP)
- Default netperf server: `netperf.bufferbloat.net`
- `--server` flag overrides default
- Separate download and upload grades
- Exit 0: test ran and produced grades (any grade, even F)
- Exit 1: test couldn't run (missing tools, server unreachable, flent crash, etc.)
- No partial results -- if flent fails or is interrupted, report error and exit 1

### Claude's Discretion
- Data model choice: benchmark-specific BenchmarkResult vs reusing CheckResult/Severity
- Test progress display (countdown, passthrough, or silent)
- Whether to require config file argument or make it standalone
- Whether to warn or block when wanctl daemon is running during benchmark
- Whether to persist flent raw JSON output for debugging
- Internal function decomposition
- Flent output parsing approach

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| BENCH-01 | Operator can run RRUL bufferbloat test via `wanctl-benchmark` CLI wrapping flent | CLI pattern from check_cake.py, subprocess.run with flent, pyproject.toml entry point |
| BENCH-02 | Benchmark checks prerequisites (flent, netperf installed) with clear install instructions on failure | shutil.which() for binary detection, apt install instructions |
| BENCH-03 | Benchmark checks netperf server connectivity before starting full test | netperf TCP_STREAM 3s timeout probe (from calibrate.py pattern) |
| BENCH-04 | Benchmark grades results A+ through F using industry-standard latency-increase thresholds | Parse flent JSON "Ping (ms) ICMP" series, compute mean delta from baseline |
| BENCH-05 | Benchmark reports separate download and upload bufferbloat grades | Parse "Ping (ms) ICMP" during download-heavy vs upload-heavy portions (or use single ICMP series + per-direction throughput) |
| BENCH-06 | Benchmark supports `--quick` mode for fast 10s iteration during tuning | `--quick` sets flent `-l 10` instead of default `-l 60` |
| BENCH-07 | Benchmark supports `--server` flag to specify netperf server host | `--server` sets flent `-H <server>` |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| subprocess | stdlib | Invoke flent, netperf binaries | Project pattern (calibrate.py), zero deps |
| gzip | stdlib | Decompress flent .flent.gz output | Flent saves results as gzipped JSON |
| json | stdlib | Parse flent result data | Standard JSON parsing |
| shutil | stdlib | shutil.which() for binary detection | Standard way to find executables |
| statistics | stdlib | Compute percentiles from latency arrays | P50/P95/P99 calculation |
| argparse | stdlib | CLI argument parsing | Project standard |
| dataclasses | stdlib | BenchmarkResult data model | Project pattern |
| tempfile | stdlib | Temporary directory for flent output | Clean up .flent.gz after parsing |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| flent | system binary | Run RRUL bufferbloat test | Invoked via subprocess, NOT imported |
| netperf | system binary | TCP load generation (used by flent) | Required dependency of flent |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| BenchmarkResult dataclass | CheckResult/Severity | CheckResult is validation-oriented (category/field/severity/message); benchmark needs grades, percentiles, throughput -- different domain |
| Parse flent JSON directly | Parse flent `-f stats` text output | JSON is structured, parseable, stable; text output format may change between versions |
| shutil.which() | subprocess FileNotFoundError | which() gives upfront check before attempting; FileNotFoundError is reactive |

**Installation:**
```bash
# System packages only -- no pip install needed
sudo apt install flent netperf
```

## Architecture Patterns

### Recommended Project Structure
```
src/wanctl/
    benchmark.py          # NEW: benchmark CLI tool (standalone module)
tests/
    test_benchmark.py     # NEW: comprehensive tests
pyproject.toml            # ADD: wanctl-benchmark entry point
```

### Pattern 1: Standalone CLI Tool (Follows check_cake.py)
**What:** Single-module CLI tool with `create_parser()`, `main()`, internal helpers
**When to use:** All wanctl CLI tools follow this pattern
**Example:**
```python
# Source: check_cake.py, check_config.py established pattern
def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wanctl-benchmark",
        description="Run RRUL bufferbloat test and grade results",
    )
    parser.add_argument("--server", default="netperf.bufferbloat.net",
                        help="Netperf server host")
    parser.add_argument("--quick", action="store_true",
                        help="Run 10s quick test instead of 60s full test")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    parser.add_argument("--no-color", action="store_true",
                        help="Disable colored output")
    return parser

def main() -> int:
    parser = create_parser()
    args = parser.parse_args()
    # ... prerequisite checks, run test, parse, grade, display
    return 0  # or 1 on failure
```

### Pattern 2: Subprocess Invocation with Security Annotations
**What:** Using subprocess.run() with bandit nosec annotations
**When to use:** Calling external binaries (flent, netperf)
**Example:**
```python
# Source: calibrate.py established pattern
import subprocess  # nosec B404 - Required for running flent/netperf benchmarking tools

result = subprocess.run(  # nosec B603 - cmd is hardcoded flent invocation
    cmd, capture_output=True, text=True, timeout=timeout
)
```

### Pattern 3: Flent JSON Data Parsing
**What:** Parse gzipped JSON from flent, extract time-series data
**When to use:** After flent subprocess completes successfully
**Example:**
```python
import gzip
import json

def parse_flent_results(flent_gz_path: str) -> dict:
    """Parse flent .flent.gz output file."""
    with gzip.open(flent_gz_path, "rt") as f:
        data = json.load(f)
    # data["results"] contains series like:
    #   "Ping (ms) ICMP": [values...]      -- latency under load
    #   "TCP download sum": [values...]     -- total download Mbps
    #   "TCP upload sum": [values...]       -- total upload Mbps
    # data["x_values"] contains timestamps
    # data["metadata"] contains test metadata
    return data
```

### Pattern 4: BenchmarkResult Data Model
**What:** Dedicated dataclass for benchmark outcomes (Phase 87 storage-friendly)
**When to use:** Return type from run_benchmark(), input to format functions
**Example:**
```python
@dataclass
class BenchmarkResult:
    """Result of a single RRUL bufferbloat test."""
    # Grades
    download_grade: str          # "A+", "A", "B", "C", "D", "F"
    upload_grade: str
    # Latency (ms) -- increase over baseline
    download_latency_avg: float
    download_latency_p50: float
    download_latency_p95: float
    download_latency_p99: float
    upload_latency_avg: float
    upload_latency_p50: float
    upload_latency_p95: float
    upload_latency_p99: float
    # Throughput (Mbps)
    download_throughput: float
    upload_throughput: float
    # Metadata
    baseline_rtt: float          # Pre-test baseline RTT
    server: str
    duration: int                # Test duration in seconds
    timestamp: str               # ISO 8601
```

### Anti-Patterns to Avoid
- **Importing flent as Python library:** Unstable internal API, pulls heavy GUI deps (matplotlib, PyQt5). Project decision: subprocess only.
- **Parsing flent text output:** The `-f stats` text format is human-readable but fragile. Parse the structured JSON (.flent.gz) instead.
- **Using CheckResult for grades:** CheckResult is designed for pass/warn/error validation results with category/field/severity. Benchmark grades are a different concept (A+ through F with numeric backing data).
- **Computing percentiles manually when statistics module exists:** Python 3.12 `statistics` module has no built-in percentile, but numpy-style quantile can be done with `sorted()` and index math, or use the `statistics.quantiles()` function (Python 3.8+).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Binary detection | Path walking or try/except subprocess | `shutil.which("flent")` | Standard, handles PATH correctly |
| Percentile calculation | Manual index math | `statistics.quantiles(data, n=100)` | Returns 99 cut points; P50=index 49, P95=index 94, P99=index 98 |
| Gzip JSON parsing | Manual decompression | `gzip.open(path, "rt")` + `json.load()` | Standard stdlib pattern |
| RRUL test execution | Custom netperf orchestration | `flent rrul -H host -l duration -o output.flent.gz` | Flent handles all stream coordination, timing, DSCP marking |
| Server connectivity check | Raw socket connect | `netperf -H host -t TCP_STREAM -l 1` with 3s timeout | Tests actual netperf protocol, not just TCP connect |
| Baseline RTT measurement | Custom ICMP implementation | `ping -c 5 -i 0.2 host` parsed with existing `parse_ping_output()` | Already proven in calibrate.py |

**Key insight:** The RRUL test is inherently complex (8 TCP streams with different DSCP, ICMP ping, UDP RTT, all synchronized). Flent exists specifically to orchestrate this. Our job is just to invoke it and interpret its structured output.

## Common Pitfalls

### Pitfall 1: RRUL Ping Series Does Not Separate Download/Upload Latency
**What goes wrong:** The RRUL test runs all streams simultaneously. The `"Ping (ms) ICMP"` series measures latency under COMBINED load (4 TCP down + 4 TCP up at the same time), not separate download-only or upload-only latency.
**Why it happens:** RRUL is designed to stress-test bidirectional -- it doesn't have a download-only or upload-only phase.
**How to avoid:** For BENCH-05 (separate grades), either: (a) run `rrul` and derive "download grade" and "upload grade" from the same latency data but report per-direction throughput alongside a shared latency grade, OR (b) run two separate tests: `tcp_download` then `tcp_upload` from flent with concurrent ping, OR (c) use the single RRUL latency as the grade for both directions (since bufferbloat in either direction causes latency for both). **Recommendation:** Option (c) is most honest -- RRUL measures bidirectional latency under simultaneous load. Report one latency grade per direction using the SAME ping data, but show per-direction throughput. The "download grade" and "upload grade" can differ by using directional latency proxies if available, or simply report the combined latency as the grade for each direction. The key insight is that the user wants to see separate grades to understand if one direction is worse than the other, which is visible in throughput even if latency is shared.
**Warning signs:** If grades are identical for both directions, that's correct behavior for RRUL (latency is shared).

**IMPORTANT UPDATE:** After further analysis, the best approach for separate grades is to use the flent `rrul` test's built-in `"Ping (ms) ICMP"` series as a SINGLE latency-under-load measurement, compute one grade from it, and report it for both directions. The per-direction throughput values (`"TCP download sum"` and `"TCP upload sum"`) provide the directional differentiation. If truly separate directional latency is needed later, we could run `tcp_download` and `tcp_upload` tests sequentially, but that doubles test time and is not standard RRUL.

### Pitfall 2: Flent Output File Location
**What goes wrong:** Flent automatically names and places its .flent.gz output file based on test name, timestamp, and hostname.
**Why it happens:** Without explicit `-o` flag, flent writes to current directory with auto-generated name. With `-o`, you control the path.
**How to avoid:** Use `-o /tmp/wanctl-benchmark-XXXX/results.flent.gz` with a tempdir to control the output path. Use `tempfile.mkdtemp()` and clean up after parsing.
**Warning signs:** Stale .flent.gz files accumulating in the working directory.

### Pitfall 3: Null Values in Flent Time Series
**What goes wrong:** Flent data arrays may contain `null` (None) values for missing data points.
**Why it happens:** Network measurement tools don't always produce data at every sample point (packet loss, timing issues).
**How to avoid:** Filter None values before computing statistics: `values = [v for v in series if v is not None]`.
**Warning signs:** `TypeError: '<' not supported between instances of 'NoneType' and 'float'` during sorting/percentile.

### Pitfall 4: Netperf Server Reliability
**What goes wrong:** `netperf.bufferbloat.net` is volunteer-hosted and can be intermittently unreachable or bandwidth-limited.
**Why it happens:** Community infrastructure with limited resources.
**How to avoid:** The 3s connectivity check (BENCH-03) catches this early. The `--server` flag (BENCH-07) lets operators use their own netperf server. Consider mentioning `netperf-west.bufferbloat.net` and `netperf-eu.bufferbloat.net` as alternatives in error messages.
**Warning signs:** Connectivity check passes but test produces very low throughput (server congested, not link bottleneck).

### Pitfall 5: Flent Requires Root or NET_RAW Capability for ICMP
**What goes wrong:** Flent uses ICMP ping which may require elevated privileges.
**Why it happens:** Raw ICMP sockets need CAP_NET_RAW on Linux.
**How to avoid:** On most Linux systems, the `ping` binary is setuid or has capabilities set. Flent typically uses system ping binary which inherits these. Inside LXC containers (wanctl deployment), this should work. If it doesn't, the flent error output will indicate the issue.
**Warning signs:** Flent exits with error about ICMP permissions.

### Pitfall 6: Test Duration Affects Grade Accuracy
**What goes wrong:** Very short tests (10s `--quick` mode) may not reach TCP steady state, giving misleading grades.
**Why it happens:** TCP slow start takes time; 4 streams with different DSCP markings need time to stabilize.
**How to avoid:** Add a note in `--quick` output that grades may be less accurate. The first few seconds of flent data include ramp-up -- consider trimming initial samples (e.g., skip first 10% of data points) for more accurate statistics, especially for 10s tests.
**Warning signs:** Quick mode consistently shows worse grades than full test.

## Code Examples

### Prerequisite Checking
```python
# Verified pattern from shutil stdlib docs
import shutil

def check_prerequisites(server: str) -> list[tuple[str, bool, str]]:
    """Check all prerequisites, return list of (name, passed, detail)."""
    checks = []

    # Check flent binary
    flent_path = shutil.which("flent")
    if flent_path:
        checks.append(("flent", True, f"found at {flent_path}"))
    else:
        checks.append(("flent", False, "not found"))

    # Check netperf binary
    netperf_path = shutil.which("netperf")
    if netperf_path:
        checks.append(("netperf", True, f"found at {netperf_path}"))
    else:
        checks.append(("netperf", False, "not found"))

    # Check server connectivity (only if both binaries present)
    if flent_path and netperf_path:
        reachable, baseline_ms = check_server_connectivity(server)
        if reachable:
            checks.append(("server", True, f"reachable ({baseline_ms:.0f}ms baseline)"))
        else:
            checks.append(("server", False, f"{server} unreachable"))

    return checks
```

### Running Flent RRUL Test
```python
# Source: calibrate.py subprocess pattern + flent CLI docs
import subprocess  # nosec B404
import tempfile

def run_flent_rrul(server: str, duration: int) -> str | None:
    """Run flent RRUL test, return path to .flent.gz file or None on failure."""
    with tempfile.TemporaryDirectory(prefix="wanctl-benchmark-") as tmpdir:
        output_path = f"{tmpdir}/results.flent.gz"
        cmd = [
            "flent", "rrul",
            "-H", server,
            "-l", str(duration),
            "-o", output_path,
        ]
        result = subprocess.run(  # nosec B603 - cmd is hardcoded flent invocation
            cmd,
            capture_output=True,
            text=True,
            timeout=duration + 30,  # grace period for flent overhead
        )
        if result.returncode != 0:
            return None
        return output_path  # caller must parse before tmpdir cleanup
```

Note: The actual implementation must handle the tempdir lifecycle carefully -- parse the .flent.gz BEFORE the tmpdir is cleaned up, or copy it out.

### Parsing Flent JSON
```python
import gzip
import json
import statistics

def parse_flent_results(gz_path: str) -> dict:
    """Parse flent gzipped JSON output."""
    with gzip.open(gz_path, "rt") as f:
        data = json.load(f)
    return data

def extract_latency_stats(data: dict) -> dict:
    """Extract latency statistics from flent results."""
    ping_series = data["results"].get("Ping (ms) ICMP", [])
    # Filter None values
    values = [v for v in ping_series if v is not None and v > 0]

    if not values:
        return {"avg": 0, "p50": 0, "p95": 0, "p99": 0}

    sorted_vals = sorted(values)
    n = len(sorted_vals)

    return {
        "avg": statistics.mean(values),
        "p50": sorted_vals[int(n * 0.50)],
        "p95": sorted_vals[int(n * 0.95)] if n > 20 else sorted_vals[-1],
        "p99": sorted_vals[int(n * 0.99)] if n > 100 else sorted_vals[-1],
    }

def extract_throughput(data: dict) -> tuple[float, float]:
    """Extract average download/upload throughput in Mbps."""
    dl = data["results"].get("TCP download sum", [])
    ul = data["results"].get("TCP upload sum", [])
    dl_values = [v for v in dl if v is not None]
    ul_values = [v for v in ul if v is not None]
    return (
        statistics.mean(dl_values) if dl_values else 0.0,
        statistics.mean(ul_values) if ul_values else 0.0,
    )
```

### Grade Computation
```python
def compute_grade(latency_increase_ms: float) -> str:
    """Compute bufferbloat grade from average latency increase.

    Grade thresholds (from CONTEXT.md -- locked decision):
      A+ < 5ms, A < 15ms, B < 30ms, C < 60ms, D < 200ms, F >= 200ms
    """
    if latency_increase_ms < 5:
        return "A+"
    elif latency_increase_ms < 15:
        return "A"
    elif latency_increase_ms < 30:
        return "B"
    elif latency_increase_ms < 60:
        return "C"
    elif latency_increase_ms < 200:
        return "D"
    else:
        return "F"
```

### Connectivity Check with Baseline RTT
```python
# Source: calibrate.py check_netperf_server() + ping baseline pattern
import subprocess  # nosec B404

def check_server_connectivity(server: str, timeout: int = 3) -> tuple[bool, float]:
    """Check netperf server reachability with measured baseline RTT.

    Returns (reachable, baseline_rtt_ms). baseline_rtt_ms is 0 if unreachable.
    """
    # Quick netperf probe (1-second TCP_STREAM test)
    cmd = ["netperf", "-H", server, "-t", "TCP_STREAM", "-l", "1"]
    try:
        result = subprocess.run(  # nosec B603
            cmd, capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            return False, 0.0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, 0.0

    # Measure baseline RTT
    ping_cmd = ["ping", "-c", "5", "-i", "0.2", server]
    try:
        ping_result = subprocess.run(  # nosec B603
            ping_cmd, capture_output=True, text=True, timeout=5
        )
        from wanctl.rtt_measurement import parse_ping_output
        rtts = parse_ping_output(ping_result.stdout)
        if rtts:
            return True, min(rtts)  # min as baseline (idle latency)
    except Exception:
        pass
    return True, 0.0  # Server reachable but couldn't measure RTT
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual netperf + ping orchestration | flent RRUL wraps it all | ~2015 | Standardized, reproducible tests |
| Custom bufferbloat grading | DSLReports/Waveform A-F grades | ~2018 | Industry-standard thresholds |
| Plot-only output (matplotlib) | JSON data + optional plotting | flent 2.0+ | Scriptable, parseable results |

**Deprecated/outdated:**
- `netperf-wrapper` (old name for flent): renamed to `flent` in 2015

## Open Questions

1. **Separate download/upload grades from single RRUL test**
   - What we know: RRUL runs all streams simultaneously; `"Ping (ms) ICMP"` measures latency under combined load. There is no separate "download latency" vs "upload latency" series in standard RRUL.
   - What's unclear: Whether users expect truly independent directional latency grades or accept that RRUL latency is inherently bidirectional.
   - Recommendation: Use the single `"Ping (ms) ICMP"` latency series for both directions. The "download grade" and "upload grade" will have the same latency base but different throughput values. This is honest -- RRUL measures combined impact. If the user wants isolated directional testing, they can use separate `tcp_download` / `tcp_upload` tests in a future phase.

2. **Daemon warning vs blocking**
   - What we know: Running a benchmark while wanctl daemon is active will produce inaccurate results (daemon will react to the saturated link and adjust queue limits).
   - What's unclear: Whether to warn (allow benchmark anyway) or block (refuse to run).
   - Recommendation: Warn with a prominent message, but allow the test to proceed. The daemon's adjustments are what the user wants to see graded in some cases (testing CAKE under real conditions). Use lock_utils to detect daemon.

3. **Persisting flent raw JSON**
   - What we know: The .flent.gz file is valuable for debugging but accumulates disk space.
   - Recommendation: Do NOT persist by default. Add `--save-raw` flag if desired later. Phase 87 handles storage.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `.venv/bin/pytest tests/test_benchmark.py -x` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BENCH-01 | main() runs flent subprocess and returns grade | unit (mock subprocess) | `.venv/bin/pytest tests/test_benchmark.py::TestRunBenchmark -x` | No -- Wave 0 |
| BENCH-02 | Missing flent/netperf shows install instructions | unit (mock shutil.which) | `.venv/bin/pytest tests/test_benchmark.py::TestPrerequisites -x` | No -- Wave 0 |
| BENCH-03 | Server connectivity check with 3s timeout | unit (mock subprocess) | `.venv/bin/pytest tests/test_benchmark.py::TestServerConnectivity -x` | No -- Wave 0 |
| BENCH-04 | Grade computation from latency increase | unit (pure function) | `.venv/bin/pytest tests/test_benchmark.py::TestGradeComputation -x` | No -- Wave 0 |
| BENCH-05 | Separate download/upload grades in output | unit (mock flent data) | `.venv/bin/pytest tests/test_benchmark.py::TestDirectionalGrades -x` | No -- Wave 0 |
| BENCH-06 | --quick mode passes -l 10 to flent | unit (check subprocess args) | `.venv/bin/pytest tests/test_benchmark.py::TestQuickMode -x` | No -- Wave 0 |
| BENCH-07 | --server flag passes -H to flent | unit (check subprocess args) | `.venv/bin/pytest tests/test_benchmark.py::TestServerFlag -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_benchmark.py -x`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_benchmark.py` -- covers BENCH-01 through BENCH-07
- [ ] No framework install needed (pytest already in dev deps)
- [ ] No conftest changes needed (tests are fully self-contained with mocked subprocess)

## Sources

### Primary (HIGH confidence)
- [Flent man page](https://manpages.debian.org/testing/flent/flent.1.en.html) -- CLI options, output formats
- [Flent data format](https://flent.org/data-format.html) -- JSON structure: version, x_values, results, metadata, raw_values
- [Flent running options](https://flent.org/options.html) -- `-f`, `-o`, `-H`, `-l` flags
- [Flent tests](https://flent.org/tests.html) -- RRUL test description
- [Flent issue #184](https://github.com/tohojo/flent/issues/184) -- Data series names: "Ping (ms) ICMP", "TCP download sum/avg", "TCP upload sum/avg"
- [Flent issue #209](https://github.com/tohojo/flent/issues/209) -- netperf.bufferbloat.net reliability, alternative servers

### Secondary (MEDIUM confidence)
- [RRUL test suite](https://www.bufferbloat.net/projects/codel/wiki/RRUL_test_suite/) -- RRUL specification
- [RRUL chart explanation](https://www.bufferbloat.net/projects/bloat/wiki/RRUL_Chart_Explanation/) -- Data interpretation
- [Netbeez flent article](https://netbeez.net/blog/flent/) -- Example commands

### Tertiary (LOW confidence)
- Flent rrul.conf on GitHub (rate-limited, couldn't fetch directly) -- Data series definitions confirmed via issue #184

### Project Code (HIGH confidence)
- `src/wanctl/calibrate.py` -- subprocess pattern, netperf connectivity check, ping parsing
- `src/wanctl/check_cake.py` -- CLI pattern (create_parser, main, exit codes)
- `src/wanctl/check_config.py` -- CheckResult/Severity model, format_results/format_results_json
- `src/wanctl/lock_utils.py` -- read_lock_pid(), is_process_alive() for daemon detection
- `src/wanctl/rtt_measurement.py` -- parse_ping_output() for baseline RTT

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all stdlib, no new dependencies, established project patterns
- Architecture: HIGH -- follows proven check_cake.py CLI pattern exactly
- Flent JSON parsing: MEDIUM -- data series names confirmed from multiple sources but not from running flent directly; may need minor adjustments for exact key names
- Pitfalls: HIGH -- well-documented in flent community (null values, ICMP permissions, server reliability)

**Research date:** 2026-03-13
**Valid until:** 2026-04-13 (stable domain -- flent/netperf change slowly)
