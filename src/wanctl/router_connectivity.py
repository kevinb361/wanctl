"""Router connectivity state tracking for cycle-level failure detection.

This module provides RouterConnectivityState for tracking consecutive router
communication failures and classify_failure_type() for categorizing exceptions
into actionable failure types.

Used by the control loop to detect router unreachability mid-cycle and track
reconnection state for appropriate recovery handling.
"""

import logging
import socket
import subprocess  # nosec B404 - used for type checking TimeoutExpired
import time


def classify_failure_type(exception: Exception) -> str:
    """
    Classify an exception into a failure type category.

    Extends the pattern from retry_utils.is_retryable_error() to provide
    more granular failure classification for connectivity tracking.

    Categories:
    - "timeout": Connection or read timeout
    - "connection_refused": Remote actively refused connection
    - "network_unreachable": Network layer failure (routing, unreachable)
    - "dns_failure": DNS resolution failure
    - "auth_failure": Authentication/authorization failure
    - "unknown": Unrecognized exception type

    Args:
        exception: The exception to classify

    Returns:
        String identifying the failure type category
    """
    exc_str = str(exception).lower()

    # Timeout exceptions
    if isinstance(exception, (TimeoutError, socket.timeout)):
        return "timeout"
    if isinstance(exception, subprocess.TimeoutExpired):
        return "timeout"

    # Connection refused - specific exception type
    if isinstance(exception, ConnectionRefusedError):
        return "connection_refused"

    # DNS failure - socket.gaierror
    if isinstance(exception, socket.gaierror):
        return "dns_failure"

    # Handle requests library exceptions (if available)
    try:
        import requests.exceptions

        if isinstance(
            exception, (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout)
        ):
            return "timeout"
        if isinstance(exception, requests.exceptions.ConnectionError):
            if "refused" in exc_str:
                return "connection_refused"
            return "network_unreachable"
    except ImportError:
        pass

    # Handle paramiko exceptions (if available)
    try:
        from paramiko import AuthenticationException

        if isinstance(exception, AuthenticationException):
            return "auth_failure"
    except ImportError:
        pass

    # String-based classification for OSError and generic exceptions
    if "connection refused" in exc_str:
        return "connection_refused"
    if "network is unreachable" in exc_str:
        return "network_unreachable"
    if "no route to host" in exc_str:
        return "network_unreachable"
    if "name or service not known" in exc_str:
        return "dns_failure"
    if "authentication failed" in exc_str:
        return "auth_failure"

    return "unknown"


class RouterConnectivityState:
    """
    Tracks router connectivity state for cycle-level failure detection.

    Maintains consecutive failure count and failure type classification
    to enable appropriate recovery handling (e.g., exponential backoff,
    alerting, fallback behavior).

    Attributes:
        consecutive_failures: Number of consecutive communication failures
        last_failure_type: Classification of most recent failure
        last_failure_time: Monotonic timestamp of most recent failure
        is_reachable: Whether router is currently considered reachable

    Example:
        state = RouterConnectivityState(logger)

        try:
            result = router.send_command(cmd)
            state.record_success()
        except Exception as e:
            failure_type = state.record_failure(e)
            if state.consecutive_failures >= 3:
                logger.error(f"Router unreachable: {failure_type}")
    """

    def __init__(self, logger: logging.Logger) -> None:
        """
        Initialize connectivity state.

        Args:
            logger: Logger instance for connectivity events
        """
        self.logger = logger
        self.consecutive_failures: int = 0
        self.last_failure_type: str | None = None
        self.last_failure_time: float | None = None
        self.is_reachable: bool = True

    def record_success(self) -> None:
        """
        Record a successful router communication.

        If recovering from failures, logs the reconnection event.
        Resets all failure tracking state.
        """
        if self.consecutive_failures > 0:
            self.logger.info(
                f"Router reconnected after {self.consecutive_failures} consecutive failures"
            )

        self.consecutive_failures = 0
        self.last_failure_type = None
        self.last_failure_time = None
        self.is_reachable = True

    def record_failure(self, exception: Exception) -> str:
        """
        Record a router communication failure.

        Increments failure counter, classifies the failure type, and
        updates reachability state.

        Args:
            exception: The exception that caused the failure

        Returns:
            The classified failure type string
        """
        failure_type = classify_failure_type(exception)

        self.consecutive_failures += 1
        self.last_failure_type = failure_type
        self.last_failure_time = time.monotonic()
        self.is_reachable = False

        return failure_type

    def to_dict(self) -> dict[str, bool | int | str | float | None]:
        """
        Export state as dictionary for health endpoint integration.

        Returns:
            Dictionary with connectivity state fields
        """
        return {
            "is_reachable": self.is_reachable,
            "consecutive_failures": self.consecutive_failures,
            "last_failure_type": self.last_failure_type,
            "last_failure_time": self.last_failure_time,
        }
