"""Tests for hysteresis configuration parsing, schema validation, and wiring.

Covers:
- Config._load_threshold_config parses dwell_cycles/deadband_ms from YAML
- Default values applied when absent (dwell_cycles=3, deadband_ms=3.0)
- Zero values accepted (disables hysteresis, backward compat)
- SCHEMA entries exist with correct types and bounds
- WANController passes config values to both QueueController instances

Requirements: CONF-01, CONF-03
"""

import logging
from unittest.mock import MagicMock, patch

import pytest
import yaml

from wanctl.autorate_config import Config
from wanctl.wan_controller import WANController

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def autorate_config_dict():
    """Minimal valid autorate config dict for hysteresis config tests."""
    return {
        "wan_name": "TestWAN",
        "router": {
            "host": "192.168.1.1",
            "user": "admin",
            "ssh_key": "/tmp/test_id_rsa",
            "transport": "ssh",
        },
        "queues": {
            "download": "cake-download",
            "upload": "cake-upload",
        },
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
            "upload": {
                "floor_mbps": 25,
                "ceiling_mbps": 40,
                "step_up_mbps": 1,
                "factor_down": 0.85,
            },
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


def _make_config(tmp_path, config_dict):
    """Write YAML and create Config from it."""
    config_file = tmp_path / "autorate.yaml"
    config_file.write_text(yaml.dump(config_dict))
    return Config(str(config_file))


# =============================================================================
# TestHysteresisConfigParsing
# =============================================================================


class TestHysteresisConfigParsing:
    """Test Config._load_threshold_config parses hysteresis parameters."""

    def test_explicit_values(self, tmp_path, autorate_config_dict):
        """Config with dwell_cycles=5, deadband_ms=4.0 in YAML."""
        autorate_config_dict["continuous_monitoring"]["thresholds"]["dwell_cycles"] = 5
        autorate_config_dict["continuous_monitoring"]["thresholds"]["deadband_ms"] = 4.0
        config = _make_config(tmp_path, autorate_config_dict)
        assert config.dwell_cycles == 5
        assert config.deadband_ms == 4.0

    def test_defaults_when_absent(self, tmp_path, autorate_config_dict):
        """Config with no dwell_cycles/deadband_ms uses defaults per CONF-03."""
        # Ensure keys are absent
        assert "dwell_cycles" not in autorate_config_dict["continuous_monitoring"]["thresholds"]
        assert "deadband_ms" not in autorate_config_dict["continuous_monitoring"]["thresholds"]
        config = _make_config(tmp_path, autorate_config_dict)
        assert config.dwell_cycles == 3
        assert config.deadband_ms == 3.0

    def test_zero_disables_hysteresis(self, tmp_path, autorate_config_dict):
        """dwell_cycles=0, deadband_ms=0.0 accepted (backward compat escape hatch)."""
        autorate_config_dict["continuous_monitoring"]["thresholds"]["dwell_cycles"] = 0
        autorate_config_dict["continuous_monitoring"]["thresholds"]["deadband_ms"] = 0.0
        config = _make_config(tmp_path, autorate_config_dict)
        assert config.dwell_cycles == 0
        assert config.deadband_ms == 0.0


# =============================================================================
# TestHysteresisSchemaValidation
# =============================================================================


class TestHysteresisSchemaValidation:
    """Test Config.SCHEMA entries for hysteresis parameters."""

    def test_dwell_cycles_schema_entry(self):
        """SCHEMA has dwell_cycles entry: int, optional, 0-20."""
        entry = None
        for item in Config.SCHEMA:
            if item["path"] == "continuous_monitoring.thresholds.dwell_cycles":
                entry = item
                break
        assert entry is not None, "dwell_cycles SCHEMA entry not found"
        assert entry["type"] is int
        assert entry["required"] is False
        assert entry["min"] == 0
        assert entry["max"] == 20

    def test_deadband_ms_schema_entry(self):
        """SCHEMA has deadband_ms entry: (int, float), optional, 0.0-20.0."""
        entry = None
        for item in Config.SCHEMA:
            if item["path"] == "continuous_monitoring.thresholds.deadband_ms":
                entry = item
                break
        assert entry is not None, "deadband_ms SCHEMA entry not found"
        assert entry["type"] == (int, float)
        assert entry["required"] is False
        assert entry["min"] == 0.0
        assert entry["max"] == 20.0


# =============================================================================
# TestHysteresisWiring
# =============================================================================


class TestHysteresisWiring:
    """Test WANController passes hysteresis config to QueueController."""

    @pytest.fixture
    def mock_config(self, mock_autorate_config):
        """Extend shared fixture with hysteresis parameters."""
        mock_autorate_config.dwell_cycles = 5
        mock_autorate_config.deadband_ms = 4.0
        return mock_autorate_config

    def test_download_receives_config_dwell(self, mock_config):
        """WANController.download gets dwell_cycles from config."""
        router = MagicMock()
        rtt = MagicMock()
        logger = logging.getLogger("test")
        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=router,
                rtt_measurement=rtt,
                logger=logger,
            )
        assert controller.download.dwell_cycles == 5
        assert controller.download.deadband_ms == 4.0

    def test_upload_receives_config_dwell(self, mock_config):
        """WANController.upload gets dwell_cycles from config."""
        router = MagicMock()
        rtt = MagicMock()
        logger = logging.getLogger("test")
        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=router,
                rtt_measurement=rtt,
                logger=logger,
            )
        assert controller.upload.dwell_cycles == 5
        assert controller.upload.deadband_ms == 4.0

    def test_default_wiring(self, mock_autorate_config):
        """Default values (3, 3.0) wire through to QueueControllers."""
        mock_autorate_config.dwell_cycles = 3
        mock_autorate_config.deadband_ms = 3.0
        router = MagicMock()
        rtt = MagicMock()
        logger = logging.getLogger("test")
        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_autorate_config,
                router=router,
                rtt_measurement=rtt,
                logger=logger,
            )
        assert controller.download.dwell_cycles == 3
        assert controller.download.deadband_ms == 3.0
        assert controller.upload.dwell_cycles == 3
        assert controller.upload.deadband_ms == 3.0
