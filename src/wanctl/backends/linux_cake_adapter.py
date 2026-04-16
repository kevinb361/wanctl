"""Adapter bridging LinuxCakeBackend to the daemon's RouterOS-style set_limits() API.

The daemon's WANController calls ``router.set_limits(wan, down_bps, up_bps)`` which
sends both download and upload rates in a single call.  LinuxCakeBackend controls one
NIC per instance via ``set_bandwidth(queue, rate_bps)``.

LinuxCakeAdapter wraps *two* LinuxCakeBackend instances (download + upload) and
exposes the same ``set_limits()`` signature so WANController works unchanged.

On construction the adapter:
1. Creates download and upload LinuxCakeBackend instances from config
2. Calls initialize_cake() on each to create CAKE qdiscs via tc qdisc replace
3. Validates CAKE params via readback

Usage in daemon (ContinuousAutoRate.__init__):
    if config.router_transport == "linux-cake":
        router = LinuxCakeAdapter.from_config(config, logger)
    else:
        router = RouterOS(config, logger)
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from wanctl.backends.linux_cake import LinuxCakeBackend
from wanctl.cake_params import build_cake_params, build_expected_readback

if TYPE_CHECKING:
    from wanctl.config_base import BaseConfig


def _make_backend(config: BaseConfig, direction: str) -> LinuxCakeBackend:
    """Create the appropriate backend based on transport config."""
    if config.router_transport == "linux-cake-netlink":
        from wanctl.backends.netlink_cake import NetlinkCakeBackend
        return NetlinkCakeBackend.from_config(config, direction=direction)
    return LinuxCakeBackend.from_config(config, direction=direction)


class LinuxCakeAdapter:
    """Adapts two LinuxCakeBackend instances to the RouterOS set_limits() interface.

    The daemon's WANController only calls set_limits(wan, down_bps, up_bps).
    This adapter translates that into per-interface set_bandwidth() calls.
    Works with both LinuxCakeBackend (subprocess) and NetlinkCakeBackend (pyroute2).
    """

    def __init__(
        self,
        dl_backend: LinuxCakeBackend,
        ul_backend: LinuxCakeBackend,
        logger: logging.Logger,
        last_set_down_bps: int | None = None,
        last_set_up_bps: int | None = None,
        dl_increase_coalesce_bps: int = 0,
        ul_increase_coalesce_bps: int = 0,
        increase_coalesce_window_sec: float = 0.0,
    ):
        self.dl_backend = dl_backend
        self.ul_backend = ul_backend
        self.logger = logger
        self._last_set_down_bps = last_set_down_bps
        self._last_set_up_bps = last_set_up_bps
        self._dl_increase_coalesce_bps = max(0, int(dl_increase_coalesce_bps))
        self._ul_increase_coalesce_bps = max(0, int(ul_increase_coalesce_bps))
        self._increase_coalesce_window_sec = max(0.0, float(increase_coalesce_window_sec))
        self._last_dl_write_ts: float | None = None
        self._last_ul_write_ts: float | None = None
        self._last_set_limits_stats: dict[str, float] = {
            "autorate_router_write_download": 0.0,
            "autorate_router_write_upload": 0.0,
            "autorate_router_write_skipped": 0.0,
            "autorate_router_write_fallback": 0.0,
        }

    @property
    def needs_rate_limiting(self) -> bool:
        """linux-cake adapter always wraps kernel backends -- no rate limiting."""
        return False

    @property
    def rate_limit_params(self) -> dict[str, int]:
        """No rate limit params needed for linux-cake."""
        return {}

    def get_last_applied_limits(self) -> tuple[int | None, int | None]:
        """Return the most recent rates actually applied to the kernel."""
        return self._last_set_down_bps, self._last_set_up_bps

    def _should_coalesce_increase(
        self,
        requested_bps: int,
        last_applied_bps: int | None,
        last_write_ts: float | None,
        threshold_bps: int,
        now: float,
    ) -> bool:
        """Return True when a small upward nudge should wait for the next cycle."""
        if (
            last_applied_bps is None
            or requested_bps <= last_applied_bps
            or threshold_bps <= 0
            or self._increase_coalesce_window_sec <= 0.0
            or last_write_ts is None
        ):
            return False
        delta_bps = requested_bps - last_applied_bps
        if delta_bps > threshold_bps:
            return False
        return (now - last_write_ts) < self._increase_coalesce_window_sec

    def set_limits(self, wan: str, down_bps: int, up_bps: int) -> bool:
        """Set CAKE bandwidth on both download and upload interfaces.

        Matches RouterOS.set_limits() signature so WANController needs no changes.

        Args:
            wan: WAN name (for logging only)
            down_bps: Download bandwidth in bits per second
            up_bps: Upload bandwidth in bits per second

        Returns:
            True if both set_bandwidth() calls succeeded, False if either failed.
        """
        now = time.monotonic()
        dl_changed = down_bps != self._last_set_down_bps
        ul_changed = up_bps != self._last_set_up_bps

        self._last_set_limits_stats = {
            "autorate_router_write_download": 0.0,
            "autorate_router_write_upload": 0.0,
            "autorate_router_write_skipped": 0.0,
            "autorate_router_write_fallback": 0.0,
        }
        dl_ok = True
        ul_ok = True

        if dl_changed:
            if self._should_coalesce_increase(
                requested_bps=down_bps,
                last_applied_bps=self._last_set_down_bps,
                last_write_ts=self._last_dl_write_ts,
                threshold_bps=self._dl_increase_coalesce_bps,
                now=now,
            ):
                self._last_set_limits_stats["autorate_router_write_skipped"] += 0.0
                self.logger.debug(
                    "%s: Coalescing small download increase on %s (%s -> %sbps)",
                    wan,
                    self.dl_backend.interface,
                    self._last_set_down_bps,
                    down_bps,
                )
            else:
                start = time.perf_counter()
                dl_ok = self.dl_backend.set_bandwidth(queue="", rate_bps=down_bps)
                elapsed_ms = getattr(
                    self.dl_backend,
                    "_last_write_elapsed_ms",
                    (time.perf_counter() - start) * 1000.0,
                )
                if getattr(self.dl_backend, "_last_write_used_fallback", False):
                    self._last_set_limits_stats["autorate_router_write_fallback"] += elapsed_ms
                elif getattr(self.dl_backend, "_last_write_skipped", False):
                    self._last_set_limits_stats["autorate_router_write_skipped"] += elapsed_ms
                else:
                    self._last_set_limits_stats["autorate_router_write_download"] += elapsed_ms
                if dl_ok:
                    self._last_set_down_bps = down_bps
                    self._last_dl_write_ts = now

        if ul_changed:
            if self._should_coalesce_increase(
                requested_bps=up_bps,
                last_applied_bps=self._last_set_up_bps,
                last_write_ts=self._last_ul_write_ts,
                threshold_bps=self._ul_increase_coalesce_bps,
                now=now,
            ):
                self._last_set_limits_stats["autorate_router_write_skipped"] += 0.0
                self.logger.debug(
                    "%s: Coalescing small upload increase on %s (%s -> %sbps)",
                    wan,
                    self.ul_backend.interface,
                    self._last_set_up_bps,
                    up_bps,
                )
            else:
                start = time.perf_counter()
                ul_ok = self.ul_backend.set_bandwidth(queue="", rate_bps=up_bps)
                elapsed_ms = getattr(
                    self.ul_backend,
                    "_last_write_elapsed_ms",
                    (time.perf_counter() - start) * 1000.0,
                )
                if getattr(self.ul_backend, "_last_write_used_fallback", False):
                    self._last_set_limits_stats["autorate_router_write_fallback"] += elapsed_ms
                elif getattr(self.ul_backend, "_last_write_skipped", False):
                    self._last_set_limits_stats["autorate_router_write_skipped"] += elapsed_ms
                else:
                    self._last_set_limits_stats["autorate_router_write_upload"] += elapsed_ms
                if ul_ok:
                    self._last_set_up_bps = up_bps
                    self._last_ul_write_ts = now

        if not dl_ok:
            self.logger.error(
                "%s: Failed to set download bandwidth on %s", wan, self.dl_backend.interface
            )
        if not ul_ok:
            self.logger.error(
                "%s: Failed to set upload bandwidth on %s", wan, self.ul_backend.interface
            )

        return dl_ok and ul_ok

    def consume_last_set_limits_stats(self) -> dict[str, float]:
        """Return and clear the most recent per-direction write timings."""
        stats = dict(self._last_set_limits_stats)
        self._last_set_limits_stats = {key: 0.0 for key in stats}
        return stats

    def get_both_queue_stats(self) -> tuple[dict | None, dict | None]:
        """Read CAKE stats for both DL and UL in a single netlink dump.

        When both backends are NetlinkCakeBackend, issues one tc("dump")
        without an interface filter and parses both interfaces from the
        response — saving one netlink round-trip per cycle.

        Falls back to two separate get_queue_stats calls for subprocess backends.

        Returns:
            (dl_stats, ul_stats) tuple.
        """
        from wanctl.backends.netlink_cake import NetlinkCakeBackend

        if not (isinstance(self.dl_backend, NetlinkCakeBackend)
                and isinstance(self.ul_backend, NetlinkCakeBackend)):
            return (
                self.dl_backend.get_queue_stats(""),
                self.ul_backend.get_queue_stats(""),
            )

        try:
            ipr = self.dl_backend._get_ipr()
            msgs = ipr.tc("dump")
        except Exception:
            return (
                self.dl_backend.get_queue_stats(""),
                self.ul_backend.get_queue_stats(""),
            )

        dl_stats = self.dl_backend._parse_cake_msg(msgs)
        ul_stats = self.ul_backend._parse_cake_msg(msgs)
        return dl_stats, ul_stats

    @classmethod
    def from_config(cls, config: BaseConfig, logger: logging.Logger) -> LinuxCakeAdapter:
        """Create LinuxCakeAdapter from config, initializing CAKE qdiscs.

        Steps:
        1. Create download and upload LinuxCakeBackend instances
        2. Build CAKE params (direction-aware defaults + config overrides)
        3. Call initialize_cake() on each interface (tc qdisc replace)
        4. Validate CAKE params via readback

        Args:
            config: Config object with .data dict containing cake_params section
            logger: Logger instance

        Returns:
            Configured LinuxCakeAdapter with CAKE initialized on both interfaces.

        Raises:
            RuntimeError: If CAKE initialization fails on either interface.
        """
        dl_backend = _make_backend(config, direction="download")
        dl_backend.logger = logger

        ul_backend = _make_backend(config, direction="upload")
        ul_backend.logger = logger

        cake_config = config.data.get("cake_params", {})
        initial_rates_bps: dict[str, int] = {}

        # Build direction-aware params and initialize CAKE on each interface
        for direction, backend in [("download", dl_backend), ("upload", ul_backend)]:
            # Initial bandwidth from config ceiling (CAKE needs a starting bandwidth)
            if direction == "download":
                cm = config.data.get("continuous_monitoring", {})
                ceiling_mbps = cm.get("download", {}).get("ceiling_mbps", 500)
                initial_bw_kbit = int(ceiling_mbps * 1000)
            else:
                cm = config.data.get("continuous_monitoring", {})
                ceiling_mbps = cm.get("upload", {}).get("ceiling_mbps", 40)
                initial_bw_kbit = int(ceiling_mbps * 1000)
            initial_rates_bps[direction] = initial_bw_kbit * 1000

            params = build_cake_params(
                direction=direction,
                cake_config=cake_config,
                bandwidth_kbit=initial_bw_kbit,
            )

            logger.info(
                "Initializing CAKE on %s (%s): %s",
                backend.interface,
                direction,
                params,
            )

            if not backend.initialize_cake(params):
                raise RuntimeError(
                    f"Failed to initialize CAKE on {backend.interface} ({direction})"
                )

            # Validate readback (BACK-03)
            expected = build_expected_readback(params)
            if expected and not backend.validate_cake(expected):
                logger.warning(
                    "CAKE readback validation failed on %s (%s) -- continuing anyway",
                    backend.interface,
                    direction,
                )

        logger.info(
            "LinuxCakeAdapter ready: download=%s, upload=%s",
            dl_backend.interface,
            ul_backend.interface,
        )

        return cls(
            dl_backend=dl_backend,
            ul_backend=ul_backend,
            logger=logger,
            last_set_down_bps=initial_rates_bps["download"],
            last_set_up_bps=initial_rates_bps["upload"],
            dl_increase_coalesce_bps=int(
                config.data.get("continuous_monitoring", {})
                .get("download", {})
                .get("step_up_mbps", 0)
                * 1_000_000
            ),
            ul_increase_coalesce_bps=int(
                config.data.get("continuous_monitoring", {})
                .get("upload", {})
                .get("step_up_mbps", 0)
                * 1_000_000
            ),
            increase_coalesce_window_sec=0.2,
        )
