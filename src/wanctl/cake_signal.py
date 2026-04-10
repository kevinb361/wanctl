"""CAKE qdisc signal processing for secondary congestion detection.

Processes raw CAKE netlink statistics (drops, backlog, peak delay) into
smoothed signals via EWMA. These signals augment the primary RTT-based
congestion detection with queue-level observability.

Signal flow:
    NetlinkCakeBackend.get_queue_stats() -> raw dict
        -> CakeSignalProcessor.update() -> CakeSignalSnapshot
            -> stored on WANController._dl_cake_snapshot / _ul_cake_snapshot
            -> exposed via get_health_data() for monitoring

Per-tin separation:
    Active drop rate (drop_rate) excludes Bulk tin (index 0) because Bulk
    traffic is intentionally deprioritised by CAKE's diffserv4 and its drops
    are expected under load. Total drop rate (total_drop_rate) includes all
    tins for completeness.

u32 counter handling:
    CAKE kernel counters are unsigned 32-bit integers that wrap at 2^32-1.
    u32_delta() handles wrap-around and includes a sanity guard against
    impossible deltas (> 1M drops in a single 50ms cycle).

Requirements: CAKE-01, CAKE-02, CAKE-03
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Unsigned 32-bit max for counter wrapping.
U32_MAX = 0xFFFFFFFF

# Production cycle interval (50ms = 20Hz).
CYCLE_INTERVAL_SECONDS = 0.05

# Sanity guard: > 1M drops in a single 50ms cycle is impossible.
SANITY_MAX_DELTA = 1_000_000


def u32_delta(current: int, previous: int) -> int:
    """Compute delta between two u32 counters, handling wrap-around.

    Returns 0 if the computed delta exceeds SANITY_MAX_DELTA, treating
    it as a wrap artifact rather than a real drop spike.

    Args:
        current: Current counter value.
        previous: Previous counter value.

    Returns:
        Non-negative delta, or 0 if sanity guard triggers.
    """
    if current >= previous:
        delta = current - previous
    else:
        # Wrap-around: distance from previous to U32_MAX, plus current, plus 1
        delta = (U32_MAX - previous) + current + 1
    if delta > SANITY_MAX_DELTA:
        return 0
    return delta


@dataclass(frozen=True, slots=True)
class TinSnapshot:
    """Immutable per-tin statistics snapshot for one cycle.

    Attributes:
        name: Tin name (Bulk, BestEffort, Video, Voice).
        dropped_packets: Raw cumulative counter from kernel.
        drop_delta: Delta since last read (computed by u32_delta).
        backlog_bytes: Current queue backlog in bytes.
        peak_delay_us: Peak sojourn delay in microseconds.
        ecn_marked_packets: Cumulative ECN CE-marked packets.
    """

    name: str
    dropped_packets: int
    drop_delta: int
    backlog_bytes: int
    peak_delay_us: int
    ecn_marked_packets: int


@dataclass(frozen=True, slots=True)
class CakeSignalSnapshot:
    """Immutable snapshot of processed CAKE signals for one cycle.

    Safe to pass across threads (e.g., to health endpoint handler).

    Attributes:
        drop_rate: EWMA drops/sec for BestEffort+Video+Voice tins (excludes Bulk).
        total_drop_rate: EWMA drops/sec for all tins including Bulk.
        backlog_bytes: Sum of BestEffort+Video+Voice backlog bytes.
        peak_delay_us: Max peak_delay across BestEffort+Video+Voice tins.
        tins: Per-tin snapshots (tuple for immutability).
        cold_start: True on first update (delta not yet available).
    """

    drop_rate: float
    total_drop_rate: float
    backlog_bytes: int
    peak_delay_us: int
    tins: tuple[TinSnapshot, ...]
    cold_start: bool


@dataclass(frozen=True, slots=True)
class CakeSignalConfig:
    """Configuration for CAKE signal processing.

    All fields default to disabled/off for safe rollout.

    Attributes:
        enabled: Master switch for CAKE signal processing.
        drop_rate_enabled: Whether drop rate signal feeds into zone logic (Phase 160).
        backlog_enabled: Whether backlog signal feeds into zone logic (Phase 160).
        peak_delay_enabled: Whether peak delay signal feeds into zone logic (Phase 160).
        metrics_enabled: Whether to emit Prometheus-style metrics (Phase 160).
        time_constant_sec: EWMA time constant in seconds. alpha = cycle_interval / tc.
        drop_rate_threshold: Drops/sec above which dwell timer is bypassed (DETECT-01).
            0.0 disables the bypass. Conservative default avoids false triggers.
        backlog_threshold_bytes: Queue backlog bytes above which green_streak is
            suppressed, preventing premature rate recovery (DETECT-02).
            0 disables suppression.
        refractory_cycles: Cycles to mask CAKE signals after a drop-triggered
            rate reduction, preventing cascading reductions (DETECT-03).
        probe_multiplier_factor: Exponential probe growth factor per recovery
            step (RECOV-01). 1.0 disables exponential growth (linear only).
        probe_ceiling_pct: Fraction of ceiling above which probing reverts to
            linear step_up (RECOV-02). E.g., 0.9 means above 90% of ceiling.
    """

    enabled: bool = False
    drop_rate_enabled: bool = False
    backlog_enabled: bool = False
    peak_delay_enabled: bool = False
    metrics_enabled: bool = False
    time_constant_sec: float = 1.0
    drop_rate_threshold: float = 10.0
    backlog_threshold_bytes: int = 10000
    refractory_cycles: int = 40
    probe_multiplier_factor: float = 1.5
    probe_ceiling_pct: float = 0.9


class CakeSignalProcessor:
    """Processes raw CAKE qdisc stats into smoothed signal snapshots.

    Maintains EWMA state for drop rates, tracks per-tin counters for
    u32 delta computation, and produces frozen CakeSignalSnapshot objects.

    Args:
        config: CakeSignalConfig controlling enabled state and EWMA smoothing.
        tin_names: Ordered tin names matching CAKE diffserv4. Defaults to
            ["Bulk", "BestEffort", "Video", "Voice"].
    """

    def __init__(
        self,
        config: CakeSignalConfig,
        tin_names: list[str] | None = None,
    ) -> None:
        self._config = config
        self._tin_names = tin_names or ["Bulk", "BestEffort", "Video", "Voice"]
        self._prev_counters: dict[int, int] | None = None  # tin_index -> dropped_packets
        self._cold_start = True
        self._drop_rate_ewma = 0.0  # Active (excludes Bulk)
        self._total_drop_rate_ewma = 0.0  # All tins
        tc = max(0.1, config.time_constant_sec) if config.time_constant_sec > 0 else 1.0
        self._alpha = CYCLE_INTERVAL_SECONDS / tc
        self._last_snapshot: CakeSignalSnapshot | None = None

    @property
    def config(self) -> CakeSignalConfig:
        """Current configuration."""
        return self._config

    @config.setter
    def config(self, value: CakeSignalConfig) -> None:
        """Update config (for SIGUSR1 reload). Recalculates alpha."""
        self._config = value
        tc = max(0.1, value.time_constant_sec) if value.time_constant_sec > 0 else 1.0
        self._alpha = CYCLE_INTERVAL_SECONDS / tc

    def update(self, raw_stats: dict[str, Any] | None) -> CakeSignalSnapshot | None:
        """Process one cycle of CAKE stats.

        Args:
            raw_stats: Return value from NetlinkCakeBackend.get_queue_stats(),
                or None if stats unavailable.

        Returns:
            CakeSignalSnapshot with smoothed signals, or None if disabled
            or stats unavailable on cold start.
        """
        if not self._config.enabled:
            return None

        if raw_stats is None:
            return self._last_snapshot

        tins_raw: list[dict[str, Any]] = raw_stats.get("tins", [])
        if not tins_raw:
            return self._last_snapshot

        # Extract current per-tin drop counters
        current_counters: dict[int, int] = {}
        for i, tin in enumerate(tins_raw):
            current_counters[i] = tin.get("dropped_packets", 0)

        # Cold start: store counters, return zero-rate snapshot
        if self._prev_counters is None:
            self._prev_counters = current_counters
            self._cold_start = True

            tin_snapshots = tuple(
                TinSnapshot(
                    name=self._tin_names[i] if i < len(self._tin_names) else f"Tin{i}",
                    dropped_packets=current_counters.get(i, 0),
                    drop_delta=0,
                    backlog_bytes=tins_raw[i].get("backlog_bytes", 0),
                    peak_delay_us=tins_raw[i].get("peak_delay_us", 0),
                    ecn_marked_packets=tins_raw[i].get("ecn_marked_packets", 0),
                )
                for i in range(len(tins_raw))
            )

            # Compute backlog and peak delay excluding Bulk (index 0)
            active_backlog = sum(
                tins_raw[i].get("backlog_bytes", 0) for i in range(1, len(tins_raw))
            )
            active_peak_delay = max(
                (tins_raw[i].get("peak_delay_us", 0) for i in range(1, len(tins_raw))),
                default=0,
            )

            snapshot = CakeSignalSnapshot(
                drop_rate=0.0,
                total_drop_rate=0.0,
                backlog_bytes=active_backlog,
                peak_delay_us=active_peak_delay,
                tins=tin_snapshots,
                cold_start=True,
            )
            self._last_snapshot = snapshot
            return snapshot

        # Compute deltas
        deltas: dict[int, int] = {}
        for i in range(len(tins_raw)):
            prev = self._prev_counters.get(i, 0)
            curr = current_counters.get(i, 0)
            deltas[i] = u32_delta(curr, prev)

        # Update previous counters for next cycle
        self._prev_counters = current_counters

        # Sum active drops (tins[1:] = BestEffort+Video+Voice)
        active_drops = sum(deltas.get(i, 0) for i in range(1, len(tins_raw)))
        total_drops = sum(deltas.get(i, 0) for i in range(len(tins_raw)))

        # Convert to drops/sec
        active_drops_per_sec = active_drops / CYCLE_INTERVAL_SECONDS
        total_drops_per_sec = total_drops / CYCLE_INTERVAL_SECONDS

        # EWMA smooth
        alpha = self._alpha
        self._drop_rate_ewma = (
            (1.0 - alpha) * self._drop_rate_ewma + alpha * active_drops_per_sec
        )
        self._total_drop_rate_ewma = (
            (1.0 - alpha) * self._total_drop_rate_ewma + alpha * total_drops_per_sec
        )

        # Build per-tin snapshots
        tin_snapshots = tuple(
            TinSnapshot(
                name=self._tin_names[i] if i < len(self._tin_names) else f"Tin{i}",
                dropped_packets=current_counters.get(i, 0),
                drop_delta=deltas.get(i, 0),
                backlog_bytes=tins_raw[i].get("backlog_bytes", 0),
                peak_delay_us=tins_raw[i].get("peak_delay_us", 0),
                ecn_marked_packets=tins_raw[i].get("ecn_marked_packets", 0),
            )
            for i in range(len(tins_raw))
        )

        # Compute backlog and peak delay excluding Bulk (index 0)
        active_backlog = sum(
            tins_raw[i].get("backlog_bytes", 0) for i in range(1, len(tins_raw))
        )
        active_peak_delay = max(
            (tins_raw[i].get("peak_delay_us", 0) for i in range(1, len(tins_raw))),
            default=0,
        )

        self._cold_start = False
        snapshot = CakeSignalSnapshot(
            drop_rate=self._drop_rate_ewma,
            total_drop_rate=self._total_drop_rate_ewma,
            backlog_bytes=active_backlog,
            peak_delay_us=active_peak_delay,
            tins=tin_snapshots,
            cold_start=False,
        )
        self._last_snapshot = snapshot
        return snapshot
