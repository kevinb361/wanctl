"""Linux CAKE qdisc backend for wanctl.

Implements the RouterBackend ABC using local tc subprocess commands to control
CAKE qdiscs on a Linux bridge VM. Handles bandwidth updates (tc qdisc change),
statistics collection (tc -j -s qdisc show), CAKE initialization (tc qdisc replace),
and parameter validation (readback verification).

Requirements: BACK-01, BACK-02, BACK-03, BACK-04
No new Python dependencies -- uses stdlib subprocess, json, shutil only.

Config schema:
    router:
      transport: "linux-cake"
    cake_params:
      download_interface: "br-wan-dl"
      upload_interface: "br-wan-ul"
    timeouts:
      tc_command: 5.0
"""

import json
import logging
import shutil
import subprocess
from typing import Any

from wanctl.backends.base import RouterBackend

# diffserv4 tin order: index 0=Bulk, 1=BestEffort, 2=Video, 3=Voice
TIN_NAMES: list[str] = ["Bulk", "BestEffort", "Video", "Voice"]

# Overhead keywords that need expansion to tc-compatible form.
# Some keywords (docsis, conservative, raw) are direct tc tokens.
# Compound keywords must be split into encapsulation flag + numeric overhead.
OVERHEAD_KEYWORD_EXPANSION: dict[str, list[str]] = {
    "bridged-ptm": ["ptm", "overhead", "22"],
    "pppoe-ptm": ["ptm", "overhead", "30"],
    "bridged-llcsnap": ["atm", "overhead", "32"],
    "pppoa-vcmux": ["atm", "overhead", "10"],
    "pppoa-llc": ["atm", "overhead", "14"],
    "pppoe-vcmux": ["atm", "overhead", "32"],
    "pppoe-llcsnap": ["atm", "overhead", "40"],
    "ethernet": ["noatm", "overhead", "38"],
}


class LinuxCakeBackend(RouterBackend):
    """Linux CAKE qdisc implementation of the router backend interface.

    Uses local tc subprocess calls to manage CAKE qdiscs for:
    - Bandwidth control via tc qdisc change (BACK-01)
    - Statistics collection with per-tin parsing via tc -j -s qdisc show (BACK-02, BACK-04)
    - CAKE initialization via tc qdisc replace (BACK-03)
    - Parameter validation via readback (BACK-03)

    Mangle rule methods are no-op stubs -- steering mangle rules stay on
    MikroTik router and are handled separately (Phase 108).
    """

    def __init__(
        self,
        interface: str,
        logger: logging.Logger | None = None,
        tc_timeout: float = 5.0,
    ):
        """Initialize LinuxCakeBackend.

        Args:
            interface: Network interface name (e.g., "eth0", "br-wan0")
            logger: Logger instance. If None, creates a default logger.
            tc_timeout: Default timeout for tc commands in seconds.
        """
        super().__init__(logger)
        self.interface = interface
        self.tc_timeout = tc_timeout

    def _run_tc(
        self, args: list[str], timeout: float | None = None
    ) -> tuple[int, str, str]:
        """Execute a tc command and return (returncode, stdout, stderr).

        Args:
            args: tc subcommand arguments (e.g., ["qdisc", "show", "dev", "eth0"])
            timeout: Command timeout in seconds. Uses self.tc_timeout if None.

        Returns:
            Tuple of (return_code, stdout, stderr).
            Returns (-1, "", "timeout") on timeout.
            Returns (-1, "", "tc not found") if tc binary is missing.
        """
        cmd = ["tc"] + args
        try:
            result = subprocess.run(  # noqa: S603 -- hardcoded tc invocation, no user input
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout or self.tc_timeout,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            self.logger.warning(
                "tc command timed out after %ss: %s",
                timeout or self.tc_timeout,
                " ".join(cmd),
            )
            return -1, "", "timeout"
        except FileNotFoundError:
            self.logger.error("tc binary not found")
            return -1, "", "tc not found"

    def _find_cake_entry(self, json_output: str) -> dict | None:
        """Find the CAKE qdisc entry in tc JSON output.

        Args:
            json_output: Raw JSON string from tc -j qdisc show.

        Returns:
            The CAKE entry dict, or None if not found or parse error.
        """
        try:
            data = json.loads(json_output)
        except json.JSONDecodeError as e:
            self.logger.error("Failed to parse tc JSON: %s", e)
            return None

        if not data or not isinstance(data, list):
            self.logger.warning("Empty or invalid tc JSON output")
            return None

        for entry in data:
            if isinstance(entry, dict) and entry.get("kind") == "cake":
                return entry

        return None

    # =========================================================================
    # ABC abstract methods
    # =========================================================================

    def set_bandwidth(self, queue: str, rate_bps: int) -> bool:
        """Set CAKE bandwidth via tc qdisc change.

        Args:
            queue: Ignored for linux-cake (interface set at init). Kept for ABC compat.
            rate_bps: Bandwidth limit in bits per second.

        Returns:
            True if tc command succeeded, False otherwise.
        """
        rate_kbit = rate_bps // 1000
        rc, _, err = self._run_tc(
            [
                "qdisc",
                "change",
                "dev",
                self.interface,
                "root",
                "cake",
                "bandwidth",
                f"{rate_kbit}kbit",
            ],
            timeout=self.tc_timeout,
        )
        if rc == 0:
            self.logger.debug("Set %s bandwidth to %skbit", self.interface, rate_kbit)
            return True
        self.logger.warning("tc qdisc change failed on %s: %s", self.interface, err)
        return False

    def get_bandwidth(self, queue: str) -> int | None:
        """Get current CAKE bandwidth from tc JSON output.

        Args:
            queue: Ignored for linux-cake (interface set at init). Kept for ABC compat.

        Returns:
            Current bandwidth in bps, or None on error.
        """
        rc, out, err = self._run_tc(
            ["-j", "qdisc", "show", "dev", self.interface],
            timeout=self.tc_timeout,
        )
        if rc != 0:
            self.logger.warning("tc qdisc show failed on %s: %s", self.interface, err)
            return None

        cake_entry = self._find_cake_entry(out)
        if cake_entry is None:
            self.logger.warning("No CAKE qdisc found on %s", self.interface)
            return None

        bandwidth = cake_entry.get("options", {}).get("bandwidth")
        if bandwidth is None:
            self.logger.warning("No bandwidth field in CAKE options on %s", self.interface)
            return None

        return int(bandwidth)

    def get_queue_stats(self, queue: str) -> dict | None:
        """Get CAKE qdisc statistics with per-tin parsing.

        Returns a superset dict compatible with existing consumers (5 base fields)
        plus extended CAKE fields (tins, memory, ecn, capacity).

        Args:
            queue: Ignored for linux-cake (interface set at init). Kept for ABC compat.

        Returns:
            Stats dict with base 5 + extended 4 fields + tins list, or None on error.
        """
        rc, out, err = self._run_tc(
            ["-j", "-s", "qdisc", "show", "dev", self.interface],
            timeout=self.tc_timeout,
        )
        if rc != 0:
            self.logger.warning(
                "tc qdisc show -s failed on %s: %s", self.interface, err
            )
            return None

        cake_entry = self._find_cake_entry(out)
        if cake_entry is None:
            self.logger.warning("No CAKE qdisc found on %s for stats", self.interface)
            return None

        # Base 5 fields (backward-compatible contract)
        stats: dict[str, Any] = {
            "packets": cake_entry.get("packets", 0),
            "bytes": cake_entry.get("bytes", 0),
            "dropped": cake_entry.get("drops", 0),  # tc uses "drops"
            "queued_packets": cake_entry.get("qlen", 0),
            "queued_bytes": cake_entry.get("backlog", 0),
        }

        # Extended CAKE fields
        stats["memory_used"] = cake_entry.get("memory_used", 0)
        stats["memory_limit"] = cake_entry.get("memory_limit", 0)
        stats["capacity_estimate"] = cake_entry.get("capacity_estimate", 0)

        # Per-tin statistics
        raw_tins = cake_entry.get("tins", [])
        tins: list[dict[str, Any]] = []
        total_ecn = 0
        for tin in raw_tins:
            tin_stats: dict[str, Any] = {
                "sent_bytes": tin.get("sent_bytes", 0),
                "sent_packets": tin.get("sent_packets", 0),
                "dropped_packets": tin.get("drops", 0),  # tc JSON = "drops"
                "ecn_marked_packets": tin.get("ecn_mark", 0),  # tc JSON = "ecn_mark"
                "backlog_bytes": tin.get("backlog_bytes", 0),
                "peak_delay_us": tin.get("peak_delay_us", 0),
                "avg_delay_us": tin.get("avg_delay_us", 0),
                "base_delay_us": tin.get("base_delay_us", 0),
                "sparse_flows": tin.get("sparse_flows", 0),
                "bulk_flows": tin.get("bulk_flows", 0),
                "unresponsive_flows": tin.get("unresponsive_flows", 0),
            }
            total_ecn += tin_stats["ecn_marked_packets"]
            tins.append(tin_stats)

        stats["tins"] = tins
        stats["ecn_marked"] = total_ecn

        return stats

    def enable_rule(self, comment: str) -> bool:
        """No-op: mangle rules stay on MikroTik router (Phase 108)."""
        self.logger.debug("enable_rule no-op on linux-cake backend: %s", comment)
        return True

    def disable_rule(self, comment: str) -> bool:
        """No-op: mangle rules stay on MikroTik router (Phase 108)."""
        self.logger.debug("disable_rule no-op on linux-cake backend: %s", comment)
        return True

    def is_rule_enabled(self, comment: str) -> bool | None:
        """No-op: mangle rules stay on MikroTik router (Phase 108)."""
        return None

    # =========================================================================
    # Optional overrides
    # =========================================================================

    def test_connection(self) -> bool:
        """Verify tc binary availability and CAKE qdisc presence.

        Checks:
        1. tc binary exists on PATH (via shutil.which)
        2. tc can query the interface
        3. CAKE qdisc is present on the interface

        Returns:
            True if all checks pass, False otherwise.
        """
        if shutil.which("tc") is None:
            self.logger.error("tc binary not found on PATH")
            return False

        rc, out, err = self._run_tc(
            ["-j", "qdisc", "show", "dev", self.interface],
            timeout=self.tc_timeout,
        )
        if rc != 0:
            self.logger.error(
                "tc qdisc show failed on %s: %s", self.interface, err
            )
            return False

        cake_entry = self._find_cake_entry(out)
        if cake_entry is None:
            self.logger.error("No CAKE qdisc found on %s", self.interface)
            return False

        return True

    # =========================================================================
    # CAKE-specific methods (not in ABC)
    # =========================================================================

    def initialize_cake(self, params: dict[str, Any]) -> bool:
        """Initialize CAKE qdisc via tc qdisc replace.

        Called at daemon startup. Uses replace (not add) to handle the case
        where a qdisc already exists. This is required because systemd-networkd
        silently drops CAKE params if a qdisc already exists (systemd #31226).

        Args:
            params: CAKE parameters dict. Supported keys:
                - bandwidth: str like "500000kbit"
                - diffserv: str like "diffserv4"
                - overhead_keyword: str (standalone tc token like "docsis", "bridged-ptm")
                - overhead: int (numeric fallback, used only if overhead_keyword absent)
                - mpu: int
                - memlimit: str like "33554432"
                - rtt: str like "100ms"
                - Boolean flags (present=enabled): "split-gso", "ack-filter",
                  "ingress", "ecn"

        Returns:
            True if tc command succeeded, False otherwise.
        """
        cmd_args = ["qdisc", "replace", "dev", self.interface, "root", "cake"]

        # Key-value params
        if "bandwidth" in params:
            cmd_args.extend(["bandwidth", str(params["bandwidth"])])
        if "diffserv" in params:
            cmd_args.append(str(params["diffserv"]))
        if "overhead_keyword" in params:
            kw = str(params["overhead_keyword"])
            if kw in OVERHEAD_KEYWORD_EXPANSION:
                cmd_args.extend(OVERHEAD_KEYWORD_EXPANSION[kw])
            else:
                # Direct tc keywords: docsis, conservative, raw
                cmd_args.append(kw)
        elif "overhead" in params:
            cmd_args.extend(["overhead", str(params["overhead"])])
        if "mpu" in params:
            cmd_args.extend(["mpu", str(params["mpu"])])
        if "memlimit" in params:
            cmd_args.extend(["memlimit", str(params["memlimit"])])
        if "rtt" in params:
            cmd_args.extend(["rtt", str(params["rtt"])])

        # Boolean flags -- append literal string if present and truthy
        # Note: "ecn" is excluded -- not supported by iproute2-6.15.0's tc,
        # and CAKE enables ECN by default on all tins anyway.
        for flag in ("split-gso", "ack-filter", "ingress"):
            if params.get(flag):
                cmd_args.append(flag)

        rc, _, err = self._run_tc(cmd_args, timeout=10.0)
        if rc == 0:
            self.logger.info(
                "Initialized CAKE on %s: %s", self.interface, " ".join(cmd_args[6:])
            )
            return True
        self.logger.error(
            "Failed to initialize CAKE on %s: %s", self.interface, err
        )
        return False

    def validate_cake(self, expected: dict[str, Any]) -> bool:
        """Validate CAKE parameters by reading back via tc -j qdisc show.

        Compares the options section of the CAKE qdisc against expected values.

        Args:
            expected: Dict of parameter names to expected values.
                      Keys must match tc JSON options field names.

        Returns:
            True if all expected parameters match, False on any mismatch.
        """
        rc, out, err = self._run_tc(
            ["-j", "qdisc", "show", "dev", self.interface],
            timeout=self.tc_timeout,
        )
        if rc != 0:
            self.logger.error(
                "tc qdisc show failed during validation on %s: %s",
                self.interface,
                err,
            )
            return False

        cake_entry = self._find_cake_entry(out)
        if cake_entry is None:
            self.logger.error(
                "No CAKE qdisc found on %s during validation", self.interface
            )
            return False

        options = cake_entry.get("options", {})
        all_match = True
        for key, expected_value in expected.items():
            actual_value = options.get(key)
            if actual_value != expected_value:
                self.logger.error(
                    "CAKE param mismatch on %s: %s expected=%r actual=%r",
                    self.interface,
                    key,
                    expected_value,
                    actual_value,
                )
                all_match = False

        return all_match

    @classmethod
    def from_config(
        cls, config: Any, direction: str = "download"
    ) -> "LinuxCakeBackend":
        """Create LinuxCakeBackend from config object.

        Reads interface from cake_params section based on direction.
        Direction is determined by the daemon context (upload vs download instance).

        Args:
            config: Configuration object with .data dict containing cake_params.
            direction: "download" or "upload" -- determines which interface to use.

        Returns:
            Configured LinuxCakeBackend instance.

        Raises:
            ValueError: If the required interface field is missing or empty.
        """
        cake_params = config.data.get("cake_params", {})
        interface_key = f"{direction}_interface"
        interface = cake_params.get(interface_key, "")
        if not interface:
            raise ValueError(
                f"cake_params.{interface_key} required for linux-cake transport"
            )
        tc_timeout = config.data.get("timeouts", {}).get("tc_command", 5.0)
        return cls(interface=interface, tc_timeout=tc_timeout)
