"""Tests for RouterOS REST API client.

BACK-01, BACK-02: Comprehensive coverage for REST API client including:
- Constructor and from_config initialization
- Command parsing and execution
- Queue tree operations
- Mangle rule operations
- Resource ID lookup and caching
- High-level API methods
- Connection testing and cleanup
"""

import logging
import os
from unittest.mock import MagicMock, patch

import pytest
import requests

from wanctl.routeros_rest import RouterOSREST


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_session():
    """Create mock requests Session with standard response."""
    session = MagicMock(spec=requests.Session)
    response = MagicMock()
    response.ok = True
    response.json.return_value = []
    session.get.return_value = response
    session.patch.return_value = response
    session.post.return_value = response
    return session


@pytest.fixture
def rest_client(mock_session):
    """Create REST client with mocked session."""
    with patch("wanctl.routeros_rest.requests.Session") as mock_class:
        mock_class.return_value = mock_session
        client = RouterOSREST(
            host="192.168.1.1",
            user="admin",
            password="test",  # pragma: allowlist secret
        )
    client._session = mock_session
    return client


@pytest.fixture
def mock_logger():
    """Create mock logger for testing."""
    return MagicMock(spec=logging.Logger)


# =============================================================================
# TestRouterOSRESTInit - Constructor Tests
# =============================================================================


class TestRouterOSRESTInit:
    """Tests for RouterOSREST constructor and initialization."""

    def test_default_port_443_uses_https(self):
        """Default port 443 creates https URL."""
        with patch("wanctl.routeros_rest.requests.Session"):
            client = RouterOSREST(
                host="192.168.1.1",
                user="admin",
                password="test",  # pragma: allowlist secret
            )
        assert client.base_url == "https://192.168.1.1:443/rest"

    def test_custom_port_80_uses_http(self):
        """Port 80 creates http URL."""
        with patch("wanctl.routeros_rest.requests.Session"):
            client = RouterOSREST(
                host="192.168.1.1",
                user="admin",
                password="test",  # pragma: allowlist secret
                port=80,
            )
        assert client.base_url == "http://192.168.1.1:80/rest"

    def test_session_auth_configured(self):
        """Session has correct (user, password) auth."""
        mock_session = MagicMock()
        with patch("wanctl.routeros_rest.requests.Session", return_value=mock_session):
            RouterOSREST(
                host="192.168.1.1",
                user="admin",
                password="secret123",  # pragma: allowlist secret
            )
        assert mock_session.auth == ("admin", "secret123")

    def test_session_verify_ssl_false_default(self):
        """verify=False by default."""
        mock_session = MagicMock()
        with patch("wanctl.routeros_rest.requests.Session", return_value=mock_session):
            RouterOSREST(
                host="192.168.1.1",
                user="admin",
                password="test",  # pragma: allowlist secret
            )
        assert mock_session.verify is False

    def test_session_verify_ssl_true(self):
        """verify=True when configured."""
        mock_session = MagicMock()
        with patch("wanctl.routeros_rest.requests.Session", return_value=mock_session):
            RouterOSREST(
                host="192.168.1.1",
                user="admin",
                password="test",  # pragma: allowlist secret
                verify_ssl=True,
            )
        assert mock_session.verify is True

    def test_custom_timeout(self):
        """Custom timeout stored correctly."""
        with patch("wanctl.routeros_rest.requests.Session"):
            client = RouterOSREST(
                host="192.168.1.1",
                user="admin",
                password="test",  # pragma: allowlist secret
                timeout=30,
            )
        assert client.timeout == 30

    def test_logger_provided(self):
        """Uses provided logger."""
        custom_logger = MagicMock(spec=logging.Logger)
        with patch("wanctl.routeros_rest.requests.Session"):
            client = RouterOSREST(
                host="192.168.1.1",
                user="admin",
                password="test",  # pragma: allowlist secret
                logger=custom_logger,
            )
        assert client.logger is custom_logger

    def test_logger_default(self):
        """Creates default logger when none provided."""
        with patch("wanctl.routeros_rest.requests.Session"):
            client = RouterOSREST(
                host="192.168.1.1",
                user="admin",
                password="test",  # pragma: allowlist secret
            )
        assert client.logger is not None
        assert isinstance(client.logger, logging.Logger)

    def test_caches_initialized_empty(self):
        """_queue_id_cache and _mangle_id_cache start empty."""
        with patch("wanctl.routeros_rest.requests.Session"):
            client = RouterOSREST(
                host="192.168.1.1",
                user="admin",
                password="test",  # pragma: allowlist secret
            )
        assert client._queue_id_cache == {}
        assert client._mangle_id_cache == {}


# =============================================================================
# TestFromConfig - from_config Class Method Tests
# =============================================================================


class TestFromConfig:
    """Tests for RouterOSREST.from_config class method."""

    def test_from_config_basic(self, mock_logger):
        """Creates client from config object."""
        config = MagicMock()
        config.router_host = "10.0.0.1"
        config.router_user = "api_user"
        config.router_password = "api_pass"  # pragma: allowlist secret
        config.router_port = 443
        config.router_verify_ssl = False
        config.timeout_ssh_command = 20

        with patch("wanctl.routeros_rest.requests.Session"):
            client = RouterOSREST.from_config(config, mock_logger)

        assert client.host == "10.0.0.1"
        assert client.user == "api_user"
        assert client.password == "api_pass"  # pragma: allowlist secret
        assert client.port == 443
        assert client.timeout == 20

    def test_from_config_env_password(self, mock_logger):
        """Expands ${VAR} password from environment."""
        config = MagicMock()
        config.router_host = "10.0.0.1"
        config.router_user = "admin"
        config.router_password = "${ROUTER_PASSWORD}"
        config.router_port = 443
        config.router_verify_ssl = False
        config.timeout_ssh_command = 15

        with patch.dict(os.environ, {"ROUTER_PASSWORD": "env_secret"}):
            with patch("wanctl.routeros_rest.requests.Session"):
                client = RouterOSREST.from_config(config, mock_logger)

        assert client.password == "env_secret"  # pragma: allowlist secret

    def test_from_config_default_port(self, mock_logger):
        """Uses 443 when not specified."""
        config = MagicMock(spec=[])
        config.router_host = "10.0.0.1"
        config.router_user = "admin"
        config.router_password = "pass"  # pragma: allowlist secret

        with patch("wanctl.routeros_rest.requests.Session"):
            client = RouterOSREST.from_config(config, mock_logger)

        assert client.port == 443

    def test_from_config_custom_timeout(self, mock_logger):
        """Uses timeout_ssh_command from config."""
        config = MagicMock()
        config.router_host = "10.0.0.1"
        config.router_user = "admin"
        config.router_password = "pass"  # pragma: allowlist secret
        config.router_port = 443
        config.router_verify_ssl = False
        config.timeout_ssh_command = 45

        with patch("wanctl.routeros_rest.requests.Session"):
            client = RouterOSREST.from_config(config, mock_logger)

        assert client.timeout == 45


# =============================================================================
# TestRouterOSRESTRunCmd - run_cmd Method Tests
# =============================================================================


class TestRouterOSRESTRunCmd:
    """Tests for RouterOSREST.run_cmd method."""

    def test_run_cmd_success_returns_json(self, rest_client, mock_session):
        """Successful response returns (0, json_string, '')."""
        response = MagicMock()
        response.ok = True
        response.json.return_value = [{"name": "WAN-Download", ".id": "*1"}]
        mock_session.get.return_value = response

        rc, stdout, stderr = rest_client.run_cmd('/queue tree print where name="WAN-Download"')

        assert rc == 0
        assert '"name": "WAN-Download"' in stdout
        assert stderr == ""

    def test_run_cmd_network_error_in_handler(self, rest_client, mock_session):
        """RequestException in handler returns (1, '', 'Command failed')."""
        # When RequestException occurs inside a handler, it catches it and returns None,
        # which results in "Command failed" from run_cmd
        mock_session.get.side_effect = requests.RequestException("Connection refused")

        rc, stdout, stderr = rest_client.run_cmd('/queue tree print where name="WAN-Download"')

        assert rc == 1
        assert stdout == ""
        assert stderr == "Command failed"

    def test_run_cmd_network_error_propagated(self, rest_client):
        """RequestException propagating to run_cmd returns (1, '', error_message)."""
        # Mock _execute_command to raise exception directly
        with patch.object(
            rest_client, "_execute_command", side_effect=requests.RequestException("Connection refused")
        ):
            rc, stdout, stderr = rest_client.run_cmd("/queue tree print")

        assert rc == 1
        assert stdout == ""
        assert "Connection refused" in stderr

    def test_run_cmd_unexpected_error(self, rest_client, mock_session):
        """Generic exception returns (1, '', error_message)."""
        mock_session.get.side_effect = ValueError("Unexpected error")

        rc, stdout, stderr = rest_client.run_cmd('/queue tree print where name="WAN-Download"')

        assert rc == 1
        assert stdout == ""
        assert "Unexpected error" in stderr

    def test_run_cmd_uses_custom_timeout(self, rest_client, mock_session):
        """Timeout parameter passed to _execute_command."""
        response = MagicMock()
        response.ok = True
        response.json.return_value = []
        mock_session.get.return_value = response

        rest_client.run_cmd('/queue tree print where name="test"', timeout=30)

        # Check that the GET request used the custom timeout
        mock_session.get.assert_called_once()
        call_kwargs = mock_session.get.call_args[1]
        assert call_kwargs["timeout"] == 30

    def test_run_cmd_unsupported_command(self, rest_client):
        """Unsupported commands return (1, '', 'Command failed')."""
        rc, stdout, stderr = rest_client.run_cmd("/system reboot")

        assert rc == 1
        assert stdout == ""
        assert stderr == "Command failed"

    def test_run_cmd_batched_commands(self, rest_client, mock_session):
        """Commands with semicolons execute in sequence."""
        # Mock the queue ID lookup and PATCH for queue tree set commands
        get_response = MagicMock()
        get_response.ok = True
        get_response.json.return_value = [{"name": "WAN-Download", ".id": "*1"}]
        mock_session.get.return_value = get_response

        patch_response = MagicMock()
        patch_response.ok = True
        mock_session.patch.return_value = patch_response

        cmd = '/queue tree set [find name="WAN-Download"] max-limit=100; /queue tree set [find name="WAN-Download"] max-limit=200'
        rc, stdout, stderr = rest_client.run_cmd(cmd)

        assert rc == 0
        # PATCH should have been called twice (once for each command)
        assert mock_session.patch.call_count == 2


# =============================================================================
# TestParsing - Parsing Helper Tests
# =============================================================================


class TestParsing:
    """Tests for command parsing helper methods."""

    def test_parse_find_name_extracts_name(self, rest_client):
        """'[find name="WAN-Download"]' -> 'WAN-Download'."""
        cmd = '/queue tree set [find name="WAN-Download"] max-limit=500000000'
        result = rest_client._parse_find_name(cmd)
        assert result == "WAN-Download"

    def test_parse_find_name_no_match(self, rest_client):
        """Returns None when pattern not found."""
        cmd = "/queue tree print"
        result = rest_client._parse_find_name(cmd)
        assert result is None

    def test_parse_find_comment_extracts_comment(self, rest_client):
        """'[find comment="steering"]' -> 'steering'."""
        cmd = '/ip firewall mangle enable [find comment="steering"]'
        result = rest_client._parse_find_comment(cmd)
        assert result == "steering"

    def test_parse_find_comment_no_match(self, rest_client):
        """Returns None when pattern not found."""
        cmd = "/ip firewall mangle print"
        result = rest_client._parse_find_comment(cmd)
        assert result is None

    def test_parse_parameters_extracts_queue(self, rest_client):
        """'queue=cake-down' extracted."""
        cmd = '/queue tree set [find name="WAN"] queue=cake-down'
        result = rest_client._parse_parameters(cmd)
        assert result.get("queue") == "cake-down"

    def test_parse_parameters_extracts_max_limit(self, rest_client):
        """'max-limit=500000000' extracted."""
        cmd = '/queue tree set [find name="WAN"] max-limit=500000000'
        result = rest_client._parse_parameters(cmd)
        assert result.get("max-limit") == "500000000"

    def test_parse_parameters_extracts_both(self, rest_client):
        """Multiple params extracted."""
        cmd = '/queue tree set [find name="WAN"] queue=cake-down max-limit=500000000'
        result = rest_client._parse_parameters(cmd)
        assert result.get("queue") == "cake-down"
        assert result.get("max-limit") == "500000000"

    def test_parse_parameters_empty_cmd(self, rest_client):
        """Returns empty dict for commands without parameters."""
        cmd = "/queue tree print"
        result = rest_client._parse_parameters(cmd)
        assert result == {}


# =============================================================================
# TestQueueTreeSet - Queue Tree Set Handler Tests
# =============================================================================


class TestQueueTreeSet:
    """Tests for _handle_queue_tree_set method."""

    def test_handle_queue_tree_set_success(self, rest_client, mock_session):
        """Updates queue with PATCH."""
        # Mock queue ID lookup
        get_response = MagicMock()
        get_response.ok = True
        get_response.json.return_value = [{"name": "WAN-Download", ".id": "*1"}]
        mock_session.get.return_value = get_response

        # Mock PATCH response
        patch_response = MagicMock()
        patch_response.ok = True
        mock_session.patch.return_value = patch_response

        cmd = '/queue tree set [find name="WAN-Download"] max-limit=500000000'
        result = rest_client._handle_queue_tree_set(cmd)

        assert result is not None
        assert result["status"] == "ok"
        assert result["queue"] == "WAN-Download"
        mock_session.patch.assert_called_once()

    def test_handle_queue_tree_set_no_name(self, rest_client):
        """Returns None when name missing."""
        cmd = "/queue tree set max-limit=500000000"
        result = rest_client._handle_queue_tree_set(cmd)
        assert result is None

    def test_handle_queue_tree_set_no_params(self, rest_client):
        """Returns None when no params."""
        cmd = '/queue tree set [find name="WAN-Download"]'
        result = rest_client._handle_queue_tree_set(cmd)
        assert result is None

    def test_handle_queue_tree_set_queue_not_found(self, rest_client, mock_session):
        """Returns None when queue doesn't exist."""
        # Mock queue ID lookup returning empty
        get_response = MagicMock()
        get_response.ok = True
        get_response.json.return_value = []
        mock_session.get.return_value = get_response

        cmd = '/queue tree set [find name="NonExistent"] max-limit=500000000'
        result = rest_client._handle_queue_tree_set(cmd)

        assert result is None

    def test_handle_queue_tree_set_patch_failure(self, rest_client, mock_session):
        """Returns None on HTTP error."""
        # Mock queue ID lookup success
        get_response = MagicMock()
        get_response.ok = True
        get_response.json.return_value = [{"name": "WAN-Download", ".id": "*1"}]
        mock_session.get.return_value = get_response

        # Mock PATCH failure
        patch_response = MagicMock()
        patch_response.ok = False
        patch_response.status_code = 400
        patch_response.text = "Bad Request"
        mock_session.patch.return_value = patch_response

        cmd = '/queue tree set [find name="WAN-Download"] max-limit=500000000'
        result = rest_client._handle_queue_tree_set(cmd)

        assert result is None
