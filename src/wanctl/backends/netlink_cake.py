"""Netlink CAKE qdisc backend for wanctl.

Extends LinuxCakeBackend with pyroute2 netlink transport for CAKE bandwidth
changes, replacing subprocess tc fork/exec with direct netlink socket calls.
Falls back to subprocess (via super()) on any netlink failure.

Performance: Netlink tc call ~0.3ms vs subprocess tc ~3.1ms, reclaiming ~5ms
per 50ms control cycle (two directions x ~2.8ms savings each).

Requirements: NLNK-01, NLNK-02, NLNK-03, NLNK-04
Optional dependency: pyroute2>=0.9.5 (install via `pip install wanctl[netlink]`)

Config schema:
    router:
      transport: "linux-cake-netlink"
    cake_params:
      download_interface: "br-wan-dl"
      upload_interface: "br-wan-ul"
    timeouts:
      tc_command: 5.0
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from wanctl.backends.linux_cake import LinuxCakeBackend

if TYPE_CHECKING:
    from wanctl.config_base import BaseConfig

# Lazy import to avoid hard dependency.
# pyroute2 is optional -- only needed for linux-cake-netlink transport.
_pyroute2_available = False
try:
    from pyroute2 import IPRoute
    from pyroute2.netlink.exceptions import NetlinkError

    _pyroute2_available = True
except ImportError:
    IPRoute = None  # noqa: N806
    NetlinkError = OSError  # noqa: N806

# Map overhead keywords to pyroute2 kwargs.
# "docsis" is a special CAKE preset: overhead=-1 signals the kernel to use
# the built-in DOCSIS overhead table.
_OVERHEAD_KEYWORD_TO_PYROUTE2: dict[str, dict[str, Any]] = {
    "docsis": {"overhead": -1},
    "bridged-ptm": {"atm_mode": "ptm", "overhead": 22},
    "pppoe-ptm": {"atm_mode": "ptm", "overhead": 30},
    "bridged-llcsnap": {"atm_mode": "atm", "overhead": 32},
    "pppoa-vcmux": {"atm_mode": "atm", "overhead": 10},
    "pppoa-llc": {"atm_mode": "atm", "overhead": 14},
    "pppoe-vcmux": {"atm_mode": "atm", "overhead": 32},
    "pppoe-llcsnap": {"atm_mode": "atm", "overhead": 40},
    "ethernet": {"atm_mode": "noatm", "overhead": 38},
}

# Map validate_cake expected dict keys to TCA_CAKE option attribute names.
_VALIDATE_KEY_TO_TCA: dict[str, str] = {
    "diffserv": "TCA_CAKE_DIFFSERV_MODE",
    "overhead": "TCA_CAKE_OVERHEAD",
    "bandwidth": "TCA_CAKE_BASE_RATE64",
    "rtt": "TCA_CAKE_RTT",
    "memlimit": "TCA_CAKE_MEMORY",
    "split_gso": "TCA_CAKE_SPLIT_GSO",
    "ack_filter": "TCA_CAKE_ACK_FILTER",
    "ingress": "TCA_CAKE_INGRESS",
}


class NetlinkCakeBackend(LinuxCakeBackend):
    """CAKE backend using pyroute2 netlink instead of subprocess tc.

    Inherits from LinuxCakeBackend and overrides bandwidth control methods
    with netlink implementations. On any netlink failure (NetlinkError, OSError,
    ImportError), transparently falls back to the subprocess path via super().

    Singleton IPRoute instance persists across calls for daemon lifetime.
    When the netlink socket dies, the reference is nulled and re-created
    on the next call.
    """

    def __init__(
        self,
        interface: str,
        logger: logging.Logger | None = None,
        tc_timeout: float = 5.0,
    ):
        """Initialize NetlinkCakeBackend.

        Args:
            interface: Network interface name (e.g., "eth0", "br-wan-dl")
            logger: Logger instance. If None, creates a default logger.
            tc_timeout: Default timeout for subprocess tc fallback commands.
        """
        super().__init__(interface=interface, logger=logger, tc_timeout=tc_timeout)
        self._ipr: Any = None  # IPRoute | None -- Any to avoid type errors when pyroute2 absent
        self._ifindex: int | None = None

    def _get_ipr(self) -> Any:
        """Get or create singleton IPRoute connection.

        Creates IPRoute(groups=0) on first call to avoid multicast subscription
        overhead. Resolves interface index via link_lookup on each reconnection.

        Returns:
            IPRoute instance ready for tc operations.

        Raises:
            ImportError: If pyroute2 is not installed.
            OSError: If the configured interface is not found.
        """
        if not _pyroute2_available:
            raise ImportError("pyroute2 not installed")
        if self._ipr is None:
            self._ipr = IPRoute(groups=0)
            indices = self._ipr.link_lookup(ifname=self.interface)
            if not indices:
                self._ipr.close()
                self._ipr = None
                raise OSError(f"Interface {self.interface} not found")
            self._ifindex = indices[0]
        return self._ipr

    def _reset_ipr(self) -> None:
        """Close and null the IPRoute reference to force reconnect on next call."""
        if self._ipr is not None:
            try:
                self._ipr.close()
            except Exception:
                pass
        self._ipr = None

    # =========================================================================
    # Overridden methods with netlink + fallback
    # =========================================================================

    def set_bandwidth(self, queue: str, rate_bps: int) -> bool:
        """Set CAKE bandwidth via netlink. Falls back to subprocess on failure.

        Args:
            queue: Ignored for linux-cake (interface set at init). Kept for ABC compat.
            rate_bps: Bandwidth limit in bits per second.

        Returns:
            True if bandwidth was set successfully (via netlink or fallback).
        """
        rate_kbit = rate_bps // 1000
        try:
            ipr = self._get_ipr()
            ipr.tc("change", kind="cake", index=self._ifindex, bandwidth=f"{rate_kbit}kbit")
            self.logger.debug("Netlink: set %s bandwidth to %skbit", self.interface, rate_kbit)
            return True
        except (NetlinkError, OSError, ImportError) as e:
            self.logger.warning(
                "Netlink tc change failed on %s: %s -- falling back to subprocess",
                self.interface,
                e,
            )
            self._reset_ipr()
            return super().set_bandwidth(queue, rate_bps)

    def get_bandwidth(self, queue: str) -> int | None:
        """Get current CAKE bandwidth via netlink. Falls back to subprocess on failure.

        Args:
            queue: Ignored for linux-cake (interface set at init). Kept for ABC compat.

        Returns:
            Current bandwidth in bps, or None on error.
        """
        try:
            ipr = self._get_ipr()
            msgs = ipr.tc("dump", index=self._ifindex)
            for msg in msgs:
                if msg.get_attr("TCA_KIND") == "cake":
                    options = msg.get_attr("TCA_OPTIONS")
                    if options is not None:
                        rate64 = options.get_attr("TCA_CAKE_BASE_RATE64")
                        if rate64 is not None:
                            # TCA_CAKE_BASE_RATE64 is in bytes/sec, convert to bps
                            return int(rate64) * 8
            self.logger.warning("No CAKE qdisc found on %s via netlink", self.interface)
            return None
        except (NetlinkError, OSError, ImportError) as e:
            self.logger.warning(
                "Netlink tc dump failed on %s: %s -- falling back to subprocess",
                self.interface,
                e,
            )
            self._reset_ipr()
            return super().get_bandwidth(queue)

    def get_queue_stats(self, queue: str) -> dict[str, Any] | None:
        """Get CAKE qdisc statistics with per-tin parsing via netlink.

        Reads TCA_STATS2 from tc("dump") response and maps netlink attributes
        to the same dict contract as LinuxCakeBackend.get_queue_stats():
        - 5 base fields: packets, bytes, dropped, queued_packets, queued_bytes
        - 4 extended fields: memory_used, memory_limit, capacity_estimate, ecn_marked
        - tins list: per-tin dicts with 11 fields each

        Falls back to subprocess on NetlinkError/OSError/ImportError.

        Args:
            queue: Ignored for linux-cake (interface set at init). Kept for ABC compat.

        Returns:
            Stats dict with base 5 + extended 4 fields + tins list, or None on error.
        """
        try:
            ipr = self._get_ipr()
            msgs = ipr.tc("dump", index=self._ifindex)
        except (NetlinkError, OSError, ImportError) as e:
            self.logger.warning(
                "Netlink stats dump failed on %s: %s -- falling back to subprocess",
                self.interface,
                e,
            )
            self._reset_ipr()
            return super().get_queue_stats(queue)

        # Find CAKE message in dump response
        cake_msg = None
        for msg in msgs:
            if msg.get_attr("TCA_KIND") == "cake":
                cake_msg = msg
                break
        if cake_msg is None:
            self.logger.warning("No CAKE qdisc found on %s via netlink", self.interface)
            return None

        # Extract base stats from TCA_STATS2
        stats2 = cake_msg.get_attr("TCA_STATS2")
        if stats2 is None:
            self.logger.warning(
                "No TCA_STATS2 in CAKE response on %s -- falling back to subprocess",
                self.interface,
            )
            self._reset_ipr()
            return super().get_queue_stats(queue)

        basic = stats2.get_attr("TCA_STATS_BASIC") or {}
        queue_stats = stats2.get_attr("TCA_STATS_QUEUE") or {}

        # pyroute2 TCA_STATS_BASIC/QUEUE return dict-like objects
        stats: dict[str, Any] = {
            "packets": basic.get("packets", 0) if isinstance(basic, dict) else getattr(basic, "packets", 0),
            "bytes": basic.get("bytes", 0) if isinstance(basic, dict) else getattr(basic, "bytes", 0),
            "dropped": queue_stats.get("drops", 0) if isinstance(queue_stats, dict) else getattr(queue_stats, "drops", 0),
            "queued_packets": queue_stats.get("qlen", 0) if isinstance(queue_stats, dict) else getattr(queue_stats, "qlen", 0),
            "queued_bytes": queue_stats.get("backlog", 0) if isinstance(queue_stats, dict) else getattr(queue_stats, "backlog", 0),
        }

        # Extract CAKE-specific stats from TCA_STATS_APP
        app = stats2.get_attr("TCA_STATS_APP")
        if app is not None:
            stats["memory_used"] = app.get_attr("TCA_CAKE_STATS_MEMORY_USED") or 0
            stats["memory_limit"] = app.get_attr("TCA_CAKE_STATS_MEMORY_LIMIT") or 0
            stats["capacity_estimate"] = app.get_attr("TCA_CAKE_STATS_CAPACITY_ESTIMATE64") or 0
        else:
            stats["memory_used"] = 0
            stats["memory_limit"] = 0
            stats["capacity_estimate"] = 0

        # Extract per-tin stats
        tins: list[dict[str, Any]] = []
        total_ecn = 0
        if app is not None:
            tins_container = app.get_attr("TCA_CAKE_STATS_TIN_STATS")
            if tins_container is not None:
                # Iterate over tin attrs: TCA_CAKE_TIN_STATS_0, _1, _2, ...
                for i in range(8):  # up to 8 tins (diffserv4=4, besteffort=1, diffserv3=3)
                    tin = tins_container.get_attr(f"TCA_CAKE_TIN_STATS_{i}")
                    if tin is None:
                        break
                    tin_stats: dict[str, Any] = {
                        "sent_bytes": tin.get_attr("TCA_CAKE_TIN_STATS_SENT_BYTES64") or 0,
                        "sent_packets": tin.get_attr("TCA_CAKE_TIN_STATS_SENT_PACKETS") or 0,
                        "dropped_packets": tin.get_attr("TCA_CAKE_TIN_STATS_DROPPED_PACKETS") or 0,
                        "ecn_marked_packets": tin.get_attr("TCA_CAKE_TIN_STATS_ECN_MARKED_PACKETS") or 0,
                        "backlog_bytes": tin.get_attr("TCA_CAKE_TIN_STATS_BACKLOG_BYTES") or 0,
                        "peak_delay_us": tin.get_attr("TCA_CAKE_TIN_STATS_PEAK_DELAY_US") or 0,
                        "avg_delay_us": tin.get_attr("TCA_CAKE_TIN_STATS_AVG_DELAY_US") or 0,
                        "base_delay_us": tin.get_attr("TCA_CAKE_TIN_STATS_BASE_DELAY_US") or 0,
                        "sparse_flows": tin.get_attr("TCA_CAKE_TIN_STATS_SPARSE_FLOWS") or 0,
                        "bulk_flows": tin.get_attr("TCA_CAKE_TIN_STATS_BULK_FLOWS") or 0,
                        "unresponsive_flows": tin.get_attr("TCA_CAKE_TIN_STATS_UNRESPONSIVE_FLOWS") or 0,
                    }
                    total_ecn += tin_stats["ecn_marked_packets"]
                    tins.append(tin_stats)

        stats["tins"] = tins
        stats["ecn_marked"] = total_ecn
        return stats

    def initialize_cake(self, params: dict[str, Any]) -> bool:
        """Initialize CAKE qdisc via netlink tc replace. Falls back on failure.

        Maps params dict keys to pyroute2 kwargs:
        - bandwidth -> bandwidth (string like "500000kbit")
        - diffserv -> diffserv_mode
        - overhead_keyword -> expanded via _OVERHEAD_KEYWORD_TO_PYROUTE2
        - overhead (numeric) -> overhead
        - mpu -> mpu
        - memlimit -> memlimit (converted to int)
        - rtt -> rtt (string like "100ms")
        - split-gso -> split_gso=True
        - ack-filter -> ack_filter=True
        - ingress -> ingress=True

        Args:
            params: CAKE parameters dict (same format as LinuxCakeBackend).

        Returns:
            True if CAKE was initialized successfully.
        """
        try:
            ipr = self._get_ipr()
            kwargs: dict[str, Any] = {}

            if "bandwidth" in params:
                kwargs["bandwidth"] = str(params["bandwidth"])
            if "diffserv" in params:
                kwargs["diffserv_mode"] = str(params["diffserv"])
            if "overhead_keyword" in params:
                kw = str(params["overhead_keyword"])
                if kw in _OVERHEAD_KEYWORD_TO_PYROUTE2:
                    kwargs.update(_OVERHEAD_KEYWORD_TO_PYROUTE2[kw])
                else:
                    # Direct keywords like "conservative", "raw" -- fall through
                    # to subprocess since pyroute2 may not support them directly
                    return super().initialize_cake(params)
            elif "overhead" in params:
                kwargs["overhead"] = int(params["overhead"])
            if "mpu" in params:
                kwargs["mpu"] = int(params["mpu"])
            if "memlimit" in params:
                kwargs["memlimit"] = int(params["memlimit"])
            if "rtt" in params:
                kwargs["rtt"] = str(params["rtt"])

            # Boolean flags
            for tc_flag, pyroute2_kwarg in [
                ("split-gso", "split_gso"),
                ("ack-filter", "ack_filter"),
                ("ingress", "ingress"),
            ]:
                if params.get(tc_flag):
                    kwargs[pyroute2_kwarg] = True

            ipr.tc("replace", kind="cake", index=self._ifindex, **kwargs)
            self.logger.info(
                "Netlink: initialized CAKE on %s: %s",
                self.interface,
                kwargs,
            )
            return True
        except (NetlinkError, OSError, ImportError, ValueError, TypeError) as e:
            self.logger.warning(
                "Netlink tc replace failed on %s: %s -- falling back to subprocess",
                self.interface,
                e,
            )
            self._reset_ipr()
            return super().initialize_cake(params)

    def validate_cake(self, expected: dict[str, Any]) -> bool:
        """Validate CAKE parameters by reading back via netlink.

        Compares options from netlink tc dump against expected values using
        the TCA attribute name mapping.

        Args:
            expected: Dict of parameter names to expected values.

        Returns:
            True if all expected parameters match, False on any mismatch.
        """
        try:
            ipr = self._get_ipr()
            msgs = ipr.tc("dump", index=self._ifindex)
            for msg in msgs:
                if msg.get_attr("TCA_KIND") == "cake":
                    options = msg.get_attr("TCA_OPTIONS")
                    if options is None:
                        self.logger.error("No CAKE options found on %s", self.interface)
                        return False
                    all_match = True
                    for key, expected_value in expected.items():
                        tca_key = _VALIDATE_KEY_TO_TCA.get(key)
                        if tca_key is not None:
                            actual = options.get_attr(tca_key)
                        else:
                            actual = options.get_attr(key)
                        if actual != expected_value:
                            self.logger.error(
                                "CAKE param mismatch on %s: %s expected=%r actual=%r",
                                self.interface,
                                key,
                                expected_value,
                                actual,
                            )
                            all_match = False
                    return all_match
            self.logger.error("No CAKE qdisc found on %s during validation", self.interface)
            return False
        except (NetlinkError, OSError, ImportError) as e:
            self.logger.warning(
                "Netlink validate failed on %s: %s -- falling back to subprocess",
                self.interface,
                e,
            )
            self._reset_ipr()
            return super().validate_cake(expected)

    def test_connection(self) -> bool:
        """Test connectivity by checking interface and CAKE qdisc via netlink.

        Returns:
            True if interface exists and CAKE qdisc is present.
        """
        try:
            ipr = self._get_ipr()
            msgs = ipr.tc("dump", index=self._ifindex)
            for msg in msgs:
                if msg.get_attr("TCA_KIND") == "cake":
                    return True
            self.logger.error("No CAKE qdisc found on %s via netlink", self.interface)
            return False
        except (NetlinkError, OSError, ImportError) as e:
            self.logger.warning(
                "Netlink test_connection failed on %s: %s -- falling back to subprocess",
                self.interface,
                e,
            )
            self._reset_ipr()
            return super().test_connection()

    def close(self) -> None:
        """Release IPRoute resources.

        Safe to call when no IPRoute exists (no-op).
        """
        if self._ipr is not None:
            try:
                self._ipr.close()
            except Exception:
                pass
            self._ipr = None

    @classmethod
    def from_config(cls, config: BaseConfig, direction: str = "download") -> NetlinkCakeBackend:
        """Create NetlinkCakeBackend from config object.

        Same logic as LinuxCakeBackend.from_config but returns NetlinkCakeBackend.

        Args:
            config: Configuration object with .data dict containing cake_params.
            direction: "download" or "upload" -- determines which interface to use.

        Returns:
            Configured NetlinkCakeBackend instance.

        Raises:
            ValueError: If the required interface field is missing or empty.
        """
        cake_params = config.data.get("cake_params", {})
        interface_key = f"{direction}_interface"
        interface = cake_params.get(interface_key, "")
        if not interface:
            raise ValueError(f"cake_params.{interface_key} required for linux-cake-netlink transport")
        tc_timeout = config.data.get("timeouts", {}).get("tc_command", 5.0)
        return cls(interface=interface, tc_timeout=tc_timeout)
