"""Centralized timeout configuration for wanctl operations.

Consolidates timeout constants used across autorate, steering, and calibration
to ensure consistent behavior and prevent timeout value drift.

All timeout values in seconds.

Design Rationale
----------------

SSH Timeout Values (per component):

- Autorate (15s): Runs every ~2 seconds in continuous monitoring mode. Needs
  responsiveness to detect congestion quickly, but 15s allows for occasional
  RouterOS slowdowns under load. Too short risks false failures during router
  CPU spikes; too long delays congestion response.

- Steering (30s): Operates on a 2-second assessment cycle but makes routing
  changes infrequently. Longer timeout prioritizes reliability over speed since
  a missed steering decision is less critical than a false positive. The daemon
  can tolerate occasional slow responses without degrading user experience.

- Calibrate (10s): Performs quick baseline RTT measurements. Short timeout
  ensures fast feedback during manual calibration runs. If the router doesn't
  respond within 10s, the measurement is likely invalid anyway due to extreme
  congestion or connectivity issues.

Ping Timeout Values:

- Autorate (1s per ping): Single-ping timeout for frequent RTT sampling. Short
  timeout ensures the control loop stays responsive. Lost pings are handled via
  EWMA smoothing rather than long waits.

- Steering (10s total): Allows multiple ping attempts within the assessment
  window. Longer total timeout improves reliability of congestion detection
  without blocking the daemon's main loop.

- Calibrate (15s): Generous timeout for baseline establishment. Calibration
  runs infrequently and accuracy matters more than speed. Allows for path
  variations and ensures the baseline reflects actual network conditions.

Tradeoffs:

Shorter timeouts improve responsiveness and faster failure detection but risk
false negatives (missing valid but slow responses). Longer timeouts improve
reliability but can cause control loop stalls. The values here represent
production-tuned defaults based on observed RouterOS behavior and network
characteristics across DOCSIS and VDSL links.
"""

from typing import Literal

# Type alias for valid component names - typos caught at type-check time
ComponentName = Literal["autorate", "steering", "calibrate"]

# =============================================================================
# SSH/REST Command Execution Timeouts
# =============================================================================

# Autorate controller SSH timeout (15 seconds for typical RouterOS latency)
DEFAULT_AUTORATE_SSH_TIMEOUT = 15

# Steering daemon SSH timeout (30 seconds, allows more retries)
DEFAULT_STEERING_SSH_TIMEOUT = 30

# Calibration SSH timeout (10 seconds for quick baseline measurement)
DEFAULT_CALIBRATE_SSH_TIMEOUT = 10

# =============================================================================
# Ping Timeouts
# =============================================================================

# Autorate single ping timeout (1 second per ping)
DEFAULT_AUTORATE_PING_TIMEOUT = 1

# Steering total ping timeout (10 seconds for all attempts)
DEFAULT_STEERING_PING_TOTAL_TIMEOUT = 10

# Calibration single ping timeout (15 seconds)
DEFAULT_CALIBRATE_PING_TIMEOUT = 15

# =============================================================================
# Subprocess Command Timeouts (General Purpose)
# =============================================================================

# Quick command execution (find, list operations)
TIMEOUT_QUICK = 5

# Standard command execution (most operations)
TIMEOUT_STANDARD = 10

# Long-running command execution (netperf, iperf3)
TIMEOUT_LONG = 30

# Throughput measurement timeout (aggressive measurement)
TIMEOUT_THROUGHPUT_MEASUREMENT = 30

# =============================================================================
# File Lock Timeouts
# =============================================================================

# Lock acquisition timeout (prevent indefinite waits)
DEFAULT_LOCK_TIMEOUT = 300  # 5 minutes


def get_ssh_timeout(component: ComponentName) -> int:
    """Get SSH timeout for a component.

    Args:
        component: Component name ("autorate", "steering", "calibrate")

    Returns:
        Timeout in seconds

    Raises:
        ValueError: If component is unknown
    """
    timeouts = {
        "autorate": DEFAULT_AUTORATE_SSH_TIMEOUT,
        "steering": DEFAULT_STEERING_SSH_TIMEOUT,
        "calibrate": DEFAULT_CALIBRATE_SSH_TIMEOUT,
    }

    if component not in timeouts:
        raise ValueError(
            f"Unknown component: {component}. Must be one of: {', '.join(timeouts.keys())}"
        )

    return timeouts[component]


def get_ping_timeout(component: ComponentName, total: bool = False) -> int:
    """Get ping timeout for a component.

    Args:
        component: Component name ("autorate", "steering", "calibrate")
        total: If True, return total timeout for all ping attempts; if False, return per-ping timeout

    Returns:
        Timeout in seconds

    Raises:
        ValueError: If component is unknown
    """
    if component == "autorate":
        return DEFAULT_AUTORATE_PING_TIMEOUT

    if component == "steering":
        return (
            DEFAULT_STEERING_PING_TOTAL_TIMEOUT
            if total
            else DEFAULT_STEERING_PING_TOTAL_TIMEOUT // 3
        )

    if component == "calibrate":
        return DEFAULT_CALIBRATE_PING_TIMEOUT

    raise ValueError(
        f"Unknown component: {component}. Must be one of: autorate, steering, calibrate"
    )
