"""RouterOS command dispatch adapter.

Thin wrapper that creates a router client with failover support
and delegates command execution to the underlying transport backend.
"""

import logging

from wanctl.autorate_config import Config
from wanctl.router_client import get_router_client_with_failover


class RouterOS:
    """RouterOS interface for setting queue limits.

    Supports multiple transports:
    - ssh: SSH via paramiko - uses SSH keys
    - rest: REST API via HTTPS (default) - uses password authentication

    Transport is selected via config.router_transport field.
    """

    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger
        # Use factory function to get appropriate client (SSH or REST) with failover
        self.client = get_router_client_with_failover(config, logger)

    @property
    def needs_rate_limiting(self) -> bool:
        """RouterOS needs rate limiting unless YAML explicitly disables it."""
        rl_config = self.config.rate_limiter_config
        if rl_config.get("enabled") is False:
            return False
        return True

    @property
    def rate_limit_params(self) -> dict[str, int]:
        """Rate limiter params: backend defaults merged with YAML overrides."""
        rl_config = self.config.rate_limiter_config
        return {
            "max_changes": rl_config.get("max_changes", 5),
            "window_seconds": rl_config.get("window_seconds", 10),
        }

    def set_limits(self, wan: str, down_bps: int, up_bps: int) -> bool:
        """Set CAKE limits for one WAN using a single batched router command"""
        self.logger.debug(f"{wan}: Setting limits DOWN={down_bps} UP={up_bps}")

        # WAN name for queue type (e.g., "ATT" -> "att", "Spectrum" -> "spectrum")
        wan_lower = self.config.wan_name.lower()

        # Batch both queue commands into a single SSH call for lower latency
        # RouterOS supports semicolon-separated commands
        cmd = (
            f'/queue tree set [find name="{self.config.queue_down}"] '
            f"queue=cake-down-{wan_lower} max-limit={down_bps}; "
            f'/queue tree set [find name="{self.config.queue_up}"] '
            f"queue=cake-up-{wan_lower} max-limit={up_bps}"
        )

        rc, _, _ = self.client.run_cmd(cmd)
        if rc != 0:
            self.logger.error(f"Failed to set queue limits: {cmd}")
            return False

        return True
