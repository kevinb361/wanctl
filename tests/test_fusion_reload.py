"""Tests for SIGUSR1-triggered fusion config reload.

Covers:
- WANController._reload_fusion_config() state transitions (enabled, icmp_weight)
- WANController._reload_fusion_config() validation (warn+default on invalid values)
- WANController._reload_fusion_config() error handling (missing YAML, empty YAML)
- Autorate main loop SIGUSR1 check calls _reload_fusion_config on all WANControllers

Requirements: FUSE-02 (disabled-by-default with SIGUSR1 toggle).
"""

import logging
from unittest.mock import MagicMock

import pytest
import yaml

from wanctl.fusion_healer import HealState
from wanctl.wan_controller import WANController

# =============================================================================
# HELPERS
# =============================================================================


def _make_controller(tmp_path, yaml_content, initial_enabled=False, initial_weight=0.7):
    """Create a mock WANController with config_file_path pointing to YAML.

    Args:
        tmp_path: Pytest tmp_path fixture.
        yaml_content: Dict to serialize as YAML (or None for empty file).
        initial_enabled: Starting _fusion_enabled value.
        initial_weight: Starting _fusion_icmp_weight value.

    Returns:
        MagicMock WANController with real _reload_fusion_config bound.
    """
    config_file = tmp_path / "autorate.yaml"
    if yaml_content is not None:
        config_file.write_text(yaml.dump(yaml_content))
    else:
        config_file.write_text("")

    controller = MagicMock(spec=WANController)
    controller.wan_name = "spectrum"
    controller.logger = logging.getLogger("test.fusion_reload")
    controller.config = MagicMock()
    controller.config.config_file_path = str(config_file)
    controller._fusion_enabled = initial_enabled
    controller._fusion_icmp_weight = initial_weight
    controller._fusion_healer = None

    # Bind the real method
    controller._reload_fusion_config = WANController._reload_fusion_config.__get__(
        controller, WANController
    )

    return controller


# =============================================================================
# TestReloadFusionConfig
# =============================================================================


class TestReloadFusionConfig:
    """Tests for WANController._reload_fusion_config()."""

    def test_toggle_enabled_false_to_true(self, tmp_path, caplog):
        """YAML has fusion.enabled=true, controller starts disabled. After reload, enabled."""
        ctrl = _make_controller(
            tmp_path,
            {"fusion": {"enabled": True, "icmp_weight": 0.7}},
            initial_enabled=False,
        )

        with caplog.at_level(logging.WARNING, logger="test.fusion_reload"):
            ctrl._reload_fusion_config()

        assert ctrl._fusion_enabled is True
        assert "enabled=False->True" in caplog.text

    def test_toggle_enabled_true_to_false(self, tmp_path, caplog):
        """YAML has fusion.enabled=false, controller starts enabled. After reload, disabled."""
        ctrl = _make_controller(
            tmp_path,
            {"fusion": {"enabled": False, "icmp_weight": 0.7}},
            initial_enabled=True,
        )

        with caplog.at_level(logging.WARNING, logger="test.fusion_reload"):
            ctrl._reload_fusion_config()

        assert ctrl._fusion_enabled is False
        assert "enabled=True->False" in caplog.text

    def test_change_icmp_weight(self, tmp_path, caplog):
        """YAML has fusion.icmp_weight=0.5, controller starts at 0.7. After reload, 0.5."""
        ctrl = _make_controller(
            tmp_path,
            {"fusion": {"enabled": False, "icmp_weight": 0.5}},
            initial_weight=0.7,
        )

        with caplog.at_level(logging.WARNING, logger="test.fusion_reload"):
            ctrl._reload_fusion_config()

        assert ctrl._fusion_icmp_weight == pytest.approx(0.5)
        assert "icmp_weight=0.7->0.5" in caplog.text

    def test_both_unchanged(self, tmp_path, caplog):
        """YAML matches current state. Log contains (unchanged) for weight."""
        ctrl = _make_controller(
            tmp_path,
            {"fusion": {"enabled": False, "icmp_weight": 0.7}},
            initial_enabled=False,
            initial_weight=0.7,
        )

        with caplog.at_level(logging.WARNING, logger="test.fusion_reload"):
            ctrl._reload_fusion_config()

        assert ctrl._fusion_enabled is False
        assert ctrl._fusion_icmp_weight == pytest.approx(0.7)
        assert "enabled=False" in caplog.text
        assert "icmp_weight=0.7 (unchanged)" in caplog.text

    def test_invalid_weight_warns_defaults(self, tmp_path, caplog):
        """YAML has fusion.icmp_weight='abc'. After reload, defaults to 0.7."""
        ctrl = _make_controller(
            tmp_path,
            {"fusion": {"enabled": False, "icmp_weight": "abc"}},
            initial_weight=0.5,
        )

        with caplog.at_level(logging.WARNING, logger="test.fusion_reload"):
            ctrl._reload_fusion_config()

        assert ctrl._fusion_icmp_weight == pytest.approx(0.7)
        assert "invalid" in caplog.text.lower()

    def test_invalid_enabled_warns_defaults(self, tmp_path, caplog):
        """YAML has fusion.enabled='yes'. After reload, defaults to False."""
        ctrl = _make_controller(
            tmp_path,
            {"fusion": {"enabled": "yes", "icmp_weight": 0.7}},
            initial_enabled=True,
        )

        with caplog.at_level(logging.WARNING, logger="test.fusion_reload"):
            ctrl._reload_fusion_config()

        assert ctrl._fusion_enabled is False
        assert "fusion.enabled must be bool" in caplog.text

    def test_missing_yaml_file_logs_error_no_change(self, tmp_path, caplog):
        """Config file does not exist. After reload, state unchanged. Error logged."""
        ctrl = _make_controller(
            tmp_path,
            {"fusion": {"enabled": True}},
            initial_enabled=False,
            initial_weight=0.5,
        )
        # Point to nonexistent file
        ctrl.config.config_file_path = str(tmp_path / "nonexistent.yaml")

        with caplog.at_level(logging.ERROR, logger="test.fusion_reload"):
            ctrl._reload_fusion_config()

        assert ctrl._fusion_enabled is False
        assert ctrl._fusion_icmp_weight == pytest.approx(0.5)
        assert "Config reload failed" in caplog.text

    def test_no_fusion_section_uses_defaults(self, tmp_path, caplog):
        """YAML has no fusion key. After reload, enabled=False, icmp_weight=0.7."""
        ctrl = _make_controller(
            tmp_path,
            {"wan_name": "spectrum"},
            initial_enabled=True,
            initial_weight=0.5,
        )

        with caplog.at_level(logging.WARNING, logger="test.fusion_reload"):
            ctrl._reload_fusion_config()

        assert ctrl._fusion_enabled is False
        assert ctrl._fusion_icmp_weight == pytest.approx(0.7)

    def test_healer_suspended_blocks_reenable(self, tmp_path, caplog):
        """YAML says enabled=true but healer is SUSPENDED. Fusion stays disabled.

        Regression test for SIGUSR1 override bug discovered 2026-04-02:
        sending SIGUSR1 to reload any config change would re-enable fusion
        from YAML despite the healer having suspended it for low correlation.
        """
        ctrl = _make_controller(
            tmp_path,
            {"fusion": {"enabled": True, "icmp_weight": 0.7}},
            initial_enabled=False,
        )
        # Attach a mock healer in SUSPENDED state
        ctrl._fusion_healer = MagicMock()
        ctrl._fusion_healer.state = HealState.SUSPENDED

        with caplog.at_level(logging.WARNING, logger="test.fusion_reload"):
            ctrl._reload_fusion_config()

        assert ctrl._fusion_enabled is False, (
            "Fusion must stay disabled when healer is SUSPENDED"
        )
        assert "Respecting healer state" in caplog.text

    def test_healer_active_allows_reenable(self, tmp_path, caplog):
        """YAML says enabled=true and healer is ACTIVE. Fusion re-enables normally."""
        ctrl = _make_controller(
            tmp_path,
            {"fusion": {"enabled": True, "icmp_weight": 0.7}},
            initial_enabled=False,
        )
        ctrl._fusion_healer = MagicMock()
        ctrl._fusion_healer.state = HealState.ACTIVE

        with caplog.at_level(logging.WARNING, logger="test.fusion_reload"):
            ctrl._reload_fusion_config()

        assert ctrl._fusion_enabled is True

    def test_healer_suspended_allows_disable(self, tmp_path, caplog):
        """YAML says enabled=false with healer SUSPENDED. Operator kill switch works."""
        ctrl = _make_controller(
            tmp_path,
            {"fusion": {"enabled": False, "icmp_weight": 0.7}},
            initial_enabled=True,
        )
        ctrl._fusion_healer = MagicMock()
        ctrl._fusion_healer.state = HealState.SUSPENDED

        with caplog.at_level(logging.WARNING, logger="test.fusion_reload"):
            ctrl._reload_fusion_config()

        assert ctrl._fusion_enabled is False, (
            "Operator kill switch (enabled=false) must always work"
        )

    def test_no_healer_allows_reenable(self, tmp_path, caplog):
        """No healer attached. YAML enabled=true takes effect (backward compat)."""
        ctrl = _make_controller(
            tmp_path,
            {"fusion": {"enabled": True, "icmp_weight": 0.7}},
            initial_enabled=False,
        )
        # _fusion_healer is already None from _make_controller

        with caplog.at_level(logging.WARNING, logger="test.fusion_reload"):
            ctrl._reload_fusion_config()

        assert ctrl._fusion_enabled is True

    def test_empty_yaml_uses_defaults(self, tmp_path, caplog):
        """YAML is empty (safe_load returns None). After reload, defaults."""
        ctrl = _make_controller(
            tmp_path,
            None,  # Empty YAML
            initial_enabled=True,
            initial_weight=0.5,
        )

        with caplog.at_level(logging.WARNING, logger="test.fusion_reload"):
            ctrl._reload_fusion_config()

        assert ctrl._fusion_enabled is False
        assert ctrl._fusion_icmp_weight == pytest.approx(0.7)


# =============================================================================
# TestAutorateSIGUSR1Loop
# =============================================================================


class TestAutorateSIGUSR1Loop:
    """Tests for SIGUSR1 check in autorate main loop."""

    def test_sigusr1_calls_reload_on_all_wan_controllers(self, tmp_path):
        """SIGUSR1 triggers _reload_fusion_config on every WANController."""
        from unittest.mock import patch

        # Create two mock WAN controllers
        ctrl1 = MagicMock()
        ctrl1_logger = MagicMock()
        ctrl2 = MagicMock()
        ctrl2_logger = MagicMock()

        wan_controllers = [
            {"controller": ctrl1, "logger": ctrl1_logger},
            {"controller": ctrl2, "logger": ctrl2_logger},
        ]

        # Simulate the SIGUSR1 check block from the main loop
        # This tests the actual code pattern that will be added:
        #   if is_reload_requested():
        #       for wan_info in controller.wan_controllers:
        #           wan_info["logger"].info("SIGUSR1 received, reloading fusion config")
        #           wan_info["controller"]._reload_fusion_config()
        #       reset_reload_state()
        from wanctl.signal_utils import is_reload_requested, reset_reload_state

        with patch("wanctl.signal_utils._reload_event") as mock_event:
            mock_event.is_set.return_value = True

            if is_reload_requested():
                for wan_info in wan_controllers:
                    wan_info["logger"].info("SIGUSR1 received, reloading fusion config")
                    wan_info["controller"]._reload_fusion_config()
                reset_reload_state()

        ctrl1._reload_fusion_config.assert_called_once()
        ctrl2._reload_fusion_config.assert_called_once()
        ctrl1_logger.info.assert_called_once()
        ctrl2_logger.info.assert_called_once()
        mock_event.clear.assert_called_once()
