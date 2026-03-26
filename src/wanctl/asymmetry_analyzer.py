"""OWD asymmetric congestion detection from IRTT burst measurements.

Analyzes send_delay vs receive_delay divergence within IRTT measurement
bursts to detect upstream-only or downstream-only congestion. Uses ratio-
based detection (NTP-independent) with configurable threshold.

Components:
    AsymmetryResult: Frozen dataclass with direction + ratio snapshot
    AsymmetryAnalyzer: Stateful analyzer with transition logging
    DIRECTION_ENCODING: Float mapping for SQLite persistence

Signal flow:
    analyze(irtt_result) -> AsymmetryResult with direction/ratio
    Direction transitions logged at INFO, per-measurement at DEBUG
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from wanctl.irtt_measurement import IRTTResult

# Direction encoding for SQLite REAL column persistence
DIRECTION_ENCODING: dict[str, float] = {
    "unknown": 0.0,
    "symmetric": 1.0,
    "upstream": 2.0,
    "downstream": 3.0,
}

# Minimum delay threshold (ms) -- below this, ratios amplify noise
_MIN_DELAY_MS = 0.1


@dataclass(frozen=True, slots=True)
class AsymmetryResult:
    """Directional congestion detection result from IRTT OWD analysis."""

    direction: str  # "upstream", "downstream", "symmetric", "unknown"
    ratio: float  # max(send/receive, receive/send) -- always >= 1.0 (or 0.0 for unknown)
    send_delay_ms: float
    receive_delay_ms: float


class AsymmetryAnalyzer:
    """Compute directional congestion from IRTT send/receive delay medians.

    Args:
        ratio_threshold: Minimum ratio for asymmetry declaration (default 2.0)
        logger: Logger instance for transition messages
        wan_name: WAN identifier for log prefixing
    """

    def __init__(
        self,
        ratio_threshold: float = 2.0,
        logger: logging.Logger | None = None,
        wan_name: str = "",
    ) -> None:
        self._threshold = ratio_threshold
        self._last_direction: str = "unknown"
        self._logger = logger or logging.getLogger(__name__)
        self._wan_name = wan_name

    def analyze(self, irtt_result: IRTTResult) -> AsymmetryResult:
        """Compute asymmetry direction from IRTT send/receive delay medians.

        Returns AsymmetryResult with direction and ratio. Direction is one of:
        - "upstream": send_delay dominates (send/receive >= threshold)
        - "downstream": receive_delay dominates (receive/send >= threshold)
        - "symmetric": neither direction exceeds threshold
        - "unknown": data unavailable or unreliable
        """
        send = irtt_result.send_delay_median_ms
        receive = irtt_result.receive_delay_median_ms

        # Both delays near zero or negative -- data unavailable
        if send <= 0 and receive <= 0:
            result = AsymmetryResult("unknown", 0.0, send, receive)
            self._log_transition(result.direction)
            return result

        # Both delays below noise floor -- symmetric by definition
        if send < _MIN_DELAY_MS and receive < _MIN_DELAY_MS:
            result = AsymmetryResult("symmetric", 1.0, send, receive)
            self._log_transition(result.direction)
            return result

        # Divide-by-zero guards -- one side is zero, other is positive
        if receive <= 0:
            # send > 0, receive <= 0: upstream dominant, cap ratio at 100.0
            result = AsymmetryResult("upstream", min(send / _MIN_DELAY_MS, 100.0), send, receive)
            self._log_transition(result.direction)
            return result
        if send <= 0:
            # receive > 0, send <= 0: downstream dominant, cap ratio at 100.0
            result = AsymmetryResult(
                "downstream", min(receive / _MIN_DELAY_MS, 100.0), send, receive
            )
            self._log_transition(result.direction)
            return result

        # Normal case: compute directional ratios
        send_ratio = send / receive
        recv_ratio = receive / send

        if send_ratio >= self._threshold:
            direction = "upstream"
            ratio = send_ratio
        elif recv_ratio >= self._threshold:
            direction = "downstream"
            ratio = recv_ratio
        else:
            direction = "symmetric"
            ratio = max(send_ratio, recv_ratio)

        result = AsymmetryResult(direction, ratio, send, receive)
        self._log_transition(result.direction)
        return result

    def _log_transition(self, new_direction: str) -> None:
        """Log direction transitions at INFO, suppress repeated states."""
        if new_direction != self._last_direction:
            self._logger.info(
                f"{self._wan_name}: Asymmetry transition {self._last_direction} -> {new_direction}"
            )
            self._last_direction = new_direction
