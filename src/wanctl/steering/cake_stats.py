#!/usr/bin/env python3
"""
CAKE Statistics Reader for RouterOS
Reads CAKE queue statistics (drops, queue depth) via SSH
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional

from ..config_base import ConfigValidationError
from ..router_client import get_router_client


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
    rtt_delta: float = 0.0           # Current RTT - baseline (ms)
    rtt_delta_ewma: float = 0.0      # Smoothed RTT delta (ms)
    cake_drops: int = 0              # Drops in measurement window
    queued_packets: int = 0          # Current queue depth
    baseline_rtt: float = 0.0        # Baseline RTT for reference

    def __str__(self) -> str:
        return (f"rtt={self.rtt_delta:.1f}ms ewma={self.rtt_delta_ewma:.1f}ms "
                f"drops={self.cake_drops} q={self.queued_packets}")


class CakeStatsReader:
    """Read CAKE statistics from RouterOS queue (supports SSH and REST)"""

    def __init__(self, config, logger: logging.Logger):
        self.config = config
        self.logger = logger

        # Create router client using factory (supports SSH and REST)
        self.client = get_router_client(config, logger)

        # Track previous stats for delta calculation (best practice - no RouterOS resets needed)
        # Delta math approach:
        #   - RouterOS counters (packets, bytes, dropped) are cumulative and monotonically increasing
        #   - We calculate deltas by subtracting previous read from current read
        #   - This avoids the race condition of reset → read (events can be missed in the gap)
        #   - No RouterOS command overhead (saves ~50-150ms per cycle)
        #   - Correctly handles counter overflow at 2^64 (Python handles subtraction correctly)
        # Why not counter resets?:
        #   - Reset → read window creates measurement gap (some drops could be missed)
        #   - Extra RouterOS command adds latency during 2-second steering cycles
        #   - Less accurate (captures cumulative state instead of exact interval)
        self.previous_stats = {}  # queue_name -> CakeStats

    def read_stats(self, queue_name: str) -> Optional[CakeStats]:
        """
        Read CAKE statistics for a specific queue

        Returns delta stats since last read (best practice - no counter resets)
        - Cumulative counters (packets, bytes, dropped): delta from previous
        - Instantaneous values (queued_packets, queued_bytes): current value

        Returns CakeStats or None on error
        """
        # C2 fix: Validate queue_name to prevent command injection in RouterOS queries
        try:
            from ..config_base import BaseConfig
            queue_name = BaseConfig.validate_identifier(queue_name, 'queue_name')
        except ConfigValidationError as e:
            self.logger.error(f"Invalid queue name: {e}")
            return None

        cmd = f'/queue/tree print stats detail where name="{queue_name}"'
        rc, out, err = self.client.run_cmd(cmd, capture=True, timeout=5)  # Fast query, high frequency

        if rc != 0:
            self.logger.error(f"Failed to read CAKE stats for {queue_name}: {err}")
            return None

        # Parse current cumulative stats from RouterOS
        current = CakeStats()

        try:
            # Handle both SSH (text) and REST (JSON) output formats
            if out.strip().startswith('[') or out.strip().startswith('{'):
                # JSON format (REST API) - W10 fix: add JSON parsing error handling
                import json
                try:
                    data = json.loads(out)
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse CAKE stats JSON for {queue_name}: {e}")
                    self.logger.debug(f"Invalid JSON response: {out[:200]}")
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
                current.packets = int(q.get('packets', 0))
                current.bytes = int(q.get('bytes', 0))
                current.dropped = int(q.get('dropped', 0))
                current.queued_packets = int(q.get('queued-packets', 0))
                current.queued_bytes = int(q.get('queued-bytes', 0))
            else:
                # Text format (SSH CLI output)
                # Example output:
                # name="WAN-Download-1" parent=bridge1 ...
                # rate=0 packet-rate=0 queued-bytes=0 queued-packets=0
                # bytes=272603902153 packets=184614358 dropped=0

                # Extract cumulative counters (monotonically increasing)
                match = re.search(r'packets=(\d+)', out)
                if match:
                    current.packets = int(match.group(1))

                match = re.search(r'bytes=(\d+)', out)
                if match:
                    current.bytes = int(match.group(1))

                match = re.search(r'dropped=(\d+)', out)
                if match:
                    current.dropped = int(match.group(1))

                # Extract instantaneous values (current queue depth)
                match = re.search(r'queued-packets=(\d+)', out)
                if match:
                    current.queued_packets = int(match.group(1))

                match = re.search(r'queued-bytes=(\d+)', out)
                if match:
                    current.queued_bytes = int(match.group(1))

            # Calculate delta from previous read (best practice)
            previous = self.previous_stats.get(queue_name)

            if previous is None:
                # First read - return current as delta, store for next time
                self.logger.debug(f"CAKE stats [{queue_name}] first read, storing baseline")
                self.previous_stats[queue_name] = current
                # Return current values for first sample
                return current

            # Calculate deltas for cumulative counters
            delta = CakeStats(
                packets=current.packets - previous.packets,
                bytes=current.bytes - previous.bytes,
                dropped=current.dropped - previous.dropped,
                queued_packets=current.queued_packets,  # instantaneous
                queued_bytes=current.queued_bytes       # instantaneous
            )

            # Store current for next delta calculation
            self.previous_stats[queue_name] = current

            self.logger.debug(f"CAKE stats [{queue_name}] delta: {delta}")
            return delta

        except Exception as e:
            self.logger.error(f"Failed to parse CAKE stats: {e}")
            self.logger.debug(f"Raw output: {out[:200]}")
            return None

