"""Queue bandwidth state machine for download and upload directions.

Implements 3-state (GREEN/YELLOW/RED) and 4-state (GREEN/YELLOW/SOFT_RED/RED)
congestion response with hysteresis counters and dwell timer.
"""

import logging
import time
from typing import Any

from wanctl.rate_utils import enforce_rate_bounds


class QueueController:
    """Controls one queue (download or upload) with 3-zone or 4-zone logic"""

    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        name: str,
        floor_green: int,
        floor_yellow: int,
        floor_soft_red: int,
        floor_red: int,
        ceiling: int,
        step_up: int,
        factor_down: float,
        factor_down_yellow: float = 1.0,
        green_required: int = 5,
        dwell_cycles: int = 3,
        deadband_ms: float = 3.0,
    ):
        self.name = name
        self.floor_green_bps = floor_green
        self.floor_yellow_bps = floor_yellow
        self.floor_soft_red_bps = floor_soft_red  # Phase 2A
        self.floor_red_bps = floor_red
        self.ceiling_bps = ceiling
        self.step_up_bps = step_up
        self.factor_down = factor_down
        self.factor_down_yellow = (
            factor_down_yellow  # Gentle decay for YELLOW (default 1.0 = no decay)
        )
        self.current_rate = ceiling  # Start at ceiling

        # Hysteresis counters (require consecutive green cycles before stepping up)
        self.green_streak = 0
        self.soft_red_streak = 0  # Phase 2A: Track SOFT_RED sustain
        self.red_streak = 0
        self.green_required = green_required  # Consecutive GREEN cycles before stepping up
        self.soft_red_required = 1  # Reduced from 3 for faster response (50ms vs 150ms)

        # Hysteresis: dwell timer gates GREEN->YELLOW (requires consecutive above-threshold cycles)
        self.dwell_cycles = dwell_cycles
        self.deadband_ms = deadband_ms
        self._yellow_dwell = 0
        self._transitions_suppressed = 0  # Cumulative count of absorbed dwell cycles

        # Windowed suppression counter (Phase 136: HYST-01, per D-01/D-02)
        self._window_suppressions: int = 0
        self._window_start_time: float = time.time()
        self._window_had_congestion: bool = False

        # Track previous state for transition detection
        self._last_zone: str = "GREEN"

    def adjust(
        self, baseline_rtt: float, load_rtt: float, target_delta: float, warn_delta: float
    ) -> tuple[str, int, str | None]:
        """
        Apply 3-zone logic with hysteresis and return (zone, new_rate, transition_reason)

        Zones:
        - GREEN: delta <= target_delta -> slowly increase rate (requires consecutive green cycles)
        - YELLOW: target_delta < delta <= warn_delta -> hold steady
        - RED: delta > warn_delta -> aggressively back off (immediate)

        Hysteresis:
        - RED: Immediate step-down on 1 red sample
        - GREEN: Require 5 consecutive green cycles before stepping up (prevents seesaw)

        Returns:
            (zone, new_rate, transition_reason)
            transition_reason is None if no state change, otherwise explains why
        """
        delta = load_rtt - baseline_rtt
        zone = self._classify_zone_3state(delta, target_delta, warn_delta)

        # Track congestion during window (Phase 136: HYST-01)
        if zone in ("YELLOW", "RED"):
            self._window_had_congestion = True

        new_rate = self._compute_rate_3state(zone)
        new_rate = enforce_rate_bounds(new_rate, floor=self.floor_red_bps, ceiling=self.ceiling_bps)
        self.current_rate = new_rate

        transition_reason = self._build_transition_reason(
            zone, delta, target=target_delta, warn=warn_delta
        )
        return zone, new_rate, transition_reason

    def _classify_zone_3state(
        self, delta: float, target_delta: float, warn_delta: float
    ) -> str:
        """Classify congestion zone for 3-state logic with dwell timer and deadband."""
        if delta > warn_delta:
            # RED: immediate, bypasses dwell (D-02)
            self.red_streak += 1
            self.green_streak = 0
            self._yellow_dwell = 0
            return "RED"

        if delta > target_delta:
            # Above GREEN->YELLOW threshold
            self.green_streak = 0
            self.red_streak = 0
            return self._apply_dwell_logic()

        if self._last_zone == "YELLOW" and delta >= (
            target_delta - min(self.deadband_ms, target_delta * 0.5)
        ):
            # Deadband: delta below target but within margin -> stay YELLOW (HYST-02, D-03)
            self.green_streak = 0
            self.red_streak = 0
            self._yellow_dwell = 0
            return "YELLOW"

        # GREEN: delta below threshold (and below deadband if was YELLOW)
        self.green_streak += 1
        self.red_streak = 0
        self._yellow_dwell = 0  # Reset dwell counter (HYST-03)
        return "GREEN"

    def _apply_dwell_logic(self) -> str:
        """Apply dwell timer for GREEN->YELLOW transition (HYST-01).

        Shared by both 3-state and 4-state zone classification.
        """
        if self._last_zone == "YELLOW":
            return "YELLOW"  # Already in YELLOW, stay there

        self._yellow_dwell += 1
        _dir = "DL" if self.name == "download" else "UL"
        if self._yellow_dwell >= self.dwell_cycles:
            self._logger.info(
                "[HYSTERESIS] %s dwell expired, GREEN->YELLOW confirmed", _dir
            )
            return "YELLOW"

        # Hold GREEN during dwell, rates hold steady (D-01)
        self._transitions_suppressed += 1
        self._window_suppressions += 1
        self._logger.debug(
            "[HYSTERESIS] %s transition suppressed, dwell %d/%d",
            _dir,
            self._yellow_dwell,
            self.dwell_cycles,
        )
        return "GREEN"

    def _compute_rate_3state(self, zone: str) -> int:
        """Compute new rate for 3-state logic based on zone and streaks."""
        if self.red_streak >= 1:
            return int(self.current_rate * self.factor_down)
        if self.green_streak >= self.green_required:
            return self.current_rate + self.step_up_bps
        if zone == "YELLOW":
            return int(self.current_rate * self.factor_down_yellow)
        return self.current_rate

    def _build_transition_reason(
        self,
        zone: str,
        delta: float,
        *,
        target: float = 0.0,
        warn: float = 0.0,
        soft_red: float = 0.0,
        hard_red: float = 0.0,
    ) -> str | None:
        """Build transition reason string if zone changed, update _last_zone.

        Shared by both 3-state and 4-state logic.
        """
        if zone == self._last_zone:
            return None

        self._last_zone = zone
        if zone == "RED":
            threshold = hard_red if hard_red else warn
            label = "hard_red threshold" if hard_red else "warn threshold"
            return f"RTT delta {delta:.1f}ms exceeded {label} {threshold}ms"
        if zone == "SOFT_RED":
            return f"RTT delta {delta:.1f}ms exceeded soft_red threshold {soft_red}ms"
        if zone == "YELLOW":
            threshold = target if target else 0.0
            label = "green threshold" if hard_red else "target threshold"
            return f"RTT delta {delta:.1f}ms exceeded {label} {threshold}ms"
        if zone == "GREEN":
            threshold = target if target else 0.0
            label = "green threshold" if hard_red else "target threshold"
            return f"RTT delta {delta:.1f}ms fell below {label} {threshold}ms"
        return None

    def adjust_4state(
        self,
        baseline_rtt: float,
        load_rtt: float,
        green_threshold: float,
        soft_red_threshold: float,
        hard_red_threshold: float,
    ) -> tuple[str, int, str | None]:
        """
        Apply 4-state logic with hysteresis and return (state, new_rate, transition_reason)

        Phase 2A: Download-only (Spectrum download)
        Upload continues to use 3-state adjust() method

        States (based on RTT delta from baseline):
        - GREEN: delta <= 15ms -> slowly increase rate (requires consecutive green cycles)
        - YELLOW: 15ms < delta <= 45ms -> hold steady
        - SOFT_RED: 45ms < delta <= 80ms -> clamp to soft_red floor and HOLD (no steering)
        - RED: delta > 80ms -> aggressive backoff (immediate)

        Hysteresis:
        - RED: Immediate on 1 sample
        - SOFT_RED: Requires 3 consecutive samples (~6 seconds)
        - GREEN: Requires 5 consecutive samples before stepping up
        - YELLOW: Immediate

        Returns:
            (zone, new_rate, transition_reason)
            transition_reason is None if no state change, otherwise explains why
        """
        delta = load_rtt - baseline_rtt
        zone = self._classify_zone_4state(delta, green_threshold, soft_red_threshold, hard_red_threshold)

        # Track congestion during window (Phase 136: HYST-01)
        if zone in ("YELLOW", "SOFT_RED", "RED"):
            self._window_had_congestion = True

        new_rate, state_floor = self._compute_rate_4state(zone)
        new_rate = enforce_rate_bounds(new_rate, floor=state_floor, ceiling=self.ceiling_bps)
        self.current_rate = new_rate

        transition_reason = self._build_transition_reason(
            zone, delta, target=green_threshold, soft_red=soft_red_threshold, hard_red=hard_red_threshold
        )
        return zone, new_rate, transition_reason

    def _classify_zone_4state(
        self,
        delta: float,
        green_threshold: float,
        soft_red_threshold: float,
        hard_red_threshold: float,
    ) -> str:
        """Classify congestion zone for 4-state logic with dwell timer and deadband."""
        # Determine raw state based on thresholds
        if delta > hard_red_threshold:
            raw_state = "RED"
        elif delta > soft_red_threshold:
            raw_state = "SOFT_RED"
        elif delta > green_threshold:
            raw_state = "YELLOW"
        else:
            raw_state = "GREEN"

        if raw_state == "SOFT_RED":
            return self._apply_soft_red_sustain()
        if raw_state == "RED":
            self.red_streak += 1
            self.soft_red_streak = 0
            self.green_streak = 0
            self._yellow_dwell = 0
            return "RED"
        if raw_state == "YELLOW":
            self.green_streak = 0
            self.soft_red_streak = 0
            self.red_streak = 0
            return self._apply_dwell_logic()

        # raw_state == "GREEN" -- check deadband
        if self._last_zone == "YELLOW" and delta >= (
            green_threshold - min(self.deadband_ms, green_threshold * 0.5)
        ):
            # Deadband: raw GREEN but within margin -> stay YELLOW (HYST-02, D-03)
            self.green_streak = 0
            self.soft_red_streak = 0
            self.red_streak = 0
            self._yellow_dwell = 0
            return "YELLOW"

        # GREEN: below threshold and below deadband
        self.green_streak += 1
        self.soft_red_streak = 0
        self.red_streak = 0
        self._yellow_dwell = 0  # Reset dwell counter (HYST-03)
        return "GREEN"

    def _apply_soft_red_sustain(self) -> str:
        """Apply SOFT_RED sustain logic -- require consecutive samples before confirming."""
        self.soft_red_streak += 1
        self.green_streak = 0
        self.red_streak = 0
        self._yellow_dwell = 0
        if self.soft_red_streak >= self.soft_red_required:
            return "SOFT_RED"
        return "YELLOW"  # Not sustained yet

    def _compute_rate_4state(self, zone: str) -> tuple[int, int]:
        """Compute new rate and floor for 4-state logic. Returns (rate, floor)."""
        state_floor = self.floor_green_bps

        if self.red_streak >= 1:
            return int(self.current_rate * self.factor_down), self.floor_red_bps
        if zone == "SOFT_RED":
            return self.current_rate, self.floor_soft_red_bps
        if self.green_streak >= self.green_required:
            return self.current_rate + self.step_up_bps, state_floor
        if zone == "YELLOW":
            return int(self.current_rate * self.factor_down_yellow), self.floor_yellow_bps
        return self.current_rate, state_floor

    def reset_window(self) -> int:
        """Reset windowed suppression counter. Returns previous window's count.

        Called at 60s window boundary by WANController._check_hysteresis_window().
        Phase 136: HYST-01, per D-01/D-02.
        """
        count = self._window_suppressions
        self._window_suppressions = 0
        self._window_start_time = time.time()
        self._window_had_congestion = False
        return count

    # =========================================================================
    # PUBLIC FACADE API
    # =========================================================================

    def get_health_data(self) -> dict[str, Any]:
        """Return hysteresis state for the health endpoint."""
        return {
            "hysteresis": {
                "dwell_counter": self._yellow_dwell,
                "dwell_cycles": self.dwell_cycles,
                "deadband_ms": self.deadband_ms,
                "transitions_suppressed": self._transitions_suppressed,
                "suppressions_per_min": self._window_suppressions,
                "window_start_epoch": self._window_start_time,
            },
        }
