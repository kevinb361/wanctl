# Phase 89: IRTT Foundation - Research

**Researched:** 2026-03-16
**Domain:** IRTT subprocess integration, JSON parsing, YAML config, Dockerfile update
**Confidence:** HIGH

## Summary

Phase 89 wraps the IRTT (Isochronous Round-Trip Tester) binary as a subprocess, parses its JSON output into a frozen dataclass, adds YAML configuration, and installs it on production containers. IRTT is a Go binary available in Debian bookworm's main repository (version 0.9.0-2) and measures UDP round-trip time, one-way delay, IPDV, and directional packet loss.

The implementation follows well-established project patterns: IRTTMeasurement class (like RTTMeasurement), IRTTResult frozen dataclass (like SignalResult), _load_irtt_config() warn+default pattern (like _load_signal_processing_config), and subprocess.run() with shutil.which() binary check (like benchmark.py). The JSON field paths documented in the CONTEXT.md need correction -- the actual paths differ from `stats.send_call.lost`/`stats.receive_call.lost`. The correct loss fields are `stats.upstream_loss_percent` and `stats.downstream_loss_percent`, with packets at `stats.packets_sent` and `stats.packets_received`.

**Primary recommendation:** Build IRTTMeasurement as a standalone module (`src/wanctl/irtt_measurement.py`) with measure() returning IRTTResult|None, following the RTTMeasurement class pattern. All failures return None silently after appropriate logging.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Short burst measurement: `irtt client -o - --json -d {duration} -i {interval} -l 48 {server}:{port}`
- Default burst: 1s duration, 100ms interval (10 packets), 48-byte payload (hardcoded)
- Core params YAML-configurable: duration_sec and interval_ms. Payload size hardcoded.
- IRTT uses nanoseconds internally -- divide by 1_000_000 for milliseconds
- Extracted JSON fields: rtt_mean, rtt_median, ipdv_mean, send_loss, receive_loss, packets_sent, packets_received
- Field paths: stats.rtt.mean, stats.rtt.median, stats.ipdv.mean, stats.send_call.lost, stats.receive_call.lost (need live verification)
- IRTT server: 104.200.21.31:2112 (self-hosted Dallas, standard IRTT port)
- IRTTResult frozen dataclass (frozen=True, slots=True) -- same pattern as SignalResult
- Fields: rtt_mean_ms, rtt_median_ms, ipdv_mean_ms, send_loss, receive_loss, packets_sent, packets_received, server, port, timestamp (monotonic), success
- measure() returns IRTTResult | None -- None on any failure
- Class with measure() method, not module-level function -- follows RTTMeasurement pattern
- Constructor takes config dict + logger. Checks shutil.which("irtt") at init time.
- is_available() method returns whether binary exists AND config has enabled=True and server set
- Always instantiated even when disabled -- measure() returns None immediately (no-op pattern)
- First failure logged at WARNING, subsequent identical failures at DEBUG
- Recovery logged at INFO with consecutive failure count
- Binary missing at startup: WARNING with apt install hint, measurements permanently disabled
- Subprocess timeout: duration_sec + 5 seconds grace period
- Track _consecutive_failures and _first_failure_logged for log level management
- New `irtt:` section in autorate YAML config, disabled by default
- Config keys: enabled (bool, default false), server (str, default None), port (int, default 2112), duration_sec (float, default 1.0), interval_ms (int, default 100)
- Config loading follows _load_signal_processing_config() warn+default pattern
- No SCHEMA entry needed -- warn+default handles validation internally
- Dockerfile updated: add `irtt` to apt-get install line
- Manual install on existing containers: `sudo apt install -y irtt` on cake-spectrum and cake-att

### Claude's Discretion
- Internal method organization (_run_irtt, _parse_json, etc.)
- Exact IRTT command-line flag formatting
- Test fixture design and mock subprocess patterns
- JSON parsing error handling details beyond "return None"
- Whether to cache the shutil.which result or check each time

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| IRTT-01 | IRTT client subprocess is wrapped with JSON output parsing for RTT, loss, and IPDV | IRTTMeasurement class with _run_irtt() subprocess call and _parse_json() for stats extraction; verified JSON field paths documented below |
| IRTT-04 | IRTT configuration via YAML section (server, port, cadence, enabled) disabled by default | _load_irtt_config() following _load_signal_processing_config() warn+default pattern; irtt: YAML section |
| IRTT-05 | IRTT unavailability (server down, binary missing) has zero impact on controller behavior | No-op instantiation pattern (always create, return None when disabled/failed); _consecutive_failures tracking with log level management |
| IRTT-08 | IRTT binary installed on production containers via apt | irtt 0.9.0-2 in Debian bookworm main repo; add to Dockerfile apt-get install line |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| irtt | 0.9.0-2 | UDP RTT, IPDV, loss measurement | Standard Debian package, Go binary, JSON output, nanosecond precision |
| subprocess | stdlib | Invoke irtt client binary | Project-established pattern (benchmark.py) |
| json | stdlib | Parse IRTT JSON output | Stdlib, no deps |
| shutil | stdlib | Binary availability check | Project pattern (shutil.which) |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| time | stdlib | monotonic() timestamp | IRTTResult timestamp field |
| dataclasses | stdlib | IRTTResult frozen dataclass | Same pattern as SignalResult |
| logging | stdlib | Failure/recovery logging | Log level management |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| subprocess irtt | Python UDP socket | Custom code, no IPDV/loss stats, massive hand-rolling |
| JSON stdout (-o -) | Temp file (-o /tmp/x.json.gz) | File I/O overhead, cleanup needed, stdout is simpler |

**Installation:**
```bash
# Dockerfile (already has apt-get line -- just add irtt)
apt-get install -y --no-install-recommends irtt

# Manual on existing containers
sudo apt install -y irtt
```

## Architecture Patterns

### Recommended Project Structure
```
src/wanctl/
  irtt_measurement.py    # NEW: IRTTMeasurement class + IRTTResult dataclass
  autorate_continuous.py  # MODIFY: add _load_irtt_config() to Config class
docker/
  Dockerfile             # MODIFY: add irtt to apt-get install line
docs/
  CONFIG_SCHEMA.md       # MODIFY: add irtt: YAML section documentation
tests/
  test_irtt_measurement.py  # NEW: unit tests
```

### Pattern 1: No-Op Instantiation
**What:** Always instantiate IRTTMeasurement even when disabled. measure() returns None immediately.
**When to use:** When the caller (WANController) should not need conditional creation logic.
**Example:**
```python
# Source: follows RTTMeasurement pattern from rtt_measurement.py
class IRTTMeasurement:
    def __init__(self, config: dict, logger: logging.Logger) -> None:
        self._enabled = config.get("enabled", False)
        self._server = config.get("server")
        self._port = config.get("port", 2112)
        self._binary_path = shutil.which("irtt")
        # ... rest of init

    def measure(self) -> IRTTResult | None:
        if not self.is_available():
            return None
        # ... invoke subprocess
```

### Pattern 2: Warn+Default Config Loading
**What:** Invalid config values warn and fall back to defaults, never crash.
**When to use:** For all YAML config sections (established project pattern).
**Example:**
```python
# Source: _load_signal_processing_config() pattern at autorate_continuous.py:633
def _load_irtt_config(self) -> None:
    logger = logging.getLogger(__name__)
    irtt = self.data.get("irtt", {})

    enabled = irtt.get("enabled", False)
    if not isinstance(enabled, bool):
        logger.warning(f"irtt.enabled must be bool, got {enabled!r}; defaulting to false")
        enabled = False

    server = irtt.get("server", None)
    if server is not None and not isinstance(server, str):
        logger.warning(f"irtt.server must be str, got {server!r}; defaulting to None")
        server = None

    # ... validate port, duration_sec, interval_ms similarly

    self.irtt_config = {
        "enabled": enabled,
        "server": server,
        "port": port,
        "duration_sec": duration_sec,
        "interval_ms": interval_ms,
    }
```

### Pattern 3: Subprocess with JSON Capture
**What:** subprocess.run() with capture_output=True, text=True, timeout, JSON parsing.
**When to use:** Wrapping external binaries (benchmark.py establishes this pattern).
**Example:**
```python
# Source: benchmark.py check_server_connectivity() pattern at line 301-306
result = subprocess.run(
    cmd,
    capture_output=True,
    text=True,
    timeout=self._timeout,
)
if result.returncode != 0:
    return None
data = json.loads(result.stdout)
```

### Pattern 4: Log Level Management for Repeated Failures
**What:** First failure at WARNING, subsequent at DEBUG, recovery at INFO.
**When to use:** Preventing log spam from recurring failures.
**Example:**
```python
# Custom pattern per CONTEXT.md decision
if not self._first_failure_logged:
    self._logger.warning(f"IRTT measurement failed: {reason}")
    self._first_failure_logged = True
else:
    self._logger.debug(f"IRTT measurement failed: {reason}")
self._consecutive_failures += 1

# On recovery:
if self._consecutive_failures > 0:
    self._logger.info(
        f"IRTT recovered after {self._consecutive_failures} consecutive failures"
    )
    self._consecutive_failures = 0
    self._first_failure_logged = False
```

### Anti-Patterns to Avoid
- **Checking binary on every measure():** Cache shutil.which() result at init time. If binary is missing at startup, it stays missing (no hot-install detection needed).
- **Blocking the hot loop:** IRTT runs 1s bursts -- never call from the 50ms cycle. Phase 90 adds the background thread. Phase 89 only provides the callable.
- **Parsing IRTT text output:** Always use `-o -` for JSON stdout. Text output format is not stable.
- **Using -o to write temp files:** Use `-o -` for stdout. Avoids file I/O, temp directory cleanup, and permission issues.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| UDP RTT/IPDV measurement | Raw UDP socket code | irtt binary via subprocess | IRTT handles timing, IPDV calc, loss detection, clock compensation |
| JSON field validation | Custom schema validator | Simple dict.get() with defaults | Only 7 fields, not worth a schema library |
| Config validation | Custom validation framework | Inline warn+default pattern | Project-established pattern, consistent behavior |

**Key insight:** IRTT is a mature, specialized measurement tool. The subprocess wrapper is intentionally thin -- all complexity lives in the IRTT binary itself.

## Common Pitfalls

### Pitfall 1: Wrong JSON Field Paths
**What goes wrong:** CONTEXT.md documents `stats.send_call.lost` and `stats.receive_call.lost` as loss fields, but the actual IRTT JSON uses `stats.upstream_loss_percent` and `stats.downstream_loss_percent`.
**Why it happens:** Field names documented from man pages need live verification (noted in STATE.md).
**How to avoid:** Use the verified field paths from official documentation:
- RTT: `stats.rtt.mean`, `stats.rtt.median`, `stats.rtt.min`, `stats.rtt.max`
- IPDV round-trip: `stats.ipdv_round_trip.mean` (always available without server timestamps)
- IPDV send/receive: `stats.ipdv_send.mean`, `stats.ipdv_receive.mean` (need `--tstamp=both` flag)
- Loss: `stats.upstream_loss_percent`, `stats.downstream_loss_percent`, `stats.packet_loss_percent`
- Packets: `stats.packets_sent`, `stats.packets_received`
**Warning signs:** KeyError or None when accessing send_call/receive_call paths.

### Pitfall 2: Nanosecond vs Millisecond Confusion
**What goes wrong:** IRTT reports all durations in nanoseconds (integers). Treating them as milliseconds produces 1,000,000x wrong values.
**Why it happens:** Most tools report ms, IRTT reports ns for precision.
**How to avoid:** Always divide by 1_000_000 when converting to ms. Document this in the parsing method.
**Warning signs:** RTT values in millions instead of tens.

### Pitfall 3: IPDV Availability Depends on Server Timestamps
**What goes wrong:** `stats.ipdv_send` and `stats.ipdv_receive` are only populated when server timestamps are enabled (`--tstamp=both`).
**Why it happens:** IRTT cannot calculate one-way delay variation without both endpoints' timestamps.
**How to avoid:** Use `stats.ipdv_round_trip` which is always available. If directional IPDV is needed, add `--tstamp=both` to the command and check if server supports it.
**Warning signs:** Empty or missing ipdv_send/ipdv_receive objects in JSON.

### Pitfall 4: IRTT Client Exit Code Behavior
**What goes wrong:** IRTT returns non-zero exit code on partial failures (e.g., 100% packet loss), but the JSON output may still be valid.
**Why it happens:** IRTT treats complete loss as an error condition.
**How to avoid:** Check for valid JSON output even on non-zero return code. If JSON is parseable and has stats, use it. If unparseable, return None.
**Warning signs:** Valid measurement data discarded due to non-zero exit code.

### Pitfall 5: Duration Format String
**What goes wrong:** Passing `-d 1` instead of `-d 1s` (IRTT uses Go duration syntax).
**Why it happens:** Go duration format requires explicit units (1s, 100ms, not bare integers).
**How to avoid:** Always format with explicit units: `-d {duration}s` for seconds, `-i {interval}ms` for milliseconds.
**Warning signs:** "invalid duration" error from irtt subprocess.

### Pitfall 6: Subprocess Timeout vs IRTT Duration
**What goes wrong:** subprocess.run() timeout too tight, killing IRTT before it finishes.
**Why it happens:** IRTT adds wait time after last packet (`--wait` default is 3x the interval).
**How to avoid:** Set subprocess timeout to duration_sec + 5 seconds grace period (per CONTEXT.md decision).
**Warning signs:** TimeoutExpired exceptions during normal operation.

## Code Examples

Verified patterns from official sources and existing codebase:

### IRTT Command Construction
```python
# Source: CONTEXT.md + verified IRTT man page flags
def _build_command(self) -> list[str]:
    """Build irtt client command with configured parameters."""
    return [
        "irtt", "client",
        "-o", "-",           # JSON output to stdout
        "-Q",                # Really quiet (suppress text output, JSON only)
        "-d", f"{self._duration_sec}s",   # Go duration format
        "-i", f"{self._interval_ms}ms",   # Go duration format
        "-l", "48",                        # 48-byte payload (hardcoded)
        f"{self._server}:{self._port}",    # server:port as positional arg
    ]
```

### IRTTResult Frozen Dataclass
```python
# Source: follows SignalResult pattern from signal_processing.py:39-65
@dataclass(frozen=True, slots=True)
class IRTTResult:
    """Result from a single IRTT measurement burst."""
    rtt_mean_ms: float
    rtt_median_ms: float
    ipdv_mean_ms: float
    send_loss: float        # upstream_loss_percent from IRTT JSON
    receive_loss: float     # downstream_loss_percent from IRTT JSON
    packets_sent: int
    packets_received: int
    server: str
    port: int
    timestamp: float        # time.monotonic()
    success: bool
```

### JSON Parsing with Nanosecond Conversion
```python
# Source: verified from IRTT man page and official docs
def _parse_json(self, raw_json: str) -> IRTTResult | None:
    """Parse IRTT JSON output into IRTTResult."""
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return None

    stats = data.get("stats")
    if not stats:
        return None

    rtt = stats.get("rtt", {})
    ipdv_rt = stats.get("ipdv_round_trip", {})

    # IRTT reports durations in nanoseconds
    NS_TO_MS = 1_000_000

    return IRTTResult(
        rtt_mean_ms=rtt.get("mean", 0) / NS_TO_MS,
        rtt_median_ms=rtt.get("median", 0) / NS_TO_MS,
        ipdv_mean_ms=ipdv_rt.get("mean", 0) / NS_TO_MS,
        send_loss=stats.get("upstream_loss_percent", 0.0),
        receive_loss=stats.get("downstream_loss_percent", 0.0),
        packets_sent=stats.get("packets_sent", 0),
        packets_received=stats.get("packets_received", 0),
        server=self._server,
        port=self._port,
        timestamp=time.monotonic(),
        success=True,
    )
```

### Config Loading (warn+default)
```python
# Source: _load_signal_processing_config() in autorate_continuous.py:633-707
def _load_irtt_config(self) -> None:
    logger = logging.getLogger(__name__)
    irtt = self.data.get("irtt", {})

    if not isinstance(irtt, dict):
        logger.warning(f"irtt config must be dict, got {type(irtt).__name__}; using defaults")
        irtt = {}

    enabled = irtt.get("enabled", False)
    if not isinstance(enabled, bool):
        logger.warning(f"irtt.enabled must be bool, got {enabled!r}; defaulting to false")
        enabled = False

    server = irtt.get("server", None)
    if server is not None and not isinstance(server, str):
        logger.warning(f"irtt.server must be str, got {server!r}; defaulting to None")
        server = None

    port = irtt.get("port", 2112)
    if not isinstance(port, int) or isinstance(port, bool) or port < 1 or port > 65535:
        logger.warning(f"irtt.port must be int 1-65535, got {port!r}; defaulting to 2112")
        port = 2112

    duration_sec = irtt.get("duration_sec", 1.0)
    if not isinstance(duration_sec, (int, float)) or isinstance(duration_sec, bool) or duration_sec <= 0:
        logger.warning(f"irtt.duration_sec must be positive number, got {duration_sec!r}; defaulting to 1.0")
        duration_sec = 1.0

    interval_ms = irtt.get("interval_ms", 100)
    if not isinstance(interval_ms, int) or isinstance(interval_ms, bool) or interval_ms < 1:
        logger.warning(f"irtt.interval_ms must be positive int, got {interval_ms!r}; defaulting to 100")
        interval_ms = 100

    self.irtt_config = {
        "enabled": enabled,
        "server": server,
        "port": port,
        "duration_sec": float(duration_sec),
        "interval_ms": interval_ms,
    }

    if enabled and server:
        logger.info(f"IRTT: enabled, server={server}:{port}, burst={duration_sec}s@{interval_ms}ms")
    else:
        logger.info("IRTT: disabled (enable via irtt.enabled + irtt.server)")
```

### Mock Subprocess Pattern for Tests
```python
# Source: follows test_benchmark.py and test_calibrate.py patterns
@patch("wanctl.irtt_measurement.subprocess.run")
@patch("wanctl.irtt_measurement.shutil.which")
def test_measure_success(self, mock_which, mock_run):
    mock_which.return_value = "/usr/bin/irtt"
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps(SAMPLE_IRTT_JSON),
        stderr="",
    )
    m = IRTTMeasurement(config=TEST_CONFIG, logger=logging.getLogger("test"))
    result = m.measure()
    assert result is not None
    assert result.success is True
    assert result.rtt_mean_ms > 0

@patch("wanctl.irtt_measurement.shutil.which")
def test_binary_missing(self, mock_which):
    mock_which.return_value = None
    m = IRTTMeasurement(config=TEST_CONFIG, logger=logging.getLogger("test"))
    assert m.is_available() is False
    assert m.measure() is None
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ICMP ping only (icmplib) | ICMP + IRTT UDP (complementary) | v1.18 | IPDV metrics, directional loss, protocol diversity |
| RTT from single protocol | Multi-protocol correlation (Phase 90) | Planned v1.18 | Detect ICMP deprioritization |

**Deprecated/outdated:**
- IRTT 0.9.0 is the version in Debian bookworm. Version 0.9.1 exists in Debian trixie/Ubuntu 25.10+ but is not needed -- 0.9.0 has all required features.

## IRTT JSON Output Reference

### Verified Field Paths (from official man page)
```
stats.rtt.mean              # int (nanoseconds)
stats.rtt.median            # int (nanoseconds)
stats.rtt.min               # int (nanoseconds)
stats.rtt.max               # int (nanoseconds)
stats.rtt.stddev            # int (nanoseconds)
stats.rtt.variance          # int (nanoseconds^2)
stats.rtt.total             # int (nanoseconds, sum of all RTTs)
stats.rtt.n                 # int (number of RTT samples)

stats.ipdv_round_trip.mean  # int (nanoseconds) - always available
stats.ipdv_send.mean        # int (nanoseconds) - only with --tstamp=both
stats.ipdv_receive.mean     # int (nanoseconds) - only with --tstamp=both

stats.packets_sent          # int
stats.packets_received      # int
stats.server_packets_received  # int (server side, includes duplicates)

stats.packet_loss_percent      # float
stats.upstream_loss_percent    # float
stats.downstream_loss_percent  # float
```

### IRTT Command Flags Reference
| Flag | Purpose | Value |
|------|---------|-------|
| `-o -` | JSON output to stdout | Required |
| `-Q` | Really quiet (suppress text, only JSON) | Required |
| `-d` | Duration (Go format) | `1s` (default) |
| `-i` | Interval (Go format) | `100ms` (default) |
| `-l` | Payload length bytes | `48` (hardcoded) |
| `--tstamp` | Server timestamp mode | `none` (default), `send`, `receive`, `both` |
| `--stats` | Server stats mode | `none` (default), `count`, `window`, `both` |
| `-4` / `-6` | Force IPv4/IPv6 | Optional |

### CONTEXT.md Correction
The CONTEXT.md lists field paths `stats.send_call.lost` and `stats.receive_call.lost` -- these do **not exist** in IRTT's JSON output. The correct fields for directional loss are:
- `stats.upstream_loss_percent` (send loss)
- `stats.downstream_loss_percent` (receive loss)

This was flagged in STATE.md as "need live verification" and is now verified from official documentation.

## Open Questions

1. **Live JSON Output Verification**
   - What we know: Field paths verified from man pages and official docs
   - What's unclear: Whether self-hosted IRTT server at 104.200.21.31:2112 responds with all expected stats fields
   - Recommendation: Run `irtt client -o - -Q -d 1s -i 100ms -l 48 104.200.21.31:2112` from containers during implementation and validate JSON structure matches expectations

2. **IRTT Binary in python:3.12-slim Base Image**
   - What we know: irtt is in Debian bookworm main, python:3.12-slim is bookworm-based
   - What's unclear: Whether python:3.12-slim includes the universe/main distinction or if additional apt sources needed
   - Recommendation: Verify during Dockerfile build. Bookworm main should be available by default. Fallback: download binary from GitHub releases.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | pyproject.toml (existing) |
| Quick run command | `.venv/bin/pytest tests/test_irtt_measurement.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| IRTT-01 | Subprocess invocation + JSON parsing | unit | `.venv/bin/pytest tests/test_irtt_measurement.py::TestMeasure -x` | Wave 0 |
| IRTT-01 | IRTTResult dataclass fields | unit | `.venv/bin/pytest tests/test_irtt_measurement.py::TestIRTTResult -x` | Wave 0 |
| IRTT-04 | YAML irtt: config loading | unit | `.venv/bin/pytest tests/test_irtt_measurement.py::TestConfig -x` | Wave 0 |
| IRTT-04 | Config warn+default on invalid values | unit | `.venv/bin/pytest tests/test_irtt_measurement.py::TestConfigValidation -x` | Wave 0 |
| IRTT-05 | Binary missing returns None | unit | `.venv/bin/pytest tests/test_irtt_measurement.py::TestFallback -x` | Wave 0 |
| IRTT-05 | Server unreachable returns None | unit | `.venv/bin/pytest tests/test_irtt_measurement.py::TestFallback -x` | Wave 0 |
| IRTT-05 | Timeout returns None | unit | `.venv/bin/pytest tests/test_irtt_measurement.py::TestFallback -x` | Wave 0 |
| IRTT-05 | Log level management (first WARNING, repeat DEBUG) | unit | `.venv/bin/pytest tests/test_irtt_measurement.py::TestLogging -x` | Wave 0 |
| IRTT-08 | Dockerfile includes irtt | unit | `.venv/bin/pytest tests/test_irtt_measurement.py::TestDockerfile -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_irtt_measurement.py -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_irtt_measurement.py` -- covers IRTT-01, IRTT-04, IRTT-05
- [ ] `tests/test_irtt_config.py` -- covers IRTT-04 config validation (or inline in test_irtt_measurement.py)
- [ ] No new framework install needed -- existing pytest infrastructure sufficient

## Sources

### Primary (HIGH confidence)
- [IRTT man page (Debian)](https://manpages.debian.org/testing/irtt/irtt-client.1.en.html) -- JSON output format, command-line flags, duration syntax
- [IRTT man page (ManKier)](https://www.mankier.com/1/irtt-client) -- JSON field paths for stats, duration stats objects
- [IRTT GitHub repo](https://github.com/heistp/irtt) -- Source code, version info (0.9.0-0.9.1)
- [Debian bookworm irtt package](https://packages.debian.org/bookworm/irtt) -- Version 0.9.0-2, in main section
- [Ubuntu package search (irtt)](https://packages.ubuntu.com/search?keywords=irtt) -- Package availability across releases
- Existing codebase: `benchmark.py`, `rtt_measurement.py`, `signal_processing.py`, `autorate_continuous.py` -- established patterns

### Secondary (MEDIUM confidence)
- [IRTT man page (Ubuntu focal)](https://manpages.ubuntu.com/manpages/focal/man1/irtt-client.1.html) -- Cross-verified JSON structure
- IRTT GitHub source `result.go` -- JSON field tags for packets_sent, upstream_loss_percent, etc.

### Tertiary (LOW confidence)
- None -- all critical claims verified from multiple official sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- irtt is in Debian main, subprocess/json/shutil are stdlib
- Architecture: HIGH -- directly follows established project patterns (RTTMeasurement, SignalResult, benchmark.py)
- Pitfalls: HIGH -- JSON field paths verified from multiple official sources, nanosecond conversion documented
- IRTT JSON fields: MEDIUM -- verified from docs but not yet from live output; live verification during implementation

**Research date:** 2026-03-16
**Valid until:** 2026-04-16 (IRTT is stable, slow-moving project -- 0.9.0 from 2018)
