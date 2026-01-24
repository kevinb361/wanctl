"""Retry utilities with exponential backoff for transient failures."""

import functools
import logging
import random  # nosec B311 - used for jitter timing, not security
import subprocess  # nosec B404 - used for type checking TimeoutExpired
import time
from collections.abc import Callable
from typing import Any


def is_retryable_error(exception: Exception) -> bool:
    """
    Determine if an exception represents a transient/retryable error.

    Retryable conditions:
    - subprocess.TimeoutExpired (network/SSH timeout)
    - ConnectionError subclasses (connection refused, reset)
    - OSError with connection-related messages
    - requests.exceptions.ConnectionError, Timeout, ChunkedEncodingError

    Non-retryable conditions:
    - Authentication failures (permission denied, 401/403)
    - Command syntax errors
    - Other logic errors

    Args:
        exception: The exception to check

    Returns:
        True if the error is likely transient and worth retrying
    """
    # Timeout is always retryable
    if isinstance(exception, subprocess.TimeoutExpired):
        return True

    # Connection errors are retryable
    if isinstance(exception, ConnectionError):
        return True

    # OSError with specific messages
    if isinstance(exception, OSError):
        err_str = str(exception).lower()
        retryable_messages = [
            "connection refused",
            "connection timed out",
            "connection reset",
            "broken pipe",
            "network is unreachable",
        ]
        return any(msg in err_str for msg in retryable_messages)

    # Handle requests library exceptions (if requests is available)
    try:
        import requests.exceptions

        # Retryable requests errors
        if isinstance(
            exception,
            (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError,
            ),
        ):
            return True
        # Non-retryable: HTTPError with 4xx client errors (except 408 Request Timeout)
        if isinstance(exception, requests.exceptions.HTTPError):
            if hasattr(exception, "response") and exception.response is not None:
                status = exception.response.status_code
                # 408 (Request Timeout) and 5xx are retryable
                if status == 408 or status >= 500:
                    return True
            return False
    except ImportError:
        pass

    # All other exceptions are not retryable
    return False


def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 10.0,
    jitter: bool = True,
    on_retry: Callable[[int, Exception, float], None] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator that retries a function on transient failures with exponential backoff.

    Implements exponential backoff with optional jitter to avoid thundering herd.
    Only retries on exceptions identified as transient by is_retryable_error().

    Args:
        max_attempts: Maximum number of attempts (including initial try)
        initial_delay: Initial delay in seconds before first retry
        backoff_factor: Multiplier for delay on each retry (2.0 = double each time)
        max_delay: Maximum delay between retries in seconds
        jitter: Add random jitter (0-50%) to delay to avoid thundering herd
        on_retry: Optional callback invoked before each retry sleep. Receives:
            - attempt: Current attempt number (1-indexed, before the retry)
            - exception: The exception that triggered the retry
            - delay: The delay in seconds before the next attempt

    Returns:
        Decorated function that retries on transient failures

    Example:
        @retry_with_backoff(max_attempts=3, initial_delay=1.0)
        def _run_cmd(self, cmd: str) -> Tuple[int, str, str]:
            # SSH command execution
            ...

        # With retry metrics callback:
        def track_retry(attempt: int, exc: Exception, delay: float) -> None:
            metrics.increment("retries", tags={"attempt": attempt, "error": type(exc).__name__})

        @retry_with_backoff(max_attempts=3, on_retry=track_retry)
        def _run_cmd(self, cmd: str) -> Tuple[int, str, str]:
            # SSH command execution with retry tracking
            ...

    Retry schedule (with backoff_factor=2.0, initial_delay=1.0):
    - Attempt 1: immediate
    - Attempt 2: after 1.0s (+ jitter)
    - Attempt 3: after 2.0s (+ jitter)
    - Give up after 3 attempts
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get logger from self if method, otherwise create basic logger
            if args and hasattr(args[0], "logger"):
                logger = args[0].logger
            else:
                logger = logging.getLogger(__name__)

            delay = initial_delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    result = func(*args, **kwargs)

                    # If this is a retry (attempt > 1), log success
                    if attempt > 1:
                        logger.info(f"✓ Command succeeded on attempt {attempt}/{max_attempts}")

                    return result

                except Exception as e:
                    last_exception = e

                    # Check if error is retryable
                    if not is_retryable_error(e):
                        logger.debug(f"Non-retryable error: {type(e).__name__}: {e}")
                        raise

                    # If this was the last attempt, raise
                    if attempt >= max_attempts:
                        logger.error(
                            f"Command failed after {max_attempts} attempts: {type(e).__name__}: {e}"
                        )
                        raise

                    # Calculate delay with jitter
                    actual_delay = delay
                    if jitter:
                        # Add 0-50% random jitter (nosec B311 - timing, not crypto)
                        jitter_amount = delay * random.uniform(0, 0.5)
                        actual_delay = delay + jitter_amount

                    # Cap at max_delay
                    actual_delay = min(actual_delay, max_delay)

                    logger.warning(
                        f"Transient error on attempt {attempt}/{max_attempts}: "
                        f"{type(e).__name__}: {e} - "
                        f"retrying in {actual_delay:.1f}s"
                    )

                    # Invoke retry callback if provided
                    if on_retry is not None:
                        on_retry(attempt, e, actual_delay)

                    time.sleep(actual_delay)

                    # Exponential backoff for next attempt
                    delay *= backoff_factor

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


def verify_with_retry(
    check_func: Callable[[], Any],
    expected_result: Any,
    max_retries: int = 3,
    initial_delay: float = 0.1,
    backoff_factor: float = 2.0,
    logger: logging.Logger | None = None,
    operation_name: str = "verification",
) -> bool:
    """
    Retry a check function until expected result is reached or retries exhausted.

    Used for verifying state changes (e.g., rule enable/disable) where the
    control operation succeeds but the state change takes time to propagate.

    Args:
        check_func: Function that returns the current state/value
        expected_result: The value we're waiting for
        max_retries: Maximum number of check attempts
        initial_delay: Initial delay in seconds before first retry
        backoff_factor: Multiplier for delay on each retry (2.0 = double each time)
        logger: Logger instance (optional)
        operation_name: Name of the operation for logging

    Returns:
        True if expected result achieved within retries, False if exhausted

    Examples:
        Basic usage - check function returns expected result immediately:

        >>> verify_with_retry(lambda: True, True, max_retries=3)
        True

        Check function returns unexpected result (exhausts retries):

        >>> verify_with_retry(lambda: False, True, max_retries=2, initial_delay=0.01)
        False

        Simulating state change - counter increments until match:

        >>> counter = {'value': 0}
        >>> def check_counter():
        ...     counter['value'] += 1
        ...     return counter['value'] >= 3
        >>> verify_with_retry(check_counter, True, max_retries=5, initial_delay=0.01)
        True
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    delay = initial_delay

    for attempt in range(max_retries):
        result = check_func()

        if result == expected_result:
            # Verification succeeded
            if attempt > 0:
                logger.info(f"{operation_name} verified after {attempt + 1} attempts")
            return True

        if attempt < max_retries - 1:
            logger.debug(
                f"{operation_name} check failed (attempt {attempt + 1}/{max_retries}), "
                f"expected={expected_result}, got={result}"
            )
            time.sleep(delay)
            delay *= backoff_factor

    logger.warning(
        f"{operation_name} failed - expected result not achieved after {max_retries} attempts"
    )
    return False


def measure_with_retry(
    measure_func: Callable[[], Any],
    max_retries: int = 3,
    retry_delay: float = 0.5,
    fallback_func: Callable[[], Any] | None = None,
    logger: logging.Logger | None = None,
    operation_name: str = "measurement",
) -> Any:
    """
    Retry a measurement function with fixed delay, falling back on exhaustion.

    Used for measurements that may transiently fail (e.g., ping, RTT measurement)
    where a fallback value can be used if all retries are exhausted.

    Args:
        measure_func: Function that performs the measurement and returns a value or None
        max_retries: Maximum number of measurement attempts
        retry_delay: Fixed delay in seconds between attempts
        fallback_func: Optional function to call if all retries fail (should return fallback value or None)
        logger: Logger instance (optional)
        operation_name: Name of the operation for logging

    Returns:
        Measurement value on success, fallback value on failure, or None if no fallback

    Examples:
        Basic usage - measurement succeeds immediately:

        >>> measure_with_retry(lambda: 42.5, max_retries=3)
        42.5

        Measurement fails, uses fallback:

        >>> measure_with_retry(lambda: None, max_retries=2, retry_delay=0.01,
        ...                    fallback_func=lambda: 99.9)
        99.9

        Measurement fails with no fallback returns None:

        >>> measure_with_retry(lambda: None, max_retries=2, retry_delay=0.01)

        Simulating transient failure - succeeds on second attempt:

        >>> attempts = {'count': 0}
        >>> def flaky_measure():
        ...     attempts['count'] += 1
        ...     return 25.0 if attempts['count'] >= 2 else None
        >>> measure_with_retry(flaky_measure, max_retries=3, retry_delay=0.01)
        25.0
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    for attempt in range(max_retries):
        result = measure_func()

        if result is not None:
            # Measurement succeeded
            if attempt > 0:
                logger.info(f"{operation_name} succeeded on attempt {attempt + 1}")
            return result

        # Measurement failed
        logger.warning(f"{operation_name} failed on attempt {attempt + 1}/{max_retries}")

        # Delay before next attempt (but not after last failed attempt)
        if attempt < max_retries - 1:
            time.sleep(retry_delay)

    # All retries exhausted - try fallback
    if fallback_func is not None:
        logger.warning(f"{operation_name} exhausted - attempting fallback")
        return fallback_func()

    logger.error(f"{operation_name} failed after {max_retries} attempts and no fallback available")
    return None
