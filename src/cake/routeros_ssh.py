"""Shared RouterOS SSH client for executing commands on MikroTik routers.

This module provides a unified interface for SSH command execution across
all CAKE system components, eliminating code duplication and ensuring
consistent behavior (retry logic, timeouts, logging).

Usage:
    from cake.routeros_ssh import RouterOSSSH

    ssh = RouterOSSSH(
        host="192.168.1.1",
        user="admin",
        ssh_key="/path/to/key",
        timeout=15,
        logger=logger
    )
    rc, stdout, stderr = ssh.run_cmd("/queue tree print", capture=True)
"""

import logging
import subprocess
from typing import Tuple

from cake.retry_utils import retry_with_backoff


class RouterOSSSH:
    """SSH client for executing commands on RouterOS devices.

    Provides:
    - Automatic retry with exponential backoff on transient failures
    - Configurable connection and command timeouts
    - Consistent logging of commands and results

    Attributes:
        host: RouterOS device IP address or hostname
        user: SSH username
        ssh_key: Path to SSH private key file
        timeout: Command timeout in seconds
        logger: Logger instance for debug/error messages
    """

    def __init__(
        self,
        host: str,
        user: str,
        ssh_key: str,
        timeout: int = 15,
        logger: logging.Logger = None
    ):
        """Initialize RouterOS SSH client.

        Args:
            host: RouterOS device IP address or hostname
            user: SSH username for authentication
            ssh_key: Path to SSH private key file
            timeout: Command timeout in seconds (default: 15)
            logger: Logger instance (optional, creates null logger if not provided)
        """
        self.host = host
        self.user = user
        self.ssh_key = ssh_key
        self.timeout = timeout
        self.logger = logger or logging.getLogger(__name__)

    @classmethod
    def from_config(cls, config, logger: logging.Logger) -> "RouterOSSSH":
        """Create RouterOSSSH instance from a config object.

        Expects config to have:
        - router_host: str
        - router_user: str
        - ssh_key: str
        - timeout_ssh_command: int (optional, defaults to 15)

        Args:
            config: Configuration object with router connection settings
            logger: Logger instance

        Returns:
            Configured RouterOSSSH instance
        """
        return cls(
            host=config.router_host,
            user=config.router_user,
            ssh_key=config.ssh_key,
            timeout=getattr(config, 'timeout_ssh_command', 15),
            logger=logger
        )

    @retry_with_backoff(max_attempts=3, initial_delay=1.0, backoff_factor=2.0)
    def run_cmd(self, cmd: str, capture: bool = False) -> Tuple[int, str, str]:
        """Execute RouterOS command via SSH with automatic retry.

        Retries on:
        - Timeout (subprocess.TimeoutExpired)
        - Connection errors (refused, reset, unreachable)

        Does NOT retry on:
        - Authentication failures
        - Command syntax errors

        Args:
            cmd: RouterOS command to execute
            capture: Whether to capture stdout/stderr (default: False)

        Returns:
            Tuple of (returncode, stdout, stderr)
            - stdout/stderr are empty strings if capture=False

        Raises:
            Exception: On non-retryable errors or after max retry attempts
        """
        args = [
            "ssh",
            "-i", self.ssh_key,
            "-o", "ConnectTimeout=10",
            f"{self.user}@{self.host}",
            cmd
        ]

        self.logger.debug(f"RouterOS command: {cmd}")

        if capture:
            res = subprocess.run(
                args,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout
            )
            self.logger.debug(f"RouterOS stdout: {res.stdout}")
            return res.returncode, res.stdout, res.stderr
        else:
            res = subprocess.run(args, text=True, timeout=self.timeout)
            return res.returncode, "", ""
