# Phase 90: IRTT Daemon Integration - Research

**Researched:** 2026-03-16
**Domain:** Python threading, lock-free caching, daemon thread lifecycle, protocol correlation
**Confidence:** HIGH

## Summary

Phase 90 integrates the IRTT measurement subsystem (built in Phase 89) into the autorate daemon as a background thread. The phase has four requirements: background daemon thread execution (IRTT-02), lock-free zero-blocking cache reads from the 50ms hot loop (IRTT-03), loss direction tracking (IRTT-06), and ICMP vs UDP protocol correlation (IRTT-07).

The implementation is straightforward because every building block exists. IRTTMeasurement is fully implemented with measure() -> IRTTResult | None. The project has three established threading patterns to follow: MetricsServer (persistent daemon thread with join), WebhookDelivery (fire-and-forget daemon threads), and signal_utils (shutdown_event for interruptible sleep). The frozen IRTTResult dataclass is already designed for thread-safe cache sharing.

**Primary recommendation:** Create a thin IRTTThread coordinator class in a new module, following the MetricsServer start/stop lifecycle pattern. Use the existing shutdown_event for interruptible sleep. Lock-free caching via frozen dataclass assignment is safe under CPython 3.12 GIL.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Thread owned by ContinuousAutoRate (top-level daemon), started in main() alongside metrics/health servers
- One IRTT thread serves both WANs (measures single path per server)
- New module: `src/wanctl/irtt_thread.py` (separate from irtt_measurement.py -- clean separation of measurement logic vs threading)
- IRTTThread class: constructor takes IRTTMeasurement, cadence_sec, shutdown_event, logger
- start() / stop() methods. stop() signals shutdown event + join(5s timeout)
- Interruptible sleep via `shutdown_event.wait(timeout=cadence_sec)` -- thread wakes instantly on SIGTERM
- Thread runs as daemon thread (daemon=True)
- Started after daemon init, stopped in main() finally block (before connection cleanup)
- Cadence configurable via existing `irtt:` YAML section: `cadence_sec` key, default 10
- Lock-free: frozen IRTTResult assignment is atomic under CPython GIL
- `self._cached_result: IRTTResult | None = None` on IRTTThread
- `get_latest() -> IRTTResult | None` returns the cached result directly
- Main loop reads each 50ms cycle -- zero blocking, zero lock contention
- Staleness computed by caller: `age_sec = time.monotonic() - result.timestamp`
- Result stored on IRTTThread, WANController accesses via reference to the thread
- Read cached IRTT result each cycle after RTT measurement
- Log at DEBUG: RTT, IPDV, loss_up%, loss_down%
- Do NOT feed into congestion control -- observation mode only
- Existing IRTTResult fields `send_loss` and `receive_loss` are sufficient for IRTT-06
- Interpretation (thresholds, enums) deferred to v1.19+ fusion
- Simple ratio per measurement: `ratio = icmp_rtt / irtt_rtt`
- Computed in WANController.run_cycle() where both load_rtt and cached irtt_result are available
- Stored as `self._irtt_correlation: float | None` on WANController for Phase 92 health endpoint
- Deprioritization thresholds: ratio > 1.5 = ICMP deprioritized, ratio < 0.67 = UDP deprioritized
- First detection logged at INFO, subsequent at DEBUG, recovery at INFO
- Guards: only compute when both irtt_result.rtt_mean_ms > 0 and load_rtt > 0

### Claude's Discretion
- IRTTThread internal method naming and organization
- Exception handling inside the background thread loop
- Test fixture design for threading tests (mock threading.Event, mock IRTTMeasurement)
- DEBUG log format for per-cycle IRTT reporting
- Whether correlation check runs every cycle or only when IRTT result is new

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| IRTT-02 | IRTT measurements run in background daemon thread on configurable cadence (default 10s) | IRTTThread class with shutdown_event.wait() for interruptible sleep; MetricsServer pattern for lifecycle; cadence_sec added to _load_irtt_config() |
| IRTT-03 | Main control loop reads latest cached IRTT result each cycle with zero blocking | Lock-free frozen dataclass assignment is atomic under CPython 3.12 GIL; get_latest() returns cached reference directly |
| IRTT-06 | Upstream vs downstream packet loss direction tracked per IRTT measurement burst | IRTTResult already has send_loss (upstream) and receive_loss (downstream) fields; no new code needed in irtt_thread.py -- cached result carries these |
| IRTT-07 | ICMP vs UDP RTT correlation detects protocol-specific deprioritization | ratio = load_rtt / irtt_result.rtt_mean_ms computed in WANController.run_cycle(); first-detection/repeat-at-DEBUG log pattern |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| threading (stdlib) | Python 3.12 | Background daemon thread, Event for interruptible sleep | Already used by MetricsServer, WebhookDelivery, signal_utils |
| time (stdlib) | Python 3.12 | monotonic() for timestamps and staleness | Already used throughout codebase |
| dataclasses (stdlib) | Python 3.12 | Frozen IRTTResult for lock-free sharing | Already exists from Phase 89 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| logging (stdlib) | Python 3.12 | Thread-safe logging from background thread | Python logging is thread-safe by default |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Lock-free frozen dataclass | threading.Lock around cache | Lock adds contention to 50ms hot path for data that changes every 10s -- unnecessary overhead |
| threading.Event.wait() | time.sleep() | sleep() is not interruptible on SIGTERM -- thread hangs up to cadence_sec before exit |
| Separate module irtt_thread.py | Inline in autorate_continuous.py | Separate module follows measurement/threading separation principle, testable in isolation |

**Installation:**
```bash
# No new dependencies required -- all stdlib
```

## Architecture Patterns

### Recommended Project Structure
```
src/wanctl/
  irtt_measurement.py     # Phase 89: IRTTMeasurement class, IRTTResult dataclass
  irtt_thread.py          # Phase 90: IRTTThread background coordinator (NEW)
  autorate_continuous.py  # Modified: create/start/stop IRTTThread, read cache in run_cycle()
docs/
  CONFIG_SCHEMA.md        # Modified: add cadence_sec to irtt section
```

### Pattern 1: Background Daemon Thread with Interruptible Sleep
**What:** A persistent background thread that runs measurement loops on a configurable cadence, sleeping between iterations via `shutdown_event.wait(timeout=N)` for instant SIGTERM response.
**When to use:** When a subsystem must run independently of the main control loop at a different frequency.
**Example:**
```python
# Source: existing MetricsServer pattern + signal_utils
class IRTTThread:
    def __init__(
        self,
        measurement: IRTTMeasurement,
        cadence_sec: float,
        shutdown_event: threading.Event,
        logger: logging.Logger,
    ) -> None:
        self._measurement = measurement
        self._cadence_sec = cadence_sec
        self._shutdown_event = shutdown_event
        self._logger = logger
        self._cached_result: IRTTResult | None = None
        self._thread: threading.Thread | None = None

    def get_latest(self) -> IRTTResult | None:
        """Return cached IRTT result. Lock-free, constant time."""
        return self._cached_result

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run,
            name="wanctl-irtt",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def _run(self) -> None:
        """Background loop: measure, cache, sleep."""
        while not self._shutdown_event.is_set():
            try:
                result = self._measurement.measure()
                if result is not None:
                    self._cached_result = result  # Atomic under CPython GIL
            except Exception:
                self._logger.debug("IRTT thread iteration error", exc_info=True)
            self._shutdown_event.wait(timeout=self._cadence_sec)
```

### Pattern 2: Lock-Free Cache via Frozen Dataclass Assignment
**What:** Thread A writes `self._cached_result = new_frozen_object` and Thread B reads `result = self._cached_result` without any lock. This is safe because: (a) the object is frozen (immutable), so no partial reads, and (b) reference assignment (`STORE_ATTR`) is a single bytecode instruction, serialized by the GIL.
**When to use:** When one writer thread produces infrequent updates consumed by a high-frequency reader thread, and stale reads are acceptable.
**Critical constraint:** Only safe under CPython 3.12 with the GIL enabled. If the project migrates to free-threaded Python (3.13+ no-GIL), this pattern needs review. However, Python 3.14's free-threading docs confirm that attribute assignment on regular objects is atomic (it's equivalent to dict item assignment which is documented as atomic even in free-threaded mode).

### Pattern 3: First-Detection/Repeat-at-DEBUG Log Pattern
**What:** Log a new condition at INFO on first occurrence, then at DEBUG for subsequent cycles while condition persists, and at INFO when it recovers. Prevents log spam while ensuring operators see state changes.
**When to use:** For conditions that persist across many cycles (protocol deprioritization, IRTT failure).
**Example:**
```python
# Already used by IRTTMeasurement._log_failure() and various alert detectors
if not self._deprioritization_logged:
    self.logger.info(
        f"{self.wan_name}: Protocol deprioritization detected: "
        f"ICMP/UDP ratio={ratio:.2f} ({interpretation}), "
        f"ICMP={load_rtt:.1f}ms, UDP={irtt_rtt:.1f}ms"
    )
    self._deprioritization_logged = True
else:
    self.logger.debug(f"{self.wan_name}: Protocol ratio={ratio:.2f}")
```

### Anti-Patterns to Avoid
- **Using threading.Lock for the cache:** The 50ms hot loop reads the cache every cycle. Adding lock contention for data that changes every 10s is wasteful. The frozen dataclass + GIL pattern provides safety with zero overhead.
- **Calling measure() in the hot loop:** IRTT subprocess takes 1-6 seconds per burst. Must run in background thread, never in the 50ms cycle.
- **Using time.sleep() instead of Event.wait():** time.sleep() is not interruptible. The thread would hang up to cadence_sec (10s) on SIGTERM, delaying shutdown. Event.wait() returns immediately when the shutdown event is set.
- **Creating IRTTThread per WAN:** CONTEXT.md specifies one thread serves both WANs. IRTT measures a single path to the IRTT server -- it's not WAN-specific.
- **Feeding IRTT data into congestion control:** This phase is observation mode only. IRTT results go to logs and will go to metrics/health in Phase 92.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Interruptible sleep | time.sleep() + flag check | shutdown_event.wait(timeout=N) | Event.wait() is both a sleep and a shutdown check in one atomic call |
| Thread-safe logging | Custom thread-safe logger | Python stdlib logging | Python's logging module is already thread-safe |
| Measurement execution | Custom subprocess management | IRTTMeasurement.measure() | Phase 89 already handles all failure modes, binary caching, log management |
| Shutdown coordination | Custom flag with volatile semantics | signal_utils.get_shutdown_event() | Project-wide shutdown coordination already built |

**Key insight:** IRTTThread is a thin coordinator. All measurement complexity lives in IRTTMeasurement (Phase 89). All shutdown coordination lives in signal_utils. The thread just calls measure() on a schedule and caches the result.

## Common Pitfalls

### Pitfall 1: Thread Not Started When IRTT Disabled
**What goes wrong:** Creating and starting IRTTThread even when IRTT is disabled wastes resources (thread sits idle calling measure() which returns None immediately every 10s).
**Why it happens:** Not checking is_available() before starting the thread.
**How to avoid:** Only create and start IRTTThread if `measurement.is_available()` returns True. If IRTT is disabled, WANController gets `irtt_thread=None` and skips all IRTT-related logic.
**Warning signs:** Thread created but measure() always returns None in logs.

### Pitfall 2: Shutdown Hangs If Thread Join Timeout Too Short
**What goes wrong:** If a measurement is in-flight when shutdown is requested, the thread needs time to complete the subprocess before it can exit. If join timeout is less than the subprocess timeout (duration_sec + 5s), the main thread moves on while the IRTT thread is still running.
**Why it happens:** IRTT subprocess can take up to `duration_sec + 5` seconds.
**How to avoid:** Use join(timeout=5.0) as specified in CONTEXT.md. The thread is daemon=True so even if join times out, the process will still exit cleanly. The 5s join is a "best effort" -- the daemon=True flag is the safety net.
**Warning signs:** "Daemon shutdown complete" log appears before IRTT thread logs its final iteration.

### Pitfall 3: Division by Zero in Protocol Correlation
**What goes wrong:** Computing `icmp_rtt / irtt_rtt` when either value is 0 or negative.
**Why it happens:** IRTT may report 0ms RTT on failure, or load_rtt could be 0 at startup.
**How to avoid:** Guard with `if irtt_result.rtt_mean_ms > 0 and load_rtt > 0` before computing ratio (as specified in CONTEXT.md).
**Warning signs:** ZeroDivisionError traceback in logs.

### Pitfall 4: Stale IRTT Results After IRTT Server Goes Down
**What goes wrong:** The cached IRTT result could be minutes old if the IRTT server is unreachable. The protocol correlation would compare current ICMP RTT against ancient UDP RTT.
**Why it happens:** Cache stores last successful result indefinitely.
**How to avoid:** Compute staleness: `age_sec = time.monotonic() - result.timestamp`. Skip correlation if age exceeds a reasonable threshold (e.g., 3x cadence_sec = 30s). Log staleness at DEBUG for operator visibility.
**Warning signs:** Protocol correlation ratio suddenly changes dramatically when IRTT server recovers.

### Pitfall 5: IRTTThread Not Stopped in Finally Block
**What goes wrong:** If IRTTThread.stop() is not called in the main() finally block, the thread may keep running during cleanup, potentially interfering with MetricsWriter close or other shutdown steps.
**Why it happens:** Adding a new thread without adding it to the cleanup sequence.
**How to avoid:** Add `irtt_thread.stop()` early in the finally block (before connection cleanup, after state save -- matching the pattern of metrics_server.stop() and health_server.shutdown()).
**Warning signs:** Shutdown takes longer than expected; "Periodic maintenance" or IRTT measurement logs after "Shutting down daemon..." message.

### Pitfall 6: Thread Exception Kills Background Loop
**What goes wrong:** An unhandled exception in the _run() loop terminates the thread silently. No more IRTT measurements, but no error visible.
**Why it happens:** Not wrapping the measure() call in try/except.
**How to avoid:** Wrap the entire loop body in try/except Exception, log at DEBUG (not WARNING -- to avoid spam from persistent errors like network issues), continue the loop. The IRTTMeasurement.measure() already catches its own errors and returns None, but the thread loop should have a safety net.
**Warning signs:** IRTT results stop appearing in logs with no error message.

## Code Examples

### IRTTThread Module Structure
```python
# Source: CONTEXT.md decisions + existing MetricsServer/WebhookDelivery patterns
"""Background IRTT measurement thread.

Runs IRTT measurements on a configurable cadence, caching the latest
result for lock-free consumption by the 50ms control loop.
"""
from __future__ import annotations

import logging
import threading

from wanctl.irtt_measurement import IRTTMeasurement, IRTTResult


class IRTTThread:
    """Background thread that runs IRTT measurements and caches results."""

    def __init__(
        self,
        measurement: IRTTMeasurement,
        cadence_sec: float,
        shutdown_event: threading.Event,
        logger: logging.Logger,
    ) -> None:
        self._measurement = measurement
        self._cadence_sec = cadence_sec
        self._shutdown_event = shutdown_event
        self._logger = logger
        self._cached_result: IRTTResult | None = None
        self._thread: threading.Thread | None = None

    def get_latest(self) -> IRTTResult | None:
        return self._cached_result

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run,
            name="wanctl-irtt",
            daemon=True,
        )
        self._thread.start()
        self._logger.info(f"IRTT thread started (cadence={self._cadence_sec}s)")

    def stop(self) -> None:
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._logger.info("IRTT thread stopped")

    def _run(self) -> None:
        while not self._shutdown_event.is_set():
            try:
                result = self._measurement.measure()
                if result is not None:
                    self._cached_result = result
            except Exception:
                self._logger.debug("IRTT measurement iteration error", exc_info=True)
            self._shutdown_event.wait(timeout=self._cadence_sec)
```

### Config Loader Addition (cadence_sec)
```python
# Source: existing _load_irtt_config() pattern in autorate_continuous.py
cadence_sec = irtt.get("cadence_sec", 10)
if (
    not isinstance(cadence_sec, (int, float))
    or isinstance(cadence_sec, bool)
    or cadence_sec < 1
):
    logger.warning(
        f"irtt.cadence_sec must be number >= 1, got {cadence_sec!r}; "
        f"defaulting to 10"
    )
    cadence_sec = 10

# Added to self.irtt_config dict:
self.irtt_config["cadence_sec"] = float(cadence_sec)
```

### WANController run_cycle() IRTT Integration
```python
# Source: CONTEXT.md decisions -- after RTT measurement, before state management
# Read cached IRTT result
irtt_result = self._irtt_thread.get_latest() if self._irtt_thread else None
if irtt_result is not None:
    age = time.monotonic() - irtt_result.timestamp
    self.logger.debug(
        f"{self.wan_name}: IRTT RTT={irtt_result.rtt_mean_ms:.1f}ms, "
        f"IPDV={irtt_result.ipdv_mean_ms:.1f}ms, "
        f"loss_up={irtt_result.send_loss:.1f}%, "
        f"loss_down={irtt_result.receive_loss:.1f}%, "
        f"age={age:.1f}s"
    )

    # Protocol correlation (IRTT-07)
    if irtt_result.rtt_mean_ms > 0 and self.load_rtt > 0:
        ratio = self.load_rtt / irtt_result.rtt_mean_ms
        self._check_protocol_correlation(ratio)
```

### Protocol Correlation with First-Detection Logging
```python
# Source: CONTEXT.md thresholds + existing first-detection pattern
def _check_protocol_correlation(self, ratio: float) -> None:
    """Check ICMP/UDP RTT ratio for protocol deprioritization."""
    deprioritized = ratio > 1.5 or ratio < 0.67

    if deprioritized:
        if ratio > 1.5:
            interpretation = "ICMP deprioritized"
        else:
            interpretation = "UDP deprioritized"

        if not self._irtt_deprioritization_logged:
            self.logger.info(
                f"{self.wan_name}: Protocol deprioritization: "
                f"ICMP/UDP ratio={ratio:.2f} ({interpretation})"
            )
            self._irtt_deprioritization_logged = True
        else:
            self.logger.debug(
                f"{self.wan_name}: Protocol ratio={ratio:.2f}"
            )
    else:
        if self._irtt_deprioritization_logged:
            self.logger.info(
                f"{self.wan_name}: Protocol correlation recovered, "
                f"ratio={ratio:.2f}"
            )
            self._irtt_deprioritization_logged = False

    self._irtt_correlation = ratio
```

### main() Lifecycle Integration
```python
# Source: existing main() server startup pattern (lines 2772-2773)
# After _start_servers(controller), before the main loop:
irtt_thread = _start_irtt_thread(controller)

# In the finally block, after state save, before lock cleanup:
if irtt_thread is not None:
    irtt_thread.stop()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No IRTT support | IRTTMeasurement class (Phase 89) | v1.18 Phase 89 | IRTT binary wrapper with JSON parsing |
| ICMP only | ICMP + IRTT (observation mode) | v1.18 Phase 90 | Protocol diversity for measurement validation |
| No loss direction | send_loss + receive_loss from IRTT | v1.18 Phase 89/90 | Upstream vs downstream loss distinction |

**Deprecated/outdated:**
- Nothing deprecated. IRTT is additive -- ICMP remains the primary measurement source.

## Open Questions

1. **Correlation check frequency: every cycle vs only on new IRTT result?**
   - What we know: IRTT updates every 10s, but load_rtt changes every 50ms. The ratio will change based on ICMP side even when IRTT is stale.
   - What's unclear: Is it useful to recompute ratio every cycle, or only when a fresh IRTT result arrives?
   - Recommendation: Compute every cycle but only log when the result is fresh (age < cadence_sec). Store the ratio regardless for Phase 92 health endpoint. The computation is trivial (one division) so per-cycle overhead is negligible.

2. **Staleness threshold for skipping correlation**
   - What we know: CONTEXT.md doesn't specify a max age for stale results.
   - What's unclear: At what age does comparing ICMP vs cached IRTT become meaningless?
   - Recommendation: Use 3x cadence (default 30s) as staleness cutoff. If result is older than that, set `self._irtt_correlation = None` and log at DEBUG. This handles IRTT server outages gracefully.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `.venv/bin/pytest tests/test_irtt_thread.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| IRTT-02 | Background thread starts, runs measure() on cadence, stops on shutdown | unit | `.venv/bin/pytest tests/test_irtt_thread.py -x -k "start or stop or cadence or shutdown"` | No -- Wave 0 |
| IRTT-03 | get_latest() returns cached result without blocking; None before first measurement | unit | `.venv/bin/pytest tests/test_irtt_thread.py -x -k "get_latest or cache"` | No -- Wave 0 |
| IRTT-06 | send_loss and receive_loss available in cached result | unit | `.venv/bin/pytest tests/test_irtt_thread.py -x -k "loss"` | No -- Wave 0 |
| IRTT-07 | Protocol correlation computed, deprioritization detected and logged | unit | `.venv/bin/pytest tests/test_irtt_thread.py -x -k "correlation or deprioritization"` | No -- Wave 0 |
| Config | cadence_sec validated with warn+default pattern | unit | `.venv/bin/pytest tests/test_irtt_config.py -x -k "cadence"` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_irtt_thread.py tests/test_irtt_config.py tests/test_irtt_measurement.py -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_irtt_thread.py` -- covers IRTT-02, IRTT-03, IRTT-06 (thread lifecycle, caching, loss availability)
- [ ] Additional tests in `tests/test_irtt_config.py` -- covers cadence_sec validation
- [ ] Tests for protocol correlation in WANController context (IRTT-07) -- may go in test_irtt_thread.py or a dedicated test file
- Framework and conftest fixtures already exist -- no new infrastructure needed

## Sources

### Primary (HIGH confidence)
- `/home/kevin/projects/wanctl/src/wanctl/irtt_measurement.py` -- IRTTMeasurement class, IRTTResult frozen dataclass (11 fields)
- `/home/kevin/projects/wanctl/src/wanctl/signal_utils.py` -- get_shutdown_event(), threading.Event coordination
- `/home/kevin/projects/wanctl/src/wanctl/metrics.py` -- MetricsServer daemon thread pattern (start/stop/join)
- `/home/kevin/projects/wanctl/src/wanctl/webhook_delivery.py` -- WebhookDelivery daemon thread pattern (daemon=True, fire-and-forget)
- `/home/kevin/projects/wanctl/src/wanctl/autorate_continuous.py` -- main() lifecycle (lines 2683-2984), WANController.__init__ (line 1134), WANController.run_cycle() (line 1783), Config._load_irtt_config() (line 709)
- `/home/kevin/projects/wanctl/tests/conftest.py` -- mock_autorate_config fixture with irtt_config defaults
- [Python 3.14 Thread Safety Guarantees](https://docs.python.org/3/library/threadsafety.html) -- attribute assignment atomicity under GIL

### Secondary (MEDIUM confidence)
- [PEP 703](https://peps.python.org/pep-0703/) -- GIL removal design; confirms reference assignment atomicity considerations
- [Python Free-Threading Guide](https://py-free-threading.github.io/porting/) -- future-proofing: attribute assignment remains safe even in free-threaded Python

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all stdlib, all patterns exist in codebase
- Architecture: HIGH -- CONTEXT.md decisions are comprehensive, all integration points verified in source
- Pitfalls: HIGH -- threading patterns well-established in project, edge cases identified from existing code review

**Research date:** 2026-03-16
**Valid until:** 2026-04-16 (stable -- stdlib threading, no external deps)
