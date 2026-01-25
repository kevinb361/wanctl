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


# =============================================================================
# TestQueueResetCounters - Queue Reset Counters Handler Tests
# =============================================================================


class TestQueueResetCounters:
    """Tests for _handle_queue_reset_counters method."""

    def test_handle_queue_reset_counters_success(self, rest_client, mock_session):
        """POST to reset-counters endpoint."""
        # Mock queue ID lookup
        get_response = MagicMock()
        get_response.ok = True
        get_response.json.return_value = [{"name": "WAN-Download", ".id": "*1"}]
        mock_session.get.return_value = get_response

        # Mock POST response
        post_response = MagicMock()
        post_response.ok = True
        mock_session.post.return_value = post_response

        cmd = '/queue tree reset-counters [find name="WAN-Download"]'
        result = rest_client._handle_queue_reset_counters(cmd)

        assert result is not None
        assert result["status"] == "ok"
        assert result["queue"] == "WAN-Download"
        mock_session.post.assert_called_once()

    def test_handle_queue_reset_counters_find_name(self, rest_client, mock_session):
        """Parses [find name="..."]."""
        get_response = MagicMock()
        get_response.ok = True
        get_response.json.return_value = [{"name": "WAN-Upload", ".id": "*2"}]
        mock_session.get.return_value = get_response

        post_response = MagicMock()
        post_response.ok = True
        mock_session.post.return_value = post_response

        cmd = '/queue tree reset-counters [find name="WAN-Upload"]'
        result = rest_client._handle_queue_reset_counters(cmd)

        assert result is not None
        assert result["queue"] == "WAN-Upload"

    def test_handle_queue_reset_counters_where_name(self, rest_client, mock_session):
        """Parses where name="..." format."""
        get_response = MagicMock()
        get_response.ok = True
        get_response.json.return_value = [{"name": "WAN-Download", ".id": "*1"}]
        mock_session.get.return_value = get_response

        post_response = MagicMock()
        post_response.ok = True
        mock_session.post.return_value = post_response

        cmd = '/queue tree reset-counters where name="WAN-Download"'
        result = rest_client._handle_queue_reset_counters(cmd)

        assert result is not None
        assert result["queue"] == "WAN-Download"

    def test_handle_queue_reset_counters_no_name(self, rest_client):
        """Returns None when no name found."""
        cmd = "/queue tree reset-counters"
        result = rest_client._handle_queue_reset_counters(cmd)
        assert result is None

    def test_handle_queue_reset_counters_queue_not_found(self, rest_client, mock_session):
        """Returns None when queue doesn't exist."""
        get_response = MagicMock()
        get_response.ok = True
        get_response.json.return_value = []
        mock_session.get.return_value = get_response

        cmd = '/queue tree reset-counters [find name="NonExistent"]'
        result = rest_client._handle_queue_reset_counters(cmd)

        assert result is None

    def test_handle_queue_reset_counters_post_failure(self, rest_client, mock_session):
        """Returns None on HTTP error."""
        get_response = MagicMock()
        get_response.ok = True
        get_response.json.return_value = [{"name": "WAN-Download", ".id": "*1"}]
        mock_session.get.return_value = get_response

        post_response = MagicMock()
        post_response.ok = False
        post_response.status_code = 500
        post_response.text = "Internal Error"
        mock_session.post.return_value = post_response

        cmd = '/queue tree reset-counters [find name="WAN-Download"]'
        result = rest_client._handle_queue_reset_counters(cmd)

        assert result is None


# =============================================================================
# TestQueueTreePrint - Queue Tree Print Handler Tests
# =============================================================================


class TestQueueTreePrint:
    """Tests for _handle_queue_tree_print method."""

    def test_handle_queue_tree_print_all(self, rest_client, mock_session):
        """GET without filter."""
        response = MagicMock()
        response.ok = True
        response.json.return_value = [
            {"name": "WAN-Download", ".id": "*1"},
            {"name": "WAN-Upload", ".id": "*2"},
        ]
        mock_session.get.return_value = response

        cmd = "/queue tree print"
        result = rest_client._handle_queue_tree_print(cmd)

        assert result is not None
        assert len(result) == 2
        mock_session.get.assert_called_once()

    def test_handle_queue_tree_print_filtered(self, rest_client, mock_session):
        """GET with name param."""
        response = MagicMock()
        response.ok = True
        response.json.return_value = [{"name": "WAN-Download", ".id": "*1"}]
        mock_session.get.return_value = response

        cmd = '/queue tree print where name="WAN-Download"'
        result = rest_client._handle_queue_tree_print(cmd)

        assert result is not None
        assert len(result) == 1
        call_kwargs = mock_session.get.call_args[1]
        assert call_kwargs["params"]["name"] == "WAN-Download"

    def test_handle_queue_tree_print_failure(self, rest_client, mock_session):
        """Returns None on HTTP error."""
        response = MagicMock()
        response.ok = False
        response.status_code = 500
        mock_session.get.return_value = response

        cmd = "/queue tree print"
        result = rest_client._handle_queue_tree_print(cmd)

        assert result is None


# =============================================================================
# TestMangleRule - Mangle Rule Handler Tests
# =============================================================================


class TestMangleRule:
    """Tests for _handle_mangle_rule method."""

    def test_handle_mangle_rule_enable(self, rest_client, mock_session):
        """Sets disabled=false."""
        get_response = MagicMock()
        get_response.ok = True
        get_response.json.return_value = [{"comment": "steering", ".id": "*1"}]
        mock_session.get.return_value = get_response

        patch_response = MagicMock()
        patch_response.ok = True
        mock_session.patch.return_value = patch_response

        cmd = '/ip firewall mangle enable [find comment="steering"]'
        result = rest_client._handle_mangle_rule(cmd)

        assert result is not None
        assert result["status"] == "ok"
        assert result["disabled"] == "false"
        mock_session.patch.assert_called_once()
        call_kwargs = mock_session.patch.call_args[1]
        assert call_kwargs["json"]["disabled"] == "false"

    def test_handle_mangle_rule_disable(self, rest_client, mock_session):
        """Sets disabled=true."""
        get_response = MagicMock()
        get_response.ok = True
        get_response.json.return_value = [{"comment": "steering", ".id": "*1"}]
        mock_session.get.return_value = get_response

        patch_response = MagicMock()
        patch_response.ok = True
        mock_session.patch.return_value = patch_response

        cmd = '/ip firewall mangle disable [find comment="steering"]'
        result = rest_client._handle_mangle_rule(cmd)

        assert result is not None
        assert result["disabled"] == "true"
        call_kwargs = mock_session.patch.call_args[1]
        assert call_kwargs["json"]["disabled"] == "true"

    def test_handle_mangle_rule_no_comment(self, rest_client):
        """Returns None when no comment."""
        cmd = "/ip firewall mangle enable"
        result = rest_client._handle_mangle_rule(cmd)
        assert result is None

    def test_handle_mangle_rule_unknown_action(self, rest_client):
        """Returns None when neither enable/disable."""
        cmd = '/ip firewall mangle print [find comment="steering"]'
        result = rest_client._handle_mangle_rule(cmd)
        assert result is None

    def test_handle_mangle_rule_not_found(self, rest_client, mock_session):
        """Returns None when rule doesn't exist."""
        get_response = MagicMock()
        get_response.ok = True
        get_response.json.return_value = []
        mock_session.get.return_value = get_response

        cmd = '/ip firewall mangle enable [find comment="nonexistent"]'
        result = rest_client._handle_mangle_rule(cmd)

        assert result is None

    def test_handle_mangle_rule_patch_failure(self, rest_client, mock_session):
        """Returns None on HTTP error."""
        get_response = MagicMock()
        get_response.ok = True
        get_response.json.return_value = [{"comment": "steering", ".id": "*1"}]
        mock_session.get.return_value = get_response

        patch_response = MagicMock()
        patch_response.ok = False
        patch_response.status_code = 403
        mock_session.patch.return_value = patch_response

        cmd = '/ip firewall mangle enable [find comment="steering"]'
        result = rest_client._handle_mangle_rule(cmd)

        assert result is None


# =============================================================================
# TestResourceIdLookup - Resource ID Lookup Tests
# =============================================================================


class TestResourceIdLookup:
    """Tests for _find_resource_id and related methods."""

    def test_find_resource_id_cache_hit(self, rest_client, mock_session):
        """Returns cached ID without API call."""
        # Pre-populate cache
        rest_client._queue_id_cache["WAN-Download"] = "*1"

        result = rest_client._find_queue_id("WAN-Download")

        assert result == "*1"
        # No API call should be made
        mock_session.get.assert_not_called()

    def test_find_resource_id_cache_miss_then_hit(self, rest_client, mock_session):
        """Caches result for next call."""
        response = MagicMock()
        response.ok = True
        response.json.return_value = [{"name": "WAN-Download", ".id": "*1"}]
        mock_session.get.return_value = response

        # First call - cache miss
        result1 = rest_client._find_queue_id("WAN-Download")
        assert result1 == "*1"
        assert mock_session.get.call_count == 1

        # Second call - cache hit
        result2 = rest_client._find_queue_id("WAN-Download")
        assert result2 == "*1"
        # Should not make another API call
        assert mock_session.get.call_count == 1

    def test_find_resource_id_no_cache(self, rest_client, mock_session):
        """use_cache=False always queries API."""
        response = MagicMock()
        response.ok = True
        response.json.return_value = [{"name": "WAN-Download", ".id": "*1"}]
        mock_session.get.return_value = response

        # Pre-populate cache
        rest_client._queue_id_cache["WAN-Download"] = "*old"

        # With use_cache=False, should query API despite cache
        result = rest_client._find_queue_id("WAN-Download", use_cache=False)

        assert result == "*1"
        mock_session.get.assert_called_once()

    def test_find_resource_id_not_found(self, rest_client, mock_session):
        """Returns None when resource missing."""
        response = MagicMock()
        response.ok = True
        response.json.return_value = []
        mock_session.get.return_value = response

        result = rest_client._find_queue_id("NonExistent")

        assert result is None

    def test_find_resource_id_network_error(self, rest_client, mock_session):
        """Returns None on RequestException."""
        mock_session.get.side_effect = requests.RequestException("Connection error")

        result = rest_client._find_queue_id("WAN-Download")

        assert result is None

    def test_find_queue_id_uses_queue_cache(self, rest_client, mock_session):
        """Uses _queue_id_cache."""
        response = MagicMock()
        response.ok = True
        response.json.return_value = [{"name": "WAN-Download", ".id": "*1"}]
        mock_session.get.return_value = response

        rest_client._find_queue_id("WAN-Download")

        assert "WAN-Download" in rest_client._queue_id_cache
        assert rest_client._queue_id_cache["WAN-Download"] == "*1"

    def test_find_mangle_rule_id_uses_mangle_cache(self, rest_client, mock_session):
        """Uses _mangle_id_cache."""
        response = MagicMock()
        response.ok = True
        response.json.return_value = [{"comment": "steering", ".id": "*5"}]
        mock_session.get.return_value = response

        rest_client._find_mangle_rule_id("steering")

        assert "steering" in rest_client._mangle_id_cache
        assert rest_client._mangle_id_cache["steering"] == "*5"


# =============================================================================
# TestHighLevelAPI - High-Level API Method Tests
# =============================================================================


class TestHighLevelAPI:
    """Tests for high-level API methods."""

    def test_set_queue_limit_success(self, rest_client, mock_session):
        """Updates queue limit via PATCH."""
        get_response = MagicMock()
        get_response.ok = True
        get_response.json.return_value = [{"name": "WAN-Download", ".id": "*1"}]
        mock_session.get.return_value = get_response

        patch_response = MagicMock()
        patch_response.ok = True
        mock_session.patch.return_value = patch_response

        result = rest_client.set_queue_limit("WAN-Download", 500_000_000)

        assert result is True
        mock_session.patch.assert_called_once()
        call_kwargs = mock_session.patch.call_args[1]
        assert call_kwargs["json"]["max-limit"] == "500000000"

    def test_set_queue_limit_queue_not_found(self, rest_client, mock_session):
        """Returns False when queue not found."""
        response = MagicMock()
        response.ok = True
        response.json.return_value = []
        mock_session.get.return_value = response

        result = rest_client.set_queue_limit("NonExistent", 500_000_000)

        assert result is False

    def test_set_queue_limit_patch_failure(self, rest_client, mock_session):
        """Returns False on HTTP error."""
        get_response = MagicMock()
        get_response.ok = True
        get_response.json.return_value = [{"name": "WAN-Download", ".id": "*1"}]
        mock_session.get.return_value = get_response

        patch_response = MagicMock()
        patch_response.ok = False
        patch_response.status_code = 400
        mock_session.patch.return_value = patch_response

        result = rest_client.set_queue_limit("WAN-Download", 500_000_000)

        assert result is False

    def test_get_queue_stats_success(self, rest_client, mock_session):
        """Returns queue dict from GET."""
        response = MagicMock()
        response.ok = True
        response.json.return_value = [
            {"name": "WAN-Download", ".id": "*1", "max-limit": "500000000", "rate": "100000"}
        ]
        mock_session.get.return_value = response

        result = rest_client.get_queue_stats("WAN-Download")

        assert result is not None
        assert result["name"] == "WAN-Download"
        assert result["max-limit"] == "500000000"

    def test_get_queue_stats_not_found(self, rest_client, mock_session):
        """Returns None when queue missing."""
        response = MagicMock()
        response.ok = True
        response.json.return_value = []
        mock_session.get.return_value = response

        result = rest_client.get_queue_stats("NonExistent")

        assert result is None

    def test_get_queue_stats_network_error(self, rest_client, mock_session):
        """Returns None on RequestException."""
        mock_session.get.side_effect = requests.RequestException("Connection error")

        result = rest_client.get_queue_stats("WAN-Download")

        assert result is None

    def test_test_connection_success(self, rest_client, mock_session):
        """Returns True on ok response."""
        response = MagicMock()
        response.ok = True
        mock_session.get.return_value = response

        result = rest_client.test_connection()

        assert result is True
        mock_session.get.assert_called_once()
        call_args = mock_session.get.call_args[0]
        assert "system/resource" in call_args[0]

    def test_test_connection_failure(self, rest_client, mock_session):
        """Returns False on network error."""
        mock_session.get.side_effect = requests.RequestException("Connection refused")

        result = rest_client.test_connection()

        assert result is False

    def test_close_closes_session(self, rest_client, mock_session):
        """Calls session.close()."""
        rest_client.close()

        mock_session.close.assert_called_once()
        assert rest_client._session is None

    def test_close_safe_when_no_session(self, rest_client):
        """Handles None session."""
        rest_client._session = None

        # Should not raise
        rest_client.close()

    def test_close_safe_on_exception(self, rest_client, mock_session):
        """Handles exception during close."""
        mock_session.close.side_effect = RuntimeError("Close failed")

        # Should not raise
        rest_client.close()
        assert rest_client._session is None
