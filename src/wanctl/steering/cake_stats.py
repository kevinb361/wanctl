#!/usr/bin/env python3
"""
CAKE Statistics Reader for RouterOS
Reads CAKE queue statistics (drops, queue depth) via SSH
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional

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

        # Track previous stats for delta calculation (best practice)
        self.previous_stats = {}  # queue_name -> CakeStats

    def read_stats(self, queue_name: str) -> Optional[CakeStats]:
        """
        Read CAKE statistics for a specific queue

        Returns delta stats since last read (best practice - no counter resets)
        - Cumulative counters (packets, bytes, dropped): delta from previous
        - Instantaneous values (queued_packets, queued_bytes): current value

        Returns CakeStats or None on error
        """
        cmd = f'/queue/tree print stats detail where name="{queue_name}"'
        rc, out, err = self.client.run_cmd(cmd, capture=True)

        if rc != 0:
            self.logger.error(f"Failed to read CAKE stats for {queue_name}: {err}")
            return None

        # Parse current cumulative stats from RouterOS
        current = CakeStats()

        try:
            # Handle both SSH (text) and REST (JSON) output formats
            if out.strip().startswith('[') or out.strip().startswith('{'):
                # JSON format (REST API)
                import json
                data = json.loads(out)
                # REST API returns a list of matching queues
                if isinstance(data, list) and len(data) > 0:
                    q = data[0]
                elif isinstance(data, dict):
                    q = data
                else:
                    self.logger.warning(f"No queue data in response for {queue_name}")
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

    def reset_counters(self, queue_name: str) -> bool:
        """
        Reset CAKE statistics counters for a queue

        This allows measuring deltas over a specific time window
        """
        cmd = f'/queue/tree reset-counters [find name="{queue_name}"]'
        rc, _, err = self.client.run_cmd(cmd)

        if rc != 0:
            self.logger.error(f"Failed to reset CAKE counters for {queue_name}: {err}")
            return False

        self.logger.debug(f"Reset CAKE counters for {queue_name}")
        return True

    def reset_all_counters(self) -> bool:
        """Reset all WAN queue counters"""
        cmd = '/queue/tree reset-counters [find name~"WAN-"]'
        rc, _, err = self.client.run_cmd(cmd)

        if rc != 0:
            self.logger.error(f"Failed to reset all CAKE counters: {err}")
            return False

        self.logger.debug("Reset all WAN CAKE counters")
        return True
