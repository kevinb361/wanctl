"""Queue bandwidth state machine for download and upload directions.

Implements 3-state (GREEN/YELLOW/RED) and 4-state (GREEN/YELLOW/SOFT_RED/RED)
congestion response with hysteresis counters and dwell timer.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import TYPE_CHECKING, Any

from wanctl.rate_utils import enforce_rate_bounds

if TYPE_CHECKING:
    from wanctl.cake_signal import CakeSignalSnapshot


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
        drop_rate_threshold: float = 0.0,
        backlog_threshold_bytes: int = 0,
        probe_multiplier_factor: float = 1.0,
        probe_ceiling_pct: float = 0.9,
        consecutive_yellow_decay_clamp: int = 0,
        # Phase 201 (DOCSIS-aware UL control mode) — keyword-only with safe
        # defaults. Legacy callers are byte-identical because docsis_mode
        # defaults False and the new branches gate on it.
        docsis_mode: bool = False,
        setpoint_bps: int | None = None,
        integral_window_seconds: float = 2.0,
        integral_threshold_ms_s: float = 30.0,
        cake_backlog_low_threshold_bytes: int = 5000,
        cake_delay_delta_low_threshold_us: int = 5000,
        red_decay_step_pct: float = 0.02,
        red_decay_delta_max_pct: float = 0.10,
        anti_windup_cycles: int = 60,
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
        # 200-10 R3: bound consecutive YELLOW multiplicative decay cycles.
        # Default 0 = no clamp (byte-identical). When > 0, hold after that
        # many consecutive YELLOW decay calls until any non-YELLOW zone resets.
        self.consecutive_yellow_decay_clamp = consecutive_yellow_decay_clamp
        self._yellow_decay_streak = 0
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

        # CAKE signal detection thresholds (Phase 160: DETECT-01, DETECT-02)
        self._drop_rate_threshold: float = drop_rate_threshold
        self._backlog_threshold_bytes: int = backlog_threshold_bytes
        self._dwell_bypassed_count: int = 0
        self._backlog_suppressed_count: int = 0
        self._dwell_bypassed_this_cycle: bool = False
        self._backlog_suppressed_this_cycle: bool = False

        # Exponential probe state (Phase 161: RECOV-01, RECOV-02, RECOV-03)
        self._probe_multiplier: float = 1.0
        self._probe_multiplier_factor: float = probe_multiplier_factor
        self._probe_ceiling_pct: float = probe_ceiling_pct
        self._probe_step_count: int = 0

        # Track previous state for transition detection
        self._last_zone: str = "GREEN"

        # Phase 201 — DOCSIS-aware UL control mode internals.
        # All initialized unconditionally; only consulted when docsis_mode=True.
        self._docsis_mode: bool = docsis_mode
        self._setpoint_bps: int | None = setpoint_bps
        # Cycle is 50ms (cake_signal.CYCLE_INTERVAL_SECONDS); use literal here
        # to avoid an import cycle with the legacy module surface.
        _window_size = max(1, round(integral_window_seconds / 0.05))
        self._integral_window: deque[float] = deque(maxlen=_window_size)
        self._integral_threshold_ms_s: float = integral_threshold_ms_s
        self._cake_backlog_low_threshold_bytes: int = cake_backlog_low_threshold_bytes
        self._cake_delay_delta_low_threshold_us: int = cake_delay_delta_low_threshold_us
        self._headroom_state: str = "EXHAUSTED"
        self._cake_aligned: bool = False
        self._last_integral_ms_s: float = 0.0
        self._red_decay_step_pct: float = red_decay_step_pct
        self._red_decay_delta_max_pct: float = red_decay_delta_max_pct
        self._anti_windup_cycles: int = anti_windup_cycles
        self._headroom_exhausted_streak: int = 0
        self._anti_windup_triggers: int = 0
        self._last_anti_windup_log_cycle: int = -(10**9)
        self._cycle_count: int = 0
        # REVIEWS HIGH-5: cycle-fidelity floor-hit counter (monotonic, daemon lifetime).
        self.floor_hit_cycles: int = 0
        # Phase 201 gap-closure: diagnostic fields for /health serialization.
        # Bounded ring buffer; 200 entries = 10s of cycles @ 50ms.
        self._zone_trace: deque[str] = deque(maxlen=200)
        self._last_max_delay_delta_us: int = 0
        # DOCSIS-mode current_rate seed (RESEARCH §4 recommendation): avoid a
        # 1-cycle ceiling-touch at daemon start by initializing at setpoint.
        if self._docsis_mode and self._setpoint_bps is not None:
            self.current_rate = min(self.current_rate, self._setpoint_bps)

    def adjust(
        self,
        baseline_rtt: float,
        load_rtt: float,
        target_delta: float,
        warn_delta: float,
        cake_snapshot: CakeSignalSnapshot | None = None,
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
        self._dwell_bypassed_this_cycle = False
        self._backlog_suppressed_this_cycle = False
        delta = load_rtt - baseline_rtt
        # Phase 201: integral + cake-alignment update BEFORE classify.
        # Consumes the same delta the classifier consumes, preserving existing
        # asymmetry-gate semantics from WANController.
        if self._docsis_mode:
            self._last_integral_ms_s, self._headroom_state = self._update_integral(delta)
            self._cake_aligned = self._is_cake_aligned_for_pushup(cake_snapshot)
            self._cycle_count += 1
            self._apply_anti_windup_if_needed()
        zone = self._classify_zone_3state(delta, target_delta, warn_delta, cake_snapshot)
        self._zone_trace.append(zone)
        if cake_snapshot is not None:
            self._last_max_delay_delta_us = int(cake_snapshot.max_delay_delta_us)

        # Track congestion during window (Phase 136: HYST-01)
        if zone in ("YELLOW", "RED"):
            self._window_had_congestion = True

        new_rate = self._compute_rate_3state(zone)
        new_rate = enforce_rate_bounds(new_rate, floor=self.floor_red_bps, ceiling=self.ceiling_bps)
        if new_rate == self.floor_red_bps:
            self.floor_hit_cycles += 1
        self.current_rate = new_rate

        transition_reason = self._build_transition_reason(
            zone, delta, target=target_delta, warn=warn_delta
        )
        return zone, new_rate, transition_reason

    def _classify_zone_3state(
        self,
        delta: float,
        target_delta: float,
        warn_delta: float,
        cake_snapshot: CakeSignalSnapshot | None = None,
    ) -> str:
        """Classify congestion zone for 3-state logic with dwell timer and deadband."""
        if delta > warn_delta:
            # RED: immediate, bypasses dwell (D-02)
            self.red_streak += 1
            self.green_streak = 0
            self._probe_multiplier = 1.0
            self._yellow_dwell = 0
            return "RED"

        if delta > target_delta:
            # Above GREEN->YELLOW threshold
            self.green_streak = 0
            self._probe_multiplier = 1.0
            self.red_streak = 0
            # DETECT-01: Drop rate bypasses dwell timer
            if (
                cake_snapshot is not None
                and not cake_snapshot.cold_start
                and self._drop_rate_threshold > 0
                and cake_snapshot.drop_rate > self._drop_rate_threshold
            ):
                self._dwell_bypassed_count += 1
                self._dwell_bypassed_this_cycle = True
                self._yellow_dwell = 0
                return "YELLOW"
            return self._apply_dwell_logic()

        if self._last_zone == "YELLOW" and delta >= (
            target_delta - min(self.deadband_ms, target_delta * 0.5)
        ):
            # Deadband: delta below target but within margin -> stay YELLOW (HYST-02, D-03)
            self.green_streak = 0
            self._probe_multiplier = 1.0
            self.red_streak = 0
            self._yellow_dwell = 0
            return "YELLOW"

        # GREEN: delta below threshold (and below deadband if was YELLOW)
        self.green_streak += 1
        self.red_streak = 0
        self._yellow_dwell = 0  # Reset dwell counter (HYST-03)

        # DETECT-02: Suppress green_streak while backlog is high
        if (
            cake_snapshot is not None
            and not cake_snapshot.cold_start
            and self._backlog_threshold_bytes > 0
            and cake_snapshot.backlog_bytes > self._backlog_threshold_bytes
        ):
            self.green_streak = 0
            self._probe_multiplier = 1.0
            self._backlog_suppressed_count += 1
            self._backlog_suppressed_this_cycle = True

        return "GREEN"

    def _update_integral(self, delta_ms: float) -> tuple[float, str]:
        """Append delta sample, return (integral_ms_s, headroom_state).

        Phase 201 RESEARCH §1. Negative deltas clamp to zero (transient
        improvements add no headroom credit). Window-not-full is conservative
        (EXHAUSTED) — controller stays clamped at setpoint until enough samples
        accumulate. Cycle interval is 50ms; integral_ms_s = sum * 0.05.
        """
        self._integral_window.append(max(0.0, float(delta_ms)))
        integral_ms_s = sum(self._integral_window) * 0.05
        self._last_integral_ms_s = integral_ms_s
        if len(self._integral_window) < (self._integral_window.maxlen or 0):
            self._headroom_exhausted_streak += 1
            return integral_ms_s, "EXHAUSTED"
        if integral_ms_s <= self._integral_threshold_ms_s:
            self._headroom_exhausted_streak = 0
            return integral_ms_s, "AVAILABLE"
        self._headroom_exhausted_streak += 1
        return integral_ms_s, "EXHAUSTED"

    def _recompute_headroom_state(self) -> None:
        """Synchronously recompute headroom_state from the integral window."""
        self._last_integral_ms_s = sum(self._integral_window) * 0.05
        if len(self._integral_window) < (self._integral_window.maxlen or 0):
            self._headroom_state = "EXHAUSTED"
        elif self._last_integral_ms_s <= self._integral_threshold_ms_s:
            self._headroom_state = "AVAILABLE"
        else:
            self._headroom_state = "EXHAUSTED"

    def _apply_anti_windup_if_needed(self) -> None:
        """Cap stuck DOCSIS integral after canary 20260504T231334Z floor cycles.

        VERIFICATION.md identified 1453 floor cycles with integral stuck in the
        30-155 ms*s range. Codex MEDIUM-CODEX-2 requires cap-and-clamp below
        threshold (not halve) and immediate headroom recompute.
        """
        if not self._docsis_mode:
            return
        if self._headroom_exhausted_streak < self._anti_windup_cycles:
            return
        if self.current_rate != self.floor_red_bps:
            return
        target_ms_s = max(0.0, self._integral_threshold_ms_s - 1.0)
        maxlen = self._integral_window.maxlen or 1
        per_sample = (target_ms_s / 0.05) / maxlen
        self._integral_window.clear()
        for _ in range(maxlen):
            self._integral_window.append(per_sample)
        self._last_integral_ms_s = sum(self._integral_window) * 0.05
        self._recompute_headroom_state()
        self._headroom_exhausted_streak = 0
        self._anti_windup_triggers += 1
        if self._cycle_count - self._last_anti_windup_log_cycle >= self._anti_windup_cycles:
            self._logger.info(
                "[ANTI-WINDUP] %s integral capped to %.2f ms*s after %d EXHAUSTED cycles at floor",
                self.name,
                target_ms_s,
                self._anti_windup_cycles,
            )
            self._last_anti_windup_log_cycle = self._cycle_count

    def _is_cake_aligned_for_pushup(self, cake: CakeSignalSnapshot | None) -> bool:
        """Categorical AND-gate: backlog low AND max_delay_delta_us low.

        Phase 197 mirror — never µs/ms ratio (Phase 200 RETRO Codex pushback).
        Cold-start veto-deny is intentional (RESEARCH Pitfall 4).
        """
        if cake is None or getattr(cake, "cold_start", False):
            return False
        backlog_low = cake.backlog_bytes <= self._cake_backlog_low_threshold_bytes
        delay_low = cake.max_delay_delta_us <= self._cake_delay_delta_low_threshold_us
        return bool(backlog_low and delay_low)

    def _apply_dwell_logic(self) -> str:
        """Apply dwell timer for GREEN->YELLOW transition (HYST-01).

        Shared by both 3-state and 4-state zone classification.
        """
        if self._last_zone == "YELLOW":
            return "YELLOW"  # Already in YELLOW, stay there

        self._yellow_dwell += 1
        _dir = "DL" if self.name == "download" else "UL"
        if self._yellow_dwell >= self.dwell_cycles:
            self._logger.info("[HYSTERESIS] %s dwell expired, GREEN->YELLOW confirmed", _dir)
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
            # 200-10 R3: RED decay remains immediate and resets YELLOW clamp state.
            self._yellow_decay_streak = 0
            if self._docsis_mode and self._setpoint_bps is not None:
                delta_max_bps = max(1, int(self._setpoint_bps * self._red_decay_delta_max_pct))
                clamp_bps = self._setpoint_bps - delta_max_bps
                if self.current_rate >= clamp_bps:
                    # REGIME A: bounded-absolute decay (codex HIGH-CODEX-1 Option B).
                    # Rev-4 invariant (HIGH-CODEX-2): immediate bounded decrease on every
                    # RED cycle until clamp, then hold at clamp above floor. Pre-clamp
                    # cycles decrease by step_bps; at-clamp cycles hold (MEDIUM-NEW-2
                    # validator proves clamp > floor). Canary 20260504T231334Z cycle
                    # table cycles 1-18 has floor_hit_cycles=0.
                    step_bps = max(1, int(self._setpoint_bps * self._red_decay_step_pct))
                    return max(int(self.current_rate - step_bps), clamp_bps)
            return int(self.current_rate * self.factor_down)
        if self.green_streak >= self.green_required:
            # 200-10 R3: sustained GREEN recovery resets the YELLOW clamp state.
            self._yellow_decay_streak = 0
            raw_rate = self.current_rate + self._compute_probe_step()
            # Phase 201: setpoint clamp on push-up only.
            # Decreases (RED/YELLOW) are unaffected — those branches return earlier.
            if self._docsis_mode and self._setpoint_bps is not None:
                if not (self._headroom_state == "AVAILABLE" and self._cake_aligned):
                    return min(raw_rate, self._setpoint_bps)
            return raw_rate
        if zone == "YELLOW":
            if (
                self._docsis_mode
                and self._setpoint_bps is not None
                and self.current_rate > self._setpoint_bps
                and self._headroom_state == "EXHAUSTED"
                and self._yellow_decay_streak >= self.dwell_cycles
            ):
                return min(int(self.current_rate * self.factor_down_yellow), self._setpoint_bps)
            if (
                self.consecutive_yellow_decay_clamp > 0
                and self._yellow_decay_streak >= self.consecutive_yellow_decay_clamp
            ):
                self._logger.debug(
                    "[YELLOW-CLAMP] %s held rate at %d after %d consecutive YELLOW decay cycles",
                    self.name,
                    self.current_rate,
                    self._yellow_decay_streak,
                )
                return self.current_rate
            self._yellow_decay_streak += 1
            return int(self.current_rate * self.factor_down_yellow)
        # 200-10 R3: any non-YELLOW zone, including a single GREEN below
        # green_required, resets the clamp counter.
        self._yellow_decay_streak = 0
        return self.current_rate

    def _compute_probe_step(self) -> int:
        """Compute recovery step with exponential probing (RECOV-01, RECOV-02).

        Step = step_up_bps * _probe_multiplier, then advance multiplier.
        Above probe_ceiling_pct of ceiling, reverts to linear step_up_bps.

        Returns:
            Step size in bps to add to current_rate.
        """
        # RECOV-02: Linear above ceiling threshold
        if self.current_rate >= self.ceiling_bps * self._probe_ceiling_pct:
            return self.step_up_bps

        # RECOV-01: Exponential probing
        step = int(self.step_up_bps * self._probe_multiplier)
        self._probe_multiplier *= self._probe_multiplier_factor
        max_multiplier = max(
            1.0, (self.ceiling_bps - self.floor_red_bps) / max(1, self.step_up_bps)
        )
        self._probe_multiplier = min(self._probe_multiplier, max_multiplier)
        self._probe_step_count += 1
        return step

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
        cake_snapshot: CakeSignalSnapshot | None = None,
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
        self._dwell_bypassed_this_cycle = False
        self._backlog_suppressed_this_cycle = False
        delta = load_rtt - baseline_rtt
        zone = self._classify_zone_4state(
            delta, green_threshold, soft_red_threshold, hard_red_threshold, cake_snapshot
        )

        # Track congestion during window (Phase 136: HYST-01)
        if zone in ("YELLOW", "SOFT_RED", "RED"):
            self._window_had_congestion = True

        new_rate, state_floor = self._compute_rate_4state(zone)
        new_rate = enforce_rate_bounds(new_rate, floor=state_floor, ceiling=self.ceiling_bps)
        self.current_rate = new_rate

        transition_reason = self._build_transition_reason(
            zone,
            delta,
            target=green_threshold,
            soft_red=soft_red_threshold,
            hard_red=hard_red_threshold,
        )
        return zone, new_rate, transition_reason

    def _classify_zone_4state(
        self,
        delta: float,
        green_threshold: float,
        soft_red_threshold: float,
        hard_red_threshold: float,
        cake_snapshot: CakeSignalSnapshot | None = None,
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
            self._probe_multiplier = 1.0
            self._yellow_dwell = 0
            return "RED"
        if raw_state == "YELLOW":
            self.green_streak = 0
            self._probe_multiplier = 1.0
            self.soft_red_streak = 0
            self.red_streak = 0
            # DETECT-01: Drop rate bypasses dwell timer
            if (
                cake_snapshot is not None
                and not cake_snapshot.cold_start
                and self._drop_rate_threshold > 0
                and cake_snapshot.drop_rate > self._drop_rate_threshold
            ):
                self._dwell_bypassed_count += 1
                self._dwell_bypassed_this_cycle = True
                self._yellow_dwell = 0
                return "YELLOW"
            return self._apply_dwell_logic()

        # raw_state == "GREEN" -- check deadband
        if self._last_zone == "YELLOW" and delta >= (
            green_threshold - min(self.deadband_ms, green_threshold * 0.5)
        ):
            # Deadband: raw GREEN but within margin -> stay YELLOW (HYST-02, D-03)
            self.green_streak = 0
            self._probe_multiplier = 1.0
            self.soft_red_streak = 0
            self.red_streak = 0
            self._yellow_dwell = 0
            return "YELLOW"

        # GREEN: below threshold and below deadband
        self.green_streak += 1
        self.soft_red_streak = 0
        self.red_streak = 0
        self._yellow_dwell = 0  # Reset dwell counter (HYST-03)

        # DETECT-02: Suppress green_streak while backlog is high
        if (
            cake_snapshot is not None
            and not cake_snapshot.cold_start
            and self._backlog_threshold_bytes > 0
            and cake_snapshot.backlog_bytes > self._backlog_threshold_bytes
        ):
            self.green_streak = 0
            self._probe_multiplier = 1.0
            self._backlog_suppressed_count += 1
            self._backlog_suppressed_this_cycle = True

        return "GREEN"

    def _apply_soft_red_sustain(self) -> str:
        """Apply SOFT_RED sustain logic -- require consecutive samples before confirming."""
        self.soft_red_streak += 1
        self.green_streak = 0
        self._probe_multiplier = 1.0
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
            return self.current_rate + self._compute_probe_step(), state_floor
        if zone == "YELLOW":
            return int(self.current_rate * self.factor_down_yellow), self.floor_yellow_bps
        return self.current_rate, state_floor

    def apply_burst_clamp(self) -> int:
        """Apply a bounded fast clamp for a confirmed download burst.

        This bypasses the slower YELLOW descent by taking one RED-strength
        decay step, but never drops below the SOFT_RED floor and never
        increases the rate if the queue is already below that floor.
        """
        self.green_streak = 0
        self.soft_red_streak = max(self.soft_red_streak, self.soft_red_required)
        self.red_streak = 0
        self._yellow_dwell = 0
        self._probe_multiplier = 1.0
        self._last_zone = "SOFT_RED"

        decayed_rate = int(self.current_rate * self.factor_down)
        new_rate = max(self.floor_soft_red_bps, decayed_rate)
        new_rate = min(new_rate, self.current_rate)
        self.current_rate = new_rate
        return new_rate

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
        """Return hysteresis and CAKE detection state for the health endpoint."""
        return {
            "hysteresis": {
                "dwell_counter": self._yellow_dwell,
                "dwell_cycles": self.dwell_cycles,
                "deadband_ms": self.deadband_ms,
                "transitions_suppressed": self._transitions_suppressed,
                "suppressions_per_min": self._window_suppressions,
                "window_start_epoch": self._window_start_time,
            },
            "cake_detection": {
                "drop_rate_threshold": self._drop_rate_threshold,
                "backlog_threshold_bytes": self._backlog_threshold_bytes,
                "dwell_bypassed_count": self._dwell_bypassed_count,
                "backlog_suppressed_count": self._backlog_suppressed_count,
                "dwell_bypassed_this_cycle": self._dwell_bypassed_this_cycle,
                "backlog_suppressed_this_cycle": self._backlog_suppressed_this_cycle,
            },
            "recovery_probe": {
                "probe_multiplier": self._probe_multiplier,
                "probe_multiplier_factor": self._probe_multiplier_factor,
                "probe_ceiling_pct": self._probe_ceiling_pct,
                "probe_step_count": self._probe_step_count,
                "above_ceiling_pct": self.current_rate
                >= self.ceiling_bps * self._probe_ceiling_pct,
            },
            "docsis_mode_active": bool(self._docsis_mode),
            "setpoint_mbps": ((self._setpoint_bps / 1_000_000) if self._setpoint_bps else None),
            "headroom_state": self._headroom_state,
            "rtt_integral_ms_s": round(self._last_integral_ms_s, 3),
            "cake_aligned": bool(self._cake_aligned),
            "floor_hit_cycles_total": int(self.floor_hit_cycles),
            # Original Plan 201-13 fields (rev 1):
            "max_delay_delta_us": int(self._last_max_delay_delta_us),
            "red_streak": int(self.red_streak),
            "zone_trace": list(self._zone_trace),
            # Absorbed from Plan 201-14 rev 4 WARNING 4/6. Fallbacks tolerate
            # pre-201-14 controller state for wave-ordering safety.
            "headroom_exhausted_streak": int(getattr(self, "_headroom_exhausted_streak", 0)),
            "anti_windup_cycles": int(getattr(self, "_anti_windup_cycles", 60)),
            "anti_windup_triggers": int(getattr(self, "_anti_windup_triggers", 0)),
            # REV 3 (codex MEDIUM-CODEX-3 active-knob proof) — runtime-state
            # echoes, NOT YAML re-reads.
            "red_decay_step_pct": float(getattr(self, "_red_decay_step_pct", 0.02)),
            "red_decay_delta_max_pct": float(getattr(self, "_red_decay_delta_max_pct", 0.10)),
        }
