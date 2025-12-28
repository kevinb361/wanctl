#!/usr/bin/env python3
"""
Phase 2B: Confidence-Based Steering with Sustained Degradation

Replaces binary RED→steer logic with multi-signal confidence scoring and
sustain timers to reduce unnecessary WAN steering.

Architecture:
  - Confidence score (0-100) computed from existing signals only
  - Sustain timers (degrade/hold_down/recovery) filter transient events
  - Flap detection safety brake prevents oscillation
  - Dry-run mode for validation (log-only, no routing changes)

Design Document: docs/PHASE_2B_DESIGN.md
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Tuple
from congestion_assessment import CongestionState


# =============================================================================
# CONFIDENCE SCORING
# =============================================================================

class ConfidenceWeights:
    """
    Heuristic weights for confidence scoring.

    These are fixed values based on operational experience, NOT statistical
    models or ML. Tuning is done via config thresholds, not weight adjustment.
    """
    # CAKE state base scores
    RED_STATE = 50
    SOFT_RED_SUSTAINED = 25  # Requires ≥ 3 cycles
    YELLOW_STATE = 10
    GREEN_STATE = 0

    # Additional signal contributions
    RTT_DELTA_HIGH = 15      # > 80ms
    RTT_DELTA_SEVERE = 25    # > 120ms
    DROPS_INCREASING = 10    # Trend over 3 cycles
    QUEUE_HIGH_SUSTAINED = 10  # ≥ 2 cycles


@dataclass
class ConfidenceSignals:
    """
    Input signals for confidence computation.
    All signals derived from existing measurements—no new probes.
    """
    cake_state: str  # "GREEN", "YELLOW", "SOFT_RED", "RED"
    rtt_delta_ms: float
    drops_per_sec: float
    queue_depth_pct: float

    # Historical context (for sustained detection)
    cake_state_history: List[str] = field(default_factory=list)
    drops_history: List[float] = field(default_factory=list)
    queue_history: List[float] = field(default_factory=list)


def compute_confidence(
    signals: ConfidenceSignals,
    logger: logging.Logger
) -> Tuple[int, List[str]]:
    """
    Compute confidence score (0-100) from current signals.

    Returns: (score, contributing_signals)

    Important:
      - Confidence recomputes from scratch every cycle (NO hysteresis)
      - When signals improve, confidence drops immediately
      - Temporal behavior lives in timers (sustain), not in score itself
    """
    score = 0
    contributors = []

    # Base score from CAKE state
    if signals.cake_state == "RED":
        score += ConfidenceWeights.RED_STATE
        contributors.append("RED")
    elif signals.cake_state == "SOFT_RED":
        # Only count if sustained ≥ 3 cycles
        if len(signals.cake_state_history) >= 3:
            recent = signals.cake_state_history[-3:]
            if all(s == "SOFT_RED" for s in recent):
                score += ConfidenceWeights.SOFT_RED_SUSTAINED
                contributors.append("SOFT_RED_sustained")
        else:
            # Not enough history, don't count
            pass
    elif signals.cake_state == "YELLOW":
        score += ConfidenceWeights.YELLOW_STATE
        contributors.append("YELLOW")
    else:  # GREEN
        score += ConfidenceWeights.GREEN_STATE

    # RTT delta contribution
    if signals.rtt_delta_ms > 120.0:
        score += ConfidenceWeights.RTT_DELTA_SEVERE
        contributors.append(f"rtt_delta={signals.rtt_delta_ms:.1f}ms(severe)")
    elif signals.rtt_delta_ms > 80.0:
        score += ConfidenceWeights.RTT_DELTA_HIGH
        contributors.append(f"rtt_delta={signals.rtt_delta_ms:.1f}ms(high)")

    # Drop rate trend (increasing over last 3 cycles)
    if len(signals.drops_history) >= 3:
        recent_drops = signals.drops_history[-3:]
        if recent_drops[-1] > recent_drops[0] and recent_drops[-1] > 0:
            score += ConfidenceWeights.DROPS_INCREASING
            contributors.append(f"drops_increasing({recent_drops[-1]:.1f}/s)")

    # Queue depth sustained
    if len(signals.queue_history) >= 2:
        recent_queue = signals.queue_history[-2:]
        if all(q > 50.0 for q in recent_queue):  # > 50% queue utilization
            score += ConfidenceWeights.QUEUE_HIGH_SUSTAINED
            contributors.append(f"queue_high({signals.queue_depth_pct:.0f}%)")

    # Clamp to 0-100
    score = max(0, min(100, score))

    logger.debug(f"Confidence={score} signals=[{', '.join(contributors)}]")

    return score, contributors


# =============================================================================
# TIMER STATE TRACKING
# =============================================================================

@dataclass
class TimerState:
    """
    Phase 2B meta-state for sustain timers and flap detection.

    This tracks decision confidence, not measurements.
    """
    # Confidence tracking
    confidence_score: int = 0
    confidence_contributors: List[str] = field(default_factory=list)

    # Sustain timers (seconds remaining)
    degrade_timer: Optional[int] = None  # Countdown to enable steering
    hold_down_timer: Optional[int] = None  # Post-steer cooldown
    recovery_timer: Optional[int] = None  # Countdown to disable steering

    # Flap detection
    flap_window: List[Tuple[str, float]] = field(default_factory=list)  # (event, timestamp)
    flap_penalty_active: bool = False
    flap_penalty_expiry: Optional[float] = None

    # Decision tracking (for logging)
    last_decision: Optional[str] = None
    last_decision_time: Optional[float] = None


class TimerManager:
    """Manages sustain timers and state transitions"""

    def __init__(
        self,
        steer_threshold: int,
        recovery_threshold: int,
        sustain_duration: int,
        recovery_duration: int,
        hold_down_duration: int,
        logger: logging.Logger
    ):
        self.steer_threshold = steer_threshold
        self.recovery_threshold = recovery_threshold
        self.sustain_duration = sustain_duration
        self.recovery_duration = recovery_duration
        self.hold_down_duration = hold_down_duration
        self.logger = logger

    def update_degrade_timer(
        self,
        timer_state: TimerState,
        confidence: int,
        current_state: str
    ) -> Optional[str]:
        """
        Update degrade timer and check for steer decision.

        Returns: "ENABLE_STEERING" if timer expires, None otherwise
        """
        # Only track degrade timer in SPECTRUM_GOOD state
        if current_state != "SPECTRUM_GOOD":
            if timer_state.degrade_timer is not None:
                timer_state.degrade_timer = None
                self.logger.debug("degrade_timer cleared (not in GOOD state)")
            return None

        # Check confidence threshold
        if confidence >= self.steer_threshold:
            if timer_state.degrade_timer is None:
                # Start timer
                timer_state.degrade_timer = self.sustain_duration
                self.logger.info(
                    f"confidence={confidence} signals={timer_state.confidence_contributors} "
                    f"degrade_timer_start={self.sustain_duration}s"
                )
            else:
                # Decrement timer
                timer_state.degrade_timer -= 2  # Assessment interval is 2s
                self.logger.info(
                    f"confidence={confidence} signals={timer_state.confidence_contributors} "
                    f"degrade_timer={timer_state.degrade_timer}s"
                )

                if timer_state.degrade_timer <= 0:
                    # Timer expired—steer!
                    self.logger.warning(
                        f"degrade_timer expired: confidence={confidence} sustained={self.sustain_duration}s"
                    )
                    timer_state.degrade_timer = None
                    return "ENABLE_STEERING"
        else:
            # Confidence dropped below threshold
            if timer_state.degrade_timer is not None:
                self.logger.info(
                    f"confidence={confidence} degrade_timer_reset reason=below_threshold"
                )
                timer_state.degrade_timer = None

        return None

    def update_hold_down_timer(self, timer_state: TimerState, current_state: str):
        """
        Update hold-down timer (post-steer cooldown).

        Hold-down never resets—runs to completion.
        """
        if current_state != "SPECTRUM_DEGRADED":
            # Not in degraded state, no hold-down
            if timer_state.hold_down_timer is not None:
                timer_state.hold_down_timer = None
                self.logger.debug("hold_down_timer cleared (not in DEGRADED state)")
            return

        if timer_state.hold_down_timer is not None:
            # Decrement timer
            timer_state.hold_down_timer -= 2
            self.logger.debug(
                f"hold_down_active remaining={timer_state.hold_down_timer}s "
                f"confidence={timer_state.confidence_score} (ignored)"
            )

            if timer_state.hold_down_timer <= 0:
                # Hold-down expired
                self.logger.info("hold_down_expired resume_evaluation")
                timer_state.hold_down_timer = None

    def update_recovery_timer(
        self,
        timer_state: TimerState,
        confidence: int,
        cake_state: str,
        rtt_delta: float,
        drops: float,
        current_state: str
    ) -> Optional[str]:
        """
        Update recovery timer and check for recovery decision.

        Returns: "DISABLE_STEERING" if timer expires, None otherwise
        """
        # Only track recovery timer in SPECTRUM_DEGRADED state (after hold-down)
        if current_state != "SPECTRUM_DEGRADED" or timer_state.hold_down_timer is not None:
            if timer_state.recovery_timer is not None:
                timer_state.recovery_timer = None
                self.logger.debug("recovery_timer cleared (hold-down active or not in DEGRADED)")
            return None

        # Check recovery conditions
        recovery_eligible = (
            confidence <= self.recovery_threshold and
            cake_state == "GREEN" and
            rtt_delta < 10.0 and
            drops < 0.001
        )

        if recovery_eligible:
            if timer_state.recovery_timer is None:
                # Start timer
                timer_state.recovery_timer = self.recovery_duration
                self.logger.info(
                    f"confidence={confidence} signals={timer_state.confidence_contributors} "
                    f"recovery_timer_start={self.recovery_duration}s"
                )
            else:
                # Decrement timer
                timer_state.recovery_timer -= 2
                self.logger.info(
                    f"confidence={confidence} signals={timer_state.confidence_contributors} "
                    f"recovery_timer={timer_state.recovery_timer}s"
                )

                if timer_state.recovery_timer <= 0:
                    # Timer expired—recover!
                    self.logger.info(
                        f"recovery_timer expired: confidence={confidence} sustained={self.recovery_duration}s"
                    )
                    timer_state.recovery_timer = None
                    return "DISABLE_STEERING"
        else:
            # Recovery conditions violated
            if timer_state.recovery_timer is not None:
                reason = []
                if confidence > self.recovery_threshold:
                    reason.append(f"confidence={confidence}")
                if cake_state != "GREEN":
                    reason.append(f"state={cake_state}")
                if rtt_delta >= 10.0:
                    reason.append(f"rtt_delta={rtt_delta:.1f}ms")
                if drops >= 0.001:
                    reason.append(f"drops={drops:.3f}")

                self.logger.info(
                    f"recovery_timer_reset reason=[{', '.join(reason)}]"
                )
                timer_state.recovery_timer = None

        return None


# =============================================================================
# FLAP DETECTION
# =============================================================================

class FlapDetector:
    """
    Detect repeated steering oscillations and apply penalty.

    Safety brake to prevent system from becoming part of the problem.
    """

    def __init__(
        self,
        enabled: bool,
        window_minutes: int,
        max_toggles: int,
        penalty_duration: int,
        penalty_threshold_add: int,
        logger: logging.Logger
    ):
        self.enabled = enabled
        self.window_seconds = window_minutes * 60
        self.max_toggles = max_toggles
        self.penalty_duration = penalty_duration
        self.penalty_threshold_add = penalty_threshold_add
        self.logger = logger

    def record_toggle(self, timer_state: TimerState, event: str):
        """Record a steering state change (enable or disable)"""
        if not self.enabled:
            return

        now = time.time()
        timer_state.flap_window.append((event, now))

        # Prune old events outside window
        cutoff = now - self.window_seconds
        timer_state.flap_window = [
            (e, t) for e, t in timer_state.flap_window if t > cutoff
        ]

    def check_flapping(
        self,
        timer_state: TimerState,
        base_threshold: int
    ) -> int:
        """
        Check for flapping and apply penalty if needed.

        Returns: effective steer threshold (base + penalty if active)
        """
        if not self.enabled:
            return base_threshold

        # Check if penalty already active
        if timer_state.flap_penalty_active:
            if time.time() < timer_state.flap_penalty_expiry:
                # Penalty still active
                return base_threshold + self.penalty_threshold_add
            else:
                # Penalty expired
                self.logger.warning(
                    f"[FLAP-BRAKE] DISENGAGED: penalty_expired, "
                    f"threshold={base_threshold + self.penalty_threshold_add}→{base_threshold} (restored)"
                )
                timer_state.flap_penalty_active = False
                timer_state.flap_penalty_expiry = None
                return base_threshold

        # Check for flapping
        toggle_count = len(timer_state.flap_window)
        if toggle_count > self.max_toggles:
            # Flapping detected—engage penalty
            self.logger.error(
                f"[FLAP-BRAKE] ENGAGED: flap_detected, toggles={toggle_count}, "
                f"window={self.window_seconds // 60}min, "
                f"threshold={base_threshold}→{base_threshold + self.penalty_threshold_add}, "
                f"duration={self.penalty_duration}s"
            )
            timer_state.flap_penalty_active = True
            timer_state.flap_penalty_expiry = time.time() + self.penalty_duration
            return base_threshold + self.penalty_threshold_add

        return base_threshold


# =============================================================================
# DRY-RUN MODE
# =============================================================================

class DryRunLogger:
    """Logs hypothetical decisions without executing routing changes"""

    def __init__(self, enabled: bool, logger: logging.Logger):
        self.enabled = enabled
        self.logger = logger

    def log_decision(
        self,
        decision: str,
        confidence: int,
        contributors: List[str],
        sustained: int
    ):
        """Log a hypothetical steering decision"""
        if not self.enabled:
            return

        signals_str = ', '.join(contributors)

        if decision == "ENABLE_STEERING":
            self.logger.warning(
                f"[DRY-RUN] WOULD_ENABLE_STEERING confidence={confidence} "
                f"sustained={sustained}s signals=[{signals_str}]"
            )
            self.logger.info("[DRY-RUN] Would execute: enable mangle rule")
            self.logger.info("[DRY-RUN] Actual routing unchanged")
        elif decision == "DISABLE_STEERING":
            self.logger.info(
                f"[DRY-RUN] WOULD_DISABLE_STEERING confidence={confidence} "
                f"sustained={sustained}s signals=[{signals_str}]"
            )
            self.logger.info("[DRY-RUN] Would execute: disable mangle rule")
            self.logger.info("[DRY-RUN] Actual routing unchanged")


# =============================================================================
# PHASE 2B CONTROLLER
# =============================================================================

class Phase2BController:
    """
    Confidence-based steering controller with sustained degradation filtering.

    Integrates with existing SteeringDaemon via dry-run mode.
    """

    def __init__(
        self,
        config_v3: dict,
        logger: logging.Logger
    ):
        self.logger = logger
        self.config = config_v3

        # Confidence thresholds
        confidence_cfg = config_v3['confidence']
        self.base_steer_threshold = confidence_cfg['steer_threshold']
        self.recovery_threshold = confidence_cfg['recovery_threshold']

        # Timer manager
        timers_cfg = config_v3['timers']
        self.timer_mgr = TimerManager(
            steer_threshold=self.base_steer_threshold,
            recovery_threshold=self.recovery_threshold,
            sustain_duration=confidence_cfg['sustain_duration_sec'],
            recovery_duration=confidence_cfg['recovery_sustain_sec'],
            hold_down_duration=timers_cfg['hold_down_duration_sec'],
            logger=logger
        )

        # Flap detector
        flap_cfg = config_v3['flap_detection']
        self.flap_detector = FlapDetector(
            enabled=flap_cfg['enabled'],
            window_minutes=flap_cfg['window_minutes'],
            max_toggles=flap_cfg['max_toggles'],
            penalty_duration=flap_cfg['penalty_duration_sec'],
            penalty_threshold_add=flap_cfg['penalty_threshold_add'],
            logger=logger
        )

        # Dry-run mode
        dry_run_cfg = config_v3['dry_run']
        self.dry_run = DryRunLogger(
            enabled=dry_run_cfg['enabled'],
            logger=logger
        )

        # State
        self.timer_state = TimerState()

        self.logger.info("Phase 2B Controller initialized (confidence-based steering)")
        if dry_run_cfg['enabled']:
            self.logger.warning("[DRY-RUN] Phase 2B in LOG-ONLY mode - no routing changes")

    def evaluate(
        self,
        signals: ConfidenceSignals,
        current_state: str
    ) -> Optional[str]:
        """
        Evaluate steering decision based on confidence and timers.

        Args:
            signals: Current congestion signals
            current_state: "SPECTRUM_GOOD" or "SPECTRUM_DEGRADED"

        Returns:
            "ENABLE_STEERING", "DISABLE_STEERING", or None
        """
        # Compute confidence
        confidence, contributors = compute_confidence(signals, self.logger)
        self.timer_state.confidence_score = confidence
        self.timer_state.confidence_contributors = contributors

        # Check flap penalty
        effective_threshold = self.flap_detector.check_flapping(
            self.timer_state,
            self.base_steer_threshold
        )

        # Update timers
        if current_state == "SPECTRUM_GOOD":
            # Check for degradation
            decision = self.timer_mgr.update_degrade_timer(
                self.timer_state,
                confidence,
                current_state
            )

            if decision == "ENABLE_STEERING":
                # Log decision
                self.dry_run.log_decision(
                    decision,
                    confidence,
                    contributors,
                    self.config['confidence']['sustain_duration_sec']
                )

                # Record toggle for flap detection
                self.flap_detector.record_toggle(self.timer_state, "ENABLE")

                return decision if not self.dry_run.enabled else None

        elif current_state == "SPECTRUM_DEGRADED":
            # Update hold-down
            self.timer_mgr.update_hold_down_timer(self.timer_state, current_state)

            # Check for recovery (only if hold-down expired)
            if self.timer_state.hold_down_timer is None:
                decision = self.timer_mgr.update_recovery_timer(
                    self.timer_state,
                    confidence,
                    signals.cake_state,
                    signals.rtt_delta_ms,
                    signals.drops_per_sec,
                    current_state
                )

                if decision == "DISABLE_STEERING":
                    # Log decision
                    self.dry_run.log_decision(
                        decision,
                        confidence,
                        contributors,
                        self.config['confidence']['recovery_sustain_sec']
                    )

                    # Record toggle for flap detection
                    self.flap_detector.record_toggle(self.timer_state, "DISABLE")

                    return decision if not self.dry_run.enabled else None

        return None
