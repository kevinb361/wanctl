# Architecture Patterns: v1.18 Measurement Quality

**Domain:** IRTT integration, container networking audit, RTT signal processing for existing dual-WAN controller
**Researched:** 2026-03-16
**Confidence:** HIGH (extends proven patterns, direct code analysis, verified IRTT documentation)

## Current Architecture (Baseline)

### Data Flow: Autorate Daemon (50ms cycle)

```
measure_rtt()          --> icmplib.ping() to 1-3 reflectors (ICMP)
  |
update_ewma()          --> load_rtt (fast EWMA), baseline_rtt (slow, idle-only)
  |
delta = load - base    --> RTT delta drives congestion state
  |
adjust_4state()        --> GREEN/YELLOW/SOFT_RED/RED zone determination
  |
router.set_queue()     --> CAKE rate adjustment via REST/SSH to MikroTik
  |
state_file.save()      --> JSON with ewma.baseline_rtt + congestion.dl_state/ul_state
  |
metrics_writer.batch() --> SQLite wanctl_rtt_ms, wanctl_rtt_delta_ms, etc.
```

### Data Flow: Steering Daemon (500ms cycle)

```
baseline_loader.load()     --> reads autorate state file (baseline_rtt + wan_zone)
  |
cake_stats.read()          --> CAKE drops/queue from router via REST/SSH
  |
_measure_current_rtt()     --> icmplib.ping() with retry + history fallback
  |
delta = current - baseline --> RTT delta
  |
ewma_smoothing()           --> rtt_delta_ewma, queue_ewma
  |
CongestionSignals()        --> multi-signal struct (rtt, ewma, drops, queue)
  |
assess_congestion_state()  --> CongestionState enum
  |
confidence_scoring()       --> ConfidenceController 0-100 score
  |
steering_decision()        --> ENABLE/DISABLE routing changes
```

### Key Components Involved in RTT Measurement

| Component | File | Role |
|-----------|------|------|
| `RTTMeasurement` | `rtt_measurement.py` | ICMP ping via icmplib, aggregation strategies (avg/median/min/max) |
| `BaselineRTTManager` | `baseline_rtt_manager.py` | EWMA baseline with idle-only update invariant |
| `BaselineRTTLoader` | `baseline_rtt_manager.py` | Cross-daemon baseline sharing via state file |
| `BaselineValidator` | `baseline_rtt_manager.py` | Bounds checking [10-60ms] for baseline sanity |
| `WANController.measure_rtt()` | `autorate_continuous.py` | Autorate RTT entry point (median-of-three via concurrent pings) |
| `WANController.update_ewma()` | `autorate_continuous.py` | Fast/slow EWMA update with delta calc |
| `SteeringDaemon._measure_current_rtt_with_retry()` | `steering/daemon.py` | Steering RTT with retry + history fallback |
| `CongestionSignals` | `steering/cake_stats.py` | Multi-signal struct consumed by assessment |
| `ewma_update()` | `steering/congestion_assessment.py` | Generic EWMA with bounds, NaN, and alpha validation |
| `ConfidenceSignals` | `steering/steering_confidence.py` | Input to confidence scoring (rtt_delta_ms field) |

## Recommended Architecture

### High-Level: Add Signal Quality Layer + IRTT Source

```
src/wanctl/
  signal_quality.py      [NEW]    -- HampelFilter, JitterTracker, RTTConfidence
  irtt_measurement.py    [NEW]    -- IRTTMeasurement, IRTTResult, IRTTWorker
  container_probe.py     [NEW]    -- ContainerLatencyProbe (startup diagnostic)
  rtt_measurement.py     [MODIFY] -- integrate outlier filter before EWMA
  autorate_continuous.py [MODIFY] -- wire IRTT background thread, signal quality
  steering/daemon.py     [MODIFY] -- wire signal quality (same pattern)
  health_check.py        [MODIFY] -- add signal_quality + irtt sections
  storage/schema.py      [MODIFY] -- new metric names
```

### Design Principle: Supplemental, Not Replacement

IRTT is an additional measurement source that enriches the existing RTT signal. It does NOT replace icmplib in the hot loop. The architecture maintains icmplib as the authoritative control signal (20Hz, in-process, zero subprocess overhead) while IRTT provides periodic supplemental data (0.2Hz, background thread, richer metrics including OWD and IPDV).

```
                    50ms cycle (20Hz) -- HOT PATH
                    +-----------------+
                    |                 |
    icmplib ping -->| RTTMeasurement  |---> HampelFilter ---> EWMA update
                    |                 |     (outlier gate)    (existing, unchanged)
                    +-----------------+
                           |
                    JitterTracker  RTTConfidence
                    (updated per   (updated per
                     cycle)         cycle)

                    Background thread (every 5s) -- NOT in hot path
                    +-----------------+
                    |                 |
    irtt client --> | IRTTMeasurement |---> IRTTResult (cached, thread-safe)
    (subprocess)    |                 |     - rtt_ms, jitter_ms, owd
                    +-----------------+     - enriches health endpoint + metrics
```

### Component Boundaries

| Component | Responsibility | Communicates With | New/Modified |
|-----------|---------------|-------------------|--------------|
| `signal_quality.py` | Outlier filtering, jitter tracking, confidence intervals | Called by measure_rtt() per cycle | **NEW** |
| `irtt_measurement.py` | subprocess irtt wrapper, JSON parsing, background thread | Thread-safe cache read by daemons | **NEW** |
| `container_probe.py` | Startup network diagnostics | Health endpoint, logging | **NEW** |
| `rtt_measurement.py` | icmplib ping (unchanged interface) | signal_quality.py | **UNCHANGED** |
| `autorate_continuous.py` | Wire IRTT thread, signal quality, new metrics | irtt_measurement.py, signal_quality.py | **MODIFIED** |
| `steering/daemon.py` | Wire signal quality (same pattern as autorate) | signal_quality.py | **MODIFIED** |
| `health_check.py` | Add signal_quality + irtt sections to /health | signal_quality state, irtt cache | **MODIFIED** |
| `storage/schema.py` | New metric names in STORED_METRICS | MetricsWriter | **MODIFIED** |

### UNCHANGED (Critical Protected Zones)

These components must NOT be modified:

| Component | Why Protected |
|-----------|---------------|
| `_update_baseline_if_idle()` | Architectural invariant: baseline freeze under load |
| `adjust_4state()` | Core congestion state machine (dl direction) |
| `adjust()` | Core congestion state machine (ul direction) |
| `assess_congestion_state()` | Steering congestion assessment |
| `ConfidenceWeights` | Confidence scoring weights |
| State file schema | Backward compatibility (ewma.baseline_rtt, congestion.dl_state) |
| CAKE rate adjustment logic | Core control algorithm |
| `ewma_update()` | Bounds-checked EWMA with C5 fix |
| `BaselineRTTManager.update_baseline_ewma()` | Idle-only baseline update invariant |

## Critical Architectural Decision: IRTT Runs Outside Hot Loop

IRTT must NOT run inside the 50ms cycle. Rationale:

| Factor | Hot Loop (icmplib) | Background (IRTT) |
|--------|-------------------|-------------------|
| Startup cost | 0ms (library call) | 5-10ms (process fork) |
| Measurement time | 5-15ms (1-3 pings) | 1-3s (burst of 5 UDP packets) |
| Budget impact | 10-30% of 50ms | Would consume 2000-6000% of budget |
| Failure mode | Returns None, fallback chain | Thread cache stale, main loop unaffected |
| Availability | Always (ICMP universal) | Requires IRTT server running |

The background thread is fire-and-forget. The main loop never waits for IRTT. If IRTT fails, the daemon continues with icmplib-only measurement (identical to current v1.17 behavior).

## New Component Specifications

### signal_quality.py

```python
"""RTT signal quality processing: outlier filtering, jitter, confidence.

All classes are stateful but side-effect-free -- they take a float,
update internal state, return a result. No I/O, no logging in the hot path.
Designed for 20Hz (50ms cycle) consumption.
"""

class HampelFilter:
    """Hampel identifier for RTT outlier detection.

    Uses median and MAD (median absolute deviation) on a sliding window.
    More robust than mean/stddev for heavy-tailed RTT distributions.

    When outlier detected: returns True, caller substitutes window median.
    """
    def __init__(self, window_size: int = 7, n_sigma: float = 3.0):
        self.window: deque[float] = deque(maxlen=window_size)
        self.n_sigma = n_sigma
        self.outlier_count: int = 0
        self.total_count: int = 0

    def is_outlier(self, value: float) -> bool:
        """Check if value is an outlier. Always appends to window."""
        # Window must fill before filtering activates
        # Uses MAD * 1.4826 (consistent estimator for Gaussian)

    def get_replacement(self) -> float:
        """Return median of current window (substitute for outlier)."""

    @property
    def outlier_rate(self) -> float:
        """Fraction of total samples that were outliers."""


class JitterTracker:
    """RFC 3550 EWMA jitter estimation.

    J(i) = J(i-1) + (|D(i)| - J(i-1)) / 16
    where D(i) = (rtt_i - rtt_{i-1}) - expected_interval
    For RTT measurement, expected_interval is 0 (we want raw variation).
    """
    def __init__(self, gain: float = 0.0625):  # 1/16 per RFC 3550
        self.jitter: float = 0.0
        self._last_rtt: float | None = None

    def update(self, rtt_ms: float) -> float:
        """Update jitter estimate, return current jitter in ms."""


class RTTConfidence:
    """Rolling confidence interval for RTT measurements.

    Maintains a sliding window and computes mean +/- t*stderr
    for a given confidence level. Window size determines precision.
    """
    def __init__(self, window_size: int = 20, confidence_level: float = 0.95):
        self._window: deque[float] = deque(maxlen=window_size)

    def update(self, rtt_ms: float) -> None:
        """Add sample to window."""

    def get_interval(self) -> tuple[float, float] | None:
        """Return (lower, upper) CI bounds in ms, or None if insufficient data."""

    @property
    def ci_width(self) -> float:
        """Width of current confidence interval (upper - lower) in ms."""
```

### irtt_measurement.py

```python
"""IRTT (Isochronous Round-Trip Tester) measurement via subprocess.

Runs `irtt client` as a subprocess, parses JSON output, provides
IRTTResult with RTT, OWD, IPDV, and packet loss metrics.

IRTT is a Go binary installed via `apt install irtt`.
NOT a Python library -- subprocess is the correct integration pattern
(same as flent in benchmark.py, v1.17).
"""

@dataclass
class IRTTResult:
    """Parsed result from single irtt client invocation."""
    rtt_mean_ms: float
    rtt_median_ms: float
    rtt_min_ms: float
    rtt_max_ms: float
    rtt_stddev_ms: float
    send_delay_mean_ms: float      # OWD upstream
    receive_delay_mean_ms: float   # OWD downstream
    ipdv_mean_ms: float            # jitter (IPDV)
    packet_loss_pct: float
    sample_count: int
    server: str
    timestamp: float               # time.monotonic() of measurement

    # IRTT JSON output has durations in nanoseconds
    # Convert: value / 1_000_000 to get ms

class IRTTMeasurement:
    """Run irtt client subprocess and parse JSON output.

    Key design decisions:
    - Duration 1s with 200ms interval = ~5 samples per burst
    - Subprocess timeout 3s (never blocks caller)
    - Graceful degradation: returns None on any failure
    - HMAC authentication for private servers
    """
    def __init__(self, logger: logging.Logger,
                 hmac_key: str = "", timeout: float = 3.0):
        self.logger = logger
        self._hmac_key = hmac_key
        self._timeout = timeout

    def measure(self, server: str, port: int = 2112,
                duration_ms: int = 1000,
                interval_ms: int = 200) -> IRTTResult | None:
        """Single IRTT measurement. Returns None on any failure.

        Calls: irtt client <server>:<port> -d 1s -i 200ms -o - --fill=rand
        Parses: JSON from stdout, stats.rtt.{mean,median,min,max,stddev}
        """

    def is_available(self) -> bool:
        """Check if irtt binary is in PATH."""

class IRTTWorker:
    """Background thread that periodically runs IRTT measurements.

    Follows WebhookDelivery pattern (v1.15): daemon thread with
    thread-safe shared state. Main loop reads cache in <0.1ms.
    """
    def __init__(self, measurement: IRTTMeasurement, server: str,
                 port: int, interval_sec: float,
                 shutdown_event: threading.Event):
        self._measurement = measurement
        self._server = server
        self._port = port
        self._interval_sec = interval_sec
        self._shutdown_event = shutdown_event
        self.latest_result: IRTTResult | None = None  # GIL-safe read

    def start(self) -> None:
        """Start background measurement thread."""

    def _worker(self) -> None:
        """Background loop: measure, cache, sleep."""
        while not self._shutdown_event.wait(timeout=self._interval_sec):
            result = self._measurement.measure(self._server, self._port)
            self.latest_result = result  # atomic write (Python GIL)
```

**IRTT JSON output structure** (values in nanoseconds):

```json
{
  "stats": {
    "rtt": {
      "total": 175000000, "n": 5,
      "min": 29455000, "max": 54460000,
      "mean": 35000000, "median": 34200000,
      "stddev": 4752000, "variance": 22581504000000
    },
    "send_delay": { "mean": 18694000 },
    "receive_delay": { "mean": 16306000 },
    "ipdv_round_trip": { "mean": 1230000 }
  },
  "round_trips": [ ... per-packet data ... ]
}
```

### container_probe.py

```python
"""Container networking latency probe.

Runs at daemon startup to characterize local network stack overhead.
Result is informational only (health endpoint + log) -- NOT used to
adjust RTT values.

Production context:
- cake-spectrum (10.10.110.246) and cake-att (10.10.110.247) are LXC containers
- Docker compose uses network_mode: host
- LXC bridge overhead: typically 0.1-0.5ms
- WAN RTT: Spectrum avg 37.6ms, ATT avg 29.0ms
- Container overhead is <1.5% of WAN RTT -- within EWMA noise
"""

@dataclass
class ContainerLatencyResult:
    gateway_rtt_ms: float | None    # RTT to default gateway
    loopback_rtt_ms: float          # RTT to localhost (kernel overhead)
    estimated_overhead_ms: float    # gateway - loopback (if both available)
    is_host_network: bool           # True if network_mode: host detected
    timestamp: float

class ContainerLatencyProbe:
    def probe(self) -> ContainerLatencyResult:
        """Quick probe at startup: 3 pings to gateway, 3 to localhost."""
```

## Data Flow: Per-Cycle (50ms hot path) with Signal Quality

```
1. icmplib.ping() returns measured_rtt (existing, unchanged)
2. HampelFilter.is_outlier(measured_rtt) -> bool
   IF outlier:
     log warning, use median of window as rtt_for_ewma
     increment outlier counter
   ELSE:
     rtt_for_ewma = measured_rtt
3. JitterTracker.update(rtt_for_ewma) -> current_jitter_ms
4. RTTConfidence.update(rtt_for_ewma) -> (lower, upper) or None
5. update_ewma(rtt_for_ewma) -> load_rtt, baseline_rtt (EXISTING, UNCHANGED)
6. Record signal quality metrics periodically (every 1200 cycles = 60s)
```

**Key insight:** The signal quality layer sits BETWEEN measurement and EWMA. It filters the input, not the EWMA itself. The EWMA logic, baseline invariant, and congestion state machine are completely untouched.

## Integration: IRTT Observability Only

In v1.18, IRTT data goes to health endpoint and metrics only. It does NOT feed into the congestion state machine.

```
IRTT background thread:
  measure() -> IRTTResult -> cache

Main loop (each cycle):
  read cached IRTTResult
  IF available and fresh (<15s old):
    emit wanctl_rtt_irtt_ms to metrics
    include in health endpoint signal_quality section
  ELSE:
    health endpoint shows irtt_available: false

Health endpoint response:
  "signal_quality": {
    "outlier_rate": 0.02,
    "jitter_ms": 1.3,
    "confidence_interval": [36.2, 38.1],
    "irtt": {
      "available": true,
      "last_rtt_ms": 35.4,
      "last_jitter_ms": 0.8,
      "server": "104.200.21.31",
      "age_sec": 3.2
    },
    "container_latency": {
      "gateway_rtt_ms": 0.4,
      "overhead_ms": 0.3,
      "probed_at": "2026-03-16T10:00:00Z"
    }
  }
```

## YAML Config Schema

```yaml
# Signal quality configuration (all sub-features independently controllable)
signal_quality:
  outlier_filter: true           # Enable Hampel outlier detection
  hampel_window: 7               # Sliding window size (samples)
  hampel_sigma: 3.0              # Outlier threshold (MAD multiplier)
  jitter_tracking: true          # Enable RFC 3550 EWMA jitter
  jitter_gain: 0.0625            # EWMA gain (1/16 = RFC 3550 default)
  confidence_tracking: true      # Enable rolling confidence intervals
  confidence_window: 20          # Window size for CI calculation (samples)

# IRTT supplemental measurement
irtt:
  enabled: false                 # Disabled by default (ships safe)
  server: "104.200.21.31"        # IRTT server address (self-hosted Dallas VPS)
  port: 2112                     # IRTT server port (default 2112)
  interval_sec: 5                # Seconds between measurement bursts
  duration_ms: 1000              # Duration of each burst (ms)
  interval_ms: 200               # Packet interval within burst (ms)
  stale_threshold_sec: 15        # Discard results older than this
  # hmac_key: ""                 # Optional HMAC key for server auth
```

## Patterns to Follow

### Pattern 1: Signal Processing as Pure Functions

**What:** HampelFilter, JitterTracker, RTTConfidence are stateful but side-effect-free. They take a float, update internal state, return a result. No I/O, no logging in the hot path.
**When:** Any signal processing in the 50ms cycle.
**Why:** Testable without mocking, predictable performance, zero cycle budget impact.

### Pattern 2: Subprocess Wrapper with JSON Output (established in benchmark.py)

**What:** External binary invoked via `subprocess.run()`, JSON output parsed with stdlib `json`.
**When:** IRTT measurement (same pattern as flent in v1.17).
**Why:** Clean process isolation, timeout control, structured output, no FFI.

### Pattern 3: Background Thread with Shared State (established in WebhookDelivery)

**What:** Daemon thread runs periodic task, shares result via thread-safe attribute.
**When:** IRTT measurement loop running alongside 50ms control loop.
**Why:** Decouples IRTT timing from control loop, zero blocking.

### Pattern 4: Feature Gated by Config (established in wan_state, alerting)

**What:** New features disabled by default, enabled via YAML config.
**When:** All new measurement features (IRTT, signal quality sub-features).
**Why:** No behavioral change on upgrade; explicit opt-in required.

### Pattern 5: Bounded Deque for Rolling Windows (established in dashboard sparklines)

**What:** `collections.deque(maxlen=N)` for constant-memory sliding windows.
**When:** All rolling signal processing (Hampel, confidence).
**Why:** Automatic eviction, O(1) append, bounded memory.

## Anti-Patterns to Avoid

### Anti-Pattern 1: IRTT in the Hot Loop

**What:** Calling subprocess irtt inside run_cycle().
**Why bad:** 5-10ms startup + 1-3s measurement = 2000-6000% of 50ms budget.
**Instead:** Background thread with periodic bursts, main loop reads cached result.

### Anti-Pattern 2: Heavyweight Signal Processing Libraries

**What:** `import numpy`, `import scipy` for simple statistics.
**Why bad:** 30MB+ deps, slow import time, overkill for median/stdev on 7-20 values.
**Instead:** `from statistics import median, stdev` + `from collections import deque`.

### Anti-Pattern 3: Signal Processing That Modifies Control Logic

**What:** Outlier filter that changes congestion thresholds, jitter that overrides state machine.
**Why bad:** Violates the architectural spine (control model is read-only per CLAUDE.md).
**Instead:** Signal processing feeds INTO the existing pipeline. HampelFilter gates values BEFORE update_ewma(). Jitter and confidence are OBSERVABILITY only in v1.18.

### Anti-Pattern 4: Discarding Outlier Measurements Entirely

**What:** When Hampel detects outlier, skip the cycle's measurement entirely.
**Why bad:** Missing a cycle leaves a gap; EWMA and state machine expect regular input.
**Instead:** Substitute window median for the outlier value. Log original + substituted for debugging.

### Anti-Pattern 5: IRTT Controlling Congestion State

**What:** Using IRTT RTT as an input to the GREEN/YELLOW/SOFT_RED/RED state machine.
**Why bad:** IRTT runs at 0.2Hz vs icmplib at 20Hz. Mixing timescales in the state machine would cause stale-data decisions. Proper dual-signal fusion requires dedicated research.
**Instead:** IRTT is observability-only in v1.18. Health endpoint and metrics only.

### Anti-Pattern 6: Correcting RTT for Container Latency

**What:** Subtracting measured container overhead from RTT values.
**Why bad:** LXC bridge overhead is 0.1-0.5ms, well within measurement noise for 29-38ms WAN RTT. The EWMA naturally absorbs constant offsets into baseline.
**Instead:** Log container latency in health endpoint for diagnostics. Never adjust RTT values.

## Scalability Considerations

| Concern | Current (v1.17) | v1.18 with IRTT + Signal Quality |
|---------|-----------------|----------------------------------|
| Cycle time impact | 0ms additional | <0.2ms (Hampel + jitter + CI arithmetic) |
| Memory | Minimal | +deque(maxlen=7) + deque(maxlen=20) + cached IRTTResult |
| Network traffic | ICMP to 1-3 reflectors | +UDP/2112 to IRTT server every 5s |
| CPU (IRTT thread) | N/A | ~10ms every 5s (subprocess fork+exec) |
| Dependencies | icmplib (Python) | +irtt binary (system package, apt install) |
| Python deps | Zero new | Zero new (stdlib statistics + collections) |
| Infrastructure | None | IRTT server on Dallas VPS (supplemental) |

## IRTT Server Infrastructure

The IRTT server at 104.200.21.31 (Dallas VPS) is self-hosted:

- **Installation:** `apt install irtt`, systemd service auto-enabled
- **Port:** UDP 2112 (default), must be open on server firewall
- **HMAC:** Enable authentication: `irtt server --hmac <key>` in systemd override
- **Availability:** Single server is SPOF, but IRTT is supplemental so downtime = ICMP-only mode
- **Client install:** `apt install irtt` on both cake-spectrum and cake-att containers
- **Monitoring:** Health endpoint reports IRTT reachability and last successful measurement time

## Build Order (Dependency-Driven)

```
Phase 1: Signal Quality Foundation    Phase 2: IRTT Measurement       Phase 3: Integration
===============================       ========================        ====================

signal_quality.py (all classes)       IRTTResult dataclass            WANController wiring
  - HampelFilter                      IRTTMeasurement class             - outlier filter gate
  - JitterTracker                       - subprocess wrapper             - jitter + CI tracking
  - RTTConfidence                       - JSON parsing                   - IRTT thread start
                                        - error handling                 - config: irtt section
ContainerLatencyProbe                   - HMAC support
  - startup diagnostic                                               SteeringDaemon wiring
  - health endpoint field             IRTTWorker thread                 - same signal quality
                                        - background loop
No daemon changes needed                - cache pattern               Health endpoint fields
Tests: unit + property                                                New SQLite metrics
                                      Tests: unit (mock subprocess)   Tests: integration + e2e
```

### Phase Ordering Rationale

- **Phase 1 before Phase 2:** Signal quality is useful independently (outlier filtering improves ICMP-only measurement). IRTT adds a second signal but the quality layer must exist first.
- **Phase 2 before Phase 3:** IRTT module must be tested standalone before wiring into daemons.
- **Container probe in Phase 1:** Standalone, no dependencies, provides immediate diagnostic value.
- **Phase 3 last:** All new components must exist and be unit-tested before integration.

### Dependency Graph

```
HampelFilter (no deps)    JitterTracker (no deps)    RTTConfidence (no deps)
         \                        |                         /
          +-- signal_quality.py --+  (all pure functions)
                                  |
IRTTResult (dataclass, no deps)   |
  |                               |
IRTTMeasurement (deps: IRTTResult)|
  |                               |
IRTTWorker (deps: IRTTMeasurement + threading.Event from signal_utils)
  |                               |
  +---- WANController wiring -----+ (deps: IRTTWorker + signal_quality)
  |     SteeringDaemon wiring       |
  |                                  |
  +-- Health endpoint changes -------+ (deps: wiring complete)
       SQLite metrics (independent, any phase)

ContainerLatencyProbe (fully independent, parallel with anything)
```

## Sources

- [IRTT GitHub Repository](https://github.com/heistp/irtt) -- tool architecture, Go implementation
- [IRTT Client Man Page](https://www.mankier.com/1/irtt-client) -- CLI options, -d, -i, -o, --hmac
- [IRTT Debian Man Page](https://manpages.debian.org/testing/irtt/irtt-client.1.en.html) -- JSON output format
- [IRTT Server Man Page (Ubuntu)](https://manpages.ubuntu.com/manpages/focal/man1/irtt-server.1.html) -- server config, systemd
- [IRTT Go Package Docs](https://pkg.go.dev/github.com/heistp/irtt) -- DurationStats (nanoseconds), Result types
- [cake-autorate IRTT integration](https://github.com/lynxthecat/cake-autorate/blob/master/CHANGELOG.md) -- precedent in similar project
- [Performance of Container Networking Technologies (ACM)](https://dl.acm.org/doi/pdf/10.1145/3094405.3094406) -- veth/bridge overhead
- [Jitterbug: Jitter-based Congestion Inference (CAIDA)](https://www.caida.org/catalog/papers/2022_jitterbug/jitterbug.pdf) -- IQR outlier detection
- [RFC 3550](https://www.ietf.org/rfc/rfc3550.txt) -- jitter EWMA calculation (gain = 1/16)
- Direct code analysis: `rtt_measurement.py`, `baseline_rtt_manager.py`, `autorate_continuous.py`, `steering/daemon.py`, `signal_utils.py`, `steering/congestion_assessment.py`, `steering/steering_confidence.py`, `benchmark.py`, `webhook_delivery.py`, `docker/docker-compose.yml`, `docker/Dockerfile`

---
*Architecture research for: wanctl v1.18 Measurement Quality*
*Researched: 2026-03-16*
