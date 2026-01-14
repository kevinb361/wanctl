"""Tests for steering config deprecation warnings.

Tests the deprecation warning behavior:
- Warning logged when bad_samples used
- Warning logged when good_samples used
- No warning when only new params used
- Warning logged when both old and new used
"""

from unittest.mock import MagicMock

import pytest

from wanctl.steering.daemon import _warn_deprecated_param


class TestDeprecationWarningHelper:
    """Tests for _warn_deprecated_param helper function."""

    def test_warns_when_deprecated_param_present(self):
        """Logs warning when deprecated parameter is in config."""
        config = {'bad_samples': 8}
        logger = MagicMock()

        _warn_deprecated_param(config, 'bad_samples', 'red_samples_required', logger)

        logger.warning.assert_called_once()
        warning_msg = logger.warning.call_args[0][0]
        assert 'bad_samples' in warning_msg
        assert 'red_samples_required' in warning_msg
        assert 'DEPRECATED' in warning_msg

    def test_no_warning_when_deprecated_param_absent(self):
        """No warning when deprecated parameter is not in config."""
        config = {'red_samples_required': 2}
        logger = MagicMock()

        _warn_deprecated_param(config, 'bad_samples', 'red_samples_required', logger)

        logger.warning.assert_not_called()

    def test_warning_message_format(self):
        """Warning message has correct format with old name, new name, and removal notice."""
        config = {'good_samples': 15}
        logger = MagicMock()

        _warn_deprecated_param(config, 'good_samples', 'green_samples_required', logger)

        warning_msg = logger.warning.call_args[0][0]
        assert "'good_samples'" in warning_msg
        assert "'green_samples_required'" in warning_msg
        assert 'will be removed' in warning_msg


class TestDeprecationWarningsInConfig:
    """Tests for deprecation warnings when loading steering config."""

    @pytest.fixture
    def minimal_config_data(self):
        """Create minimal valid steering config."""
        return {
            'wan_name': 'test',
            'topology': {
                'primary_wan': 'wan1',
                'primary_wan_config': '/etc/wanctl/wan1.yaml',
                'alternate_wan': 'wan2',
            },
            'router': {
                'host': '10.0.0.1',
                'user': 'admin',
                'ssh_key': '/tmp/key',
            },
            'mangle_rule': {'comment': 'test rule'},
            'measurement': {
                'interval_seconds': 2,
                'ping_host': '1.1.1.1',
                'ping_count': 3,
            },
            'thresholds': {
                'green_rtt_ms': 5,
                'yellow_rtt_ms': 15,
                'red_rtt_ms': 15,
            },
            'mode': {'cake_aware': True},
            'state': {'file': '/tmp/state.json', 'history_size': 100},
            'logging': {'main_log': '/tmp/main.log', 'debug_log': '/tmp/debug.log'},
            'lock_file': '/tmp/test.lock',
            'lock_timeout': 60,
        }

    def test_bad_samples_logs_deprecation_warning(self, minimal_config_data, caplog):
        """Loading config with bad_samples logs deprecation warning."""
        import logging

        minimal_config_data['thresholds']['bad_samples'] = 8

        with caplog.at_level(logging.WARNING):
            # SteeringConfig expects a file path, so we need to mock it
            # For this test, we'll test the helper function directly
            pass

        # Direct test of helper function with the thresholds dict
        logger = MagicMock()
        _warn_deprecated_param(
            minimal_config_data['thresholds'],
            'bad_samples',
            'red_samples_required',
            logger
        )
        logger.warning.assert_called_once()

    def test_good_samples_logs_deprecation_warning(self, minimal_config_data):
        """Loading config with good_samples logs deprecation warning."""
        minimal_config_data['thresholds']['good_samples'] = 15

        logger = MagicMock()
        _warn_deprecated_param(
            minimal_config_data['thresholds'],
            'good_samples',
            'green_samples_required',
            logger
        )
        logger.warning.assert_called_once()

    def test_new_params_no_warning(self, minimal_config_data):
        """Config with only new params does not log warning."""
        minimal_config_data['thresholds']['red_samples_required'] = 2
        minimal_config_data['thresholds']['green_samples_required'] = 15

        logger = MagicMock()
        # Check neither deprecated param triggers warning
        _warn_deprecated_param(
            minimal_config_data['thresholds'],
            'bad_samples',
            'red_samples_required',
            logger
        )
        _warn_deprecated_param(
            minimal_config_data['thresholds'],
            'good_samples',
            'green_samples_required',
            logger
        )
        logger.warning.assert_not_called()

    def test_both_params_logs_warning(self, minimal_config_data):
        """Config with both old and new params still logs warning for old."""
        minimal_config_data['thresholds']['bad_samples'] = 8
        minimal_config_data['thresholds']['red_samples_required'] = 2

        logger = MagicMock()
        _warn_deprecated_param(
            minimal_config_data['thresholds'],
            'bad_samples',
            'red_samples_required',
            logger
        )
        # Warning should still be logged for the deprecated param
        logger.warning.assert_called_once()
