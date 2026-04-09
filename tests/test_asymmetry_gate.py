"""Tests for asymmetry-aware upload delta attenuation gate (Phase 156).

Covers ASYM-01 (delta attenuation), ASYM-02 (consecutive sample hysteresis),
ASYM-03 (staleness auto-disable), bidirectional override, config loading,
and SIGUSR1 hot-reload.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
import yaml

from wanctl.asymmetry_analyzer import AsymmetryResult
from wanctl.wan_controller import WANController


# =============================================================================
# Helpers
# =============================================================================


def _make_controller(mock_autorate_config, gate_enabled=True):
    """Create a WANController with asymmetry gate config for testing."""
    mock_autorate_config.asymmetry_gate_config = {
        "enabled": gate_enabled,
        "damping_factor": 0.5,
        "min_ratio": 3.0,
        "confirm_readings": 3,
        "staleness_sec": 30.0,
    }
    router = MagicMock()
    router.needs_rate_limiting = False
    rtt = MagicMock()
    logger = MagicMock()
    controller = WANController(
        wan_name="TestWAN",
        config=mock_autorate_config,
        router=router,
        rtt_measurement=rtt,
        logger=logger,
    )
    controller.baseline_rtt = 25.0
    controller.load_rtt = 50.0
    return controller


def _downstream_result(ratio=4.0):
    """Create a downstream AsymmetryResult."""
    return AsymmetryResult(
        direction="downstream",
        ratio=ratio,
        send_delay_ms=5.0,
        receive_delay_ms=20.0,
    )


def _symmetric_result():
    """Create a symmetric AsymmetryResult."""
    return AsymmetryResult(
        direction="symmetric",
        ratio=1.2,
        send_delay_ms=10.0,
        receive_delay_ms=11.0,
    )


# =============================================================================
# TestComputeEffectiveUlLoadRtt
# =============================================================================


class TestComputeEffectiveUlLoadRtt:
    """Tests for WANController._compute_effective_ul_load_rtt() gate method."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_autorate_config):
        self.config = mock_autorate_config

    def test_gate_disabled_returns_raw_load_rtt(self):
        """Gate disabled in config -> returns self.load_rtt unchanged."""
        controller = _make_controller(self.config, gate_enabled=False)
        controller._last_asymmetry_result = _downstream_result()
        controller._last_asymmetry_result_ts = time.monotonic()

        result = controller._compute_effective_ul_load_rtt()
        assert result == controller.load_rtt

    def test_no_asymmetry_result_returns_raw_load_rtt(self):
        """Gate enabled, no asymmetry result -> returns self.load_rtt unchanged."""
        controller = _make_controller(self.config, gate_enabled=True)
        # _last_asymmetry_result is None by default from init

        result = controller._compute_effective_ul_load_rtt()
        assert result == controller.load_rtt

    def test_one_downstream_reading_not_active(self):
        """Gate enabled, 1 downstream reading -> NOT active (ASYM-02)."""
        controller = _make_controller(self.config, gate_enabled=True)
        controller._last_asymmetry_result = _downstream_result()
        controller._last_asymmetry_result_ts = time.monotonic()

        result = controller._compute_effective_ul_load_rtt()
        assert result == controller.load_rtt  # Not enough consecutive readings
        assert controller._asymmetry_downstream_streak == 1
        assert controller._asymmetry_gate_active is False

    def test_two_downstream_readings_not_active(self):
        """Gate enabled, 2 downstream readings -> NOT active (confirm_readings=3)."""
        controller = _make_controller(self.config, gate_enabled=True)
        controller._last_asymmetry_result = _downstream_result()
        controller._last_asymmetry_result_ts = time.monotonic()

        controller._compute_effective_ul_load_rtt()  # streak=1
        controller._compute_effective_ul_load_rtt()  # streak=2

        assert controller._asymmetry_downstream_streak == 2
        assert controller._asymmetry_gate_active is False

    def test_three_consecutive_downstream_activates_gate(self):
        """Gate enabled, 3 consecutive downstream readings -> ACTIVE (ASYM-01, ASYM-02).

        With baseline=25, load=50, delta=25, damping=0.5:
        effective = 25.0 + (25.0 * 0.5) = 37.5
        """
        controller = _make_controller(self.config, gate_enabled=True)
        controller._last_asymmetry_result = _downstream_result()
        controller._last_asymmetry_result_ts = time.monotonic()

        # Build up streak
        controller._compute_effective_ul_load_rtt()  # streak=1, returns 50.0
        controller._compute_effective_ul_load_rtt()  # streak=2, returns 50.0
        result = controller._compute_effective_ul_load_rtt()  # streak=3, ACTIVE

        assert controller._asymmetry_gate_active is True
        assert controller._asymmetry_downstream_streak == 3
        assert result == pytest.approx(37.5)

    def test_non_downstream_reading_resets_streak(self):
        """Gate active, then 1 non-downstream reading -> deactivated, streak reset."""
        controller = _make_controller(self.config, gate_enabled=True)
        controller._last_asymmetry_result = _downstream_result()
        controller._last_asymmetry_result_ts = time.monotonic()

        # Activate gate
        for _ in range(3):
            controller._compute_effective_ul_load_rtt()
        assert controller._asymmetry_gate_active is True

        # Switch to symmetric
        controller._last_asymmetry_result = _symmetric_result()
        result = controller._compute_effective_ul_load_rtt()

        assert controller._asymmetry_gate_active is False
        assert controller._asymmetry_downstream_streak == 0
        assert result == controller.load_rtt

    def test_stale_irtt_disables_gate(self):
        """Gate enabled, IRTT age > 30s -> gate disabled (ASYM-03)."""
        controller = _make_controller(self.config, gate_enabled=True)
        controller._last_asymmetry_result = _downstream_result()
        # Set timestamp to 31 seconds ago
        controller._last_asymmetry_result_ts = time.monotonic() - 31.0

        result = controller._compute_effective_ul_load_rtt()
        assert result == controller.load_rtt
        assert controller._asymmetry_gate_active is False
        assert controller._asymmetry_downstream_streak == 0

    def test_stale_irtt_deactivates_active_gate(self):
        """Gate active, IRTT goes stale -> gate deactivated + streak reset (ASYM-03)."""
        controller = _make_controller(self.config, gate_enabled=True)
        controller._last_asymmetry_result = _downstream_result()
        controller._last_asymmetry_result_ts = time.monotonic()

        # Activate gate
        for _ in range(3):
            controller._compute_effective_ul_load_rtt()
        assert controller._asymmetry_gate_active is True

        # Make IRTT stale
        controller._last_asymmetry_result_ts = time.monotonic() - 31.0
        result = controller._compute_effective_ul_load_rtt()

        assert controller._asymmetry_gate_active is False
        assert controller._asymmetry_downstream_streak == 0
        assert result == controller.load_rtt

    def test_bidirectional_override_returns_raw(self):
        """Delta > hard_red_threshold -> bidirectional override, returns self.load_rtt."""
        controller = _make_controller(self.config, gate_enabled=True)
        controller._last_asymmetry_result = _downstream_result()
        controller._last_asymmetry_result_ts = time.monotonic()
        # Set load_rtt so delta > hard_red_threshold (80.0)
        controller.baseline_rtt = 25.0
        controller.load_rtt = 115.0  # delta=90 > 80

        result = controller._compute_effective_ul_load_rtt()
        assert result == controller.load_rtt
        assert controller._asymmetry_gate_active is False

    def test_bidirectional_override_deactivates_gate(self):
        """Gate active, bidirectional override fires -> gate deactivated."""
        controller = _make_controller(self.config, gate_enabled=True)
        controller._last_asymmetry_result = _downstream_result()
        controller._last_asymmetry_result_ts = time.monotonic()

        # Activate gate
        for _ in range(3):
            controller._compute_effective_ul_load_rtt()
        assert controller._asymmetry_gate_active is True

        # Trigger bidirectional override
        controller.load_rtt = 115.0  # delta=90 > 80
        result = controller._compute_effective_ul_load_rtt()

        assert controller._asymmetry_gate_active is False
        assert result == controller.load_rtt

    def test_ratio_below_min_does_not_count(self):
        """Downstream result with ratio < min_ratio does not increment streak."""
        controller = _make_controller(self.config, gate_enabled=True)
        controller._last_asymmetry_result = AsymmetryResult(
            direction="downstream",
            ratio=2.0,  # Below min_ratio of 3.0
            send_delay_ms=5.0,
            receive_delay_ms=10.0,
        )
        controller._last_asymmetry_result_ts = time.monotonic()

        result = controller._compute_effective_ul_load_rtt()
        assert controller._asymmetry_downstream_streak == 0
        assert controller._asymmetry_gate_active is False
        assert result == controller.load_rtt

    def test_attenuation_math_with_different_damping(self):
        """Verify attenuation math: effective = baseline + (delta * damping_factor)."""
        controller = _make_controller(self.config, gate_enabled=True)
        controller._asymmetry_damping_factor = 0.3
        controller.baseline_rtt = 20.0
        controller.load_rtt = 60.0  # delta=40
        controller._last_asymmetry_result = _downstream_result()
        controller._last_asymmetry_result_ts = time.monotonic()

        # Activate gate
        for _ in range(3):
            controller._compute_effective_ul_load_rtt()

        # effective = 20.0 + (40.0 * 0.3) = 32.0
        result = controller._compute_effective_ul_load_rtt()
        assert result == pytest.approx(32.0)


# =============================================================================
# TestAsymmetryGateConfigLoading
# =============================================================================


class TestAsymmetryGateConfigLoading:
    """Tests for autorate_config _load_asymmetry_gate_config."""

    @staticmethod
    def _minimal_config(asymmetry_gate=None):
        """Build a minimal valid config dict for Config instantiation."""
        upload = {
            "floor_mbps": 25,
            "ceiling_mbps": 40,
            "step_up_mbps": 1,
            "factor_down": 0.85,
        }
        if asymmetry_gate is not None:
            upload["asymmetry_gate"] = asymmetry_gate
        return {
            "wan_name": "test",
            "router": {
                "host": "192.168.1.1",
                "user": "admin",
                "ssh_key": "/tmp/test_id_rsa",
                "transport": "ssh",
            },
            "queues": {"download": "cake-download", "upload": "cake-upload"},
            "continuous_monitoring": {
                "enabled": True,
                "baseline_rtt_initial": 25.0,
                "ping_hosts": ["1.1.1.1"],
                "download": {
                    "floor_mbps": 400,
                    "ceiling_mbps": 920,
                    "step_up_mbps": 10,
                    "factor_down": 0.85,
                },
                "upload": upload,
                "thresholds": {
                    "target_bloat_ms": 15,
                    "warn_bloat_ms": 45,
                    "baseline_time_constant_sec": 60,
                    "load_time_constant_sec": 0.5,
                },
            },
            "logging": {
                "main_log": "/tmp/test_autorate.log",
                "debug_log": "/tmp/test_autorate_debug.log",
            },
            "lock_file": "/tmp/test_autorate.lock",
            "lock_timeout": 300,
        }

    def _load(self, tmp_path, asymmetry_gate=None):
        """Write config to file and load it."""
        from wanctl.autorate_config import Config

        cfg = self._minimal_config(asymmetry_gate)
        path = tmp_path / "config.yaml"
        path.write_text(yaml.dump(cfg))
        return Config(str(path))

    def test_valid_config_produces_correct_dict(self, tmp_path):
        """Valid YAML produces correct config dict."""
        config = self._load(tmp_path, {
            "enabled": True,
            "damping_factor": 0.4,
            "min_ratio": 2.5,
            "confirm_readings": 5,
            "staleness_sec": 60.0,
        })
        gate = config.asymmetry_gate_config
        assert gate["enabled"] is True
        assert gate["damping_factor"] == pytest.approx(0.4)
        assert gate["min_ratio"] == pytest.approx(2.5)
        assert gate["confirm_readings"] == 5
        assert gate["staleness_sec"] == pytest.approx(60.0)

    def test_missing_section_uses_defaults(self, tmp_path):
        """Missing asymmetry_gate section -> all defaults."""
        config = self._load(tmp_path)
        gate = config.asymmetry_gate_config
        assert gate["enabled"] is False
        assert gate["damping_factor"] == pytest.approx(0.5)
        assert gate["min_ratio"] == pytest.approx(3.0)
        assert gate["confirm_readings"] == 3
        assert gate["staleness_sec"] == pytest.approx(30.0)

    def test_damping_factor_out_of_bounds_defaults(self, tmp_path):
        """damping_factor < 0.0 or > 1.0 -> default 0.5."""
        config = self._load(tmp_path, {"damping_factor": 1.5})
        assert config.asymmetry_gate_config["damping_factor"] == pytest.approx(0.5)

    def test_min_ratio_below_one_defaults(self, tmp_path):
        """min_ratio < 1.0 -> default 3.0."""
        config = self._load(tmp_path, {"min_ratio": 0.5})
        assert config.asymmetry_gate_config["min_ratio"] == pytest.approx(3.0)

    def test_confirm_readings_out_of_bounds_defaults(self, tmp_path):
        """confirm_readings < 1 or > 10 -> default 3."""
        config = self._load(tmp_path, {"confirm_readings": 15})
        assert config.asymmetry_gate_config["confirm_readings"] == 3

    def test_staleness_sec_out_of_bounds_defaults(self, tmp_path):
        """staleness_sec < 5.0 or > 120.0 -> default 30.0."""
        config = self._load(tmp_path, {"staleness_sec": 200.0})
        assert config.asymmetry_gate_config["staleness_sec"] == pytest.approx(30.0)


# =============================================================================
# TestAsymmetryGateSIGUSR1Reload
# =============================================================================


class TestAsymmetryGateSIGUSR1Reload:
    """Tests for _reload_asymmetry_gate_config."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_autorate_config, tmp_path):
        self.config = mock_autorate_config
        self.yaml_path = tmp_path / "test.yaml"
        self.config.config_file_path = str(self.yaml_path)

    def _write_yaml(self, gate_config):
        """Write a YAML config file with the given asymmetry_gate section."""
        import yaml

        data = {
            "continuous_monitoring": {
                "upload": {
                    "asymmetry_gate": gate_config,
                },
            },
        }
        self.yaml_path.write_text(yaml.dump(data))

    def test_reload_toggles_enabled(self):
        """SIGUSR1 reload: enabled true -> false."""
        controller = _make_controller(self.config, gate_enabled=True)
        controller.config.config_file_path = str(self.yaml_path)
        assert controller._asymmetry_gate_enabled is True

        self._write_yaml({"enabled": False, "damping_factor": 0.5})
        controller._reload_asymmetry_gate_config()

        assert controller._asymmetry_gate_enabled is False

    def test_reload_updates_damping_factor(self):
        """SIGUSR1 reload: damping_factor change."""
        controller = _make_controller(self.config, gate_enabled=True)
        controller.config.config_file_path = str(self.yaml_path)
        assert controller._asymmetry_damping_factor == pytest.approx(0.5)

        self._write_yaml({"enabled": True, "damping_factor": 0.3})
        controller._reload_asymmetry_gate_config()

        assert controller._asymmetry_damping_factor == pytest.approx(0.3)

    def test_reload_invalid_yaml_keeps_current(self):
        """SIGUSR1 reload with invalid YAML keeps current values."""
        controller = _make_controller(self.config, gate_enabled=True)
        controller.config.config_file_path = str(self.yaml_path)
        # Write invalid content
        self.yaml_path.write_text("not: valid: yaml: [[[")
        controller._reload_asymmetry_gate_config()

        # Values unchanged
        assert controller._asymmetry_gate_enabled is True
        assert controller._asymmetry_damping_factor == pytest.approx(0.5)

    def test_reload_disabling_resets_active_gate(self):
        """Disabling gate via reload resets active state and streak."""
        controller = _make_controller(self.config, gate_enabled=True)
        controller.config.config_file_path = str(self.yaml_path)
        # Simulate active gate
        controller._asymmetry_gate_active = True
        controller._asymmetry_downstream_streak = 5

        self._write_yaml({"enabled": False})
        controller._reload_asymmetry_gate_config()

        assert controller._asymmetry_gate_active is False
        assert controller._asymmetry_downstream_streak == 0

    def test_reload_dispatched_from_reload_method(self):
        """reload() dispatches to _reload_asymmetry_gate_config."""
        controller = _make_controller(self.config, gate_enabled=True)
        controller.config.config_file_path = str(self.yaml_path)
        self._write_yaml({"enabled": False, "damping_factor": 0.5})

        controller.reload()

        assert controller._asymmetry_gate_enabled is False


# =============================================================================
# TestCongestionAssessmentIntegration
# =============================================================================


class TestCongestionAssessmentIntegration:
    """Tests that _run_congestion_assessment uses effective_load_rtt."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_autorate_config):
        self.config = mock_autorate_config

    def test_congestion_assessment_passes_effective_load_rtt(self):
        """upload.adjust() receives attenuated load_rtt when gate is active."""
        controller = _make_controller(self.config, gate_enabled=True)
        controller._last_asymmetry_result = _downstream_result()
        controller._last_asymmetry_result_ts = time.monotonic()

        # Activate gate (3 consecutive readings)
        for _ in range(3):
            controller._compute_effective_ul_load_rtt()
        assert controller._asymmetry_gate_active is True

        # Mock upload.adjust to capture the load_rtt argument
        original_adjust = controller.upload.adjust
        captured_args = {}

        def capture_adjust(baseline, load_rtt, target_delta, warn_delta):
            captured_args["load_rtt"] = load_rtt
            return "GREEN", 35_000_000, None

        controller.upload.adjust = capture_adjust
        controller.download.adjust_4state = MagicMock(
            return_value=("GREEN", 800_000_000, None)
        )
        # Stub alert/drift/flapping checks
        controller._check_congestion_alerts = MagicMock()
        controller._check_baseline_drift = MagicMock()
        controller._check_flapping_alerts = MagicMock()

        controller._run_congestion_assessment()

        # effective = 25.0 + (25.0 * 0.5) = 37.5
        assert captured_args["load_rtt"] == pytest.approx(37.5)

    def test_congestion_assessment_passes_raw_when_gate_disabled(self):
        """upload.adjust() receives raw load_rtt when gate is disabled."""
        controller = _make_controller(self.config, gate_enabled=False)
        controller._last_asymmetry_result = _downstream_result()
        controller._last_asymmetry_result_ts = time.monotonic()

        captured_args = {}

        def capture_adjust(baseline, load_rtt, target_delta, warn_delta):
            captured_args["load_rtt"] = load_rtt
            return "GREEN", 35_000_000, None

        controller.upload.adjust = capture_adjust
        controller.download.adjust_4state = MagicMock(
            return_value=("GREEN", 800_000_000, None)
        )
        controller._check_congestion_alerts = MagicMock()
        controller._check_baseline_drift = MagicMock()
        controller._check_flapping_alerts = MagicMock()

        controller._run_congestion_assessment()

        assert captured_args["load_rtt"] == controller.load_rtt


# =============================================================================
# TestHealthDataIncludesGate
# =============================================================================


class TestHealthDataIncludesGate:
    """Tests that get_health_data includes asymmetry_gate section."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_autorate_config):
        self.config = mock_autorate_config

    def test_health_data_includes_gate_section(self):
        """get_health_data() includes asymmetry_gate key."""
        controller = _make_controller(self.config, gate_enabled=True)
        health = controller.get_health_data()

        assert "asymmetry_gate" in health
        gate = health["asymmetry_gate"]
        assert gate["enabled"] is True
        assert gate["active"] is False
        assert gate["downstream_streak"] == 0
        assert gate["damping_factor"] == pytest.approx(0.5)
        assert gate["last_result_age_sec"] is None  # No result yet

    def test_health_data_gate_with_active_state(self):
        """get_health_data() shows active state when gate is active."""
        controller = _make_controller(self.config, gate_enabled=True)
        controller._last_asymmetry_result = _downstream_result()
        controller._last_asymmetry_result_ts = time.monotonic()

        # Activate gate
        for _ in range(3):
            controller._compute_effective_ul_load_rtt()

        health = controller.get_health_data()
        gate = health["asymmetry_gate"]
        assert gate["active"] is True
        assert gate["downstream_streak"] == 3
        assert gate["last_result_age_sec"] is not None


# =============================================================================
# TestIRTTObservationTimestamp
# =============================================================================


class TestIRTTObservationTimestamp:
    """Tests that _run_irtt_observation sets _last_asymmetry_result_ts."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_autorate_config):
        self.config = mock_autorate_config

    def test_irtt_observation_sets_timestamp(self):
        """_run_irtt_observation updates _last_asymmetry_result_ts after asymmetry analysis."""
        controller = _make_controller(self.config, gate_enabled=True)
        assert controller._last_asymmetry_result_ts == 0.0

        # Set up a mock IRTT thread with result
        mock_irtt_thread = MagicMock()
        mock_result = MagicMock()
        mock_result.timestamp = time.monotonic()
        mock_result.rtt_mean_ms = 25.0
        mock_result.ipdv_mean_ms = 2.0
        mock_result.send_loss = 0.0
        mock_result.receive_loss = 0.0
        mock_result.send_delay_median_ms = 5.0
        mock_result.receive_delay_median_ms = 20.0
        mock_irtt_thread.get_latest.return_value = mock_result
        mock_irtt_thread.cadence_sec = 10.0
        controller._irtt_thread = mock_irtt_thread

        # Mock signal result
        mock_signal = MagicMock()
        mock_signal.filtered_rtt = 25.0

        controller._run_irtt_observation(mock_signal)

        assert controller._last_asymmetry_result_ts > 0.0
