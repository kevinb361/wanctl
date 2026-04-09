"""Pytest configuration and shared fixtures."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(autouse=True)
def reset_prometheus_registry():
    """Reset Prometheus metrics registry before and after each test.

    Required for xdist worker isolation (D-18). Each test must start with
    clean metrics state regardless of which worker process runs it.
    """
    try:
        from wanctl import metrics

        metrics.reset()
    except (ImportError, AttributeError):
        pass
    yield
    try:
        from wanctl import metrics

        metrics.reset()
    except (ImportError, AttributeError):
        pass


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_config_data():
    """Sample configuration data for testing."""
    return {
        "wan_name": "TestWAN",
        "router": {"host": "192.168.1.1", "user": "admin", "ssh_key": "/path/to/key"},
        "queues": {"download": "WAN-Download-Test", "upload": "WAN-Upload-Test"},
        "bandwidth": {"down_max": 100, "down_min": 10, "up_max": 20, "up_min": 5},
        "logging": {"main_log": "/tmp/test.log", "debug_log": "/tmp/test_debug.log"},
        "lock_file": "/tmp/test.lock",
        "lock_timeout": 300,
    }


# =============================================================================
# SHARED MOCK CONFIG FIXTURES
#
# Canonical mock configs for autorate test files.
# The superset of attributes needed across all autorate consumers.
#
# Class-level mock_config fixtures in test_wan_controller.py and
# test_autorate_baseline_bounds.py can extend this shared fixture
# for per-class overrides.
#
# Steering mock config lives in tests/steering/conftest.py.
# =============================================================================


@pytest.fixture
def mock_autorate_config():
    """Shared mock config for autorate WANController tests.

    Contains the full superset of attributes used across all autorate test
    files. Individual tests may override specific attributes as needed.
    """
    config = MagicMock()
    config.wan_name = "TestWAN"
    config.baseline_rtt_initial = 25.0
    # Download parameters
    config.download_floor_green = 800_000_000
    config.download_floor_yellow = 600_000_000
    config.download_floor_soft_red = 500_000_000
    config.download_floor_red = 400_000_000
    config.download_ceiling = 920_000_000
    config.download_step_up = 10_000_000
    config.download_factor_down = 0.85
    config.download_factor_down_yellow = 0.96
    config.download_green_required = 5
    # Upload parameters
    config.upload_floor_green = 35_000_000
    config.upload_floor_yellow = 30_000_000
    config.upload_floor_red = 25_000_000
    config.upload_ceiling = 40_000_000
    config.upload_step_up = 1_000_000
    config.upload_factor_down = 0.85
    config.upload_factor_down_yellow = 0.94
    config.upload_green_required = 5
    # Bloat thresholds
    config.target_bloat_ms = 15.0
    config.warn_bloat_ms = 45.0
    config.hard_red_bloat_ms = 80.0
    # EWMA and baseline
    config.alpha_baseline = 0.001
    config.alpha_load = 0.1
    config.baseline_update_threshold_ms = 3.0
    config.baseline_rtt_min = 10.0
    config.baseline_rtt_max = 60.0
    config.accel_threshold_ms = 15.0
    config.accel_confirm_cycles = 3
    # Hysteresis parameters (Phase 122)
    config.dwell_cycles = 3
    config.deadband_ms = 3.0
    # Ping / measurement
    config.ping_hosts = ["1.1.1.1"]
    config.use_median_of_three = False
    # Fallback
    config.fallback_enabled = True
    config.fallback_check_gateway = True
    config.fallback_check_tcp = True
    config.fallback_gateway_ip = ""
    config.fallback_tcp_targets = [["1.1.1.1", 443], ["8.8.8.8", 443]]
    config.fallback_mode = "graceful_degradation"
    config.fallback_max_cycles = 3
    # Metrics and state
    config.metrics_enabled = False
    config.state_file = MagicMock()
    # Queue names
    config.queue_down = "dl-spectrum"
    config.queue_up = "ul-spectrum"
    # Alerting (disabled by default in tests)
    config.alerting_config = None
    # Signal processing config (always active, default params)
    config.signal_processing_config = {
        "hampel_window_size": 7,
        "hampel_sigma_threshold": 3.0,
        "jitter_time_constant_sec": 2.0,
        "variance_time_constant_sec": 5.0,
    }
    # IRTT config (disabled by default in tests)
    config.irtt_config = {
        "enabled": False,
        "server": None,
        "port": 2112,
        "duration_sec": 1.0,
        "interval_ms": 100,
        "cadence_sec": 10.0,
    }
    # Reflector quality config (default params for tests)
    config.reflector_quality_config = {
        "min_score": 0.8,
        "window_size": 50,
        "probe_interval_sec": 30.0,
        "recovery_count": 3,
    }
    # OWD asymmetry detection config (default ratio_threshold 2.0)
    config.owd_asymmetry_config = {"ratio_threshold": 2.0}
    # Fusion config (optional, default icmp_weight 0.7, disabled by default)
    config.fusion_config = {"icmp_weight": 0.7, "enabled": False}
    # Asymmetry gate config (Phase 156, disabled by default in tests)
    config.asymmetry_gate_config = {
        "enabled": False,
        "damping_factor": 0.5,
        "min_ratio": 3.0,
        "confirm_readings": 3,
        "staleness_sec": 30.0,
    }
    # Tuning config (optional, disabled by default)
    config.tuning_config = None
    return config
