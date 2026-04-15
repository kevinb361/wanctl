"""Reflector quality scoring for RTT measurement hosts.

Provides rolling quality scoring, deprioritization, periodic probing,
and recovery logic for ICMP ping reflectors. Deprioritized reflectors
are excluded from active measurement but receive periodic probe pings
to detect recovery.

Components:
    ReflectorStatus: Frozen dataclass with per-host quality snapshot
    ReflectorScorer: Stateful scorer with rolling windows, probe scheduling,
        and event draining for persistence

Signal flow:
    record_result(host, success) -> updates per-host deque, checks thresholds
    record_results(results) -> batch wrapper applying host results in order
    get_active_hosts() -> returns non-deprioritized hosts (or best-scoring fallback)
    maybe_probe(now, rtt_measurement) -> probes one deprioritized host if interval elapsed
    drain_events() -> returns buffered transition events for SQLite persistence

Args pattern:
    ReflectorScorer is instantiated per-WAN in WANController with config dict
    extracted from the reflector_quality YAML section.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wanctl.rtt_measurement import RTTMeasurement


@dataclass(frozen=True, slots=True)
class ReflectorStatus:
    """Per-host quality snapshot returned by ReflectorScorer.get_all_statuses().

    Attributes:
        host: Reflector IP or hostname.
        score: 0.0-1.0 success rate over the rolling window.
        status: "active" or "deprioritized".
        measurements: Number of results recorded (may be < window_size during warmup).
        consecutive_successes: Recovery counter for deprioritized hosts.
    """

    host: str
    score: float
    status: str
    measurements: int
    consecutive_successes: int


class ReflectorScorer:
    """Rolling quality scorer for RTT measurement reflectors.

    Tracks per-host success rate over a count-based window. Hosts that drop
    below min_score after warmup are deprioritized and excluded from active
    measurement. Deprioritized hosts receive periodic probe pings and recover
    after N consecutive successes.

    Transition events (deprioritization, recovery) are buffered in
    _pending_events and drained via drain_events() for SQLite persistence.

    Args:
        hosts: List of reflector IPs/hostnames.
        min_score: Minimum score threshold for active status (0.0-1.0).
        window_size: Rolling window size for success rate calculation.
        probe_interval_sec: Minimum seconds between probes for a deprioritized host.
        recovery_count: Consecutive successes needed to recover a deprioritized host.
        logger: Logger instance (defaults to module logger).
        wan_name: WAN identifier for log messages.
    """

    def __init__(
        self,
        hosts: list[str],
        min_score: float = 0.8,
        window_size: int = 50,
        probe_interval_sec: float = 30.0,
        recovery_count: int = 3,
        logger: logging.Logger | None = None,
        wan_name: str = "",
    ) -> None:
        self._hosts: list[str] = list(hosts)
        self._min_score: float = min_score
        self._window_size: int = window_size
        self._probe_interval_sec: float = probe_interval_sec
        self._recovery_count: int = recovery_count
        self._logger: logging.Logger = logger or logging.getLogger(__name__)
        self._wan_name: str = wan_name

        # Per-host rolling windows of bool success/failure
        self._windows: dict[str, deque[bool]] = {h: deque(maxlen=window_size) for h in hosts}
        # Cached rolling success counts to avoid repeated deque summation
        self._success_counts: dict[str, int] = {h: 0 for h in hosts}
        # Recovery counter per host
        self._consecutive_successes: dict[str, int] = {h: 0 for h in hosts}
        # Set of deprioritized host strings
        self._deprioritized: set[str] = set()
        # Monotonic timestamps of last probe per host
        self._last_probe_time: dict[str, float] = {}
        # Round-robin index for deprioritized host probing
        self._probe_index: int = 0
        # Buffered transition events for persistence
        self._pending_events: list[dict] = []

    # =========================================================================
    # PUBLIC FACADE API
    # =========================================================================

    @property
    def min_score(self) -> float:
        """Minimum score threshold for reflector selection."""
        return self._min_score

    @min_score.setter
    def min_score(self, value: float) -> None:
        self._min_score = value

    def record_result(self, host: str, success: bool) -> None:
        """Record a ping result and check for state transitions.

        Appends success/failure to the host's rolling window, recalculates
        score, and checks for deprioritization or recovery transitions.

        Args:
            host: Reflector IP/hostname.
            success: True if ping succeeded, False if failed/timed out.
        """
        self._record_result(host, success)

    def record_results(self, results: dict[str, bool]) -> None:
        """Record a batch of ping results in input order.

        This preserves the existing per-host transition semantics while
        reducing Python call overhead in the controller hot path.

        Args:
            results: Mapping of host -> success flag.
        """
        for host, success in results.items():
            self._record_result(host, success)

    def _record_result(self, host: str, success: bool) -> None:
        """Shared single-result implementation for record APIs."""
        window = self._windows[host]
        if len(window) == window.maxlen and window[0]:
            self._success_counts[host] -= 1
        window.append(success)
        if success:
            self._success_counts[host] += 1

        score = self._score_for_host(host)

        if host not in self._deprioritized:
            # Check for deprioritization (warmup guard: need >= 10 measurements)
            if score < self._min_score and len(window) >= 10:
                self._deprioritized.add(host)
                self._logger.warning(
                    f"{self._wan_name}: Reflector {host} deprioritized "
                    f"(score={score:.3f} < {self._min_score})"
                )
                self._pending_events.append(
                    {"event_type": "deprioritized", "host": host, "score": score}
                )
        else:
            # Track consecutive successes for recovery
            if success:
                self._consecutive_successes[host] += 1
            else:
                self._consecutive_successes[host] = 0

            # Check for recovery
            if self._consecutive_successes[host] >= self._recovery_count:
                # Re-qualify recovered hosts on fresh evidence instead of stale
                # failures in the old rolling window. This prevents immediate
                # recover/deprioritize flapping after a probe streak.
                self._windows[host] = deque([True] * self._recovery_count, maxlen=self._window_size)
                self._success_counts[host] = self._recovery_count
                self._deprioritized.discard(host)
                self._consecutive_successes[host] = 0
                self._logger.info(
                    f"{self._wan_name}: Reflector {host} recovered "
                    f"(score reset on {self._recovery_count} successful probes)"
                )
                self._pending_events.append(
                    {
                        "event_type": "recovered",
                        "host": host,
                        "score": 1.0,
                    }
                )

    def has_pending_events(self) -> bool:
        """Whether there are transition events waiting to be persisted."""
        return bool(self._pending_events)

    def _score_for_host(self, host: str) -> float:
        """Return cached rolling score for a host."""
        measurement_count = len(self._windows[host])
        if measurement_count == 0:
            return 1.0
        return self._success_counts[host] / measurement_count

    def drain_events(self) -> list[dict]:
        """Return and clear buffered transition events.

        Returns:
            List of event dicts with keys: event_type, host, score.
            Empty list if no transitions occurred since last drain.
        """
        events = self._pending_events
        self._pending_events = []
        return events

    def get_active_hosts(self) -> list[str]:
        """Return list of non-deprioritized hosts.

        When all hosts are deprioritized, returns a single-element list
        with the best-scoring host and logs a WARNING.

        Returns:
            List of active host strings.
        """
        active = [h for h in self._hosts if h not in self._deprioritized]
        if not active:
            best = self.get_best_host()
            self._logger.warning(
                f"{self._wan_name}: All reflectors deprioritized, forcing best-scoring {best}"
            )
            return [best]
        return active

    def get_best_host(self) -> str:
        """Return the host with the highest score.

        Ties are broken by host order in the original list.
        If no measurements yet, returns the first host.

        Returns:
            Host string with the highest quality score.
        """
        best_host = self._hosts[0]
        best_score = -1.0

        for h in self._hosts:
            score = self._score_for_host(h)
            if score > best_score:
                best_score = score
                best_host = h

        return best_host

    def get_all_statuses(self) -> list[ReflectorStatus]:
        """Return quality status for all hosts.

        Returns:
            List of ReflectorStatus frozen dataclasses, one per host.
        """
        statuses: list[ReflectorStatus] = []
        for h in self._hosts:
            window = self._windows[h]
            score = self._score_for_host(h)
            statuses.append(
                ReflectorStatus(
                    host=h,
                    score=score,
                    status="deprioritized" if h in self._deprioritized else "active",
                    measurements=len(window),
                    consecutive_successes=self._consecutive_successes[h],
                )
            )
        return statuses

    def maybe_probe(self, now: float, rtt_measurement: RTTMeasurement) -> list[tuple[str, bool]]:
        """Probe one deprioritized host if probe interval has elapsed.

        Probes a single deprioritized host via round-robin to avoid
        cycle budget overrun. Records the result and checks for recovery.

        Args:
            now: Current monotonic time in seconds.
            rtt_measurement: RTTMeasurement instance for probe pings.

        Returns:
            List of (host, success) tuples. Empty if no probe was due.
            At most one element (one host probed per call).
        """
        deprioritized_list = [h for h in self._hosts if h in self._deprioritized]
        if not deprioritized_list:
            return []

        # Round-robin selection
        host = deprioritized_list[self._probe_index % len(deprioritized_list)]

        # Check interval
        if now - self._last_probe_time.get(host, 0) < self._probe_interval_sec:
            return []

        # Perform probe
        result = rtt_measurement.ping_host(host, count=1)
        success = result is not None

        # Record result (updates score, checks recovery)
        self.record_result(host, success)

        # Update probe tracking
        self._last_probe_time[host] = now
        self._probe_index += 1

        return [(host, success)]
