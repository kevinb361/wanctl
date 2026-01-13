"""Unified systemd integration utilities for daemon health reporting.

Consolidates systemd watchdog and status notification logic used across daemons
(autorate_continuous.py, steering/daemon.py). Provides reusable functions for
systemd notification with graceful fallback when systemd is not available.

Usage for daemons (watchdog notifications):

    from wanctl.systemd_utils import (
        is_systemd_available,
        notify_watchdog,
        notify_status,
        notify_degraded,
    )

    def main():
        if is_systemd_available():
            logger.info("Systemd watchdog support enabled")

        while running:
            success = run_cycle()

            # Notify watchdog ONLY if healthy
            if success:
                notify_watchdog()
            else:
                notify_degraded(f"{failure_count} consecutive failures")

All notify functions are no-ops if systemd is not available (graceful fallback).
This eliminates the need for `if sd_notify:` checks throughout daemon code.
"""

# Optional systemd integration - graceful fallback if not available
try:
    from systemd.daemon import notify as _sd_notify

    _HAVE_SYSTEMD = True
except ImportError:
    _HAVE_SYSTEMD = False
    _sd_notify = None


def is_systemd_available() -> bool:
    """Check if systemd integration is available.

    Returns:
        True if systemd.daemon module is available, False otherwise.

    Example:
        if is_systemd_available():
            logger.info("Systemd watchdog support enabled")
    """
    return _HAVE_SYSTEMD


def notify_ready() -> None:
    """Send READY=1 notification to systemd.

    Used for Type=notify services to indicate the daemon has finished
    initialization and is ready to serve requests.

    No-op if systemd is not available.
    """
    if _sd_notify is not None:
        _sd_notify("READY=1")


def notify_watchdog() -> None:
    """Send WATCHDOG=1 notification to systemd.

    Should be called on each successful cycle to indicate the daemon is
    healthy. Systemd will restart the daemon if watchdog notifications
    stop arriving within the configured interval.

    No-op if systemd is not available.

    Example:
        if cycle_success:
            notify_watchdog()
    """
    if _sd_notify is not None:
        _sd_notify("WATCHDOG=1")


def notify_status(status: str) -> None:
    """Send STATUS notification to systemd.

    Updates the daemon's status string visible in `systemctl status`.

    Args:
        status: Status message to display.

    No-op if systemd is not available.

    Example:
        notify_status("Processing 100 requests/sec")
    """
    if _sd_notify is not None:
        _sd_notify(f"STATUS={status}")


def notify_stopping() -> None:
    """Send STOPPING=1 notification to systemd.

    Indicates the daemon is beginning its shutdown sequence.

    No-op if systemd is not available.
    """
    if _sd_notify is not None:
        _sd_notify("STOPPING=1")


def notify_degraded(message: str) -> None:
    """Send degraded status notification to systemd.

    Convenience function for reporting degraded state. Prefixes the
    message with "Degraded - " for consistent status formatting.

    Args:
        message: Description of the degraded condition.

    No-op if systemd is not available.

    Example:
        notify_degraded("3 consecutive failures")
        # Results in STATUS=Degraded - 3 consecutive failures
    """
    if _sd_notify is not None:
        _sd_notify(f"STATUS=Degraded - {message}")
