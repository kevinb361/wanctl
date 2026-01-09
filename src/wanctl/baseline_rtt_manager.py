"""Baseline RTT management and EWMA smoothing utilities.

Consolidates baseline RTT handling logic used in both autorate_continuous.py
and steering/daemon.py. Provides EWMA baseline updates with idle-only condition,
bounds validation, and RTT delta calculation.

Key architectural invariant: Baseline RTT must not drift during load.
Only update baseline when delta is minimal (line is idle).
"""

import logging
from pathlib import Path
from typing import Optional

from .state_utils import safe_json_load_file


class BaselineRTTManager:
    """Manages baseline RTT tracking with EWMA smoothing and idle-only updates.

    Architectural invariant: Baseline RTT represents the "normal" RTT without
    congestion. It must ONLY update when the line is idle (delta < threshold)
    to prevent baseline drift that would mask true congestion.

    Attributes:
        baseline_rtt: Current baseline RTT in milliseconds
        alpha_baseline: EWMA smoothing factor for baseline (0-1, typically 0.1-0.3)
        baseline_update_threshold: Only update baseline when delta < this (ms)
        logger: Logger instance
    """

    def __init__(
        self,
        initial_baseline: float,
        alpha_baseline: float,
        baseline_update_threshold: float,
        logger: logging.Logger
    ):
        """Initialize baseline RTT manager.

        Args:
            initial_baseline: Initial baseline RTT in milliseconds
            alpha_baseline: EWMA smoothing factor (0.0-1.0)
            baseline_update_threshold: Only update when load_rtt - baseline < this (ms)
            logger: Logger instance for debug messages
        """
        self.baseline_rtt = initial_baseline
        self.alpha_baseline = alpha_baseline
        self.baseline_update_threshold = baseline_update_threshold
        self.logger = logger

    def update_baseline_ewma(self, measured_rtt: float, load_rtt: float) -> None:
        """Update baseline RTT using EWMA with idle-only condition.

        Critical: Only update baseline when delta is very small. This prevents
        baseline drift during load, which would mask true congestion.

        Args:
            measured_rtt: Current measured RTT (from ping)
            load_rtt: Current load RTT (fast EWMA)
        """
        # Calculate delta (how much above baseline we currently are)
        delta = load_rtt - self.baseline_rtt

        if delta < self.baseline_update_threshold:
            # Line is idle or nearly idle - safe to update baseline
            old_baseline = self.baseline_rtt
            self.baseline_rtt = (
                (1 - self.alpha_baseline) * self.baseline_rtt +
                self.alpha_baseline * measured_rtt
            )
            self.logger.debug(
                f"Baseline RTT updated (idle): {old_baseline:.2f}ms -> {self.baseline_rtt:.2f}ms "
                f"(delta={delta:.2f}ms, below threshold={self.baseline_update_threshold}ms)"
            )
        else:
            # Under load - freeze baseline to prevent drift
            self.logger.debug(
                f"Baseline RTT frozen (under load): {self.baseline_rtt:.2f}ms "
                f"(delta={delta:.2f}ms, above threshold={self.baseline_update_threshold}ms)"
            )

    def get_delta(self, current_rtt: float) -> float:
        """Calculate RTT delta from baseline.

        Args:
            current_rtt: Current measured RTT in milliseconds

        Returns:
            Delta (current_rtt - baseline_rtt) in milliseconds
        """
        if self.baseline_rtt is None:
            return 0.0
        return current_rtt - self.baseline_rtt

    def set_baseline(self, new_baseline: float) -> None:
        """Set baseline RTT to new value (for external updates).

        Args:
            new_baseline: New baseline RTT in milliseconds
        """
        self.baseline_rtt = new_baseline

    def to_dict(self) -> dict:
        """Export baseline RTT state for persistence.

        Returns:
            Dictionary with baseline_rtt value
        """
        return {
            "baseline_rtt": self.baseline_rtt
        }

    def from_dict(self, data: dict) -> None:
        """Restore baseline RTT state from persistence.

        Args:
            data: Dictionary with baseline_rtt value
        """
        if "baseline_rtt" in data and data["baseline_rtt"] is not None:
            self.baseline_rtt = float(data["baseline_rtt"])


class BaselineValidator:
    """Validates baseline RTT against configured bounds.

    Provides defense-in-depth validation to prevent malicious or corrupted
    baseline values from affecting control decisions (C4 security fix).
    """

    def __init__(
        self,
        min_baseline: float,
        max_baseline: float,
        logger: logging.Logger
    ):
        """Initialize baseline validator.

        Args:
            min_baseline: Minimum sane baseline RTT (ms)
            max_baseline: Maximum sane baseline RTT (ms)
            logger: Logger instance
        """
        self.min_baseline = min_baseline
        self.max_baseline = max_baseline
        self.logger = logger

    def validate(self, baseline_rtt: float) -> bool:
        """Validate baseline RTT is within bounds.

        Args:
            baseline_rtt: Baseline RTT to validate (ms)

        Returns:
            True if valid (within bounds), False if out of bounds
        """
        if baseline_rtt < self.min_baseline or baseline_rtt > self.max_baseline:
            self.logger.warning(
                f"Baseline RTT out of bounds [{self.min_baseline:.1f}-{self.max_baseline:.1f}ms]: "
                f"{baseline_rtt:.2f}ms, rejecting (possible corruption or attack)"
            )
            return False
        return True

    def get_validated(self, baseline_rtt: Optional[float]) -> Optional[float]:
        """Validate and return baseline RTT, or None if invalid.

        Args:
            baseline_rtt: Baseline RTT to validate

        Returns:
            baseline_rtt if valid, None if invalid or None
        """
        if baseline_rtt is None:
            return None
        return baseline_rtt if self.validate(baseline_rtt) else None


class BaselineRTTLoader:
    """Loads baseline RTT from autorate state file.

    Used by steering daemon to load baseline established by autorate_continuous.
    Includes bounds validation and error handling.
    """

    def __init__(
        self,
        state_file: Path,
        validator: BaselineValidator,
        logger: logging.Logger,
        change_threshold: float = 5.0
    ):
        """Initialize baseline RTT loader.

        Args:
            state_file: Path to autorate_continuous state file
            validator: BaselineValidator for bounds checking
            logger: Logger instance
            change_threshold: Log warning if baseline changes by more than this (ms)
        """
        self.state_file = state_file
        self.validator = validator
        self.logger = logger
        self.change_threshold = change_threshold
        self.last_baseline = None

    def load(self) -> Optional[float]:
        """Load baseline RTT from state file.

        Reads ewma.baseline_rtt from autorate_continuous state file with
        bounds validation.

        Returns:
            Baseline RTT in milliseconds, or None if unavailable/invalid
        """
        if not self.state_file.exists():
            self.logger.debug(f"State file not found: {self.state_file}")
            return None

        state = safe_json_load_file(
            self.state_file,
            logger=self.logger,
            default=None,
            error_context="autorate state for baseline RTT"
        )

        if state is None:
            self.logger.warning("Failed to load state file for baseline RTT")
            return None

        # Extract baseline from autorate_continuous format: state['ewma']['baseline_rtt']
        try:
            if 'ewma' in state and 'baseline_rtt' in state['ewma']:
                baseline_rtt = float(state['ewma']['baseline_rtt'])

                # Validate bounds
                if not self.validator.validate(baseline_rtt):
                    return None

                # Log significant changes
                if self.last_baseline is not None:
                    change = abs(baseline_rtt - self.last_baseline)
                    if change > self.change_threshold:
                        self.logger.info(
                            f"Baseline RTT changed: {self.last_baseline:.2f}ms -> {baseline_rtt:.2f}ms "
                            f"(delta {change:+.2f}ms)"
                        )

                self.last_baseline = baseline_rtt
                self.logger.debug(f"Loaded baseline RTT: {baseline_rtt:.2f}ms")
                return baseline_rtt
            else:
                self.logger.debug("Baseline RTT not found in state file")
                return None

        except (KeyError, ValueError, TypeError) as e:
            self.logger.error(f"Failed to parse baseline RTT from state: {e}")
            return None


def calculate_rtt_delta(current_rtt: float, baseline_rtt: Optional[float]) -> float:
    """Calculate RTT delta from baseline.

    Helper function for calculating delta when baseline manager not available.

    Args:
        current_rtt: Current RTT in milliseconds
        baseline_rtt: Baseline RTT in milliseconds (or None)

    Returns:
        Delta (current_rtt - baseline_rtt), or 0.0 if baseline is None
    """
    if baseline_rtt is None:
        return 0.0
    return current_rtt - baseline_rtt
