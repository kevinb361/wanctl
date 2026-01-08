"""Shared RouterOS SSH client for executing commands on MikroTik routers.

This module provides a unified interface for SSH command execution across
all CAKE system components, eliminating code duplication and ensuring
consistent behavior (retry logic, timeouts, logging).

Uses paramiko for persistent SSH connections to minimize connection overhead.
A single connection is maintained for the daemon lifetime, with automatic
reconnection on failure.

Usage:
    from wanctl.routeros_ssh import RouterOSSSH

    ssh = RouterOSSSH(
        host="192.168.1.1",
        user="admin",
        ssh_key="/path/to/key",
        timeout=15,
        logger=logger
    )
    rc, stdout, stderr = ssh.run_cmd("/queue tree print", capture=True)

    # Clean up when done (important for daemon mode)
    ssh.close()
"""

import logging
from pathlib import Path
from typing import Optional, Tuple

import paramiko

from wanctl.retry_utils import retry_with_backoff


class RouterOSSSH:
    """SSH client for executing commands on RouterOS devices.

    Uses paramiko for persistent connections - establishes connection once
    and reuses for all subsequent commands. This reduces latency from
    ~200ms per command (subprocess SSH) to ~30-50ms (reused connection).

    Provides:
    - Persistent SSH connection with automatic reconnection
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
        self._client: Optional[paramiko.SSHClient] = None

    def _get_known_hosts_path(self) -> Path:
        """Get path to user's known_hosts file.

        Returns ~/.ssh/known_hosts for the current user, creating the
        .ssh directory if it doesn't exist.

        For the wanctl service user, this will be /var/lib/wanctl/.ssh/known_hosts
        """
        ssh_dir = Path.home() / ".ssh"
        ssh_dir.mkdir(mode=0o700, exist_ok=True)
        known_hosts = ssh_dir / "known_hosts"

        # Create empty known_hosts if it doesn't exist
        if not known_hosts.exists():
            known_hosts.touch(mode=0o600)

        return known_hosts

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

    def _connect(self) -> None:
        """Establish SSH connection using paramiko.

        Creates a new SSHClient, loads the private key, and connects
        to the router. Connection timeout is 10 seconds.

        SECURITY: Host key validation is ENABLED. The router's SSH host key
        must be present in known_hosts before connection will succeed.
        Run: ssh-keyscan -H <router_ip> >> ~/.ssh/known_hosts

        Raises:
            paramiko.SSHException: On connection failure or host key mismatch
            FileNotFoundError: If SSH key file doesn't exist
        """
        self._client = paramiko.SSHClient()

        # Load system and user known_hosts for host key verification
        # This prevents MITM attacks by validating router identity
        self._client.load_system_host_keys()
        self._client.load_host_keys(str(self._get_known_hosts_path()))

        # RejectPolicy is the default - connection fails if host key not in known_hosts
        # Do NOT use AutoAddPolicy - it accepts any key and enables MITM attacks
        self._client.set_missing_host_key_policy(paramiko.RejectPolicy())

        self.logger.debug(f"Establishing SSH connection to {self.user}@{self.host}")

        self._client.connect(
            hostname=self.host,
            username=self.user,
            key_filename=self.ssh_key,
            timeout=10,  # Connection timeout
            allow_agent=False,
            look_for_keys=False
        )

        self.logger.debug(f"SSH connection established to {self.host}")

    def _is_connected(self) -> bool:
        """Check if SSH connection is still alive.

        Returns:
            True if connected and transport is active, False otherwise
        """
        if self._client is None:
            return False
        transport = self._client.get_transport()
        return transport is not None and transport.is_active()

    def _ensure_connected(self) -> None:
        """Ensure persistent SSH connection is established.

        Checks if current connection is alive, and reconnects if not.
        This handles connection drops, network issues, and router reboots.
        """
        if not self._is_connected():
            if self._client is not None:
                self.logger.debug("SSH connection lost, reconnecting...")
                try:
                    self._client.close()
                except Exception:
                    pass
            self._connect()

    @retry_with_backoff(max_attempts=3, initial_delay=1.0, backoff_factor=2.0)
    def run_cmd(self, cmd: str, capture: bool = False) -> Tuple[int, str, str]:
        """Execute RouterOS command via persistent SSH connection.

        Uses paramiko's exec_command() on a persistent connection for
        low-latency command execution (~30-50ms vs ~200ms for subprocess).

        Retries on:
        - Connection errors (connection lost, timeout)
        - Transport errors

        Does NOT retry on:
        - Authentication failures (handled at connection time)
        - Command syntax errors (RouterOS returns non-zero)

        Args:
            cmd: RouterOS command to execute
            capture: Whether to capture stdout/stderr (default: False)
                    Note: With paramiko, we always capture for return code detection

        Returns:
            Tuple of (returncode, stdout, stderr)
            - returncode: 0 for success, non-zero for failure
            - stdout/stderr: command output (empty strings if capture=False)

        Raises:
            Exception: On non-retryable errors or after max retry attempts
        """
        self._ensure_connected()

        self.logger.debug(f"RouterOS command: {cmd}")

        try:
            # Execute command with timeout
            stdin, stdout, stderr = self._client.exec_command(
                cmd,
                timeout=self.timeout
            )

            # Wait for command to complete and get exit status
            exit_status = stdout.channel.recv_exit_status()

            if capture:
                stdout_text = stdout.read().decode('utf-8', errors='replace')
                stderr_text = stderr.read().decode('utf-8', errors='replace')
                self.logger.debug(f"RouterOS stdout: {stdout_text}")
                return exit_status, stdout_text, stderr_text
            else:
                # Drain the channels even if not capturing (required for proper cleanup)
                stdout.read()
                stderr.read()
                return exit_status, "", ""

        except paramiko.SSHException as e:
            # Connection issue - close and let retry reconnect
            self.logger.warning(f"SSH error executing command: {e}")
            self._client = None
            raise

    def close(self) -> None:
        """Close the persistent SSH connection.

        Should be called when the daemon shuts down to clean up resources.
        Safe to call multiple times or when not connected.
        """
        if self._client is not None:
            try:
                self._client.close()
                self.logger.debug(f"SSH connection closed to {self.host}")
            except Exception as e:
                self.logger.debug(f"Error closing SSH connection: {e}")
            finally:
                self._client = None
