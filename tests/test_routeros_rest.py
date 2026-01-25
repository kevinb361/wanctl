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
