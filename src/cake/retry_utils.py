"""Retry utilities with exponential backoff for transient failures."""

import functools
import logging
import random
import subprocess
import time
from typing import Callable, Tuple, Type


def is_retryable_error(exception: Exception) -> bool:
    """
    Determine if an exception represents a transient/retryable error.

    Retryable conditions:
    - subprocess.TimeoutExpired (network/SSH timeout)
    - ConnectionError subclasses (connection refused, reset)
    - OSError with connection-related messages

    Non-retryable conditions:
    - Authentication failures (permission denied)
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
            'connection refused',
            'connection timed out',
            'connection reset',
            'broken pipe',
            'network is unreachable'
        ]
        return any(msg in err_str for msg in retryable_messages)

    # All other exceptions are not retryable
    return False


def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 10.0,
    jitter: bool = True
):
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

    Returns:
        Decorated function that retries on transient failures

    Example:
        @retry_with_backoff(max_attempts=3, initial_delay=1.0)
        def _run_cmd(self, cmd: str) -> Tuple[int, str, str]:
            # SSH command execution
            ...

    Retry schedule (with backoff_factor=2.0, initial_delay=1.0):
    - Attempt 1: immediate
    - Attempt 2: after 1.0s (+ jitter)
    - Attempt 3: after 2.0s (+ jitter)
    - Give up after 3 attempts
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get logger from self if method, otherwise create basic logger
            if args and hasattr(args[0], 'logger'):
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
                            f"Command failed after {max_attempts} attempts: "
                            f"{type(e).__name__}: {e}"
                        )
                        raise

                    # Calculate delay with jitter
                    actual_delay = delay
                    if jitter:
                        # Add 0-50% random jitter
                        jitter_amount = delay * random.uniform(0, 0.5)
                        actual_delay = delay + jitter_amount

                    # Cap at max_delay
                    actual_delay = min(actual_delay, max_delay)

                    logger.warning(
                        f"Transient error on attempt {attempt}/{max_attempts}: "
                        f"{type(e).__name__}: {e} - "
                        f"retrying in {actual_delay:.1f}s"
                    )

                    time.sleep(actual_delay)

                    # Exponential backoff for next attempt
                    delay *= backoff_factor

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper
    return decorator
