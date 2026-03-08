#!/usr/bin/env python3
"""
Performance Profiling Utility Module

Provides instrumentation for measuring operation latencies in the wanctl system.
Designed for non-invasive timing of measurement subsystems (RouterOS, ICMP, CAKE).

Use PerfTimer context manager for timing individual operations:
    with PerfTimer("operation_name", logger):
        # code to time

Use OperationProfiler for accumulating metrics across multiple cycles:
    profiler = OperationProfiler(max_samples=100)
    profiler.record("label", elapsed_ms)
    stats = profiler.stats("label")
"""

import logging
import time
from collections import deque
from collections.abc import Callable
from typing import Any


class PerfTimer:
    """Context manager for timing code blocks with millisecond precision.

    Measures elapsed time using perf_counter() for high-precision timing
    (not affected by system clock adjustments). Logs results in format:
        label: X.Xms

    Example:
        with PerfTimer("ping_measurement", logger):
            # ping code here
        # Logs: "ping_measurement: 123.4ms"
    """

    def __init__(self, label: str, logger: logging.Logger | None = None):
        """
        Initialize timer.

        Args:
            label: Human-readable name for the operation being timed
            logger: Optional logger instance. If provided, results logged at DEBUG level.
                   If None, timing is measured but not logged.
        """
        self.label = label
        self.logger = logger
        self.start_time = 0.0
        self.elapsed_ms = 0.0

    def __enter__(self) -> "PerfTimer":
        """Start the timer."""
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Stop timer, calculate elapsed time, and log if logger provided."""
        end_time = time.perf_counter()
        self.elapsed_ms = (end_time - self.start_time) * 1000.0

        if self.logger:
            self.logger.debug(f"{self.label}: {self.elapsed_ms:.1f}ms")


class OperationProfiler:
    """Accumulate timing measurements across multiple cycles.

    Stores measurement history in bounded deques (configurable max_samples)
    to prevent unbounded memory growth in long-running daemons.

    Calculates statistics: min, max, avg, p95, p99

    Example:
        profiler = OperationProfiler(max_samples=100)
        profiler.record("steering_rtt", 45.2)
        profiler.record("steering_rtt", 43.8)
        profiler.record("steering_rtt", 44.5)

        stats = profiler.stats("steering_rtt")
        # Returns: {
        #   'count': 3,
        #   'min_ms': 43.8,
        #   'max_ms': 45.2,
        #   'avg_ms': 44.5,
        #   'p95_ms': 45.1,
        #   'p99_ms': 45.2
        # }
    """

    def __init__(self, max_samples: int = 100):
        """
        Initialize profiler.

        Args:
            max_samples: Maximum number of samples to keep per label.
                        Older samples are automatically evicted.
                        Default 100 prevents unbounded growth.
        """
        self.max_samples = max_samples
        self.samples: dict[str, deque[float]] = {}

    def record(self, label: str, elapsed_ms: float) -> None:
        """Record a measurement.

        Args:
            label: Name of the operation being measured
            elapsed_ms: Elapsed time in milliseconds
        """
        if label not in self.samples:
            self.samples[label] = deque(maxlen=self.max_samples)
        self.samples[label].append(elapsed_ms)

    def stats(self, label: str) -> dict[str, Any]:
        """Get statistics for a label.

        Returns a dictionary with:
            count: Number of samples collected
            min_ms: Minimum value
            max_ms: Maximum value
            avg_ms: Average value
            p95_ms: 95th percentile
            p99_ms: 99th percentile
            samples: List of all samples

        Args:
            label: Name of the operation

        Returns:
            Dict with statistics, or empty dict if label not found
        """
        if label not in self.samples or len(self.samples[label]) == 0:
            return {}

        samples = list(self.samples[label])
        sorted_samples = sorted(samples)
        count = len(sorted_samples)

        # Calculate percentiles using index method
        # p95: 95% of data falls below this value
        # p99: 99% of data falls below this value
        p95_idx = int((95 / 100) * (count - 1))
        p99_idx = int((99 / 100) * (count - 1))

        return {
            "count": count,
            "min_ms": min(sorted_samples),
            "max_ms": max(sorted_samples),
            "avg_ms": sum(sorted_samples) / count,
            "p95_ms": sorted_samples[p95_idx],
            "p99_ms": sorted_samples[p99_idx],
            "samples": samples,
        }

    def clear(self, label: str | None = None) -> None:
        """Clear samples for a specific label or all labels.

        Args:
            label: Name of operation to clear, or None to clear all
        """
        if label is None:
            self.samples.clear()
        elif label in self.samples:
            self.samples[label].clear()

    def report(self, logger: logging.Logger | None = None) -> str:
        """Generate a summary report of all collected metrics.

        Args:
            logger: Optional logger. If provided, logs the report at INFO level.

        Returns:
            Formatted report string
        """
        if not self.samples:
            report = "No profiling data collected"
        else:
            lines = ["=== Profiling Report ==="]
            for label in sorted(self.samples.keys()):
                stats = self.stats(label)
                if stats:
                    lines.append(
                        f"{label}: count={stats['count']}, "
                        f"min={stats['min_ms']:.1f}ms, "
                        f"avg={stats['avg_ms']:.1f}ms, "
                        f"max={stats['max_ms']:.1f}ms, "
                        f"p95={stats['p95_ms']:.1f}ms, "
                        f"p99={stats['p99_ms']:.1f}ms"
                    )
            report = "\n".join(lines)

        if logger:
            logger.info(report)

        return report


def measure_operation(
    func: Callable[..., Any], label: str, logger: logging.Logger | None = None
) -> Callable[..., Any]:
    """Decorator for timing function calls.

    Wraps a function to measure its execution time and log the result.

    Example:
        @measure_operation("read_cake_stats")
        def read_cake_stats(self):
            # function code
            return result

    Args:
        func: Function to wrap
        label: Name for the timing measurement
        logger: Optional logger instance

    Returns:
        Wrapped function that times execution
    """

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        with PerfTimer(label, logger):
            return func(*args, **kwargs)

    return wrapper


# =============================================================================
# SHARED PROFILING HELPERS
# =============================================================================

PROFILE_REPORT_INTERVAL = 1200  # ~60s at 50ms cycles


def record_cycle_profiling(
    profiler: OperationProfiler,
    timings: dict[str, float],
    cycle_start: float,
    cycle_interval_ms: float,
    logger: logging.Logger,
    daemon_name: str,
    label_prefix: str,
    overrun_count: int,
    profiling_enabled: bool,
    profile_cycle_count: int,
) -> tuple[int, int]:
    """Record subsystem timing, detect overruns, emit structured logs.

    Shared implementation for both autorate and steering daemon profiling.
    Each daemon's _record_profiling() method delegates to this function.

    Args:
        profiler: OperationProfiler instance to record timings to
        timings: Dict of label->elapsed_ms for each subsystem
        cycle_start: perf_counter() timestamp when cycle started
        cycle_interval_ms: Target cycle interval in milliseconds
        logger: Logger for warnings and debug output
        daemon_name: Name for overrun warning messages (e.g., "spectrum", "Steering")
        label_prefix: Prefix for cycle_total label (e.g., "autorate", "steering")
        overrun_count: Current cumulative overrun count
        profiling_enabled: Whether periodic report is enabled
        profile_cycle_count: Current cycle count toward next report

    Returns:
        Tuple of (updated_overrun_count, updated_profile_cycle_count)
    """
    total_ms = (time.perf_counter() - cycle_start) * 1000.0

    # Record each subsystem timing
    for label, elapsed_ms in timings.items():
        profiler.record(label, elapsed_ms)

    # Record cycle total
    profiler.record(f"{label_prefix}_cycle_total", total_ms)

    # Overrun detection
    is_overrun = total_ms > cycle_interval_ms
    if is_overrun:
        overrun_count += 1
        # Rate-limited WARNING: 1st, 3rd, every 10th
        if overrun_count == 1 or overrun_count == 3 or overrun_count % 10 == 0:
            logger.warning(
                f"{daemon_name} overrun: {total_ms:.1f}ms > "
                f"{cycle_interval_ms:.0f}ms (total: {overrun_count})"
            )

    # Structured DEBUG log every cycle -- build extra dict from timing keys
    extra: dict[str, Any] = {"cycle_total_ms": round(total_ms, 1), "overrun": is_overrun}
    for label, elapsed_ms in timings.items():
        # Convert "autorate_rtt_measurement" -> "rtt_measurement_ms"
        # Convert "steering_cake_stats" -> "cake_stats_ms"
        suffix = label.split("_", 1)[1] if "_" in label else label
        extra[f"{suffix}_ms"] = round(elapsed_ms, 1)
    logger.debug("Cycle timing", extra=extra)

    # Periodic profiling report (deque maxlen handles eviction, no clear needed)
    profile_cycle_count += 1
    if profiling_enabled and profile_cycle_count >= PROFILE_REPORT_INTERVAL:
        profiler.report(logger)
        profile_cycle_count = 0

    return overrun_count, profile_cycle_count
