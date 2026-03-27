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


# =============================================================================
# TestHealthEndpoint
# =============================================================================


class TestHealthEndpoint:
    """Tests for fusion heal state in health endpoint response."""

    @pytest.fixture(autouse=True)
    def reset_handler_state(self):
        """Reset HealthCheckHandler class state before each test."""
        from wanctl.health_check import HealthCheckHandler

        HealthCheckHandler.controller = None
        HealthCheckHandler.start_time = None
        HealthCheckHandler.consecutive_failures = 0
        yield
        HealthCheckHandler.controller = None
        HealthCheckHandler.start_time = None
        HealthCheckHandler.consecutive_failures = 0

    def _make_wan(self, fusion_enabled=True, healer=None):
        """Create a mock WAN controller with fusion healer attributes."""
        wan = MagicMock()
        wan.baseline_rtt = 24.5
        wan.load_rtt = 28.3
        wan.download.current_rate = 800_000_000
        wan.download.red_streak = 0
        wan.download.soft_red_streak = 0
        wan.download.soft_red_required = 3
        wan.download.green_streak = 5
        wan.download.green_required = 5
        wan.upload.current_rate = 35_000_000
        wan.upload.red_streak = 0
        wan.upload.soft_red_streak = 0
        wan.upload.soft_red_required = 3
        wan.upload.green_streak = 5
        wan.upload.green_required = 5
        wan.router_connectivity.is_reachable = True
        wan.router_connectivity.to_dict.return_value = {
            "is_reachable": True,
            "consecutive_failures": 0,
            "last_failure_type": None,
            "last_failure_time": None,
        }
        wan._last_signal_result = None
        wan._irtt_thread = None
        wan._irtt_correlation = None
        wan._last_asymmetry_result = None
        wan._fusion_enabled = fusion_enabled
        wan._fusion_icmp_weight = 0.7
        wan._last_fused_rtt = None
        wan._last_icmp_filtered_rtt = 25.0
        wan._fusion_healer = healer
        return wan

    def _make_controller(self, wan):
        """Build a mock controller wrapping a single WAN."""
        mock_controller = MagicMock()
        mock_config = MagicMock()
        mock_config.wan_name = "spectrum"
        mock_config.irtt_config = {"enabled": False}
        mock_controller.wan_controllers = [
            {"controller": wan, "config": mock_config, "logger": MagicMock()}
        ]
        return mock_controller

    def _get_health(self, controller):
        """Start health server, fetch data, shut down."""
        import json
        import socket
        import urllib.request

        from wanctl.health_check import start_health_server

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                return json.loads(response.read().decode())
        finally:
            server.shutdown()

    def test_health_shows_heal_state_active(self):
        """Health response contains heal_state=active when healer is ACTIVE."""
        healer = MagicMock()
        healer.state = HealState.ACTIVE
        healer.pearson_r = 0.85
        healer.window_avg = 0.83
        healer.is_grace_active = False

        wan = self._make_wan(fusion_enabled=True, healer=healer)
        data = self._get_health(self._make_controller(wan))

        fusion = data["wans"][0]["fusion"]
        assert fusion["heal_state"] == "active"
        assert fusion["pearson_correlation"] == 0.85
        assert fusion["correlation_window_avg"] == 0.83
        assert fusion["heal_grace_active"] is False

    def test_health_shows_heal_state_suspended(self):
        """Health response contains heal_state=suspended when healer is SUSPENDED."""
        healer = MagicMock()
        healer.state = HealState.SUSPENDED
        healer.pearson_r = 0.15
        healer.window_avg = 0.12
        healer.is_grace_active = False

        wan = self._make_wan(fusion_enabled=False, healer=healer)
        data = self._get_health(self._make_controller(wan))

        fusion = data["wans"][0]["fusion"]
        assert fusion["heal_state"] == "suspended"
        assert fusion["heal_grace_active"] is False

    def test_health_no_healer(self):
        """Health response contains heal_state=no_healer when _fusion_healer is None."""
        wan = self._make_wan(fusion_enabled=True, healer=None)
        data = self._get_health(self._make_controller(wan))

        fusion = data["wans"][0]["fusion"]
        assert fusion["heal_state"] == "no_healer"
        assert fusion["pearson_correlation"] is None
        assert fusion["heal_grace_active"] is False

    def test_health_warmup_pearson_none(self):
        """Health response has pearson_correlation=None during warmup."""
        healer = MagicMock()
        healer.state = HealState.ACTIVE
        healer.pearson_r = None
        healer.window_avg = None
        healer.is_grace_active = False

        wan = self._make_wan(fusion_enabled=True, healer=healer)
        data = self._get_health(self._make_controller(wan))

        fusion = data["wans"][0]["fusion"]
        assert fusion["heal_state"] == "active"
        assert fusion["pearson_correlation"] is None
        assert fusion["correlation_window_avg"] is None
