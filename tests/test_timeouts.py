"""Unit tests for timeout configuration utilities."""

import pytest

from wanctl.timeouts import (
    DEFAULT_AUTORATE_SSH_TIMEOUT,
    DEFAULT_STEERING_SSH_TIMEOUT,
    DEFAULT_CALIBRATE_SSH_TIMEOUT,
    DEFAULT_AUTORATE_PING_TIMEOUT,
    DEFAULT_STEERING_PING_TOTAL_TIMEOUT,
    DEFAULT_CALIBRATE_PING_TIMEOUT,
    TIMEOUT_QUICK,
    TIMEOUT_STANDARD,
    TIMEOUT_LONG,
    DEFAULT_LOCK_TIMEOUT,
    get_ssh_timeout,
    get_ping_timeout,
)


class TestTimeoutConstants:
    """Test timeout constant values."""

    def test_ssh_timeout_autorate(self):
        """Test autorate SSH timeout is reasonable."""
        assert DEFAULT_AUTORATE_SSH_TIMEOUT == 15
        assert isinstance(DEFAULT_AUTORATE_SSH_TIMEOUT, int)
        assert DEFAULT_AUTORATE_SSH_TIMEOUT > 0

    def test_ssh_timeout_steering(self):
        """Test steering SSH timeout is reasonable."""
        assert DEFAULT_STEERING_SSH_TIMEOUT == 30
        assert isinstance(DEFAULT_STEERING_SSH_TIMEOUT, int)
        assert DEFAULT_STEERING_SSH_TIMEOUT > 0

    def test_ssh_timeout_calibrate(self):
        """Test calibrate SSH timeout is reasonable."""
        assert DEFAULT_CALIBRATE_SSH_TIMEOUT == 10
        assert isinstance(DEFAULT_CALIBRATE_SSH_TIMEOUT, int)
        assert DEFAULT_CALIBRATE_SSH_TIMEOUT > 0

    def test_ping_timeout_autorate(self):
        """Test autorate ping timeout is reasonable."""
        assert DEFAULT_AUTORATE_PING_TIMEOUT == 1
        assert isinstance(DEFAULT_AUTORATE_PING_TIMEOUT, int)
        assert DEFAULT_AUTORATE_PING_TIMEOUT > 0

    def test_ping_timeout_steering(self):
        """Test steering ping total timeout is reasonable."""
        assert DEFAULT_STEERING_PING_TOTAL_TIMEOUT == 10
        assert isinstance(DEFAULT_STEERING_PING_TOTAL_TIMEOUT, int)
        assert DEFAULT_STEERING_PING_TOTAL_TIMEOUT > 0

    def test_ping_timeout_calibrate(self):
        """Test calibrate ping timeout is reasonable."""
        assert DEFAULT_CALIBRATE_PING_TIMEOUT == 15
        assert isinstance(DEFAULT_CALIBRATE_PING_TIMEOUT, int)
        assert DEFAULT_CALIBRATE_PING_TIMEOUT > 0

    def test_quick_timeout(self):
        """Test TIMEOUT_QUICK is reasonable."""
        assert TIMEOUT_QUICK == 5
        assert TIMEOUT_QUICK < TIMEOUT_STANDARD

    def test_standard_timeout(self):
        """Test TIMEOUT_STANDARD is reasonable."""
        assert TIMEOUT_STANDARD == 10
        assert TIMEOUT_STANDARD < TIMEOUT_LONG

    def test_long_timeout(self):
        """Test TIMEOUT_LONG is reasonable."""
        assert TIMEOUT_LONG == 30
        assert TIMEOUT_LONG > TIMEOUT_STANDARD

    def test_lock_timeout(self):
        """Test lock timeout is reasonable."""
        assert DEFAULT_LOCK_TIMEOUT == 300
        assert DEFAULT_LOCK_TIMEOUT > 60  # At least 1 minute

    def test_timeout_ordering(self):
        """Test timeouts are reasonably ordered."""
        assert TIMEOUT_QUICK < TIMEOUT_STANDARD < TIMEOUT_LONG
        assert DEFAULT_AUTORATE_SSH_TIMEOUT < DEFAULT_STEERING_SSH_TIMEOUT


class TestGetSshTimeout:
    """Test get_ssh_timeout function."""

    def test_autorate_ssh_timeout(self):
        """Test getting autorate SSH timeout."""
        timeout = get_ssh_timeout("autorate")
        assert timeout == DEFAULT_AUTORATE_SSH_TIMEOUT

    def test_steering_ssh_timeout(self):
        """Test getting steering SSH timeout."""
        timeout = get_ssh_timeout("steering")
        assert timeout == DEFAULT_STEERING_SSH_TIMEOUT

    def test_calibrate_ssh_timeout(self):
        """Test getting calibrate SSH timeout."""
        timeout = get_ssh_timeout("calibrate")
        assert timeout == DEFAULT_CALIBRATE_SSH_TIMEOUT

    def test_unknown_component_raises_error(self):
        """Test that unknown component raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_ssh_timeout("unknown")
        assert "unknown" in str(exc_info.value).lower()

    def test_case_sensitive_component(self):
        """Test that component names are case-sensitive."""
        with pytest.raises(ValueError):
            get_ssh_timeout("AUTORATE")  # Must be lowercase

    def test_return_type_is_int(self):
        """Test that return value is always int."""
        for component in ["autorate", "steering", "calibrate"]:
            timeout = get_ssh_timeout(component)
            assert isinstance(timeout, int)
            assert timeout > 0


class TestGetPingTimeout:
    """Test get_ping_timeout function."""

    def test_autorate_ping_timeout(self):
        """Test getting autorate ping timeout."""
        timeout = get_ping_timeout("autorate")
        assert timeout == DEFAULT_AUTORATE_PING_TIMEOUT

    def test_autorate_ping_timeout_total_flag_ignored(self):
        """Test that total flag doesn't affect autorate ping timeout."""
        timeout_normal = get_ping_timeout("autorate", total=False)
        timeout_total = get_ping_timeout("autorate", total=True)
        assert timeout_normal == timeout_total

    def test_steering_ping_timeout_per_ping(self):
        """Test getting steering ping timeout for single ping."""
        timeout = get_ping_timeout("steering", total=False)
        assert timeout > 0
        assert timeout < DEFAULT_STEERING_PING_TOTAL_TIMEOUT

    def test_steering_ping_timeout_total(self):
        """Test getting steering ping timeout for all pings."""
        timeout = get_ping_timeout("steering", total=True)
        assert timeout == DEFAULT_STEERING_PING_TOTAL_TIMEOUT

    def test_calibrate_ping_timeout(self):
        """Test getting calibrate ping timeout."""
        timeout = get_ping_timeout("calibrate")
        assert timeout == DEFAULT_CALIBRATE_PING_TIMEOUT

    def test_unknown_component_raises_error(self):
        """Test that unknown component raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_ping_timeout("unknown")
        assert "unknown" in str(exc_info.value).lower()

    def test_return_type_is_int(self):
        """Test that return value is always int."""
        for component in ["autorate", "steering", "calibrate"]:
            timeout = get_ping_timeout(component)
            assert isinstance(timeout, int)
            assert timeout > 0

    def test_per_ping_less_than_total(self):
        """Test that per-ping timeout is less than total for steering."""
        per_ping = get_ping_timeout("steering", total=False)
        total = get_ping_timeout("steering", total=True)
        assert per_ping <= total
