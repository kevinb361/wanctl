"""Unit tests for AsymmetryAnalyzer, AsymmetryResult, and OWD config loading."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from wanctl.asymmetry_analyzer import (
    DIRECTION_ENCODING,
    AsymmetryAnalyzer,
    AsymmetryResult,
)
from wanctl.irtt_measurement import IRTTResult


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
        analyzer = AsymmetryAnalyzer(
            ratio_threshold=3.0, logger=_make_logger(), wan_name="test"
        )
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
        from wanctl.autorate_continuous import Config

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
        with patch("wanctl.autorate_continuous.logging") as mock_logging:
            mock_logger = MagicMock()
            mock_logging.getLogger.return_value = mock_logger
            config._load_owd_asymmetry_config()
            mock_logger.warning.assert_called()
            assert config.owd_asymmetry_config["ratio_threshold"] == pytest.approx(2.0)

    def test_ratio_threshold_below_one_warns_and_defaults(self) -> None:
        """ratio_threshold < 1.0 warns and defaults to 2.0."""
        config = self._make_config({"owd_asymmetry": {"ratio_threshold": 0.5}})
        with patch("wanctl.autorate_continuous.logging") as mock_logging:
            mock_logger = MagicMock()
            mock_logging.getLogger.return_value = mock_logger
            config._load_owd_asymmetry_config()
            mock_logger.warning.assert_called()
            assert config.owd_asymmetry_config["ratio_threshold"] == pytest.approx(2.0)

    def test_ratio_threshold_zero_warns_and_defaults(self) -> None:
        """ratio_threshold=0 warns and defaults to 2.0."""
        config = self._make_config({"owd_asymmetry": {"ratio_threshold": 0}})
        with patch("wanctl.autorate_continuous.logging") as mock_logging:
            mock_logger = MagicMock()
            mock_logging.getLogger.return_value = mock_logger
            config._load_owd_asymmetry_config()
            mock_logger.warning.assert_called()
            assert config.owd_asymmetry_config["ratio_threshold"] == pytest.approx(2.0)

    def test_ratio_threshold_string_warns_and_defaults(self) -> None:
        """ratio_threshold as string warns and defaults to 2.0."""
        config = self._make_config({"owd_asymmetry": {"ratio_threshold": "high"}})
        with patch("wanctl.autorate_continuous.logging") as mock_logging:
            mock_logger = MagicMock()
            mock_logging.getLogger.return_value = mock_logger
            config._load_owd_asymmetry_config()
            mock_logger.warning.assert_called()
            assert config.owd_asymmetry_config["ratio_threshold"] == pytest.approx(2.0)

    def test_ratio_threshold_bool_warns_and_defaults(self) -> None:
        """ratio_threshold as bool warns and defaults to 2.0."""
        config = self._make_config({"owd_asymmetry": {"ratio_threshold": True}})
        with patch("wanctl.autorate_continuous.logging") as mock_logging:
            mock_logger = MagicMock()
            mock_logging.getLogger.return_value = mock_logger
            config._load_owd_asymmetry_config()
            mock_logger.warning.assert_called()
            assert config.owd_asymmetry_config["ratio_threshold"] == pytest.approx(2.0)

    def test_ratio_threshold_negative_warns_and_defaults(self) -> None:
        """Negative ratio_threshold warns and defaults to 2.0."""
        config = self._make_config({"owd_asymmetry": {"ratio_threshold": -1.5}})
        with patch("wanctl.autorate_continuous.logging") as mock_logging:
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
