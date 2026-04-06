"""Tests for Phase 136: Hysteresis observability - windowed suppression counters.

TDD RED phase: These tests define the behavior contract for windowed suppression
rate tracking in QueueController, health endpoint extensions, and periodic logging.
"""

import json
import logging
import time
import urllib.request
from unittest.mock import MagicMock

import pytest

from tests.helpers import find_free_port
from wanctl.health_check import (
    HealthCheckHandler,
    start_health_server,
)
from wanctl.perf_profiler import OperationProfiler
from wanctl.queue_controller import QueueController

# =============================================================================
# TEST HELPERS
# =============================================================================


def _make_qc(name: str = "upload", dwell_cycles: int = 3) -> QueueController:
    """Create a QueueController with standard test params."""
    return QueueController(
        name=name,
        floor_green=5_000_000,
        floor_yellow=4_000_000,
        floor_soft_red=3_000_000,
        floor_red=2_000_000,
        ceiling=10_000_000,
        step_up=500_000,
        factor_down=0.85,
        factor_down_yellow=0.96,
        green_required=5,
        dwell_cycles=dwell_cycles,
        deadband_ms=0.0,
    )


def _make_download_qc(dwell_cycles: int = 3) -> QueueController:
    """Create a download QueueController for 4-state tests."""
    return QueueController(
        name="download",
        floor_green=500_000_000,
        floor_yellow=400_000_000,
        floor_soft_red=300_000_000,
        floor_red=200_000_000,
        ceiling=900_000_000,
        step_up=10_000_000,
        factor_down=0.85,
        factor_down_yellow=0.96,
        green_required=5,
        dwell_cycles=dwell_cycles,
        deadband_ms=0.0,
    )


# =============================================================================
# WINDOWED COUNTER IN QUEUECONTROLLER
# =============================================================================


class TestQueueControllerWindowedCounter:
    """QueueController tracks suppressions in 60s windows."""

    BASELINE = 10.0
    LOAD_RTT = 20.0  # delta=10.0
    TARGET_DELTA = 5.0  # delta > 5 triggers dwell
    WARN_DELTA = 25.0

    # 4-state thresholds
    GREEN_THRESHOLD = 5.0
    SOFT_RED_THRESHOLD = 15.0
    HARD_RED_THRESHOLD = 25.0

    def test_init_window_suppressions_zero(self):
        """New QueueController has _window_suppressions=0."""
        qc = _make_qc()
        assert qc._window_suppressions == 0

    def test_init_window_start_time_set(self):
        """New QueueController has _window_start_time set to current time."""
        before = time.time()
        qc = _make_qc()
        after = time.time()
        assert before <= qc._window_start_time <= after

    def test_init_window_had_congestion_false(self):
        """New QueueController has _window_had_congestion=False."""
        qc = _make_qc()
        assert qc._window_had_congestion is False

    def test_adjust_dwell_increments_window_suppressions(self):
        """Suppression during dwell in adjust() increments _window_suppressions."""
        qc = _make_qc(dwell_cycles=3)
        # 2 cycles above threshold but below dwell_cycles -> 2 suppressed
        for _ in range(2):
            qc.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.LOAD_RTT,
                target_delta=self.TARGET_DELTA,
                warn_delta=self.WARN_DELTA,
            )
        assert qc._window_suppressions == 2
        # Also verify cumulative counter matches
        assert qc._transitions_suppressed == 2

    def test_adjust_4state_dwell_increments_window_suppressions(self):
        """Suppression during dwell in adjust_4state() increments _window_suppressions."""
        qc = _make_download_qc(dwell_cycles=3)
        # 2 cycles in YELLOW zone during dwell -> 2 suppressed
        for _ in range(2):
            qc.adjust_4state(
                baseline_rtt=self.BASELINE,
                load_rtt=self.LOAD_RTT,
                green_threshold=self.GREEN_THRESHOLD,
                soft_red_threshold=self.SOFT_RED_THRESHOLD,
                hard_red_threshold=self.HARD_RED_THRESHOLD,
            )
        assert qc._window_suppressions == 2
        assert qc._transitions_suppressed == 2

    def test_reset_window_returns_previous_count(self):
        """reset_window() returns the previous window's suppression count."""
        qc = _make_qc(dwell_cycles=3)
        # Cause 2 suppressions
        for _ in range(2):
            qc.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.LOAD_RTT,
                target_delta=self.TARGET_DELTA,
                warn_delta=self.WARN_DELTA,
            )
        count = qc.reset_window()
        assert count == 2

    def test_reset_window_resets_to_zero(self):
        """reset_window() resets _window_suppressions to 0."""
        qc = _make_qc(dwell_cycles=3)
        for _ in range(2):
            qc.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.LOAD_RTT,
                target_delta=self.TARGET_DELTA,
                warn_delta=self.WARN_DELTA,
            )
        qc.reset_window()
        assert qc._window_suppressions == 0

    def test_reset_window_updates_start_time(self):
        """reset_window() updates _window_start_time."""
        qc = _make_qc()
        old_start = qc._window_start_time
        time.sleep(0.01)  # Ensure time passes
        qc.reset_window()
        assert qc._window_start_time > old_start

    def test_reset_window_resets_congestion_flag(self):
        """reset_window() clears _window_had_congestion."""
        qc = _make_qc()
        qc._window_had_congestion = True
        qc.reset_window()
        assert qc._window_had_congestion is False


# =============================================================================
# CONGESTION TRACKING
# =============================================================================


class TestWindowCongestionTracking:
    """_window_had_congestion tracks whether congestion occurred during window."""

    BASELINE = 10.0
    TARGET_DELTA = 5.0
    WARN_DELTA = 25.0

    # 4-state thresholds
    GREEN_THRESHOLD = 5.0
    SOFT_RED_THRESHOLD = 15.0
    HARD_RED_THRESHOLD = 25.0

    def test_yellow_sets_congestion_flag_adjust(self):
        """adjust() entering YELLOW sets _window_had_congestion=True."""
        qc = _make_qc(dwell_cycles=1)  # dwell=1 so first above-threshold fires YELLOW
        # delta=10 > target=5, dwell=1 -> immediate YELLOW
        zone, _, _ = qc.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=20.0,
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )
        assert zone == "YELLOW"
        assert qc._window_had_congestion is True

    def test_red_sets_congestion_flag_adjust(self):
        """adjust() entering RED sets _window_had_congestion=True."""
        qc = _make_qc()
        # delta=30 > warn=25 -> RED
        zone, _, _ = qc.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=40.0,
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )
        assert zone == "RED"
        assert qc._window_had_congestion is True

    def test_green_does_not_set_congestion_flag(self):
        """adjust() staying GREEN does not set _window_had_congestion."""
        qc = _make_qc()
        # delta=1 < target=5 -> GREEN
        zone, _, _ = qc.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=11.0,
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )
        assert zone == "GREEN"
        assert qc._window_had_congestion is False

    def test_dwell_held_green_does_not_set_congestion(self):
        """Dwell-held GREEN (zone="GREEN" while above threshold) does not set _window_had_congestion."""
        qc = _make_qc(dwell_cycles=3)
        # delta=10 > target=5 but dwell holds GREEN
        zone, _, _ = qc.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=20.0,
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )
        assert zone == "GREEN"  # Held by dwell
        assert qc._window_had_congestion is False

    def test_yellow_sets_congestion_flag_4state(self):
        """adjust_4state() entering YELLOW sets _window_had_congestion=True."""
        qc = _make_download_qc(dwell_cycles=1)
        # delta=10 > green=5 -> YELLOW (dwell=1 fires immediately)
        zone, _, _ = qc.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=20.0,
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
        )
        assert zone == "YELLOW"
        assert qc._window_had_congestion is True

    def test_soft_red_sets_congestion_flag_4state(self):
        """adjust_4state() entering SOFT_RED sets _window_had_congestion=True."""
        qc = _make_download_qc(dwell_cycles=1)
        # delta=20 > soft_red=15 -> SOFT_RED (soft_red_required=1)
        zone, _, _ = qc.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=30.0,
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
        )
        assert zone == "SOFT_RED"
        assert qc._window_had_congestion is True

    def test_red_sets_congestion_flag_4state(self):
        """adjust_4state() entering RED sets _window_had_congestion=True."""
        qc = _make_download_qc()
        # delta=30 > hard_red=25 -> RED
        zone, _, _ = qc.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=40.0,
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
        )
        assert zone == "RED"
        assert qc._window_had_congestion is True

    def test_congestion_flag_persists_across_zones(self):
        """Once set, _window_had_congestion stays True even if zone returns to GREEN."""
        qc = _make_qc(dwell_cycles=1)
        # Enter YELLOW
        qc.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=20.0,
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )
        assert qc._window_had_congestion is True

        # Return to GREEN
        qc.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=11.0,
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )
        # Flag stays True (only reset by reset_window())
        assert qc._window_had_congestion is True

    def test_reset_window_clears_congestion(self):
        """reset_window() clears _window_had_congestion."""
        qc = _make_qc(dwell_cycles=1)
        qc.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=20.0,
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )
        assert qc._window_had_congestion is True
        qc.reset_window()
        assert qc._window_had_congestion is False


# =============================================================================
# HEALTH ENDPOINT
# =============================================================================


class TestHysteresisHealthEndpoint:
    """Health endpoint includes windowed suppression fields in hysteresis section."""

    @pytest.fixture(autouse=True)
    def reset_handler_state(self):
        """Reset HealthCheckHandler class state before each test."""
        HealthCheckHandler.controller = None
        HealthCheckHandler.start_time = None
        HealthCheckHandler.consecutive_failures = 0
        yield
        HealthCheckHandler.controller = None
        HealthCheckHandler.start_time = None
        HealthCheckHandler.consecutive_failures = 0

    def _make_mock_wan_controller(self):
        """Create a mock WAN controller with all required attributes."""
        wan = MagicMock()
        wan.baseline_rtt = 24.5
        wan.load_rtt = 28.3
        wan.download.current_rate = 800_000_000
        wan.download.red_streak = 0
        wan.download.soft_red_streak = 0
        wan.download.soft_red_required = 3
        wan.download.green_streak = 5
        wan.download.green_required = 5
        wan.download._yellow_dwell = 0
        wan.download.dwell_cycles = 3
        wan.download.deadband_ms = 3.0
        wan.download._transitions_suppressed = 12
        wan.download._window_suppressions = 5
        wan.download._window_start_time = 1712345000.0
        wan.upload.current_rate = 35_000_000
        wan.upload.red_streak = 0
        wan.upload.soft_red_streak = 0
        wan.upload.soft_red_required = 3
        wan.upload.green_streak = 5
        wan.upload.green_required = 5
        wan.upload._yellow_dwell = 0
        wan.upload.dwell_cycles = 3
        wan.upload.deadband_ms = 3.0
        wan.upload._transitions_suppressed = 8
        wan.upload._window_suppressions = 3
        wan.upload._window_start_time = 1712345000.0
        wan.router_connectivity.is_reachable = True
        wan.router_connectivity.to_dict.return_value = {
            "is_reachable": True,
            "consecutive_failures": 0,
            "last_failure_type": None,
            "last_failure_time": None,
        }
        wan._last_signal_result = None
        wan._irtt_thread = None
        wan._irtt_correlation = None
        wan._last_asymmetry_result = None
        wan._fusion_enabled = False
        wan._fusion_icmp_weight = 0.7
        wan._last_fused_rtt = None
        wan._last_icmp_filtered_rtt = None
        wan._fusion_healer = None
        wan._profiler = OperationProfiler(max_samples=1200)
        wan._overrun_count = 0
        wan._cycle_interval_ms = 50.0
        wan._warning_threshold_pct = 80.0
        wan._suppression_alert_threshold = 20
        return wan

    def test_hysteresis_has_windowed_fields_download(self):
        """Download hysteresis section includes suppressions_per_min, window_start_epoch, alert_threshold_per_min."""
        wan = self._make_mock_wan_controller()
        mock_controller = MagicMock()
        mock_config = MagicMock()
        mock_config.wan_name = "spectrum"
        mock_config.irtt_config = {"enabled": False}
        mock_controller.wan_controllers = [
            {"controller": wan, "config": mock_config, "logger": MagicMock()}
        ]

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=mock_controller)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            dl_hyst = data["wans"][0]["download"]["hysteresis"]
            assert "suppressions_per_min" in dl_hyst
            assert dl_hyst["suppressions_per_min"] == 5
            assert "window_start_epoch" in dl_hyst
            assert dl_hyst["window_start_epoch"] == 1712345000.0
            assert "alert_threshold_per_min" in dl_hyst
            assert dl_hyst["alert_threshold_per_min"] == 20
            # Existing fields still present
            assert "dwell_counter" in dl_hyst
            assert "transitions_suppressed" in dl_hyst
            assert dl_hyst["transitions_suppressed"] == 12
        finally:
            server.shutdown()

    def test_hysteresis_has_windowed_fields_upload(self):
        """Upload hysteresis section includes suppressions_per_min, window_start_epoch, alert_threshold_per_min."""
        wan = self._make_mock_wan_controller()
        mock_controller = MagicMock()
        mock_config = MagicMock()
        mock_config.wan_name = "spectrum"
        mock_config.irtt_config = {"enabled": False}
        mock_controller.wan_controllers = [
            {"controller": wan, "config": mock_config, "logger": MagicMock()}
        ]

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=mock_controller)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            ul_hyst = data["wans"][0]["upload"]["hysteresis"]
            assert "suppressions_per_min" in ul_hyst
            assert ul_hyst["suppressions_per_min"] == 3
            assert "window_start_epoch" in ul_hyst
            assert ul_hyst["window_start_epoch"] == 1712345000.0
            assert "alert_threshold_per_min" in ul_hyst
            assert ul_hyst["alert_threshold_per_min"] == 20
        finally:
            server.shutdown()


# =============================================================================
# PERIODIC LOGGING (WANController._check_hysteresis_window)
# =============================================================================


class TestPeriodicHysteresisLogging:
    """WANController logs INFO at 60s window boundary when congestion occurred."""

    def _make_mock_wan_controller(self):
        """Create a mock WANController with download/upload QueueControllers."""
        from wanctl.wan_controller import WANController

        wc = MagicMock(spec=WANController)
        wc.wan_name = "spectrum"
        wc.logger = logging.getLogger("wanctl.autorate_continuous")
        wc._suppression_alert_threshold = 20
        wc.alert_engine = MagicMock()

        # Use real QueueControllers for accurate behavior
        wc.download = _make_download_qc()
        wc.upload = _make_qc()

        return wc

    def test_logs_info_when_congestion_and_window_elapsed(self, caplog):
        """_check_hysteresis_window() logs INFO when 60s window elapsed AND congestion occurred."""
        from wanctl.wan_controller import WANController

        wc = self._make_mock_wan_controller()

        # Set up: had congestion and some suppressions
        wc.download._window_had_congestion = True
        wc.download._window_suppressions = 7
        wc.upload._window_suppressions = 3

        # Make window appear elapsed (set start time 61s ago)
        past = time.time() - 61.0
        wc.download._window_start_time = past
        wc.upload._window_start_time = past

        with caplog.at_level(logging.INFO, logger="wanctl.autorate_continuous"):
            dl_count, ul_count = WANController._check_hysteresis_window(wc)

        assert dl_count == 7
        assert ul_count == 3
        assert any("[HYSTERESIS]" in r.message and "suppressions" in r.message for r in caplog.records)

    def test_no_log_when_no_congestion(self, caplog):
        """_check_hysteresis_window() does NOT log when window elapsed but no congestion (D-06)."""
        from wanctl.wan_controller import WANController

        wc = self._make_mock_wan_controller()

        # No congestion, just suppressions from GREEN-only window
        wc.download._window_had_congestion = False
        wc.upload._window_had_congestion = False
        wc.download._window_suppressions = 2
        wc.upload._window_suppressions = 1

        past = time.time() - 61.0
        wc.download._window_start_time = past
        wc.upload._window_start_time = past

        with caplog.at_level(logging.INFO, logger="wanctl.autorate_continuous"):
            dl_count, ul_count = WANController._check_hysteresis_window(wc)

        assert dl_count == 2
        assert ul_count == 1
        # No INFO log emitted
        assert not any("[HYSTERESIS]" in r.message for r in caplog.records)

    def test_no_log_when_window_not_elapsed(self, caplog):
        """_check_hysteresis_window() returns (0,0) when <60s elapsed."""
        from wanctl.wan_controller import WANController

        wc = self._make_mock_wan_controller()

        # Window just started (not elapsed)
        wc.download._window_start_time = time.time()
        wc.download._window_suppressions = 5

        with caplog.at_level(logging.INFO, logger="wanctl.autorate_continuous"):
            dl_count, ul_count = WANController._check_hysteresis_window(wc)

        assert dl_count == 0
        assert ul_count == 0
        assert not any("[HYSTERESIS]" in r.message for r in caplog.records)

    def test_counters_reset_after_window_boundary(self):
        """After window boundary, counters are reset for next window."""
        from wanctl.wan_controller import WANController

        wc = self._make_mock_wan_controller()

        wc.download._window_had_congestion = True
        wc.download._window_suppressions = 5
        wc.upload._window_suppressions = 3

        past = time.time() - 61.0
        wc.download._window_start_time = past
        wc.upload._window_start_time = past

        WANController._check_hysteresis_window(wc)

        # Counters should be reset
        assert wc.download._window_suppressions == 0
        assert wc.upload._window_suppressions == 0
        assert wc.download._window_had_congestion is False
        assert wc.upload._window_had_congestion is False
        # Window start time should be updated
        assert wc.download._window_start_time > past
        assert wc.upload._window_start_time > past
