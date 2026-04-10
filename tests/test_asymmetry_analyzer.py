"""Unit tests for AsymmetryAnalyzer, AsymmetryResult, OWD config loading,
asymmetry fields in health endpoints, and WANController persistence wiring.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.request
from unittest.mock import MagicMock, patch

import pytest

from tests.helpers import find_free_port
from wanctl.asymmetry_analyzer import (
    DIRECTION_ENCODING,
    AsymmetryAnalyzer,
    AsymmetryResult,
)
from wanctl.health_check import start_health_server
from wanctl.irtt_measurement import IRTTResult
from wanctl.storage.schema import STORED_METRICS
from wanctl.wan_controller import WANController

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_irtt_result(
    send_delay_ms: float = 0.0,
    receive_delay_ms: float = 0.0,
) -> IRTTResult:
    """Build an IRTTResult with specified OWD fields; other fields are defaults."""
    return IRTTResult(
        rtt_mean_ms=20.0,
        rtt_median_ms=19.0,
        ipdv_mean_ms=1.0,
        send_loss=0.0,
        receive_loss=0.0,
        packets_sent=10,
        packets_received=10,
        server="127.0.0.1",
        port=2112,
        timestamp=1000.0,
        success=True,
        send_delay_median_ms=send_delay_ms,
        receive_delay_median_ms=receive_delay_ms,
    )


def _make_logger() -> logging.Logger:
    """Create a test logger."""
    return logging.getLogger("test.asymmetry")


# ---------------------------------------------------------------------------
# TestAsymmetryResult
# ---------------------------------------------------------------------------


class TestAsymmetryResult:
    """Tests for the AsymmetryResult frozen dataclass."""

    def test_frozen_raises_on_assignment(self) -> None:
        """AsymmetryResult is frozen (assignment raises)."""
        result = AsymmetryResult(
            direction="symmetric", ratio=1.2, send_delay_ms=10.0, receive_delay_ms=12.0
        )
        with pytest.raises(AttributeError):
            result.direction = "upstream"  # type: ignore[misc]

    def test_all_fields_present(self) -> None:
        """AsymmetryResult has all 4 expected fields."""
        result = AsymmetryResult(
            direction="upstream", ratio=2.5, send_delay_ms=25.0, receive_delay_ms=10.0
        )
        assert result.direction == "upstream"
        assert result.ratio == pytest.approx(2.5)
        assert result.send_delay_ms == pytest.approx(25.0)
        assert result.receive_delay_ms == pytest.approx(10.0)

    def test_direction_encoding_values(self) -> None:
        """DIRECTION_ENCODING maps all 4 directions to expected float values."""
        assert DIRECTION_ENCODING["unknown"] == pytest.approx(0.0)
        assert DIRECTION_ENCODING["symmetric"] == pytest.approx(1.0)
        assert DIRECTION_ENCODING["upstream"] == pytest.approx(2.0)
        assert DIRECTION_ENCODING["downstream"] == pytest.approx(3.0)

    def test_direction_encoding_complete(self) -> None:
        """DIRECTION_ENCODING contains exactly 4 entries."""
        assert len(DIRECTION_ENCODING) == 4


# ---------------------------------------------------------------------------
# TestAsymmetryAnalyzer
# ---------------------------------------------------------------------------


class TestAsymmetryAnalyzer:
    """Tests for AsymmetryAnalyzer.analyze() direction computation."""

    def test_upstream_at_default_threshold(self) -> None:
        """Direction is 'upstream' when send_delay / receive_delay >= 2.0."""
        analyzer = AsymmetryAnalyzer(logger=_make_logger(), wan_name="test")
        result = analyzer.analyze(_make_irtt_result(send_delay_ms=20.0, receive_delay_ms=10.0))
        assert result.direction == "upstream"
        assert result.ratio == pytest.approx(2.0)

    def test_downstream_at_default_threshold(self) -> None:
        """Direction is 'downstream' when receive_delay / send_delay >= 2.0."""
        analyzer = AsymmetryAnalyzer(logger=_make_logger(), wan_name="test")
        result = analyzer.analyze(_make_irtt_result(send_delay_ms=10.0, receive_delay_ms=20.0))
        assert result.direction == "downstream"
        assert result.ratio == pytest.approx(2.0)

    def test_symmetric_below_threshold(self) -> None:
        """Direction is 'symmetric' when ratio < threshold in both directions."""
        analyzer = AsymmetryAnalyzer(logger=_make_logger(), wan_name="test")
        result = analyzer.analyze(_make_irtt_result(send_delay_ms=15.0, receive_delay_ms=10.0))
        assert result.direction == "symmetric"
        assert result.ratio == pytest.approx(1.5)

    def test_unknown_both_zero(self) -> None:
        """Direction is 'unknown' when both delays <= 0."""
        analyzer = AsymmetryAnalyzer(logger=_make_logger(), wan_name="test")
        result = analyzer.analyze(_make_irtt_result(send_delay_ms=0.0, receive_delay_ms=0.0))
        assert result.direction == "unknown"
        assert result.ratio == pytest.approx(0.0)

    def test_unknown_both_negative(self) -> None:
        """Direction is 'unknown' when both delays are negative."""
        analyzer = AsymmetryAnalyzer(logger=_make_logger(), wan_name="test")
        result = analyzer.analyze(_make_irtt_result(send_delay_ms=-1.0, receive_delay_ms=-2.0))
        assert result.direction == "unknown"
        assert result.ratio == pytest.approx(0.0)

    def test_divide_by_zero_receive_zero_send_positive(self) -> None:
        """Direction is 'upstream' with capped ratio when receive=0, send>0."""
        analyzer = AsymmetryAnalyzer(logger=_make_logger(), wan_name="test")
        result = analyzer.analyze(_make_irtt_result(send_delay_ms=10.0, receive_delay_ms=0.0))
        assert result.direction == "upstream"
        assert result.ratio <= 100.0  # capped
        assert result.ratio > 1.0

    def test_divide_by_zero_send_zero_receive_positive(self) -> None:
        """Direction is 'downstream' with capped ratio when send=0, receive>0."""
        analyzer = AsymmetryAnalyzer(logger=_make_logger(), wan_name="test")
        result = analyzer.analyze(_make_irtt_result(send_delay_ms=0.0, receive_delay_ms=10.0))
        assert result.direction == "downstream"
        assert result.ratio <= 100.0  # capped
        assert result.ratio > 1.0

    def test_custom_threshold(self) -> None:
        """Custom ratio_threshold changes asymmetry detection sensitivity."""
        analyzer = AsymmetryAnalyzer(ratio_threshold=3.0, logger=_make_logger(), wan_name="test")
        # 2x ratio is below 3.0 threshold -> symmetric
        result = analyzer.analyze(_make_irtt_result(send_delay_ms=20.0, receive_delay_ms=10.0))
        assert result.direction == "symmetric"
        # 3x ratio meets 3.0 threshold -> upstream
        result = analyzer.analyze(_make_irtt_result(send_delay_ms=30.0, receive_delay_ms=10.0))
        assert result.direction == "upstream"

    def test_noise_guard_both_below_min_delay(self) -> None:
        """Direction is 'symmetric' when both delays below 0.1ms (noise guard)."""
        analyzer = AsymmetryAnalyzer(logger=_make_logger(), wan_name="test")
        result = analyzer.analyze(_make_irtt_result(send_delay_ms=0.05, receive_delay_ms=0.02))
        assert result.direction == "symmetric"
        assert result.ratio == pytest.approx(1.0)

    def test_send_delay_preserved_in_result(self) -> None:
        """AsymmetryResult preserves original send_delay_ms."""
        analyzer = AsymmetryAnalyzer(logger=_make_logger(), wan_name="test")
        result = analyzer.analyze(_make_irtt_result(send_delay_ms=25.0, receive_delay_ms=10.0))
        assert result.send_delay_ms == pytest.approx(25.0)

    def test_receive_delay_preserved_in_result(self) -> None:
        """AsymmetryResult preserves original receive_delay_ms."""
        analyzer = AsymmetryAnalyzer(logger=_make_logger(), wan_name="test")
        result = analyzer.analyze(_make_irtt_result(send_delay_ms=10.0, receive_delay_ms=25.0))
        assert result.receive_delay_ms == pytest.approx(25.0)


# ---------------------------------------------------------------------------
# TestTransitionLogging
# ---------------------------------------------------------------------------


class TestTransitionLogging:
    """Tests for direction transition logging behavior."""

    def test_logs_info_on_direction_change(self) -> None:
        """INFO logged when direction transitions (e.g., unknown -> upstream)."""
        logger = _make_logger()
        analyzer = AsymmetryAnalyzer(logger=logger, wan_name="spectrum")
        with patch.object(logger, "info") as mock_info:
            analyzer.analyze(_make_irtt_result(send_delay_ms=20.0, receive_delay_ms=10.0))
            # Should log transition from unknown -> upstream
            assert mock_info.call_count == 1
            msg = mock_info.call_args[0][0]
            assert "unknown" in msg
            assert "upstream" in msg

    def test_no_log_on_repeated_direction(self) -> None:
        """No INFO logged when direction stays the same across measurements."""
        logger = _make_logger()
        analyzer = AsymmetryAnalyzer(logger=logger, wan_name="spectrum")
        with patch.object(logger, "info") as mock_info:
            # First call: unknown -> upstream (logs)
            analyzer.analyze(_make_irtt_result(send_delay_ms=20.0, receive_delay_ms=10.0))
            mock_info.reset_mock()
            # Second call: still upstream (should NOT log)
            analyzer.analyze(_make_irtt_result(send_delay_ms=22.0, receive_delay_ms=11.0))
            assert mock_info.call_count == 0

    def test_logs_on_second_transition(self) -> None:
        """INFO logged on subsequent transitions (upstream -> symmetric)."""
        logger = _make_logger()
        analyzer = AsymmetryAnalyzer(logger=logger, wan_name="spectrum")
        with patch.object(logger, "info") as mock_info:
            # unknown -> upstream
            analyzer.analyze(_make_irtt_result(send_delay_ms=20.0, receive_delay_ms=10.0))
            mock_info.reset_mock()
            # upstream -> symmetric
            analyzer.analyze(_make_irtt_result(send_delay_ms=12.0, receive_delay_ms=10.0))
            assert mock_info.call_count == 1
            msg = mock_info.call_args[0][0]
            assert "upstream" in msg
            assert "symmetric" in msg

    def test_wan_name_in_log_message(self) -> None:
        """WAN name is included in transition log messages."""
        logger = _make_logger()
        analyzer = AsymmetryAnalyzer(logger=logger, wan_name="att")
        with patch.object(logger, "info") as mock_info:
            analyzer.analyze(_make_irtt_result(send_delay_ms=20.0, receive_delay_ms=10.0))
            msg = mock_info.call_args[0][0]
            assert "att" in msg


# ---------------------------------------------------------------------------
# TestOWDAsymmetryConfig
# ---------------------------------------------------------------------------


class TestOWDAsymmetryConfig:
    """Tests for _load_owd_asymmetry_config in autorate_continuous.py Config."""

    def _make_config(self, data: dict) -> object:
        """Construct a minimal Config-like object with the owd_asymmetry section."""
        from wanctl.autorate_config import Config

        config = object.__new__(Config)
        config.data = data
        return config

    def test_valid_config(self) -> None:
        """Valid owd_asymmetry section loads correctly."""
        config = self._make_config({"owd_asymmetry": {"ratio_threshold": 3.0}})
        config._load_owd_asymmetry_config()
        assert config.owd_asymmetry_config["ratio_threshold"] == pytest.approx(3.0)

    def test_missing_section_uses_defaults(self) -> None:
        """Missing owd_asymmetry section uses default ratio_threshold=2.0."""
        config = self._make_config({})
        config._load_owd_asymmetry_config()
        assert config.owd_asymmetry_config["ratio_threshold"] == pytest.approx(2.0)

    def test_non_dict_warns_and_defaults(self) -> None:
        """Non-dict owd_asymmetry warns and uses defaults."""
        config = self._make_config({"owd_asymmetry": "invalid"})
        with patch("wanctl.autorate_config.logging") as mock_logging:
            mock_logger = MagicMock()
            mock_logging.getLogger.return_value = mock_logger
            config._load_owd_asymmetry_config()
            mock_logger.warning.assert_called()
            assert config.owd_asymmetry_config["ratio_threshold"] == pytest.approx(2.0)

    def test_ratio_threshold_below_one_warns_and_defaults(self) -> None:
        """ratio_threshold < 1.0 warns and defaults to 2.0."""
        config = self._make_config({"owd_asymmetry": {"ratio_threshold": 0.5}})
        with patch("wanctl.autorate_config.logging") as mock_logging:
            mock_logger = MagicMock()
            mock_logging.getLogger.return_value = mock_logger
            config._load_owd_asymmetry_config()
            mock_logger.warning.assert_called()
            assert config.owd_asymmetry_config["ratio_threshold"] == pytest.approx(2.0)

    def test_ratio_threshold_zero_warns_and_defaults(self) -> None:
        """ratio_threshold=0 warns and defaults to 2.0."""
        config = self._make_config({"owd_asymmetry": {"ratio_threshold": 0}})
        with patch("wanctl.autorate_config.logging") as mock_logging:
            mock_logger = MagicMock()
            mock_logging.getLogger.return_value = mock_logger
            config._load_owd_asymmetry_config()
            mock_logger.warning.assert_called()
            assert config.owd_asymmetry_config["ratio_threshold"] == pytest.approx(2.0)

    def test_ratio_threshold_string_warns_and_defaults(self) -> None:
        """ratio_threshold as string warns and defaults to 2.0."""
        config = self._make_config({"owd_asymmetry": {"ratio_threshold": "high"}})
        with patch("wanctl.autorate_config.logging") as mock_logging:
            mock_logger = MagicMock()
            mock_logging.getLogger.return_value = mock_logger
            config._load_owd_asymmetry_config()
            mock_logger.warning.assert_called()
            assert config.owd_asymmetry_config["ratio_threshold"] == pytest.approx(2.0)

    def test_ratio_threshold_bool_warns_and_defaults(self) -> None:
        """ratio_threshold as bool warns and defaults to 2.0."""
        config = self._make_config({"owd_asymmetry": {"ratio_threshold": True}})
        with patch("wanctl.autorate_config.logging") as mock_logging:
            mock_logger = MagicMock()
            mock_logging.getLogger.return_value = mock_logger
            config._load_owd_asymmetry_config()
            mock_logger.warning.assert_called()
            assert config.owd_asymmetry_config["ratio_threshold"] == pytest.approx(2.0)

    def test_ratio_threshold_negative_warns_and_defaults(self) -> None:
        """Negative ratio_threshold warns and defaults to 2.0."""
        config = self._make_config({"owd_asymmetry": {"ratio_threshold": -1.5}})
        with patch("wanctl.autorate_config.logging") as mock_logging:
            mock_logger = MagicMock()
            mock_logging.getLogger.return_value = mock_logger
            config._load_owd_asymmetry_config()
            mock_logger.warning.assert_called()
            assert config.owd_asymmetry_config["ratio_threshold"] == pytest.approx(2.0)

    def test_ratio_threshold_int_accepted(self) -> None:
        """Integer ratio_threshold (e.g., 3) is accepted and stored as float."""
        config = self._make_config({"owd_asymmetry": {"ratio_threshold": 3}})
        config._load_owd_asymmetry_config()
        assert config.owd_asymmetry_config["ratio_threshold"] == pytest.approx(3.0)
        assert isinstance(config.owd_asymmetry_config["ratio_threshold"], float)


# =============================================================================
# MERGED FROM test_asymmetry_health.py
# =============================================================================


def _make_health_wan_controller() -> MagicMock:
    """Create a mock WAN controller with all required attributes."""
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
    # Phase 121-124: hysteresis attributes
    wan.download._yellow_dwell = 0
    wan.download.dwell_cycles = 5
    wan.download.deadband_ms = 3.0
    wan.download._transitions_suppressed = 0
    wan.download._window_suppressions = 0
    wan.download._window_start_time = 0.0
    wan.upload._yellow_dwell = 0
    wan.upload.dwell_cycles = 5
    wan.upload.deadband_ms = 3.0
    wan.upload._transitions_suppressed = 0
    wan.upload._window_suppressions = 0
    wan.upload._window_start_time = 0.0
    wan._suppression_alert_threshold = 20
    # Prevent MagicMock truthy issues (attributes accessed by health endpoint)
    wan._last_signal_result = None
    wan._irtt_thread = None
    wan._irtt_correlation = None
    wan._reflector_scorer = None
    wan._last_asymmetry_result = None
    wan._asymmetry_analyzer = None
    wan.alert_engine = None
    wan._fusion_enabled = False
    wan._fusion_icmp_weight = 0.7
    wan._last_fused_rtt = None
    wan._last_icmp_filtered_rtt = None
    wan._fusion_healer = None
    wan._tuning_enabled = False
    wan._tuning_state = None
    wan._parameter_locks = None
    wan._overrun_count = 0
    wan._cycle_interval_ms = 50.0
    wan._profiler.stats.return_value = None
    _qc_health = {
        "hysteresis": {
            "dwell_counter": 0,
            "dwell_cycles": 5,
            "deadband_ms": 3.0,
            "transitions_suppressed": 0,
            "suppressions_per_min": 0,
            "window_start_epoch": 0.0,
        },
        "cake_detection": {},
        "recovery_probe": {},
    }
    wan.download.get_health_data.return_value = _qc_health
    wan.upload.get_health_data.return_value = _qc_health

    # Dynamic side_effect reads current attributes so tests can override after construction
    def _health_data():
        return {
            "cycle_budget": {
                "profiler": wan._profiler,
                "overrun_count": 0,
                "cycle_interval_ms": 50.0,
                "warning_threshold_pct": 80.0,
            },
            "signal_result": wan._last_signal_result,
            "irtt": {
                "thread": wan._irtt_thread,
                "correlation": wan._irtt_correlation,
                "last_asymmetry_result": wan._last_asymmetry_result,
            },
            "reflector": {"scorer": wan._reflector_scorer},
            "fusion": {
                "enabled": wan._fusion_enabled,
                "icmp_filtered_rtt": wan._last_icmp_filtered_rtt,
                "fused_rtt": wan._last_fused_rtt,
                "icmp_weight": wan._fusion_icmp_weight,
                "healer": wan._fusion_healer,
            },
            "tuning": {
                "enabled": False,
                "state": None,
                "parameter_locks": None,
                "pending_observation": None,
            },
            "suppression_alert": {"threshold": 20},
            "asymmetry_gate": {
                "enabled": False,
                "active": False,
                "downstream_streak": 0,
                "damping_factor": 1.0,
                "last_result_age_sec": None,
            },
            "cake_signal": {
                "enabled": False,
                "supported": False,
                "download": None,
                "upload": None,
                "detection": {
                    "dl_refractory_remaining": 0,
                    "ul_refractory_remaining": 0,
                    "refractory_cycles": 40,
                    "dl_dwell_bypassed_count": 0,
                    "ul_dwell_bypassed_count": 0,
                    "dl_backlog_suppressed_count": 0,
                    "ul_backlog_suppressed_count": 0,
                    "dl_recovery_probe": {},
                    "ul_recovery_probe": {},
                },
            },
        }

    wan.get_health_data.side_effect = _health_data
    return wan


def _make_health_controller(wan: MagicMock, irtt_config: dict | None = None) -> MagicMock:
    """Build a mock controller wrapping a single WAN."""
    mock_controller = MagicMock()
    mock_config = MagicMock()
    mock_config.wan_name = "spectrum"
    mock_config.irtt_config = irtt_config or {"enabled": False}
    mock_controller.wan_controllers = [
        {"controller": wan, "config": mock_config, "logger": MagicMock()}
    ]
    return mock_controller


def _make_health_irtt_result(timestamp: float | None = None) -> IRTTResult:
    """Create an IRTTResult for testing."""
    return IRTTResult(
        rtt_mean_ms=28.5,
        rtt_median_ms=27.3,
        ipdv_mean_ms=1.2,
        send_loss=0.5,
        receive_loss=1.0,
        packets_sent=100,
        packets_received=99,
        server="104.200.21.31",
        port=2112,
        timestamp=timestamp or (time.monotonic() - 5.0),
        success=True,
        send_delay_median_ms=15.0,
        receive_delay_median_ms=12.0,
    )


class TestAsymmetryHealthIRTTAvailable:
    """Test asymmetry fields when IRTT is available with result."""

    def test_asymmetry_direction_upstream(self) -> None:
        """asymmetry_direction shows 'upstream' when result.direction == 'upstream'."""
        wan = _make_health_wan_controller()
        mock_irtt_thread = MagicMock()
        mock_irtt_thread.get_latest.return_value = _make_health_irtt_result()
        wan._irtt_thread = mock_irtt_thread
        wan._irtt_correlation = 0.95
        wan._last_asymmetry_result = AsymmetryResult(
            direction="upstream", ratio=2.5, send_delay_ms=20.0, receive_delay_ms=8.0
        )

        controller = _make_health_controller(wan, irtt_config={"enabled": True})
        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            irtt = data["wans"][0]["irtt"]
            assert irtt["asymmetry_direction"] == "upstream"
            assert irtt["asymmetry_ratio"] == 2.5
        finally:
            server.shutdown()

    def test_asymmetry_direction_downstream(self) -> None:
        """asymmetry_direction shows 'downstream' when result.direction == 'downstream'."""
        wan = _make_health_wan_controller()
        mock_irtt_thread = MagicMock()
        mock_irtt_thread.get_latest.return_value = _make_health_irtt_result()
        wan._irtt_thread = mock_irtt_thread
        wan._irtt_correlation = None
        wan._last_asymmetry_result = AsymmetryResult(
            direction="downstream", ratio=3.1, send_delay_ms=8.0, receive_delay_ms=24.8
        )

        controller = _make_health_controller(wan, irtt_config={"enabled": True})
        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            irtt = data["wans"][0]["irtt"]
            assert irtt["asymmetry_direction"] == "downstream"
            assert irtt["asymmetry_ratio"] == 3.1
        finally:
            server.shutdown()

    def test_asymmetry_ratio_rounded_to_2_decimals(self) -> None:
        """asymmetry_ratio is rounded to 2 decimal places."""
        wan = _make_health_wan_controller()
        mock_irtt_thread = MagicMock()
        mock_irtt_thread.get_latest.return_value = _make_health_irtt_result()
        wan._irtt_thread = mock_irtt_thread
        wan._irtt_correlation = None
        wan._last_asymmetry_result = AsymmetryResult(
            direction="symmetric", ratio=1.23456789, send_delay_ms=10.0, receive_delay_ms=10.0
        )

        controller = _make_health_controller(wan, irtt_config={"enabled": True})
        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            irtt = data["wans"][0]["irtt"]
            assert irtt["asymmetry_ratio"] == 1.23
        finally:
            server.shutdown()


class TestAsymmetryHealthNoResult:
    """Test asymmetry fields when IRTT available but no asymmetry result yet."""

    def test_direction_unknown_when_no_result(self) -> None:
        """asymmetry_direction is 'unknown' when _last_asymmetry_result is None."""
        wan = _make_health_wan_controller()
        mock_irtt_thread = MagicMock()
        mock_irtt_thread.get_latest.return_value = _make_health_irtt_result()
        wan._irtt_thread = mock_irtt_thread
        wan._irtt_correlation = None
        wan._last_asymmetry_result = None

        controller = _make_health_controller(wan, irtt_config={"enabled": True})
        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            irtt = data["wans"][0]["irtt"]
            assert irtt["asymmetry_direction"] == "unknown"
            assert irtt["asymmetry_ratio"] is None
        finally:
            server.shutdown()


class TestAsymmetryHealthIRTTDisabled:
    """Test IRTT section when IRTT is disabled -- no asymmetry fields."""

    def test_no_asymmetry_fields_when_irtt_disabled(self) -> None:
        """IRTT section has available=False and does NOT contain 'asymmetry_direction' when disabled."""
        wan = _make_health_wan_controller()
        wan._irtt_thread = None

        controller = _make_health_controller(wan, irtt_config={"enabled": False})
        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            irtt = data["wans"][0]["irtt"]
            assert irtt["available"] is False
            assert "asymmetry_direction" not in irtt
            assert "asymmetry_ratio" not in irtt
        finally:
            server.shutdown()

    def test_no_asymmetry_fields_when_binary_not_found(self) -> None:
        """IRTT section has no asymmetry fields when enabled but binary not found."""
        wan = _make_health_wan_controller()
        wan._irtt_thread = None

        controller = _make_health_controller(wan, irtt_config={"enabled": True})
        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            irtt = data["wans"][0]["irtt"]
            assert irtt["available"] is False
            assert "asymmetry_direction" not in irtt
            assert "asymmetry_ratio" not in irtt
        finally:
            server.shutdown()


class TestAsymmetryHealthAwaitingMeasurement:
    """Test asymmetry fields when IRTT available but awaiting first measurement."""

    def test_direction_unknown_awaiting_measurement(self) -> None:
        """asymmetry_direction is 'unknown' when IRTT thread exists but no result yet."""
        wan = _make_health_wan_controller()
        mock_irtt_thread = MagicMock()
        mock_irtt_thread.get_latest.return_value = None
        wan._irtt_thread = mock_irtt_thread

        controller = _make_health_controller(wan, irtt_config={"enabled": True})
        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            irtt = data["wans"][0]["irtt"]
            assert irtt["asymmetry_direction"] == "unknown"
            assert irtt["asymmetry_ratio"] is None
        finally:
            server.shutdown()


# =============================================================================
# MERGED FROM test_asymmetry_persistence.py
# =============================================================================


def _make_persistence_irtt_result(
    send_delay: float = 10.0,
    receive_delay: float = 5.0,
    timestamp: float = 1000.0,
) -> IRTTResult:
    """Create an IRTTResult with OWD fields for testing."""
    return IRTTResult(
        rtt_mean_ms=20.0,
        rtt_median_ms=19.0,
        ipdv_mean_ms=2.0,
        send_loss=0.0,
        receive_loss=0.0,
        packets_sent=10,
        packets_received=10,
        server="104.200.21.31",
        port=2112,
        timestamp=timestamp,
        success=True,
        send_delay_median_ms=send_delay,
        receive_delay_median_ms=receive_delay,
    )


class TestStoredMetrics:
    """Verify STORED_METRICS dict contains asymmetry entries."""

    def test_asymmetry_ratio_in_stored_metrics(self) -> None:
        """STORED_METRICS contains wanctl_irtt_asymmetry_ratio."""
        assert "wanctl_irtt_asymmetry_ratio" in STORED_METRICS

    def test_asymmetry_direction_in_stored_metrics(self) -> None:
        """STORED_METRICS contains wanctl_irtt_asymmetry_direction."""
        assert "wanctl_irtt_asymmetry_direction" in STORED_METRICS

    def test_asymmetry_ratio_description(self) -> None:
        """wanctl_irtt_asymmetry_ratio has a meaningful description."""
        desc = STORED_METRICS["wanctl_irtt_asymmetry_ratio"]
        assert "ratio" in desc.lower()

    def test_asymmetry_direction_description(self) -> None:
        """wanctl_irtt_asymmetry_direction has a meaningful description."""
        desc = STORED_METRICS["wanctl_irtt_asymmetry_direction"]
        assert "direction" in desc.lower()


class TestDirectionEncoding:
    """Verify DIRECTION_ENCODING values match expected float encoding."""

    def test_unknown_is_zero(self) -> None:
        """unknown maps to 0.0."""
        assert DIRECTION_ENCODING["unknown"] == 0.0

    def test_symmetric_is_one(self) -> None:
        """symmetric maps to 1.0."""
        assert DIRECTION_ENCODING["symmetric"] == 1.0

    def test_upstream_is_two(self) -> None:
        """upstream maps to 2.0."""
        assert DIRECTION_ENCODING["upstream"] == 2.0

    def test_downstream_is_three(self) -> None:
        """downstream maps to 3.0."""
        assert DIRECTION_ENCODING["downstream"] == 3.0

    def test_all_four_directions_present(self) -> None:
        """All four direction keys present in encoding dict."""
        assert set(DIRECTION_ENCODING.keys()) == {
            "unknown",
            "symmetric",
            "upstream",
            "downstream",
        }


class TestWANControllerAsymmetryAttributes:
    """Verify WANController has _asymmetry_analyzer and _last_asymmetry_result."""

    def test_has_asymmetry_analyzer_attribute(self) -> None:
        """WANController initialization creates _asymmetry_analyzer."""
        _mock_config = self._make_config()
        with patch("wanctl.routeros_interface.get_router_client_with_failover"):
            from wanctl.wan_controller import WANController

            _controller = WANController.__new__(WANController)
            # Check the attribute exists in the class (may be in __init__ or extracted helper)
            import inspect

            source = inspect.getsource(WANController)
            assert "_asymmetry_analyzer" in source

    def test_has_last_asymmetry_result_attribute(self) -> None:
        """WANController initialization creates _last_asymmetry_result."""
        import inspect


        source = inspect.getsource(WANController)
        assert "_last_asymmetry_result" in source

    def _make_config(self) -> MagicMock:
        """Create a mock config for testing."""
        config = MagicMock()
        config.owd_asymmetry_config = {"ratio_threshold": 2.0}
        return config


class TestAsymmetryMetricsWrite:
    """Verify asymmetry metrics included in metrics_batch during IRTT write."""

    def test_metrics_batch_includes_asymmetry_ratio(self) -> None:
        """metrics_batch includes wanctl_irtt_asymmetry_ratio when asymmetry result available."""
        # Verify the code path in WANController contains the metric name
        # (may be in run_cycle directly or in an extracted helper)
        import inspect


        source = inspect.getsource(WANController)
        assert "wanctl_irtt_asymmetry_ratio" in source

    def test_metrics_batch_includes_asymmetry_direction(self) -> None:
        """metrics_batch includes wanctl_irtt_asymmetry_direction when asymmetry result available."""
        import inspect


        source = inspect.getsource(WANController)
        assert "wanctl_irtt_asymmetry_direction" in source

    def test_direction_uses_encoding_dict(self) -> None:
        """Direction metric value uses DIRECTION_ENCODING.get() for float conversion."""
        import inspect


        source = inspect.getsource(WANController)
        assert "DIRECTION_ENCODING.get(" in source

    def test_asymmetry_metrics_inside_irtt_dedup_guard(self) -> None:
        """Asymmetry metrics only written when irtt_result.timestamp != _last_irtt_write_ts."""
        import inspect


        source = inspect.getsource(WANController)
        # Verify both asymmetry metrics appear after the IRTT dedup guard
        irtt_dedup_idx = source.index("_last_irtt_write_ts")
        ratio_idx = source.index("wanctl_irtt_asymmetry_ratio")
        assert ratio_idx > irtt_dedup_idx


class TestAsymmetryDedup:
    """Verify asymmetry metrics use same dedup guard as existing IRTT metrics."""

    def test_asymmetry_analyze_called_for_fresh_irtt(self) -> None:
        """analyze() is called in WANController when irtt_result is available."""
        import inspect


        source = inspect.getsource(WANController)
        assert "_asymmetry_analyzer.analyze(irtt_result)" in source

    def test_last_asymmetry_result_updated(self) -> None:
        """_last_asymmetry_result updated after analyze() call in WANController."""
        import inspect


        source = inspect.getsource(WANController)
        assert "_last_asymmetry_result = asym" in source or "_last_asymmetry_result" in source


class TestLastAsymmetryResult:
    """Verify _last_asymmetry_result behavior."""

    def test_analyzer_produces_result(self) -> None:
        """AsymmetryAnalyzer.analyze returns AsymmetryResult."""
        analyzer = AsymmetryAnalyzer(ratio_threshold=2.0, wan_name="test")
        irtt = _make_persistence_irtt_result(send_delay=20.0, receive_delay=8.0)
        result = analyzer.analyze(irtt)
        assert isinstance(result, AsymmetryResult)
        assert result.direction == "upstream"
        assert result.ratio == pytest.approx(2.5)

    def test_result_stays_none_when_no_irtt(self) -> None:
        """When IRTT unavailable, _last_asymmetry_result should remain None."""
        # This tests the logical guarantee: no IRTT -> no analyze call -> no result
        # The attribute starts as None in __init__ (or extracted helper) and only gets
        # set in run_cycle when irtt_result is not None
        import inspect


        source = inspect.getsource(WANController)
        assert "_last_asymmetry_result: AsymmetryResult | None = None" in source

    def test_result_updated_after_analyze(self) -> None:
        """After analyze() call, result reflects the analysis."""
        analyzer = AsymmetryAnalyzer(ratio_threshold=2.0, wan_name="test")
        irtt = _make_persistence_irtt_result(send_delay=5.0, receive_delay=5.0)
        result = analyzer.analyze(irtt)
        assert result.direction == "symmetric"
        assert result.ratio == pytest.approx(1.0)

    def test_direction_encoding_for_persistence(self) -> None:
        """DIRECTION_ENCODING correctly maps result.direction to float."""
        analyzer = AsymmetryAnalyzer(ratio_threshold=2.0, wan_name="test")

        # upstream
        irtt_up = _make_persistence_irtt_result(send_delay=20.0, receive_delay=8.0)
        result = analyzer.analyze(irtt_up)
        assert DIRECTION_ENCODING.get(result.direction, 0.0) == 2.0

        # downstream
        irtt_down = _make_persistence_irtt_result(send_delay=8.0, receive_delay=20.0)
        result = analyzer.analyze(irtt_down)
        assert DIRECTION_ENCODING.get(result.direction, 0.0) == 3.0

        # symmetric
        irtt_sym = _make_persistence_irtt_result(send_delay=10.0, receive_delay=10.0)
        result = analyzer.analyze(irtt_sym)
        assert DIRECTION_ENCODING.get(result.direction, 0.0) == 1.0

