"""Tests for fusion configuration loading and validation.

Covers:
- Config._load_fusion_config() default values
- Config._load_fusion_config() validation (warn+default)
- Config._load_fusion_config() custom values
- Config._load_fusion_config() logging output

Requirements: FUSE-03 (YAML-configurable fusion weights with warn+default validation).
"""

import logging

import pytest
import yaml

from wanctl.autorate_config import Config

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def autorate_config_dict():
    """Minimal valid autorate config dict for fusion config tests."""
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
# TestFusionConfig
# =============================================================================


class TestFusionConfig:
    """Fusion config loading and validation tests."""

    def test_default_when_absent(self, tmp_path, autorate_config_dict):
        """Config without fusion section gets default icmp_weight 0.7."""
        config = _make_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["icmp_weight"] == 0.7

    @pytest.mark.parametrize("weight", [0.0, 0.3, 0.5, 0.7, 1.0])
    def test_custom_valid_weight(self, tmp_path, autorate_config_dict, weight):
        """Config with valid fusion.icmp_weight uses the provided value."""
        autorate_config_dict["fusion"] = {"icmp_weight": weight}
        config = _make_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["icmp_weight"] == weight

    def test_invalid_above_range(self, tmp_path, autorate_config_dict, caplog):
        """icmp_weight > 1.0 warns and defaults to 0.7."""
        autorate_config_dict["fusion"] = {"icmp_weight": 1.5}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["icmp_weight"] == 0.7
        assert "defaulting to 0.7" in caplog.text

    def test_invalid_below_range(self, tmp_path, autorate_config_dict, caplog):
        """icmp_weight < 0.0 warns and defaults to 0.7."""
        autorate_config_dict["fusion"] = {"icmp_weight": -0.1}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["icmp_weight"] == 0.7
        assert "defaulting to 0.7" in caplog.text

    def test_invalid_string(self, tmp_path, autorate_config_dict, caplog):
        """icmp_weight as string warns and defaults to 0.7."""
        autorate_config_dict["fusion"] = {"icmp_weight": "bad"}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["icmp_weight"] == 0.7
        assert "defaulting to 0.7" in caplog.text

    def test_invalid_boolean(self, tmp_path, autorate_config_dict, caplog):
        """icmp_weight as boolean warns and defaults to 0.7."""
        autorate_config_dict["fusion"] = {"icmp_weight": True}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["icmp_weight"] == 0.7
        assert "defaulting to 0.7" in caplog.text

    def test_invalid_section_not_dict(self, tmp_path, autorate_config_dict, caplog):
        """fusion section as string warns and defaults to 0.7."""
        autorate_config_dict["fusion"] = "not_a_dict"
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["icmp_weight"] == 0.7
        assert "using defaults" in caplog.text

    def test_edge_zero(self, tmp_path, autorate_config_dict):
        """icmp_weight 0.0 (all IRTT) is valid."""
        autorate_config_dict["fusion"] = {"icmp_weight": 0.0}
        config = _make_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["icmp_weight"] == 0.0

    def test_edge_one(self, tmp_path, autorate_config_dict):
        """icmp_weight 1.0 (all ICMP) is valid."""
        autorate_config_dict["fusion"] = {"icmp_weight": 1.0}
        config = _make_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["icmp_weight"] == 1.0

    def test_info_log_emitted(self, tmp_path, autorate_config_dict, caplog):
        """INFO log contains icmp_weight and irtt_weight values."""
        autorate_config_dict["fusion"] = {"icmp_weight": 0.6}
        with caplog.at_level(logging.INFO):
            _make_config(tmp_path, autorate_config_dict)
        assert "icmp_weight=0.6" in caplog.text
        assert "healing.suspend_threshold=" in caplog.text

    # -----------------------------------------------------------------
    # fusion.enabled tests (FUSE-02)
    # -----------------------------------------------------------------

    def test_enabled_defaults_false(self, tmp_path, autorate_config_dict):
        """Config with no fusion section defaults enabled to False."""
        config = _make_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["enabled"] is False

    def test_enabled_true(self, tmp_path, autorate_config_dict):
        """Config with fusion.enabled=True sets enabled to True."""
        autorate_config_dict["fusion"] = {"enabled": True}
        config = _make_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["enabled"] is True

    def test_enabled_false_explicit(self, tmp_path, autorate_config_dict):
        """Config with fusion.enabled=False explicitly sets enabled to False."""
        autorate_config_dict["fusion"] = {"enabled": False}
        config = _make_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["enabled"] is False

    def test_enabled_non_bool_warns_defaults_false(self, tmp_path, autorate_config_dict, caplog):
        """fusion.enabled='yes' (string) warns and defaults to False."""
        autorate_config_dict["fusion"] = {"enabled": "yes"}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["enabled"] is False
        assert "fusion.enabled must be bool" in caplog.text

    def test_enabled_non_bool_int_warns_defaults_false(
        self, tmp_path, autorate_config_dict, caplog
    ):
        """fusion.enabled=1 (int) warns and defaults to False."""
        autorate_config_dict["fusion"] = {"enabled": 1}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["enabled"] is False
        assert "fusion.enabled must be bool" in caplog.text
