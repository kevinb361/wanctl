#!/usr/bin/env python3
"""
CAKE Statistics Reader for RouterOS and Linux CAKE backends.

Supports two code paths:
- RouterOS (rest/ssh): reads CAKE queue stats via FailoverRouterClient
- Linux CAKE: reads stats via LinuxCakeBackend (local tc commands)

Transport is detected from the primary WAN autorate config (Pitfall 5).
"""

import logging
import re
from dataclasses import dataclass
from typing import Any

import yaml

from ..backends import get_backend
from ..config_base import ConfigValidationError
from ..router_client import get_router_client_with_failover
from ..state_utils import safe_json_loads


@dataclass
class CakeStats:
    """CAKE queue statistics snapshot"""

    packets: int = 0
    bytes: int = 0
    dropped: int = 0
    queued_packets: int = 0
    queued_bytes: int = 0


@dataclass
class CongestionSignals:
    """Multi-signal congestion assessment"""

    rtt_delta: float = 0.0  # Current RTT - baseline (ms)
    rtt_delta_ewma: float = 0.0  # Smoothed RTT delta (ms)
    cake_drops: int = 0  # Drops in measurement window
    queued_packets: int = 0  # Current queue depth
    baseline_rtt: float = 0.0  # Baseline RTT for reference

    def __str__(self) -> str:
        return (
            f"rtt={self.rtt_delta:.1f}ms ewma={self.rtt_delta_ewma:.1f}ms "
            f"drops={self.cake_drops} q={self.queued_packets}"
        )


class CakeStatsReader:
    """Read CAKE statistics from RouterOS queue or Linux CAKE backend.

    Transport-aware: detects linux-cake from the primary WAN autorate config
    and delegates to LinuxCakeBackend for local tc stats. Falls back to
    FailoverRouterClient for rest/ssh transport.
    """

    def __init__(self, config: Any, logger: logging.Logger):
        self.config = config
        self.logger = logger

        # Per-tin stats cache for health endpoint consumption (CAKE-07)
        self.last_tin_stats: list[dict] | None = None

        # Detect transport from primary WAN autorate config (D-04, Pitfall 5)
        self._is_linux_cake = False
        self._linux_backend: Any = None
        self.client: Any = None

        try:
            autorate_config_path = getattr(config, "primary_wan_config", None)
            if autorate_config_path:
                with open(autorate_config_path) as f:
                    autorate_data = yaml.safe_load(f)
                autorate_transport = autorate_data.get("router", {}).get("transport", "rest")
            else:
                autorate_transport = "rest"
        except Exception as e:
            logger.warning("Failed to load autorate config for transport detection: %s", e)
            autorate_transport = "rest"

        if autorate_transport == "linux-cake":
            # Linux CAKE path: use LinuxCakeBackend via factory (D-01, D-02)
            try:
                # Build a minimal config namespace for get_backend()
                class _AutorateConfigProxy:
                    """Minimal config proxy for get_backend() factory."""

                    def __init__(self, data: dict):
                        self.data = data
                        self.router_transport = data.get("router", {}).get("transport", "rest")
                        self.router = data.get("router", {})

                proxy = _AutorateConfigProxy(autorate_data)
                self._linux_backend = get_backend(proxy)  # type: ignore[arg-type]
                self._is_linux_cake = True
                logger.info("CakeStatsReader using linux-cake backend")
            except Exception as e:
                logger.warning(
                    "Failed to create LinuxCakeBackend, falling back to RouterOS: %s",
                    e,
                )
                self.client = get_router_client_with_failover(config, logger)
        else:
            # RouterOS path: use FailoverRouterClient (existing behavior)
            self.client = get_router_client_with_failover(config, logger)

        # Track previous stats for delta calculation (best practice - no resets needed)
        # Delta math approach:
        #   - Counters (packets, bytes, dropped) are cumulative and monotonically increasing
        #   - We calculate deltas by subtracting previous read from current read
        #   - This avoids the race condition of reset -> read (events can be missed in the gap)
        #   - Correctly handles counter overflow at 2^64 (Python handles subtraction correctly)
        self.previous_stats: dict[str, CakeStats] = {}  # queue_name -> CakeStats

    @property
    def is_linux_cake(self) -> bool:
        """Whether backend is linux-cake (for tin distribution display)."""
        return self._is_linux_cake

    def _parse_json_response(self, out: str, queue_name: str) -> CakeStats | None:
        """
        Parse CAKE stats from REST API JSON response.

        Args:
            out: Raw JSON string from RouterOS REST API
            queue_name: Queue name for logging context

        Returns:
            CakeStats with cumulative values parsed from JSON, or None on error.
            Fields use hyphenated names (e.g., 'queued-packets').
        """
        data = safe_json_loads(
            out,
            logger=self.logger,
            error_context=f"CAKE stats for {queue_name}",
            log_content_preview=True,
            preview_length=200,
        )

        if data is None:
            return None

        # REST API returns a list of matching queues
        if isinstance(data, list) and len(data) > 0:
            q = data[0]
        elif isinstance(data, dict):
            q = data
        else:
            self.logger.warning(f"No queue data in response for {queue_name}")
            return None

        # Validate that response contains expected fields
        if not isinstance(q, dict):
            self.logger.error(f"Invalid queue data structure (not dict) for {queue_name}")
            return None

        # Extract stats from JSON (field names use hyphens)
        return CakeStats(
            packets=int(q.get("packets", 0)),
            bytes=int(q.get("bytes", 0)),
            dropped=int(q.get("dropped", 0)),
            queued_packets=int(q.get("queued-packets", 0)),
            queued_bytes=int(q.get("queued-bytes", 0)),
        )

    def _parse_text_response(self, out: str) -> CakeStats:
        """
        Parse CAKE stats from SSH CLI text response.

        Args:
            out: Raw text output from RouterOS SSH command

        Returns:
            CakeStats with values parsed via regex. Missing fields default to 0.

        Example input format:
            name="WAN-Download-1" parent=bridge1 ...
            rate=0 packet-rate=0 queued-bytes=0 queued-packets=0
            bytes=272603902153 packets=184614358 dropped=0
        """
        stats = CakeStats()

        # Extract cumulative counters (monotonically increasing)
        match = re.search(r"packets=(\d+)", out)
        if match:
            stats.packets = int(match.group(1))

        match = re.search(r"bytes=(\d+)", out)
        if match:
            stats.bytes = int(match.group(1))

        match = re.search(r"dropped=(\d+)", out)
        if match:
            stats.dropped = int(match.group(1))

        # Extract instantaneous values (current queue depth)
        match = re.search(r"queued-packets=(\d+)", out)
        if match:
            stats.queued_packets = int(match.group(1))

        match = re.search(r"queued-bytes=(\d+)", out)
        if match:
            stats.queued_bytes = int(match.group(1))

        return stats

    def _calculate_stats_delta(self, current: CakeStats, queue_name: str) -> CakeStats:
        """
        Calculate delta from previous stats for cumulative counters.

        Args:
            current: Current cumulative stats from RouterOS
            queue_name: Queue name for tracking previous stats

        Returns:
            CakeStats with:
            - Cumulative counters (packets, bytes, dropped): delta from previous
            - Instantaneous values (queued_packets, queued_bytes): current value

        On first read, stores baseline and returns current values.
        """
        previous = self.previous_stats.get(queue_name)

        if previous is None:
            # First read - return current as delta, store for next time
            self.logger.debug(f"CAKE stats [{queue_name}] first read, storing baseline")
            self.previous_stats[queue_name] = current
            return current

        # Calculate deltas for cumulative counters
        delta = CakeStats(
            packets=current.packets - previous.packets,
            bytes=current.bytes - previous.bytes,
            dropped=current.dropped - previous.dropped,
            queued_packets=current.queued_packets,  # instantaneous
            queued_bytes=current.queued_bytes,  # instantaneous
        )

        # Store current for next delta calculation
        self.previous_stats[queue_name] = current

        self.logger.debug(f"CAKE stats [{queue_name}] delta: {delta}")
        return delta

    def _read_stats_linux_cake(self, queue_name: str) -> CakeStats | None:
        """Read CAKE stats via LinuxCakeBackend (local tc commands).

        Converts the backend's dict return to CakeStats for contract compatibility,
        caches per-tin data for health endpoint, and passes through delta calculation.

        Args:
            queue_name: Queue name (passed to backend for ABC compat, ignored by tc).

        Returns:
            CakeStats with delta values, or None on error.
        """
        try:
            stats = self._linux_backend.get_queue_stats(queue_name)
        except Exception as e:
            self.logger.error("LinuxCakeBackend.get_queue_stats() failed: %s", e)
            return None

        if stats is None:
            return None

        # Cache per-tin data for health endpoint consumption (D-05, D-06)
        self.last_tin_stats = stats.get("tins", [])

        # Convert dict to CakeStats (preserving existing contract -- Pitfall 2)
        current = CakeStats(
            packets=stats["packets"],
            bytes=stats["bytes"],
            dropped=stats["dropped"],
            queued_packets=stats["queued_packets"],
            queued_bytes=stats["queued_bytes"],
        )

        # Pass through delta calculation (same as RouterOS path -- Pitfall 3)
        return self._calculate_stats_delta(current, queue_name)

    def read_stats(self, queue_name: str) -> CakeStats | None:
        """
        Read CAKE statistics for a specific queue.

        Returns delta stats since last read (best practice - no counter resets):
        - Cumulative counters (packets, bytes, dropped): delta from previous
        - Instantaneous values (queued_packets, queued_bytes): current value

        Returns CakeStats or None on error.
        """
        # C2 fix: Validate queue_name to prevent command injection in RouterOS queries
        try:
            from ..config_base import BaseConfig

            queue_name = BaseConfig.validate_identifier(queue_name, "queue_name")
        except ConfigValidationError as e:
            self.logger.error(f"Invalid queue name: {e}")
            return None

        # Linux CAKE path: delegate to LinuxCakeBackend
        if self._is_linux_cake:
            return self._read_stats_linux_cake(queue_name)

        # RouterOS path: execute via FailoverRouterClient
        cmd = f'/queue/tree print stats detail where name="{queue_name}"'
        rc, out, err = self.client.run_cmd(cmd, capture=True, timeout=5)

        if rc != 0:
            self.logger.error(f"Failed to read CAKE stats for {queue_name}: {err}")
            return None

        # Parse response based on format
        try:
            if out.strip().startswith("[") or out.strip().startswith("{"):
                current = self._parse_json_response(out, queue_name)
            else:
                current = self._parse_text_response(out)

            if current is None:
                return None

            # Calculate delta from previous
            return self._calculate_stats_delta(current, queue_name)

        except Exception as e:
            self.logger.error(f"Failed to parse CAKE stats: {e}")
            self.logger.debug(f"Raw output: {out[:200]}")
            return None
