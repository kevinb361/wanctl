"""Centralized timeout configuration for wanctl operations.

Consolidates timeout constants used across autorate, steering, and calibration
to ensure consistent behavior and prevent timeout value drift.

All timeout values in seconds.
"""

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


def get_ssh_timeout(component: str) -> int:
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
            f"Unknown component: {component}. "
            f"Must be one of: {', '.join(timeouts.keys())}"
        )

    return timeouts[component]


def get_ping_timeout(component: str, total: bool = False) -> int:
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
        return DEFAULT_STEERING_PING_TOTAL_TIMEOUT if total else DEFAULT_STEERING_PING_TOTAL_TIMEOUT // 3

    if component == "calibrate":
        return DEFAULT_CALIBRATE_PING_TIMEOUT

    raise ValueError(
        f"Unknown component: {component}. "
        f"Must be one of: autorate, steering, calibrate"
    )
