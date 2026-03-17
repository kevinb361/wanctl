"""IRTT (Isochronous Round-Trip Tester) subprocess wrapper.

Wraps the ``irtt`` binary as a subprocess, parsing JSON output into a frozen
:class:`IRTTResult` dataclass.  All failure modes (binary missing, timeout,
parse error, server unreachable) return ``None`` so the caller never needs
conditional error handling.

The class is always instantiated -- even when disabled -- and
:meth:`measure` returns ``None`` immediately for the no-op case.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IRTTResult:
    """Result from a single IRTT measurement burst.

    All RTT / IPDV fields are in **milliseconds** (converted from IRTT's
    native nanosecond representation).
    """

    rtt_mean_ms: float
    rtt_median_ms: float
    ipdv_mean_ms: float
    send_loss: float  # upstream_loss_percent from IRTT JSON
    receive_loss: float  # downstream_loss_percent from IRTT JSON
    packets_sent: int
    packets_received: int
    server: str
    port: int
    timestamp: float  # time.monotonic()
    success: bool
    send_delay_median_ms: float = 0.0  # stats.send_delay.median / NS_TO_MS
    receive_delay_median_ms: float = 0.0  # stats.receive_delay.median / NS_TO_MS


class IRTTMeasurement:
    """Invoke the ``irtt`` binary and parse its JSON stats output.

    Args:
        config: Dict with keys ``enabled``, ``server``, ``port``,
            ``duration_sec``, ``interval_ms``.
        logger: Logger instance for failure / recovery messages.
    """

    def __init__(self, config: dict, logger: logging.Logger) -> None:
        self._enabled: bool = config.get("enabled", False)
        self._server: str | None = config.get("server")
        self._port: int = config.get("port", 2112)
        self._duration_sec: float = float(config.get("duration_sec", 1.0))
        self._interval_ms: int = config.get("interval_ms", 100)
        self._timeout: float = self._duration_sec + 5  # Grace period
        self._binary_path: str | None = shutil.which("irtt")
        self._logger = logger

        # Failure tracking for log-level management.
        self._consecutive_failures: int = 0
        self._first_failure_logged: bool = False

        if self._binary_path is None:
            self._logger.warning("IRTT binary not found. Install with: sudo apt install -y irtt")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Return whether IRTT measurements can be performed."""
        return bool(self._binary_path and self._enabled and self._server)

    def measure(self) -> IRTTResult | None:
        """Run a single IRTT burst and return the parsed result.

        Returns ``None`` on any failure (binary missing, disabled, timeout,
        unparseable output, missing stats key).
        """
        if not self.is_available():
            return None

        try:
            cmd = self._build_command()
            result = subprocess.run(  # noqa: S603 -- hardcoded irtt invocation
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
            # Try JSON parsing even on non-zero exit (Pitfall 4: IRTT returns
            # non-zero on 100 % packet loss but stdout may still be valid).
            parsed = self._parse_json(result.stdout)
            if parsed is not None:
                # Recovery logging.
                if self._consecutive_failures > 0:
                    self._logger.info(
                        f"IRTT recovered after {self._consecutive_failures} consecutive failures"
                    )
                    self._consecutive_failures = 0
                    self._first_failure_logged = False
                return parsed

            self._log_failure("empty or unparseable JSON output")
            return None

        except subprocess.TimeoutExpired:
            self._log_failure(f"subprocess timed out after {self._timeout}s")
            return None
        except Exception as exc:
            self._log_failure(str(exc))
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_command(self) -> list[str]:
        """Build the ``irtt client`` command line."""
        return [
            "irtt",
            "client",
            "-o",
            "-",  # JSON output to stdout
            "-Q",  # Really quiet (suppress text, JSON only)
            "-d",
            f"{self._duration_sec}s",  # Go duration format
            "-i",
            f"{self._interval_ms}ms",  # Go duration format
            "-l",
            "48",  # 48-byte payload (hardcoded)
            f"{self._server}:{self._port}",  # server:port positional arg
        ]

    def _parse_json(self, raw_json: str) -> IRTTResult | None:
        """Parse IRTT JSON output into an :class:`IRTTResult`.

        Returns ``None`` on any parse or extraction error.
        """
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            return None

        stats = data.get("stats")
        if not stats:
            return None

        # IRTT reports all durations in nanoseconds.
        NS_TO_MS = 1_000_000

        rtt = stats.get("rtt", {})
        ipdv_rt = stats.get("ipdv_round_trip", {})
        send_delay = stats.get("send_delay", {})
        receive_delay = stats.get("receive_delay", {})

        return IRTTResult(
            rtt_mean_ms=rtt.get("mean", 0) / NS_TO_MS,
            rtt_median_ms=rtt.get("median", 0) / NS_TO_MS,
            ipdv_mean_ms=ipdv_rt.get("mean", 0) / NS_TO_MS,
            send_loss=stats.get("upstream_loss_percent", 0.0),
            receive_loss=stats.get("downstream_loss_percent", 0.0),
            packets_sent=stats.get("packets_sent", 0),
            packets_received=stats.get("packets_received", 0),
            server=self._server,  # type: ignore[arg-type]
            port=self._port,
            timestamp=time.monotonic(),
            success=True,
            send_delay_median_ms=send_delay.get("median", 0) / NS_TO_MS,
            receive_delay_median_ms=receive_delay.get("median", 0) / NS_TO_MS,
        )

    def _log_failure(self, reason: str) -> None:
        """Log a measurement failure, managing log level to avoid spam.

        First failure is logged at WARNING; subsequent identical failures
        at DEBUG.  Recovery (in :meth:`measure`) logs at INFO.
        """
        if not self._first_failure_logged:
            self._logger.warning(f"IRTT measurement failed: {reason}")
            self._first_failure_logged = True
        else:
            self._logger.debug(f"IRTT measurement failed: {reason}")
        self._consecutive_failures += 1
