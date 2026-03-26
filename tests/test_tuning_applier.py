"""Tests for tuning applier -- bounds enforcement, persistence, and logging."""

import logging
import sqlite3
from unittest.mock import MagicMock

import pytest

from wanctl.tuning.models import SafetyBounds, TuningConfig, TuningResult


# Helper: build a TuningConfig for tests
def _make_config(
    max_step_pct: float = 10.0,
) -> TuningConfig:
    return TuningConfig(
        enabled=True,
        cadence_sec=3600,
        lookback_hours=24,
        warmup_hours=4,
        max_step_pct=max_step_pct,
        bounds={
            "target_bloat_ms": SafetyBounds(min_value=3.0, max_value=50.0),
        },
    )


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


class TestApplyTuningResultsEmpty:
    """Empty results list does nothing."""

    def test_empty_results_returns_empty(self) -> None:
        from wanctl.tuning.applier import apply_tuning_results

        result = apply_tuning_results(
            results=[],
            tuning_config=_make_config(),
            writer=None,
        )
        assert result == []


class TestApplyTuningResultsLogging:
    """Single result logged at WARNING with correct format."""

    def test_result_logged_at_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        from wanctl.tuning.applier import apply_tuning_results

        result = _make_result(old_value=15.0, new_value=13.5)
        with caplog.at_level(logging.WARNING):
            applied = apply_tuning_results(
                results=[result],
                tuning_config=_make_config(),
                writer=None,
            )
        assert len(applied) == 1
        assert "Spectrum" in caplog.text
        assert "target_bloat_ms" in caplog.text
        assert "15.0" in caplog.text
        assert "p75 delta" in caplog.text


class TestApplyTuningResultsBoundsEnforcement:
    """Bounds enforcement via clamp_to_step."""

    def test_oversized_change_clamped(self) -> None:
        from wanctl.tuning.applier import apply_tuning_results

        # Request change from 15.0 to 5.0 (66% change, max is 10%)
        result = _make_result(old_value=15.0, new_value=5.0)
        config = _make_config(max_step_pct=10.0)

        applied = apply_tuning_results(
            results=[result],
            tuning_config=config,
            writer=None,
        )
        assert len(applied) == 1
        # 10% of 15.0 = 1.5, so max decrease to 13.5
        assert applied[0].new_value == 13.5

    def test_change_within_bounds_not_clamped(self) -> None:
        from wanctl.tuning.applier import apply_tuning_results

        # Request change from 15.0 to 14.5 (3.3% change, within 10% max)
        result = _make_result(old_value=15.0, new_value=14.5)
        config = _make_config(max_step_pct=10.0)

        applied = apply_tuning_results(
            results=[result],
            tuning_config=config,
            writer=None,
        )
        assert len(applied) == 1
        assert applied[0].new_value == 14.5


class TestApplyTuningResultsTrivialChange:
    """Trivial change (< 0.1 abs difference) is skipped and logged at DEBUG."""

    def test_trivial_change_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        from wanctl.tuning.applier import apply_tuning_results

        # Change from 15.0 to 15.05 -> after clamp still ~15.0, trivial
        result = _make_result(old_value=15.0, new_value=15.05)
        config = _make_config(max_step_pct=10.0)

        with caplog.at_level(logging.DEBUG):
            applied = apply_tuning_results(
                results=[result],
                tuning_config=config,
                writer=None,
            )
        assert applied == []
        assert "trivial change" in caplog.text


class TestApplyTuningResultsReturnPostClamp:
    """apply_tuning_results returns post-clamp results."""

    def test_return_values_are_post_clamp(self) -> None:
        from wanctl.tuning.applier import apply_tuning_results

        # Big change that will be clamped
        result = _make_result(old_value=15.0, new_value=5.0)
        config = _make_config(max_step_pct=10.0)

        applied = apply_tuning_results(
            results=[result],
            tuning_config=config,
            writer=None,
        )
        assert len(applied) == 1
        # Post-clamp: old_value unchanged, new_value is clamped
        assert applied[0].old_value == 15.0
        assert applied[0].new_value == 13.5
        assert applied[0].parameter == "target_bloat_ms"
        assert applied[0].confidence == 0.85
        assert applied[0].rationale == "p75 delta"
        assert applied[0].wan_name == "Spectrum"


class TestApplyTuningResultsMissingBounds:
    """Missing bounds for a parameter skips that result."""

    def test_no_bounds_skipped(self) -> None:
        from wanctl.tuning.applier import apply_tuning_results

        result = _make_result(parameter="unknown_param")
        config = _make_config()  # Only has bounds for target_bloat_ms

        applied = apply_tuning_results(
            results=[result],
            tuning_config=config,
            writer=None,
        )
        assert applied == []


class TestPersistTuningResultNoneWriter:
    """persist_tuning_result with writer=None returns None."""

    def test_none_writer_returns_none(self) -> None:
        from wanctl.tuning.applier import persist_tuning_result

        result = _make_result()
        row_id = persist_tuning_result(result, writer=None)
        assert row_id is None


class TestPersistTuningResultSuccess:
    """persist_tuning_result with valid writer INSERTs row and returns lastrowid."""

    def test_valid_writer_inserts_and_returns_rowid(self) -> None:
        from wanctl.tuning.applier import persist_tuning_result

        mock_writer = MagicMock()
        mock_writer.connection.execute.return_value.lastrowid = 42

        result = _make_result()
        row_id = persist_tuning_result(result, writer=mock_writer)

        assert row_id == 42
        mock_writer.connection.execute.assert_called_once()
        # Verify the SQL contains INSERT INTO tuning_params
        call_args = mock_writer.connection.execute.call_args
        sql = call_args[0][0]
        assert "INSERT INTO tuning_params" in sql

    def test_insert_column_values(self) -> None:
        from wanctl.tuning.applier import persist_tuning_result

        mock_writer = MagicMock()
        mock_writer.connection.execute.return_value.lastrowid = 1

        result = _make_result(
            parameter="target_bloat_ms",
            old_value=15.0,
            new_value=13.5,
            confidence=0.85,
            rationale="p75 delta",
            data_points=100,
            wan_name="Spectrum",
        )
        persist_tuning_result(result, writer=mock_writer)

        call_args = mock_writer.connection.execute.call_args
        params = call_args[0][1]
        # Verify column values: (ts, wan_name, parameter, old, new, confidence, rationale, data_points)
        assert params[1] == "Spectrum"  # wan_name
        assert params[2] == "target_bloat_ms"  # parameter
        assert params[3] == 15.0  # old_value
        assert params[4] == 13.5  # new_value
        assert params[5] == 0.85  # confidence
        assert params[6] == "p75 delta"  # rationale
        assert params[7] == 100  # data_points


class TestPersistTuningResultException:
    """persist_tuning_result catches Exception and returns None."""

    def test_exception_returns_none(self, caplog: pytest.LogCaptureFixture) -> None:
        from wanctl.tuning.applier import persist_tuning_result

        mock_writer = MagicMock()
        mock_writer.connection.execute.side_effect = sqlite3.OperationalError("table not found")

        result = _make_result()
        with caplog.at_level(logging.WARNING):
            row_id = persist_tuning_result(result, writer=mock_writer)

        assert row_id is None
        assert "Failed to persist tuning result" in caplog.text


class TestApplyTuningResultsWithPersistence:
    """Integration: apply_tuning_results calls persist for each applied result."""

    def test_persist_called_for_applied_result(self) -> None:
        from wanctl.tuning.applier import apply_tuning_results

        mock_writer = MagicMock()
        mock_writer.connection.execute.return_value.lastrowid = 1

        result = _make_result(old_value=15.0, new_value=13.5)
        config = _make_config()

        applied = apply_tuning_results(
            results=[result],
            tuning_config=config,
            writer=mock_writer,
        )
        assert len(applied) == 1
        # Writer should have been called
        mock_writer.connection.execute.assert_called_once()


class TestPersistTuningResultRealSQLite:
    """Integration: persist into a real in-memory SQLite database."""

    def test_real_sqlite_insert(self) -> None:
        from wanctl.storage.schema import create_tables
        from wanctl.tuning.applier import persist_tuning_result

        conn = sqlite3.connect(":memory:")
        create_tables(conn)

        # Create a minimal writer-like object with .connection
        mock_writer = MagicMock()
        mock_writer.connection = conn

        result = _make_result(
            parameter="target_bloat_ms",
            old_value=15.0,
            new_value=13.5,
            confidence=0.85,
            rationale="p75 delta",
            data_points=100,
            wan_name="Spectrum",
        )
        row_id = persist_tuning_result(result, writer=mock_writer)

        assert row_id is not None
        assert row_id > 0

        # Verify the row was actually inserted
        cursor = conn.execute(
            "SELECT wan_name, parameter, old_value, new_value, confidence, rationale, data_points "
            "FROM tuning_params WHERE id = ?",
            (row_id,),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "Spectrum"
        assert row[1] == "target_bloat_ms"
        assert row[2] == 15.0
        assert row[3] == 13.5
        assert row[4] == 0.85
        assert row[5] == "p75 delta"
        assert row[6] == 100

        conn.close()


class TestPersistRevertRecordNoneWriter:
    """persist_revert_record with writer=None returns None."""

    def test_none_writer_returns_none(self) -> None:
        from wanctl.tuning.applier import persist_revert_record

        result = _make_result()
        row_id = persist_revert_record(result, writer=None)
        assert row_id is None


class TestPersistRevertRecordSuccess:
    """persist_revert_record with valid writer INSERTs row with reverted=1."""

    def test_valid_writer_inserts_and_returns_rowid(self) -> None:
        from wanctl.tuning.applier import persist_revert_record

        mock_writer = MagicMock()
        mock_writer.connection.execute.return_value.lastrowid = 99

        result = _make_result()
        row_id = persist_revert_record(result, writer=mock_writer)

        assert row_id == 99
        mock_writer.connection.execute.assert_called_once()
        # Verify the SQL contains INSERT INTO tuning_params and reverted
        call_args = mock_writer.connection.execute.call_args
        sql = call_args[0][0]
        assert "INSERT INTO tuning_params" in sql
        assert "reverted" in sql

    def test_insert_includes_reverted_one(self) -> None:
        from wanctl.tuning.applier import persist_revert_record

        mock_writer = MagicMock()
        mock_writer.connection.execute.return_value.lastrowid = 1

        result = _make_result(
            parameter="target_bloat_ms",
            old_value=13.5,
            new_value=15.0,
            confidence=1.0,
            rationale="REVERT: congestion rate 10.00%->20.00% (ratio 2.0x > 1.5x)",
            data_points=0,
            wan_name="Spectrum",
        )
        persist_revert_record(result, writer=mock_writer)

        call_args = mock_writer.connection.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        # SQL should have VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1) -- hardcoded 1
        assert "1" in sql  # reverted=1 is in the SQL template
        # Verify column values
        assert params[1] == "Spectrum"  # wan_name
        assert params[2] == "target_bloat_ms"  # parameter
        assert params[3] == 13.5  # old_value
        assert params[4] == 15.0  # new_value
        assert params[5] == 1.0  # confidence
        assert params[7] == 0  # data_points


class TestPersistRevertRecordException:
    """persist_revert_record catches Exception and returns None."""

    def test_exception_returns_none(self, caplog: pytest.LogCaptureFixture) -> None:
        from wanctl.tuning.applier import persist_revert_record

        mock_writer = MagicMock()
        mock_writer.connection.execute.side_effect = sqlite3.OperationalError("table not found")

        result = _make_result()
        with caplog.at_level(logging.WARNING):
            row_id = persist_revert_record(result, writer=mock_writer)

        assert row_id is None
        assert "Failed to persist revert" in caplog.text


class TestPersistRevertRecordRealSQLite:
    """Integration: persist_revert_record into real in-memory SQLite."""

    def test_real_sqlite_insert_with_reverted_flag(self) -> None:
        from wanctl.storage.schema import create_tables
        from wanctl.tuning.applier import persist_revert_record

        conn = sqlite3.connect(":memory:")
        create_tables(conn)

        mock_writer = MagicMock()
        mock_writer.connection = conn

        result = _make_result(
            parameter="target_bloat_ms",
            old_value=13.5,
            new_value=15.0,
            confidence=1.0,
            rationale="REVERT: congestion rate 10.00%->20.00% (ratio 2.0x > 1.5x)",
            data_points=0,
            wan_name="Spectrum",
        )
        row_id = persist_revert_record(result, writer=mock_writer)

        assert row_id is not None
        assert row_id > 0

        # Verify the row was actually inserted with reverted=1
        cursor = conn.execute(
            "SELECT wan_name, parameter, old_value, new_value, confidence, "
            "rationale, data_points, reverted "
            "FROM tuning_params WHERE id = ?",
            (row_id,),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "Spectrum"
        assert row[1] == "target_bloat_ms"
        assert row[2] == 13.5
        assert row[3] == 15.0
        assert row[4] == 1.0
        assert row[6] == 0
        assert row[7] == 1  # reverted flag

        conn.close()
