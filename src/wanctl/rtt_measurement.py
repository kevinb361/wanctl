"""
Unified RTT measurement utilities.

Consolidates ping-based RTT measurement logic used in both autorate_continuous.py
and steering/daemon.py. Provides flexible configuration for different measurement
strategies (average vs median) and timeout behaviors.
"""

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

# Pre-compiled regex for RTT parsing (avoids per-call compilation overhead)
_RTT_PATTERN = re.compile(r"time=([0-9.]+)")


def parse_ping_output(text: str, logger_instance: logging.Logger | None = None) -> list[float]:
    """
    Parse RTT values from ping command output.

    Handles standard ping output format: "time=<rtt>ms"
    Extracts all RTT values from lines containing "time=" marker.

    Note: This function is retained for calibrate.py backward compatibility.
    The hot-path RTT measurement uses icmplib directly and does not call this.

    Args:
        text: Raw output from ping command
        logger_instance: Optional logger for debug messages

    Returns:
        List of RTT values in milliseconds (float). Empty list if no valid RTTs found.

    Examples:
        >>> output = "64 bytes from 8.8.8.8: time=12.3 ms"
        >>> parse_ping_output(output)
        [12.3]

        >>> output = "time=12.3\\ntime=12.4\\ntime=12.5"
        >>> parse_ping_output(output)
        [12.3, 12.4, 12.5]
    """
    rtts: list[float] = []

    if not text:
        return rtts

    for line in text.splitlines():
        if "time=" not in line:
            continue

        try:
            # Use pre-compiled regex for robust parsing - handles various ping formats
            match = _RTT_PATTERN.search(line)
            if match:
                rtt = float(match.group(1))
                rtts.append(rtt)
            else:
                # Fallback to string parsing if regex doesn't match
                rtt_str = line.split("time=")[1].split()[0]
                # Handle formats like "12.3ms" without space
                rtt_str = rtt_str.replace("ms", "")
                rtt = float(rtt_str)
                rtts.append(rtt)
        except (ValueError, IndexError) as e:
            # Log parse failures if logger provided
            if logger_instance:
                logger_instance.debug(f"Failed to parse RTT from line '{line}': {e}")

    return rtts


class RTTAggregationStrategy(Enum):
    """RTT aggregation strategy when multiple samples collected."""

    AVERAGE = "average"  # Mean of all samples
    MEDIAN = "median"  # Median of all samples
    MIN = "min"  # Minimum (best RTT)
    MAX = "max"  # Maximum (worst RTT)


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


class RTTMeasurement:
    """
    Unified RTT measurement via icmplib raw ICMP sockets.

    Consolidates RTT measurement logic from autorate_continuous.py and
    steering/daemon.py into a single configurable class.

    Handles:
    - icmplib raw ICMP socket ping (no subprocess fork/exec overhead)
    - RTT sample collection
    - Multiple aggregation strategies (average, median, min, max)
    - Comprehensive error handling and logging
    """

    def __init__(
        self,
        logger: logging.Logger,
        timeout_ping: int = 1,
        aggregation_strategy: RTTAggregationStrategy = RTTAggregationStrategy.AVERAGE,
        log_sample_stats: bool = False,
        source_ip: str | None = None,
    ):
        """
        Initialize RTT measurement.

        Args:
            logger: Logger instance for error/debug messages
            timeout_ping: Per-packet timeout in seconds (passed to icmplib.ping timeout)
            aggregation_strategy: How to aggregate multiple RTT samples (AVERAGE, MEDIAN, MIN, MAX)
            log_sample_stats: If True, log min/max/median for debugging (only with AVERAGE strategy)
            source_ip: Source IP address for ICMP packets. Used on multi-homed hosts
                where different source IPs route through different WANs via policy routing.

        Examples:
            # autorate_continuous style: 5 samples, average, show min/max
            rtt = RTTMeasurement(logger, timeout_ping=1, aggregation_strategy=RTTAggregationStrategy.AVERAGE, log_sample_stats=True)

            # steering/daemon style: 1 sample, median
            rtt = RTTMeasurement(logger, timeout_ping=2, aggregation_strategy=RTTAggregationStrategy.MEDIAN)

            # source-bound for multi-WAN VM (ATT pings via FORCE_OUT_ATT)
            rtt = RTTMeasurement(logger, source_ip="10.10.110.224")
        """
        self.logger = logger
        self.timeout_ping = timeout_ping
        self.aggregation_strategy = aggregation_strategy
        self.log_sample_stats = log_sample_stats
        self.source_ip = source_ip

    def ping_host(self, host: str, count: int = 1) -> float | None:
        """
        Ping host and return aggregated RTT in milliseconds.

        Uses icmplib raw ICMP sockets (no subprocess fork/exec overhead).
        Requires CAP_NET_RAW capability (containers provide this).

        Args:
            host: Hostname or IP address to ping
            count: Number of ping packets to send

        Returns:
            Aggregated RTT value in milliseconds, or None on failure

        Examples:
            >>> rtt = RTTMeasurement(logger)
            >>> avg = rtt.ping_host("8.8.8.8", count=5)
            >>> avg
            12.5

            >>> rtt = RTTMeasurement(logger, aggregation_strategy=RTTAggregationStrategy.MEDIAN)
            >>> median = rtt.ping_host("1.1.1.1", count=1)
            >>> median
            10.2
        """
        try:
            result = icmplib.ping(
                address=host,
                count=count,
                interval=0,
                timeout=self.timeout_ping,
                privileged=True,
                source=self.source_ip,
            )

            if not result.is_alive:
                self.logger.warning(f"Ping to {host} failed (no response)")
                return None

            if not result.rtts:
                self.logger.warning(f"No RTT samples from {host}")
                return None

            # Aggregate RTT samples based on strategy
            aggregated_rtt = self._aggregate_rtts(result.rtts)

            # Log result with sample statistics if requested
            if self.log_sample_stats and len(result.rtts) > 1:
                self.logger.debug(
                    f"Ping {host}: {aggregated_rtt:.2f}ms ({self.aggregation_strategy.value}) "
                    f"(min={min(result.rtts):.2f}, max={max(result.rtts):.2f}, "
                    f"count={len(result.rtts)})"
                )
            else:
                self.logger.debug(
                    f"Ping {host}: {aggregated_rtt:.2f}ms ({self.aggregation_strategy.value}, "
                    f"count={len(result.rtts)})"
                )

            return aggregated_rtt

        except icmplib.NameLookupError:
            self.logger.warning(f"DNS lookup failed for {host}")
            return None
        except icmplib.SocketPermissionError:
            self.logger.error("Insufficient privileges for ICMP (need CAP_NET_RAW)")
            return None
        except icmplib.ICMPLibError as e:
            self.logger.error(f"Ping error to {host}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Ping error to {host}: {e}")
            return None

    def _aggregate_rtts(self, rtts: list) -> float:
        """
        Aggregate RTT samples based on configured strategy.

        Args:
            rtts: List of RTT measurements in milliseconds

        Returns:
            Aggregated RTT value

        Raises:
            ValueError: If strategy is unknown or list is empty
        """
        if not rtts:
            raise ValueError("Cannot aggregate empty RTT list")

        match self.aggregation_strategy:
            case RTTAggregationStrategy.AVERAGE:
                return float(statistics.mean(rtts))
            case RTTAggregationStrategy.MEDIAN:
                return float(statistics.median(rtts))
            case RTTAggregationStrategy.MIN:
                return float(min(rtts))
            case RTTAggregationStrategy.MAX:
                return float(max(rtts))
            case _:
                raise ValueError(f"Unknown aggregation strategy: {self.aggregation_strategy}")

    def ping_hosts_with_results(
        self, hosts: list[str], count: int = 1, timeout: float = 3.0
    ) -> dict[str, float | None]:
        """Ping multiple hosts concurrently, return per-host results.

        Unlike ping_hosts_concurrent() which returns a flat list of successful RTTs,
        this method preserves host attribution for per-reflector quality tracking.

        Args:
            hosts: List of hostnames/IPs to ping
            count: Number of ping packets per host (passed to ping_host)
            timeout: Total timeout for all concurrent pings in seconds

        Returns:
            Dict mapping host -> RTT in ms (or None if ping failed/timed out).
        """
        if not hosts:
            return {}

        results: dict[str, float | None] = {}

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(hosts)) as executor:
            future_to_host = {executor.submit(self.ping_host, host, count): host for host in hosts}
            try:
                for future in concurrent.futures.as_completed(future_to_host, timeout=timeout):
                    host = future_to_host[future]
                    try:
                        results[host] = future.result()
                    except Exception:
                        self.logger.debug("Concurrent ping to %s failed", host, exc_info=True)
                        results[host] = None
            except concurrent.futures.TimeoutError:
                for host in future_to_host.values():
                    if host not in results:
                        results[host] = None

        return results

    def ping_hosts_concurrent(
        self, hosts: list[str], count: int = 1, timeout: float = 3.0
    ) -> list[float]:
        """
        Ping multiple hosts concurrently and return successful RTTs.

        Uses ThreadPoolExecutor to ping all hosts in parallel, reducing total
        measurement time for median-of-three scenarios from 3x to 1x.

        Args:
            hosts: List of hostnames/IPs to ping
            count: Number of ping packets per host (passed to ping_host)
            timeout: Total timeout for all concurrent pings in seconds

        Returns:
            List of successful RTT measurements in milliseconds.
            Empty list if all pings failed.

        Example:
            >>> rtt = RTTMeasurement(logger)
            >>> rtts = rtt.ping_hosts_concurrent(["8.8.8.8", "1.1.1.1", "9.9.9.9"])
            >>> rtts
            [12.3, 10.5, 14.2]
            >>> statistics.median(rtts)
            12.3
        """
        if not hosts:
            return []

        rtts: list[float] = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(hosts)) as executor:
            # Submit all pings in parallel
            future_to_host = {executor.submit(self.ping_host, host, count): host for host in hosts}

            # Collect results with timeout
            try:
                for future in concurrent.futures.as_completed(future_to_host, timeout=timeout):
                    host = future_to_host[future]
                    try:
                        rtt = future.result()
                        if rtt is not None:
                            rtts.append(rtt)
                    except Exception as e:
                        self.logger.debug(f"Concurrent ping to {host} failed: {e}")
            except concurrent.futures.TimeoutError:
                self.logger.debug(f"Concurrent ping timeout after {timeout}s")

        return rtts


class BackgroundRTTThread:
    """Dedicated background thread for continuous RTT measurement.

    Follows the IRTTThread pattern: daemon thread, GIL-protected pointer swap
    of a frozen dataclass, start/stop lifecycle. The control loop reads the
    latest RTT from ``get_latest()`` (lock-free) instead of blocking on ICMP I/O.

    Uses a persistent :class:`concurrent.futures.ThreadPoolExecutor` for
    concurrent per-host pings (no per-cycle pool creation/teardown).

    Args:
        rtt_measurement: Configured :class:`RTTMeasurement` instance.
        hosts_fn: Callable returning current list of reflector hosts.
        shutdown_event: :class:`threading.Event` that signals graceful shutdown.
        logger: Logger for lifecycle and error messages.
        pool: Persistent :class:`ThreadPoolExecutor` for concurrent pings.
        cadence_sec: Minimum seconds between measurement cycles (default 0.0 =
            measure as fast as ICMP allows).
    """

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

    def start(self) -> None:
        """Create and start the background daemon thread."""
        self._thread = threading.Thread(
            target=self._run,
            name="wanctl-rtt-bg",
            daemon=True,
        )
        self._thread.start()
        self._logger.info("Background RTT thread started")

    def stop(self) -> None:
        """Join the background thread (up to 5 s timeout)."""
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._logger.info("Background RTT thread stopped")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

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
                per_host = self._ping_with_persistent_pool(hosts)
                elapsed_s = time.perf_counter() - t0
                elapsed_ms = elapsed_s * 1000.0

                # Extract successful RTTs for aggregation
                successful = [v for v in per_host.values() if v is not None]

                if successful:
                    # Same aggregation as WANController.measure_rtt():
                    # median-of-3+, average-of-2, single pass-through
                    if len(successful) >= 3:
                        rtt_ms = statistics.median(successful)
                    elif len(successful) == 2:
                        rtt_ms = statistics.mean(successful)
                    else:
                        rtt_ms = successful[0]

                    self._cached = RTTSnapshot(
                        rtt_ms=rtt_ms,
                        per_host_results=per_host,
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

    def _ping_with_persistent_pool(
        self, hosts: list[str], timeout: float = 3.0
    ) -> dict[str, float | None]:
        """Ping hosts concurrently using the persistent ThreadPoolExecutor.

        Same logic as :meth:`RTTMeasurement.ping_hosts_with_results` but uses
        ``self._pool`` instead of creating a new context-manager pool each cycle.

        Args:
            hosts: List of hostnames/IPs to ping.
            timeout: Total timeout for all concurrent pings in seconds.

        Returns:
            Dict mapping host -> RTT in ms (or None if ping failed/timed out).
        """
        results: dict[str, float | None] = {}
        future_to_host = {
            self._pool.submit(self._rtt_measurement.ping_host, host, 1): host
            for host in hosts
        }
        try:
            for future in concurrent.futures.as_completed(future_to_host, timeout=timeout):
                host = future_to_host[future]
                try:
                    results[host] = future.result()
                except Exception:
                    self._logger.debug("Concurrent ping to %s failed", host, exc_info=True)
                    results[host] = None
        except concurrent.futures.TimeoutError:
            for host in future_to_host.values():
                if host not in results:
                    results[host] = None

        return results
