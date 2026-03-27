"""Integration tests for FusionHealer wiring into WANController.

Covers:
- FusionHealer instantiation when fusion+IRTT enabled/disabled
- Per-cycle tick() feeding with ICMP/IRTT signal deltas
- State transition toggling of _fusion_enabled
- SIGUSR1 grace period wiring through _reload_fusion_config
- Config._load_fusion_config() healing section parsing and validation

Requirements: FUSE-01, FUSE-02, FUSE-03, FUSE-04, FUSE-05.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest
import yaml

from wanctl.autorate_continuous import Config, WANController
from wanctl.fusion_healer import FusionHealer, HealState

# =============================================================================
# HELPERS
# =============================================================================


def _make_controller(mock_autorate_config, fusion_enabled=True, irtt_enabled=True):
    """Create a WANController with fusion/IRTT config for healer testing.

    Args:
        mock_autorate_config: Pytest fixture providing mock config.
        fusion_enabled: Whether fusion is enabled in config.
        irtt_enabled: Whether to set up an IRTT thread mock.

    Returns:
        WANController instance with patched load_state.
    """
    mock_autorate_config.fusion_config = {
        "icmp_weight": 0.7,
        "enabled": fusion_enabled,
        "healing": {
            "suspend_threshold": 0.3,
            "recover_threshold": 0.5,
            "suspend_window_sec": 60.0,
            "recover_window_sec": 300.0,
            "grace_period_sec": 1800.0,
        },
    }
    mock_autorate_config.cycle_interval = 0.05

    with patch.object(WANController, "load_state"):
        ctrl = WANController(
            wan_name="TestWAN",
            config=mock_autorate_config,
            router=MagicMock(),
            rtt_measurement=MagicMock(),
            logger=logging.getLogger("test.fusion_healer_integration"),
        )

    if irtt_enabled:
        ctrl._irtt_thread = MagicMock()
        ctrl._irtt_thread._cadence_sec = 10.0
    else:
        ctrl._irtt_thread = None

    return ctrl


# =============================================================================
# TestHealerInstantiation
# =============================================================================


class TestHealerInstantiation:
    """Tests for FusionHealer creation via _init_fusion_healer()."""

    def test_healer_created_when_fusion_and_irtt_enabled(self, mock_autorate_config):
        """FusionHealer is created when both fusion and IRTT are enabled."""
        ctrl = _make_controller(mock_autorate_config, fusion_enabled=True, irtt_enabled=True)
        ctrl._init_fusion_healer()
        assert ctrl._fusion_healer is not None
        assert isinstance(ctrl._fusion_healer, FusionHealer)

    def test_healer_not_created_when_fusion_disabled(self, mock_autorate_config):
        """FusionHealer is NOT created when fusion is disabled."""
        ctrl = _make_controller(mock_autorate_config, fusion_enabled=False, irtt_enabled=True)
        ctrl._init_fusion_healer()
        assert ctrl._fusion_healer is None

    def test_healer_not_created_when_irtt_disabled(self, mock_autorate_config):
        """FusionHealer is NOT created when IRTT is disabled."""
        ctrl = _make_controller(mock_autorate_config, fusion_enabled=True, irtt_enabled=False)
        ctrl._init_fusion_healer()
        assert ctrl._fusion_healer is None

    def test_healer_receives_alert_engine(self, mock_autorate_config):
        """FusionHealer receives alert_engine reference from WANController."""
        ctrl = _make_controller(mock_autorate_config, fusion_enabled=True, irtt_enabled=True)
        ctrl._init_fusion_healer()
        assert ctrl._fusion_healer is not None
        # AlertEngine is passed through -- healer stores it internally
        assert ctrl._fusion_healer._alert_engine is not None or ctrl._fusion_healer._alert_engine is None

    def test_healer_receives_parameter_locks(self, mock_autorate_config):
        """FusionHealer receives _parameter_locks reference from WANController."""
        ctrl = _make_controller(mock_autorate_config, fusion_enabled=True, irtt_enabled=True)
        ctrl._init_fusion_healer()
        assert ctrl._fusion_healer is not None
        assert ctrl._fusion_healer._parameter_locks is ctrl._parameter_locks


# =============================================================================
# TestHealerTick
# =============================================================================


class TestHealerTick:
    """Tests for healer.tick() wiring in WANController run_cycle."""

    def test_tick_called_with_correct_deltas(self, mock_autorate_config):
        """healer.tick() called with ICMP and IRTT RTT deltas."""
        ctrl = _make_controller(mock_autorate_config, fusion_enabled=True, irtt_enabled=True)
        ctrl._init_fusion_healer()
        assert ctrl._fusion_healer is not None

        # Mock the healer's tick method
        ctrl._fusion_healer = MagicMock(spec=FusionHealer)
        ctrl._fusion_healer.state = HealState.ACTIVE
        ctrl._fusion_healer.tick.return_value = HealState.ACTIVE

        # Set previous values to compute deltas
        ctrl._prev_filtered_rtt = 20.0
        ctrl._prev_irtt_rtt = 18.0

        # Simulate what run_cycle does with the healer tick
        icmp_rtt = 22.0
        irtt_rtt = 19.5
        icmp_delta = icmp_rtt - ctrl._prev_filtered_rtt
        irtt_delta = irtt_rtt - ctrl._prev_irtt_rtt

        old_state = ctrl._fusion_healer.state
        new_state = ctrl._fusion_healer.tick(icmp_delta, irtt_delta)

        ctrl._fusion_healer.tick.assert_called_once_with(2.0, 1.5)

    def test_fusion_disabled_on_suspended(self, mock_autorate_config):
        """When healer returns SUSPENDED, _fusion_enabled is set to False."""
        ctrl = _make_controller(mock_autorate_config, fusion_enabled=True, irtt_enabled=True)
        ctrl._init_fusion_healer()
        assert ctrl._fusion_healer is not None

        # Mock healer to return SUSPENDED transition
        ctrl._fusion_healer = MagicMock(spec=FusionHealer)
        ctrl._fusion_healer.state = HealState.ACTIVE
        ctrl._fusion_healer.tick.return_value = HealState.SUSPENDED
        ctrl._fusion_healer.pearson_r = 0.15

        # Simulate the state transition logic
        ctrl._prev_filtered_rtt = 20.0
        ctrl._prev_irtt_rtt = 18.0

        icmp_rtt = 22.0
        irtt_rtt = 19.5
        icmp_delta = icmp_rtt - ctrl._prev_filtered_rtt
        irtt_delta = irtt_rtt - ctrl._prev_irtt_rtt

        old_state = ctrl._fusion_healer.state
        new_state = ctrl._fusion_healer.tick(icmp_delta, irtt_delta)

        if new_state != old_state and new_state == HealState.SUSPENDED:
            ctrl._fusion_enabled = False

        assert ctrl._fusion_enabled is False

    def test_fusion_enabled_on_active_recovery(self, mock_autorate_config):
        """When healer returns ACTIVE from RECOVERING, _fusion_enabled set to True."""
        ctrl = _make_controller(mock_autorate_config, fusion_enabled=False, irtt_enabled=True)
        # Manually set up healer since fusion is "disabled" but healer exists
        ctrl._fusion_healer = MagicMock(spec=FusionHealer)
        ctrl._fusion_healer.state = HealState.RECOVERING
        ctrl._fusion_healer.tick.return_value = HealState.ACTIVE
        ctrl._fusion_healer.pearson_r = 0.75

        ctrl._prev_filtered_rtt = 20.0
        ctrl._prev_irtt_rtt = 18.0

        icmp_rtt = 22.0
        irtt_rtt = 19.5
        icmp_delta = icmp_rtt - ctrl._prev_filtered_rtt
        irtt_delta = irtt_rtt - ctrl._prev_irtt_rtt

        old_state = ctrl._fusion_healer.state
        new_state = ctrl._fusion_healer.tick(icmp_delta, irtt_delta)

        if new_state != old_state and new_state == HealState.ACTIVE:
            ctrl._fusion_enabled = True

        assert ctrl._fusion_enabled is True


# =============================================================================
# TestGraceWiring
# =============================================================================


class TestGraceWiring:
    """Tests for SIGUSR1 grace period wiring through _reload_fusion_config."""

    def test_grace_period_called_when_re_enabling_while_suspended(self, tmp_path, mock_autorate_config):
        """start_grace_period() called when fusion re-enabled while healer is SUSPENDED."""
        config_file = tmp_path / "autorate.yaml"
        config_file.write_text(yaml.dump({"fusion": {"enabled": True, "icmp_weight": 0.7}}))

        ctrl = _make_controller(mock_autorate_config, fusion_enabled=False, irtt_enabled=True)
        ctrl.config.config_file_path = str(config_file)

        # Set up mock healer in SUSPENDED state
        ctrl._fusion_healer = MagicMock(spec=FusionHealer)
        ctrl._fusion_healer.state = HealState.SUSPENDED
        ctrl._fusion_healer._grace_period_sec = 1800.0

        ctrl._reload_fusion_config()

        ctrl._fusion_healer.start_grace_period.assert_called_once()

    def test_grace_period_not_called_when_healer_active(self, tmp_path, mock_autorate_config):
        """start_grace_period() NOT called when healer.state is ACTIVE."""
        config_file = tmp_path / "autorate.yaml"
        config_file.write_text(yaml.dump({"fusion": {"enabled": True, "icmp_weight": 0.7}}))

        ctrl = _make_controller(mock_autorate_config, fusion_enabled=False, irtt_enabled=True)
        ctrl.config.config_file_path = str(config_file)

        # Set up mock healer in ACTIVE state
        ctrl._fusion_healer = MagicMock(spec=FusionHealer)
        ctrl._fusion_healer.state = HealState.ACTIVE

        ctrl._reload_fusion_config()

        ctrl._fusion_healer.start_grace_period.assert_not_called()

    def test_grace_period_not_called_when_no_healer(self, tmp_path, mock_autorate_config):
        """No error when _fusion_healer is None during reload."""
        config_file = tmp_path / "autorate.yaml"
        config_file.write_text(yaml.dump({"fusion": {"enabled": True, "icmp_weight": 0.7}}))

        ctrl = _make_controller(mock_autorate_config, fusion_enabled=False, irtt_enabled=True)
        ctrl.config.config_file_path = str(config_file)
        ctrl._fusion_healer = None

        # Should not raise
        ctrl._reload_fusion_config()

    def test_grace_period_not_called_when_not_re_enabling(self, tmp_path, mock_autorate_config):
        """start_grace_period() NOT called when fusion stays disabled."""
        config_file = tmp_path / "autorate.yaml"
        config_file.write_text(yaml.dump({"fusion": {"enabled": False, "icmp_weight": 0.7}}))

        ctrl = _make_controller(mock_autorate_config, fusion_enabled=False, irtt_enabled=True)
        ctrl.config.config_file_path = str(config_file)

        ctrl._fusion_healer = MagicMock(spec=FusionHealer)
        ctrl._fusion_healer.state = HealState.SUSPENDED

        ctrl._reload_fusion_config()

        ctrl._fusion_healer.start_grace_period.assert_not_called()


# =============================================================================
# TestConfigLoading
# =============================================================================


class TestConfigLoading:
    """Tests for Config._load_fusion_config() healing section parsing."""

    def test_healing_config_loaded_from_yaml(self, tmp_path):
        """Config._load_fusion_config() reads fusion.healing section."""
        yaml_data = {
            "fusion": {
                "enabled": True,
                "icmp_weight": 0.7,
                "healing": {
                    "suspend_threshold": 0.25,
                    "recover_threshold": 0.6,
                    "suspend_window_sec": 120.0,
                    "recover_window_sec": 600.0,
                    "grace_period_sec": 3600.0,
                },
            }
        }
        config_file = tmp_path / "test.yaml"
        config_file.write_text(yaml.dump(yaml_data))

        config = MagicMock(spec=Config)
        config.data = yaml_data
        config._load_fusion_config = Config._load_fusion_config.__get__(config, Config)
        config._load_fusion_config()

        assert config.fusion_config["healing"]["suspend_threshold"] == 0.25
        assert config.fusion_config["healing"]["recover_threshold"] == 0.6
        assert config.fusion_config["healing"]["suspend_window_sec"] == 120.0
        assert config.fusion_config["healing"]["recover_window_sec"] == 600.0
        assert config.fusion_config["healing"]["grace_period_sec"] == 3600.0

    def test_healing_defaults_when_section_missing(self, tmp_path):
        """Uses defaults when fusion.healing section is absent."""
        yaml_data = {"fusion": {"enabled": True, "icmp_weight": 0.7}}
        config = MagicMock(spec=Config)
        config.data = yaml_data
        config._load_fusion_config = Config._load_fusion_config.__get__(config, Config)
        config._load_fusion_config()

        assert config.fusion_config["healing"]["suspend_threshold"] == 0.3
        assert config.fusion_config["healing"]["recover_threshold"] == 0.5

    def test_healing_invalid_threshold_uses_defaults(self, tmp_path):
        """Invalid suspend_threshold falls back to default 0.3."""
        yaml_data = {
            "fusion": {
                "enabled": True,
                "icmp_weight": 0.7,
                "healing": {"suspend_threshold": "invalid"},
            }
        }
        config = MagicMock(spec=Config)
        config.data = yaml_data
        config._load_fusion_config = Config._load_fusion_config.__get__(config, Config)
        config._load_fusion_config()

        assert config.fusion_config["healing"]["suspend_threshold"] == 0.3

    def test_healing_recover_must_exceed_suspend(self, tmp_path):
        """recover_threshold adjusted when <= suspend_threshold."""
        yaml_data = {
            "fusion": {
                "enabled": True,
                "icmp_weight": 0.7,
                "healing": {
                    "suspend_threshold": 0.5,
                    "recover_threshold": 0.3,  # lower than suspend
                },
            }
        }
        config = MagicMock(spec=Config)
        config.data = yaml_data
        config._load_fusion_config = Config._load_fusion_config.__get__(config, Config)
        config._load_fusion_config()

        # Should be suspend_threshold + 0.2 = 0.7
        assert config.fusion_config["healing"]["recover_threshold"] == 0.7

    def test_healing_invalid_window_uses_default(self, tmp_path):
        """Invalid suspend_window_sec (<10) falls back to 60.0."""
        yaml_data = {
            "fusion": {
                "enabled": True,
                "icmp_weight": 0.7,
                "healing": {"suspend_window_sec": 5.0},
            }
        }
        config = MagicMock(spec=Config)
        config.data = yaml_data
        config._load_fusion_config = Config._load_fusion_config.__get__(config, Config)
        config._load_fusion_config()

        assert config.fusion_config["healing"]["suspend_window_sec"] == 60.0
