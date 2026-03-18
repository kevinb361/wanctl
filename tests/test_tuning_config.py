"""Tests for tuning config parsing, SQLite schema, and conftest fixture."""

import logging
import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from wanctl.storage.schema import TUNING_PARAMS_SCHEMA, create_tables
from wanctl.tuning.models import SafetyBounds, TuningConfig


class TestLoadTuningConfigDisabled:
    """_load_tuning_config() when tuning is absent or disabled."""

    def _make_config_obj(self, data: dict) -> MagicMock:
        """Create a mock Config with data dict for _load_tuning_config."""
        config = MagicMock()
        config.data = data
        return config

    def test_absent_section(self):
        """No tuning: section sets tuning_config = None."""
        from wanctl.autorate_continuous import Config

        config = self._make_config_obj({})
        Config._load_tuning_config(config)
        assert config.tuning_config is None

    def test_empty_section(self):
        """Empty tuning: {} sets tuning_config = None."""
        from wanctl.autorate_continuous import Config

        config = self._make_config_obj({"tuning": {}})
        Config._load_tuning_config(config)
        assert config.tuning_config is None

    def test_enabled_false(self):
        """tuning.enabled: false sets tuning_config = None."""
        from wanctl.autorate_continuous import Config

        config = self._make_config_obj({"tuning": {"enabled": False}})
        Config._load_tuning_config(config)
        assert config.tuning_config is None

    def test_enabled_non_bool(self, caplog):
        """tuning.enabled: 'yes' (non-bool) warns and disables."""
        from wanctl.autorate_continuous import Config

        config = self._make_config_obj({"tuning": {"enabled": "yes"}})
        with caplog.at_level(logging.WARNING):
            Config._load_tuning_config(config)
        assert config.tuning_config is None
        assert "must be bool" in caplog.text


class TestLoadTuningConfigEnabled:
    """_load_tuning_config() with valid tuning enabled."""

    def _make_config_obj(self, data: dict) -> MagicMock:
        config = MagicMock()
        config.data = data
        return config

    def test_valid_minimal(self):
        """Enabled with defaults and no bounds creates TuningConfig."""
        from wanctl.autorate_continuous import Config

        config = self._make_config_obj({"tuning": {"enabled": True}})
        Config._load_tuning_config(config)
        tc = config.tuning_config
        assert isinstance(tc, TuningConfig)
        assert tc.enabled is True
        assert tc.cadence_sec == 3600
        assert tc.lookback_hours == 24
        assert tc.warmup_hours == 1
        assert tc.max_step_pct == 10.0
        assert tc.bounds == {}

    def test_valid_with_bounds(self):
        """Parses bounds dict into SafetyBounds objects."""
        from wanctl.autorate_continuous import Config

        data = {
            "tuning": {
                "enabled": True,
                "bounds": {"target_bloat_ms": {"min": 3, "max": 30}},
            }
        }
        config = self._make_config_obj(data)
        Config._load_tuning_config(config)
        tc = config.tuning_config
        assert isinstance(tc, TuningConfig)
        assert "target_bloat_ms" in tc.bounds
        assert tc.bounds["target_bloat_ms"].min_value == 3.0
        assert tc.bounds["target_bloat_ms"].max_value == 30.0

    def test_valid_custom_values(self):
        """Custom cadence, lookback, warmup, max_step_pct."""
        from wanctl.autorate_continuous import Config

        data = {
            "tuning": {
                "enabled": True,
                "cadence_sec": 7200,
                "lookback_hours": 48,
                "warmup_hours": 2,
                "max_step_pct": 5.0,
            }
        }
        config = self._make_config_obj(data)
        Config._load_tuning_config(config)
        tc = config.tuning_config
        assert tc.cadence_sec == 7200
        assert tc.lookback_hours == 48
        assert tc.warmup_hours == 2
        assert tc.max_step_pct == 5.0


class TestLoadTuningConfigValidation:
    """_load_tuning_config() rejects invalid values with warn+disable."""

    def _make_config_obj(self, data: dict) -> MagicMock:
        config = MagicMock()
        config.data = data
        return config

    def test_bounds_scalar_not_dict(self, caplog):
        """bounds.target_bloat_ms: 15 (scalar) warns and disables."""
        from wanctl.autorate_continuous import Config

        data = {
            "tuning": {
                "enabled": True,
                "bounds": {"target_bloat_ms": 15},
            }
        }
        config = self._make_config_obj(data)
        with caplog.at_level(logging.WARNING):
            Config._load_tuning_config(config)
        assert config.tuning_config is None
        assert "must be a dict" in caplog.text or "must be dict" in caplog.text

    def test_bounds_min_greater_than_max(self, caplog):
        """bounds.target_bloat_ms: {min: 30, max: 3} warns and disables."""
        from wanctl.autorate_continuous import Config

        data = {
            "tuning": {
                "enabled": True,
                "bounds": {"target_bloat_ms": {"min": 30, "max": 3}},
            }
        }
        config = self._make_config_obj(data)
        with caplog.at_level(logging.WARNING):
            Config._load_tuning_config(config)
        assert config.tuning_config is None
        assert "min" in caplog.text.lower() and "max" in caplog.text.lower()

    def test_negative_max_step_pct(self, caplog):
        """max_step_pct: -5 warns and disables."""
        from wanctl.autorate_continuous import Config

        data = {
            "tuning": {
                "enabled": True,
                "max_step_pct": -5,
            }
        }
        config = self._make_config_obj(data)
        with caplog.at_level(logging.WARNING):
            Config._load_tuning_config(config)
        assert config.tuning_config is None

    def test_cadence_too_low(self, caplog):
        """cadence_sec: 60 (below 600 minimum) warns and disables."""
        from wanctl.autorate_continuous import Config

        data = {
            "tuning": {
                "enabled": True,
                "cadence_sec": 60,
            }
        }
        config = self._make_config_obj(data)
        with caplog.at_level(logging.WARNING):
            Config._load_tuning_config(config)
        assert config.tuning_config is None
        assert "600" in caplog.text or "minimum" in caplog.text.lower()


class TestTuningParamsSchema:
    """TUNING_PARAMS_SCHEMA creates correct table."""

    def test_schema_string_exists(self):
        """TUNING_PARAMS_SCHEMA is a non-empty string."""
        assert isinstance(TUNING_PARAMS_SCHEMA, str)
        assert "tuning_params" in TUNING_PARAMS_SCHEMA

    def test_create_table(self):
        """create_tables() creates tuning_params table."""
        conn = sqlite3.connect(":memory:")
        create_tables(conn)
        cursor = conn.execute("PRAGMA table_info(tuning_params)")
        columns = {row[1] for row in cursor.fetchall()}
        expected = {
            "id",
            "timestamp",
            "wan_name",
            "parameter",
            "old_value",
            "new_value",
            "confidence",
            "rationale",
            "data_points",
            "reverted",
        }
        assert expected == columns
        conn.close()

    def test_indexes_created(self):
        """Indexes on tuning_params are created."""
        conn = sqlite3.connect(":memory:")
        create_tables(conn)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='tuning_params'"
        )
        indexes = {row[0] for row in cursor.fetchall()}
        assert "idx_tuning_timestamp" in indexes
        assert "idx_tuning_wan_param" in indexes
        conn.close()

    def test_idempotent(self):
        """Calling create_tables() twice does not error."""
        conn = sqlite3.connect(":memory:")
        create_tables(conn)
        create_tables(conn)  # Should not raise
        conn.close()


class TestConftestFixture:
    """Verify mock_autorate_config fixture includes tuning_config."""

    def test_tuning_config_none(self, mock_autorate_config):
        """Fixture sets tuning_config = None."""
        assert mock_autorate_config.tuning_config is None


class TestLoadSpecificFieldsIntegration:
    """Verify _load_tuning_config is called from _load_specific_fields."""

    def test_load_specific_fields_calls_tuning(self):
        """_load_specific_fields calls _load_tuning_config."""
        from wanctl.autorate_continuous import Config

        # Verify the method exists and is called in _load_specific_fields
        import inspect

        source = inspect.getsource(Config._load_specific_fields)
        assert "_load_tuning_config" in source
