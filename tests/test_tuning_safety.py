"""Tests for tuning safety module -- congestion measurement, revert detection, hysteresis lock."""

from dataclasses import FrozenInstanceError
from unittest.mock import patch

import pytest

from wanctl.tuning.models import TuningResult


# Helper: build a TuningResult for revert tests
def _make_result(
    parameter: str = "target_bloat_ms",
    old_value: float = 15.0,
    new_value: float = 13.5,
    confidence: float = 0.85,
    rationale: str = "p75 delta",
    data_points: int = 100,
    wan_name: str = "Spectrum",
) -> TuningResult:
    return TuningResult(
        parameter=parameter,
        old_value=old_value,
        new_value=new_value,
        confidence=confidence,
        rationale=rationale,
        data_points=data_points,
        wan_name=wan_name,
    )


def _make_metric_row(
    timestamp: int,
    wan_name: str = "Spectrum",
    metric_name: str = "wanctl_state",
    value: float = 0.0,
    labels: str | None = None,
    granularity: str = "1m",
) -> dict:
    """Build a metric row dict matching query_metrics return format."""
    return {
        "timestamp": timestamp,
        "wan_name": wan_name,
        "metric_name": metric_name,
        "value": value,
        "labels": labels,
        "granularity": granularity,
    }


# ============================================================================
# measure_congestion_rate tests
# ============================================================================


class TestMeasureCongestionRateBasic:
    """measure_congestion_rate returns correct fraction of congested samples."""

    @patch("wanctl.tuning.safety.query_metrics")
    def test_returns_correct_fraction(self, mock_qm) -> None:
        from wanctl.tuning.safety import measure_congestion_rate

        # 3 of 10 samples are SOFT_RED or RED (state >= 2.0)
        rows = []
        for i in range(10):
            state = 2.0 if i < 3 else 0.0  # 3 congested, 7 GREEN
            rows.append(_make_metric_row(timestamp=1000 + i * 60, value=state))

        mock_qm.return_value = rows
        rate = measure_congestion_rate("/tmp/test.db", "Spectrum", 1000, 2000)
        assert rate == pytest.approx(0.3)

    @patch("wanctl.tuning.safety.query_metrics")
    def test_all_green_returns_zero(self, mock_qm) -> None:
        from wanctl.tuning.safety import measure_congestion_rate

        rows = [_make_metric_row(timestamp=1000 + i * 60, value=0.0) for i in range(15)]
        mock_qm.return_value = rows
        rate = measure_congestion_rate("/tmp/test.db", "Spectrum", 1000, 2000)
        assert rate == 0.0

    @patch("wanctl.tuning.safety.query_metrics")
    def test_all_red_returns_one(self, mock_qm) -> None:
        from wanctl.tuning.safety import measure_congestion_rate

        rows = [_make_metric_row(timestamp=1000 + i * 60, value=3.0) for i in range(20)]
        mock_qm.return_value = rows
        rate = measure_congestion_rate("/tmp/test.db", "Spectrum", 1000, 2000)
        assert rate == 1.0


class TestMeasureCongestionRateInsufficientData:
    """measure_congestion_rate returns None when data is insufficient."""

    @patch("wanctl.tuning.safety.query_metrics")
    def test_returns_none_below_min_samples(self, mock_qm) -> None:
        from wanctl.tuning.safety import MIN_OBSERVATION_SAMPLES, measure_congestion_rate

        # Only 5 samples, below MIN_OBSERVATION_SAMPLES (10)
        rows = [_make_metric_row(timestamp=1000 + i * 60, value=0.0) for i in range(5)]
        mock_qm.return_value = rows
        rate = measure_congestion_rate("/tmp/test.db", "Spectrum", 1000, 2000)
        assert rate is None

    @patch("wanctl.tuning.safety.query_metrics")
    def test_returns_none_on_empty(self, mock_qm) -> None:
        from wanctl.tuning.safety import measure_congestion_rate

        mock_qm.return_value = []
        rate = measure_congestion_rate("/tmp/test.db", "Spectrum", 1000, 2000)
        assert rate is None


class TestMeasureCongestionRateFiltering:
    """measure_congestion_rate filters only wanctl_state metric."""

    @patch("wanctl.tuning.safety.query_metrics")
    def test_ignores_non_state_metrics(self, mock_qm) -> None:
        from wanctl.tuning.safety import measure_congestion_rate

        rows = []
        # 12 wanctl_state rows (all GREEN)
        for i in range(12):
            rows.append(_make_metric_row(timestamp=1000 + i * 60, value=0.0))
        # 5 non-state metric rows with high values (should be ignored)
        for i in range(5):
            rows.append(
                _make_metric_row(
                    timestamp=1000 + i * 60,
                    metric_name="wanctl_rtt_ms",
                    value=100.0,
                )
            )

        mock_qm.return_value = rows
        rate = measure_congestion_rate("/tmp/test.db", "Spectrum", 1000, 2000)
        assert rate == 0.0  # All 12 state samples are GREEN

    @patch("wanctl.tuning.safety.query_metrics")
    def test_mixed_states_counted_correctly(self, mock_qm) -> None:
        from wanctl.tuning.safety import measure_congestion_rate

        # 5 GREEN (0.0), 3 YELLOW (1.0), 2 SOFT_RED (2.0), 2 RED (3.0)
        values = [0.0] * 5 + [1.0] * 3 + [2.0] * 2 + [3.0] * 2
        rows = [
            _make_metric_row(timestamp=1000 + i * 60, value=v) for i, v in enumerate(values)
        ]
        mock_qm.return_value = rows
        rate = measure_congestion_rate("/tmp/test.db", "Spectrum", 1000, 2000)
        # 4 out of 12 are >= 2.0 (2 SOFT_RED + 2 RED)
        assert rate == pytest.approx(4.0 / 12.0)


# ============================================================================
# PendingObservation tests
# ============================================================================


class TestPendingObservation:
    """PendingObservation frozen dataclass."""

    def test_creation(self) -> None:
        from wanctl.tuning.safety import PendingObservation

        r = _make_result()
        obs = PendingObservation(
            applied_ts=1000,
            pre_congestion_rate=0.1,
            applied_results=(r,),
        )
        assert obs.applied_ts == 1000
        assert obs.pre_congestion_rate == 0.1
        assert obs.applied_results == (r,)

    def test_frozen(self) -> None:
        from wanctl.tuning.safety import PendingObservation

        obs = PendingObservation(
            applied_ts=1000,
            pre_congestion_rate=0.1,
            applied_results=(),
        )
        with pytest.raises(FrozenInstanceError):
            obs.applied_ts = 2000  # type: ignore[misc]

    def test_applied_results_is_tuple(self) -> None:
        from wanctl.tuning.safety import PendingObservation

        r1 = _make_result(parameter="target_bloat_ms")
        r2 = _make_result(parameter="warn_bloat_ms")
        obs = PendingObservation(
            applied_ts=1000,
            pre_congestion_rate=0.05,
            applied_results=(r1, r2),
        )
        assert isinstance(obs.applied_results, tuple)
        assert len(obs.applied_results) == 2


# ============================================================================
# check_and_revert tests
# ============================================================================


class TestCheckAndRevertEarlyReturns:
    """check_and_revert returns empty list for various early-exit conditions."""

    def test_none_observation_returns_empty(self) -> None:
        from wanctl.tuning.safety import check_and_revert

        result = check_and_revert(
            pending_observation=None,
            db_path="/tmp/test.db",
            wan_name="Spectrum",
        )
        assert result == []

    @patch("wanctl.tuning.safety.measure_congestion_rate")
    def test_none_post_rate_returns_empty(self, mock_measure) -> None:
        from wanctl.tuning.safety import PendingObservation, check_and_revert

        mock_measure.return_value = None  # Insufficient data
        obs = PendingObservation(
            applied_ts=1000,
            pre_congestion_rate=0.1,
            applied_results=(_make_result(),),
        )
        result = check_and_revert(
            pending_observation=obs,
            db_path="/tmp/test.db",
            wan_name="Spectrum",
        )
        assert result == []

    @patch("wanctl.tuning.safety.measure_congestion_rate")
    def test_below_min_congestion_returns_empty(self, mock_measure) -> None:
        from wanctl.tuning.safety import (
            DEFAULT_MIN_CONGESTION_RATE,
            PendingObservation,
            check_and_revert,
        )

        # Post rate is below minimum (negligible congestion)
        mock_measure.return_value = DEFAULT_MIN_CONGESTION_RATE - 0.01
        obs = PendingObservation(
            applied_ts=1000,
            pre_congestion_rate=0.01,
            applied_results=(_make_result(),),
        )
        result = check_and_revert(
            pending_observation=obs,
            db_path="/tmp/test.db",
            wan_name="Spectrum",
        )
        assert result == []

    @patch("wanctl.tuning.safety.measure_congestion_rate")
    def test_ratio_below_threshold_returns_empty(self, mock_measure) -> None:
        from wanctl.tuning.safety import PendingObservation, check_and_revert

        # Pre rate 0.10, post rate 0.12 -> ratio 1.2 < 1.5 threshold
        mock_measure.return_value = 0.12
        obs = PendingObservation(
            applied_ts=1000,
            pre_congestion_rate=0.10,
            applied_results=(_make_result(),),
        )
        result = check_and_revert(
            pending_observation=obs,
            db_path="/tmp/test.db",
            wan_name="Spectrum",
        )
        assert result == []


class TestCheckAndRevertTriggersRevert:
    """check_and_revert returns revert TuningResults when degradation is detected."""

    @patch("wanctl.tuning.safety.measure_congestion_rate")
    def test_revert_triggered_on_degradation(self, mock_measure) -> None:
        from wanctl.tuning.safety import PendingObservation, check_and_revert

        # Pre rate 0.10, post rate 0.20 -> ratio 2.0 > 1.5 threshold
        mock_measure.return_value = 0.20
        obs = PendingObservation(
            applied_ts=1000,
            pre_congestion_rate=0.10,
            applied_results=(
                _make_result(parameter="target_bloat_ms", old_value=15.0, new_value=13.5),
            ),
        )
        result = check_and_revert(
            pending_observation=obs,
            db_path="/tmp/test.db",
            wan_name="Spectrum",
        )
        assert len(result) == 1
        # Revert swaps old/new
        assert result[0].old_value == 13.5
        assert result[0].new_value == 15.0

    @patch("wanctl.tuning.safety.measure_congestion_rate")
    def test_revert_rationale_has_prefix(self, mock_measure) -> None:
        from wanctl.tuning.safety import PendingObservation, check_and_revert

        mock_measure.return_value = 0.20
        obs = PendingObservation(
            applied_ts=1000,
            pre_congestion_rate=0.10,
            applied_results=(_make_result(),),
        )
        result = check_and_revert(
            pending_observation=obs,
            db_path="/tmp/test.db",
            wan_name="Spectrum",
        )
        assert len(result) == 1
        assert result[0].rationale.startswith("REVERT:")
        assert "10.00%" in result[0].rationale
        assert "20.00%" in result[0].rationale
        assert "2.0x" in result[0].rationale

    @patch("wanctl.tuning.safety.measure_congestion_rate")
    def test_revert_confidence_is_one(self, mock_measure) -> None:
        from wanctl.tuning.safety import PendingObservation, check_and_revert

        mock_measure.return_value = 0.20
        obs = PendingObservation(
            applied_ts=1000,
            pre_congestion_rate=0.10,
            applied_results=(_make_result(),),
        )
        result = check_and_revert(
            pending_observation=obs,
            db_path="/tmp/test.db",
            wan_name="Spectrum",
        )
        assert result[0].confidence == 1.0

    @patch("wanctl.tuning.safety.measure_congestion_rate")
    def test_revert_data_points_is_zero(self, mock_measure) -> None:
        from wanctl.tuning.safety import PendingObservation, check_and_revert

        mock_measure.return_value = 0.20
        obs = PendingObservation(
            applied_ts=1000,
            pre_congestion_rate=0.10,
            applied_results=(_make_result(),),
        )
        result = check_and_revert(
            pending_observation=obs,
            db_path="/tmp/test.db",
            wan_name="Spectrum",
        )
        assert result[0].data_points == 0

    @patch("wanctl.tuning.safety.measure_congestion_rate")
    def test_near_zero_pre_rate_uses_min_denominator(self, mock_measure) -> None:
        from wanctl.tuning.safety import (
            DEFAULT_MIN_CONGESTION_RATE,
            PendingObservation,
            check_and_revert,
        )

        # Pre rate near zero, post rate above min -> ratio uses min_congestion_rate as denominator
        mock_measure.return_value = 0.10
        obs = PendingObservation(
            applied_ts=1000,
            pre_congestion_rate=0.0005,  # < 0.001
            applied_results=(_make_result(),),
        )
        result = check_and_revert(
            pending_observation=obs,
            db_path="/tmp/test.db",
            wan_name="Spectrum",
        )
        # ratio = 0.10 / 0.05 = 2.0 > 1.5, should trigger revert
        assert len(result) == 1

    @patch("wanctl.tuning.safety.measure_congestion_rate")
    def test_reverts_all_in_batch(self, mock_measure) -> None:
        from wanctl.tuning.safety import PendingObservation, check_and_revert

        mock_measure.return_value = 0.20
        r1 = _make_result(parameter="target_bloat_ms", old_value=15.0, new_value=13.5)
        r2 = _make_result(parameter="warn_bloat_ms", old_value=25.0, new_value=22.0)
        obs = PendingObservation(
            applied_ts=1000,
            pre_congestion_rate=0.10,
            applied_results=(r1, r2),
        )
        result = check_and_revert(
            pending_observation=obs,
            db_path="/tmp/test.db",
            wan_name="Spectrum",
        )
        assert len(result) == 2
        # First revert
        assert result[0].parameter == "target_bloat_ms"
        assert result[0].old_value == 13.5
        assert result[0].new_value == 15.0
        # Second revert
        assert result[1].parameter == "warn_bloat_ms"
        assert result[1].old_value == 22.0
        assert result[1].new_value == 25.0


# ============================================================================
# is_parameter_locked / lock_parameter tests
# ============================================================================


class TestIsParameterLocked:
    """is_parameter_locked checks lock expiry against monotonic time."""

    def test_unknown_parameter_returns_false(self) -> None:
        from wanctl.tuning.safety import is_parameter_locked

        locks: dict[str, float] = {}
        assert is_parameter_locked(locks, "target_bloat_ms") is False

    @patch("wanctl.tuning.safety.time")
    def test_active_lock_returns_true(self, mock_time) -> None:
        from wanctl.tuning.safety import is_parameter_locked

        mock_time.monotonic.return_value = 100.0
        locks = {"target_bloat_ms": 200.0}  # Expires at 200, current is 100
        assert is_parameter_locked(locks, "target_bloat_ms") is True

    @patch("wanctl.tuning.safety.time")
    def test_expired_lock_returns_false_and_removes(self, mock_time) -> None:
        from wanctl.tuning.safety import is_parameter_locked

        mock_time.monotonic.return_value = 300.0
        locks = {"target_bloat_ms": 200.0}  # Expired at 200, current is 300
        assert is_parameter_locked(locks, "target_bloat_ms") is False
        # Lock entry should be removed
        assert "target_bloat_ms" not in locks


class TestLockParameter:
    """lock_parameter sets expiry in the locks dict."""

    @patch("wanctl.tuning.safety.time")
    def test_sets_expiry(self, mock_time) -> None:
        from wanctl.tuning.safety import lock_parameter

        mock_time.monotonic.return_value = 100.0
        locks: dict[str, float] = {}
        lock_parameter(locks, "target_bloat_ms", cooldown_sec=86400.0)
        assert locks["target_bloat_ms"] == 100.0 + 86400.0

    @patch("wanctl.tuning.safety.time")
    def test_multiple_independent_locks(self, mock_time) -> None:
        from wanctl.tuning.safety import is_parameter_locked, lock_parameter

        mock_time.monotonic.return_value = 100.0
        locks: dict[str, float] = {}
        lock_parameter(locks, "target_bloat_ms", cooldown_sec=3600.0)
        lock_parameter(locks, "warn_bloat_ms", cooldown_sec=7200.0)

        assert "target_bloat_ms" in locks
        assert "warn_bloat_ms" in locks
        assert locks["target_bloat_ms"] == 3700.0
        assert locks["warn_bloat_ms"] == 7300.0

        # Both should be locked
        assert is_parameter_locked(locks, "target_bloat_ms") is True
        assert is_parameter_locked(locks, "warn_bloat_ms") is True
