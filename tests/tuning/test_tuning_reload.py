"""Tests for tuning config SIGUSR1 reload.

Tests _reload_tuning_config() on WANController: enabled/disabled transitions,
old->new logging, invalid config handling, and file read errors.
"""

import logging

import yaml

from wanctl.tuning.models import TuningState


class TestReloadTuningConfig:
    """Tests for WANController._reload_tuning_config()."""

    def _make_wc(self, mock_autorate_config, tmp_path, yaml_content=None):
        """Create a WANController with a real YAML config file."""
        from unittest.mock import MagicMock

        from wanctl.wan_controller import WANController

        config_file = tmp_path / "config.yaml"
        if yaml_content is not None:
            config_file.write_text(yaml.dump(yaml_content))
        else:
            config_file.write_text("wan_name: Test\n")

        mock_autorate_config.config_file_path = str(config_file)
        mock_autorate_config.tuning_config = None

        wc = WANController(
            wan_name="Test",
            config=mock_autorate_config,
            router=MagicMock(),
            rtt_measurement=MagicMock(),
            logger=logging.getLogger("test.tuning.reload"),
        )
        return wc

    def test_disabled_to_enabled_transition_logs_warning(
        self, mock_autorate_config, tmp_path, caplog
    ):
        """Enabling tuning via SIGUSR1 should log WARNING with old->new."""
        wc = self._make_wc(mock_autorate_config, tmp_path)
        assert wc._tuning_enabled is False

        # Write new config with tuning enabled
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"tuning": {"enabled": True}}))

        with caplog.at_level(logging.WARNING, logger="test.tuning.reload"):
            wc._reload_tuning_config()

        assert wc._tuning_enabled is True
        assert wc._tuning_state is not None
        assert "enabled=False->True" in caplog.text

    def test_enabled_to_disabled_transition_logs_warning(
        self, mock_autorate_config, tmp_path, caplog
    ):
        """Disabling tuning via SIGUSR1 should log WARNING with old->new."""
        wc = self._make_wc(mock_autorate_config, tmp_path, {"tuning": {"enabled": True}})
        # Force enable
        wc._tuning_enabled = True
        wc._tuning_state = TuningState(
            enabled=True, last_run_ts=None, recent_adjustments=[], parameters={}
        )

        # Write new config with tuning disabled
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"tuning": {"enabled": False}}))

        with caplog.at_level(logging.WARNING, logger="test.tuning.reload"):
            wc._reload_tuning_config()

        assert wc._tuning_enabled is False
        assert wc._tuning_state is None
        assert "enabled=True->False" in caplog.text

    def test_unchanged_state_logs_info(self, mock_autorate_config, tmp_path, caplog):
        """Unchanged enabled state should log INFO (not WARNING)."""
        wc = self._make_wc(mock_autorate_config, tmp_path)
        assert wc._tuning_enabled is False

        # Config stays disabled
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"tuning": {"enabled": False}}))

        with caplog.at_level(logging.DEBUG, logger="test.tuning.reload"):
            wc._reload_tuning_config()

        assert wc._tuning_enabled is False
        assert "enabled=False (unchanged)" in caplog.text

    def test_invalid_enabled_type_defaults_to_false(self, mock_autorate_config, tmp_path, caplog):
        """Non-bool tuning.enabled should default to false with warning."""
        wc = self._make_wc(mock_autorate_config, tmp_path)

        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"tuning": {"enabled": "yes"}}))

        with caplog.at_level(logging.WARNING, logger="test.tuning.reload"):
            wc._reload_tuning_config()

        assert wc._tuning_enabled is False
        assert "must be bool" in caplog.text

    def test_missing_tuning_section_defaults_to_false(self, mock_autorate_config, tmp_path):
        """Missing tuning section should default to false."""
        wc = self._make_wc(mock_autorate_config, tmp_path)

        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"wan_name": "Test"}))

        wc._reload_tuning_config()
        assert wc._tuning_enabled is False

    def test_file_read_error_logs_error_and_returns(self, mock_autorate_config, tmp_path, caplog):
        """File read error should be logged and state preserved."""
        wc = self._make_wc(mock_autorate_config, tmp_path)

        # Point to nonexistent file
        wc.config.config_file_path = str(tmp_path / "nonexistent.yaml")

        with caplog.at_level(logging.ERROR, logger="test.tuning.reload"):
            wc._reload_tuning_config()

        assert "Config reload failed" in caplog.text
        assert wc._tuning_enabled is False  # Preserved original state
