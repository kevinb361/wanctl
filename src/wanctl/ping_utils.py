"""
Unified ping output parsing utilities.

Consolidates ping output parsing logic used across autorate_continuous.py,
steering/daemon.py, and calibrate.py.
"""

import re
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


def parse_ping_output(text: str, logger_instance: Optional[logging.Logger] = None) -> List[float]:
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
    rtts: List[float] = []

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
