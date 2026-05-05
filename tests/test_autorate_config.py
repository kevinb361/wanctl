"""Tests for Config class loading and validation in autorate_continuous.

Covers:
- Config._load_download_config (single-floor and state-based floors)
- Config._load_upload_config (single-floor and state-based floors)
- Floor ordering validation

Coverage target: lines 274-343 (_load_download_config, _load_upload_config).
"""

import logging
from pathlib import Path

import pytest

from wanctl.autorate_config import Config

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def base_config_yaml_state_based() -> str:
    """Base config YAML with state-based floors (v2/v3 format)."""
    return """
wan_name: TestWAN
router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/tmp/test_id_rsa"
  transport: "ssh"

queues:
  download: "cake-download"
  upload: "cake-upload"

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 25.0
  ping_hosts:
    - "1.1.1.1"
  download:
    floor_green_mbps: 800
    floor_yellow_mbps: 600
    floor_soft_red_mbps: 500
    floor_red_mbps: 400
    ceiling_mbps: 920
    step_up_mbps: 10
    factor_down: 0.85
  upload:
    floor_green_mbps: 35
    floor_yellow_mbps: 30
    floor_red_mbps: 25
    ceiling_mbps: 40
    step_up_mbps: 1
    factor_down: 0.85
  thresholds:
    target_bloat_ms: 15
    warn_bloat_ms: 45
    baseline_time_constant_sec: 60
    load_time_constant_sec: 0.5

logging:
  main_log: "/tmp/test_autorate.log"
  debug_log: "/tmp/test_autorate_debug.log"

lock_file: "/tmp/test_autorate.lock"
lock_timeout: 300
"""


@pytest.fixture
def base_config_yaml_single_floor() -> str:
    """Base config YAML with single floor_mbps (applies to all states)."""
    return """
wan_name: TestWAN
router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/tmp/test_id_rsa"
  transport: "ssh"

queues:
  download: "cake-download"
  upload: "cake-upload"

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 25.0
  ping_hosts:
    - "1.1.1.1"
  download:
    floor_mbps: 400
    ceiling_mbps: 920
    step_up_mbps: 10
    factor_down: 0.85
  upload:
    floor_mbps: 25
    ceiling_mbps: 40
    step_up_mbps: 1
    factor_down: 0.85
  thresholds:
    target_bloat_ms: 15
    warn_bloat_ms: 45
    baseline_time_constant_sec: 60
    load_time_constant_sec: 0.5

logging:
  main_log: "/tmp/test_autorate.log"
  debug_log: "/tmp/test_autorate_debug.log"

lock_file: "/tmp/test_autorate.lock"
lock_timeout: 300
"""


# =============================================================================
# TestLoadDownloadConfig
# =============================================================================


class TestLoadDownloadConfig:
    """Tests for Config._load_download_config method."""

    def test_load_download_single_floor(self, base_config_yaml_single_floor, tmp_path):
        """Single floor_mbps applies to all states."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(base_config_yaml_single_floor)

        config = Config(str(config_file))

        # Single floor (400 Mbps) should be used for all states
        expected_floor = 400 * 1_000_000
        assert config.download_floor_green == expected_floor
        assert config.download_floor_yellow == expected_floor
        assert config.download_floor_soft_red == expected_floor
        assert config.download_floor_red == expected_floor

    def test_load_download_state_based_floors(self, base_config_yaml_state_based, tmp_path):
        """State-based floors are mapped correctly."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(base_config_yaml_state_based)

        config = Config(str(config_file))

        # State-based floors should be mapped correctly
        assert config.download_floor_green == 800 * 1_000_000
        assert config.download_floor_yellow == 600 * 1_000_000
        assert config.download_floor_soft_red == 500 * 1_000_000
        assert config.download_floor_red == 400 * 1_000_000

    def test_load_download_soft_red_defaults_to_yellow(self, tmp_path):
        """Missing floor_soft_red_mbps defaults to floor_yellow_mbps."""
        config_yaml = """
wan_name: TestWAN
router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/tmp/test_id_rsa"

queues:
  download: "cake-download"
  upload: "cake-upload"

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 25.0
  ping_hosts:
    - "1.1.1.1"
  download:
    floor_green_mbps: 800
    floor_yellow_mbps: 600
    # floor_soft_red_mbps intentionally missing - should default to floor_yellow_mbps
    floor_red_mbps: 400
    ceiling_mbps: 920
    step_up_mbps: 10
    factor_down: 0.85
  upload:
    floor_mbps: 25
    ceiling_mbps: 40
    step_up_mbps: 1
    factor_down: 0.85
  thresholds:
    target_bloat_ms: 15
    warn_bloat_ms: 45
    baseline_time_constant_sec: 60
    load_time_constant_sec: 0.5

logging:
  main_log: "/tmp/test.log"
  debug_log: "/tmp/test_debug.log"

lock_file: "/tmp/test.lock"
lock_timeout: 300
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_yaml)

        config = Config(str(config_file))

        # floor_soft_red should default to floor_yellow (600 Mbps)
        assert config.download_floor_soft_red == 600 * 1_000_000
        assert config.download_floor_yellow == 600 * 1_000_000

    def test_load_download_floor_ordering_validation(self, tmp_path):
        """Invalid floor ordering raises ValueError."""
        # Invalid: red floor > yellow floor (should be red <= yellow)
        config_yaml = """
wan_name: TestWAN
router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/tmp/test_id_rsa"

queues:
  download: "cake-download"
  upload: "cake-upload"

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 25.0
  ping_hosts:
    - "1.1.1.1"
  download:
    floor_green_mbps: 800
    floor_yellow_mbps: 400
    floor_soft_red_mbps: 500
    floor_red_mbps: 600
    ceiling_mbps: 920
    step_up_mbps: 10
    factor_down: 0.85
  upload:
    floor_mbps: 25
    ceiling_mbps: 40
    step_up_mbps: 1
    factor_down: 0.85
  thresholds:
    target_bloat_ms: 15
    warn_bloat_ms: 45
    baseline_time_constant_sec: 60
    load_time_constant_sec: 0.5

logging:
  main_log: "/tmp/test.log"
  debug_log: "/tmp/test_debug.log"

lock_file: "/tmp/test.lock"
lock_timeout: 300
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_yaml)

        with pytest.raises(ValueError, match="floor ordering"):
            Config(str(config_file))


# =============================================================================
# TestLoadUploadConfig
# =============================================================================


class TestPhase201Schema:
    def test_docsis_mode_default_false(self, tmp_path, base_config_yaml_single_floor):
        cfg_path = tmp_path / "test.yaml"
        cfg_path.write_text(base_config_yaml_single_floor)
        cfg = Config(str(cfg_path))
        assert cfg.docsis_mode is False

    def test_docsis_mode_true_requires_setpoint_mbps_raises(
        self, tmp_path, base_config_yaml_single_floor
    ):
        cfg_path = tmp_path / "test.yaml"
        cfg_path.write_text(
            base_config_yaml_single_floor.replace(
                "    factor_down: 0.85\n",
                "    factor_down: 0.85\n    docsis_mode: true\n",
            )
        )
        with pytest.raises(ValueError, match="docsis_mode.*setpoint_mbps"):
            Config(str(cfg_path))

    def test_setpoint_below_floor_raises(self, tmp_path, base_config_yaml_single_floor):
        cfg_path = tmp_path / "test.yaml"
        cfg_path.write_text(
            base_config_yaml_single_floor.replace(
                "    factor_down: 0.85\n",
                "    factor_down: 0.85\n    docsis_mode: true\n    setpoint_mbps: 4\n",
            )
        )
        with pytest.raises(ValueError, match="setpoint_mbps"):
            Config(str(cfg_path))

    def test_setpoint_above_ceiling_raises(self, tmp_path, base_config_yaml_single_floor):
        cfg_path = tmp_path / "test.yaml"
        cfg_path.write_text(
            base_config_yaml_single_floor.replace(
                "    factor_down: 0.85\n",
                "    factor_down: 0.85\n    docsis_mode: true\n    setpoint_mbps: 50\n",
            )
        )
        with pytest.raises(ValueError, match="setpoint_mbps"):
            Config(str(cfg_path))

    def test_explicit_presence_flags_are_presence_based(self, tmp_path):
        # Per Phase 200 Codex pre-review: presence-based, NEVER value-derived.
        # Operator setting docsis_mode: false (matching default) MUST still
        # produce _docsis_mode_explicit=True (because the key was written).
        yaml_text = """
wan_name: TestWAN
router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/tmp/test_id_rsa"
queues:
  download: "cake-download"
  upload: "cake-upload"
continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 25.0
  ping_hosts: ["1.1.1.1"]
  download:
    floor_mbps: 400
    ceiling_mbps: 920
    step_up_mbps: 10
    factor_down: 0.85
  upload:
    floor_mbps: 25
    ceiling_mbps: 40
    step_up_mbps: 1
    factor_down: 0.85
    docsis_mode: false
  thresholds:
    target_bloat_ms: 15
    warn_bloat_ms: 45
    baseline_time_constant_sec: 60
    load_time_constant_sec: 0.5
logging:
  main_log: "/tmp/test.log"
  debug_log: "/tmp/test_debug.log"
lock_file: "/tmp/test.lock"
lock_timeout: 300
"""
        cfg_path = tmp_path / "test.yaml"
        cfg_path.write_text(yaml_text)
        cfg = Config(str(cfg_path))
        assert cfg._docsis_mode_explicit is True  # KEY WAS WRITTEN
        assert cfg.docsis_mode is False


class TestSafe06Phase201KeysKnown:
    def test_all_phase201_keys_in_known_autorate_paths(self):
        from wanctl.check_config_validators import KNOWN_AUTORATE_PATHS

        expected = {
            "continuous_monitoring.upload.docsis_mode",
            "continuous_monitoring.upload.setpoint_mbps",
            "continuous_monitoring.upload.integral_window_seconds",
            "continuous_monitoring.upload.integral_threshold_ms_s",
            "continuous_monitoring.upload.cake_backlog_low_threshold_bytes",
            "continuous_monitoring.upload.cake_delay_delta_low_threshold_us",
        }
        assert expected <= KNOWN_AUTORATE_PATHS


class TestRedDecayValidators:
    def _write_with_upload(self, tmp_path, base_config_yaml_single_floor: str, upload_lines: str):
        cfg_path = tmp_path / "test.yaml"
        cfg_path.write_text(
            base_config_yaml_single_floor.replace(
                "    factor_down: 0.85\n",
                "    factor_down: 0.85\n" + upload_lines,
            )
        )
        return cfg_path

    def _load_with_upload(self, tmp_path, base_config_yaml_single_floor: str, upload_lines: str):
        return Config(str(self._write_with_upload(tmp_path, base_config_yaml_single_floor, upload_lines)))

    def test_step_pct_must_be_positive(self, tmp_path, base_config_yaml_single_floor):
        for value in (0.0, -0.01):
            with pytest.raises(ValueError, match="red_decay_step_pct.*> 0"):
                self._load_with_upload(
                    tmp_path,
                    base_config_yaml_single_floor,
                    f"    red_decay_step_pct: {value}\n    red_decay_delta_max_pct: 0.10\n",
                )
        cfg = self._load_with_upload(
            tmp_path,
            base_config_yaml_single_floor,
            "    red_decay_step_pct: 0.01\n    red_decay_delta_max_pct: 0.10\n",
        )
        assert cfg.red_decay_step_pct == pytest.approx(0.01)

    def test_step_pct_must_be_le_delta_max(self, tmp_path, base_config_yaml_single_floor):
        cfg = self._load_with_upload(
            tmp_path,
            base_config_yaml_single_floor,
            "    red_decay_step_pct: 0.05\n    red_decay_delta_max_pct: 0.05\n",
        )
        assert cfg.red_decay_delta_max_pct == pytest.approx(0.05)
        with pytest.raises(ValueError, match="red_decay_step_pct.*<=.*red_decay_delta_max_pct"):
            self._load_with_upload(
                tmp_path,
                base_config_yaml_single_floor,
                "    red_decay_step_pct: 0.06\n    red_decay_delta_max_pct: 0.05\n",
            )
        cfg = self._load_with_upload(
            tmp_path,
            base_config_yaml_single_floor,
            "    red_decay_step_pct: 0.04\n    red_decay_delta_max_pct: 0.05\n",
        )
        assert cfg.red_decay_step_pct == pytest.approx(0.04)

    def test_delta_max_must_be_lt_one(self, tmp_path, base_config_yaml_single_floor):
        for value in (1.0, 1.5):
            with pytest.raises(ValueError, match="red_decay_delta_max_pct.*< 1.0"):
                self._load_with_upload(
                    tmp_path,
                    base_config_yaml_single_floor,
                    f"    red_decay_step_pct: 0.02\n    red_decay_delta_max_pct: {value}\n",
                )
        cfg = self._load_with_upload(
            tmp_path,
            base_config_yaml_single_floor,
            "    red_decay_step_pct: 0.02\n    red_decay_delta_max_pct: 0.999\n",
        )
        assert cfg.red_decay_delta_max_pct == pytest.approx(0.999)

    def test_docsis_mode_clamp_must_exceed_floor(self, tmp_path, base_config_yaml_single_floor):
        with pytest.raises(ValueError, match="clamp.*floor"):
            self._load_with_upload(
                tmp_path,
                base_config_yaml_single_floor,
                "    docsis_mode: true\n    setpoint_mbps: 12\n    floor_mbps: 8\n    red_decay_delta_max_pct: 0.3333333333333333\n",
            )
        cfg = self._load_with_upload(
            tmp_path,
            base_config_yaml_single_floor,
            "    docsis_mode: true\n    setpoint_mbps: 12\n    floor_mbps: 8\n    red_decay_delta_max_pct: 0.30\n",
        )
        assert cfg.setpoint_mbps == 12
        with pytest.raises(ValueError, match="clamp.*floor"):
            self._load_with_upload(
                tmp_path,
                base_config_yaml_single_floor,
                "    docsis_mode: true\n    setpoint_mbps: 10\n    floor_mbps: 8\n    red_decay_delta_max_pct: 0.20\n",
            )

    def test_docsis_mode_false_skips_clamp_invariant(self, tmp_path, base_config_yaml_single_floor):
        cfg = self._load_with_upload(
            tmp_path,
            base_config_yaml_single_floor,
            "    docsis_mode: false\n    setpoint_mbps: 12\n    floor_mbps: 8\n    red_decay_delta_max_pct: 0.99\n",
        )
        assert cfg.docsis_mode is False

    def test_at_equality_clamp_equals_floor_rejects(self, tmp_path, base_config_yaml_single_floor):
        with pytest.raises(ValueError, match="clamp.*floor"):
            self._load_with_upload(
                tmp_path,
                base_config_yaml_single_floor,
                "    docsis_mode: true\n    setpoint_mbps: 10\n    floor_mbps: 8\n    red_decay_delta_max_pct: 0.20\n",
            )


class TestLoadUploadConfig:
    """Tests for Config._load_upload_config method."""

    def test_load_upload_single_floor(self, base_config_yaml_single_floor, tmp_path):
        """Single floor_mbps applies to all states."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(base_config_yaml_single_floor)

        config = Config(str(config_file))

        # Single floor (25 Mbps) should be used for all states
        expected_floor = 25 * 1_000_000
        assert config.upload_floor_green == expected_floor
        assert config.upload_floor_yellow == expected_floor
        assert config.upload_floor_red == expected_floor

    def test_load_upload_state_based_floors(self, base_config_yaml_state_based, tmp_path):
        """State-based floors are mapped correctly."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(base_config_yaml_state_based)

        config = Config(str(config_file))

        # State-based floors should be mapped correctly
        assert config.upload_floor_green == 35 * 1_000_000
        assert config.upload_floor_yellow == 30 * 1_000_000
        assert config.upload_floor_red == 25 * 1_000_000

    def test_load_upload_floor_ordering_validation(self, tmp_path):
        """Invalid floor ordering raises ValueError."""
        # Invalid: red floor > yellow floor (should be red <= yellow)
        config_yaml = """
wan_name: TestWAN
router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/tmp/test_id_rsa"

queues:
  download: "cake-download"
  upload: "cake-upload"

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 25.0
  ping_hosts:
    - "1.1.1.1"
  download:
    floor_mbps: 400
    ceiling_mbps: 920
    step_up_mbps: 10
    factor_down: 0.85
  upload:
    floor_green_mbps: 25
    floor_yellow_mbps: 20
    floor_red_mbps: 30
    ceiling_mbps: 40
    step_up_mbps: 1
    factor_down: 0.85
  thresholds:
    target_bloat_ms: 15
    warn_bloat_ms: 45
    baseline_time_constant_sec: 60
    load_time_constant_sec: 0.5

logging:
  main_log: "/tmp/test.log"
  debug_log: "/tmp/test_debug.log"

lock_file: "/tmp/test.lock"
lock_timeout: 300
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_yaml)

        with pytest.raises(ValueError, match="floor ordering"):
            Config(str(config_file))


class TestLoadUploadThresholdConfig:
    """Tests for optional upload-specific RTT thresholds."""

    def test_upload_thresholds_default_to_global_thresholds(
        self, base_config_yaml_single_floor, tmp_path
    ):
        """Upload thresholds preserve existing behavior unless explicitly configured."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(base_config_yaml_single_floor)

        config = Config(str(config_file))

        assert config.upload_target_bloat_ms == 15
        assert config.upload_warn_bloat_ms == 45

    def test_upload_thresholds_can_override_global_thresholds(
        self, base_config_yaml_single_floor, tmp_path
    ):
        """Upload-specific target/warn thresholds load from continuous_monitoring.upload."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            base_config_yaml_single_floor.replace(
                "    factor_down: 0.85\n  thresholds:",
                "    factor_down: 0.85\n"
                "    target_bloat_ms: 42\n"
                "    warn_bloat_ms: 105\n"
                "  thresholds:",
            )
        )

        config = Config(str(config_file))

        assert config.target_bloat_ms == 15
        assert config.warn_bloat_ms == 45
        assert config.upload_target_bloat_ms == 42
        assert config.upload_warn_bloat_ms == 105

    def test_upload_thresholds_must_be_ordered(self, base_config_yaml_single_floor, tmp_path):
        """Upload-specific target must stay below upload-specific warn threshold."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            base_config_yaml_single_floor.replace(
                "    factor_down: 0.85\n  thresholds:",
                "    factor_down: 0.85\n"
                "    target_bloat_ms: 110\n"
                "    warn_bloat_ms: 90\n"
                "  thresholds:",
            )
        )

        with pytest.raises(ValueError, match="threshold"):
            Config(str(config_file))


class TestUploadYellowDecayClampConfig:
    """200-10 R3 config loading for consecutive YELLOW decay clamp."""

    def test_consecutive_yellow_decay_clamp_default_and_explicit(
        self, base_config_yaml_single_floor, tmp_path
    ):
        """Absent key disables clamp; explicit key records value and presence flag."""
        default_config_file = tmp_path / "default.yaml"
        default_config_file.write_text(base_config_yaml_single_floor)

        default_config = Config(str(default_config_file))

        assert default_config.upload_consecutive_yellow_decay_clamp == 0
        assert default_config._upload_consecutive_yellow_decay_clamp_explicit is False

        explicit_config_file = tmp_path / "explicit.yaml"
        explicit_config_file.write_text(
            base_config_yaml_single_floor.replace(
                "    factor_down: 0.85\n  thresholds:",
                "    factor_down: 0.85\n"
                "    consecutive_yellow_decay_clamp: 40\n"
                "  thresholds:",
            )
        )

        explicit_config = Config(str(explicit_config_file))

        assert explicit_config.upload_consecutive_yellow_decay_clamp == 40
        assert explicit_config._upload_consecutive_yellow_decay_clamp_explicit is True

    def test_consecutive_yellow_decay_clamp_is_known_safe06_path(
        self, base_config_yaml_single_floor, tmp_path, caplog
    ):
        """SAFE-06: the new upload key is registered and emits no unknown-key warning."""
        from wanctl.check_config_validators import KNOWN_AUTORATE_PATHS

        assert (
            "continuous_monitoring.upload.consecutive_yellow_decay_clamp"
            in KNOWN_AUTORATE_PATHS
        )
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            base_config_yaml_single_floor.replace(
                "    factor_down: 0.85\n  thresholds:",
                "    factor_down: 0.85\n"
                "    consecutive_yellow_decay_clamp: 40\n"
                "  thresholds:",
            )
        )

        with caplog.at_level(logging.WARNING, logger="wanctl.autorate_config"):
            Config(str(config_file))

        unknown_warnings = [
            rec for rec in caplog.records if "Unknown config key" in rec.getMessage()
        ]
        assert unknown_warnings == []


class TestSafe06UnknownKeyWarning:
    """SAFE-06 (D-08): daemon must warn on unknown config keys at startup."""

    def test_unknown_continuous_monitoring_key_warns(
        self, base_config_yaml_single_floor, tmp_path, caplog
    ):
        """Synthetic unknown key produces a WARNING containing its path."""
        unknown_key_yaml = base_config_yaml_single_floor.replace(
            "    factor_down: 0.85\n  thresholds:",
            "    factor_down: 0.85\n"
            "    target_bloat_ms_typo: 42\n"
            "  thresholds:",
        )
        config_file = tmp_path / "config.yaml"
        config_file.write_text(unknown_key_yaml)

        with caplog.at_level(logging.WARNING, logger="wanctl.autorate_config"):
            Config(str(config_file))

        unknown_warnings = [
            rec
            for rec in caplog.records
            if rec.levelno == logging.WARNING and "target_bloat_ms_typo" in rec.getMessage()
        ]
        assert len(unknown_warnings) >= 1, (
            f"Expected at least one WARNING for the synthetic unknown key, got: "
            f"{[r.getMessage() for r in caplog.records]}"
        )
        assert any("unknown" in rec.getMessage().lower() for rec in unknown_warnings)

    def test_known_continuous_monitoring_keys_do_not_warn(
        self, base_config_yaml_single_floor, tmp_path, caplog
    ):
        """Valid YAML produces zero unknown-key WARNINGs."""
        yaml_text = base_config_yaml_single_floor.replace(
            "    factor_down: 0.85\n  thresholds:",
            "    factor_down: 0.85\n"
            "    target_bloat_ms: 42\n"
            "    warn_bloat_ms: 105\n"
            "  thresholds:",
        )
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_text)

        with caplog.at_level(logging.WARNING, logger="wanctl.autorate_config"):
            Config(str(config_file))

        unknown_warnings = [
            rec for rec in caplog.records if "Unknown config key" in rec.getMessage()
        ]
        assert unknown_warnings == [], (
            f"Expected zero unknown-key warnings, got: "
            f"{[r.getMessage() for r in unknown_warnings]}"
        )


# =============================================================================
# TestConfigCeilingAndSteps
# =============================================================================


class TestConfigCeilingAndSteps:
    """Tests for ceiling and step values in Config."""

    def test_ceiling_and_step_values(self, base_config_yaml_state_based, tmp_path):
        """Ceiling and step values are loaded correctly."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(base_config_yaml_state_based)

        config = Config(str(config_file))

        # Download
        assert config.download_ceiling == 920 * 1_000_000
        assert config.download_step_up == 10 * 1_000_000
        assert config.download_factor_down == 0.85

        # Upload
        assert config.upload_ceiling == 40 * 1_000_000
        assert config.upload_step_up == 1 * 1_000_000
        assert config.upload_factor_down == 0.85

    def test_optional_factor_down_yellow(self, base_config_yaml_state_based, tmp_path):
        """factor_down_yellow defaults correctly when not specified."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(base_config_yaml_state_based)

        config = Config(str(config_file))

        # Default values from code: download=0.96, upload=0.94
        assert config.download_factor_down_yellow == 0.96
        assert config.upload_factor_down_yellow == 0.94

    def test_green_required_defaults(self, base_config_yaml_state_based, tmp_path):
        """green_required defaults to 5 when not specified."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(base_config_yaml_state_based)

        config = Config(str(config_file))

        assert config.download_green_required == 5
        assert config.upload_green_required == 5


# =============================================================================
# TestConfigAlphaFallback
# =============================================================================


class TestConfigAlphaFallback:
    """Tests for Config alpha parameter fallback paths.

    Covers lines 364-386: alpha_baseline and alpha_load fallback logic.
    """

    def test_alpha_baseline_raw_value(self, tmp_path):
        """Test alpha_baseline uses raw value when no time_constant provided.

        Covers lines 364-365: elif "alpha_baseline" in thresh.
        """
        config_yaml = """
wan_name: TestWAN
router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/tmp/test_id_rsa"

queues:
  download: "cake-download"
  upload: "cake-upload"

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 25.0
  ping_hosts:
    - "1.1.1.1"
  download:
    floor_mbps: 400
    ceiling_mbps: 920
    step_up_mbps: 10
    factor_down: 0.85
  upload:
    floor_mbps: 25
    ceiling_mbps: 40
    step_up_mbps: 1
    factor_down: 0.85
  thresholds:
    target_bloat_ms: 15
    warn_bloat_ms: 45
    alpha_baseline: 0.0005
    load_time_constant_sec: 0.5

logging:
  main_log: "/tmp/test.log"
  debug_log: "/tmp/test_debug.log"

lock_file: "/tmp/test.lock"
lock_timeout: 300
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_yaml)

        config = Config(str(config_file))

        # Raw alpha_baseline should be used directly
        assert config.alpha_baseline == 0.0005

    def test_alpha_load_raw_value_with_slow_warning(self, tmp_path, caplog):
        """Test alpha_load raw value logs deprecation warning and translates correctly.

        alpha_load is now a deprecated param; deprecate_param translates it to
        load_time_constant_sec and logs a deprecation warning.
        """
        import logging

        config_yaml = """
wan_name: TestWAN
router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/tmp/test_id_rsa"

queues:
  download: "cake-download"
  upload: "cake-upload"

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 25.0
  ping_hosts:
    - "1.1.1.1"
  download:
    floor_mbps: 400
    ceiling_mbps: 920
    step_up_mbps: 10
    factor_down: 0.85
  upload:
    floor_mbps: 25
    ceiling_mbps: 40
    step_up_mbps: 1
    factor_down: 0.85
  thresholds:
    target_bloat_ms: 15
    warn_bloat_ms: 45
    baseline_time_constant_sec: 60
    alpha_load: 0.001

logging:
  main_log: "/tmp/test.log"
  debug_log: "/tmp/test_debug.log"

lock_file: "/tmp/test.lock"
lock_timeout: 300
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_yaml)

        # Enable logging capture
        with caplog.at_level(logging.WARNING, logger="wanctl.autorate_continuous"):
            config = Config(str(config_file))

        # alpha_load should still compute to same value (translated through time_constant)
        # alpha_load=0.001 -> TC=0.05/0.001=50 -> alpha=0.05/50=0.001
        assert config.alpha_load == 0.001

        # But baseline_time_constant_sec takes precedence over deprecated alpha_load,
        # so no deprecation warning for alpha_load (modern key already present).
        # Note: this config has BOTH baseline_time_constant_sec AND alpha_load,
        # but alpha_load and load_time_constant_sec are a separate pair.
        # Since load_time_constant_sec is NOT in config, deprecation warning fires.
        assert any("Deprecated" in msg and "alpha_load" in msg for msg in caplog.messages)

    def test_alpha_load_raw_value_no_warning_for_fast(self, tmp_path, caplog):
        """Test alpha_load raw value does NOT warn for fast time constant.

        A fast alpha (giving TC < 5s) should not trigger warning.
        """
        import logging

        config_yaml = """
wan_name: TestWAN
router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/tmp/test_id_rsa"

queues:
  download: "cake-download"
  upload: "cake-upload"

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 25.0
  ping_hosts:
    - "1.1.1.1"
  download:
    floor_mbps: 400
    ceiling_mbps: 920
    step_up_mbps: 10
    factor_down: 0.85
  upload:
    floor_mbps: 25
    ceiling_mbps: 40
    step_up_mbps: 1
    factor_down: 0.85
  thresholds:
    target_bloat_ms: 15
    warn_bloat_ms: 45
    baseline_time_constant_sec: 60
    alpha_load: 0.1

logging:
  main_log: "/tmp/test.log"
  debug_log: "/tmp/test_debug.log"

lock_file: "/tmp/test.lock"
lock_timeout: 300
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_yaml)

        # Enable logging capture
        with caplog.at_level(logging.WARNING, logger="wanctl.autorate_continuous"):
            config = Config(str(config_file))

        # Raw alpha_load should be used directly
        assert config.alpha_load == 0.1

        # Should NOT warn - 0.05/0.1 = 0.5s which is < 5s
        assert not any("alpha_load" in msg and "time constant" in msg for msg in caplog.messages)

    def test_missing_alpha_baseline_raises_valueerror(self, tmp_path):
        """Test missing both alpha_baseline and baseline_time_constant_sec raises ValueError.

        Covers lines 367-369: raise ValueError for missing alpha_baseline config.
        """
        config_yaml = """
wan_name: TestWAN
router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/tmp/test_id_rsa"

queues:
  download: "cake-download"
  upload: "cake-upload"

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 25.0
  ping_hosts:
    - "1.1.1.1"
  download:
    floor_mbps: 400
    ceiling_mbps: 920
    step_up_mbps: 10
    factor_down: 0.85
  upload:
    floor_mbps: 25
    ceiling_mbps: 40
    step_up_mbps: 1
    factor_down: 0.85
  thresholds:
    target_bloat_ms: 15
    warn_bloat_ms: 45
    load_time_constant_sec: 0.5

logging:
  main_log: "/tmp/test.log"
  debug_log: "/tmp/test_debug.log"

lock_file: "/tmp/test.lock"
lock_timeout: 300
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_yaml)

        with pytest.raises(
            ValueError, match="must specify either baseline_time_constant_sec or alpha_baseline"
        ):
            Config(str(config_file))

    def test_missing_alpha_load_raises_valueerror(self, tmp_path):
        """Test missing both alpha_load and load_time_constant_sec raises ValueError.

        Covers lines 385-386: raise ValueError for missing alpha_load config.
        """
        config_yaml = """
wan_name: TestWAN
router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/tmp/test_id_rsa"

queues:
  download: "cake-download"
  upload: "cake-upload"

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 25.0
  ping_hosts:
    - "1.1.1.1"
  download:
    floor_mbps: 400
    ceiling_mbps: 920
    step_up_mbps: 10
    factor_down: 0.85
  upload:
    floor_mbps: 25
    ceiling_mbps: 40
    step_up_mbps: 1
    factor_down: 0.85
  thresholds:
    target_bloat_ms: 15
    warn_bloat_ms: 45
    baseline_time_constant_sec: 60

logging:
  main_log: "/tmp/test.log"
  debug_log: "/tmp/test_debug.log"

lock_file: "/tmp/test.lock"
lock_timeout: 300
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_yaml)

        with pytest.raises(
            ValueError, match="must specify either load_time_constant_sec or alpha_load"
        ):
            Config(str(config_file))

    def test_alpha_baseline_deprecation_warning_logged(self, tmp_path, caplog):
        """Test that using alpha_baseline logs a deprecation warning."""
        import logging

        config_yaml = """
wan_name: TestWAN
router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/tmp/test_id_rsa"

queues:
  download: "cake-download"
  upload: "cake-upload"

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 25.0
  ping_hosts:
    - "1.1.1.1"
  download:
    floor_mbps: 400
    ceiling_mbps: 920
    step_up_mbps: 10
    factor_down: 0.85
  upload:
    floor_mbps: 25
    ceiling_mbps: 40
    step_up_mbps: 1
    factor_down: 0.85
  thresholds:
    target_bloat_ms: 15
    warn_bloat_ms: 45
    alpha_baseline: 0.0005
    load_time_constant_sec: 0.5

logging:
  main_log: "/tmp/test.log"
  debug_log: "/tmp/test_debug.log"

lock_file: "/tmp/test.lock"
lock_timeout: 300
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_yaml)

        with caplog.at_level(logging.WARNING, logger="wanctl.autorate_continuous"):
            config = Config(str(config_file))

        # Value should still be correct (round-trip through time_constant)
        assert config.alpha_baseline == pytest.approx(0.0005)

        # Deprecation warning should mention alpha_baseline and baseline_time_constant_sec
        assert any(
            "Deprecated" in msg and "alpha_baseline" in msg and "baseline_time_constant_sec" in msg
            for msg in caplog.messages
        )

    def test_alpha_load_deprecation_warning_logged(self, tmp_path, caplog):
        """Test that using alpha_load logs a deprecation warning."""
        import logging

        config_yaml = """
wan_name: TestWAN
router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/tmp/test_id_rsa"

queues:
  download: "cake-download"
  upload: "cake-upload"

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 25.0
  ping_hosts:
    - "1.1.1.1"
  download:
    floor_mbps: 400
    ceiling_mbps: 920
    step_up_mbps: 10
    factor_down: 0.85
  upload:
    floor_mbps: 25
    ceiling_mbps: 40
    step_up_mbps: 1
    factor_down: 0.85
  thresholds:
    target_bloat_ms: 15
    warn_bloat_ms: 45
    baseline_time_constant_sec: 60
    alpha_load: 0.1

logging:
  main_log: "/tmp/test.log"
  debug_log: "/tmp/test_debug.log"

lock_file: "/tmp/test.lock"
lock_timeout: 300
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_yaml)

        with caplog.at_level(logging.WARNING, logger="wanctl.autorate_continuous"):
            config = Config(str(config_file))

        # Value should still be correct
        assert config.alpha_load == pytest.approx(0.1)

        # Deprecation warning for alpha_load
        assert any(
            "Deprecated" in msg and "alpha_load" in msg and "load_time_constant_sec" in msg
            for msg in caplog.messages
        )


# =============================================================================
# TestConfigRouterTransportDefault
# =============================================================================


class TestConfigRouterTransportDefault:
    """Tests for autorate Config router_transport default.

    CLEAN-04: Autorate Config must default router_transport to "rest" when
    the transport key is omitted from the router section. This matches the
    steering daemon default and the factory default, resolving the previous
    contradiction where config defaulted to "ssh" but factory used "rest".
    """

    def test_router_transport_defaults_to_rest_when_omitted(self, tmp_path):
        """Config defaults router_transport to 'rest' when transport key is missing."""
        config_yaml = """
wan_name: TestWAN
router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/tmp/test_id_rsa"

queues:
  download: "cake-download"
  upload: "cake-upload"

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 25.0
  ping_hosts:
    - "1.1.1.1"
  download:
    floor_mbps: 400
    ceiling_mbps: 920
    step_up_mbps: 10
    factor_down: 0.85
  upload:
    floor_mbps: 25
    ceiling_mbps: 40
    step_up_mbps: 1
    factor_down: 0.85
  thresholds:
    target_bloat_ms: 15
    warn_bloat_ms: 45
    baseline_time_constant_sec: 60
    load_time_constant_sec: 0.5

logging:
  main_log: "/tmp/test.log"
  debug_log: "/tmp/test_debug.log"

lock_file: "/tmp/test.lock"
lock_timeout: 300
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_yaml)

        config = Config(str(config_file))

        assert config.router_transport == "rest"

    def test_router_transport_explicit_rest(self, tmp_path):
        """Config honors explicit transport='rest' setting."""
        config_yaml = """
wan_name: TestWAN
router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/tmp/test_id_rsa"
  transport: "rest"

queues:
  download: "cake-download"
  upload: "cake-upload"

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 25.0
  ping_hosts:
    - "1.1.1.1"
  download:
    floor_mbps: 400
    ceiling_mbps: 920
    step_up_mbps: 10
    factor_down: 0.85
  upload:
    floor_mbps: 25
    ceiling_mbps: 40
    step_up_mbps: 1
    factor_down: 0.85
  thresholds:
    target_bloat_ms: 15
    warn_bloat_ms: 45
    baseline_time_constant_sec: 60
    load_time_constant_sec: 0.5

logging:
  main_log: "/tmp/test.log"
  debug_log: "/tmp/test_debug.log"

lock_file: "/tmp/test.lock"
lock_timeout: 300
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_yaml)

        config = Config(str(config_file))

        assert config.router_transport == "rest"


# =============================================================================
# TestConfigVerifySslDefault
# =============================================================================


class TestConfigVerifySslDefault:
    """Tests for autorate Config verify_ssl default.

    OPS-01: Config must default router_verify_ssl to True when
    verify_ssl key is omitted from the router section. This ensures
    secure-by-default behavior matching the RouterOS REST client fallback.
    """

    def test_verify_ssl_defaults_to_true_when_omitted(self, tmp_path):
        """Config defaults router_verify_ssl to True when verify_ssl key is missing."""
        config_yaml = """
wan_name: TestWAN
router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/tmp/test_id_rsa"

queues:
  download: "cake-download"
  upload: "cake-upload"

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 25.0
  ping_hosts:
    - "1.1.1.1"
  download:
    floor_mbps: 400
    ceiling_mbps: 920
    step_up_mbps: 10
    factor_down: 0.85
  upload:
    floor_mbps: 25
    ceiling_mbps: 40
    step_up_mbps: 1
    factor_down: 0.85
  thresholds:
    target_bloat_ms: 15
    warn_bloat_ms: 45
    baseline_time_constant_sec: 60
    load_time_constant_sec: 0.5

logging:
  main_log: "/tmp/test.log"
  debug_log: "/tmp/test_debug.log"

lock_file: "/tmp/test.lock"
lock_timeout: 300
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_yaml)

        config = Config(str(config_file))

        assert config.router_verify_ssl is True

    def test_verify_ssl_explicit_false_still_works(self, tmp_path):
        """Config honors explicit verify_ssl=false setting (no regression)."""
        config_yaml = """
wan_name: TestWAN
router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/tmp/test_id_rsa"
  verify_ssl: false

queues:
  download: "cake-download"
  upload: "cake-upload"

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 25.0
  ping_hosts:
    - "1.1.1.1"
  download:
    floor_mbps: 400
    ceiling_mbps: 920
    step_up_mbps: 10
    factor_down: 0.85
  upload:
    floor_mbps: 25
    ceiling_mbps: 40
    step_up_mbps: 1
    factor_down: 0.85
  thresholds:
    target_bloat_ms: 15
    warn_bloat_ms: 45
    baseline_time_constant_sec: 60
    load_time_constant_sec: 0.5

logging:
  main_log: "/tmp/test.log"
  debug_log: "/tmp/test_debug.log"

lock_file: "/tmp/test.lock"
lock_timeout: 300
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_yaml)

        config = Config(str(config_file))

        assert config.router_verify_ssl is False


class TestConfigFallbackGatewayDefault:
    """Tests for safe fallback_gateway_ip default (SECR-03).

    When no fallback_checks.gateway_ip is configured, the default must be
    empty string (not a hardcoded IP) so verify_local_connectivity safely skips.
    """

    def test_fallback_gateway_ip_defaults_to_empty_when_omitted(self, tmp_path):
        """Config defaults fallback_gateway_ip to '' when gateway_ip key is missing."""
        config_yaml = """
wan_name: TestWAN
router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/tmp/test_id_rsa"

queues:
  download: "cake-download"
  upload: "cake-upload"

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 25.0
  ping_hosts:
    - "1.1.1.1"
  download:
    floor_mbps: 400
    ceiling_mbps: 920
    step_up_mbps: 10
    factor_down: 0.85
  upload:
    floor_mbps: 25
    ceiling_mbps: 40
    step_up_mbps: 1
    factor_down: 0.85
  thresholds:
    target_bloat_ms: 15
    warn_bloat_ms: 45
    baseline_time_constant_sec: 60
    load_time_constant_sec: 0.5

logging:
  main_log: "/tmp/test.log"
  debug_log: "/tmp/test_debug.log"

lock_file: "/tmp/test.lock"
lock_timeout: 300
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_yaml)

        config = Config(str(config_file))

        assert config.fallback_gateway_ip == ""

    def test_fallback_gateway_ip_explicit_value_preserved(self, tmp_path):
        """Config honors explicit gateway_ip when set."""
        config_yaml = """
wan_name: TestWAN
router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/tmp/test_id_rsa"

queues:
  download: "cake-download"
  upload: "cake-upload"

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 25.0
  ping_hosts:
    - "1.1.1.1"
  download:
    floor_mbps: 400
    ceiling_mbps: 920
    step_up_mbps: 10
    factor_down: 0.85
  upload:
    floor_mbps: 25
    ceiling_mbps: 40
    step_up_mbps: 1
    factor_down: 0.85
  thresholds:
    target_bloat_ms: 15
    warn_bloat_ms: 45
    baseline_time_constant_sec: 60
    load_time_constant_sec: 0.5
  fallback_checks:
    gateway_ip: "10.10.110.1"

logging:
  main_log: "/tmp/test.log"
  debug_log: "/tmp/test_debug.log"

lock_file: "/tmp/test.lock"
lock_timeout: 300
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_yaml)

        config = Config(str(config_file))

        assert config.fallback_gateway_ip == "10.10.110.1"


# =============================================================================
# MERGED FROM test_config.py
# =============================================================================


class TestStateFileConfig:
    """Tests for _load_state_config respecting YAML state_file key."""

    def _make_config_stub(self, data: dict, lock_file: str = "/tmp/wanctl_att.lock"):
        """Create a minimal Config-like object for testing _load_state_config.

        Bypasses Config.__init__ (which requires full YAML file on disk)
        by creating an instance with just the attributes _load_state_config needs.
        """
        config = object.__new__(Config)
        config.data = data
        config.lock_file = Path(lock_file)
        return config

    def test_explicit_state_file_from_yaml(self):
        """Config with state_file in YAML uses that path."""
        config = self._make_config_stub(
            data={"state_file": "/var/lib/wanctl/spectrum_state.json"},
        )
        config._load_state_config()
        assert config.state_file == Path("/var/lib/wanctl/spectrum_state.json")

    def test_missing_state_file_falls_back_to_lock_derived(self):
        """Config without state_file falls back to lock_file-derived path."""
        config = self._make_config_stub(
            data={},
            lock_file="/tmp/wanctl_att.lock",
        )
        config._load_state_config()
        assert config.state_file == Path("/tmp/wanctl_att_state.json")

    def test_empty_string_state_file_falls_back_to_lock_derived(self):
        """Config with empty string state_file falls back to lock_file-derived path."""
        config = self._make_config_stub(
            data={"state_file": ""},
            lock_file="/tmp/wanctl_spectrum.lock",
        )
        config._load_state_config()
        assert config.state_file == Path("/tmp/wanctl_spectrum_state.json")


class TestCakeStatsCadenceConfig:
    """Tests for continuous_monitoring.cake_stats_cadence_sec loading."""

    @staticmethod
    def _build_config_yaml(cake_stats_cadence_line: str = "") -> str:
        cadence_block = ""
        if cake_stats_cadence_line:
            cadence_block = f"  cake_stats_cadence_sec: {cake_stats_cadence_line}\n"
        return f"""
wan_name: TestWAN
router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/tmp/test_id_rsa"
  transport: "ssh"

queues:
  download: "cake-download"
  upload: "cake-upload"

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 25.0
{cadence_block}  ping_hosts:
    - "1.1.1.1"
  download:
    floor_green_mbps: 800
    floor_yellow_mbps: 600
    floor_soft_red_mbps: 500
    floor_red_mbps: 400
    ceiling_mbps: 920
    step_up_mbps: 10
    factor_down: 0.85
  upload:
    floor_green_mbps: 35
    floor_yellow_mbps: 30
    floor_red_mbps: 25
    ceiling_mbps: 40
    step_up_mbps: 1
    factor_down: 0.85
  thresholds:
    target_bloat_ms: 15
    warn_bloat_ms: 45
    baseline_time_constant_sec: 60
    load_time_constant_sec: 0.5

logging:
  main_log: "/tmp/test_autorate.log"
  debug_log: "/tmp/test_autorate_debug.log"

lock_file: "/tmp/test_autorate.lock"
lock_timeout: 300
"""

    def _load_config(self, tmp_path: Path, cake_stats_cadence_line: str = "") -> Config:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(self._build_config_yaml(cake_stats_cadence_line))
        return Config(str(config_file))

    def test_cake_stats_cadence_sec_default_when_missing(self, tmp_path):
        config = self._load_config(tmp_path)

        assert config.cake_stats_cadence_sec == pytest.approx(0.05)

    def test_cake_stats_cadence_sec_parses_positive_float(self, tmp_path):
        config = self._load_config(tmp_path, "0.1")

        assert config.cake_stats_cadence_sec == pytest.approx(0.1)

    @pytest.mark.parametrize(
        "value_literal",
        ["0", "-0.5", '"fast"', "true", "null", "[]"],
    )
    def test_cake_stats_cadence_sec_warns_and_defaults_on_invalid(
        self, tmp_path, caplog, value_literal
    ):
        with caplog.at_level(logging.WARNING, logger="wanctl.autorate_config"):
            config = self._load_config(tmp_path, value_literal)

        assert config.cake_stats_cadence_sec == pytest.approx(0.05)
        assert any(
            "continuous_monitoring.cake_stats_cadence_sec must be positive number" in message
            for message in caplog.messages
        )

    def test_cake_stats_cadence_sec_accepts_integer(self, tmp_path):
        config = self._load_config(tmp_path, "1")

        assert config.cake_stats_cadence_sec == pytest.approx(1.0)

    def test_cake_stats_cadence_sec_warns_and_caps_on_absurdly_large_value(
        self, tmp_path, caplog
    ):
        for value_literal in ("10.1", "100", "99999"):
            caplog.clear()
            with caplog.at_level(logging.WARNING, logger="wanctl.autorate_config"):
                config = self._load_config(tmp_path, value_literal)

            assert config.cake_stats_cadence_sec == pytest.approx(10.0)
            assert any(
                "continuous_monitoring.cake_stats_cadence_sec value" in message
                and "capping at 10.0" in message
                for message in caplog.messages
            )

        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="wanctl.autorate_config"):
            boundary_config = self._load_config(tmp_path, "10.0")

        assert boundary_config.cake_stats_cadence_sec == pytest.approx(10.0)
        assert not any("capping at" in message for message in caplog.messages)
