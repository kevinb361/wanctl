"""Burst detection via RTT acceleration (second derivative).

Detects multi-flow burst ramps by tracking the rate-of-change of RTT velocity.
Called once per cycle with the current load_rtt (EWMA-smoothed). When sustained
positive acceleration exceeds a configurable threshold for N consecutive cycles,
a burst event fires.

Detection fires BurstResult.is_burst=True which WANController._apply_burst_response
(Phase 152) uses to trigger fast-path floor-jump responses.

Signal flow:
    load_rtt -> BurstDetector.update() -> BurstResult
        -> acceleration = velocity(t) - velocity(t-1) [ms/cycle^2]
        -> is_burst when streak >= confirm_cycles

Follows SignalProcessor pattern: stdlib only, frozen dataclass result,
logger injection, per-WAN instance.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

# ============================================================================
# BurstResult dataclass
# ============================================================================


@dataclass(frozen=True, slots=True)
class BurstResult:
    """Per-cycle burst detection result returned by BurstDetector.update().

    Attributes:
        acceleration: Second derivative -- velocity(t) - velocity(t-1), in ms/cycle^2.
        velocity: First derivative -- load_rtt(t) - load_rtt(t-1), in ms/cycle.
        is_burst: True if burst confirmed (streak >= confirm_cycles).
        consecutive_accel: Current streak of above-threshold acceleration cycles.
        warming_up: True until 3+ samples received (first 2 cycles).
    """

    acceleration: float
    velocity: float
    is_burst: bool
    consecutive_accel: int
    warming_up: bool


# ============================================================================
# BurstDetector class
# ============================================================================


class BurstDetector:
    """Detects multi-flow burst ramps via RTT acceleration (second derivative).

    Computes the second derivative of load_rtt each cycle. When acceleration
    exceeds accel_threshold_ms for confirm_cycles consecutive cycles, a burst
    event fires. Single-flow linear ramps produce near-zero acceleration and
    do not trigger detection.

    Args:
        wan_name: WAN identifier for log messages.
        accel_threshold_ms: Acceleration threshold in ms/cycle^2 to count as
            above-threshold. Higher values require steeper ramps.
        confirm_cycles: Number of consecutive above-threshold acceleration
            cycles required before firing a burst event.
        logger: Logger instance for burst event warnings.
    """

    def __init__(
        self,
        wan_name: str,
        accel_threshold_ms: float,
        confirm_cycles: int,
        logger: logging.Logger,
    ) -> None:
        self._wan_name = wan_name
        self._accel_threshold = accel_threshold_ms
        self._confirm_cycles = confirm_cycles
        self._logger = logger

        # Internal state
        self._prev_load_rtt: float | None = None
        self._prev_velocity: float | None = None
        self._accel_streak: int = 0
        self._total_bursts: int = 0

    # ====================================================================
    # Core update method
    # ====================================================================

    def update(self, load_rtt: float) -> BurstResult:
        """Process one cycle's load_rtt and return burst detection result.

        Cycle 1 (no prev_load_rtt): Store load_rtt, return warming_up result.
        Cycle 2 (no prev_velocity): Compute velocity, return warming_up result.
        Cycle 3+: Compute velocity and acceleration, check burst threshold.

        Args:
            load_rtt: Current EWMA-smoothed RTT in milliseconds.

        Returns:
            BurstResult with computed acceleration, velocity, burst status.
        """
        # Cycle 1: no previous RTT yet
        if self._prev_load_rtt is None:
            self._prev_load_rtt = load_rtt
            return BurstResult(
                acceleration=0.0,
                velocity=0.0,
                is_burst=False,
                consecutive_accel=0,
                warming_up=True,
            )

        # Compute velocity (first derivative)
        velocity = load_rtt - self._prev_load_rtt
        self._prev_load_rtt = load_rtt

        # Cycle 2: no previous velocity yet
        if self._prev_velocity is None:
            self._prev_velocity = velocity
            return BurstResult(
                acceleration=0.0,
                velocity=velocity,
                is_burst=False,
                consecutive_accel=0,
                warming_up=True,
            )

        # Cycle 3+: compute acceleration (second derivative)
        acceleration = velocity - self._prev_velocity
        self._prev_velocity = velocity

        # Check acceleration against threshold
        if acceleration > self._accel_threshold:
            self._accel_streak += 1
        else:
            self._accel_streak = 0

        # Check burst confirmation
        is_burst = self._accel_streak >= self._confirm_cycles
        if is_burst and self._accel_streak == self._confirm_cycles:
            # Fire burst event exactly once when streak reaches threshold
            self._total_bursts += 1
            self._logger.warning(
                "%s: BURST detected! accel=%.2fms/cycle^2 "
                "(%d consecutive, threshold=%.1fms/cycle^2)",
                self._wan_name,
                acceleration,
                self._accel_streak,
                self._accel_threshold,
            )

        return BurstResult(
            acceleration=acceleration,
            velocity=velocity,
            is_burst=is_burst,
            consecutive_accel=self._accel_streak,
            warming_up=False,
        )

    # ====================================================================
    # Properties for runtime config mutation (SIGUSR1 reload)
    # ====================================================================

    @property
    def accel_threshold(self) -> float:
        """Current acceleration threshold in ms/cycle^2."""
        return self._accel_threshold

    @accel_threshold.setter
    def accel_threshold(self, value: float) -> None:
        self._accel_threshold = value

    @property
    def confirm_cycles(self) -> int:
        """Current confirmation cycle count."""
        return self._confirm_cycles

    @confirm_cycles.setter
    def confirm_cycles(self, value: int) -> None:
        self._confirm_cycles = value

    @property
    def total_bursts(self) -> int:
        """Lifetime count of burst events detected."""
        return self._total_bursts

    # ====================================================================
    # Reset
    # ====================================================================

    def reset(self) -> None:
        """Clear detection state for re-initialization.

        Resets RTT history, velocity, and streak counter. Does NOT reset
        total_bursts (lifetime counter).
        """
        self._prev_load_rtt = None
        self._prev_velocity = None
        self._accel_streak = 0
