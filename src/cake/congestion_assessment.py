#!/usr/bin/env python3
"""
Congestion State Assessment for Adaptive WAN Steering
Three-state model: GREEN → YELLOW → RED
"""

from enum import Enum
from dataclasses import dataclass
from cake_stats import CongestionSignals
import logging


class CongestionState(Enum):
    """Three-state congestion model"""
    GREEN = "GREEN"     # Healthy - no congestion
    YELLOW = "YELLOW"   # Warning - early congestion signals
    RED = "RED"         # Critical - confirmed congestion, routing active


@dataclass
class StateThresholds:
    """Thresholds for congestion state assessment"""
    # RTT thresholds (ms)
    green_rtt: float = 5.0      # Below this = GREEN
    yellow_rtt: float = 15.0    # Above this = YELLOW (warning)
    red_rtt: float = 15.0       # Above this (with CAKE drops) = RED

    # CAKE thresholds
    min_drops_red: int = 1      # Minimum drops required for RED
    min_queue_yellow: int = 10  # Queue depth for YELLOW warning
    min_queue_red: int = 50     # Queue depth for RED (deeper congestion)

    # Hysteresis
    red_samples_required: int = 2      # Consecutive RED samples before routing
    green_samples_required: int = 15   # Consecutive GREEN samples before recovery

    def __post_init__(self):
        """Validate thresholds"""
        assert self.green_rtt < self.yellow_rtt, "green_rtt must be < yellow_rtt"
        assert self.yellow_rtt <= self.red_rtt, "yellow_rtt must be <= red_rtt"
        assert self.min_drops_red > 0, "min_drops_red must be positive"
        assert self.red_samples_required >= 1, "red_samples_required must be >= 1"
        assert self.green_samples_required >= 1, "green_samples_required must be >= 1"


def assess_congestion_state(
    signals: CongestionSignals,
    thresholds: StateThresholds,
    logger: logging.Logger
) -> CongestionState:
    """
    Assess current congestion state based on multiple signals

    Decision logic:
      RED:    RTT > red_threshold AND drops > 0 AND queue > red_threshold
      YELLOW: RTT > yellow_threshold OR queue > yellow_threshold
      GREEN:  Otherwise

    Args:
        signals: Current congestion signals
        thresholds: State thresholds
        logger: Logger for debug output

    Returns:
        CongestionState (GREEN, YELLOW, or RED)
    """
    rtt = signals.rtt_delta_ewma
    drops = signals.cake_drops
    queue = signals.queued_packets

    # RED: Multiple signals confirm serious congestion
    if (rtt > thresholds.red_rtt and
        drops >= thresholds.min_drops_red and
        queue >= thresholds.min_queue_red):

        logger.debug(
            f"Assessment: RED - rtt={rtt:.1f}ms (>{thresholds.red_rtt}), "
            f"drops={drops} (>={thresholds.min_drops_red}), "
            f"queue={queue} (>={thresholds.min_queue_red})"
        )
        return CongestionState.RED

    # YELLOW: Early warning (elevated RTT OR rising queue, but no drops yet)
    elif (rtt > thresholds.yellow_rtt or queue >= thresholds.min_queue_yellow):
        logger.debug(
            f"Assessment: YELLOW - rtt={rtt:.1f}ms (threshold={thresholds.yellow_rtt}), "
            f"queue={queue} (threshold={thresholds.min_queue_yellow}), drops={drops}"
        )
        return CongestionState.YELLOW

    # GREEN: All systems nominal
    else:
        logger.debug(f"Assessment: GREEN - rtt={rtt:.1f}ms, drops={drops}, queue={queue}")
        return CongestionState.GREEN


def ewma_update(current: float, new_value: float, alpha: float) -> float:
    """
    Exponentially Weighted Moving Average update

    Args:
        current: Current EWMA value
        new_value: New measurement
        alpha: Smoothing factor (0-1, higher = less smoothing)

    Returns:
        Updated EWMA value
    """
    if current == 0.0:
        # First measurement - initialize with new value
        return new_value

    return (1.0 - alpha) * current + alpha * new_value
