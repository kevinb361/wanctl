"""Unified signal handling utilities for graceful shutdown.

Consolidates signal handling logic used across daemons (autorate_continuous.py,
steering/daemon.py) and utilities (calibrate.py). Provides reusable functions for
registering signal handlers and checking shutdown state.

Usage for daemons (graceful shutdown with threading.Event):

    from wanctl.signal_utils import register_signal_handlers, is_shutdown_requested

    def main():
        register_signal_handlers()  # Early in main()
        # ... initialization ...
        while not is_shutdown_requested():
            # Main loop
            pass

Usage for utilities (immediate exit on signal):

    from wanctl.signal_utils import register_signal_handlers, is_shutdown_requested

    def main():
        register_signal_handlers(include_sigterm=False)  # SIGINT only for utilities
        # ... work ...
        if is_shutdown_requested():
            return 130  # Standard SIGINT exit code

Thread-safe: Uses threading.Event() for shutdown coordination.
Deadlock-safe: Signal handler does not log (logging in signal handlers is unsafe).
"""

import signal
import threading
import types

# Module-level shutdown event (thread-safe)
_shutdown_event = threading.Event()


def _signal_handler(signum: int, frame: types.FrameType | None) -> None:
    """Signal handler for SIGTERM and SIGINT.

    Sets the shutdown event to allow the main loop to exit gracefully.
    Thread-safe: uses threading.Event() instead of boolean flag.

    Args:
        signum: Signal number received
        frame: Current stack frame (unused)
    """
    # Note: logging in signal handlers can be unsafe, so we just set the event.
    # The main loop will log the shutdown with the appropriate context.
    # Signal number can be retrieved later if needed via inspection of the event.
    _shutdown_event.set()


def register_signal_handlers(include_sigterm: bool = True) -> None:
    """Register signal handlers for graceful shutdown.

    Registers handlers for:
      - SIGTERM: Sent by systemd on service stop (daemons only)
      - SIGINT: Sent on Ctrl+C (keyboard interrupt)

    Should be called early in main() before any long-running operations.

    Args:
        include_sigterm: If True (default), registers SIGTERM handler for daemon use.
                        Set to False for interactive utilities that only need SIGINT.
    """
    if include_sigterm:
        signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)


def is_shutdown_requested() -> bool:
    """Check if shutdown has been requested via signal.

    Returns:
        True if SIGTERM or SIGINT has been received, False otherwise.
    """
    return _shutdown_event.is_set()


def get_shutdown_event() -> threading.Event:
    """Get the shutdown event for direct access.

    Use this when you need to wait on the event directly (e.g., for timed waits
    in daemon loops).

    Returns:
        The module-level threading.Event used for shutdown coordination.

    Example:
        # In a daemon main loop
        shutdown_event = get_shutdown_event()
        while not shutdown_event.is_set():
            # ... work ...
            if sleep_time > 0:
                shutdown_event.wait(timeout=sleep_time)
    """
    return _shutdown_event


def wait_for_shutdown(timeout: float | None = None) -> bool:
    """Wait for shutdown signal with optional timeout.

    Blocks until shutdown is requested or timeout expires.

    Args:
        timeout: Maximum seconds to wait. None means wait indefinitely.

    Returns:
        True if shutdown was requested, False if timeout expired.
    """
    return _shutdown_event.wait(timeout=timeout)


def reset_shutdown_state() -> None:
    """Reset the shutdown state (for testing purposes only).

    Clears the shutdown event. This should NOT be used in production code -
    it exists only for test isolation.
    """
    _shutdown_event.clear()
