"""Tests for Config class loading and validation in autorate_continuous.

Covers:
- Config._load_download_config (legacy and state-based floors)
- Config._load_upload_config (legacy and state-based floors)
- Floor ordering validation

Coverage target: lines 274-343 (_load_download_config, _load_upload_config).
"""

import pytest

from wanctl.autorate_continuous import Config


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
def base_config_yaml_legacy() -> str:
    """Base config YAML with legacy single floor (v1 format)."""
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

    def test_load_download_legacy_floor(self, base_config_yaml_legacy, tmp_path):
        """Legacy single floor_mbps applies to all states."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(base_config_yaml_legacy)

        config = Config(str(config_file))

        # Legacy floor (400 Mbps) should be used for all states
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


class TestLoadUploadConfig:
    """Tests for Config._load_upload_config method."""

    def test_load_upload_legacy_floor(self, base_config_yaml_legacy, tmp_path):
        """Legacy single floor_mbps applies to all states."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(base_config_yaml_legacy)

        config = Config(str(config_file))

        # Legacy floor (25 Mbps) should be used for all states
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
