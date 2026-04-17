# Phase 187: RTT Cache And Fallback Safety - Pattern Map

**Mapped:** 2026-04-15
**Files analyzed:** 7 (2 source, 4 tests, 1 read-only reference)
**Analogs found:** 7 / 7 (all in-repo — all analogs are living siblings of the
new code, not external references)

This phase is a surgical behavioral fix. No file is created from scratch.
Every new symbol has a direct sibling already in the same file. The planner's
job is to point the executor at the sibling and say "do exactly this."

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/wanctl/rtt_measurement.py` (lines 350-457) — MODIFY | thread + dataclass producer | GIL-atomic pointer swap (background thread → main thread) | `RTTSnapshot` dataclass (lines 90-104) + `BackgroundRTTThread._cached` / `get_latest()` (lines 383-392, 429-447) | **exact** — add a parallel frozen/slots dataclass and a parallel read-only accessor next to the existing one |
| `src/wanctl/wan_controller.py` (lines 908-1024) — MODIFY | controller | request-response (main loop consumes cached cycle status) | `WANController.measure_rtt()` + `_record_live_rtt_snapshot()` existing zero-else branch at lines 943-951 | **exact** — extend the existing else branch with a zero-success override; do not touch the hard cutoff, the scorer call, or `_record_live_rtt_snapshot`'s signature |
| `tests/test_rtt_measurement.py` — MODIFY | test (thread unit) | pytest `_run()` harness with patched `concurrent.futures.wait` and `shutdown_event.wait` side_effect | `TestBackgroundRTTThread.test_stale_data_preserved_on_all_failures` (lines 756-794) + `test_caching_updates_after_measurement` (lines 711-754) | **exact** — same fixture set, same `wait_then_stop` shutdown trick, same pool mock |
| `tests/test_wan_controller.py` — MODIFY (new `TestZeroSuccessCycle`) | test (controller integration) | direct-invocation of `WANController.measure_rtt` on a mock `wc` shell | `tests/test_rtt_measurement.py::TestMeasureRTTNonBlocking` (lines 862-949) | **exact** — the reference pattern `TestMeasureRTTNonBlocking` actually lives in `test_rtt_measurement.py` today; the planner should mirror that fixture shape in the new `TestZeroSuccessCycle` class in `test_wan_controller.py` |
| `tests/test_health_check.py` (`TestMeasurementContract`) — MODIFY | test (contract builder) | direct-call of `_build_measurement_section(...)` on a dict produced by `_make_health_data` | `TestMeasurementContract.test_contract_combination` parametrize grid (lines 4151-4230) | **exact** — extend the existing parametrize list with one new `id="test_zero_success_cycle_reports_collapsed"` row; do NOT add a new fixture helper |
| `tests/test_autorate_error_recovery.py` — MODIFY | test (regression witness for SAFE-02) | run_cycle / handle_icmp_failure graceful-degradation mocks | `TestMeasurementFailureRecovery.test_measurement_failure_invokes_fallback` (lines 276-287) and `test_measurement_failure_graceful_degradation_sequence` (lines 325-355) | **exact** — the SAFE-02 witness reuses the existing `controller_with_mocks` fixture unchanged; the new test only needs to pin "cached-but-zero-success does NOT invoke handle_icmp_failure and does NOT increment `icmp_unavailable_cycles`" |
| `src/wanctl/health_check.py` (lines 383-453) | contract-reader (**READ-ONLY**) | — | Phase 186 contract — DO NOT re-edit | — |

## Pattern Assignments

### `src/wanctl/rtt_measurement.py` — add `RTTCycleStatus` + `get_cycle_status()` + `_run()` publish

**Analog:** `RTTSnapshot` dataclass + `BackgroundRTTThread._cached` + `get_latest()` in the same file.

#### Imports pattern (lines 1-20, ALREADY PRESENT — no new imports needed)

```python
import concurrent.futures
import dataclasses
import logging
import re
import statistics
import threading
import time
from collections.abc import Callable
from enum import Enum

import icmplib
```

No new stdlib or third-party imports are required. `dataclasses`, `time`,
`threading`, and the internal types are all already pulled into this module.

#### Parallel frozen/slots dataclass pattern (lines 90-104)

```python
@dataclasses.dataclass(frozen=True, slots=True)
class RTTSnapshot:
    """Immutable RTT measurement result for GIL-protected atomic swap.

    Produced by BackgroundRTTThread, consumed by WANController.measure_rtt()
    via lock-free read of a shared variable (Python GIL guarantees atomic
    pointer assignment).
    """

    rtt_ms: float
    per_host_results: dict[str, float | None]
    timestamp: float  # time.monotonic() when measured
    measurement_ms: float  # How long measurement took (ms)
    active_hosts: tuple[str, ...] = ()
    successful_hosts: tuple[str, ...] = ()
```

**Copy this shape.** The new `RTTCycleStatus` should be defined immediately
below `RTTSnapshot`, identically decorated
(`@dataclasses.dataclass(frozen=True, slots=True)`), with a docstring that
explicitly contrasts it with `RTTSnapshot` (see Research Pattern 1). Fields
are `successful_count: int`, `active_hosts: tuple[str, ...]`,
`successful_hosts: tuple[str, ...]`, `cycle_timestamp: float`. No defaults
except where the existing sibling already uses them. No factories. No
helper methods. Field-by-field mutation is the pitfall the frozen/slots
decorator exists to prevent (see Research Pitfall 4).

#### Parallel read-only accessor pattern (lines 383-392)

```python
def __init__(
    self,
    rtt_measurement: RTTMeasurement,
    hosts_fn: Callable[[], list[str]],
    shutdown_event: threading.Event,
    logger: logging.Logger,
    pool: concurrent.futures.ThreadPoolExecutor,
    cadence_sec: float = 0.0,
) -> None:
    self._rtt_measurement = rtt_measurement
    self._hosts_fn = hosts_fn
    self._shutdown_event = shutdown_event
    self._logger = logger
    self._pool = pool
    self._cadence_sec = cadence_sec
    self._cached: RTTSnapshot | None = None
    self._thread: threading.Thread | None = None

# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def get_latest(self) -> RTTSnapshot | None:
    """Return the most recent successful measurement, or ``None``."""
    return self._cached
```

**Copy this shape.** Add `self._last_cycle_status: RTTCycleStatus | None = None`
to `__init__` alongside `self._cached`. Add a sibling `get_cycle_status(self)`
method immediately below `get_latest(self)`, with a docstring that says
"Return the most recent background cycle status, or `None` if no cycle has
completed yet." `None` is the first-cycle sentinel (Research Open Question 4
+ Pitfall 3). No lock, no copy — return the bare field. The GIL guarantees
atomic pointer read (same contract as `get_latest`).

#### Core cycle-body pattern (lines 414-457 — `_run()` loop)

```python
def _run(self) -> None:
    """Measurement loop -- runs until *shutdown_event* is set."""
    while not self._shutdown_event.is_set():
        elapsed_s = 0.0
        try:
            hosts = self._hosts_fn()
            if not hosts:
                self._shutdown_event.wait(timeout=self._cadence_sec or 0.1)
                continue

            t0 = time.perf_counter()
            per_host, successful_hosts, successful_rtts = self._ping_with_persistent_pool(hosts)
            elapsed_s = time.perf_counter() - t0
            elapsed_ms = elapsed_s * 1000.0

            if successful_rtts:
                # Same aggregation as WANController.measure_rtt():
                # median-of-3+, average-of-2, single pass-through
                if len(successful_rtts) >= 3:
                    rtt_ms = statistics.median(successful_rtts)
                elif len(successful_rtts) == 2:
                    rtt_ms = statistics.mean(successful_rtts)
                else:
                    rtt_ms = successful_rtts[0]

                self._cached = RTTSnapshot(
                    rtt_ms=rtt_ms,
                    per_host_results=per_host,
                    active_hosts=tuple(hosts),
                    successful_hosts=successful_hosts,
                    timestamp=time.monotonic(),
                    measurement_ms=elapsed_ms,
                )
            # else: stale data preferred over no data -- do NOT overwrite _cached

        except Exception:
            self._logger.debug("Background RTT measurement error", exc_info=True)

        # Adjust sleep to account for measurement duration
        if self._cadence_sec > 0:
            sleep_s = max(0.0, self._cadence_sec - elapsed_s)
        else:
            sleep_s = 0.0
        self._shutdown_event.wait(timeout=sleep_s)
```

**Edit surgically.** Insert ONE assignment inside the `try` block, positioned
AFTER `successful_rtts` is bound and BEFORE the `if successful_rtts:` branch.
It must run on both branches (successful AND zero-success):

```python
# Phase 187: always publish current-cycle status, even on zero-success.
# This is orthogonal to _cached, which still uses stale-prefer-none.
self._last_cycle_status = RTTCycleStatus(
    successful_count=len(successful_rtts),
    active_hosts=tuple(hosts),
    successful_hosts=tuple(successful_hosts),
    cycle_timestamp=time.monotonic(),
)
```

Then leave the existing `if successful_rtts:` branch **byte-identical**
(including the `# else: stale data preferred over no data` comment). The
`_cached` assignment is Phase 132 behavior and must not move.

**Do NOT** introduce a `threading.Lock` around `_last_cycle_status`. **Do NOT**
mutate the status in place. **Do NOT** assign inside the `if successful_rtts:`
branch only — the whole point is that zero-success cycles publish too.

#### Error handling pattern (lines 449-450, UNCHANGED)

```python
except Exception:
    self._logger.debug("Background RTT measurement error", exc_info=True)
```

Phase 187 does not change error handling in `_run()`. A construction failure
of `RTTCycleStatus` would raise inside the `try` block and be swallowed at
debug level, same as today. This is the correct behavior: a malformed
status assignment must not kill the background thread.

---

### `src/wanctl/wan_controller.py` — `measure_rtt()` zero-success branch

**Analog:** `WANController.measure_rtt()` existing branch at lines 908-953, and
`_record_live_rtt_snapshot()` at lines 1011-1023.

#### Existing `measure_rtt()` pattern to extend (lines 908-953)

```python
def measure_rtt(self) -> float | None:
    """Read latest RTT from background thread (non-blocking).

    Per D-01: Reads GIL-protected shared variable instead of blocking on ICMP.
    Per D-04: Staleness detection -- warn at 500ms, fail at 5s.
    ReflectorScorer integration preserved -- per-host results from snapshot.

    Falls back to blocking measurement if background thread not started
    (e.g., during tests or startup race).
    """
    if self._rtt_thread is None:
        # Fallback: no background thread (e.g., tests or startup race)
        return self._measure_rtt_blocking()

    snapshot = self._rtt_thread.get_latest()
    if snapshot is None:
        self.logger.warning(
            f"{self.wan_name}: No RTT data available (background thread starting)"
        )
        return None

    age = time.monotonic() - snapshot.timestamp
    if age > 5.0:  # Hard limit per D-04
        self.logger.warning(
            f"{self.wan_name}: RTT data stale ({age:.1f}s), treating as failure"
        )
        return None
    if age > 0.5:  # Soft warning per D-04
        self.logger.debug(f"{self.wan_name}: RTT data aging ({age:.1f}s)")

    # Record per-host results for quality scoring (same as before)
    self._reflector_scorer.record_results(
        {host: rtt_val is not None for host, rtt_val in snapshot.per_host_results.items()}
    )
    self._persist_reflector_events()
    self._record_live_rtt_snapshot(
        rtt_ms=snapshot.rtt_ms,
        timestamp=snapshot.timestamp,
        active_hosts=list(snapshot.active_hosts or snapshot.per_host_results.keys()),
        successful_hosts=list(
            snapshot.successful_hosts
            or (host for host, rtt_val in snapshot.per_host_results.items() if rtt_val is not None)
        ),
    )

    return snapshot.rtt_ms
```

**Edit pattern.**

1. Immediately after `snapshot = self._rtt_thread.get_latest()`, add:

```python
cycle_status = self._rtt_thread.get_cycle_status()
```

2. Leave the `if snapshot is None:` and `if age > 5.0:` / `age > 0.5` blocks
**byte-identical.** This is the SAFE-02 preserved path; the 5s hard cutoff
still dumps into the existing `handle_icmp_failure()` pipeline via
`_run_rtt_measurement()` returning `None`. Don't touch it.

3. Leave the `self._reflector_scorer.record_results(...)` and
`self._persist_reflector_events()` calls unchanged (Research Pitfall 5 —
the scorer must not be double-counted).

4. Replace the single `self._record_live_rtt_snapshot(...)` call with a
branch:

```python
if cycle_status is not None and cycle_status.successful_count == 0:
    active_hosts = list(cycle_status.active_hosts)
    successful_hosts: list[str] = []
    self.logger.warning(
        f"{self.wan_name}: Zero-success RTT cycle; measurement "
        f"collapsed. Reusing cached rtt_ms={snapshot.rtt_ms:.1f} "
        f"(age={age:.2f}s) for bounded controller behavior."
    )
else:
    active_hosts = list(snapshot.active_hosts or snapshot.per_host_results.keys())
    successful_hosts = list(
        snapshot.successful_hosts
        or (host for host, rtt_val in snapshot.per_host_results.items() if rtt_val is not None)
    )

self._record_live_rtt_snapshot(
    rtt_ms=snapshot.rtt_ms,
    timestamp=snapshot.timestamp,  # NOT time.monotonic() — staleness_sec must stay honest
    active_hosts=active_hosts,
    successful_hosts=successful_hosts,
)
return snapshot.rtt_ms
```

**Log throttling.** Research Open Question 2 recommends WARNING on the
first zero-success cycle, DEBUG thereafter until recovery. The planner
should resolve this in the CONTEXT phase. If unresolved, default to a
single WARNING per call (above) and surface the throttling decision as a
discuss-phase question. `wan_controller.py:2272-2277` is the existing
`icmp_unavailable_cycles` / `ICMP recovered` reference pattern for this.

#### `_record_live_rtt_snapshot()` reference (lines 1011-1023, UNCHANGED)

```python
def _record_live_rtt_snapshot(
    self,
    *,
    rtt_ms: float,
    timestamp: float,
    active_hosts: list[str],
    successful_hosts: list[str],
) -> None:
    """Publish the latest direct ICMP RTT snapshot for observability/steering."""
    self._last_raw_rtt = float(rtt_ms)
    self._last_raw_rtt_ts = timestamp
    self._last_active_reflector_hosts = list(active_hosts)
    self._last_successful_reflector_hosts = list(successful_hosts)
```

**Do NOT change this signature.** The Phase 187 fix passes `snapshot.timestamp`
(NOT `time.monotonic()`) so `_last_raw_rtt_ts` remains pinned to the age of
the actual cached sample. This is the explicit Phase 186 D-11 guardrail —
`staleness_sec` must reflect the age of the last raw RTT, not the age of
the last cycle probe (Research Pitfall 1). A unit test **must** pin this:
see the `test_zero_success_does_not_touch_raw_rtt_timestamp` gap in
Validation Architecture.

#### `get_health_data()` measurement build site (lines 3436-3450, UNCHANGED reference)

```python
"measurement": {
    "raw_rtt_ms": self._last_raw_rtt,
    "staleness_sec": (
        time.monotonic() - self._last_raw_rtt_ts
        if self._last_raw_rtt_ts is not None
        else None
    ),
    "active_reflector_hosts": list(self._last_active_reflector_hosts),
    "successful_reflector_hosts": list(self._last_successful_reflector_hosts),
    "cadence_sec": (
        self._cycle_interval_ms / 1000.0
        if self._cycle_interval_ms and self._cycle_interval_ms > 0
        else None
    ),
},
```

**Do NOT edit.** This is the Phase 186 contract producer. It reads directly
from `self._last_*_reflector_hosts`, which Phase 187 now writes honestly
from the zero-success branch. End-to-end, `successful_reflector_hosts=[]`
flows from `measure_rtt()` through this dict into `_build_measurement_section()`
and becomes `state="collapsed"` via the existing `len(successful_hosts) <= 1`
branch in `health_check.py:430-435`.

---

### `tests/test_rtt_measurement.py` — new tests in `TestBackgroundRTTThread`

**Analog:** `TestBackgroundRTTThread.test_caching_updates_after_measurement`
(lines 711-754) and `test_stale_data_preserved_on_all_failures` (lines 756-794).

#### Fixture pattern (lines 647-668 — already present, reuse as-is)

```python
@pytest.fixture
def mock_rtt_measurement(self):
    """Mock RTTMeasurement with ping_host returning 10.0."""
    m = MagicMock(spec=RTTMeasurement)
    m.ping_host.return_value = 10.0
    return m

@pytest.fixture
def shutdown_event(self):
    """Real threading.Event for shutdown."""
    return threading.Event()

@pytest.fixture
def mock_logger(self):
    """Mock logger."""
    return MagicMock()

@pytest.fixture
def mock_pool(self):
    """Mock ThreadPoolExecutor."""
    pool = MagicMock()
    return pool
```

**Reuse these fixtures unchanged.** The new zero-success tests live in the
same class and inherit these fixtures for free.

#### Single-iteration `_run()` harness (lines 711-754)

```python
def test_caching_updates_after_measurement(
    self, mock_rtt_measurement, shutdown_event, mock_logger, mock_pool
):
    """After measurement, get_latest() returns RTTSnapshot with correct rtt_ms."""
    # Mock the pool to simulate concurrent pings
    future_a = MagicMock()
    future_a.result.return_value = 10.0
    future_b = MagicMock()
    future_b.result.return_value = 12.0
    future_c = MagicMock()
    future_c.result.return_value = 11.0

    mock_pool.submit.side_effect = [future_a, future_b, future_c]

    thread = BackgroundRTTThread(
        rtt_measurement=mock_rtt_measurement,
        hosts_fn=lambda: ["8.8.8.8", "1.1.1.1", "9.9.9.9"],
        shutdown_event=shutdown_event,
        logger=mock_logger,
        pool=mock_pool,
    )

    _original_wait = shutdown_event.wait  # noqa: F841

    def wait_then_stop(timeout=None):
        """Allow one iteration then signal shutdown."""
        shutdown_event.set()
        return True

    with patch(
        "wanctl.rtt_measurement.concurrent.futures.wait",
        return_value=({future_a, future_b, future_c}, set()),
    ):
        with patch.object(shutdown_event, "wait", side_effect=wait_then_stop):
            thread._run()

    snap = thread.get_latest()
    assert snap is not None
    assert snap.rtt_ms == statistics.median([10.0, 12.0, 11.0])
```

**Copy this test harness pattern verbatim** for:

- `test_cycle_status_published_on_successful_cycle` — assert
  `thread.get_cycle_status().successful_count == 3`, `active_hosts` and
  `successful_hosts` tuples match.
- `test_cycle_status_recovers_after_successful_cycle` — two iterations by
  making `wait_then_stop` count cycles before calling `shutdown_event.set()`;
  assert the status from cycle 2 reflects the successful recovery.

#### Zero-success `_run()` harness (lines 756-794)

```python
def test_stale_data_preserved_on_all_failures(
    self, mock_rtt_measurement, shutdown_event, mock_logger, mock_pool
):
    """If all pings fail, _cached is NOT overwritten."""
    known_snap = RTTSnapshot(
        rtt_ms=10.0,
        per_host_results={"8.8.8.8": 10.0},
        timestamp=time.monotonic(),
        measurement_ms=5.0,
    )
    thread = BackgroundRTTThread(
        rtt_measurement=mock_rtt_measurement,
        hosts_fn=lambda: ["8.8.8.8", "1.1.1.1"],
        shutdown_event=shutdown_event,
        logger=mock_logger,
        pool=mock_pool,
    )
    thread._cached = known_snap  # Pre-set known snapshot

    # All futures return None (failed pings)
    future_a = MagicMock()
    future_a.result.return_value = None
    future_b = MagicMock()
    future_b.result.return_value = None
    mock_pool.submit.side_effect = [future_a, future_b]

    def wait_then_stop(timeout=None):
        shutdown_event.set()
        return True

    with patch(
        "wanctl.rtt_measurement.concurrent.futures.wait",
        return_value=({future_a, future_b}, set()),
    ):
        with patch.object(shutdown_event, "wait", side_effect=wait_then_stop):
            thread._run()

    # Should still be the same object
    assert thread._cached is known_snap
```

**Copy this exact test** as the skeleton for
`test_cycle_status_published_on_zero_success`. Keep the pre-set
`thread._cached = known_snap` (this is the critical regression guarantee
that Phase 187 does not break Phase 132). Add two assertions at the end:

```python
assert thread._cached is known_snap                      # unchanged Phase 132
cycle_status = thread.get_cycle_status()
assert cycle_status is not None
assert cycle_status.successful_count == 0
assert cycle_status.active_hosts == ("8.8.8.8", "1.1.1.1")
assert cycle_status.successful_hosts == ()
```

And for `test_cycle_status_is_none_before_first_cycle`:

```python
thread = BackgroundRTTThread(...)  # same fixtures
assert thread.get_cycle_status() is None
```

No `_run()` invocation is needed — the test pins the default-None contract.

**Do NOT** mutate `_last_cycle_status` directly in any test. All updates
must go through `_run()` so the pointer-swap pattern is exercised.

---

### `tests/test_wan_controller.py` — new `TestZeroSuccessCycle` class

**Analog:** `TestMeasureRTTNonBlocking` in `tests/test_rtt_measurement.py`
lines 862-949. (This class currently lives in `test_rtt_measurement.py`
alongside the thread tests; Phase 187 research recommends spawning the
zero-success integration tests in `test_wan_controller.py` instead. Both
placements are acceptable — the planner should confirm in CONTEXT.)

#### Mock WANController shell fixture (lines 862-874)

```python
class TestMeasureRTTNonBlocking:
    """Integration tests for WANController.measure_rtt() with BackgroundRTTThread."""

    @pytest.fixture
    def mock_wan_controller(self):
        """Create a minimal mock WANController with the fields measure_rtt needs."""
        wc = MagicMock()
        wc.wan_name = "spectrum"
        wc.logger = MagicMock()
        wc._reflector_scorer = MagicMock()
        wc._rtt_thread = MagicMock(spec=BackgroundRTTThread)
        wc._persist_reflector_events = MagicMock()
        return wc
```

**Copy this exact fixture shape** into `TestZeroSuccessCycle`. Add two
fields the zero-success branch inspects:

```python
    wc._last_raw_rtt = None
    wc._last_raw_rtt_ts = None
    wc._last_active_reflector_hosts = []
    wc._last_successful_reflector_hosts = []
    wc._record_live_rtt_snapshot = MagicMock()
```

The `_record_live_rtt_snapshot` mock is **not** optional. The integration
tests should assert that it's called with the current-cycle host lists, not
the cached snapshot's host lists. This is the only way to catch the "wrote
the wrong timestamp" pitfall (Research Pitfall 1) at unit test level.

#### Direct invocation via unbound method (lines 876-893)

```python
def test_measure_rtt_reads_from_background_thread(self, mock_wan_controller):
    """measure_rtt() reads from background thread and returns rtt_ms."""
    from wanctl.wan_controller import WANController

    snap = RTTSnapshot(
        rtt_ms=11.0,
        per_host_results={"a": 10.0, "b": 12.0, "c": 11.0},
        timestamp=time.monotonic(),
        measurement_ms=30.0,
    )
    mock_wan_controller._rtt_thread.get_latest.return_value = snap

    result = WANController.measure_rtt(mock_wan_controller)
    assert result == 11.0
    # Should record per-host results for quality scoring
    mock_wan_controller._reflector_scorer.record_results.assert_called_once_with(
        {"a": True, "b": True, "c": True}
    )
```

**Copy this invocation pattern** for each new test:

- `test_zero_success_overrides_successful_hosts` — set `get_latest.return_value = snap`
  (3 hosts), `get_cycle_status.return_value = RTTCycleStatus(successful_count=0, ...)`;
  assert `_record_live_rtt_snapshot` called with `successful_hosts=[]` and
  `timestamp == snap.timestamp` (not `time.monotonic()`).
- `test_zero_success_preserves_cached_rtt_within_5s` — same setup with
  `snap.timestamp = time.monotonic() - 2.0`; assert `result == snap.rtt_ms`
  (bounded controller behavior).
- `test_zero_success_does_not_touch_raw_rtt_timestamp` — assert
  `_record_live_rtt_snapshot.call_args.kwargs["timestamp"]` equals
  `snap.timestamp`, not a fresh `time.monotonic()` value.
- `test_zero_success_does_not_increment_icmp_unavailable_cycles` — assert
  `handle_icmp_failure` is NOT called, and (if accessible via the mock)
  `wc.icmp_unavailable_cycles` is unchanged.
- `test_cycle_status_none_matches_today_behavior` — set
  `get_cycle_status.return_value = None`; assert the call to
  `_record_live_rtt_snapshot` uses `snap.successful_hosts` (today's
  byte-identical fallback, Research Pitfall 3).

#### Hard-cutoff invariant (lines 895-910, UNCHANGED)

```python
def test_measure_rtt_stale_hard_fail(self, mock_wan_controller):
    """RTT data >5s old returns None (hard fail per D-04)."""
    from wanctl.wan_controller import WANController

    snap = RTTSnapshot(
        rtt_ms=11.0,
        per_host_results={"a": 10.0},
        timestamp=time.monotonic() - 6.0,
        measurement_ms=30.0,
    )
    mock_wan_controller._rtt_thread.get_latest.return_value = snap

    result = WANController.measure_rtt(mock_wan_controller)
    assert result is None
    mock_wan_controller.logger.warning.assert_called()
    assert "stale" in mock_wan_controller.logger.warning.call_args[0][0].lower()
```

**Leave this test unchanged** — it is the SAFE-02 hard-cutoff witness. Phase
187 must not regress it. If a zero-success test ever causes it to fail, the
zero-success branch wrote the wrong timestamp.

---

### `tests/test_health_check.py` — extend `TestMeasurementContract`

**Analog:** `TestMeasurementContract._make_health_data` builder (lines 4132-4149)
and the `test_contract_combination` parametrize list (lines 4151-4230).

#### Fixture helper (lines 4128-4149 — reuse unchanged)

```python
@staticmethod
def _make_handler() -> HealthCheckHandler:
    return HealthCheckHandler.__new__(HealthCheckHandler)

@staticmethod
def _make_health_data(
    *,
    successful_hosts: list[str] | None = None,
    active_hosts: list[str] | None = None,
    raw_rtt_ms: float | None = 26.123,
    staleness_sec: float | None = 0.05,
    cadence_sec: float | None = 0.05,
) -> dict[str, object]:
    measurement: dict[str, object] = {
        "raw_rtt_ms": raw_rtt_ms,
        "staleness_sec": staleness_sec,
        "cadence_sec": cadence_sec,
        "active_reflector_hosts": list(active_hosts or successful_hosts or []),
    }
    if successful_hosts is not None:
        measurement["successful_reflector_hosts"] = list(successful_hosts)
    return {"measurement": measurement}
```

**Do NOT add new helpers.** Every Phase 187 measurement-contract test must
be expressible via this builder's existing keyword arguments. The zero-success
case is constructed by passing `successful_hosts=[]` and
`active_hosts=["a", "b", "c"]` to capture "cycle probed 3, succeeded 0."

#### Parametrize grid pattern (lines 4151-4230)

```python
@pytest.mark.parametrize(
    ("hosts", "staleness", "cadence", "expected_state", "expected_count", "expected_stale"),
    [
        pytest.param(
            ["a", "b", "c"], 0.05, 0.05, "healthy", 3, False,
            id="test_contract_combination_healthy_fresh",
        ),
        # ... five more existing rows ...
        pytest.param(
            ["a"], 0.20, 0.05, "collapsed", 1, True,
            id="test_contract_combination_collapsed_stale",
        ),
    ],
)
def test_contract_combination(
    self, hosts, staleness, cadence, expected_state, expected_count, expected_stale,
):
    handler = self._make_handler()
    health_data = self._make_health_data(
        successful_hosts=hosts,
        staleness_sec=staleness,
        cadence_sec=cadence,
    )

    measurement = handler._build_measurement_section(health_data)

    assert measurement["state"] == expected_state
    assert measurement["successful_count"] == expected_count
    assert measurement["stale"] is expected_stale
```

**Copy this pattern.** Add a standalone test (not a new parametrize row —
this one uses `active_hosts` in addition to `successful_hosts`, which the
existing grid does not exercise):

```python
def test_zero_success_cycle_reports_collapsed(self):
    """Phase 187: cached rtt + zero-success current cycle -> state='collapsed'."""
    handler = self._make_handler()
    health_data = self._make_health_data(
        successful_hosts=[],           # current cycle: zero-success
        active_hosts=["a", "b", "c"],  # current cycle probed 3
        staleness_sec=0.20,            # cached sample age > 3*cadence -> stale
        cadence_sec=0.05,
    )

    measurement = handler._build_measurement_section(health_data)

    assert measurement["state"] == "collapsed"
    assert measurement["successful_count"] == 0
    assert measurement["stale"] is True
    assert measurement["raw_rtt_ms"] is not None  # controller still has usable value
    assert measurement["active_reflector_hosts"] == ["a", "b", "c"]
    assert measurement["successful_reflector_hosts"] == []
```

Place this test immediately after `test_contract_combination` in the class
so the six-row grid stays together.

**Explicit pytest ID convention.** Phase 186 D-03 / 186-03-SUMMARY.md
established that the six cross-product combinations MUST use explicit
pytest IDs so they are grep-verifiable with
`rg 'test_contract_combination_'`. Phase 187's new test is a seventh
standalone case, not a grid row, so it does not extend the six-ID grid —
keep it as a top-level method to preserve the existing grep contract.

---

### `tests/test_autorate_error_recovery.py` — SAFE-02 non-regression witness

**Analog:** `TestMeasurementFailureRecovery.test_measurement_failure_invokes_fallback`
(lines 276-287) and `test_measurement_failure_graceful_degradation_sequence`
(lines 325-355).

#### Fixture pattern (lines 263-274 — reuse unchanged)

```python
@pytest.fixture
def controller_with_mocks(self, mock_config, mock_router, mock_rtt_measurement, mock_logger):
    """Create a WANController with all dependencies accessible."""
    with patch.object(WANController, "load_state"):
        ctrl = WANController(
            wan_name="TestWAN",
            config=mock_config,
            router=mock_router,
            rtt_measurement=mock_rtt_measurement,
            logger=mock_logger,
        )
    return ctrl, mock_config, mock_logger
```

**Reuse this fixture as-is.** This is the controller-with-real-attributes
shell the graceful-degradation tests already depend on.

#### Fallback-invocation pattern (lines 276-287)

```python
def test_measurement_failure_invokes_fallback(self, controller_with_mocks):
    """handle_icmp_failure should be called when measure_rtt returns None."""
    ctrl, _, _ = controller_with_mocks

    with (
        patch.object(ctrl, "measure_rtt", return_value=None),
        patch.object(ctrl, "handle_icmp_failure", return_value=(True, None)) as mock_fallback,
        patch.object(ctrl, "save_state"),
    ):
        ctrl.run_cycle()

    mock_fallback.assert_called_once()
```

**Mirror as a negative test** for Phase 187 SAFE-02 witness (one new test
in `TestMeasurementFailureRecovery`). Instead of `measure_rtt` returning
`None`, stub it to return a cached `float` (e.g., `32.0`), representing
"zero-success cycle but cached within 5s":

```python
def test_zero_success_cached_rtt_does_not_invoke_icmp_fallback(self, controller_with_mocks):
    """SAFE-02: cached-but-collapsed cycle returns a usable rtt_ms and does NOT
    route into handle_icmp_failure (which is the total-outage path).
    """
    ctrl, _, _ = controller_with_mocks
    ctrl.icmp_unavailable_cycles = 0

    with (
        patch.object(ctrl, "measure_rtt", return_value=32.0),
        patch.object(ctrl, "handle_icmp_failure") as mock_fallback,
        patch.object(ctrl, "save_state"),
    ):
        ctrl.run_cycle()

    mock_fallback.assert_not_called()
    assert ctrl.icmp_unavailable_cycles == 0
```

**Do NOT** edit the existing four `TestMeasurementFailureRecovery` tests or
the 13 `TestIcmpTcpFallbackAndRecovery` tests. They collectively pin the
SAFE-02 behavior Phase 187 MUST NOT regress. Running the existing suite
unchanged IS the regression gate. Only the one new negative test above is
added.

**Graceful-degradation sequence pattern** (lines 325-355, UNCHANGED —
reference only):

```python
def test_measurement_failure_graceful_degradation_sequence(self, controller_with_mocks):
    """graceful_degradation: cycle 1=last_rtt, 2-3=freeze, 4+=fail."""
    ctrl, mock_config, _ = controller_with_mocks
    mock_config.fallback_mode = "graceful_degradation"
    mock_config.fallback_max_cycles = 3
    ctrl.load_rtt = 28.5

    # Test cycle 1: use last RTT
    ctrl.icmp_unavailable_cycles = 0
    with patch.object(ctrl, "verify_connectivity_fallback", return_value=(True, None)):
        should_continue, rtt = ctrl.handle_icmp_failure()
    assert should_continue is True
    assert rtt == 28.5  # Uses last RTT
    # ... cycles 2-4 ...
```

This test lives unchanged. A regression in Phase 187 that routes
zero-success into `handle_icmp_failure` would flip the fourth cycle
behavior — hence the new negative test above pins the opposite invariant
from the opposite side.

---

## Shared Patterns

### GIL-atomic pointer swap (cross-thread publish)

**Source:** `src/wanctl/rtt_measurement.py:439-447` (`_cached` assignment
inside `_run()`) plus the frozen/slots decorator at `rtt_measurement.py:90`.

**Apply to:** `RTTCycleStatus` + `_last_cycle_status` in `BackgroundRTTThread`.

```python
@dataclasses.dataclass(frozen=True, slots=True)
class RTTSnapshot:
    ...

# Inside _run(), after measurement completes:
self._cached = RTTSnapshot(
    rtt_ms=rtt_ms,
    per_host_results=per_host,
    active_hosts=tuple(hosts),
    successful_hosts=successful_hosts,
    timestamp=time.monotonic(),
    measurement_ms=elapsed_ms,
)
```

The full object is constructed with all fields at once, then assigned in
a single statement. `frozen=True` forbids per-field mutation; `slots=True`
forbids attribute-dict mutation. The GIL guarantees the pointer swap is
atomic. No lock needed. Phase 187's `RTTCycleStatus` gets this pattern
for free by copying the decorator and the assignment shape.

### Read-only accessor for background-thread state

**Source:** `src/wanctl/rtt_measurement.py:390-392` (`get_latest()`).

**Apply to:** `get_cycle_status()` in `BackgroundRTTThread`.

```python
def get_latest(self) -> RTTSnapshot | None:
    """Return the most recent successful measurement, or ``None``."""
    return self._cached
```

One-line body. No locking. No copying. `None` is the sentinel for
"nothing produced yet." The caller (main thread) reads a bare field; the
GIL ensures it sees either the full previous pointer or the full new
pointer, never a torn state.

### Single-iteration `_run()` test harness

**Source:** `tests/test_rtt_measurement.py:733-745` (the `wait_then_stop`
pattern).

**Apply to:** every new `_run()` unit test in `TestBackgroundRTTThread`.

```python
def wait_then_stop(timeout=None):
    """Allow one iteration then signal shutdown."""
    shutdown_event.set()
    return True

with patch(
    "wanctl.rtt_measurement.concurrent.futures.wait",
    return_value=({future_a, future_b, future_c}, set()),
):
    with patch.object(shutdown_event, "wait", side_effect=wait_then_stop):
        thread._run()
```

This pattern runs the background thread for exactly one cycle and then
exits cleanly. Every new zero-success test reuses it — no test should
attempt to run the real thread with real cadence. Two-iteration variants
(for the "recovers after zero-success" test) keep a counter in closure:

```python
cycle_counter = {"n": 0}
def wait_then_stop(timeout=None):
    cycle_counter["n"] += 1
    if cycle_counter["n"] >= 2:
        shutdown_event.set()
    return True
```

### Controller-shell mock fixture

**Source:** `tests/test_rtt_measurement.py:865-874` (`mock_wan_controller`
fixture using `MagicMock()` + hand-populated required attributes).

**Apply to:** `TestZeroSuccessCycle` in `tests/test_wan_controller.py`.

```python
@pytest.fixture
def mock_wan_controller(self):
    wc = MagicMock()
    wc.wan_name = "spectrum"
    wc.logger = MagicMock()
    wc._reflector_scorer = MagicMock()
    wc._rtt_thread = MagicMock(spec=BackgroundRTTThread)
    wc._persist_reflector_events = MagicMock()
    return wc
```

Tests invoke `WANController.measure_rtt(mock_wan_controller)` as an
unbound-method call so the mock shell substitutes for `self`. This avoids
the full `WANController.__init__` overhead and lets each test pin exactly
the attributes measure_rtt reads. Phase 187 adds `_last_raw_rtt`,
`_last_raw_rtt_ts`, `_last_active_reflector_hosts`,
`_last_successful_reflector_hosts`, and `_record_live_rtt_snapshot` to the
fixture so the new branch has a full surface to write against.

### Direct section-builder contract test

**Source:** `tests/test_health_check.py:4128-4149` + 4218-4230 (the
`_make_handler` + `_make_health_data` + direct
`handler._build_measurement_section(health_data)` pattern).

**Apply to:** new `test_zero_success_cycle_reports_collapsed` in
`TestMeasurementContract`.

```python
handler = self._make_handler()  # HealthCheckHandler.__new__(HealthCheckHandler)
health_data = self._make_health_data(
    successful_hosts=[],
    active_hosts=["a", "b", "c"],
    staleness_sec=0.20,
    cadence_sec=0.05,
)
measurement = handler._build_measurement_section(health_data)
assert measurement["state"] == "collapsed"
```

This bypasses HTTP round-trip entirely (no `send_response`, no sockets)
and pins the contract at the function level. Phase 186 D-03 established
this as the canonical pattern for measurement-contract tests; Phase 187
reuses it without modification.

### Non-regression witness via existing suite

**Source:** `tests/test_autorate_error_recovery.py:253-540`
(`TestMeasurementFailureRecovery` + `TestIcmpTcpFallbackAndRecovery`).

**Apply to:** SAFE-02 regression gate.

The existing 17+ tests in this file already cover the full ICMP →
TCP-fallback → total-outage path (`handle_icmp_failure`,
`verify_connectivity_fallback`, `icmp_unavailable_cycles`, fallback_mode
branches). Phase 187 does NOT rewrite any of them. Running
`.venv/bin/pytest tests/test_autorate_error_recovery.py -q` unchanged IS
the regression gate for SAFE-02. The single new negative test
(`test_zero_success_cached_rtt_does_not_invoke_icmp_fallback`) pins the
Phase 187 invariant from the opposite side: zero-success cached cycles
must stay OUT of the fallback path.

## No Analog Found

All Phase 187 changes have a direct, living analog in the same file. There
are no files with no close match.

## Scope Boundaries (Read-Only)

| File | Reason |
|------|--------|
| `src/wanctl/health_check.py` (lines 383-453, `_build_measurement_section`) | Phase 186 contract. Final for v1.38. Phase 187 consumes it via `_last_*_reflector_hosts` but must not re-edit it. |
| `src/wanctl/wan_controller.py:1155-1433` (`verify_local_connectivity`, `verify_tcp_connectivity`, `verify_connectivity_fallback`, `handle_icmp_failure`) | SAFE-02. Preserved verbatim. |
| `src/wanctl/wan_controller.py:2258-2280` (`_run_rtt_measurement`) | Existing `measured_rtt is None → handle_icmp_failure()` branch. Phase 187 does not change control flow; it only makes `measure_rtt()`'s `_last_*` side effects honest. |
| `RTTSnapshot` dataclass itself (`rtt_measurement.py:90-104`) | Out of scope. Research explicitly rejected broadening it: the field additions would ripple through every measurement test. The parallel `RTTCycleStatus` has a smaller blast radius. |
| `tests/test_autorate_error_recovery.py:253-540` existing tests | SAFE-02 regression gate. Witnesses, not targets. |

## Metadata

**Analog search scope:**

- `src/wanctl/rtt_measurement.py` (whole file)
- `src/wanctl/wan_controller.py` (lines 860-1024, 1155-1433, 2258-2280, 3370-3455)
- `src/wanctl/health_check.py` (lines 380-455)
- `tests/test_rtt_measurement.py` (lines 640-950)
- `tests/test_health_check.py` (lines 4120-4320)
- `tests/test_autorate_error_recovery.py` (lines 253-540)
- `.planning/phases/186-measurement-degradation-contract/186-02-SUMMARY.md`
- `.planning/phases/186-measurement-degradation-contract/186-03-SUMMARY.md`
- `.planning/phases/187-rtt-cache-and-fallback-safety/187-RESEARCH.md`

**Files scanned:** 9
**Pattern extraction date:** 2026-04-15

---
*Phase: 187-rtt-cache-and-fallback-safety*
*Pattern mapping: 2026-04-15*
