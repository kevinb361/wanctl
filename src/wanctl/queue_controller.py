"""Queue bandwidth state machine for download and upload directions.

Implements 3-state (GREEN/YELLOW/RED) and 4-state (GREEN/YELLOW/SOFT_RED/RED)
congestion response with hysteresis counters and dwell timer.
"""

import logging
import time

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

        # State-dependent zone classification with dwell timer and deadband
        if delta > warn_delta:
            # RED: immediate, bypasses dwell (D-02)
            self.red_streak += 1
            self.green_streak = 0
            self._yellow_dwell = 0
            zone = "RED"
        elif delta > target_delta:
            # Above GREEN->YELLOW threshold
            self.green_streak = 0
            self.red_streak = 0
            if self._last_zone == "YELLOW":
                # Already in YELLOW, stay there
                zone = "YELLOW"
            else:
                # In GREEN (or dwell-held GREEN), apply dwell timer (HYST-01)
                self._yellow_dwell += 1
                if self._yellow_dwell >= self.dwell_cycles:
                    zone = "YELLOW"  # Dwell satisfied, transition
                    _dir = "DL" if self.name == "download" else "UL"
                    self._logger.info(
                        "[HYSTERESIS] %s dwell expired, GREEN->YELLOW confirmed",
                        _dir,
                    )
                else:
                    zone = "GREEN"  # Hold GREEN during dwell, rates hold steady (D-01)
                    self._transitions_suppressed += 1
                    self._window_suppressions += 1
                    _dir = "DL" if self.name == "download" else "UL"
                    self._logger.debug(
                        "[HYSTERESIS] %s transition suppressed, dwell %d/%d",
                        _dir,
                        self._yellow_dwell,
                        self.dwell_cycles,
                    )
        elif self._last_zone == "YELLOW" and delta >= (target_delta - min(self.deadband_ms, target_delta * 0.5)):
            # Deadband: delta below target but within deadband margin -> stay YELLOW (HYST-02, D-03)
            # Clamp deadband to 50% of target_delta to prevent impossible recovery when deadband >= target
            self.green_streak = 0
            self.red_streak = 0
            self._yellow_dwell = 0
            zone = "YELLOW"
        else:
            # GREEN: delta below threshold (and below deadband if was YELLOW)
            self.green_streak += 1
            self.red_streak = 0
            self._yellow_dwell = 0  # Reset dwell counter (HYST-03)
            zone = "GREEN"

        # Track congestion during window (Phase 136: HYST-01)
        if zone in ("YELLOW", "RED"):
            self._window_had_congestion = True

        # Apply rate adjustments with hysteresis
        new_rate = self.current_rate

        if self.red_streak >= 1:
            # RED: Gradual decay using factor_down
            new_rate = int(self.current_rate * self.factor_down)
        elif self.green_streak >= self.green_required:
            # GREEN: Only step up after 5 consecutive green cycles
            new_rate = self.current_rate + self.step_up_bps
        elif zone == "YELLOW":
            # YELLOW: Gentle decay to prevent congestion buildup
            new_rate = int(self.current_rate * self.factor_down_yellow)
        # else: GREEN but not sustained -> hold steady

        # Enforce floor and ceiling constraints
        new_rate = enforce_rate_bounds(new_rate, floor=self.floor_red_bps, ceiling=self.ceiling_bps)

        self.current_rate = new_rate

        # Track state transitions with reason
        transition_reason: str | None = None
        if zone != self._last_zone:
            if zone == "RED":
                transition_reason = (
                    f"RTT delta {delta:.1f}ms exceeded warn threshold {warn_delta}ms"
                )
            elif zone == "YELLOW":
                transition_reason = (
                    f"RTT delta {delta:.1f}ms exceeded target threshold {target_delta}ms"
                )
            elif zone == "GREEN":
                transition_reason = (
                    f"RTT delta {delta:.1f}ms fell below target threshold {target_delta}ms"
                )
            self._last_zone = zone

        return zone, new_rate, transition_reason

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

        # Determine raw state based on thresholds
        if delta > hard_red_threshold:
            raw_state = "RED"
        elif delta > soft_red_threshold:
            raw_state = "SOFT_RED"
        elif delta > green_threshold:
            raw_state = "YELLOW"
        else:
            raw_state = "GREEN"

        # Apply sustain logic for SOFT_RED (unchanged, D-02)
        if raw_state == "SOFT_RED":
            self.soft_red_streak += 1
            self.green_streak = 0
            self.red_streak = 0
            self._yellow_dwell = 0
            if self.soft_red_streak >= self.soft_red_required:
                zone = "SOFT_RED"
            else:
                # Not sustained yet - stay in YELLOW
                zone = "YELLOW"
        elif raw_state == "RED":
            self.red_streak += 1
            self.soft_red_streak = 0
            self.green_streak = 0
            self._yellow_dwell = 0
            zone = "RED"
        elif raw_state == "YELLOW":
            # Above GREEN->YELLOW threshold: apply dwell timer (HYST-01)
            self.green_streak = 0
            self.soft_red_streak = 0
            self.red_streak = 0
            if self._last_zone == "YELLOW":
                zone = "YELLOW"  # Already YELLOW, stay
            else:
                self._yellow_dwell += 1
                if self._yellow_dwell >= self.dwell_cycles:
                    zone = "YELLOW"  # Dwell satisfied
                    _dir = "DL" if self.name == "download" else "UL"
                    self._logger.info(
                        "[HYSTERESIS] %s dwell expired, GREEN->YELLOW confirmed",
                        _dir,
                    )
                else:
                    zone = "GREEN"  # Hold during dwell (D-01)
                    self._transitions_suppressed += 1
                    self._window_suppressions += 1
                    _dir = "DL" if self.name == "download" else "UL"
                    self._logger.debug(
                        "[HYSTERESIS] %s transition suppressed, dwell %d/%d",
                        _dir,
                        self._yellow_dwell,
                        self.dwell_cycles,
                    )
        elif self._last_zone == "YELLOW" and delta >= (green_threshold - min(self.deadband_ms, green_threshold * 0.5)):
            # Deadband: raw GREEN but within deadband margin -> stay YELLOW (HYST-02, D-03)
            # Clamp deadband to 50% of green_threshold to prevent impossible recovery when deadband >= threshold
            self.green_streak = 0
            self.soft_red_streak = 0
            self.red_streak = 0
            self._yellow_dwell = 0
            zone = "YELLOW"
        else:
            # GREEN: below threshold and below deadband
            self.green_streak += 1
            self.soft_red_streak = 0
            self.red_streak = 0
            self._yellow_dwell = 0  # Reset dwell counter (HYST-03)
            zone = "GREEN"

        # Track congestion during window (Phase 136: HYST-01)
        if zone in ("YELLOW", "SOFT_RED", "RED"):
            self._window_had_congestion = True

        # Apply rate adjustments with state-appropriate floors
        new_rate = self.current_rate

        # Determine appropriate floor based on state
        state_floor = self.floor_green_bps  # Default

        if self.red_streak >= 1:
            # RED: Gradual decay using factor_down
            new_rate = int(self.current_rate * self.factor_down)
            state_floor = self.floor_red_bps
        elif zone == "SOFT_RED":
            # SOFT_RED: Clamp to soft_red floor and HOLD (no repeated decay)
            # Keep current rate but enforce soft_red floor
            state_floor = self.floor_soft_red_bps
        elif self.green_streak >= self.green_required:
            # GREEN: Only step up after 5 consecutive green cycles
            new_rate = self.current_rate + self.step_up_bps
        elif zone == "YELLOW":
            # YELLOW: Gentle decay to prevent congestion buildup
            # Uses factor_down_yellow (default 0.96 = 4% per cycle)
            new_rate = int(self.current_rate * self.factor_down_yellow)
            state_floor = self.floor_yellow_bps
        # else: GREEN but not sustained -> use default floor_green_bps

        # Enforce floor and ceiling constraints based on current state
        new_rate = enforce_rate_bounds(new_rate, floor=state_floor, ceiling=self.ceiling_bps)

        self.current_rate = new_rate

        # Track state transitions with reason
        transition_reason: str | None = None
        if zone != self._last_zone:
            if zone == "RED":
                transition_reason = (
                    f"RTT delta {delta:.1f}ms exceeded hard_red threshold {hard_red_threshold}ms"
                )
            elif zone == "SOFT_RED":
                transition_reason = (
                    f"RTT delta {delta:.1f}ms exceeded soft_red threshold {soft_red_threshold}ms"
                )
            elif zone == "YELLOW":
                transition_reason = (
                    f"RTT delta {delta:.1f}ms exceeded green threshold {green_threshold}ms"
                )
            elif zone == "GREEN":
                transition_reason = (
                    f"RTT delta {delta:.1f}ms fell below green threshold {green_threshold}ms"
                )
            self._last_zone = zone

        return zone, new_rate, transition_reason

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
