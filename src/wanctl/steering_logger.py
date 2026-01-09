"""Steering daemon logging utilities.

Consolidates common logging patterns used in steering/daemon.py including
measurement logging, state transitions, failure tracking, and rule state changes.
Provides structured logging with context for observability and debugging.
"""

import logging
from typing import Optional

from .steering.cake_stats import CongestionSignals


class SteeringLogger:
    """Structured logging for steering daemon operations.

    Consolidates common logging patterns with consistent formatting and context.
    Reduces logging boilerplate and ensures consistent observable signal format.
    """

    def __init__(self, logger: logging.Logger, wan_name: str):
        """Initialize steering logger.

        Args:
            logger: Logger instance
            wan_name: Primary WAN name (e.g., "spectrum", "att") for log context
        """
        self.logger = logger
        self.wan_name = wan_name.upper()

    def log_measurement(
        self,
        current_state: str,
        current_rtt: float,
        baseline_rtt: Optional[float],
        delta: float,
        signals: Optional[CongestionSignals] = None,
        bad_count: int = 0,
        good_count: int = 0,
        bad_samples_threshold: int = 1,
        good_samples_threshold: int = 1,
        cake_aware: bool = False
    ) -> None:
        """Log measurement cycle with RTT, delta, and state context.

        Provides structured INFO-level logging of each measurement cycle with
        all relevant context for real-time monitoring and troubleshooting.

        Args:
            current_state: Current state (SPECTRUM_GOOD, SPECTRUM_DEGRADED, etc)
            current_rtt: Current measured RTT (ms)
            baseline_rtt: Baseline RTT (ms), or None
            delta: RTT delta from baseline (ms)
            signals: CongestionSignals object (optional, for CAKE-aware mode)
            bad_count: Current bad sample counter
            good_count: Current good sample counter
            bad_samples_threshold: Threshold for bad samples
            good_samples_threshold: Threshold for good samples
            cake_aware: If True, use CAKE-aware format with signals
        """
        state_suffix = current_state.split('_')[-1] if '_' in current_state else current_state
        header = f"[{self.wan_name}_{state_suffix}]"

        if cake_aware and signals is not None:
            # CAKE-aware format: show all signals
            self.logger.info(
                f"{header} {signals} | "
                f"congestion={getattr(signals, '_congestion_state', 'N/A')}"
            )
        else:
            # RTT-only format: detailed RTT and counter info
            baseline_str = f"{baseline_rtt:.1f}ms" if baseline_rtt is not None else "N/A"
            self.logger.info(
                f"{header} RTT={current_rtt:.1f}ms, baseline={baseline_str}, delta={delta:.1f}ms | "
                f"bad_count={bad_count}/{bad_samples_threshold}, "
                f"good_count={good_count}/{good_samples_threshold}"
            )

    def log_state_transition(
        self,
        old_state: str,
        new_state: str,
        bad_count: int = 0,
        good_count: int = 0,
        reason: Optional[str] = None
    ) -> None:
        """Log state machine transition with context.

        Args:
            old_state: Previous state
            new_state: New state
            bad_count: Bad sample counter (for context)
            good_count: Good sample counter (for context)
            reason: Optional reason for transition (e.g., "RTT delta exceeded", "drop verified")
        """
        reason_str = f" ({reason})" if reason else ""
        self.logger.info(
            f"State transition: {old_state} → {new_state}{reason_str} | "
            f"bad={bad_count}, good={good_count}"
        )

    def log_failure_with_counter(
        self,
        failure_type: str,
        failure_count: int,
        max_failures: int,
        context: Optional[str] = None
    ) -> None:
        """Log repeated failures with degradation tracking.

        Used for tracking failures that trigger degraded mode (CAKE reads, ping retries, etc).
        Logs warning on first failure, error when threshold exceeded.

        Args:
            failure_type: Type of failure (e.g., "CAKE stats read", "ping")
            failure_count: Current failure counter
            max_failures: Threshold at which degraded mode triggers
            context: Optional context info (queue name, host, etc)
        """
        context_str = f" ({context})" if context else ""

        if failure_count == 1:
            # First failure - warning level
            self.logger.warning(
                f"{failure_type} failed{context_str}, using degraded mode "
                f"(failure {failure_count}/{max_failures})"
            )
        elif failure_count == max_failures:
            # Threshold reached - error level, entering degraded mode
            self.logger.error(
                f"{failure_type} unavailable after {max_failures} attempts{context_str}, "
                f"entering sustained degraded mode"
            )
        elif failure_count > max_failures:
            # Sustained degraded mode - debug level to reduce log noise
            self.logger.debug(
                f"{failure_type} still unavailable{context_str} "
                f"(failure {failure_count})"
            )

    def log_rule_state(
        self,
        rule_comment: str,
        state: str,
        verified: bool = False,
        attempts: int = 1
    ) -> None:
        """Log rule enable/disable with verification status.

        Args:
            rule_comment: Mangle rule comment/name
            state: "enabled" or "disabled"
            verified: If True, verification succeeded
            attempts: Number of attempts needed
        """
        if verified:
            if attempts == 1:
                self.logger.info(f"Steering rule {state}: {rule_comment}")
            else:
                self.logger.info(
                    f"Steering rule {state} and verified: {rule_comment} "
                    f"(took {attempts} attempts)"
                )
        else:
            self.logger.error(
                f"Steering rule {state} FAILED verification: {rule_comment} "
                f"(attempt {attempts})"
            )

    def log_retry_attempt(
        self,
        operation: str,
        attempt: int,
        max_attempts: int,
        success: bool = False,
        context: Optional[str] = None
    ) -> None:
        """Log retry attempt with progress tracking.

        Args:
            operation: Operation being retried (e.g., "ping", "rule verification")
            attempt: Current attempt number (1-based)
            max_attempts: Total attempts allowed
            success: If True, operation succeeded
            context: Optional context info
        """
        context_str = f" ({context})" if context else ""

        if success:
            self.logger.info(
                f"{operation} succeeded on attempt {attempt}{context_str}"
            )
        else:
            self.logger.warning(
                f"{operation} failed on attempt {attempt}/{max_attempts}{context_str}"
            )

    def log_baseline_update(
        self,
        old_baseline: Optional[float],
        new_baseline: float,
        change_threshold: float = 5.0
    ) -> None:
        """Log baseline RTT changes with significant change detection.

        Args:
            old_baseline: Previous baseline (None if first time)
            new_baseline: New baseline
            change_threshold: Log at INFO if change > this (ms)
        """
        if old_baseline is None:
            self.logger.info(
                f"Baseline RTT initialized: {new_baseline:.2f}ms"
            )
        else:
            change = abs(new_baseline - old_baseline)
            if change > change_threshold:
                self.logger.info(
                    f"Baseline RTT changed: {old_baseline:.2f}ms → {new_baseline:.2f}ms "
                    f"(Δ {change:+.2f}ms)"
                )
            else:
                self.logger.debug(
                    f"Baseline RTT updated: {old_baseline:.2f}ms → {new_baseline:.2f}ms "
                    f"(Δ {change:+.2f}ms)"
                )

    def log_degraded_mode_entry(self, reason: str, fallback: str) -> None:
        """Log entry into degraded mode operation.

        Args:
            reason: Why degraded mode entered (e.g., "CAKE stats unavailable")
            fallback: What we're falling back to (e.g., "RTT-only decisions")
        """
        self.logger.warning(
            f"Entering degraded mode: {reason}, using {fallback}"
        )

    def log_degraded_mode_recovery(self, recovered_service: str) -> None:
        """Log recovery from degraded mode.

        Args:
            recovered_service: What service recovered (e.g., "CAKE stats")
        """
        self.logger.info(
            f"Recovered from degraded mode: {recovered_service} available again"
        )

    def log_debug_cycle_state(
        self,
        current_state: str,
        signals: CongestionSignals,
        assessment: str,
        details: Optional[str] = None
    ) -> None:
        """Log debug information for troubleshooting.

        Args:
            current_state: Current state name
            signals: CongestionSignals object
            assessment: Assessment result (GREEN, YELLOW, RED, etc)
            details: Optional additional details
        """
        state_suffix = current_state.split('_')[-1] if '_' in current_state else current_state
        details_str = f" - {details}" if details else ""
        self.logger.debug(
            f"[{self.wan_name}_{state_suffix}] [{assessment}] {signals}{details_str}"
        )

    def log_error_with_context(
        self,
        operation: str,
        error: Exception,
        context: Optional[str] = None
    ) -> None:
        """Log error with context and full traceback at debug level.

        Args:
            operation: Operation that failed
            error: Exception that was raised
            context: Optional context info
        """
        context_str = f" ({context})" if context else ""
        self.logger.error(
            f"{operation} failed{context_str}: {error}"
        )

    def log_cache_hit(self, cached_value: str, context: Optional[str] = None) -> None:
        """Log use of cached/fallback value.

        Args:
            cached_value: Description of cached value
            context: Optional context (e.g., "baseline RTT")
        """
        context_str = f" for {context}" if context else ""
        self.logger.debug(f"Using cached {cached_value}{context_str}")
