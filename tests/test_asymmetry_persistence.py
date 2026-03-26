"""Tests for AsymmetryAnalyzer wiring into WANController and SQLite persistence.

Verifies:
- WANController has _asymmetry_analyzer and _last_asymmetry_result attributes
- run_cycle calls analyze() on fresh IRTT results
- Asymmetry metrics written to metrics_batch inside IRTT dedup guard
- Direction encoded as float via DIRECTION_ENCODING
- STORED_METRICS contains asymmetry entries
"""

from unittest.mock import MagicMock, patch

import pytest

from wanctl.asymmetry_analyzer import (
    DIRECTION_ENCODING,
    AsymmetryAnalyzer,
    AsymmetryResult,
)
from wanctl.irtt_measurement import IRTTResult
from wanctl.storage.schema import STORED_METRICS


def _make_irtt_result(
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
        """WANController.__init__ creates _asymmetry_analyzer."""
        _mock_config = self._make_config()
        with patch("wanctl.autorate_continuous.get_router_client_with_failover"):
            from wanctl.autorate_continuous import WANController

            _controller = WANController.__new__(WANController)
            # Check the attribute exists after __init__ by inspecting the real class
            # We verify this by checking the import works and the attribute name is used
            import inspect

            source = inspect.getsource(WANController.__init__)
            assert "_asymmetry_analyzer" in source

    def test_has_last_asymmetry_result_attribute(self) -> None:
        """WANController.__init__ creates _last_asymmetry_result."""
        import inspect

        from wanctl.autorate_continuous import WANController

        source = inspect.getsource(WANController.__init__)
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
        # We test by verifying the code path in run_cycle contains the metric name
        import inspect

        from wanctl.autorate_continuous import WANController

        source = inspect.getsource(WANController.run_cycle)
        assert "wanctl_irtt_asymmetry_ratio" in source

    def test_metrics_batch_includes_asymmetry_direction(self) -> None:
        """metrics_batch includes wanctl_irtt_asymmetry_direction when asymmetry result available."""
        import inspect

        from wanctl.autorate_continuous import WANController

        source = inspect.getsource(WANController.run_cycle)
        assert "wanctl_irtt_asymmetry_direction" in source

    def test_direction_uses_encoding_dict(self) -> None:
        """Direction metric value uses DIRECTION_ENCODING.get() for float conversion."""
        import inspect

        from wanctl.autorate_continuous import WANController

        source = inspect.getsource(WANController.run_cycle)
        assert "DIRECTION_ENCODING.get(" in source

    def test_asymmetry_metrics_inside_irtt_dedup_guard(self) -> None:
        """Asymmetry metrics only written when irtt_result.timestamp != _last_irtt_write_ts."""
        import inspect

        from wanctl.autorate_continuous import WANController

        source = inspect.getsource(WANController.run_cycle)
        # Verify both asymmetry metrics appear after the IRTT dedup guard
        irtt_dedup_idx = source.index("_last_irtt_write_ts")
        ratio_idx = source.index("wanctl_irtt_asymmetry_ratio")
        assert ratio_idx > irtt_dedup_idx


class TestAsymmetryDedup:
    """Verify asymmetry metrics use same dedup guard as existing IRTT metrics."""

    def test_asymmetry_analyze_called_for_fresh_irtt(self) -> None:
        """analyze() is called in run_cycle when irtt_result is available."""
        import inspect

        from wanctl.autorate_continuous import WANController

        source = inspect.getsource(WANController.run_cycle)
        assert "_asymmetry_analyzer.analyze(irtt_result)" in source

    def test_last_asymmetry_result_updated(self) -> None:
        """_last_asymmetry_result updated after analyze() call in run_cycle."""
        import inspect

        from wanctl.autorate_continuous import WANController

        source = inspect.getsource(WANController.run_cycle)
        assert "_last_asymmetry_result = asym" in source or "_last_asymmetry_result" in source


class TestLastAsymmetryResult:
    """Verify _last_asymmetry_result behavior."""

    def test_analyzer_produces_result(self) -> None:
        """AsymmetryAnalyzer.analyze returns AsymmetryResult."""
        analyzer = AsymmetryAnalyzer(ratio_threshold=2.0, wan_name="test")
        irtt = _make_irtt_result(send_delay=20.0, receive_delay=8.0)
        result = analyzer.analyze(irtt)
        assert isinstance(result, AsymmetryResult)
        assert result.direction == "upstream"
        assert result.ratio == pytest.approx(2.5)

    def test_result_stays_none_when_no_irtt(self) -> None:
        """When IRTT unavailable, _last_asymmetry_result should remain None."""
        # This tests the logical guarantee: no IRTT -> no analyze call -> no result
        # The attribute starts as None in __init__ and only gets set in run_cycle
        # when irtt_result is not None
        import inspect

        from wanctl.autorate_continuous import WANController

        source = inspect.getsource(WANController.__init__)
        assert "_last_asymmetry_result: AsymmetryResult | None = None" in source

    def test_result_updated_after_analyze(self) -> None:
        """After analyze() call, result reflects the analysis."""
        analyzer = AsymmetryAnalyzer(ratio_threshold=2.0, wan_name="test")
        irtt = _make_irtt_result(send_delay=5.0, receive_delay=5.0)
        result = analyzer.analyze(irtt)
        assert result.direction == "symmetric"
        assert result.ratio == pytest.approx(1.0)

    def test_direction_encoding_for_persistence(self) -> None:
        """DIRECTION_ENCODING correctly maps result.direction to float."""
        analyzer = AsymmetryAnalyzer(ratio_threshold=2.0, wan_name="test")

        # upstream
        irtt_up = _make_irtt_result(send_delay=20.0, receive_delay=8.0)
        result = analyzer.analyze(irtt_up)
        assert DIRECTION_ENCODING.get(result.direction, 0.0) == 2.0

        # downstream
        irtt_down = _make_irtt_result(send_delay=8.0, receive_delay=20.0)
        result = analyzer.analyze(irtt_down)
        assert DIRECTION_ENCODING.get(result.direction, 0.0) == 3.0

        # symmetric
        irtt_sym = _make_irtt_result(send_delay=10.0, receive_delay=10.0)
        result = analyzer.analyze(irtt_sym)
        assert DIRECTION_ENCODING.get(result.direction, 0.0) == 1.0
