"""Steering subpackage test fixtures.

Fixtures specific to steering daemon, confidence scoring, CAKE stats,
and steering health endpoint tests.
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_steering_config():
    """Shared mock config for steering daemon tests.

    Contains the full superset of attributes used across all steering test
    files. Individual tests may override specific attributes as needed.
    """
    config = MagicMock()
    config.primary_wan = "spectrum"
    config.alternate_wan = "att"
    config.state_good = "SPECTRUM_GOOD"
    config.state_degraded = "SPECTRUM_DEGRADED"
    config.primary_download_queue = "WAN-Download-Spectrum"
    # RTT thresholds
    config.green_rtt_ms = 5.0
    config.yellow_rtt_ms = 15.0
    config.red_rtt_ms = 15.0
    # CAKE signal thresholds
    config.min_drops_red = 1
    config.min_queue_yellow = 10
    config.min_queue_red = 50
    # Sample requirements
    config.red_samples_required = 2
    config.green_samples_required = 15
    # Metrics and confidence
    config.metrics_enabled = False
    config.use_confidence_scoring = False
    config.confidence_config = None
    # WAN-aware steering (disabled by default, SAFE-04)
    config.wan_state_config = None
    # Alerting (disabled by default in tests)
    config.alerting_config = None
    # Cycle interval for utilization calculation
    config.measurement_interval = 0.05
    return config
