"""
Unified RTT measurement utilities.

Consolidates ping-based RTT measurement logic used in both autorate_continuous.py
and steering/daemon.py. Provides flexible configuration for different measurement
strategies (average vs median) and timeout behaviors.
"""

import concurrent.futures
import logging
import re
import statistics
import subprocess
from enum import Enum


def parse_ping_output(text: str, logger_instance: logging.Logger | None = None) -> list[float]:
    """
    Parse RTT values from ping command output.

    Handles standard ping output format: "time=<rtt>ms"
    Extracts all RTT values from lines containing "time=" marker.

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
            # Use regex for robust parsing - handles various ping formats
            match = re.search(r"time=([0-9.]+)", line)
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
    MEDIAN = "median"    # Median of all samples
    MIN = "min"          # Minimum (best RTT)
    MAX = "max"          # Maximum (worst RTT)


class RTTMeasurement:
    """
    Unified RTT measurement via ping.

    Consolidates RTT measurement logic from autorate_continuous.py and
    steering/daemon.py into a single configurable class.

    Handles:
    - Subprocess ping command execution with timeouts
    - RTT sample collection and parsing
    - Multiple aggregation strategies (average, median, min, max)
    - Comprehensive error handling and logging
    """

    def __init__(
        self,
        logger: logging.Logger,
        timeout_ping: int = 1,
        timeout_total: int | None = None,
        aggregation_strategy: RTTAggregationStrategy = RTTAggregationStrategy.AVERAGE,
        log_sample_stats: bool = False,
    ):
        """
        Initialize RTT measurement.

        Args:
            logger: Logger instance for error/debug messages
            timeout_ping: Ping -W parameter (per-packet timeout) in seconds
            timeout_total: Total subprocess timeout in seconds. If None, calculated as count + 2.
                          This allows flexibility for different timing models.
            aggregation_strategy: How to aggregate multiple RTT samples (AVERAGE, MEDIAN, MIN, MAX)
            log_sample_stats: If True, log min/max/median for debugging (only with AVERAGE strategy)

        Examples:
            # autorate_continuous style: 5 samples, average, show min/max
            rtt = RTTMeasurement(logger, timeout_ping=1, aggregation_strategy=RTTAggregationStrategy.AVERAGE, log_sample_stats=True)

            # steering/daemon style: 1 sample, median, total timeout
            rtt = RTTMeasurement(logger, timeout_ping=2, timeout_total=10, aggregation_strategy=RTTAggregationStrategy.MEDIAN)
        """
        self.logger = logger
        self.timeout_ping = timeout_ping
        self.timeout_total = timeout_total
        self.aggregation_strategy = aggregation_strategy
        self.log_sample_stats = log_sample_stats

    def ping_host(self, host: str, count: int = 1) -> float | None:
        """
        Ping host and return aggregated RTT in milliseconds.

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
        cmd = ["ping", "-c", str(count), "-W", str(self.timeout_ping), host]

        try:
            # Calculate subprocess timeout
            if self.timeout_total is not None:
                subprocess_timeout = self.timeout_total
            else:
                # Default: count packets + 2 seconds overhead
                subprocess_timeout = count + 2

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=subprocess_timeout,
            )

            if result.returncode != 0:
                self.logger.warning(
                    f"Ping to {host} failed (returncode {result.returncode})"
                )
                return None

            # Parse RTT values using unified parser
            rtts = parse_ping_output(result.stdout, self.logger)

            if not rtts:
                self.logger.warning(f"No RTT samples from {host}")
                return None

            # Aggregate RTT samples based on strategy
            aggregated_rtt = self._aggregate_rtts(rtts)

            # Log result with sample statistics if requested
            if self.log_sample_stats and len(rtts) > 1:
                self.logger.debug(
                    f"Ping {host}: {aggregated_rtt:.2f}ms ({self.aggregation_strategy.value}) "
                    f"(min={min(rtts):.2f}, max={max(rtts):.2f}, count={len(rtts)})"
                )
            else:
                self.logger.debug(
                    f"Ping {host}: {aggregated_rtt:.2f}ms ({self.aggregation_strategy.value}, "
                    f"count={len(rtts)})"
                )

            return aggregated_rtt

        except subprocess.TimeoutExpired:
            self.logger.warning(f"Ping to {host} timed out (timeout={subprocess_timeout}s)")
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

    def ping_hosts_concurrent(
        self,
        hosts: list[str],
        count: int = 1,
        timeout: float = 3.0
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
            future_to_host = {
                executor.submit(self.ping_host, host, count): host
                for host in hosts
            }

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
