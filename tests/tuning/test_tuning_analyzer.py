"""Tests for tuning analyzer -- per-WAN metric query and strategy orchestration."""

import logging
import time
from unittest.mock import MagicMock, patch

import pytest

from wanctl.tuning.models import SafetyBounds, TuningConfig, TuningResult


# Helper: build a TuningConfig for tests
def _make_config(
    lookback_hours: int = 24,
    warmup_hours: int = 4,
    max_step_pct: float = 10.0,
) -> TuningConfig:
    return TuningConfig(
        enabled=True,
        cadence_sec=3600,
        lookback_hours=lookback_hours,
        warmup_hours=warmup_hours,
        max_step_pct=max_step_pct,
        bounds={
            "target_bloat_ms": SafetyBounds(min_value=3.0, max_value=50.0),
        },
    )


def _make_metrics(
    count: int = 100,
    start_offset_hours: float = 24.0,
    wan_name: str = "Spectrum",
) -> list[dict]:
    """Generate fake metrics data spanning start_offset_hours ago to now."""
    now = int(time.time())
    start = now - int(start_offset_hours * 3600)
    interval = max(1, int((start_offset_hours * 3600) / count))
    return [
        {
            "timestamp": start + (i * interval),
            "wan_name": wan_name,
            "metric_name": "wanctl_rtt_ms",
            "value": 15.0 + (i * 0.01),
            "labels": None,
            "granularity": "1m",
        }
        for i in range(count)
    ]


class TestRunTuningAnalysisEmptyStrategies:
    """Empty strategies list returns empty result."""

    def test_no_strategies_returns_empty(self) -> None:
        from wanctl.tuning.analyzer import run_tuning_analysis

        result = run_tuning_analysis(
            wan_name="Spectrum",
            db_path="/tmp/test_does_not_exist.db",
            tuning_config=_make_config(),
            current_params={"target_bloat_ms": 15.0},
            strategies=[],
        )
        assert result == []


class TestRunTuningAnalysisNoData:
    """When query_metrics returns no data, returns [] with log message."""

    @patch("wanctl.tuning.analyzer.query_metrics", return_value=[])
    def test_no_metrics_data_returns_empty(
        self, mock_qm: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        from wanctl.tuning.analyzer import run_tuning_analysis

        dummy_strategy = MagicMock(return_value=None)
        with caplog.at_level(logging.INFO):
            result = run_tuning_analysis(
                wan_name="Spectrum",
                db_path="/tmp/test.db",
                tuning_config=_make_config(),
                current_params={"target_bloat_ms": 15.0},
                strategies=[("target_bloat_ms", dummy_strategy)],
            )
        assert result == []
        assert "no metrics data" in caplog.text


class TestRunTuningAnalysisWarmup:
    """Warmup check: insufficient data returns [] with log message."""

    @patch("wanctl.tuning.analyzer.query_metrics")
    def test_insufficient_warmup_returns_empty(
        self, mock_qm: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        from wanctl.tuning.analyzer import run_tuning_analysis

        # Return data spanning only 30 minutes, need 4 hours
        mock_qm.return_value = _make_metrics(count=10, start_offset_hours=0.5)
        dummy_strategy = MagicMock(return_value=None)

        with caplog.at_level(logging.INFO):
            result = run_tuning_analysis(
                wan_name="Spectrum",
                db_path="/tmp/test.db",
                tuning_config=_make_config(warmup_hours=4),
                current_params={"target_bloat_ms": 15.0},
                strategies=[("target_bloat_ms", dummy_strategy)],
            )
        assert result == []
        assert "minutes of data" in caplog.text
        assert "need 4 hours" in caplog.text

    @patch("wanctl.tuning.analyzer.query_metrics")
    def test_sufficient_warmup_proceeds(self, mock_qm: MagicMock) -> None:
        from wanctl.tuning.analyzer import run_tuning_analysis

        # Data spanning 8 hours (well above 4-hour warmup)
        mock_qm.return_value = _make_metrics(count=100, start_offset_hours=8.0)
        # Strategy returns None (no change) -- but analysis should proceed
        dummy_strategy = MagicMock(return_value=None)

        result = run_tuning_analysis(
            wan_name="Spectrum",
            db_path="/tmp/test.db",
            tuning_config=_make_config(warmup_hours=4),
            current_params={"target_bloat_ms": 15.0},
            strategies=[("target_bloat_ms", dummy_strategy)],
        )
        # Strategy was actually called (analysis proceeded past warmup)
        dummy_strategy.assert_called_once()
        assert result == []  # Strategy returned None


class TestRunTuningAnalysisStrategyResults:
    """Strategy returning TuningResult includes it in output; None excludes it."""

    @patch("wanctl.tuning.analyzer.query_metrics")
    def test_strategy_returning_result_included(self, mock_qm: MagicMock) -> None:
        from wanctl.tuning.analyzer import run_tuning_analysis

        mock_qm.return_value = _make_metrics(count=100, start_offset_hours=25.0)

        expected = TuningResult(
            parameter="target_bloat_ms",
            old_value=15.0,
            new_value=13.5,
            confidence=0.85,
            rationale="p75 delta",
            data_points=100,
            wan_name="Spectrum",
        )
        strategy = MagicMock(return_value=expected)

        result = run_tuning_analysis(
            wan_name="Spectrum",
            db_path="/tmp/test.db",
            tuning_config=_make_config(),
            current_params={"target_bloat_ms": 15.0},
            strategies=[("target_bloat_ms", strategy)],
        )
        assert len(result) == 1
        assert result[0].parameter == "target_bloat_ms"
        assert result[0].new_value == 13.5

    @patch("wanctl.tuning.analyzer.query_metrics")
    def test_strategy_returning_none_excluded(self, mock_qm: MagicMock) -> None:
        from wanctl.tuning.analyzer import run_tuning_analysis

        mock_qm.return_value = _make_metrics(count=100, start_offset_hours=25.0)
        strategy = MagicMock(return_value=None)

        result = run_tuning_analysis(
            wan_name="Spectrum",
            db_path="/tmp/test.db",
            tuning_config=_make_config(),
            current_params={"target_bloat_ms": 15.0},
            strategies=[("target_bloat_ms", strategy)],
        )
        assert result == []

    @patch("wanctl.tuning.analyzer.query_metrics")
    def test_strategy_exception_caught_and_logged(
        self, mock_qm: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        from wanctl.tuning.analyzer import run_tuning_analysis

        mock_qm.return_value = _make_metrics(count=100, start_offset_hours=25.0)
        strategy = MagicMock(side_effect=RuntimeError("boom"))

        with caplog.at_level(logging.WARNING):
            result = run_tuning_analysis(
                wan_name="Spectrum",
                db_path="/tmp/test.db",
                tuning_config=_make_config(),
                current_params={"target_bloat_ms": 15.0},
                strategies=[("target_bloat_ms", strategy)],
            )
        assert result == []
        assert "strategy for target_bloat_ms failed" in caplog.text


class TestRunTuningAnalysisPerWanIsolation:
    """Per-WAN isolation: query_metrics is called with wan=wan_name parameter."""

    @patch("wanctl.tuning.analyzer.query_metrics")
    def test_wan_parameter_passed(self, mock_qm: MagicMock) -> None:
        from wanctl.tuning.analyzer import run_tuning_analysis

        mock_qm.return_value = []
        dummy_strategy = MagicMock(return_value=None)

        run_tuning_analysis(
            wan_name="ATT",
            db_path="/tmp/test.db",
            tuning_config=_make_config(),
            current_params={"target_bloat_ms": 15.0},
            strategies=[("target_bloat_ms", dummy_strategy)],
        )
        mock_qm.assert_called_once()
        call_kwargs = mock_qm.call_args
        assert call_kwargs.kwargs.get("wan") == "ATT" or (
            len(call_kwargs.args) > 1 and call_kwargs.args[1] == "ATT"
        )


class TestRunTuningAnalysisLookback:
    """Lookback_hours is passed correctly to query start_ts."""

    @patch("wanctl.tuning.analyzer.query_metrics")
    @patch("wanctl.tuning.analyzer.time")
    def test_lookback_hours_in_query(self, mock_time: MagicMock, mock_qm: MagicMock) -> None:
        from wanctl.tuning.analyzer import run_tuning_analysis

        mock_time.time.return_value = 1000000.0
        mock_qm.return_value = []
        dummy_strategy = MagicMock(return_value=None)

        config = _make_config(lookback_hours=48)
        run_tuning_analysis(
            wan_name="Spectrum",
            db_path="/tmp/test.db",
            tuning_config=config,
            current_params={"target_bloat_ms": 15.0},
            strategies=[("target_bloat_ms", dummy_strategy)],
        )
        mock_qm.assert_called_once()
        call_kwargs = mock_qm.call_args
        # start_ts should be now - (48 * 3600) = 1000000 - 172800 = 827200
        expected_start = 1000000 - (48 * 3600)
        assert call_kwargs.kwargs.get("start_ts") == expected_start


class TestRunTuningAnalysisGranularity:
    """Query uses '1m' granularity."""

    @patch("wanctl.tuning.analyzer.query_metrics")
    def test_granularity_is_1m(self, mock_qm: MagicMock) -> None:
        from wanctl.tuning.analyzer import run_tuning_analysis

        mock_qm.return_value = []
        dummy_strategy = MagicMock(return_value=None)

        run_tuning_analysis(
            wan_name="Spectrum",
            db_path="/tmp/test.db",
            tuning_config=_make_config(),
            current_params={"target_bloat_ms": 15.0},
            strategies=[("target_bloat_ms", dummy_strategy)],
        )
        mock_qm.assert_called_once()
        call_kwargs = mock_qm.call_args
        assert call_kwargs.kwargs.get("granularity") == "1m"


class TestRunTuningAnalysisConfidenceScaling:
    """When data_hours < 24, confidence is scaled by min(1.0, data_hours / 24.0)."""

    @patch("wanctl.tuning.analyzer.query_metrics")
    def test_confidence_scaled_for_short_data(self, mock_qm: MagicMock) -> None:
        from wanctl.tuning.analyzer import run_tuning_analysis

        # 12 hours of data -> confidence scale = 0.5
        mock_qm.return_value = _make_metrics(count=100, start_offset_hours=12.0)

        raw_result = TuningResult(
            parameter="target_bloat_ms",
            old_value=15.0,
            new_value=13.5,
            confidence=0.8,
            rationale="p75 delta",
            data_points=100,
            wan_name="Spectrum",
        )
        strategy = MagicMock(return_value=raw_result)

        result = run_tuning_analysis(
            wan_name="Spectrum",
            db_path="/tmp/test.db",
            tuning_config=_make_config(warmup_hours=4),
            current_params={"target_bloat_ms": 15.0},
            strategies=[("target_bloat_ms", strategy)],
        )
        assert len(result) == 1
        # 12h / 24h = 0.5, so 0.8 * 0.5 = 0.4
        assert result[0].confidence == pytest.approx(0.4, abs=0.05)

    @patch("wanctl.tuning.analyzer.query_metrics")
    def test_confidence_not_scaled_above_24h(self, mock_qm: MagicMock) -> None:
        from wanctl.tuning.analyzer import run_tuning_analysis

        # 48 hours of data -> confidence scale = 1.0 (capped)
        mock_qm.return_value = _make_metrics(count=200, start_offset_hours=48.0)

        raw_result = TuningResult(
            parameter="target_bloat_ms",
            old_value=15.0,
            new_value=13.5,
            confidence=0.8,
            rationale="p75 delta",
            data_points=200,
            wan_name="Spectrum",
        )
        strategy = MagicMock(return_value=raw_result)

        result = run_tuning_analysis(
            wan_name="Spectrum",
            db_path="/tmp/test.db",
            tuning_config=_make_config(warmup_hours=4),
            current_params={"target_bloat_ms": 15.0},
            strategies=[("target_bloat_ms", strategy)],
        )
        assert len(result) == 1
        assert result[0].confidence == pytest.approx(0.8, abs=0.01)


class TestRunTuningAnalysisMissingParam:
    """Missing current_params or bounds for a strategy param skips that strategy."""

    @patch("wanctl.tuning.analyzer.query_metrics")
    def test_missing_current_param_skipped(self, mock_qm: MagicMock) -> None:
        from wanctl.tuning.analyzer import run_tuning_analysis

        mock_qm.return_value = _make_metrics(count=100, start_offset_hours=25.0)
        strategy = MagicMock(return_value=None)

        result = run_tuning_analysis(
            wan_name="Spectrum",
            db_path="/tmp/test.db",
            tuning_config=_make_config(),
            current_params={},  # No current value for target_bloat_ms
            strategies=[("target_bloat_ms", strategy)],
        )
        assert result == []
        strategy.assert_not_called()

    @patch("wanctl.tuning.analyzer.query_metrics")
    def test_missing_bounds_skipped(self, mock_qm: MagicMock) -> None:
        from wanctl.tuning.analyzer import run_tuning_analysis

        mock_qm.return_value = _make_metrics(count=100, start_offset_hours=25.0)
        strategy = MagicMock(return_value=None)

        config = TuningConfig(
            enabled=True,
            cadence_sec=3600,
            lookback_hours=24,
            warmup_hours=4,
            max_step_pct=10.0,
            bounds={},  # No bounds for target_bloat_ms
        )
        result = run_tuning_analysis(
            wan_name="Spectrum",
            db_path="/tmp/test.db",
            tuning_config=config,
            current_params={"target_bloat_ms": 15.0},
            strategies=[("target_bloat_ms", strategy)],
        )
        assert result == []
        strategy.assert_not_called()
