"""RouterOS backend implementation for wanctl.

This module implements the RouterBackend interface for Mikrotik RouterOS
devices using SSH command execution.

Requires:
- SSH key authentication configured on RouterOS
- User with access to /queue/tree and /ip/firewall/mangle

Config schema:
    router:
      type: routeros
      host: "192.168.1.1"
      user: "admin"
      ssh_key: "/etc/wanctl/ssh/router.key"
"""

import logging
from typing import Any

from wanctl.backends.base import RouterBackend
from wanctl.router_command_utils import (
    check_command_success,
    extract_field_value,
    extract_queue_stats,
    validate_rule_status,
)
from wanctl.routeros_ssh import RouterOSSSH


class RouterOSBackend(RouterBackend):
    """RouterOS implementation of the router backend interface.

    Uses SSH to execute RouterOS commands for:
    - Queue tree bandwidth management
    - Mangle rule enable/disable for steering
    - Queue statistics collection
    """

    def __init__(
        self,
        host: str,
        user: str,
        ssh_key: str,
        timeout: int = 15,
        logger: logging.Logger | None = None,
    ):
        """Initialize RouterOS backend.

        Args:
            host: Router IP address or hostname
            user: SSH username
            ssh_key: Path to SSH private key
            timeout: Command timeout in seconds
            logger: Logger instance
        """
        super().__init__(logger)
        self.ssh = RouterOSSSH(
            host=host, user=user, ssh_key=ssh_key, timeout=timeout, logger=self.logger
        )

    @classmethod
    def from_config(cls, config: Any) -> "RouterOSBackend":
        """Create RouterOSBackend from config object.

        Expects config.router dict with:
        - host: Router IP/hostname
        - user: SSH username
        - ssh_key: Path to SSH key

        Args:
            config: Configuration object

        Returns:
            Configured RouterOSBackend instance
        """
        router = config.router
        timeout = config.timeouts.get("ssh_command", 15) if hasattr(config, "timeouts") else 15

        return cls(
            host=router["host"], user=router["user"], ssh_key=router["ssh_key"], timeout=timeout
        )

    def set_bandwidth(self, queue: str, rate_bps: int) -> bool:
        """Set max-limit on a RouterOS queue tree.

        Args:
            queue: Queue name (e.g., "WAN-Download-1")
            rate_bps: Bandwidth in bits per second

        Returns:
            True if successful
        """
        cmd = f'/queue/tree/set [find name="{queue}"] max-limit={rate_bps}'
        rc, _, err = self.ssh.run_cmd(cmd)

        if check_command_success(rc, cmd, err, self.logger, f"set bandwidth on {queue}"):
            self.logger.debug(f"Set {queue} max-limit to {rate_bps} bps")
            return True
        return False

    def get_bandwidth(self, queue: str) -> int | None:
        """Get current max-limit from RouterOS queue tree.

        Args:
            queue: Queue name

        Returns:
            Current bandwidth in bps, or None on error
        """
        cmd = f'/queue/tree/print detail where name="{queue}"'
        rc, out, err = self.ssh.run_cmd(cmd, capture=True)

        if rc != 0:
            self.logger.error(f"Failed to get bandwidth for {queue}: {err}")
            return None

        # Extract max-limit using utility
        max_limit = extract_field_value(out, "max-limit", int, self.logger)

        # Check for unlimited (0 or not set)
        if max_limit is None:
            if "max-limit=0" in out or "max-limit=" not in out:
                return 0
            self.logger.warning(f"Could not parse max-limit for {queue}")
            return None

        return max_limit

    def get_queue_stats(self, queue: str) -> dict | None:
        """Get statistics from RouterOS queue tree.

        Parses:
        - packets: Total packets processed
        - bytes: Total bytes processed
        - dropped: Packets dropped by CAKE
        - queued_packets: Current queue depth (packets)
        - queued_bytes: Current queue depth (bytes)

        Args:
            queue: Queue name

        Returns:
            Dict with stats, or None on error
        """
        cmd = f'/queue/tree/print stats detail where name="{queue}"'
        rc, out, err = self.ssh.run_cmd(cmd, capture=True)

        if rc != 0:
            self.logger.error(f"Failed to get stats for {queue}: {err}")
            return None

        # Extract statistics using utility (handles both SSH text and REST JSON)
        return extract_queue_stats(out, self.logger)

    def enable_rule(self, comment: str) -> bool:
        """Enable a mangle rule by comment.

        Args:
            comment: Rule comment

        Returns:
            True if successful
        """
        cmd = f'/ip/firewall/mangle/enable [find comment="{comment}"]'
        rc, _, err = self.ssh.run_cmd(cmd)

        if check_command_success(rc, cmd, err, self.logger, f"enable rule '{comment}'"):
            self.logger.info(f"Enabled mangle rule: {comment}")
            return True
        return False

    def disable_rule(self, comment: str) -> bool:
        """Disable a mangle rule by comment.

        Args:
            comment: Rule comment

        Returns:
            True if successful
        """
        cmd = f'/ip/firewall/mangle/disable [find comment="{comment}"]'
        rc, _, err = self.ssh.run_cmd(cmd)

        if check_command_success(rc, cmd, err, self.logger, f"disable rule '{comment}'"):
            self.logger.info(f"Disabled mangle rule: {comment}")
            return True
        return False

    def is_rule_enabled(self, comment: str) -> bool | None:
        """Check if a mangle rule is enabled.

        Args:
            comment: Rule comment

        Returns:
            True if enabled, False if disabled, None if not found
        """
        cmd = f'/ip/firewall/mangle/print where comment="{comment}"'
        rc, out, err = self.ssh.run_cmd(cmd, capture=True)

        if rc != 0:
            self.logger.error(f"Failed to check rule '{comment}': {err}")
            return None

        if not out.strip():
            self.logger.warning(f"Rule not found: {comment}")
            return None

        # Use utility to check rule status (X flag = disabled)
        return validate_rule_status(out, self.logger)

    def reset_queue_counters(self, queue: str) -> bool:
        """Reset queue statistics counters.

        Args:
            queue: Queue name

        Returns:
            True if successful
        """
        cmd = f'/queue/tree/reset-counters [find name="{queue}"]'
        rc, _, err = self.ssh.run_cmd(cmd)

        if rc != 0:
            self.logger.error(f"Failed to reset counters for {queue}: {err}")
            return False

        self.logger.debug(f"Reset counters for {queue}")
        return True

    def test_connection(self) -> bool:
        """Test SSH connectivity to RouterOS.

        Returns:
            True if router responds to identity command
        """
        rc, out, _ = self.ssh.run_cmd("/system/identity/print", capture=True)
        return rc == 0 and bool(out.strip())
