"""
Unified RTT measurement utilities.

Consolidates ping-based RTT measurement logic used in both autorate_continuous.py
and steering/daemon.py. Provides flexible configuration for different measurement
strategies (average vs median) and timeout behaviors.
"""

import logging
import statistics
import subprocess
from typing import Optional
from enum import Enum

from .ping_utils import parse_ping_output


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
        timeout_total: Optional[int] = None,
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

    def ping_host(self, host: str, count: int = 1) -> Optional[float]:
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
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
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

        if self.aggregation_strategy == RTTAggregationStrategy.AVERAGE:
            return float(statistics.mean(rtts))
        elif self.aggregation_strategy == RTTAggregationStrategy.MEDIAN:
            return float(statistics.median(rtts))
        elif self.aggregation_strategy == RTTAggregationStrategy.MIN:
            return float(min(rtts))
        elif self.aggregation_strategy == RTTAggregationStrategy.MAX:
            return float(max(rtts))
        else:
            raise ValueError(f"Unknown aggregation strategy: {self.aggregation_strategy}")
