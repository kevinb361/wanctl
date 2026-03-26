"""Tests for reflector_quality config loading and validation.

Covers _load_reflector_quality_config in Config class:
- Missing section uses all defaults
- Valid config passes through correctly
- Invalid values for each field warn and default
- Non-dict section warns and uses defaults
"""

import logging

import yaml

from wanctl.autorate_continuous import Config

# =============================================================================
# HELPERS
# =============================================================================


def _make_minimal_config_yaml(reflector_quality=None):
    """Create a minimal valid YAML config dict for Config instantiation.

    Includes only the required sections for Config to load without errors.
    The reflector_quality key is set to the provided value if not None.
    """
    config = {
        "wan_name": "test",
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
    if reflector_quality is not None:
        config["reflector_quality"] = reflector_quality
    return config


def _load_config_with(reflector_quality=None, tmp_path=None):
    """Create a Config object from a minimal YAML with the given reflector_quality."""
    config_dict = _make_minimal_config_yaml(reflector_quality)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config_dict))
    return Config(str(config_path))


# =============================================================================
# TestReflectorQualityConfigDefaults
# =============================================================================


class TestReflectorQualityConfigDefaults:
    """Test that missing reflector_quality section uses all defaults."""

    def test_missing_section_defaults(self, tmp_path):
        """Missing reflector_quality section sets all defaults."""
        config = _load_config_with(reflector_quality=None, tmp_path=tmp_path)
        rq = config.reflector_quality_config
        assert rq["min_score"] == 0.8
        assert rq["window_size"] == 50
        assert rq["probe_interval_sec"] == 30.0
        assert rq["recovery_count"] == 3

    def test_empty_dict_defaults(self, tmp_path):
        """Empty reflector_quality dict uses all defaults."""
        config = _load_config_with(reflector_quality={}, tmp_path=tmp_path)
        rq = config.reflector_quality_config
        assert rq["min_score"] == 0.8
        assert rq["window_size"] == 50
        assert rq["probe_interval_sec"] == 30.0
        assert rq["recovery_count"] == 3


# =============================================================================
# TestReflectorQualityConfigValid
# =============================================================================


class TestReflectorQualityConfigValid:
    """Test that valid config passes through correctly."""

    def test_valid_config(self, tmp_path):
        """Valid reflector_quality values pass through."""
        config = _load_config_with(
            reflector_quality={
                "min_score": 0.7,
                "window_size": 100,
                "probe_interval_sec": 60,
                "recovery_count": 5,
            },
            tmp_path=tmp_path,
        )
        rq = config.reflector_quality_config
        assert rq["min_score"] == 0.7
        assert rq["window_size"] == 100
        assert rq["probe_interval_sec"] == 60.0
        assert rq["recovery_count"] == 5


# =============================================================================
# TestReflectorQualityConfigInvalidMinScore
# =============================================================================


class TestReflectorQualityConfigInvalidMinScore:
    """Test min_score validation: bool, string, out-of-range -> warns, defaults to 0.8."""

    def test_bool_min_score(self, tmp_path, caplog):
        """Bool min_score warns and defaults to 0.8."""
        with caplog.at_level(logging.WARNING):
            config = _load_config_with(
                reflector_quality={"min_score": True},
                tmp_path=tmp_path,
            )
        assert config.reflector_quality_config["min_score"] == 0.8
        assert any("min_score" in r.message for r in caplog.records if r.levelno >= logging.WARNING)

    def test_string_min_score(self, tmp_path, caplog):
        """String min_score warns and defaults to 0.8."""
        with caplog.at_level(logging.WARNING):
            config = _load_config_with(
                reflector_quality={"min_score": "high"},
                tmp_path=tmp_path,
            )
        assert config.reflector_quality_config["min_score"] == 0.8

    def test_min_score_clamped_to_range(self, tmp_path):
        """min_score > 1.0 clamped to 1.0, < 0.0 clamped to 0.0."""
        config = _load_config_with(
            reflector_quality={"min_score": 1.5},
            tmp_path=tmp_path,
        )
        assert config.reflector_quality_config["min_score"] == 1.0

        config2 = _load_config_with(
            reflector_quality={"min_score": -0.5},
            tmp_path=tmp_path,
        )
        assert config2.reflector_quality_config["min_score"] == 0.0


# =============================================================================
# TestReflectorQualityConfigInvalidWindowSize
# =============================================================================


class TestReflectorQualityConfigInvalidWindowSize:
    """Test window_size validation: bool, string, < 10 -> warns, defaults to 50."""

    def test_bool_window_size(self, tmp_path, caplog):
        """Bool window_size warns and defaults to 50."""
        with caplog.at_level(logging.WARNING):
            config = _load_config_with(
                reflector_quality={"window_size": True},
                tmp_path=tmp_path,
            )
        assert config.reflector_quality_config["window_size"] == 50

    def test_string_window_size(self, tmp_path, caplog):
        """String window_size warns and defaults to 50."""
        with caplog.at_level(logging.WARNING):
            config = _load_config_with(
                reflector_quality={"window_size": "big"},
                tmp_path=tmp_path,
            )
        assert config.reflector_quality_config["window_size"] == 50

    def test_too_small_window_size(self, tmp_path, caplog):
        """window_size < 10 warns and defaults to 50."""
        with caplog.at_level(logging.WARNING):
            config = _load_config_with(
                reflector_quality={"window_size": 5},
                tmp_path=tmp_path,
            )
        assert config.reflector_quality_config["window_size"] == 50


# =============================================================================
# TestReflectorQualityConfigInvalidProbeInterval
# =============================================================================


class TestReflectorQualityConfigInvalidProbeInterval:
    """Test probe_interval_sec validation: bool, string, < 1 -> warns, defaults to 30."""

    def test_bool_probe_interval(self, tmp_path, caplog):
        """Bool probe_interval_sec warns and defaults to 30."""
        with caplog.at_level(logging.WARNING):
            config = _load_config_with(
                reflector_quality={"probe_interval_sec": True},
                tmp_path=tmp_path,
            )
        assert config.reflector_quality_config["probe_interval_sec"] == 30.0

    def test_string_probe_interval(self, tmp_path, caplog):
        """String probe_interval_sec warns and defaults to 30."""
        with caplog.at_level(logging.WARNING):
            config = _load_config_with(
                reflector_quality={"probe_interval_sec": "fast"},
                tmp_path=tmp_path,
            )
        assert config.reflector_quality_config["probe_interval_sec"] == 30.0

    def test_too_small_probe_interval(self, tmp_path, caplog):
        """probe_interval_sec < 1 warns and defaults to 30."""
        with caplog.at_level(logging.WARNING):
            config = _load_config_with(
                reflector_quality={"probe_interval_sec": 0.5},
                tmp_path=tmp_path,
            )
        assert config.reflector_quality_config["probe_interval_sec"] == 30.0


# =============================================================================
# TestReflectorQualityConfigInvalidRecoveryCount
# =============================================================================


class TestReflectorQualityConfigInvalidRecoveryCount:
    """Test recovery_count validation: bool, string, < 1 -> warns, defaults to 3."""

    def test_bool_recovery_count(self, tmp_path, caplog):
        """Bool recovery_count warns and defaults to 3."""
        with caplog.at_level(logging.WARNING):
            config = _load_config_with(
                reflector_quality={"recovery_count": True},
                tmp_path=tmp_path,
            )
        assert config.reflector_quality_config["recovery_count"] == 3

    def test_string_recovery_count(self, tmp_path, caplog):
        """String recovery_count warns and defaults to 3."""
        with caplog.at_level(logging.WARNING):
            config = _load_config_with(
                reflector_quality={"recovery_count": "many"},
                tmp_path=tmp_path,
            )
        assert config.reflector_quality_config["recovery_count"] == 3

    def test_too_small_recovery_count(self, tmp_path, caplog):
        """recovery_count < 1 warns and defaults to 3."""
        with caplog.at_level(logging.WARNING):
            config = _load_config_with(
                reflector_quality={"recovery_count": 0},
                tmp_path=tmp_path,
            )
        assert config.reflector_quality_config["recovery_count"] == 3


# =============================================================================
# TestReflectorQualityConfigNonDict
# =============================================================================


class TestReflectorQualityConfigNonDict:
    """Test non-dict reflector_quality section warns and uses defaults."""

    def test_non_dict_section(self, tmp_path, caplog):
        """Non-dict reflector_quality (e.g., string) warns and uses all defaults."""
        with caplog.at_level(logging.WARNING):
            config = _load_config_with(
                reflector_quality="invalid",
                tmp_path=tmp_path,
            )
        rq = config.reflector_quality_config
        assert rq["min_score"] == 0.8
        assert rq["window_size"] == 50
        assert rq["probe_interval_sec"] == 30.0
        assert rq["recovery_count"] == 3
        assert any("reflector_quality" in r.message and "dict" in r.message for r in caplog.records)

    def test_list_section(self, tmp_path, caplog):
        """List reflector_quality warns and uses all defaults."""
        with caplog.at_level(logging.WARNING):
            config = _load_config_with(
                reflector_quality=[1, 2, 3],
                tmp_path=tmp_path,
            )
        rq = config.reflector_quality_config
        assert rq["min_score"] == 0.8
