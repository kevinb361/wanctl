"""RouterOS REST API client for executing commands on MikroTik routers.

This module provides an HTTP/HTTPS-based interface for RouterOS command execution.
The REST API is available on RouterOS 7.x on port 443 (HTTPS) or 80 (HTTP).

Advantages over SSH:
- Lower latency (~50ms vs ~200ms for subprocess SSH)
- No connection setup overhead per command
- Simpler authentication (username/password)
- Works through firewalls that block SSH

Disadvantages:
- Requires password authentication (not SSH keys)
- Requires HTTPS setup on router (for secure connections)
- Less commonly used (less documentation)

Usage:
    from wanctl.routeros_rest import RouterOSREST

    rest = RouterOSREST(
        host="192.168.1.1",
        user="admin",
        password="password",
        port=443,
        verify_ssl=False,
        timeout=15,
        logger=logger
    )

    # Execute command
    rc, stdout, stderr = rest.run_cmd("/queue/tree/print")

    # Set queue limit directly
    success = rest.set_queue_limit("WAN-Download", 500_000_000)

    # Clean up when done
    rest.close()
"""

import logging
import re
from typing import Any

import requests
from urllib3.exceptions import InsecureRequestWarning

from wanctl.retry_utils import retry_with_backoff

# Disable SSL warnings for self-signed certificates (common on routers)
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class RouterOSREST:
    """REST API client for executing commands on RouterOS devices.

    Uses HTTP/HTTPS requests to the RouterOS REST API for fast command
    execution. This provides similar functionality to RouterOSSSH but
    with lower latency and simpler connection management.

    Attributes:
        host: RouterOS device IP address or hostname
        user: API username
        password: API password
        port: REST API port (default 443 for HTTPS)
        verify_ssl: Whether to verify SSL certificates (default False)
        timeout: Request timeout in seconds
        logger: Logger instance for debug/error messages
    """

    def __init__(
        self,
        host: str,
        user: str,
        password: str,
        port: int = 443,
        verify_ssl: bool = False,
        timeout: int = 15,
        logger: logging.Logger | None = None
    ):
        """Initialize RouterOS REST API client.

        Args:
            host: RouterOS device IP address or hostname
            user: API username for authentication
            password: API password for authentication
            port: REST API port (default 443 for HTTPS, use 80 for HTTP)
            verify_ssl: Whether to verify SSL certificates (default False)
            timeout: Request timeout in seconds (default: 15)
            logger: Logger instance (optional, creates null logger if not provided)
        """
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.logger = logger or logging.getLogger(__name__)

        # Build base URL
        protocol = "https" if port == 443 else "http"
        self.base_url = f"{protocol}://{host}:{port}/rest"

        # Create session with authentication
        self._session = requests.Session()
        self._session.auth = (user, password)
        self._session.verify = verify_ssl

        # Cache for queue/rule IDs to reduce API calls
        # Key: queue_name or rule_comment, Value: RouterOS ID (e.g., "*1")
        self._queue_id_cache: dict[str, str] = {}
        self._mangle_id_cache: dict[str, str] = {}

        self.logger.debug(f"RouterOS REST client initialized: {self.base_url}")

    @classmethod
    def from_config(cls, config, logger: logging.Logger) -> "RouterOSREST":
        """Create RouterOSREST instance from a config object.

        Expects config to have:
        - router_host: str
        - router_user: str
        - router_password: str (or from environment variable)
        - router_port: int (optional, defaults to 443)
        - router_verify_ssl: bool (optional, defaults to False)
        - timeout_ssh_command: int (optional, defaults to 15)

        Args:
            config: Configuration object with router connection settings
            logger: Logger instance

        Returns:
            Configured RouterOSREST instance
        """
        import os

        # Get password - support environment variable
        password = getattr(config, 'router_password', None)
        if password and password.startswith('${') and password.endswith('}'):
            env_var = password[2:-1]
            password = os.environ.get(env_var, '')

        return cls(
            host=config.router_host,
            user=config.router_user,
            password=password,
            port=getattr(config, 'router_port', 443),
            verify_ssl=getattr(config, 'router_verify_ssl', False),
            timeout=getattr(config, 'timeout_ssh_command', 15),
            logger=logger
        )

    @retry_with_backoff(max_attempts=3, initial_delay=1.0, backoff_factor=2.0)
    def run_cmd(self, cmd: str, capture: bool = False, timeout: int | None = None) -> tuple[int, str, str]:
        """Execute RouterOS command via REST API.

        Converts CLI-style commands to REST API calls.
        Note: Only certain commands are supported - primarily queue/tree operations.

        Retries on transient network errors (connection refused, timeout, etc.)
        with exponential backoff, matching SSH client behavior.

        Args:
            cmd: RouterOS command to execute (CLI-style)
            capture: Whether to capture output (always captured with REST)
            timeout: Command timeout in seconds (uses self.timeout if None)

        Returns:
            Tuple of (returncode, stdout, stderr)
            - returncode: 0 for success, non-zero for failure
            - stdout: JSON response as string
            - stderr: error message if any

        Raises:
            requests.RequestException: On persistent network errors after retries
        """
        timeout_val = timeout if timeout is not None else self.timeout
        self.logger.debug(f"RouterOS REST command: {cmd} (timeout={timeout_val}s)")

        try:
            # Parse CLI command and convert to REST API call
            result = self._execute_command(cmd, timeout=timeout_val)

            if result is not None:
                import json
                return 0, json.dumps(result), ""
            else:
                return 1, "", "Command failed"

        except requests.RequestException as e:
            self.logger.warning(f"REST API error: {e}")
            return 1, "", str(e)
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            return 1, "", str(e)

    def _execute_command(self, cmd: str, timeout: int | None = None) -> dict[str, Any] | None:
        """Parse CLI command and execute via REST API.

        Supports common queue tree operations:
        - /queue tree set [find name="..."] queue=... max-limit=...
        - /queue tree print where name="..."
        - /ip firewall mangle enable/disable [find comment="..."]

        Args:
            cmd: CLI-style command
            timeout: Command timeout in seconds (uses self.timeout if None)

        Returns:
            JSON response from API, or None on failure
        """
        timeout_val = timeout if timeout is not None else self.timeout

        # Handle batched commands (separated by ;)
        if ';' in cmd:
            for subcmd in cmd.split(';'):
                subcmd = subcmd.strip()
                if subcmd:
                    result = self._execute_single_command(subcmd, timeout=timeout_val)
                    if result is None:
                        return None
            return {"status": "ok"}
        else:
            return self._execute_single_command(cmd, timeout=timeout_val)

    def _execute_single_command(self, cmd: str, timeout: int | None = None) -> dict[str, Any] | None:
        """Execute a single CLI command via REST API.

        Args:
            cmd: Single CLI command
            timeout: Command timeout in seconds (uses self.timeout if None)

        Returns:
            JSON response from API, or None on failure
        """
        timeout_val = timeout if timeout is not None else self.timeout
        cmd = cmd.strip()

        # Parse /queue tree commands
        if cmd.startswith('/queue tree set'):
            return self._handle_queue_tree_set(cmd, timeout=timeout_val)
        elif 'reset-counters' in cmd and '/queue' in cmd:
            return self._handle_queue_reset_counters(cmd, timeout=timeout_val)
        elif cmd.startswith('/queue tree print') or cmd.startswith('/queue/tree print'):
            return self._handle_queue_tree_print(cmd, timeout=timeout_val)
        elif cmd.startswith('/ip firewall mangle'):
            return self._handle_mangle_rule(cmd, timeout=timeout_val)
        else:
            self.logger.warning(f"Unsupported command for REST API: {cmd}")
            return None

    def _parse_find_name(self, cmd: str) -> str | None:
        """Extract queue name from [find name="..."] pattern.

        Args:
            cmd: RouterOS command string containing [find name="..."]

        Returns:
            Extracted name string, or None if pattern not found
        """
        match = re.search(r'\[find name="([^"]+)"\]', cmd)
        return match.group(1) if match else None

    def _parse_find_comment(self, cmd: str) -> str | None:
        """Extract comment from [find comment="..."] pattern.

        Args:
            cmd: RouterOS command string containing [find comment="..."]

        Returns:
            Extracted comment string, or None if pattern not found
        """
        match = re.search(r'\[find comment="([^"]+)"\]', cmd)
        return match.group(1) if match else None

    def _parse_parameters(self, cmd: str) -> dict[str, str]:
        """Extract key=value parameters from RouterOS command.

        Extracts common parameters like queue=, max-limit= from command strings.

        Args:
            cmd: RouterOS command string with key=value pairs

        Returns:
            Dict mapping parameter names to their values
        """
        params: dict[str, str] = {}

        queue_match = re.search(r'queue=(\S+)', cmd)
        if queue_match:
            params['queue'] = queue_match.group(1)

        limit_match = re.search(r'max-limit=(\d+)', cmd)
        if limit_match:
            params['max-limit'] = limit_match.group(1)

        return params

    def _handle_queue_tree_set(self, cmd: str, timeout: int | None = None) -> dict | None:
        """Handle /queue tree set command.

        Example: /queue tree set [find name="WAN-Download"] queue=cake-down max-limit=500000000

        Args:
            cmd: Queue tree set command
            timeout: Command timeout in seconds (uses self.timeout if None)

        Returns:
            API response dict or None on failure
        """
        timeout_val = timeout if timeout is not None else self.timeout

        # Extract queue name from [find name="..."]
        queue_name = self._parse_find_name(cmd)
        if not queue_name:
            self.logger.error(f"Could not parse queue name from: {cmd}")
            return None

        # Extract parameters (queue=, max-limit=)
        params = self._parse_parameters(cmd)

        if not params:
            self.logger.error(f"No parameters found in: {cmd}")
            return None

        # First, find the queue ID
        queue_id = self._find_queue_id(queue_name, timeout=timeout_val)
        if queue_id is None:
            self.logger.error(f"Queue not found: {queue_name}")
            return None

        # Update the queue via PATCH
        url = f"{self.base_url}/queue/tree/{queue_id}"

        try:
            resp = self._session.patch(url, json=params, timeout=timeout_val)

            if resp.ok:
                self.logger.debug(f"Queue {queue_name} updated: {params}")
                return {"status": "ok", "queue": queue_name}
            else:
                self.logger.error(f"Failed to update queue {queue_name}: {resp.status_code} {resp.text}")
                return None

        except requests.RequestException as e:
            self.logger.error(f"REST API error updating queue: {e}")
            return None

    def _handle_queue_reset_counters(self, cmd: str, timeout: int | None = None) -> dict | None:
        """Handle /queue tree reset-counters command.

        Example: /queue tree reset-counters [find name="WAN-Download"]
        RouterOS REST API uses POST to /queue/tree/reset-counters with .id parameter

        Args:
            cmd: Queue tree reset-counters command
            timeout: Command timeout in seconds (uses self.timeout if None)

        Returns:
            API response dict or None on failure
        """
        timeout_val = timeout if timeout is not None else self.timeout

        # Extract queue name from [find name="..."]
        queue_name = self._parse_find_name(cmd)
        if not queue_name:
            # Try alternative format: where name="..."
            name_match = re.search(r'name="([^"]+)"', cmd)
            if name_match:
                queue_name = name_match.group(1)

        if not queue_name:
            self.logger.error(f"Could not parse queue name from: {cmd}")
            return None

        # Find the queue ID
        queue_id = self._find_queue_id(queue_name, timeout=timeout_val)
        if queue_id is None:
            self.logger.error(f"Queue not found: {queue_name}")
            return None

        # Reset counters via POST
        url = f"{self.base_url}/queue/tree/reset-counters"

        try:
            # RouterOS REST API expects .id parameter for the target
            resp = self._session.post(url, json={".id": queue_id}, timeout=timeout_val)

            if resp.ok:
                self.logger.debug(f"Reset counters for queue {queue_name}")
                return {"status": "ok", "queue": queue_name}
            else:
                self.logger.error(f"Failed to reset counters for {queue_name}: {resp.status_code} {resp.text}")
                return None

        except requests.RequestException as e:
            self.logger.error(f"REST API error resetting counters: {e}")
            return None

    def _handle_queue_tree_print(self, cmd: str, timeout: int | None = None) -> dict | None:
        """Handle /queue tree print command.

        Args:
            cmd: Queue tree print command
            timeout: Command timeout in seconds (uses self.timeout if None)

        Returns:
            Queue details dict or None on failure
        """
        timeout_val = timeout if timeout is not None else self.timeout

        # Extract queue name if filtering (uses 'where name=' syntax, not [find])
        name_match = re.search(r'where name="([^"]+)"', cmd)

        url = f"{self.base_url}/queue/tree"
        params = {}

        if name_match:
            params['name'] = name_match.group(1)

        try:
            resp = self._session.get(url, params=params, timeout=timeout_val)

            if resp.ok:
                return resp.json()
            else:
                self.logger.error(f"Failed to get queue: {resp.status_code}")
                return None

        except requests.RequestException as e:
            self.logger.error(f"REST API error: {e}")
            return None

    def _handle_mangle_rule(self, cmd: str, timeout: int | None = None) -> dict | None:
        """Handle /ip firewall mangle enable/disable commands.

        Args:
            cmd: Mangle rule command
            timeout: Command timeout in seconds (uses self.timeout if None)

        Returns:
            API response dict or None on failure
        """
        timeout_val = timeout if timeout is not None else self.timeout

        # Extract comment from [find comment="..."]
        comment = self._parse_find_comment(cmd)
        if not comment:
            self.logger.error(f"Could not parse rule comment from: {cmd}")
            return None

        # Determine if enable or disable
        if 'enable' in cmd:
            disabled = "false"
        elif 'disable' in cmd:
            disabled = "true"
        else:
            self.logger.error(f"Unknown mangle action in: {cmd}")
            return None

        # Find the rule ID
        rule_id = self._find_mangle_rule_id(comment, timeout=timeout_val)
        if rule_id is None:
            self.logger.error(f"Mangle rule not found: {comment}")
            return None

        # Update the rule
        url = f"{self.base_url}/ip/firewall/mangle/{rule_id}"

        try:
            resp = self._session.patch(url, json={"disabled": disabled}, timeout=timeout_val)

            if resp.ok:
                self.logger.debug(f"Mangle rule '{comment}' disabled={disabled}")
                return {"status": "ok", "comment": comment, "disabled": disabled}
            else:
                self.logger.error(f"Failed to update mangle rule: {resp.status_code}")
                return None

        except requests.RequestException as e:
            self.logger.error(f"REST API error: {e}")
            return None

    def _find_resource_id(
        self,
        endpoint: str,
        filter_key: str,
        filter_value: str,
        cache: dict[str, str],
        use_cache: bool = True,
        timeout: int | None = None
    ) -> str | None:
        """Find RouterOS resource ID by filter key/value.

        Generic method for looking up resource IDs with caching support.
        Used by queue and mangle rule lookups.

        Args:
            endpoint: REST API endpoint (e.g., "queue/tree", "ip/firewall/mangle")
            filter_key: Filter parameter name (e.g., "name", "comment")
            filter_value: Value to filter by
            cache: Cache dict to use for this resource type
            use_cache: Whether to check/update cache (default True)
            timeout: Request timeout in seconds

        Returns:
            Resource ID (e.g., "*1") or None if not found
        """
        timeout_val = timeout if timeout is not None else self.timeout

        # Check cache first
        if use_cache and filter_value in cache:
            self.logger.debug(f"Resource ID cache hit: {filter_value} -> {cache[filter_value]}")
            return cache[filter_value]

        url = f"{self.base_url}/{endpoint}"

        try:
            resp = self._session.get(url, params={filter_key: filter_value}, timeout=timeout_val)

            if resp.ok and resp.json():
                items = resp.json()
                if items:
                    resource_id = items[0].get('.id')
                    # Cache the result
                    if resource_id and use_cache:
                        cache[filter_value] = resource_id
                        self.logger.debug(f"Resource ID cached: {filter_value} -> {resource_id}")
                    return resource_id

            return None

        except requests.RequestException as e:
            self.logger.error(f"REST API error finding resource: {e}")
            return None

    def _find_queue_id(self, queue_name: str, use_cache: bool = True, timeout: int | None = None) -> str | None:
        """Find queue tree ID by name.

        Args:
            queue_name: Name of the queue
            use_cache: Whether to use cached ID (default True)
            timeout: Request timeout in seconds

        Returns:
            Queue ID (e.g., "*1") or None if not found
        """
        return self._find_resource_id(
            endpoint="queue/tree",
            filter_key="name",
            filter_value=queue_name,
            cache=self._queue_id_cache,
            use_cache=use_cache,
            timeout=timeout
        )

    def _find_mangle_rule_id(self, comment: str, use_cache: bool = True, timeout: int | None = None) -> str | None:
        """Find mangle rule ID by comment.

        Args:
            comment: Comment of the rule
            use_cache: Whether to use cached ID (default True)
            timeout: Request timeout in seconds

        Returns:
            Rule ID or None if not found
        """
        return self._find_resource_id(
            endpoint="ip/firewall/mangle",
            filter_key="comment",
            filter_value=comment,
            cache=self._mangle_id_cache,
            use_cache=use_cache,
            timeout=timeout
        )

    def set_queue_limit(self, queue_name: str, max_limit: int) -> bool:
        """Set queue tree max-limit directly via REST API.

        Convenience method that bypasses CLI command parsing.

        Args:
            queue_name: Name of the queue
            max_limit: Bandwidth limit in bits per second

        Returns:
            True if successful, False otherwise
        """
        queue_id = self._find_queue_id(queue_name)
        if queue_id is None:
            self.logger.error(f"Queue not found: {queue_name}")
            return False

        url = f"{self.base_url}/queue/tree/{queue_id}"

        try:
            resp = self._session.patch(
                url,
                json={"max-limit": str(max_limit)},
                timeout=self.timeout
            )

            if resp.ok:
                self.logger.debug(f"Queue {queue_name} limit set to {max_limit}")
                return True
            else:
                self.logger.error(f"Failed to set queue limit: {resp.status_code}")
                return False

        except requests.RequestException as e:
            self.logger.error(f"REST API error: {e}")
            return False

    def get_queue_stats(self, queue_name: str) -> dict | None:
        """Get queue statistics.

        Args:
            queue_name: Name of the queue

        Returns:
            Dict with queue stats or None on failure
        """
        url = f"{self.base_url}/queue/tree"

        try:
            resp = self._session.get(url, params={"name": queue_name}, timeout=self.timeout)

            if resp.ok and resp.json():
                items = resp.json()
                if items:
                    return items[0]

            return None

        except requests.RequestException as e:
            self.logger.error(f"REST API error: {e}")
            return None

    def test_connection(self) -> bool:
        """Test connectivity to the router REST API.

        Returns:
            True if API is reachable and authenticated, False otherwise
        """
        try:
            resp = self._session.get(
                f"{self.base_url}/system/resource",
                timeout=5
            )
            return resp.ok
        except requests.RequestException:
            return False

    def close(self) -> None:
        """Close the REST API session.

        Should be called when the daemon shuts down to clean up resources.
        Safe to call multiple times.
        """
        if self._session is not None:
            try:
                self._session.close()
                self.logger.debug(f"REST API session closed for {self.host}")
            except Exception as e:
                self.logger.debug(f"Error closing REST session: {e}")
            finally:
                self._session = None
