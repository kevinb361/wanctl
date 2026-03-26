"""Shared daemon utility functions.

Common helpers used by both autorate and steering daemon main() functions.
Extracted to eliminate duplication while keeping daemon-specific logic in each daemon.
"""

import logging
import time


def check_cleanup_deadline(
    step_name: str,
    step_start: float,
    deadline: float,
    timeout_seconds: float,
    logger: logging.Logger,
    *,
    now: float | None = None,
) -> None:
    """Check if a cleanup step exceeded time thresholds.

    Logs WARNING if step took >5s, ERROR if monotonic clock exceeds deadline.

    The ``now`` parameter allows callers to pass the current monotonic time so
    that tests can control timing via their own ``time`` mock. When omitted,
    ``time.monotonic()`` is called directly.

    Args:
        step_name: Name of the cleanup step (for log messages)
        step_start: monotonic() timestamp when step started
        deadline: monotonic() timestamp of overall cleanup deadline
        timeout_seconds: Total timeout budget (for error message)
        logger: Logger to emit warnings/errors
        now: Current monotonic time (optional; defaults to time.monotonic())
    """
    current = now if now is not None else time.monotonic()
    elapsed = current - step_start
    if elapsed > 5.0:
        logger.warning(f"Slow cleanup step: {step_name} took {elapsed:.1f}s")
    if current > deadline:
        logger.error(f"Cleanup deadline exceeded ({timeout_seconds}s) after {step_name}")
