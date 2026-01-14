"""Concurrent latency measurement during load tests.

Uses fping for low-overhead, high-frequency RTT measurement.
Computes statistics and detects flat-top failures (sustained high latency).
"""

import re
import shutil
import statistics
import subprocess
import threading
import time
from dataclasses import dataclass, field


@dataclass
class LatencySample:
    """Single latency measurement."""

    timestamp: float
    rtt_ms: float | None
    target: str
    success: bool


@dataclass
class LatencyStats:
    """Computed latency statistics from a collection run."""

    min_ms: float
    max_ms: float
    avg_ms: float
    median_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    jitter_ms: float
    samples: int
    successful_samples: int
    loss_pct: float

    # Flat-top detection
    flat_top_detected: bool
    flat_top_duration_sec: float
    flat_top_threshold_ms: float

    # Raw data for analysis
    raw_rtts: list[float] = field(default_factory=list)


class LatencyCollector:
    """Concurrent latency measurement during load tests.

    Runs fping in background thread to collect RTT samples at configurable
    frequency. Computes percentile statistics and detects flat-top failures.

    Usage:
        collector = LatencyCollector(target="104.200.21.31")
        collector.start()
        # ... run load test ...
        stats = collector.stop()
        print(f"P95 latency: {stats.p95_ms}ms")
    """

    def __init__(
        self,
        target: str = "104.200.21.31",
        interval_ms: float = 100,
        timeout_ms: float = 500,
        flat_top_threshold_ms: float = 100,
        flat_top_min_duration_sec: float = 2.0,
    ):
        """Initialize latency collector.

        Args:
            target: Host to ping for latency measurement
            interval_ms: Time between pings (100ms = 10Hz)
            timeout_ms: Ping timeout
            flat_top_threshold_ms: Latency above this is "high"
            flat_top_min_duration_sec: Sustained high latency to flag as flat-top
        """
        self.target = target
        self.interval_ms = interval_ms
        self.timeout_ms = timeout_ms
        self.flat_top_threshold_ms = flat_top_threshold_ms
        self.flat_top_min_duration_sec = flat_top_min_duration_sec

        self.samples: list[LatencySample] = []
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._use_fping = shutil.which("fping") is not None

    def start(self) -> None:
        """Start background latency collection."""
        self.samples = []
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._collect_loop, daemon=True)
        self._thread.start()

    def stop(self) -> LatencyStats:
        """Stop collection and return computed statistics."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        return self._compute_stats()

    def _collect_loop(self) -> None:
        """Background thread: continuous ping collection."""
        while not self._stop_event.is_set():
            start = time.time()
            sample = self._ping_once()
            self.samples.append(sample)
            elapsed = time.time() - start
            sleep_time = max(0, (self.interval_ms / 1000) - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _ping_once(self) -> LatencySample:
        """Single ping measurement."""
        timestamp = time.time()

        if self._use_fping:
            return self._ping_fping(timestamp)
        return self._ping_standard(timestamp)

    def _ping_fping(self, timestamp: float) -> LatencySample:
        """Use fping for low-overhead measurement."""
        try:
            # fping -c 1 -q outputs to stderr: "host : xmt/rcv/%loss = 1/1/0%, min/avg/max = 25.4/25.4/25.4"
            result = subprocess.run(
                ["fping", "-c", "1", "-q", "-t", str(int(self.timeout_ms)), self.target],
                capture_output=True,
                text=True,
                timeout=self.timeout_ms / 1000 + 1,
            )
            # Parse RTT from stderr
            stderr = result.stderr
            match = re.search(r"min/avg/max = ([0-9.]+)/([0-9.]+)/([0-9.]+)", stderr)
            if match:
                rtt = float(match.group(2))  # Use avg (same as min/max for single ping)
                return LatencySample(
                    timestamp=timestamp, rtt_ms=rtt, target=self.target, success=True
                )
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            pass

        return LatencySample(timestamp=timestamp, rtt_ms=None, target=self.target, success=False)

    def _ping_standard(self, timestamp: float) -> LatencySample:
        """Fallback to standard ping command."""
        try:
            result = subprocess.run(
                [
                    "ping",
                    "-c",
                    "1",
                    "-W",
                    str(int(self.timeout_ms / 1000) or 1),
                    self.target,
                ],
                capture_output=True,
                text=True,
                timeout=self.timeout_ms / 1000 + 2,
            )
            if result.returncode == 0:
                # Parse: "time=25.4 ms"
                match = re.search(r"time=([0-9.]+)\s*ms", result.stdout)
                if match:
                    rtt = float(match.group(1))
                    return LatencySample(
                        timestamp=timestamp, rtt_ms=rtt, target=self.target, success=True
                    )
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            pass

        return LatencySample(timestamp=timestamp, rtt_ms=None, target=self.target, success=False)

    def _compute_stats(self) -> LatencyStats:
        """Compute latency distribution statistics."""
        successful = [s.rtt_ms for s in self.samples if s.success and s.rtt_ms is not None]

        if not successful:
            return LatencyStats(
                min_ms=0,
                max_ms=0,
                avg_ms=0,
                median_ms=0,
                p50_ms=0,
                p95_ms=0,
                p99_ms=0,
                jitter_ms=0,
                samples=len(self.samples),
                successful_samples=0,
                loss_pct=100.0,
                flat_top_detected=False,
                flat_top_duration_sec=0,
                flat_top_threshold_ms=self.flat_top_threshold_ms,
                raw_rtts=[],
            )

        sorted_rtts = sorted(successful)
        n = len(sorted_rtts)

        def percentile(p: float) -> float:
            idx = int(n * p / 100)
            return sorted_rtts[min(idx, n - 1)]

        flat_top_detected, flat_top_duration = self._detect_flat_top(successful)

        return LatencyStats(
            min_ms=min(successful),
            max_ms=max(successful),
            avg_ms=statistics.mean(successful),
            median_ms=statistics.median(successful),
            p50_ms=percentile(50),
            p95_ms=percentile(95),
            p99_ms=percentile(99),
            jitter_ms=statistics.stdev(successful) if len(successful) > 1 else 0,
            samples=len(self.samples),
            successful_samples=len(successful),
            loss_pct=(len(self.samples) - len(successful)) / len(self.samples) * 100,
            flat_top_detected=flat_top_detected,
            flat_top_duration_sec=flat_top_duration,
            flat_top_threshold_ms=self.flat_top_threshold_ms,
            raw_rtts=successful,
        )

    def _detect_flat_top(self, rtts: list[float]) -> tuple[bool, float]:
        """Detect sustained high latency (flat-top failure).

        Returns:
            (detected, max_duration_sec)
        """
        if not rtts:
            return False, 0

        # Calculate how many consecutive samples = flat-top duration
        interval_sec = self.interval_ms / 1000
        min_samples = int(self.flat_top_min_duration_sec / interval_sec)

        consecutive_high = 0
        max_consecutive = 0

        for rtt in rtts:
            if rtt > self.flat_top_threshold_ms:
                consecutive_high += 1
                max_consecutive = max(max_consecutive, consecutive_high)
            else:
                consecutive_high = 0

        max_duration_sec = max_consecutive * interval_sec
        detected = max_consecutive >= min_samples

        return detected, max_duration_sec


def measure_baseline_rtt(target: str, samples: int = 10, interval_ms: float = 200) -> float:
    """Measure baseline RTT when idle.

    Args:
        target: Host to ping
        samples: Number of samples to collect
        interval_ms: Interval between samples

    Returns:
        Median RTT in milliseconds
    """
    collector = LatencyCollector(target=target, interval_ms=interval_ms)
    collector.start()
    time.sleep((samples * interval_ms) / 1000 + 0.5)
    stats = collector.stop()

    if stats.successful_samples == 0:
        raise RuntimeError(f"Could not measure baseline RTT to {target}")

    return stats.median_ms
