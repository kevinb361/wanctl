#!/usr/bin/env python3
"""
CAKE Passive Queue Monitor
Monitors CAKE queue statistics without active testing
Run this frequently (e.g., every 30 seconds) between active tests
"""
import argparse
import datetime
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, Tuple

import yaml

from cake.config_base import BaseConfig
from cake.logging_utils import setup_logging


class Config(BaseConfig):
    """Lightweight config loader"""

    def _load_specific_fields(self):
        """Load passive_monitor-specific configuration fields"""
        # Queues
        self.queue_down = self.data['queues']['download']
        self.queue_up = self.data['queues']['upload']

        # Passive monitoring thresholds
        pm = self.data.get('passive_monitoring', {})
        self.queue_delay_threshold = pm.get('queue_delay_threshold_ms', 10)
        self.drop_rate_threshold = pm.get('drop_rate_threshold_percent', 1.0)
        self.alert_on_issues = pm.get('alert_on_issues', True)

        # Logging (derived from main_log directory)
        log_dir = os.path.dirname(self.data['logging']['main_log'])
        self.passive_log = os.path.join(log_dir, 'cake_passive.log')
        # Set main_log for logging_utils compatibility
        self.main_log = self.passive_log

        # Timeouts (with sensible defaults)
        timeouts = self.data.get('timeouts', {})
        self.timeout_ssh_command = timeouts.get('ssh_command', 10)  # seconds


class QueueStats:
    """CAKE queue statistics"""
    def __init__(self):
        self.sent_bytes = 0
        self.sent_packets = 0
        self.dropped_packets = 0
        self.overlimits = 0
        self.backlog_bytes = 0
        self.backlog_packets = 0
        self.target_delay_ms = 0
        self.interval_delay_ms = 0
        self.way_indirect_hits = 0
        self.way_misses = 0
        self.ecn_marked = 0

        # Derived metrics
        self.drop_rate_percent = 0.0
        self.queue_delay_estimate_ms = 0.0


def get_queue_stats(
    router_host: str,
    router_user: str,
    ssh_key: str,
    interface: str,
    logger: logging.Logger
) -> Optional[QueueStats]:
    """
    Get CAKE queue statistics from router
    Uses: tc -s qdisc show dev <interface>
    """
    # Get the interface name from queue tree first
    cmd_get_parent = [
        "ssh", "-i", ssh_key, "-o", "StrictHostKeyChecking=no",
        f"{router_user}@{router_host}",
        f'/queue tree print detail where name="{interface}"'
    ]

    try:
        result = subprocess.run(
            cmd_get_parent,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=config.timeout_ssh_command
        )

        if result.returncode != 0:
            logger.error(f"Failed to get queue info: {result.stderr}")
            return None

        # Parse parent interface from output
        # Example: parent=ether2-WAN-ATT
        parent_match = re.search(r'parent=([^\s]+)', result.stdout)
        if not parent_match:
            logger.error("Could not find parent interface in queue tree")
            return None

        parent_iface = parent_match.group(1)
        logger.debug(f"Queue {interface} parent interface: {parent_iface}")

        # Now get tc stats for that interface
        cmd_tc = [
            "ssh", "-i", ssh_key, "-o", "StrictHostKeyChecking=no",
            f"{router_user}@{router_host}",
            f"tc -s qdisc show dev {parent_iface}"
        ]

        result = subprocess.run(
            cmd_tc,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=config.timeout_ssh_command
        )

        if result.returncode != 0:
            logger.warning(f"tc command failed (normal for non-Linux): {result.stderr}")
            # RouterOS doesn't support tc directly, need alternative approach
            return None

        # Parse tc output
        stats = QueueStats()
        output = result.stdout

        # Parse sent bytes/packets
        sent_match = re.search(r'Sent\s+(\d+)\s+bytes\s+(\d+)\s+pkt', output)
        if sent_match:
            stats.sent_bytes = int(sent_match.group(1))
            stats.sent_packets = int(sent_match.group(2))

        # Parse drops
        drops_match = re.search(r'dropped\s+(\d+)', output)
        if drops_match:
            stats.dropped_packets = int(drops_match.group(1))

        # Parse overlimits
        overlimits_match = re.search(r'overlimits\s+(\d+)', output)
        if overlimits_match:
            stats.overlimits = int(overlimits_match.group(1))

        # Parse backlog
        backlog_match = re.search(r'backlog\s+(\d+)b\s+(\d+)p', output)
        if backlog_match:
            stats.backlog_bytes = int(backlog_match.group(1))
            stats.backlog_packets = int(backlog_match.group(2))

        # Parse CAKE-specific stats
        target_match = re.search(r'target\s+([\d.]+)ms', output)
        if target_match:
            stats.target_delay_ms = float(target_match.group(1))

        interval_match = re.search(r'interval\s+([\d.]+)ms', output)
        if interval_match:
            stats.interval_delay_ms = float(interval_match.group(1))

        # Calculate derived metrics
        if stats.sent_packets > 0:
            stats.drop_rate_percent = (stats.dropped_packets / stats.sent_packets) * 100

        # Estimate queue delay from backlog (rough approximation)
        # This is very approximate - real queue delay needs sojourn time
        if stats.backlog_packets > 0:
            stats.queue_delay_estimate_ms = stats.backlog_packets * 0.5  # Rough estimate

        logger.debug(f"Queue stats: sent={stats.sent_packets} pkt, "
                    f"dropped={stats.dropped_packets}, "
                    f"backlog={stats.backlog_packets} pkt")

        return stats

    except subprocess.TimeoutExpired:
        logger.error("Timeout getting queue stats")
        return None
    except Exception as e:
        logger.error(f"Error getting queue stats: {e}")
        return None


def check_queue_health(
    stats: QueueStats,
    config: Config,
    logger: logging.Logger
) -> Tuple[bool, str]:
    """
    Check if queue health is acceptable
    Returns: (is_healthy, reason)
    """
    issues = []

    # Check drop rate
    if stats.drop_rate_percent > config.drop_rate_threshold:
        issues.append(f"High drop rate: {stats.drop_rate_percent:.2f}%")

    # Check queue delay estimate
    if stats.queue_delay_estimate_ms > config.queue_delay_threshold:
        issues.append(f"High queue delay: {stats.queue_delay_estimate_ms:.1f}ms")

    # Check for excessive overlimits
    if stats.overlimits > stats.sent_packets * 0.1:  # More than 10% overlimit
        issues.append(f"Excessive overlimits: {stats.overlimits}")

    if issues:
        return False, "; ".join(issues)

    return True, "Queue healthy"


def main():
    parser = argparse.ArgumentParser(
        description="CAKE Passive Queue Monitor"
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to config YAML file"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print to stdout in addition to log file"
    )
    args = parser.parse_args()

    # Load config
    try:
        config = Config(args.config)
    except Exception as e:
        print(f"ERROR: Failed to load config: {e}")
        return 1

    # Setup logging
    logger = setup_logging(config, "cake_passive")

    if args.verbose:
        # Add console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter(
            f"%(asctime)s [{config.wan_name}] %(message)s"
        ))
        logger.addHandler(ch)

    logger.info("=" * 60)
    logger.info(f"Passive Queue Monitor - {config.wan_name}")

    # Get queue stats for both directions
    down_stats = get_queue_stats(
        config.router_host,
        config.router_user,
        config.ssh_key,
        config.queue_down,
        logger
    )

    up_stats = get_queue_stats(
        config.router_host,
        config.router_user,
        config.ssh_key,
        config.queue_up,
        logger
    )

    if down_stats is None and up_stats is None:
        logger.warning("Could not retrieve queue statistics (RouterOS may not support tc)")
        logger.info("Passive monitoring works best on Linux-based routers with tc support")
        return 0

    # Check download queue
    if down_stats:
        healthy, reason = check_queue_health(down_stats, config, logger)
        if healthy:
            logger.info(f"Download queue: {reason}")
        else:
            logger.warning(f"Download queue: {reason}")
            if config.alert_on_issues:
                logger.warning("Consider triggering early active test")

        logger.info(f"  Sent: {down_stats.sent_packets} pkt, "
                   f"Dropped: {down_stats.dropped_packets} "
                   f"({down_stats.drop_rate_percent:.2f}%)")
        if down_stats.backlog_packets > 0:
            logger.info(f"  Backlog: {down_stats.backlog_packets} pkt "
                       f"({down_stats.backlog_bytes} bytes)")

    # Check upload queue
    if up_stats:
        healthy, reason = check_queue_health(up_stats, config, logger)
        if healthy:
            logger.info(f"Upload queue: {reason}")
        else:
            logger.warning(f"Upload queue: {reason}")
            if config.alert_on_issues:
                logger.warning("Consider triggering early active test")

        logger.info(f"  Sent: {up_stats.sent_packets} pkt, "
                   f"Dropped: {up_stats.dropped_packets} "
                   f"({up_stats.drop_rate_percent:.2f}%)")
        if up_stats.backlog_packets > 0:
            logger.info(f"  Backlog: {up_stats.backlog_packets} pkt "
                       f"({up_stats.backlog_bytes} bytes)")

    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
