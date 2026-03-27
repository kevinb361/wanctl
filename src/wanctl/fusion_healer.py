"""Fusion healer: auto-suspend fusion on low ICMP/IRTT correlation.

Monitors the rolling Pearson correlation between ICMP and IRTT RTT deltas
per-cycle. When protocol path divergence is detected (low correlation
sustained over a configurable window), the healer automatically suspends
fusion and locks the fusion_icmp_weight parameter. Recovery requires
sustained good correlation through an asymmetric hysteresis (longer
recovery than suspension) to avoid oscillation.

State machine:
    ACTIVE -> SUSPENDED -> RECOVERING -> ACTIVE
    RECOVERING -> SUSPENDED (correlation worsens during recovery)

Integration points:
    - AlertEngine.fire() on each state transition (rule_key="fusion_healing")
    - lock_parameter() / pop for fusion_icmp_weight during SUSPENDED/RECOVERING
    - start_grace_period() called by SIGUSR1 reload handler

Overhead: ~3us per tick() call (incremental Pearson, no allocations in steady state).
"""

from __future__ import annotations

import enum
import logging
import math
import time
from collections import deque
from typing import TYPE_CHECKING

from wanctl.tuning.safety import lock_parameter

if TYPE_CHECKING:
    from wanctl.alert_engine import AlertEngine

logger = logging.getLogger(__name__)


class HealState(enum.Enum):
    """Fusion healer state machine states."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    RECOVERING = "recovering"


class FusionHealer:
    """Per-WAN fusion healer with incremental rolling Pearson correlation.

    Monitors ICMP/IRTT signal delta correlation and manages fusion state
    through a 3-state machine with asymmetric hysteresis.

    Args:
        wan_name: WAN identifier for logging and alerts.
        suspend_threshold: Pearson r below which correlation is "low".
        recover_threshold: Pearson r above which correlation is "good".
        suspend_window_sec: Seconds of sustained low correlation to suspend.
        recover_window_sec: Seconds of sustained good correlation to recover.
        grace_period_sec: Duration of SIGUSR1 grace period.
        cycle_interval_sec: Control loop interval (default 50ms).
        min_samples: Minimum samples before Pearson is meaningful.
        alert_engine: Optional AlertEngine for transition alerts.
        parameter_locks: Optional reference to WANController._parameter_locks dict.
    """

    def __init__(
        self,
        wan_name: str,
        *,
        suspend_threshold: float = 0.3,
        recover_threshold: float = 0.5,
        suspend_window_sec: float = 60.0,
        recover_window_sec: float = 300.0,
        grace_period_sec: float = 1800.0,
        cycle_interval_sec: float = 0.05,
        min_samples: int = 100,
        alert_engine: AlertEngine | None = None,
        parameter_locks: dict[str, float] | None = None,
    ) -> None:
        self._wan_name = wan_name
        self._suspend_threshold = suspend_threshold
        self._recover_threshold = recover_threshold
        self._grace_period_sec = grace_period_sec
        self._min_samples = min_samples
        self._alert_engine = alert_engine
        self._parameter_locks = parameter_locks

        # Window sizes in samples
        self._suspend_window_samples = int(suspend_window_sec / cycle_interval_sec)
        self._recover_window_samples = int(recover_window_sec / cycle_interval_sec)

        # State
        self._state = HealState.ACTIVE
        self._grace_until: float = 0.0
        self._last_transition_ts: float | None = None

        # Rolling Pearson buffers (maxlen = suspend_window_samples for correlation window)
        self._x_buf: deque[float] = deque(maxlen=self._suspend_window_samples)
        self._y_buf: deque[float] = deque(maxlen=self._suspend_window_samples)

        # Running sums for incremental Pearson
        self._sum_x: float = 0.0
        self._sum_y: float = 0.0
        self._sum_xy: float = 0.0
        self._sum_x2: float = 0.0
        self._sum_y2: float = 0.0
        self._n: int = 0

        # Sustained counters
        self._sustained_below_count: int = 0
        self._sustained_above_count: int = 0

    def _add_sample(self, x: float, y: float) -> None:
        """Add a sample pair, evicting oldest if window is full."""
        if self._n >= self._suspend_window_samples:
            # Evict oldest
            old_x = self._x_buf[0]
            old_y = self._y_buf[0]
            self._sum_x -= old_x
            self._sum_y -= old_y
            self._sum_xy -= old_x * old_y
            self._sum_x2 -= old_x * old_x
            self._sum_y2 -= old_y * old_y
            self._n -= 1

        self._x_buf.append(x)
        self._y_buf.append(y)
        self._sum_x += x
        self._sum_y += y
        self._sum_xy += x * y
        self._sum_x2 += x * x
        self._sum_y2 += y * y
        self._n += 1

    def _compute_pearson(self) -> float | None:
        """Compute Pearson correlation from running sums.

        Returns:
            Pearson r in [-1, 1], or None if insufficient samples.
        """
        if self._n < self._min_samples:
            return None

        n = self._n
        numerator = n * self._sum_xy - self._sum_x * self._sum_y
        denom_sq = (n * self._sum_x2 - self._sum_x**2) * (
            n * self._sum_y2 - self._sum_y**2
        )

        if denom_sq <= 0.0:
            return 0.0

        return numerator / math.sqrt(denom_sq)

    def tick(self, icmp_delta: float, irtt_delta: float) -> HealState:
        """Process one cycle of ICMP/IRTT deltas through the state machine.

        Args:
            icmp_delta: ICMP RTT delta for this cycle.
            irtt_delta: IRTT RTT delta for this cycle.

        Returns:
            Current HealState after processing.
        """
        self._add_sample(icmp_delta, irtt_delta)

        # Grace period: skip monitoring
        if time.monotonic() < self._grace_until:
            return self._state

        r = self._compute_pearson()
        if r is None:
            return self._state  # Warmup

        # State machine transitions
        if self._state == HealState.ACTIVE:
            if r < self._suspend_threshold:
                self._sustained_below_count += 1
                if self._sustained_below_count >= self._suspend_window_samples:
                    self._transition_to(HealState.SUSPENDED, r)
            else:
                self._sustained_below_count = 0

        elif self._state == HealState.SUSPENDED:
            if r >= self._recover_threshold:
                self._sustained_above_count += 1
                if self._sustained_above_count >= self._recover_window_samples:
                    self._transition_to(HealState.RECOVERING, r)
            else:
                self._sustained_above_count = 0

        elif self._state == HealState.RECOVERING:
            if r >= self._recover_threshold:
                self._sustained_above_count += 1
                if self._sustained_above_count >= self._recover_window_samples:
                    self._transition_to(HealState.ACTIVE, r)
            else:
                self._sustained_above_count = 0
                if r < self._suspend_threshold:
                    # Correlation worsened during recovery
                    self._transition_to(HealState.SUSPENDED, r)

        return self._state

    def _transition_to(self, new_state: HealState, r: float) -> None:
        """Execute a state transition with alerts and parameter locking."""
        old_state = self._state
        self._state = new_state
        self._last_transition_ts = time.monotonic()

        # Reset counters
        self._sustained_below_count = 0
        self._sustained_above_count = 0

        # Alert type mapping
        alert_map = {
            (HealState.ACTIVE, HealState.SUSPENDED): "fusion_suspended",
            (HealState.SUSPENDED, HealState.RECOVERING): "fusion_recovering",
            (HealState.RECOVERING, HealState.ACTIVE): "fusion_recovered",
            (HealState.RECOVERING, HealState.SUSPENDED): "fusion_suspended",
        }
        alert_type = alert_map.get((old_state, new_state))

        # Parameter locking
        if new_state == HealState.SUSPENDED and old_state != HealState.SUSPENDED:
            if self._parameter_locks is not None:
                lock_parameter(self._parameter_locks, "fusion_icmp_weight", float("inf"))

        elif new_state == HealState.ACTIVE:
            if self._parameter_locks is not None:
                self._parameter_locks.pop("fusion_icmp_weight", None)

        # Fire alert
        if alert_type is not None:
            self._fire_transition_alert(alert_type, r)

        logger.info(
            "Fusion healer %s: %s -> %s (r=%.4f)",
            self._wan_name,
            old_state.value,
            new_state.value,
            r,
        )

    def _fire_transition_alert(self, alert_type: str, r: float) -> None:
        """Fire an AlertEngine event for a state transition."""
        if self._alert_engine is None:
            return

        threshold = (
            self._suspend_threshold
            if "suspend" in alert_type
            else self._recover_threshold
        )

        self._alert_engine.fire(
            alert_type=alert_type,
            severity="warning",
            wan_name=self._wan_name,
            details={
                "pearson_r": round(r, 4),
                "threshold": threshold,
                "state": self._state.value,
            },
            rule_key="fusion_healing",
        )

    def start_grace_period(self) -> None:
        """Start a SIGUSR1 grace period: reset counters, clear lock, go ACTIVE."""
        self._grace_until = time.monotonic() + self._grace_period_sec
        self._sustained_below_count = 0
        self._sustained_above_count = 0
        if self._parameter_locks is not None:
            self._parameter_locks.pop("fusion_icmp_weight", None)
        self._state = HealState.ACTIVE
        self._last_transition_ts = time.monotonic()

    @property
    def state(self) -> HealState:
        """Current healer state."""
        return self._state

    @property
    def pearson_r(self) -> float | None:
        """Current rolling Pearson correlation coefficient."""
        return self._compute_pearson()

    @property
    def window_avg(self) -> float | None:
        """Rolling Pearson r (alias for pearson_r per D-02)."""
        return self._compute_pearson()

    @property
    def is_grace_active(self) -> bool:
        """True if SIGUSR1 grace period is currently active."""
        return time.monotonic() < self._grace_until
