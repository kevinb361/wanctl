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
    ):
        self.dl_backend = dl_backend
        self.ul_backend = ul_backend
        self.logger = logger

    @property
    def needs_rate_limiting(self) -> bool:
        """linux-cake adapter always wraps kernel backends -- no rate limiting."""
        return False

    @property
    def rate_limit_params(self) -> dict[str, int]:
        """No rate limit params needed for linux-cake."""
        return {}

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
        dl_ok = self.dl_backend.set_bandwidth(queue="", rate_bps=down_bps)
        ul_ok = self.ul_backend.set_bandwidth(queue="", rate_bps=up_bps)

        if not dl_ok:
            self.logger.error(
                "%s: Failed to set download bandwidth on %s", wan, self.dl_backend.interface
            )
        if not ul_ok:
            self.logger.error(
                "%s: Failed to set upload bandwidth on %s", wan, self.ul_backend.interface
            )

        return dl_ok and ul_ok

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

        return cls(dl_backend=dl_backend, ul_backend=ul_backend, logger=logger)
