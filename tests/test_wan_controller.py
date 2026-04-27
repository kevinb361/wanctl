"""Tests for WANController class in autorate_continuous module."""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from wanctl.fusion_healer import HealState
from wanctl.reflector_scorer import ReflectorScorer
from wanctl.rtt_measurement import BackgroundRTTThread, RTTCycleStatus, RTTSnapshot
from wanctl.storage.writer import MetricsWriter
from wanctl.wan_controller import (
    ARBITRATION_PRIMARY_ENCODING,
    BACKGROUND_RTT_MIN_CADENCE_SECONDS,
)


class TestHandleIcmpFailure:
    """Tests for WANController.handle_icmp_failure() method.

    Tests all 3 fallback modes and edge cases:
    - graceful_degradation: cycle-based strategy (use last RTT, freeze, fail)
    - freeze: always freeze rates
    - use_last_rtt: always use last known RTT
    - total connectivity loss
    - ICMP recovery
    """

    @pytest.fixture
    def mock_config(self, mock_autorate_config):
        """Delegate to shared mock_autorate_config from conftest.py."""
        return mock_autorate_config

    @pytest.fixture
    def mock_router(self):
        """Create a mock router."""
        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = True
        router.rate_limit_params = {"max_changes": 5, "window_seconds": 10}
        return router

    @pytest.fixture
    def mock_rtt_measurement(self):
        """Create a mock RTT measurement."""
        return MagicMock()

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def controller(self, mock_config, mock_router, mock_rtt_measurement, mock_logger):
        """Create a WANController with mocked dependencies."""
        # Import here to avoid circular imports during collection
        from wanctl.wan_controller import WANController

        # Patch load_state to avoid file I/O
        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=mock_router,
                rtt_measurement=mock_rtt_measurement,
                logger=mock_logger,
            )
        return controller

    # =========================================================================
    # graceful_degradation mode tests
    # =========================================================================

    def test_graceful_degradation_cycle_1_uses_last_rtt(self, controller):
        """Cycle 1 should use last known RTT and return True."""
        controller.config.fallback_mode = "graceful_degradation"
        controller.config.fallback_max_cycles = 3
        controller.icmp_unavailable_cycles = 0
        controller.load_rtt = 28.5

        # Mock connectivity check to return True (connectivity exists)
        with patch.object(controller, "verify_connectivity_fallback", return_value=(True, None)):
            should_continue, measured_rtt = controller.handle_icmp_failure()

        assert should_continue is True
        assert measured_rtt == 28.5
        assert controller.icmp_unavailable_cycles == 1
        controller.logger.warning.assert_called()

    def test_graceful_degradation_cycle_2_freezes(self, controller):
        """Cycle 2 should freeze rates and return (True, None)."""
        controller.config.fallback_mode = "graceful_degradation"
        controller.config.fallback_max_cycles = 3
        controller.icmp_unavailable_cycles = 1  # Will become 2
        controller.load_rtt = 28.5

        with patch.object(controller, "verify_connectivity_fallback", return_value=(True, None)):
            should_continue, measured_rtt = controller.handle_icmp_failure()

        assert should_continue is True
        assert measured_rtt is None  # Freeze mode
        assert controller.icmp_unavailable_cycles == 2

    def test_graceful_degradation_cycle_3_freezes(self, controller):
        """Cycle 3 should freeze rates and return (True, None)."""
        controller.config.fallback_mode = "graceful_degradation"
        controller.config.fallback_max_cycles = 3
        controller.icmp_unavailable_cycles = 2  # Will become 3
        controller.load_rtt = 28.5

        with patch.object(controller, "verify_connectivity_fallback", return_value=(True, None)):
            should_continue, measured_rtt = controller.handle_icmp_failure()

        assert should_continue is True
        assert measured_rtt is None  # Freeze mode
        assert controller.icmp_unavailable_cycles == 3

    def test_graceful_degradation_cycle_4_fails(self, controller):
        """Cycle 4+ should give up and return (False, None)."""
        controller.config.fallback_mode = "graceful_degradation"
        controller.config.fallback_max_cycles = 3
        controller.icmp_unavailable_cycles = 3  # Will become 4
        controller.load_rtt = 28.5

        with patch.object(controller, "verify_connectivity_fallback", return_value=(True, None)):
            should_continue, measured_rtt = controller.handle_icmp_failure()

        assert should_continue is False
        assert measured_rtt is None
        assert controller.icmp_unavailable_cycles == 4
        controller.logger.error.assert_called()

    def test_graceful_degradation_cycle_5_still_fails(self, controller):
        """Cycles beyond max should continue to fail."""
        controller.config.fallback_mode = "graceful_degradation"
        controller.config.fallback_max_cycles = 3
        controller.icmp_unavailable_cycles = 10  # Well past max
        controller.load_rtt = 28.5

        with patch.object(controller, "verify_connectivity_fallback", return_value=(True, None)):
            should_continue, measured_rtt = controller.handle_icmp_failure()

        assert should_continue is False
        assert measured_rtt is None
        assert controller.icmp_unavailable_cycles == 11

    # =========================================================================
    # freeze mode tests
    # =========================================================================

    def test_freeze_mode_always_freezes(self, controller):
        """Freeze mode should always return (True, None) regardless of cycle count."""
        controller.config.fallback_mode = "freeze"
        controller.icmp_unavailable_cycles = 0
        controller.load_rtt = 28.5

        with patch.object(controller, "verify_connectivity_fallback", return_value=(True, None)):
            should_continue, measured_rtt = controller.handle_icmp_failure()

        assert should_continue is True
        assert measured_rtt is None
        assert controller.icmp_unavailable_cycles == 1
        controller.logger.warning.assert_called()

    def test_freeze_mode_freezes_on_high_cycle_count(self, controller):
        """Freeze mode should freeze even after many cycles."""
        controller.config.fallback_mode = "freeze"
        controller.icmp_unavailable_cycles = 100
        controller.load_rtt = 28.5

        with patch.object(controller, "verify_connectivity_fallback", return_value=(True, None)):
            should_continue, measured_rtt = controller.handle_icmp_failure()

        assert should_continue is True
        assert measured_rtt is None
        assert controller.icmp_unavailable_cycles == 101

    # =========================================================================
    # use_last_rtt mode tests
    # =========================================================================

    def test_use_last_rtt_mode_uses_last_rtt(self, controller):
        """use_last_rtt mode should always return last known RTT."""
        controller.config.fallback_mode = "use_last_rtt"
        controller.icmp_unavailable_cycles = 0
        controller.load_rtt = 32.7

        with patch.object(controller, "verify_connectivity_fallback", return_value=(True, None)):
            should_continue, measured_rtt = controller.handle_icmp_failure()

        assert should_continue is True
        assert measured_rtt == 32.7
        assert controller.icmp_unavailable_cycles == 1
        controller.logger.warning.assert_called()

    def test_use_last_rtt_mode_continues_on_high_cycle_count(self, controller):
        """use_last_rtt mode should continue indefinitely."""
        controller.config.fallback_mode = "use_last_rtt"
        controller.icmp_unavailable_cycles = 100
        controller.load_rtt = 32.7

        with patch.object(controller, "verify_connectivity_fallback", return_value=(True, None)):
            should_continue, measured_rtt = controller.handle_icmp_failure()

        assert should_continue is True
        assert measured_rtt == 32.7
        assert controller.icmp_unavailable_cycles == 101

    # =========================================================================
    # Total connectivity loss tests
    # =========================================================================

    def test_total_connectivity_loss_returns_false(self, controller):
        """Should return (False, None) when no connectivity at all."""
        controller.config.fallback_mode = "graceful_degradation"
        controller.icmp_unavailable_cycles = 0
        controller.load_rtt = 28.5

        with patch.object(controller, "verify_connectivity_fallback", return_value=(False, None)):
            should_continue, measured_rtt = controller.handle_icmp_failure()

        assert should_continue is False
        assert measured_rtt is None
        # Counter should NOT increment on total loss
        assert controller.icmp_unavailable_cycles == 0
        controller.logger.warning.assert_called()

    def test_total_connectivity_loss_all_modes(self, controller):
        """Total connectivity loss should fail regardless of fallback mode."""
        for mode in ["graceful_degradation", "freeze", "use_last_rtt"]:
            controller.config.fallback_mode = mode
            controller.icmp_unavailable_cycles = 0

            with patch.object(
                controller, "verify_connectivity_fallback", return_value=(False, None)
            ):
                should_continue, measured_rtt = controller.handle_icmp_failure()

            assert should_continue is False, f"Mode {mode} should fail on total loss"
            assert measured_rtt is None

    # =========================================================================
    # TCP RTT fallback tests
    # =========================================================================

    def test_tcp_rtt_used_when_available(self, controller):
        """Should use TCP RTT directly when ICMP fails but TCP RTT is available."""
        controller.config.fallback_mode = "graceful_degradation"
        controller.icmp_unavailable_cycles = 0
        controller.load_rtt = 28.5  # Should NOT be used

        # TCP RTT of 25.5ms available
        with patch.object(controller, "verify_connectivity_fallback", return_value=(True, 25.5)):
            should_continue, measured_rtt = controller.handle_icmp_failure()

        assert should_continue is True
        assert measured_rtt == 25.5  # TCP RTT, not load_rtt
        assert controller.icmp_unavailable_cycles == 1
        controller.logger.warning.assert_called()

    def test_tcp_rtt_bypasses_degradation_cycles(self, controller):
        """TCP RTT should bypass cycle-based degradation in graceful_degradation mode."""
        controller.config.fallback_mode = "graceful_degradation"
        controller.config.fallback_max_cycles = 3
        controller.icmp_unavailable_cycles = 10  # Would normally trigger failure
        controller.load_rtt = 28.5

        # TCP RTT available - should work regardless of cycle count
        with patch.object(controller, "verify_connectivity_fallback", return_value=(True, 30.2)):
            should_continue, measured_rtt = controller.handle_icmp_failure()

        assert should_continue is True
        assert measured_rtt == 30.2  # TCP RTT used despite high cycle count
        assert controller.icmp_unavailable_cycles == 11

    def test_tcp_rtt_works_in_freeze_mode(self, controller):
        """TCP RTT should be used even in freeze mode when available."""
        controller.config.fallback_mode = "freeze"
        controller.icmp_unavailable_cycles = 0
        controller.load_rtt = 28.5

        with patch.object(controller, "verify_connectivity_fallback", return_value=(True, 22.1)):
            should_continue, measured_rtt = controller.handle_icmp_failure()

        assert should_continue is True
        assert measured_rtt == 22.1  # TCP RTT, not freeze (None)

    def test_tcp_rtt_works_in_use_last_rtt_mode(self, controller):
        """TCP RTT should be used even in use_last_rtt mode when available."""
        controller.config.fallback_mode = "use_last_rtt"
        controller.icmp_unavailable_cycles = 0
        controller.load_rtt = 28.5  # Should NOT be used

        with patch.object(controller, "verify_connectivity_fallback", return_value=(True, 19.8)):
            should_continue, measured_rtt = controller.handle_icmp_failure()

        assert should_continue is True
        assert measured_rtt == 19.8  # TCP RTT, not load_rtt

    def test_fallback_to_degradation_when_no_tcp_rtt(self, controller):
        """Should fall back to degradation behavior when TCP RTT is None."""
        controller.config.fallback_mode = "graceful_degradation"
        controller.config.fallback_max_cycles = 3
        controller.icmp_unavailable_cycles = 3  # Cycle 4 - would fail
        controller.load_rtt = 28.5

        # Connectivity exists but no TCP RTT (gateway-only case)
        with patch.object(controller, "verify_connectivity_fallback", return_value=(True, None)):
            should_continue, measured_rtt = controller.handle_icmp_failure()

        assert should_continue is False  # Cycle 4 should fail
        assert measured_rtt is None

    # =========================================================================
    # Unknown mode tests
    # =========================================================================

    def test_unknown_mode_returns_false(self, controller):
        """Unknown fallback mode should return (False, None) and log error."""
        controller.config.fallback_mode = "invalid_mode"
        controller.icmp_unavailable_cycles = 0
        controller.load_rtt = 28.5

        with patch.object(controller, "verify_connectivity_fallback", return_value=(True, None)):
            should_continue, measured_rtt = controller.handle_icmp_failure()

        assert should_continue is False
        assert measured_rtt is None
        controller.logger.error.assert_called()

    # =========================================================================
    # Metrics recording tests
    # =========================================================================

    def test_metrics_recorded_when_enabled(self, controller):
        """Should record ping failure metrics when metrics are enabled."""
        controller.config.metrics_enabled = True
        controller.config.fallback_mode = "freeze"
        controller.icmp_unavailable_cycles = 0

        with (
            patch.object(controller, "verify_connectivity_fallback", return_value=(True, None)),
            patch("wanctl.wan_controller.record_ping_failure") as mock_record,
        ):
            controller.handle_icmp_failure()

        mock_record.assert_called_once_with("TestWAN")

    def test_metrics_not_recorded_when_disabled(self, controller):
        """Should not record ping failure metrics when metrics are disabled."""
        controller.config.metrics_enabled = False
        controller.config.fallback_mode = "freeze"
        controller.icmp_unavailable_cycles = 0

        with (
            patch.object(controller, "verify_connectivity_fallback", return_value=(True, None)),
            patch("wanctl.wan_controller.record_ping_failure") as mock_record,
        ):
            controller.handle_icmp_failure()

        mock_record.assert_not_called()


class TestIcmpRecovery:
    """Tests for ICMP recovery behavior in run_cycle()."""

    @pytest.fixture
    def mock_config(self, mock_autorate_config):
        """Delegate to shared mock_autorate_config from conftest.py."""
        return mock_autorate_config

    @pytest.fixture
    def mock_router(self):
        """Create a mock router."""
        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = True
        router.rate_limit_params = {"max_changes": 5, "window_seconds": 10}
        return router

    @pytest.fixture
    def mock_rtt_measurement(self):
        """Create a mock RTT measurement."""
        return MagicMock()

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def controller(self, mock_config, mock_router, mock_rtt_measurement, mock_logger):
        """Create a WANController with mocked dependencies."""
        from wanctl.wan_controller import WANController

        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=mock_router,
                rtt_measurement=mock_rtt_measurement,
                logger=mock_logger,
            )
        return controller

    def test_icmp_recovery_resets_counter(self, controller):
        """Should reset icmp_unavailable_cycles when ICMP recovers."""
        controller.icmp_unavailable_cycles = 5

        # Mock successful ICMP measurement
        with (
            patch.object(controller, "measure_rtt", return_value=25.0),
            patch.object(controller, "save_state"),
        ):
            controller.run_cycle()

        assert controller.icmp_unavailable_cycles == 0
        controller.logger.info.assert_called()

    def test_icmp_recovery_logs_message(self, controller):
        """Should log info message when ICMP recovers."""
        controller.icmp_unavailable_cycles = 3

        with (
            patch.object(controller, "measure_rtt", return_value=25.0),
            patch.object(controller, "save_state"),
        ):
            controller.run_cycle()

        # Check that info log was called with recovery message
        info_calls = [str(call) for call in controller.logger.info.call_args_list]
        recovery_logged = any("ICMP recovered" in str(call) for call in info_calls)
        assert recovery_logged, "Should log ICMP recovery message"

    def test_no_recovery_log_when_counter_zero(self, controller):
        """Should not log recovery when counter was already zero."""
        controller.icmp_unavailable_cycles = 0

        with (
            patch.object(controller, "measure_rtt", return_value=25.0),
            patch.object(controller, "save_state"),
        ):
            controller.run_cycle()

        # Check that no "ICMP recovered" message was logged
        info_calls = [str(call) for call in controller.logger.info.call_args_list]
        recovery_logged = any("ICMP recovered" in str(call) for call in info_calls)
        assert not recovery_logged, "Should not log recovery when counter was zero"


class TestApplyRateChangesIfNeeded:
    """Tests for WANController.apply_rate_changes_if_needed() method.

    Tests flash wear protection and rate limiting behavior:
    - Unchanged rates skip router call
    - Changed rates call router
    - Rate limiting throttles updates
    - Router failure returns False
    - Success updates tracking state
    """

    @pytest.fixture
    def mock_config(self, mock_autorate_config):
        """Delegate to shared mock_autorate_config from conftest.py."""
        return mock_autorate_config

    @pytest.fixture
    def mock_router(self):
        """Create a mock router."""
        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = True
        router.rate_limit_params = {"max_changes": 5, "window_seconds": 10}
        return router

    @pytest.fixture
    def mock_rtt_measurement(self):
        """Create a mock RTT measurement."""
        return MagicMock()

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def controller(self, mock_config, mock_router, mock_rtt_measurement, mock_logger):
        """Create a WANController with mocked dependencies."""
        from wanctl.wan_controller import WANController

        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=mock_router,
                rtt_measurement=mock_rtt_measurement,
                logger=mock_logger,
            )
        return controller

    # =========================================================================
    # Flash wear protection tests
    # =========================================================================

    def test_unchanged_rates_skip_router_call(self, controller, mock_router):
        """Flash wear protection: unchanged rates should not call router."""
        controller.last_applied_dl_rate = 100_000_000
        controller.last_applied_ul_rate = 20_000_000

        result = controller.apply_rate_changes_if_needed(100_000_000, 20_000_000)

        assert result is True
        assert mock_router.set_limits.call_count == 0
        controller.logger.debug.assert_called()

    def test_changed_dl_rate_calls_router(self, controller, mock_router):
        """Changed download rate should call router."""
        controller.last_applied_dl_rate = 100_000_000
        controller.last_applied_ul_rate = 20_000_000

        result = controller.apply_rate_changes_if_needed(90_000_000, 20_000_000)

        assert result is True
        mock_router.set_limits.assert_called_once_with(
            wan="TestWAN", down_bps=90_000_000, up_bps=20_000_000
        )

    def test_changed_ul_rate_calls_router(self, controller, mock_router):
        """Changed upload rate should call router."""
        controller.last_applied_dl_rate = 100_000_000
        controller.last_applied_ul_rate = 20_000_000

        result = controller.apply_rate_changes_if_needed(100_000_000, 18_000_000)

        assert result is True
        mock_router.set_limits.assert_called_once_with(
            wan="TestWAN", down_bps=100_000_000, up_bps=18_000_000
        )

    def test_both_rates_changed_calls_router(self, controller, mock_router):
        """Changed both rates should call router."""
        controller.last_applied_dl_rate = 100_000_000
        controller.last_applied_ul_rate = 20_000_000

        result = controller.apply_rate_changes_if_needed(90_000_000, 18_000_000)

        assert result is True
        mock_router.set_limits.assert_called_once()

    def test_none_last_applied_calls_router(self, controller, mock_router):
        """None as last_applied should call router (first update)."""
        controller.last_applied_dl_rate = None
        controller.last_applied_ul_rate = None

        result = controller.apply_rate_changes_if_needed(100_000_000, 20_000_000)

        assert result is True
        mock_router.set_limits.assert_called_once()

    # =========================================================================
    # Rate limiting tests
    # =========================================================================

    def test_rate_limited_skips_router_saves_state(self, controller, mock_router):
        """Rate limit exceeded should skip router but save state."""
        controller.last_applied_dl_rate = 100_000_000
        controller.last_applied_ul_rate = 20_000_000
        # Replace rate_limiter with a mock
        mock_rate_limiter = MagicMock()
        mock_rate_limiter.can_change.return_value = False
        mock_rate_limiter.time_until_available.return_value = 5.0
        controller.rate_limiter = mock_rate_limiter

        with patch.object(controller, "save_state") as mock_save:
            result = controller.apply_rate_changes_if_needed(90_000_000, 18_000_000)

        assert result is True
        assert mock_router.set_limits.call_count == 0
        mock_save.assert_called_once()
        controller.logger.debug.assert_called()  # Rate limit logged at DEBUG level

    def test_rate_limited_records_metric_when_enabled(self, controller, mock_router):
        """Rate limiting should record metric when metrics enabled."""
        controller.config.metrics_enabled = True
        controller.last_applied_dl_rate = 100_000_000
        controller.last_applied_ul_rate = 20_000_000
        # Replace rate_limiter with a mock
        mock_rate_limiter = MagicMock()
        mock_rate_limiter.can_change.return_value = False
        mock_rate_limiter.time_until_available.return_value = 5.0
        controller.rate_limiter = mock_rate_limiter

        with (
            patch.object(controller, "save_state"),
            patch("wanctl.wan_controller.record_rate_limit_event") as mock_metric,
        ):
            result = controller.apply_rate_changes_if_needed(90_000_000, 18_000_000)

        assert result is True
        mock_metric.assert_called_once_with("TestWAN")

    def test_rate_limited_no_metric_when_disabled(self, controller, mock_router):
        """Rate limiting should not record metric when metrics disabled."""
        controller.config.metrics_enabled = False
        controller.last_applied_dl_rate = 100_000_000
        controller.last_applied_ul_rate = 20_000_000
        # Replace rate_limiter with a mock
        mock_rate_limiter = MagicMock()
        mock_rate_limiter.can_change.return_value = False
        mock_rate_limiter.time_until_available.return_value = 5.0
        controller.rate_limiter = mock_rate_limiter

        with (
            patch.object(controller, "save_state"),
            patch("wanctl.wan_controller.record_rate_limit_event") as mock_metric,
        ):
            result = controller.apply_rate_changes_if_needed(90_000_000, 18_000_000)

        assert result is True
        mock_metric.assert_not_called()

    # =========================================================================
    # Router failure tests
    # =========================================================================

    def test_router_failure_returns_false(self, controller, mock_router):
        """Router.set_limits failure should return False."""
        controller.last_applied_dl_rate = 100_000_000
        controller.last_applied_ul_rate = 20_000_000
        mock_router.set_limits.return_value = False

        result = controller.apply_rate_changes_if_needed(90_000_000, 18_000_000)

        assert result is False
        controller.logger.error.assert_called()

    def test_router_failure_does_not_update_tracking(self, controller, mock_router):
        """Router failure should not update last_applied tracking."""
        controller.last_applied_dl_rate = 100_000_000
        controller.last_applied_ul_rate = 20_000_000
        mock_router.set_limits.return_value = False

        controller.apply_rate_changes_if_needed(90_000_000, 18_000_000)

        # Tracking should remain unchanged
        assert controller.last_applied_dl_rate == 100_000_000
        assert controller.last_applied_ul_rate == 20_000_000

    # =========================================================================
    # Success tracking tests
    # =========================================================================

    def test_success_updates_tracking(self, controller, mock_router):
        """Successful update should track last_applied rates."""
        controller.last_applied_dl_rate = 100_000_000
        controller.last_applied_ul_rate = 20_000_000

        result = controller.apply_rate_changes_if_needed(90_000_000, 18_000_000)

        assert result is True
        assert controller.last_applied_dl_rate == 90_000_000
        assert controller.last_applied_ul_rate == 18_000_000

    def test_success_records_change_with_rate_limiter(self, controller, mock_router):
        """Successful update should record change with rate limiter."""
        controller.last_applied_dl_rate = 100_000_000
        controller.last_applied_ul_rate = 20_000_000
        # Replace rate_limiter with a mock to verify record_change is called
        mock_rate_limiter = MagicMock()
        mock_rate_limiter.can_change.return_value = True
        controller.rate_limiter = mock_rate_limiter

        controller.apply_rate_changes_if_needed(90_000_000, 18_000_000)

        mock_rate_limiter.record_change.assert_called_once()

    def test_success_records_metric_when_enabled(self, controller, mock_router):
        """Successful update should record router_update metric when enabled."""
        controller.config.metrics_enabled = True
        controller.last_applied_dl_rate = 100_000_000
        controller.last_applied_ul_rate = 20_000_000

        with patch("wanctl.wan_controller.record_router_update") as mock_metric:
            controller.apply_rate_changes_if_needed(90_000_000, 18_000_000)

        mock_metric.assert_called_once_with("TestWAN")

    def test_success_no_metric_when_disabled(self, controller, mock_router):
        """Successful update should not record metric when disabled."""
        controller.config.metrics_enabled = False
        controller.last_applied_dl_rate = 100_000_000
        controller.last_applied_ul_rate = 20_000_000

        with patch("wanctl.wan_controller.record_router_update") as mock_metric:
            controller.apply_rate_changes_if_needed(90_000_000, 18_000_000)

        mock_metric.assert_not_called()

    # =========================================================================
    # Transport-aware rate limiter tests (Phase 151)
    # =========================================================================

    def test_linux_cake_no_rate_limiter_created(self, mock_config, mock_rtt_measurement, mock_logger):
        """Controller with needs_rate_limiting=False should have rate_limiter=None."""
        from wanctl.wan_controller import WANController

        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = False
        router.rate_limit_params = {}

        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=router,
                rtt_measurement=mock_rtt_measurement,
                logger=mock_logger,
            )

        assert controller.rate_limiter is None

    def test_linux_cake_every_cycle_applies(self, mock_config, mock_rtt_measurement, mock_logger):
        """Controller with rate_limiter=None applies every rate change (no throttling)."""
        from wanctl.wan_controller import WANController

        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = False
        router.rate_limit_params = {}

        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=router,
                rtt_measurement=mock_rtt_measurement,
                logger=mock_logger,
            )

        controller.last_applied_dl_rate = 100_000_000
        controller.last_applied_ul_rate = 20_000_000

        result = controller.apply_rate_changes_if_needed(90_000_000, 18_000_000)

        assert result is True
        router.set_limits.assert_called_once()

    def test_linux_cake_flash_wear_still_works(self, mock_config, mock_rtt_measurement, mock_logger):
        """Controller with rate_limiter=None still skips identical rates (RATE-04)."""
        from wanctl.wan_controller import WANController

        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = False
        router.rate_limit_params = {}

        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=router,
                rtt_measurement=mock_rtt_measurement,
                logger=mock_logger,
            )

        controller.last_applied_dl_rate = 100_000_000
        controller.last_applied_ul_rate = 20_000_000

        result = controller.apply_rate_changes_if_needed(100_000_000, 20_000_000)

        assert result is True
        router.set_limits.assert_not_called()

    def test_rest_rate_limiter_uses_backend_params(
        self, mock_config, mock_rtt_measurement, mock_logger
    ):
        """Controller with needs_rate_limiting=True uses backend's rate_limit_params."""
        from wanctl.wan_controller import WANController

        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = True
        router.rate_limit_params = {"max_changes": 3, "window_seconds": 5}

        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=router,
                rtt_measurement=mock_rtt_measurement,
                logger=mock_logger,
            )

        assert controller.rate_limiter is not None
        assert controller.rate_limiter.max_changes == 3
        assert controller.rate_limiter.window_seconds == 5

    def test_linux_cake_no_rate_limit_metric(
        self, mock_config, mock_rtt_measurement, mock_logger
    ):
        """Controller with rate_limiter=None never records rate_limit_event."""
        from wanctl.wan_controller import WANController

        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = False
        router.rate_limit_params = {}

        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=router,
                rtt_measurement=mock_rtt_measurement,
                logger=mock_logger,
            )

        controller.config.metrics_enabled = True
        controller.last_applied_dl_rate = None
        controller.last_applied_ul_rate = None

        with patch("wanctl.wan_controller.record_rate_limit_event") as mock_metric:
            # Apply multiple changes rapidly -- no throttling since no rate limiter
            for i in range(20):
                controller.apply_rate_changes_if_needed(
                    (80 + i) * 1_000_000, 18_000_000
                )

        mock_metric.assert_not_called()

    def test_linux_cake_apply_does_not_call_record_change(
        self, mock_config, mock_rtt_measurement, mock_logger
    ):
        """Successful apply with rate_limiter=None does not call record_change."""
        from wanctl.wan_controller import WANController

        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = False
        router.rate_limit_params = {}

        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=router,
                rtt_measurement=mock_rtt_measurement,
                logger=mock_logger,
            )

        controller.last_applied_dl_rate = 100_000_000
        controller.last_applied_ul_rate = 20_000_000

        # Should not raise AttributeError
        result = controller.apply_rate_changes_if_needed(90_000_000, 18_000_000)
        assert result is True
        # rate_limiter is None, so no record_change call possible
        assert controller.rate_limiter is None

    def test_linux_cake_apply_updates_tracking(
        self, mock_config, mock_rtt_measurement, mock_logger
    ):
        """Successful apply with rate_limiter=None still updates last_applied tracking."""
        from wanctl.wan_controller import WANController

        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = False
        router.rate_limit_params = {}

        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=router,
                rtt_measurement=mock_rtt_measurement,
                logger=mock_logger,
            )

        controller.last_applied_dl_rate = 100_000_000
        controller.last_applied_ul_rate = 20_000_000

        result = controller.apply_rate_changes_if_needed(90_000_000, 18_000_000)

        assert result is True
        assert controller.last_applied_dl_rate == 90_000_000
        assert controller.last_applied_ul_rate == 18_000_000

    def test_linux_cake_apply_uses_actual_applied_rates_when_router_exposes_them(
        self, mock_config, mock_rtt_measurement, mock_logger
    ):
        """Tracking should follow the kernel-applied rates, not only requested rates."""
        from wanctl.wan_controller import WANController

        class FakeLinuxCakeRouter:
            needs_rate_limiting = False
            rate_limit_params = {}

            def __init__(self):
                self.set_limits = MagicMock(return_value=True)

            def get_last_applied_limits(self):
                return (100_000_000, 18_000_000)

        router = FakeLinuxCakeRouter()

        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=router,
                rtt_measurement=mock_rtt_measurement,
                logger=mock_logger,
            )

        controller.last_applied_dl_rate = 100_000_000
        controller.last_applied_ul_rate = 18_000_000

        result = controller.apply_rate_changes_if_needed(105_000_000, 18_000_000)

        assert result is True
        assert controller.last_applied_dl_rate == 100_000_000
        assert controller.last_applied_ul_rate == 18_000_000


class TestUpdateBaselineIfIdle:
    """Tests for WANController._update_baseline_if_idle() baseline protection.

    These tests validate the PROTECTED ZONE invariant: baseline RTT only updates
    when the line is idle (delta < threshold). This prevents baseline drift under
    load, which would mask true bloat detection.
    """

    @pytest.fixture
    def mock_config(self, mock_autorate_config):
        """Delegate to shared mock_autorate_config from conftest.py."""
        return mock_autorate_config

    @pytest.fixture
    def mock_router(self):
        """Create a mock router."""
        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = True
        router.rate_limit_params = {"max_changes": 5, "window_seconds": 10}
        return router

    @pytest.fixture
    def mock_rtt_measurement(self):
        """Create a mock RTT measurement."""
        return MagicMock()

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def controller(self, mock_config, mock_router, mock_rtt_measurement, mock_logger):
        """Create a WANController with mocked dependencies."""
        from wanctl.wan_controller import WANController

        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=mock_router,
                rtt_measurement=mock_rtt_measurement,
                logger=mock_logger,
            )
        return controller

    # =========================================================================
    # Baseline update behavior tests
    # =========================================================================

    def test_baseline_updates_when_idle(self, controller):
        """Baseline should update when delta < threshold (idle)."""
        controller.baseline_rtt = 20.0
        controller.load_rtt = 21.0  # delta = 1ms
        controller.baseline_update_threshold = 3.0
        controller.alpha_baseline = 0.1  # 10% weight for visible change

        controller._update_baseline_if_idle(22.0)

        # Baseline should have moved toward measured_rtt
        assert controller.baseline_rtt > 20.0

    def test_baseline_freezes_under_load(self, controller):
        """Baseline should NOT update when delta >= threshold (under load)."""
        controller.baseline_rtt = 20.0
        controller.load_rtt = 25.0  # delta = 5ms
        controller.baseline_update_threshold = 3.0

        original_baseline = controller.baseline_rtt
        controller._update_baseline_if_idle(30.0)

        # Baseline should NOT change
        assert controller.baseline_rtt == original_baseline

    def test_baseline_freeze_prevents_drift(self, controller):
        """Simulated load scenario: baseline must not drift toward load."""
        controller.baseline_rtt = 20.0
        controller.load_rtt = 20.0
        controller.baseline_update_threshold = 3.0
        controller.alpha_baseline = 0.1  # 10% weight

        # Simulate 100 cycles under load
        for _ in range(100):
            # Load increases
            controller.load_rtt = 50.0  # High load RTT
            measured_rtt = 55.0  # Even higher measurement

            # Update EWMA (full method to test integration)
            controller.update_ewma(measured_rtt)

        # Baseline should NOT have drifted significantly toward load
        # With delta > threshold, baseline freezes at original value
        assert controller.baseline_rtt == pytest.approx(20.0, abs=0.1)

    def test_threshold_boundary_exact_equal(self, controller):
        """Edge case: delta exactly equals threshold."""
        controller.baseline_rtt = 20.0
        controller.load_rtt = 23.0  # delta = 3ms exactly
        controller.baseline_update_threshold = 3.0

        original_baseline = controller.baseline_rtt
        controller._update_baseline_if_idle(25.0)

        # delta >= threshold should freeze (not update)
        assert controller.baseline_rtt == original_baseline

    def test_baseline_logs_on_update(self, controller):
        """Should log debug message when baseline updates."""
        controller.baseline_rtt = 20.0
        controller.load_rtt = 20.5  # delta = 0.5ms (idle)
        controller.baseline_update_threshold = 3.0

        controller._update_baseline_if_idle(21.0)

        # Verify debug was called with baseline update message
        controller.logger.debug.assert_called_once()
        call_args = controller.logger.debug.call_args[0][0]
        assert "Baseline updated" in call_args
        assert "20.00ms" in call_args  # old baseline


class TestDualFallbackFailure:
    """Tests for dual fallback failure scenarios (ICMP + TCP both down).

    Verifies TEST-05 requirement: Dual fallback failure returns safe defaults,
    not stale data. When both ICMP pings and TCP connectivity checks fail,
    the controller must return (False, None) to signal total connectivity loss
    rather than using stale load_rtt values.

    "Safe defaults" = (False, None) - don't continue cycle, no RTT measurement
    "Stale data" = using self.load_rtt when connectivity is actually lost
    """

    @pytest.fixture
    def mock_config(self, mock_autorate_config):
        """Delegate to shared mock_autorate_config from conftest.py."""
        return mock_autorate_config

    @pytest.fixture
    def mock_router(self):
        """Create a mock router."""
        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = True
        router.rate_limit_params = {"max_changes": 5, "window_seconds": 10}
        return router

    @pytest.fixture
    def mock_rtt_measurement(self):
        """Create a mock RTT measurement."""
        return MagicMock()

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def controller(self, mock_config, mock_router, mock_rtt_measurement, mock_logger):
        """Create a WANController with mocked dependencies."""
        from wanctl.wan_controller import WANController

        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=mock_router,
                rtt_measurement=mock_rtt_measurement,
                logger=mock_logger,
            )
        return controller

    def test_dual_failure_returns_safe_defaults_not_stale_data(self, controller):
        """Dual fallback failure returns (False, None), not stale load_rtt.

        When both ICMP and TCP fail (total connectivity loss), the controller
        must return safe defaults (False, None) rather than the stale load_rtt
        value. This prevents acting on outdated RTT data when connectivity
        is actually lost.
        """
        # Set a stale load_rtt value that should NOT be returned
        controller.load_rtt = 28.5
        controller.icmp_unavailable_cycles = 0

        # Mock dual failure - both ICMP and TCP fail
        with patch.object(controller, "verify_connectivity_fallback", return_value=(False, None)):
            should_continue, measured_rtt = controller.handle_icmp_failure()

        # Safe defaults: (False, None) - NOT (True, 28.5)
        assert should_continue is False, "Cycle should NOT continue on total connectivity loss"
        assert measured_rtt is None, "Measured RTT must be None, NOT stale load_rtt (28.5)"

    @pytest.mark.parametrize(
        "mode,stale_rtt",
        [
            ("graceful_degradation", 28.5),
            ("freeze", 35.0),
            ("use_last_rtt", 42.1),
        ],
    )
    def test_dual_failure_safe_across_all_fallback_modes(self, controller, mode, stale_rtt):
        """Dual failure returns (False, None) regardless of fallback mode.

        All fallback modes must return safe defaults on total connectivity loss.
        The mode-specific behavior only applies when connectivity exists but
        ICMP is filtered. Total loss always returns (False, None).
        """
        controller.config.fallback_mode = mode
        controller.load_rtt = stale_rtt  # Distinct stale value per mode
        controller.icmp_unavailable_cycles = 0

        with patch.object(controller, "verify_connectivity_fallback", return_value=(False, None)):
            should_continue, measured_rtt = controller.handle_icmp_failure()

        assert should_continue is False, f"Mode '{mode}' must return False on total loss"
        assert measured_rtt is None, f"Mode '{mode}' must return None, not stale RTT ({stale_rtt})"

    def test_dual_failure_does_not_increment_cycle_counter(self, controller):
        """Total connectivity loss should NOT increment icmp_unavailable_cycles.

        The cycle counter is for tracking ICMP-unavailable-but-connected states.
        Total connectivity loss is a different condition - the counter should
        remain unchanged because we're not in a "degraded but working" state.
        """
        controller.config.fallback_mode = "graceful_degradation"
        controller.icmp_unavailable_cycles = 0
        controller.load_rtt = 28.5

        with patch.object(controller, "verify_connectivity_fallback", return_value=(False, None)):
            controller.handle_icmp_failure()

        assert controller.icmp_unavailable_cycles == 0, "Counter should NOT increment on total loss"

    def test_dual_failure_logs_warning(self, controller):
        """Total connectivity loss should log a warning."""
        controller.config.fallback_mode = "graceful_degradation"
        controller.icmp_unavailable_cycles = 0
        controller.load_rtt = 28.5

        with patch.object(controller, "verify_connectivity_fallback", return_value=(False, None)):
            controller.handle_icmp_failure()

        # Warning should be logged for total connectivity loss
        controller.logger.warning.assert_called()


class TestIcmpRecoveryExtended:
    """Extended ICMP recovery tests for run_cycle integration."""

    @pytest.fixture
    def mock_config(self, mock_autorate_config):
        """Delegate to shared mock_autorate_config from conftest.py."""
        return mock_autorate_config

    @pytest.fixture
    def mock_router(self):
        """Create a mock router."""
        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = True
        router.rate_limit_params = {"max_changes": 5, "window_seconds": 10}
        return router

    @pytest.fixture
    def mock_rtt_measurement(self):
        """Create a mock RTT measurement."""
        return MagicMock()

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def controller(self, mock_config, mock_router, mock_rtt_measurement, mock_logger):
        """Create a WANController with mocked dependencies."""
        from wanctl.wan_controller import WANController

        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=mock_router,
                rtt_measurement=mock_rtt_measurement,
                logger=mock_logger,
            )
        return controller

    def test_run_cycle_with_successful_rtt(self, controller, mock_router):
        """Full cycle should succeed with valid RTT measurement."""
        with (
            patch.object(controller, "measure_rtt", return_value=25.0),
            patch.object(controller, "save_state"),
        ):
            result = controller.run_cycle()

        assert result is True
        mock_router.set_limits.assert_called()

    def test_run_cycle_state_transition_logged(self, controller, mock_logger):
        """Cycle log should contain zone and rates."""
        with (
            patch.object(controller, "measure_rtt", return_value=25.0),
            patch.object(controller, "save_state"),
        ):
            controller.run_cycle()

        debug_calls = [str(call) for call in mock_logger.debug.call_args_list]
        assert any("DL=" in call and "UL=" in call for call in debug_calls)


class TestRunCycleMetrics:
    """Tests for run_cycle metrics recording."""

    @pytest.fixture
    def mock_config(self, mock_autorate_config):
        """Delegate to shared mock_autorate_config with metrics enabled."""
        mock_autorate_config.metrics_enabled = True
        return mock_autorate_config

    @pytest.fixture
    def mock_router(self):
        """Create a mock router."""
        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = True
        router.rate_limit_params = {"max_changes": 5, "window_seconds": 10}
        return router

    @pytest.fixture
    def mock_rtt_measurement(self):
        """Create a mock RTT measurement."""
        return MagicMock()

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def controller(self, mock_config, mock_router, mock_rtt_measurement, mock_logger):
        """Create a WANController with mocked dependencies."""
        from wanctl.wan_controller import WANController

        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=mock_router,
                rtt_measurement=mock_rtt_measurement,
                logger=mock_logger,
            )
        return controller

    def test_run_cycle_records_metrics_when_enabled(self, controller):
        """record_autorate_cycle should be called when metrics are enabled."""
        with (
            patch.object(controller, "measure_rtt", return_value=25.0),
            patch.object(controller, "save_state"),
            patch("wanctl.wan_controller.record_autorate_cycle") as mock_record,
        ):
            result = controller.run_cycle()

        assert result is True
        mock_record.assert_called_once()
        # Verify it was called with expected params
        call_kwargs = mock_record.call_args.kwargs
        assert call_kwargs["wan_name"] == "TestWAN"
        assert "dl_rate_mbps" in call_kwargs
        assert "ul_rate_mbps" in call_kwargs
        assert "baseline_rtt" in call_kwargs
        assert "load_rtt" in call_kwargs

    def test_run_cycle_skips_metrics_when_disabled(self, controller, mock_config):
        """record_autorate_cycle should NOT be called when metrics are disabled."""
        mock_config.metrics_enabled = False

        with (
            patch.object(controller, "measure_rtt", return_value=25.0),
            patch.object(controller, "save_state"),
            patch("wanctl.wan_controller.record_autorate_cycle") as mock_record,
        ):
            result = controller.run_cycle()

        assert result is True
        mock_record.assert_not_called()


class TestVerifyLocalConnectivity:
    """Tests for WANController.verify_local_connectivity() method.

    Covers lines 978-989:
    - Gateway check disabled returns False immediately
    - Gateway reachable returns True with warning
    - Gateway unreachable returns False
    """

    @pytest.fixture
    def controller_with_mocks(self):
        """Create a WANController with all dependencies accessible."""
        from wanctl.wan_controller import WANController

        config = MagicMock()
        config.wan_name = "TestWAN"
        config.baseline_rtt_initial = 25.0
        config.download_floor_green = 800_000_000
        config.download_floor_yellow = 600_000_000
        config.download_floor_soft_red = 500_000_000
        config.download_floor_red = 400_000_000
        config.download_ceiling = 920_000_000
        config.download_step_up = 10_000_000
        config.download_factor_down = 0.85
        config.upload_floor_green = 35_000_000
        config.upload_floor_yellow = 30_000_000
        config.upload_floor_red = 25_000_000
        config.upload_ceiling = 40_000_000
        config.upload_step_up = 1_000_000
        config.upload_factor_down = 0.85
        config.target_bloat_ms = 15.0
        config.warn_bloat_ms = 45.0
        config.hard_red_bloat_ms = 80.0
        config.alpha_baseline = 0.001
        config.alpha_load = 0.1
        config.baseline_update_threshold_ms = 3.0
        config.baseline_rtt_min = 10.0
        config.baseline_rtt_max = 60.0
        config.accel_threshold_ms = 15.0
        config.accel_confirm_cycles = 3
        config.download_green_required = 5
        config.upload_green_required = 5
        config.ping_hosts = ["1.1.1.1"]
        config.use_median_of_three = False
        config.fallback_enabled = True
        config.fallback_check_gateway = True
        config.fallback_check_tcp = True
        config.fallback_gateway_ip = "10.0.0.1"
        config.fallback_tcp_targets = [["1.1.1.1", 443], ["8.8.8.8", 443]]
        config.fallback_mode = "graceful_degradation"
        config.fallback_max_cycles = 3
        config.metrics_enabled = False
        config.cake_stats_cadence_sec = 0.05
        config.state_file = MagicMock()
        config.alerting_config = None
        config.signal_processing_config = {
            "hampel_window_size": 7,
            "hampel_sigma_threshold": 3.0,
            "jitter_time_constant_sec": 2.0,
            "variance_time_constant_sec": 5.0,
        }
        config.reflector_quality_config = {
            "min_score": 0.8,
            "window_size": 50,
            "probe_interval_sec": 30.0,
            "recovery_count": 3,
        }
        config.cake_stats_cadence_sec = 0.05

        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = True
        router.rate_limit_params = {"max_changes": 5, "window_seconds": 10}
        rtt_measurement = MagicMock()
        logger = MagicMock()

        with patch.object(WANController, "load_state"):
            ctrl = WANController(
                wan_name="TestWAN",
                config=config,
                router=router,
                rtt_measurement=rtt_measurement,
                logger=logger,
            )
        return ctrl, config, logger

    def test_gateway_check_disabled_returns_false(self, controller_with_mocks):
        """When fallback_check_gateway=False, returns False immediately."""
        ctrl, config, _ = controller_with_mocks
        config.fallback_check_gateway = False

        result = ctrl.verify_local_connectivity()

        assert result is False
        # ping_host should NOT have been called
        ctrl.rtt_measurement.ping_host.assert_not_called()

    def test_gateway_reachable_returns_true_with_warning(self, controller_with_mocks):
        """When gateway is reachable, returns True and logs warning."""
        ctrl, config, logger = controller_with_mocks
        config.fallback_check_gateway = True
        config.fallback_gateway_ip = "10.0.0.1"
        ctrl.rtt_measurement.ping_host.return_value = 5.0  # Success

        result = ctrl.verify_local_connectivity()

        assert result is True
        ctrl.rtt_measurement.ping_host.assert_called_once_with("10.0.0.1", count=1)
        # Verify warning logged
        logger.warning.assert_called_once()
        warning_msg = logger.warning.call_args[0][0]
        assert "gateway" in warning_msg.lower()
        assert "10.0.0.1" in warning_msg
        assert "reachable" in warning_msg.lower()

    def test_gateway_unreachable_returns_false(self, controller_with_mocks):
        """When gateway is unreachable, returns False."""
        ctrl, config, logger = controller_with_mocks
        config.fallback_check_gateway = True
        config.fallback_gateway_ip = "10.0.0.1"
        ctrl.rtt_measurement.ping_host.return_value = None  # Failure

        result = ctrl.verify_local_connectivity()

        assert result is False
        ctrl.rtt_measurement.ping_host.assert_called_once()
        # No warning should be logged for unreachable
        logger.warning.assert_not_called()

    def test_empty_gateway_ip_returns_false_without_ping(self, controller_with_mocks):
        """When fallback_gateway_ip is empty string, returns False and skips ping."""
        ctrl, config, _ = controller_with_mocks
        config.fallback_check_gateway = True
        config.fallback_gateway_ip = ""

        result = ctrl.verify_local_connectivity()

        assert result is False
        ctrl.rtt_measurement.ping_host.assert_not_called()


class TestVerifyTcpConnectivity:
    """Tests for WANController.verify_tcp_connectivity() method.

    Covers lines 1004-1028:
    - TCP check disabled returns (False, None)
    - All TCP targets succeed returns (True, median_rtt)
    - Partial TCP success returns (True, single_rtt)
    - All TCP fail returns (False, None)
    """

    @pytest.fixture
    def controller_with_mocks(self):
        """Create a WANController with all dependencies accessible."""
        from wanctl.wan_controller import WANController

        config = MagicMock()
        config.wan_name = "TestWAN"
        config.baseline_rtt_initial = 25.0
        config.download_floor_green = 800_000_000
        config.download_floor_yellow = 600_000_000
        config.download_floor_soft_red = 500_000_000
        config.download_floor_red = 400_000_000
        config.download_ceiling = 920_000_000
        config.download_step_up = 10_000_000
        config.download_factor_down = 0.85
        config.upload_floor_green = 35_000_000
        config.upload_floor_yellow = 30_000_000
        config.upload_floor_red = 25_000_000
        config.upload_ceiling = 40_000_000
        config.upload_step_up = 1_000_000
        config.upload_factor_down = 0.85
        config.target_bloat_ms = 15.0
        config.warn_bloat_ms = 45.0
        config.hard_red_bloat_ms = 80.0
        config.alpha_baseline = 0.001
        config.alpha_load = 0.1
        config.baseline_update_threshold_ms = 3.0
        config.baseline_rtt_min = 10.0
        config.baseline_rtt_max = 60.0
        config.accel_threshold_ms = 15.0
        config.accel_confirm_cycles = 3
        config.download_green_required = 5
        config.upload_green_required = 5
        config.ping_hosts = ["1.1.1.1"]
        config.use_median_of_three = False
        config.fallback_enabled = True
        config.fallback_check_gateway = True
        config.fallback_check_tcp = True
        config.fallback_gateway_ip = "10.0.0.1"
        config.fallback_tcp_targets = [("1.1.1.1", 443), ("8.8.8.8", 443)]
        config.fallback_mode = "graceful_degradation"
        config.fallback_max_cycles = 3
        config.metrics_enabled = False
        config.cake_stats_cadence_sec = 0.05
        config.state_file = MagicMock()
        config.alerting_config = None
        config.signal_processing_config = {
            "hampel_window_size": 7,
            "hampel_sigma_threshold": 3.0,
            "jitter_time_constant_sec": 2.0,
            "variance_time_constant_sec": 5.0,
        }
        config.reflector_quality_config = {
            "min_score": 0.8,
            "window_size": 50,
            "probe_interval_sec": 30.0,
            "recovery_count": 3,
        }

        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = True
        router.rate_limit_params = {"max_changes": 5, "window_seconds": 10}
        rtt_measurement = MagicMock()
        logger = MagicMock()

        with patch.object(WANController, "load_state"):
            ctrl = WANController(
                wan_name="TestWAN",
                config=config,
                router=router,
                rtt_measurement=rtt_measurement,
                logger=logger,
            )
        return ctrl, config, logger

    def test_tcp_check_disabled_returns_false_none(self, controller_with_mocks):
        """When fallback_check_tcp=False, returns (False, None) immediately."""
        ctrl, config, _ = controller_with_mocks
        config.fallback_check_tcp = False

        result = ctrl.verify_tcp_connectivity()

        assert result == (False, None)

    def test_all_tcp_targets_succeed(self, controller_with_mocks):
        """When all TCP targets succeed, returns (True, median_rtt)."""
        ctrl, config, logger = controller_with_mocks
        config.fallback_check_tcp = True
        config.fallback_tcp_targets = [("1.1.1.1", 443), ("8.8.8.8", 443)]

        # Mock socket.create_connection to succeed with timing
        mock_socket = MagicMock()
        call_count = [0]
        times = [0.0, 0.020, 0.020, 0.050]  # start, end1, start2, end2

        def monotonic_side_effect():
            idx = call_count[0]
            call_count[0] += 1
            return times[idx] if idx < len(times) else times[-1]

        with (
            patch("socket.create_connection", return_value=mock_socket),
            patch("time.monotonic", side_effect=monotonic_side_effect),
        ):
            result = ctrl.verify_tcp_connectivity()

        # Both succeed: RTTs are 20ms and 30ms, median = 25ms
        assert result[0] is True
        assert result[1] is not None
        assert result[1] > 0  # Should have an RTT
        logger.info.assert_called()  # "TCP connectivity verified" logged

    def test_partial_tcp_success(self, controller_with_mocks):
        """When 1 of 2 TCP targets succeed, returns (True, single_rtt)."""
        ctrl, config, logger = controller_with_mocks
        config.fallback_check_tcp = True
        config.fallback_tcp_targets = [("1.1.1.1", 443), ("8.8.8.8", 443)]

        # First connection succeeds, second fails
        mock_socket = MagicMock()
        call_count = [0]

        def create_connection_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_socket
            raise TimeoutError("Connection timed out")

        # Use a generator function for time.monotonic that never runs out
        time_count = [0]
        times = [0.0, 0.025, 0.025, 0.030]  # Extra values for safety

        def monotonic_side_effect():
            idx = time_count[0]
            time_count[0] += 1
            return times[idx] if idx < len(times) else times[-1]

        with (
            patch("socket.create_connection", side_effect=create_connection_side_effect),
            patch("time.monotonic", side_effect=monotonic_side_effect),
        ):
            result = ctrl.verify_tcp_connectivity()

        assert result[0] is True
        assert result[1] is not None  # Single RTT from successful connection
        logger.info.assert_called()

    def test_all_tcp_fail(self, controller_with_mocks):
        """When all TCP connections fail, returns (False, None)."""
        ctrl, config, logger = controller_with_mocks
        config.fallback_check_tcp = True
        config.fallback_tcp_targets = [("1.1.1.1", 443), ("8.8.8.8", 443)]

        # All connections fail
        with patch("socket.create_connection", side_effect=OSError("Connection refused")):
            result = ctrl.verify_tcp_connectivity()

        assert result == (False, None)
        # Debug logged for each failure
        assert logger.debug.call_count >= 2


class TestVerifyConnectivityFallback:
    """Tests for WANController.verify_connectivity_fallback() method.

    Covers lines 1043-1077:
    - Fallback disabled returns (False, None)
    - TCP succeeds + gateway succeeds (ICMP filtering detected)
    - TCP succeeds + gateway fails
    - TCP fails + gateway succeeds (partial connectivity)
    - Both fail (total connectivity loss)
    """

    @pytest.fixture
    def controller_with_mocks(self):
        """Create a WANController with all dependencies accessible."""
        from wanctl.wan_controller import WANController

        config = MagicMock()
        config.wan_name = "TestWAN"
        config.baseline_rtt_initial = 25.0
        config.download_floor_green = 800_000_000
        config.download_floor_yellow = 600_000_000
        config.download_floor_soft_red = 500_000_000
        config.download_floor_red = 400_000_000
        config.download_ceiling = 920_000_000
        config.download_step_up = 10_000_000
        config.download_factor_down = 0.85
        config.upload_floor_green = 35_000_000
        config.upload_floor_yellow = 30_000_000
        config.upload_floor_red = 25_000_000
        config.upload_ceiling = 40_000_000
        config.upload_step_up = 1_000_000
        config.upload_factor_down = 0.85
        config.target_bloat_ms = 15.0
        config.warn_bloat_ms = 45.0
        config.hard_red_bloat_ms = 80.0
        config.alpha_baseline = 0.001
        config.alpha_load = 0.1
        config.baseline_update_threshold_ms = 3.0
        config.baseline_rtt_min = 10.0
        config.baseline_rtt_max = 60.0
        config.accel_threshold_ms = 15.0
        config.accel_confirm_cycles = 3
        config.download_green_required = 5
        config.upload_green_required = 5
        config.ping_hosts = ["1.1.1.1"]
        config.use_median_of_three = False
        config.fallback_enabled = True
        config.fallback_check_gateway = True
        config.fallback_check_tcp = True
        config.fallback_gateway_ip = "10.0.0.1"
        config.fallback_tcp_targets = [("1.1.1.1", 443), ("8.8.8.8", 443)]
        config.fallback_mode = "graceful_degradation"
        config.fallback_max_cycles = 3
        config.metrics_enabled = False
        config.cake_stats_cadence_sec = 0.05
        config.state_file = MagicMock()
        config.alerting_config = None
        config.signal_processing_config = {
            "hampel_window_size": 7,
            "hampel_sigma_threshold": 3.0,
            "jitter_time_constant_sec": 2.0,
            "variance_time_constant_sec": 5.0,
        }
        config.reflector_quality_config = {
            "min_score": 0.8,
            "window_size": 50,
            "probe_interval_sec": 30.0,
            "recovery_count": 3,
        }

        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = True
        router.rate_limit_params = {"max_changes": 5, "window_seconds": 10}
        rtt_measurement = MagicMock()
        logger = MagicMock()

        with patch.object(WANController, "load_state"):
            ctrl = WANController(
                wan_name="TestWAN",
                config=config,
                router=router,
                rtt_measurement=rtt_measurement,
                logger=logger,
            )
        return ctrl, config, logger

    def test_fallback_disabled_returns_false_none(self, controller_with_mocks):
        """When fallback_enabled=False, returns (False, None) immediately."""
        ctrl, config, _ = controller_with_mocks
        config.fallback_enabled = False

        result = ctrl.verify_connectivity_fallback()

        assert result == (False, None)

    def test_tcp_and_gateway_succeed_icmp_filtering(self, controller_with_mocks):
        """TCP + gateway succeed indicates ICMP filtering."""
        ctrl, config, logger = controller_with_mocks
        config.fallback_enabled = True

        with (
            patch.object(ctrl, "verify_local_connectivity", return_value=True),
            patch.object(ctrl, "verify_tcp_connectivity", return_value=(True, 25.0)),
        ):
            result = ctrl.verify_connectivity_fallback()

        assert result == (True, 25.0)
        # Should warn about ICMP filtering
        warning_calls = [str(call) for call in logger.warning.call_args_list]
        assert any("ICMP filtering" in call for call in warning_calls)

    def test_tcp_succeeds_gateway_fails(self, controller_with_mocks):
        """TCP succeeds + gateway fails returns (True, tcp_rtt)."""
        ctrl, config, logger = controller_with_mocks
        config.fallback_enabled = True

        with (
            patch.object(ctrl, "verify_local_connectivity", return_value=False),
            patch.object(ctrl, "verify_tcp_connectivity", return_value=(True, 25.0)),
        ):
            result = ctrl.verify_connectivity_fallback()

        assert result == (True, 25.0)

    def test_tcp_fails_gateway_succeeds_partial(self, controller_with_mocks):
        """TCP fails + gateway succeeds indicates partial connectivity."""
        ctrl, config, logger = controller_with_mocks
        config.fallback_enabled = True

        with (
            patch.object(ctrl, "verify_local_connectivity", return_value=True),
            patch.object(ctrl, "verify_tcp_connectivity", return_value=(False, None)),
        ):
            result = ctrl.verify_connectivity_fallback()

        assert result == (True, None)
        # Should warn about partial connectivity
        warning_calls = [str(call) for call in logger.warning.call_args_list]
        assert any("gateway reachable" in call for call in warning_calls)

    def test_both_fail_total_connectivity_loss(self, controller_with_mocks):
        """Both TCP and gateway fail indicates total connectivity loss."""
        ctrl, config, logger = controller_with_mocks
        config.fallback_enabled = True

        with (
            patch.object(ctrl, "verify_local_connectivity", return_value=False),
            patch.object(ctrl, "verify_tcp_connectivity", return_value=(False, None)),
        ):
            result = ctrl.verify_connectivity_fallback()

        assert result == (False, None)
        # Should log error about total loss
        logger.error.assert_called()
        error_msg = logger.error.call_args[0][0]
        assert "total connectivity loss" in error_msg.lower()


class TestStateLoadSave:
    """Tests for WANController.load_state() and save_state() methods.

    Covers lines 1330-1368:
    - load_state with full state dict restores all fields
    - load_state with partial state uses defaults for missing
    - save_state calls state_manager.save with correct structure
    - save_state with force=True passes force to state_manager
    """

    @pytest.fixture
    def controller_with_mocks(self):
        """Create a WANController with all dependencies accessible."""
        from wanctl.wan_controller import WANController

        config = MagicMock()
        config.wan_name = "TestWAN"
        config.baseline_rtt_initial = 25.0
        config.download_floor_green = 800_000_000
        config.download_floor_yellow = 600_000_000
        config.download_floor_soft_red = 500_000_000
        config.download_floor_red = 400_000_000
        config.download_ceiling = 920_000_000
        config.download_step_up = 10_000_000
        config.download_factor_down = 0.85
        config.upload_floor_green = 35_000_000
        config.upload_floor_yellow = 30_000_000
        config.upload_floor_red = 25_000_000
        config.upload_ceiling = 40_000_000
        config.upload_step_up = 1_000_000
        config.upload_factor_down = 0.85
        config.target_bloat_ms = 15.0
        config.warn_bloat_ms = 45.0
        config.hard_red_bloat_ms = 80.0
        config.alpha_baseline = 0.001
        config.alpha_load = 0.1
        config.baseline_update_threshold_ms = 3.0
        config.baseline_rtt_min = 10.0
        config.baseline_rtt_max = 60.0
        config.accel_threshold_ms = 15.0
        config.accel_confirm_cycles = 3
        config.download_green_required = 5
        config.upload_green_required = 5
        config.ping_hosts = ["1.1.1.1"]
        config.use_median_of_three = False
        config.fallback_enabled = True
        config.fallback_check_gateway = True
        config.fallback_check_tcp = True
        config.fallback_gateway_ip = "10.0.0.1"
        config.fallback_tcp_targets = [("1.1.1.1", 443), ("8.8.8.8", 443)]
        config.fallback_mode = "graceful_degradation"
        config.fallback_max_cycles = 3
        config.metrics_enabled = False
        config.cake_stats_cadence_sec = 0.05
        config.state_file = MagicMock()
        config.alerting_config = None
        config.signal_processing_config = {
            "hampel_window_size": 7,
            "hampel_sigma_threshold": 3.0,
            "jitter_time_constant_sec": 2.0,
            "variance_time_constant_sec": 5.0,
        }
        config.reflector_quality_config = {
            "min_score": 0.8,
            "window_size": 50,
            "probe_interval_sec": 30.0,
            "recovery_count": 3,
        }

        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = True
        router.rate_limit_params = {"max_changes": 5, "window_seconds": 10}
        rtt_measurement = MagicMock()
        logger = MagicMock()

        with patch.object(WANController, "load_state"):
            ctrl = WANController(
                wan_name="TestWAN",
                config=config,
                router=router,
                rtt_measurement=rtt_measurement,
                logger=logger,
            )
        # Replace state_manager with a mock for testing
        mock_state_manager = MagicMock()
        mock_state_manager.build_controller_state = MagicMock(
            side_effect=lambda g, s, r, c: {
                "green_streak": g,
                "soft_red_streak": s,
                "red_streak": r,
                "current_rate": c,
            }
        )
        ctrl.state_manager = mock_state_manager
        return ctrl, config, logger, mock_state_manager

    def test_load_state_full_state_dict(self, controller_with_mocks):
        """load_state with full state dict restores all fields."""
        ctrl, _, _, mock_state_manager = controller_with_mocks

        # Create full state dict
        full_state = {
            "download": {
                "green_streak": 5,
                "soft_red_streak": 2,
                "red_streak": 1,
                "current_rate": 750_000_000,
            },
            "upload": {
                "green_streak": 3,
                "soft_red_streak": 0,
                "red_streak": 0,
                "current_rate": 38_000_000,
            },
            "ewma": {
                "baseline_rtt": 22.5,
                "load_rtt": 28.0,
            },
            "last_applied": {
                "dl_rate": 750_000_000,
                "ul_rate": 38_000_000,
            },
        }
        mock_state_manager.load.return_value = full_state

        ctrl.load_state()

        # Verify download state restored
        assert ctrl.download.green_streak == 5
        assert ctrl.download.soft_red_streak == 2
        assert ctrl.download.red_streak == 1
        assert ctrl.download.current_rate == 750_000_000

        # Verify upload state restored
        assert ctrl.upload.green_streak == 3
        assert ctrl.upload.soft_red_streak == 0
        assert ctrl.upload.red_streak == 0
        assert ctrl.upload.current_rate == 38_000_000

        # Verify EWMA state restored
        assert ctrl.baseline_rtt == 22.5
        assert ctrl.load_rtt == 28.0

        # Verify last_applied state restored
        assert ctrl.last_applied_dl_rate == 750_000_000
        assert ctrl.last_applied_ul_rate == 38_000_000

    def test_load_state_partial_state_uses_defaults(self, controller_with_mocks):
        """load_state with partial state uses defaults for missing sections."""
        ctrl, _, _, mock_state_manager = controller_with_mocks

        # Set known initial values
        initial_baseline = ctrl.baseline_rtt
        initial_load = ctrl.load_rtt

        # Only provide download section
        partial_state = {
            "download": {
                "green_streak": 10,
                "current_rate": 700_000_000,
            },
        }
        mock_state_manager.load.return_value = partial_state

        ctrl.load_state()

        # Download should be partially restored
        assert ctrl.download.green_streak == 10
        assert ctrl.download.current_rate == 700_000_000

        # EWMA should remain at initial values (not in partial state)
        assert ctrl.baseline_rtt == initial_baseline
        assert ctrl.load_rtt == initial_load

    def test_load_state_none_state(self, controller_with_mocks):
        """load_state with None state does nothing."""
        ctrl, _, _, mock_state_manager = controller_with_mocks

        # Store initial values
        initial_baseline = ctrl.baseline_rtt
        initial_dl_rate = ctrl.download.current_rate

        mock_state_manager.load.return_value = None

        ctrl.load_state()

        # Values should remain unchanged
        assert ctrl.baseline_rtt == initial_baseline
        assert ctrl.download.current_rate == initial_dl_rate

    def test_save_state_calls_state_manager(self, controller_with_mocks):
        """save_state calls state_manager.save with correct structure."""
        ctrl, _, _, mock_state_manager = controller_with_mocks

        # Set some values
        ctrl.download.green_streak = 7
        ctrl.download.soft_red_streak = 1
        ctrl.download.red_streak = 0
        ctrl.download.current_rate = 850_000_000
        ctrl.upload.green_streak = 4
        ctrl.upload.soft_red_streak = 0
        ctrl.upload.red_streak = 0
        ctrl.upload.current_rate = 39_000_000
        ctrl.baseline_rtt = 23.0
        ctrl.load_rtt = 26.0
        ctrl.last_applied_dl_rate = 850_000_000
        ctrl.last_applied_ul_rate = 39_000_000

        ctrl.save_state()

        # Verify save was called
        mock_state_manager.save.assert_called_once()
        call_kwargs = mock_state_manager.save.call_args.kwargs

        # Verify structure
        assert "download" in call_kwargs
        assert "upload" in call_kwargs
        assert "ewma" in call_kwargs
        assert "last_applied" in call_kwargs
        assert call_kwargs["force"] is False

    def test_save_state_with_force_true(self, controller_with_mocks):
        """save_state with force=True passes force to state_manager."""
        ctrl, _, _, mock_state_manager = controller_with_mocks

        ctrl.save_state(force=True)

        mock_state_manager.save.assert_called_once()
        call_kwargs = mock_state_manager.save.call_args.kwargs
        assert call_kwargs["force"] is True

    def test_save_state_includes_congestion(self, controller_with_mocks):
        """save_state() passes congestion dict to state_manager.save()."""
        ctrl, _, _, mock_state_manager = controller_with_mocks

        ctrl.save_state()

        mock_state_manager.save.assert_called_once()
        call_kwargs = mock_state_manager.save.call_args.kwargs
        assert "congestion" in call_kwargs
        congestion = call_kwargs["congestion"]
        assert "dl_state" in congestion
        assert "ul_state" in congestion

    def test_save_state_congestion_uses_zone_attrs(self, controller_with_mocks):
        """save_state() congestion dict uses _dl_zone and _ul_zone attrs."""
        ctrl, _, _, mock_state_manager = controller_with_mocks

        ctrl._dl_zone = "RED"
        ctrl._ul_zone = "YELLOW"

        ctrl.save_state()

        call_kwargs = mock_state_manager.save.call_args.kwargs
        assert call_kwargs["congestion"]["dl_state"] == "RED"
        assert call_kwargs["congestion"]["ul_state"] == "YELLOW"

    def test_get_health_data_includes_live_measurement_snapshot(self, controller_with_mocks):
        """get_health_data exposes the latest direct ICMP RTT snapshot."""
        ctrl, _, _, _ = controller_with_mocks

        ctrl._last_raw_rtt = 21.75
        ctrl._last_raw_rtt_ts = 100.0
        ctrl._last_active_reflector_hosts = ["1.1.1.1", "9.9.9.9"]
        ctrl._last_successful_reflector_hosts = ["1.1.1.1"]
        ctrl._rtt_thread = MagicMock(spec=BackgroundRTTThread)
        ctrl._rtt_thread.cadence_sec = 0.25

        with patch("wanctl.wan_controller.time.monotonic", return_value=100.25):
            health = ctrl.get_health_data()

        measurement = health["measurement"]
        assert measurement["raw_rtt_ms"] == 21.75
        assert measurement["staleness_sec"] == 0.25
        assert measurement["active_reflector_hosts"] == ["1.1.1.1", "9.9.9.9"]
        assert measurement["successful_reflector_hosts"] == ["1.1.1.1"]
        assert measurement["cadence_sec"] == pytest.approx(0.25)

    def test_get_health_data_includes_background_worker_stats(self, controller_with_mocks):
        """get_health_data exposes async worker timing and staleness surfaces."""
        ctrl, _, _, _ = controller_with_mocks

        ctrl._last_raw_rtt_ts = 100.0
        ctrl._rtt_thread = MagicMock(spec=BackgroundRTTThread)
        ctrl._rtt_thread.cadence_sec = 0.25
        ctrl._rtt_thread.get_profile_stats.return_value = {
            "avg_ms": 12.34,
            "p95_ms": 20.0,
            "p99_ms": 25.0,
            "max_ms": 30.0,
        }
        ctrl._cake_stats_thread = MagicMock()
        ctrl._cake_stats_thread.get_profile_stats.return_value = {
            "avg_ms": 7.0,
            "p95_ms": 10.0,
            "p99_ms": 12.0,
            "max_ms": 15.0,
        }
        ctrl._cake_stats_thread.get_latest.return_value = MagicMock(timestamp=100.1)
        ctrl._irtt_thread = MagicMock()
        ctrl._irtt_thread.cadence_sec = 10.0
        ctrl._irtt_thread.get_profile_stats.return_value = {
            "avg_ms": 40.0,
            "p95_ms": 50.0,
            "p99_ms": 60.0,
            "max_ms": 80.0,
        }
        ctrl._irtt_thread.get_latest.return_value = MagicMock(timestamp=95.0)

        with patch("wanctl.wan_controller.time.monotonic", return_value=100.25):
            health = ctrl.get_health_data()

        workers = health["background_workers"]
        assert workers["rtt"]["cadence_sec"] == pytest.approx(0.25)
        assert workers["rtt"]["stats"]["avg_ms"] == pytest.approx(12.34)
        assert workers["rtt"]["staleness_sec"] == pytest.approx(0.25)
        assert workers["cake_stats"]["cadence_sec"] == pytest.approx(0.05)
        assert workers["cake_stats"]["stats"]["avg_ms"] == pytest.approx(7.0)
        assert workers["cake_stats"]["staleness_sec"] == pytest.approx(0.15)
        assert workers["irtt"]["cadence_sec"] == pytest.approx(10.0)
        assert workers["irtt"]["stats"]["avg_ms"] == pytest.approx(40.0)
        assert workers["irtt"]["staleness_sec"] == pytest.approx(5.25)

    def test_wan_controller_stores_cake_stats_cadence_sec_from_config(self, controller_with_mocks):
        """WANController stores the background CAKE stats cadence from Config."""
        ctrl, config, _, _ = controller_with_mocks

        assert ctrl._cake_stats_cadence_sec == pytest.approx(config.cake_stats_cadence_sec)

    def test_start_background_cake_stats_uses_configured_cadence(self, controller_with_mocks):
        """BackgroundCakeStatsThread receives the configured CAKE stats cadence."""
        from wanctl.cake_signal import CakeSignalConfig, CakeSignalProcessor

        ctrl, _, _, _ = controller_with_mocks
        ctrl._cake_stats_cadence_sec = 0.25
        ctrl._cake_signal_supported = True
        ctrl._dl_cake_signal = CakeSignalProcessor(config=CakeSignalConfig(enabled=True))
        ctrl._ul_cake_signal = CakeSignalProcessor(config=CakeSignalConfig(enabled=True))
        shutdown_event = MagicMock()

        adapter = MagicMock()
        adapter.dl_backend.interface = "ifb4TestWAN"
        adapter.ul_backend.interface = "eth0"
        ctrl.router = adapter

        with patch("wanctl.wan_controller.BackgroundCakeStatsThread") as mock_thread_cls:
            mock_thread = MagicMock()
            mock_thread_cls.return_value = mock_thread

            ctrl.start_background_cake_stats(shutdown_event)

        assert mock_thread_cls.call_args.kwargs["cadence_sec"] == pytest.approx(0.25)
        mock_thread.start.assert_called_once()

    def test_update_overlap_counters_increments_on_apply_completion_with_dump_overlap(
        self, controller_with_mocks
    ):
        """Apply completion records one overlap episode and stays idempotent."""
        ctrl, _, _, _ = controller_with_mocks

        ctrl.router.dl_backend = MagicMock()
        ctrl.router.dl_backend._last_apply_started_monotonic = 100.105
        ctrl.router.dl_backend._last_apply_finished_monotonic = 100.112
        ctrl.router.dl_backend._last_apply_was_kernel_write = True
        ctrl.router.ul_backend = MagicMock()
        ctrl.router.ul_backend._last_apply_started_monotonic = None
        ctrl.router.ul_backend._last_apply_finished_monotonic = None
        ctrl.router.ul_backend._last_apply_was_kernel_write = False
        ctrl._cake_stats_thread = MagicMock()
        ctrl._cake_stats_thread.get_overlap_snapshot.return_value = MagicMock(
            last_dump_started_monotonic=100.100,
            last_dump_finished_monotonic=100.110,
        )

        assert ctrl._overlap_episodes == 0

        ctrl._update_overlap_counters_on_apply_completion()

        assert ctrl._overlap_episodes == 1
        assert ctrl._overlap_max_ms == pytest.approx(5.0, abs=0.01)
        assert ctrl._last_overlap_ms == pytest.approx(5.0, abs=0.01)
        assert ctrl._last_overlap_monotonic == pytest.approx(100.110, abs=1e-6)
        assert ctrl._last_counted_apply_finished_monotonic == 100.112

        ctrl._update_overlap_counters_on_apply_completion()

        assert ctrl._overlap_episodes == 1
        assert ctrl._overlap_max_ms == pytest.approx(5.0, abs=0.01)
        assert ctrl._last_overlap_ms == pytest.approx(5.0, abs=0.01)

    def test_update_overlap_counters_skips_when_no_kernel_write(self, controller_with_mocks):
        """Skip-only applies do not mutate overlap counters."""
        ctrl, _, _, _ = controller_with_mocks

        ctrl.router.dl_backend = MagicMock()
        ctrl.router.dl_backend._last_apply_started_monotonic = 100.105
        ctrl.router.dl_backend._last_apply_finished_monotonic = 100.112
        ctrl.router.dl_backend._last_apply_was_kernel_write = False
        ctrl.router.ul_backend = MagicMock()
        ctrl.router.ul_backend._last_apply_started_monotonic = 100.106
        ctrl.router.ul_backend._last_apply_finished_monotonic = 100.113
        ctrl.router.ul_backend._last_apply_was_kernel_write = False
        ctrl._cake_stats_thread = MagicMock()
        ctrl._cake_stats_thread.get_overlap_snapshot.return_value = MagicMock(
            last_dump_started_monotonic=100.100,
            last_dump_finished_monotonic=100.110,
        )

        ctrl._update_overlap_counters_on_apply_completion()

        assert ctrl._overlap_episodes == 0
        assert ctrl._last_overlap_ms is None
        assert ctrl._last_counted_apply_finished_monotonic is None

    def test_get_health_data_exposes_cake_stats_overlap_pure_reader_contract(
        self, controller_with_mocks
    ):
        """Health facade exposes overlap without mutating controller counters."""
        ctrl, _, _, _ = controller_with_mocks

        ctrl._overlap_episodes = 3
        ctrl._overlap_max_ms = 7.25
        ctrl._slow_apply_with_overlap_count = 1
        ctrl._last_overlap_ms = 4.5
        ctrl._last_overlap_monotonic = 200.10
        ctrl._cake_stats_cadence_sec = 0.2
        ctrl.router.dl_backend = MagicMock()
        ctrl.router.dl_backend._last_apply_started_monotonic = 199.95
        ctrl.router.dl_backend._last_apply_finished_monotonic = 200.00
        ctrl.router.ul_backend = MagicMock()
        ctrl.router.ul_backend._last_apply_started_monotonic = None
        ctrl.router.ul_backend._last_apply_finished_monotonic = None
        ctrl._cake_stats_thread = MagicMock()
        ctrl._cake_stats_thread.get_overlap_snapshot.return_value = MagicMock(
            last_dump_started_monotonic=199.90,
            last_dump_finished_monotonic=199.99,
            last_dump_elapsed_ms=8.0,
        )
        ctrl._cake_stats_thread.get_latest.return_value = MagicMock(timestamp=200.0)
        ctrl._cake_stats_thread.get_profile_stats.return_value = {"avg_ms": 7.0}

        with patch("wanctl.wan_controller.time.monotonic", return_value=200.25):
            health = ctrl.get_health_data()
            health_again = ctrl.get_health_data()

        overlap = health["background_workers"]["cake_stats"]["overlap"]
        assert overlap["active_now"] is False
        assert overlap["last_overlap_ms"] == pytest.approx(4.5)
        assert overlap["last_overlap_monotonic"] == pytest.approx(200.10)
        assert overlap["episodes"] == 3
        assert overlap["max_overlap_ms"] == pytest.approx(7.25)
        assert overlap["slow_apply_with_overlap_count"] == 1
        assert overlap["last_dump_started_monotonic"] == pytest.approx(199.90)
        assert overlap["last_dump_finished_monotonic"] == pytest.approx(199.99)
        assert overlap["last_dump_elapsed_ms"] == pytest.approx(8.0)
        assert overlap["last_apply_started_monotonic"] == pytest.approx(199.95)
        assert overlap["last_apply_finished_monotonic"] == pytest.approx(200.00)
        assert (
            health["background_workers"]["cake_stats"]["cadence_sec"]
            == pytest.approx(ctrl._cake_stats_cadence_sec)
        )
        assert (
            health_again["background_workers"]["cake_stats"]["overlap"]["episodes"] == 3
        )
        assert ctrl._overlap_episodes == 3
        assert ctrl._overlap_max_ms == pytest.approx(7.25)
        assert ctrl._slow_apply_with_overlap_count == 1


    def test_log_slow_router_apply_counts_as_overlap_when_recent_completed_overlap(
        self, controller_with_mocks
    ):
        """Recent completed overlap increments the slow-apply overlap counter."""
        ctrl, _, _, _ = controller_with_mocks

        ctrl._last_overlap_ms = 3.0
        ctrl._last_overlap_monotonic = 300.5
        ctrl._slow_apply_with_overlap_count = 0
        ctrl.router.dl_backend = MagicMock()
        ctrl.router.dl_backend._last_apply_started_monotonic = 300.40
        ctrl.router.dl_backend._last_apply_finished_monotonic = 300.45
        ctrl.router.ul_backend = MagicMock()
        ctrl.router.ul_backend._last_apply_started_monotonic = None
        ctrl.router.ul_backend._last_apply_finished_monotonic = None
        ctrl._cake_stats_thread = MagicMock()
        ctrl._cake_stats_thread.get_overlap_snapshot.return_value = MagicMock(
            last_dump_started_monotonic=300.30,
            last_dump_finished_monotonic=300.35,
            last_dump_elapsed_ms=6.0,
        )

        with patch("wanctl.wan_controller.time.monotonic", return_value=301.0):
            ctrl._log_slow_router_apply(
                elapsed_ms=85.0,
                dl_rate=50_000_000,
                ul_rate=20_000_000,
                breakdown={
                    "autorate_router_apply_primary": 85.0,
                    "autorate_router_write_download": 42.0,
                    "autorate_router_write_upload": 41.0,
                    "autorate_router_write_skipped": 0.0,
                    "autorate_router_write_fallback": 0.0,
                },
            )

        assert ctrl._slow_apply_with_overlap_count == 1
        warning_args = ctrl.logger.warning.call_args.args
        assert "overlap=%s" in warning_args[0]
        assert any(
            isinstance(arg, dict) and "active_now" in arg for arg in warning_args
        )
        assert any(
            isinstance(arg, dict)
            and "write_download_ms" in arg
            and "write_upload_ms" in arg
            and "apply_primary_ms" in arg
            for arg in warning_args
        )

    def test_zone_attrs_initialized_green(self, controller_with_mocks):
        """New WANController has _dl_zone='GREEN' and _ul_zone='GREEN'."""
        ctrl, _, _, _ = controller_with_mocks

        assert ctrl._dl_zone == "GREEN"
        assert ctrl._ul_zone == "GREEN"


class TestPhase193MetricsBatch:
    @pytest.fixture
    def controller(self, mock_autorate_config):
        from wanctl.cake_signal import CakeSignalConfig, CakeSignalProcessor
        from wanctl.wan_controller import WANController

        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = True
        router.rate_limit_params = {"max_changes": 5, "window_seconds": 10}

        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_autorate_config,
                router=router,
                rtt_measurement=MagicMock(),
                logger=MagicMock(),
            )

        controller._metrics_writer = MagicMock()
        controller._io_worker = None
        controller._dl_cake_signal = CakeSignalProcessor(
            config=CakeSignalConfig(enabled=True, metrics_enabled=True)
        )
        controller._ul_cake_signal = CakeSignalProcessor(
            config=CakeSignalConfig(enabled=True, metrics_enabled=True)
        )
        return controller

    @staticmethod
    def _make_snapshot(*, cold_start: bool, max_delay_delta_us: int):
        from wanctl.cake_signal import CakeSignalSnapshot

        return CakeSignalSnapshot(
            drop_rate=10.0,
            total_drop_rate=12.0,
            backlog_bytes=4096,
            peak_delay_us=500,
            tins=(),
            cold_start=cold_start,
            avg_delay_us=5000,
            base_delay_us=200,
            max_delay_delta_us=max_delay_delta_us,
        )

    @staticmethod
    def _metrics_by_name(batch):
        return {
            (metric_name, tuple(sorted((labels or {}).items()))): value
            for _, _, metric_name, value, labels, _ in batch
        }

    def test_dl_metrics_batch_includes_phase_193_metrics_with_values(self, controller):
        controller._dl_cake_snapshot = self._make_snapshot(
            cold_start=False, max_delay_delta_us=4800
        )
        controller._ul_cake_snapshot = None

        with patch("wanctl.wan_controller.time.time", return_value=1234):
            controller._run_logging_metrics(
                measured_rtt=25.0,
                fused_rtt=25.0,
                dl_zone="GREEN",
                ul_zone="GREEN",
                dl_rate=100_000_000,
                ul_rate=20_000_000,
                delta=5.0,
                dl_transition_reason=None,
                ul_transition_reason=None,
                irtt_result=None,
            )

        batch = controller._metrics_writer.write_metrics_batch.call_args.args[0]
        metrics = self._metrics_by_name(batch)
        dl_key = (("direction", "download"),)
        assert metrics[("wanctl_cake_avg_delay_delta_us", dl_key)] == pytest.approx(4800.0)
        assert metrics[("wanctl_arbitration_active_primary", dl_key)] == pytest.approx(
            float(ARBITRATION_PRIMARY_ENCODING["rtt"])
        )
        assert ("wanctl_rtt_confidence", dl_key) not in metrics

    def test_dl_metrics_batch_skips_nullable_values_when_snapshot_missing(self, controller):
        controller._dl_cake_snapshot = None
        controller._ul_cake_snapshot = None

        with patch("wanctl.wan_controller.time.time", return_value=1234):
            controller._run_logging_metrics(
                measured_rtt=25.0,
                fused_rtt=25.0,
                dl_zone="GREEN",
                ul_zone="GREEN",
                dl_rate=100_000_000,
                ul_rate=20_000_000,
                delta=5.0,
                dl_transition_reason=None,
                ul_transition_reason=None,
                irtt_result=None,
            )

        batch = controller._metrics_writer.write_metrics_batch.call_args.args[0]
        metrics = self._metrics_by_name(batch)
        dl_key = (("direction", "download"),)
        assert ("wanctl_cake_avg_delay_delta_us", dl_key) not in metrics
        assert ("wanctl_rtt_confidence", dl_key) not in metrics
        assert metrics[("wanctl_arbitration_active_primary", dl_key)] == pytest.approx(
            float(ARBITRATION_PRIMARY_ENCODING["rtt"])
        )

    def test_dl_metrics_batch_skips_nullable_delta_when_snapshot_is_cold_start(self, controller):
        controller._dl_cake_snapshot = self._make_snapshot(
            cold_start=True, max_delay_delta_us=9999
        )
        controller._ul_cake_snapshot = None

        with patch("wanctl.wan_controller.time.time", return_value=1234):
            controller._run_logging_metrics(
                measured_rtt=25.0,
                fused_rtt=25.0,
                dl_zone="GREEN",
                ul_zone="GREEN",
                dl_rate=100_000_000,
                ul_rate=20_000_000,
                delta=5.0,
                dl_transition_reason=None,
                ul_transition_reason=None,
                irtt_result=None,
            )

        batch = controller._metrics_writer.write_metrics_batch.call_args.args[0]
        metrics = self._metrics_by_name(batch)
        dl_key = (("direction", "download"),)
        assert ("wanctl_cake_avg_delay_delta_us", dl_key) not in metrics

    def test_dl_metrics_emit_queue_primary_when_selector_active(self, controller):
        controller._dl_cake_snapshot = self._make_snapshot(
            cold_start=False, max_delay_delta_us=20000
        )
        controller._ul_cake_snapshot = None
        controller._last_arbitration_primary = "queue"

        with patch("wanctl.wan_controller.time.time", return_value=1234):
            controller._run_logging_metrics(
                measured_rtt=25.0,
                fused_rtt=25.0,
                dl_zone="GREEN",
                ul_zone="GREEN",
                dl_rate=100_000_000,
                ul_rate=20_000_000,
                delta=5.0,
                dl_transition_reason=None,
                ul_transition_reason=None,
                irtt_result=None,
            )

        batch = controller._metrics_writer.write_metrics_batch.call_args.args[0]
        metrics = self._metrics_by_name(batch)
        dl_key = (("direction", "download"),)
        assert metrics[("wanctl_arbitration_active_primary", dl_key)] == pytest.approx(
            float(ARBITRATION_PRIMARY_ENCODING["queue"])
        )

    def test_dl_metrics_emit_rtt_primary_in_fallback(self, controller):
        controller._cake_signal_supported = False
        controller._dl_cake_snapshot = self._make_snapshot(
            cold_start=False, max_delay_delta_us=20000
        )
        controller._ul_cake_snapshot = None
        controller._last_arbitration_primary = "rtt"

        with patch("wanctl.wan_controller.time.time", return_value=1234):
            controller._run_logging_metrics(
                measured_rtt=25.0,
                fused_rtt=25.0,
                dl_zone="GREEN",
                ul_zone="GREEN",
                dl_rate=100_000_000,
                ul_rate=20_000_000,
                delta=5.0,
                dl_transition_reason=None,
                ul_transition_reason=None,
                irtt_result=None,
            )

        batch = controller._metrics_writer.write_metrics_batch.call_args.args[0]
        metrics = self._metrics_by_name(batch)
        dl_key = (("direction", "download"),)
        assert metrics[("wanctl_arbitration_active_primary", dl_key)] == pytest.approx(
            float(ARBITRATION_PRIMARY_ENCODING["rtt"])
        )

    def test_phase195_metrics_emit_rtt_confidence_when_available(self, controller):
        controller._dl_cake_snapshot = self._make_snapshot(
            cold_start=False, max_delay_delta_us=20000
        )
        controller._ul_cake_snapshot = None
        controller._last_rtt_confidence = 0.85

        with patch("wanctl.wan_controller.time.time", return_value=1234):
            controller._run_logging_metrics(
                measured_rtt=25.0,
                fused_rtt=25.0,
                dl_zone="GREEN",
                ul_zone="GREEN",
                dl_rate=100_000_000,
                ul_rate=20_000_000,
                delta=5.0,
                dl_transition_reason=None,
                ul_transition_reason=None,
                irtt_result=None,
            )

        batch = controller._metrics_writer.write_metrics_batch.call_args.args[0]
        confidence_rows = [
            row for row in batch if row[2] == "wanctl_rtt_confidence"
        ]
        assert confidence_rows == [
            (
                1234,
                "TestWAN",
                "wanctl_rtt_confidence",
                0.85,
                controller._download_labels,
                "raw",
            )
        ]
        metrics = self._metrics_by_name(batch)
        dl_key = (("direction", "download"),)
        assert metrics[("wanctl_rtt_confidence", dl_key)] == pytest.approx(0.85)

    def test_phase195_metrics_skip_rtt_confidence_when_none(self, controller):
        controller._dl_cake_snapshot = self._make_snapshot(
            cold_start=False, max_delay_delta_us=20000
        )
        controller._ul_cake_snapshot = None
        controller._last_rtt_confidence = None

        with patch("wanctl.wan_controller.time.time", return_value=1234):
            controller._run_logging_metrics(
                measured_rtt=25.0,
                fused_rtt=25.0,
                dl_zone="GREEN",
                ul_zone="GREEN",
                dl_rate=100_000_000,
                ul_rate=20_000_000,
                delta=5.0,
                dl_transition_reason=None,
                ul_transition_reason=None,
                irtt_result=None,
            )

        batch = controller._metrics_writer.write_metrics_batch.call_args.args[0]
        metrics = self._metrics_by_name(batch)
        dl_key = (("direction", "download"),)
        assert ("wanctl_rtt_confidence", dl_key) not in metrics

    def test_phase195_ul_cake_metric_order_is_unchanged(self, controller):
        controller._dl_cake_snapshot = self._make_snapshot(
            cold_start=False, max_delay_delta_us=20000
        )
        controller._ul_cake_snapshot = self._make_snapshot(
            cold_start=False, max_delay_delta_us=3000
        )
        controller._last_rtt_confidence = 0.85

        with patch("wanctl.wan_controller.time.time", return_value=1234):
            controller._run_logging_metrics(
                measured_rtt=25.0,
                fused_rtt=25.0,
                dl_zone="GREEN",
                ul_zone="GREEN",
                dl_rate=100_000_000,
                ul_rate=20_000_000,
                delta=5.0,
                dl_transition_reason=None,
                ul_transition_reason=None,
                irtt_result=None,
            )

        batch = controller._metrics_writer.write_metrics_batch.call_args.args[0]
        upload_metric_names = [
            metric_name
            for _, _, metric_name, _, labels, _ in batch
            if labels == {"direction": "upload"}
        ]
        assert upload_metric_names == [
            "wanctl_cake_drop_rate",
            "wanctl_cake_total_drop_rate",
            "wanctl_cake_backlog_bytes",
            "wanctl_cake_peak_delay_us",
        ]

    def test_ul_metrics_block_textually_unchanged_label_anchored(self):
        import re
        import subprocess

        result = subprocess.run(
            ["git", "diff", "src/wanctl/wan_controller.py"],
            capture_output=True,
            text=True,
            check=True,
        )
        offending = [
            line
            for line in result.stdout.splitlines()
            if re.match(
                r'^[+-].*"wanctl_cake_(drop_rate|total_drop_rate|backlog_bytes|peak_delay_us)".*self\._upload_labels',
                line,
            )
        ]
        assert offending == [], f"UL metrics block was modified: {offending}"

    def test_get_health_data_signal_arbitration_shape(self, controller):
        arb = controller.get_health_data()["signal_arbitration"]

        assert set(arb) == {
            "active_primary_signal",
            "rtt_confidence",
            "control_decision_reason",
            "cake_av_delay_delta_us",
            "refractory_active",
        }
        assert arb["rtt_confidence"] is None
        assert arb["refractory_active"] is False

    def test_get_health_data_signal_arbitration_cold_start_av_delta_is_none(
        self, controller
    ):
        controller._last_arbitration_primary = "queue"
        controller._last_arbitration_reason = "queue_distress"
        controller._dl_cake_snapshot = None

        missing_snapshot_arb = controller.get_health_data()["signal_arbitration"]
        assert missing_snapshot_arb["cake_av_delay_delta_us"] is None

        controller._dl_cake_snapshot = self._make_snapshot(
            cold_start=True, max_delay_delta_us=9999
        )
        cold_start_arb = controller.get_health_data()["signal_arbitration"]
        assert cold_start_arb["cake_av_delay_delta_us"] is None

    def test_get_health_data_signal_arbitration_relays_queue_primary(self, controller):
        controller._last_arbitration_primary = "queue"
        controller._last_arbitration_reason = "queue_distress"
        controller._dl_cake_snapshot = self._make_snapshot(
            cold_start=False, max_delay_delta_us=20000
        )

        arb = controller.get_health_data()["signal_arbitration"]

        assert arb["active_primary_signal"] == "queue"
        assert arb["control_decision_reason"] == "queue_distress"
        assert arb["cake_av_delay_delta_us"] == 20000


class TestPhase194DLSelector:
    @pytest.fixture
    def controller(self, mock_autorate_config):
        from wanctl.cake_signal import CakeSignalConfig, CakeSignalProcessor
        from wanctl.wan_controller import WANController

        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = True
        router.rate_limit_params = {"max_changes": 5, "window_seconds": 10}

        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_autorate_config,
                router=router,
                rtt_measurement=MagicMock(),
                logger=MagicMock(),
            )

        controller._dl_cake_signal = CakeSignalProcessor(
            config=CakeSignalConfig(enabled=True, metrics_enabled=True)
        )
        controller._ul_cake_signal = CakeSignalProcessor(
            config=CakeSignalConfig(enabled=True, metrics_enabled=True)
        )
        controller.baseline_rtt = 25.0
        controller.load_rtt = 42.0
        controller.green_threshold = 15.0
        return controller

    @staticmethod
    def _make_snapshot(*, cold_start: bool, max_delay_delta_us: int):
        from wanctl.cake_signal import CakeSignalSnapshot

        return CakeSignalSnapshot(
            drop_rate=10.0,
            total_drop_rate=12.0,
            backlog_bytes=4096,
            peak_delay_us=500,
            tins=(),
            cold_start=cold_start,
            avg_delay_us=5000,
            base_delay_us=200,
            max_delay_delta_us=max_delay_delta_us,
        )

    def test_queue_primary_distress_returns_virtual_load_rtt(self, controller):
        from wanctl.wan_controller import ARBITRATION_REASON_QUEUE_DISTRESS

        controller._cake_signal_supported = True
        snapshot = self._make_snapshot(cold_start=False, max_delay_delta_us=20000)

        primary, load_for_classifier, reason = controller._select_dl_primary_scalar_ms(
            snapshot
        )

        assert primary == "queue"
        assert load_for_classifier == pytest.approx(45.0)
        assert reason == ARBITRATION_REASON_QUEUE_DISTRESS

    def test_queue_primary_green_stable_returns_virtual_load_rtt(self, controller):
        from wanctl.wan_controller import ARBITRATION_REASON_GREEN_STABLE

        controller._cake_signal_supported = True
        snapshot = self._make_snapshot(cold_start=False, max_delay_delta_us=5000)

        primary, load_for_classifier, reason = controller._select_dl_primary_scalar_ms(
            snapshot
        )

        assert primary == "queue"
        assert load_for_classifier == pytest.approx(30.0)
        assert reason == ARBITRATION_REASON_GREEN_STABLE

    def test_fallback_when_cake_signal_not_supported_preserves_load_rtt(
        self, controller
    ):
        from wanctl.wan_controller import ARBITRATION_REASON_GREEN_STABLE

        controller._cake_signal_supported = False
        controller.load_rtt = 42.0
        snapshot = self._make_snapshot(cold_start=False, max_delay_delta_us=20000)

        primary, load_for_classifier, reason = controller._select_dl_primary_scalar_ms(
            snapshot
        )

        assert primary == "rtt"
        assert load_for_classifier == 42.0
        assert reason == ARBITRATION_REASON_GREEN_STABLE

    def test_fallback_when_snapshot_missing_preserves_load_rtt(self, controller):
        from wanctl.wan_controller import ARBITRATION_REASON_GREEN_STABLE

        controller._cake_signal_supported = True
        controller.load_rtt = 33.5

        primary, load_for_classifier, reason = controller._select_dl_primary_scalar_ms(
            None
        )

        assert primary == "rtt"
        assert load_for_classifier == 33.5
        assert reason == ARBITRATION_REASON_GREEN_STABLE

    def test_fallback_when_snapshot_is_cold_start_preserves_load_rtt(
        self, controller
    ):
        from wanctl.wan_controller import ARBITRATION_REASON_GREEN_STABLE

        controller._cake_signal_supported = True
        controller.load_rtt = 37.25
        snapshot = self._make_snapshot(cold_start=True, max_delay_delta_us=20000)

        primary, load_for_classifier, reason = controller._select_dl_primary_scalar_ms(
            snapshot
        )

        assert primary == "rtt"
        assert load_for_classifier == 37.25
        assert reason == ARBITRATION_REASON_GREEN_STABLE

    def test_initial_arbitration_state_defaults_to_rtt_primary_normal(
        self, controller
    ):
        from wanctl.wan_controller import ARBITRATION_REASON_RTT_PRIMARY_NORMAL

        assert controller._last_arbitration_primary == "rtt"
        assert controller._last_arbitration_reason == ARBITRATION_REASON_RTT_PRIMARY_NORMAL

    def test_select_dl_primary_returns_queue_during_refractory_with_valid_snapshot(
        self, controller
    ) -> None:
        """Phase 197 D-01 + D-06: refractory + valid snapshot -> queue_during_refractory."""
        controller._cake_signal_supported = True
        controller._dl_refractory_remaining = 5  # > 0
        snapshot = self._make_snapshot(cold_start=False, max_delay_delta_us=20_000)
        primary, load, reason = controller._select_dl_primary_scalar_ms(snapshot)
        assert primary == "queue"
        assert reason == "queue_during_refractory"
        assert load == pytest.approx(controller.baseline_rtt + 20.0)

    def test_select_dl_primary_returns_rtt_fallback_during_refractory_when_none(
        self, controller
    ) -> None:
        """Phase 197 D-04: refractory + None -> rtt_fallback_during_refractory."""
        controller._cake_signal_supported = True
        controller._dl_refractory_remaining = 5
        primary, load, reason = controller._select_dl_primary_scalar_ms(None)
        assert primary == "rtt"
        assert reason == "rtt_fallback_during_refractory"
        assert load == controller.load_rtt

    def test_select_dl_primary_returns_rtt_fallback_during_refractory_when_cold_start(
        self, controller
    ) -> None:
        """Phase 197 D-04: refractory + cold_start -> rtt_fallback_during_refractory."""
        controller._cake_signal_supported = True
        controller._dl_refractory_remaining = 5
        snapshot = self._make_snapshot(cold_start=True, max_delay_delta_us=20_000)
        primary, load, reason = controller._select_dl_primary_scalar_ms(snapshot)
        assert primary == "rtt"
        assert reason == "rtt_fallback_during_refractory"
        assert load == controller.load_rtt

    def test_select_dl_primary_outside_refractory_byte_identical_to_phase_195(
        self, controller
    ) -> None:
        """Phase 197 byte-identity: outside refractory, delta_ms=20.0 -> queue_distress."""
        controller._cake_signal_supported = True
        controller._dl_refractory_remaining = 0
        snapshot = self._make_snapshot(cold_start=False, max_delay_delta_us=20_000)
        primary, _, reason = controller._select_dl_primary_scalar_ms(snapshot)
        assert primary == "queue"
        assert reason == "queue_distress"


class TestPhase195Arbitration:
    @pytest.fixture
    def controller(self, mock_autorate_config):
        from wanctl.cake_signal import CakeSignalConfig, CakeSignalProcessor
        from wanctl.wan_controller import WANController

        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = True
        router.rate_limit_params = {"max_changes": 5, "window_seconds": 10}

        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_autorate_config,
                router=router,
                rtt_measurement=MagicMock(),
                logger=MagicMock(),
            )

        controller._dl_cake_signal = CakeSignalProcessor(
            config=CakeSignalConfig(enabled=True, metrics_enabled=True)
        )
        controller._ul_cake_signal = CakeSignalProcessor(
            config=CakeSignalConfig(enabled=True, metrics_enabled=True)
        )
        controller._cake_signal_supported = True
        controller.baseline_rtt = 25.0
        controller.load_rtt = 55.0
        controller.green_threshold = 15.0
        controller._last_rtt_confidence = 0.7
        controller._last_queue_direction = "worsening"
        controller._last_rtt_direction = "worsening"
        return controller

    @staticmethod
    def _make_snapshot(*, cold_start: bool = False, max_delay_delta_us: int = 500):
        from wanctl.cake_signal import CakeSignalSnapshot

        return CakeSignalSnapshot(
            drop_rate=10.0,
            total_drop_rate=12.0,
            backlog_bytes=4096,
            peak_delay_us=500,
            tins=(),
            cold_start=cold_start,
            avg_delay_us=max_delay_delta_us,
            base_delay_us=0,
            max_delay_delta_us=max_delay_delta_us,
        )

    def test_queue_distress_remains_authoritative_under_high_confidence_rtt(
        self, controller
    ):
        from wanctl.wan_controller import ARBITRATION_REASON_QUEUE_DISTRESS

        controller.load_rtt = 55.0
        controller._last_rtt_confidence = 1.0
        snapshot = self._make_snapshot(max_delay_delta_us=20_000)

        primary, load_for_classifier, reason = controller._select_dl_primary_scalar_ms(
            snapshot
        )

        assert (primary, reason) == ("queue", ARBITRATION_REASON_QUEUE_DISTRESS)
        assert load_for_classifier == pytest.approx(45.0)

    @pytest.mark.parametrize(
        ("confidence", "queue_dir", "rtt_dir", "rtt_delta_ms"),
        [
            (0.3, "worsening", "worsening", 30.0),
            (1.0, "worsening", "improving", 30.0),
            (1.0, "worsening", "worsening", 5.0),
            (0.7, "worsening", "unknown", 30.0),
            (None, "worsening", "worsening", 30.0),
        ],
    )
    def test_queue_green_rtt_veto_gate_blocks_on_missing_condition(
        self, controller, confidence, queue_dir, rtt_dir, rtt_delta_ms
    ):
        from wanctl.wan_controller import ARBITRATION_REASON_GREEN_STABLE

        controller.load_rtt = controller.baseline_rtt + rtt_delta_ms
        controller._last_rtt_confidence = confidence
        controller._last_queue_direction = queue_dir
        controller._last_rtt_direction = rtt_dir
        snapshot = self._make_snapshot(max_delay_delta_us=500)

        primary, load_for_classifier, reason = controller._select_dl_primary_scalar_ms(
            snapshot
        )

        assert (primary, reason) == ("queue", ARBITRATION_REASON_GREEN_STABLE)
        assert load_for_classifier == pytest.approx(controller.baseline_rtt + 0.5)

    @pytest.mark.parametrize("confidence", [0.6, 0.7])
    def test_queue_green_rtt_veto_gate_passes_at_high_confidence(
        self, controller, confidence
    ):
        from wanctl.wan_controller import ARBITRATION_REASON_RTT_VETO

        controller.load_rtt = 55.0
        controller._last_rtt_confidence = confidence
        controller._last_queue_direction = "worsening"
        controller._last_rtt_direction = "worsening"
        snapshot = self._make_snapshot(max_delay_delta_us=500)

        primary, load_for_classifier, reason = controller._select_dl_primary_scalar_ms(
            snapshot
        )

        assert (primary, reason) == ("rtt", ARBITRATION_REASON_RTT_VETO)
        assert load_for_classifier == pytest.approx(controller.load_rtt)

    def test_held_direction_counts_as_rtt_veto_agreement(self, controller):
        from wanctl.wan_controller import ARBITRATION_REASON_RTT_VETO

        controller.load_rtt = 55.0
        controller._last_rtt_confidence = 0.7
        controller._last_queue_direction = "held"
        controller._last_rtt_direction = "held"
        snapshot = self._make_snapshot(max_delay_delta_us=500)

        primary, load_for_classifier, reason = controller._select_dl_primary_scalar_ms(
            snapshot
        )

        assert (primary, reason) == ("rtt", ARBITRATION_REASON_RTT_VETO)
        assert load_for_classifier == pytest.approx(controller.load_rtt)

    def test_cake_unsupported_fallback_ignores_rtt_veto_gate(self, controller):
        from wanctl.wan_controller import ARBITRATION_REASON_GREEN_STABLE

        controller._cake_signal_supported = False
        controller.load_rtt = 55.0
        controller._last_rtt_confidence = 1.0
        snapshot = self._make_snapshot(max_delay_delta_us=500)

        primary, load_for_classifier, reason = controller._select_dl_primary_scalar_ms(
            snapshot
        )

        assert (primary, reason) == ("rtt", ARBITRATION_REASON_GREEN_STABLE)
        assert load_for_classifier == pytest.approx(controller.load_rtt)

    def test_selector_tuple_shape_stays_stable(self, controller):
        snapshot = self._make_snapshot(max_delay_delta_us=500)

        result = controller._select_dl_primary_scalar_ms(snapshot)

        assert isinstance(result, tuple)
        assert len(result) == 3
        primary, load_for_classifier, reason = result
        assert primary in {"queue", "rtt"}
        assert isinstance(load_for_classifier, float)
        assert isinstance(reason, str)


class TestPhase195HealerBypass:
    @pytest.fixture
    def controller(self, mock_autorate_config):
        from wanctl.cake_signal import CakeSignalConfig, CakeSignalProcessor
        from wanctl.wan_controller import WANController

        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = True
        router.rate_limit_params = {"max_changes": 5, "window_seconds": 10}

        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_autorate_config,
                router=router,
                rtt_measurement=MagicMock(),
                logger=MagicMock(),
            )

        controller._dl_cake_signal = CakeSignalProcessor(
            config=CakeSignalConfig(enabled=True, metrics_enabled=True)
        )
        controller._ul_cake_signal = CakeSignalProcessor(
            config=CakeSignalConfig(enabled=True, metrics_enabled=True)
        )
        controller._cake_signal_supported = True
        controller.baseline_rtt = 25.0
        controller.load_rtt = 45.0
        controller.green_threshold = 15.0
        controller.soft_red_threshold = 45.0
        controller.hard_red_threshold = 80.0
        controller.target_delta = 15.0
        controller.warn_delta = 45.0
        return controller

    @staticmethod
    def _make_snapshot(*, max_delay_delta_us: int = 500):
        from wanctl.cake_signal import CakeSignalSnapshot

        return CakeSignalSnapshot(
            drop_rate=10.0,
            total_drop_rate=12.0,
            backlog_bytes=4096,
            peak_delay_us=max_delay_delta_us,
            tins=(),
            cold_start=False,
            avg_delay_us=max_delay_delta_us,
            base_delay_us=0,
            max_delay_delta_us=max_delay_delta_us,
        )

    @staticmethod
    def _stub_assessment_io(controller):
        controller._dl_refractory_remaining = 0
        controller._ul_refractory_remaining = 0
        controller._dl_burst_pending = False
        controller.download.adjust_4state = MagicMock(
            return_value=("GREEN", 800_000_000, None)
        )
        controller.upload.adjust = MagicMock(return_value=("GREEN", 40_000_000, None))

    def _run_phase195_cycle(
        self,
        controller,
        *,
        queue_delta_ms: float,
        rtt_delta_ms: float,
        correlation: float | None = 1.0,
    ):
        controller._irtt_correlation = correlation
        controller._dl_cake_snapshot = self._make_snapshot(
            max_delay_delta_us=int(queue_delta_ms * 1000)
        )
        controller._ul_cake_snapshot = None
        controller.load_rtt = controller.baseline_rtt + rtt_delta_ms
        return controller._run_congestion_assessment()

    def _seed_worsening_history(
        self, controller, *, queue_delta_ms: float = 16.0, rtt_delta_ms: float = 20.0
    ):
        controller._prev_queue_delta_ms = queue_delta_ms - 1.0
        controller._prev_rtt_delta_ms = rtt_delta_ms - 1.0

    def _prime_aligned_streak(self, controller, *, cycles: int = 5):
        self._stub_assessment_io(controller)
        self._seed_worsening_history(controller)
        for offset in range(cycles):
            self._run_phase195_cycle(
                controller,
                queue_delta_ms=16.0 + offset,
                rtt_delta_ms=20.0 + offset,
                correlation=1.0,
            )

    def test_healer_bypass_streak_starts_inactive(self, controller):
        assert controller._healer_aligned_streak == 0
        assert controller._fusion_bypass_active is False

    def test_single_path_flip_never_trips_healer_bypass(self, controller):
        from wanctl.wan_controller import ARBITRATION_REASON_HEALER_BYPASS

        self._stub_assessment_io(controller)
        controller._prev_queue_delta_ms = 0.5
        controller._prev_rtt_delta_ms = 39.0

        for _ in range(10):
            self._run_phase195_cycle(
                controller,
                queue_delta_ms=0.5,
                rtt_delta_ms=40.0,
                correlation=0.3,
            )
            assert controller._healer_aligned_streak == 0
            assert controller._fusion_bypass_active is False
            assert controller._last_arbitration_reason != ARBITRATION_REASON_HEALER_BYPASS

    def test_aligned_distress_trips_healer_bypass_at_six_cycles(self, controller):
        from wanctl.wan_controller import (
            ARBITRATION_REASON_HEALER_BYPASS,
            ARBITRATION_REASON_QUEUE_DISTRESS,
            ARBITRATION_REASON_RTT_VETO,
        )

        self._stub_assessment_io(controller)
        self._seed_worsening_history(controller)

        for offset in range(5):
            self._run_phase195_cycle(
                controller,
                queue_delta_ms=16.0 + offset,
                rtt_delta_ms=20.0 + offset,
                correlation=1.0,
            )
            assert controller._healer_aligned_streak == offset + 1
            assert controller._fusion_bypass_active is False
            assert controller._last_arbitration_reason in {
                ARBITRATION_REASON_QUEUE_DISTRESS,
                ARBITRATION_REASON_RTT_VETO,
            }

        self._run_phase195_cycle(
            controller,
            queue_delta_ms=21.0,
            rtt_delta_ms=25.0,
            correlation=1.0,
        )

        assert controller._healer_aligned_streak == 6
        assert controller._fusion_bypass_active is True
        assert controller._fusion_bypass_reason == "queue_rtt_aligned_distress"
        assert controller._fusion_bypass_count == 1
        assert controller._fusion_bypass_offset_ms == pytest.approx(25.0)
        assert controller._last_arbitration_reason == ARBITRATION_REASON_HEALER_BYPASS

    def test_held_direction_counts_toward_healer_bypass_streak(self, controller):
        self._stub_assessment_io(controller)
        controller._prev_queue_delta_ms = 16.0
        controller._prev_rtt_delta_ms = 20.0

        for _ in range(6):
            self._run_phase195_cycle(
                controller,
                queue_delta_ms=16.0,
                rtt_delta_ms=20.0,
                correlation=1.0,
            )

        assert controller._healer_aligned_streak == 6
        assert controller._fusion_bypass_active is True
        assert controller._fusion_bypass_reason == "queue_rtt_aligned_distress"

    def test_direction_flip_resets_healer_bypass_streak(self, controller):
        self._prime_aligned_streak(controller, cycles=5)

        self._run_phase195_cycle(
            controller,
            queue_delta_ms=21.0,
            rtt_delta_ms=10.0,
            correlation=1.0,
        )

        assert controller._healer_aligned_streak == 0
        assert controller._fusion_bypass_active is False

    def test_confidence_drop_resets_healer_bypass_streak(self, controller):
        self._prime_aligned_streak(controller, cycles=5)

        self._run_phase195_cycle(
            controller,
            queue_delta_ms=21.0,
            rtt_delta_ms=25.0,
            correlation=None,
        )

        assert controller._last_rtt_confidence == pytest.approx(0.5)
        assert controller._healer_aligned_streak == 0
        assert controller._fusion_bypass_active is False

    def test_queue_green_resets_healer_bypass_streak_and_releases_active_bypass(
        self, controller
    ):
        self._prime_aligned_streak(controller, cycles=6)
        assert controller._fusion_bypass_active is True
        assert controller._fusion_bypass_count == 1

        self._run_phase195_cycle(
            controller,
            queue_delta_ms=0.5,
            rtt_delta_ms=26.0,
            correlation=1.0,
        )

        assert controller._healer_aligned_streak == 0
        assert controller._fusion_bypass_active is False
        assert controller._fusion_bypass_reason is None
        assert controller._fusion_bypass_count == 1

    def test_rtt_below_yellow_resets_healer_bypass_streak(self, controller):
        self._prime_aligned_streak(controller, cycles=5)

        self._run_phase195_cycle(
            controller,
            queue_delta_ms=21.0,
            rtt_delta_ms=5.0,
            correlation=1.0,
        )

        assert controller._healer_aligned_streak == 0
        assert controller._fusion_bypass_active is False

    def test_unknown_direction_never_counts_toward_healer_bypass(self, controller):
        self._stub_assessment_io(controller)
        controller._prev_queue_delta_ms = 15.0
        controller._prev_rtt_delta_ms = None

        self._run_phase195_cycle(
            controller,
            queue_delta_ms=16.0,
            rtt_delta_ms=20.0,
            correlation=1.0,
        )

        assert controller._last_rtt_direction == "unknown"
        assert controller._healer_aligned_streak == 0
        assert controller._fusion_bypass_active is False

    def test_compute_fused_rtt_no_longer_emits_absolute_disagreement(
        self, controller
    ):
        from types import SimpleNamespace

        controller._fusion_enabled = True
        controller._irtt_thread = MagicMock(cadence_sec=10.0)
        controller._irtt_thread.get_latest.return_value = SimpleNamespace(
            timestamp=time.monotonic(),
            rtt_mean_ms=100.0,
        )

        result = controller._compute_fused_rtt(20.0)

        assert result == pytest.approx(20.0)
        assert controller._fusion_bypass_active is False
        assert controller._fusion_bypass_reason != "absolute_disagreement"

    def test_phase195_source_keeps_ul_call_site_and_avoids_magnitude_ratio(self):
        import re
        from pathlib import Path

        source = Path("src/wanctl/wan_controller.py").read_text()

        assert re.search(
            r"self\.upload\.adjust\(\s*"
            r"self\.baseline_rtt,\s*effective_ul_load_rtt,\s*"
            r"self\.target_delta,\s*self\.warn_delta,\s*"
            r"cake_snapshot=ul_cake,\s*\)",
            source,
        )
        assert not re.search(
            r"max_delay_delta_us\s*/\s*(?:self\.)?load_rtt",
            source,
        )
        assert not re.search(
            r"(?:self\.)?load_rtt\s*/\s*.*max_delay_delta_us",
            source,
        )


class TestPhase195Confidence:
    @pytest.fixture
    def controller(self, mock_autorate_config):
        from wanctl.cake_signal import CakeSignalConfig, CakeSignalProcessor
        from wanctl.wan_controller import WANController

        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = True
        router.rate_limit_params = {"max_changes": 5, "window_seconds": 10}

        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_autorate_config,
                router=router,
                rtt_measurement=MagicMock(),
                logger=MagicMock(),
            )

        controller._dl_cake_signal = CakeSignalProcessor(
            config=CakeSignalConfig(enabled=True, metrics_enabled=True)
        )
        controller._ul_cake_signal = CakeSignalProcessor(
            config=CakeSignalConfig(enabled=True, metrics_enabled=True)
        )
        controller.baseline_rtt = 25.0
        controller.load_rtt = 42.0
        controller.green_threshold = 15.0
        controller.soft_red_threshold = 45.0
        controller.hard_red_threshold = 80.0
        controller.target_delta = 15.0
        controller.warn_delta = 45.0
        return controller

    @staticmethod
    def _make_snapshot(*, cold_start: bool = False, max_delay_delta_us: int = 0):
        from wanctl.cake_signal import CakeSignalSnapshot

        return CakeSignalSnapshot(
            drop_rate=10.0,
            total_drop_rate=12.0,
            backlog_bytes=4096,
            peak_delay_us=500,
            tins=(),
            cold_start=cold_start,
            avg_delay_us=max_delay_delta_us,
            base_delay_us=0,
            max_delay_delta_us=max_delay_delta_us,
        )

    @staticmethod
    def _stub_assessment_io(controller):
        controller._cake_signal_supported = True
        controller._dl_refractory_remaining = 0
        controller._ul_refractory_remaining = 0
        controller._dl_burst_pending = False
        controller.download.adjust_4state = MagicMock(
            return_value=("GREEN", 800_000_000, None)
        )
        controller.upload.adjust = MagicMock(return_value=("GREEN", 40_000_000, None))

    def test_healer_bypass_constant(self):
        from wanctl.wan_controller import ARBITRATION_REASON_HEALER_BYPASS

        assert ARBITRATION_REASON_HEALER_BYPASS == "healer_bypass"

    def test_initial_confidence_stashes(self, controller):
        assert controller._last_rtt_confidence is None
        assert controller._last_queue_direction == "unknown"
        assert controller._last_rtt_direction == "unknown"
        assert controller._prev_queue_delta_ms is None
        assert controller._prev_rtt_delta_ms is None
        assert controller._healer_aligned_streak == 0

    @pytest.mark.parametrize(
        ("previous", "current", "expected"),
        [
            (None, 10.0, "unknown"),
            (5.0, 10.0, "worsening"),
            (10.0, 5.0, "improving"),
            (5.0, 5.0, "held"),
        ],
    )
    def test_classify_direction(self, controller, previous, current, expected):
        assert controller._classify_direction(previous, current) == expected

    @pytest.mark.parametrize(
        ("ratio", "queue_direction", "rtt_direction", "expected"),
        [
            (0.3, "worsening", "worsening", 0.0),
            (1.0, "worsening", "improving", 0.0),
            (1.0, "worsening", "worsening", 1.0),
            (None, "worsening", "worsening", 0.5),
            (1.0, "unknown", "worsening", 0.5),
        ],
    )
    def test_derive_rtt_confidence(
        self, controller, ratio, queue_direction, rtt_direction, expected
    ):
        controller._irtt_correlation = ratio

        assert controller._derive_rtt_confidence(
            queue_direction, rtt_direction
        ) == pytest.approx(expected)

    def test_direction_and_confidence_helpers_are_pure(self, controller):
        controller._last_rtt_confidence = None
        controller._last_queue_direction = "unknown"
        controller._last_rtt_direction = "unknown"
        controller._prev_queue_delta_ms = None
        controller._prev_rtt_delta_ms = None
        controller._healer_aligned_streak = 0
        before = {
            "_last_rtt_confidence": controller._last_rtt_confidence,
            "_last_queue_direction": controller._last_queue_direction,
            "_last_rtt_direction": controller._last_rtt_direction,
            "_prev_queue_delta_ms": controller._prev_queue_delta_ms,
            "_prev_rtt_delta_ms": controller._prev_rtt_delta_ms,
            "_healer_aligned_streak": controller._healer_aligned_streak,
        }

        assert controller._classify_direction(1.0, 2.0) == "worsening"
        controller._irtt_correlation = 1.0
        assert controller._derive_rtt_confidence("worsening", "worsening") == 1.0

        after = {
            "_last_rtt_confidence": controller._last_rtt_confidence,
            "_last_queue_direction": controller._last_queue_direction,
            "_last_rtt_direction": controller._last_rtt_direction,
            "_prev_queue_delta_ms": controller._prev_queue_delta_ms,
            "_prev_rtt_delta_ms": controller._prev_rtt_delta_ms,
            "_healer_aligned_streak": controller._healer_aligned_streak,
        }
        assert after == before

    def test_phase195_cold_start_cycle_leaves_confidence_none(self, controller):
        self._stub_assessment_io(controller)
        controller._dl_cake_snapshot = None
        controller._ul_cake_snapshot = None

        controller._run_congestion_assessment()

        assert controller._last_rtt_confidence is None
        assert controller._last_queue_direction == "unknown"
        assert controller._last_rtt_direction == "unknown"

        controller._dl_cake_snapshot = self._make_snapshot(
            cold_start=True, max_delay_delta_us=5000
        )
        controller._run_congestion_assessment()

        assert controller._last_rtt_confidence is None
        assert controller._last_queue_direction == "unknown"
        assert controller._last_rtt_direction == "unknown"

    def test_phase195_first_valid_snapshot_has_warmup_confidence(
        self, controller
    ):
        self._stub_assessment_io(controller)
        controller._irtt_correlation = 1.0
        controller._dl_cake_snapshot = self._make_snapshot(max_delay_delta_us=1000)
        controller.load_rtt = 30.0

        controller._run_congestion_assessment()

        assert controller._last_queue_direction == "unknown"
        assert controller._last_rtt_direction == "unknown"
        assert controller._last_rtt_confidence == pytest.approx(0.5)

    def test_phase195_derives_high_confidence_when_queue_and_rtt_worsen(
        self, controller
    ):
        self._stub_assessment_io(controller)
        controller._irtt_correlation = 1.0

        controller._dl_cake_snapshot = self._make_snapshot(max_delay_delta_us=1000)
        controller.load_rtt = 30.0
        controller._run_congestion_assessment()

        controller._dl_cake_snapshot = self._make_snapshot(max_delay_delta_us=5000)
        controller.load_rtt = 45.0
        controller._run_congestion_assessment()

        assert controller._last_queue_direction == "worsening"
        assert controller._last_rtt_direction == "worsening"
        assert controller._last_rtt_confidence == pytest.approx(1.0)

    def test_phase195_protocol_disagreement_caps_cycle_confidence(
        self, controller
    ):
        self._stub_assessment_io(controller)

        controller._irtt_correlation = 1.0
        controller._dl_cake_snapshot = self._make_snapshot(max_delay_delta_us=1000)
        controller.load_rtt = 30.0
        controller._run_congestion_assessment()

        controller._irtt_correlation = 0.3
        controller._dl_cake_snapshot = self._make_snapshot(max_delay_delta_us=5000)
        controller.load_rtt = 45.0
        controller._run_congestion_assessment()

        assert controller._last_queue_direction == "worsening"
        assert controller._last_rtt_direction == "worsening"
        assert controller._last_rtt_confidence == pytest.approx(0.0)

    def test_phase195_prev_rtt_delta_uses_raw_load_not_selector_output(
        self, controller
    ):
        self._stub_assessment_io(controller)
        controller._irtt_correlation = 1.0
        controller._prev_queue_delta_ms = 10.0
        controller._prev_rtt_delta_ms = 7.0
        controller._dl_cake_snapshot = self._make_snapshot(max_delay_delta_us=5000)
        controller.load_rtt = 45.0

        controller._run_congestion_assessment()

        assert controller._prev_queue_delta_ms == pytest.approx(5.0)
        assert controller._prev_rtt_delta_ms == pytest.approx(20.0)

        controller._dl_cake_snapshot = self._make_snapshot(max_delay_delta_us=6000)
        controller.load_rtt = 40.0
        controller._run_congestion_assessment()

        assert controller._last_rtt_direction == "improving"

    def test_phase195_health_reports_live_confidence_float(self, controller):
        self._stub_assessment_io(controller)
        controller._irtt_correlation = 1.0

        controller._dl_cake_snapshot = self._make_snapshot(max_delay_delta_us=1000)
        controller.load_rtt = 30.0
        controller._run_congestion_assessment()
        controller._dl_cake_snapshot = self._make_snapshot(max_delay_delta_us=5000)
        controller.load_rtt = 45.0
        controller._run_congestion_assessment()

        arb = controller.get_health_data()["signal_arbitration"]
        assert isinstance(arb["rtt_confidence"], float)
        assert arb["rtt_confidence"] == pytest.approx(controller._last_rtt_confidence)

    def test_phase195_health_reports_none_before_cycle(self, controller):
        assert controller.get_health_data()["signal_arbitration"]["rtt_confidence"] is None

    def test_phase195_dl_classifier_inputs_stay_phase194_compatible(
        self, controller
    ):
        self._stub_assessment_io(controller)
        captured: list[tuple[str, int, str, str]] = []

        def fake_adjust(
            baseline_rtt,
            load_for_classifier,
            green_threshold,
            soft_red_threshold,
            hard_red_threshold,
            *,
            cake_snapshot,
        ):
            delta = load_for_classifier - baseline_rtt
            zone = "YELLOW" if delta > green_threshold else "GREEN"
            rate = int(load_for_classifier * 1_000_000)
            return zone, rate, None

        controller.download.adjust_4state = MagicMock(side_effect=fake_adjust)

        for delta_us in [
            0,
            1000,
            5000,
            10000,
            16000,
            20000,
            25000,
            30000,
            45000,
            60000,
            30000,
            15000,
            5000,
            0,
            2500,
            7500,
            12500,
            17500,
            22500,
            27500,
        ]:
            controller._dl_cake_snapshot = self._make_snapshot(
                max_delay_delta_us=delta_us
            )
            controller.load_rtt = 25.0 + delta_us / 2000.0
            dl_zone, dl_rate, *_ = controller._run_congestion_assessment()
            captured.append(
                (
                    dl_zone,
                    dl_rate,
                    controller._last_arbitration_primary,
                    controller._last_arbitration_reason,
                )
            )

        expected = []
        for delta_us in [
            0,
            1000,
            5000,
            10000,
            16000,
            20000,
            25000,
            30000,
            45000,
            60000,
            30000,
            15000,
            5000,
            0,
            2500,
            7500,
            12500,
            17500,
            22500,
            27500,
        ]:
            classifier_load = 25.0 + delta_us / 1000.0
            delta = classifier_load - 25.0
            expected.append(
                (
                    "YELLOW" if delta > controller.green_threshold else "GREEN",
                    int(classifier_load * 1_000_000),
                    "queue",
                    "queue_distress"
                    if delta > controller.green_threshold
                    else "green_stable",
                )
            )

        assert captured == expected


class TestMeasureRttMedianOfThree:
    """Tests for WANController.measure_rtt() median-of-three edge cases.

    Covers lines 890-910:
    - 2 hosts return RTT (partial success)
    - 1 host returns RTT (minimal success)
    - All hosts fail (return empty)
    - Single host ping path (use_median_of_three=False)
    """

    @pytest.fixture
    def controller_with_mocks(self):
        """Create a WANController with all dependencies accessible."""
        from wanctl.wan_controller import WANController

        config = MagicMock()
        config.wan_name = "TestWAN"
        config.baseline_rtt_initial = 25.0
        config.download_floor_green = 800_000_000
        config.download_floor_yellow = 600_000_000
        config.download_floor_soft_red = 500_000_000
        config.download_floor_red = 400_000_000
        config.download_ceiling = 920_000_000
        config.download_step_up = 10_000_000
        config.download_factor_down = 0.85
        config.upload_floor_green = 35_000_000
        config.upload_floor_yellow = 30_000_000
        config.upload_floor_red = 25_000_000
        config.upload_ceiling = 40_000_000
        config.upload_step_up = 1_000_000
        config.upload_factor_down = 0.85
        config.target_bloat_ms = 15.0
        config.warn_bloat_ms = 45.0
        config.hard_red_bloat_ms = 80.0
        config.alpha_baseline = 0.001
        config.alpha_load = 0.1
        config.baseline_update_threshold_ms = 3.0
        config.baseline_rtt_min = 10.0
        config.baseline_rtt_max = 60.0
        config.accel_threshold_ms = 15.0
        config.accel_confirm_cycles = 3
        config.download_green_required = 5
        config.upload_green_required = 5
        config.ping_hosts = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]  # 3 hosts for median
        config.use_median_of_three = True
        config.fallback_enabled = True
        config.fallback_check_gateway = True
        config.fallback_check_tcp = True
        config.fallback_gateway_ip = "10.0.0.1"
        config.fallback_tcp_targets = [["1.1.1.1", 443], ["8.8.8.8", 443]]
        config.fallback_mode = "graceful_degradation"
        config.fallback_max_cycles = 3
        config.metrics_enabled = False
        config.state_file = MagicMock()
        config.alerting_config = None
        config.signal_processing_config = {
            "hampel_window_size": 7,
            "hampel_sigma_threshold": 3.0,
            "jitter_time_constant_sec": 2.0,
            "variance_time_constant_sec": 5.0,
        }
        config.reflector_quality_config = {
            "min_score": 0.8,
            "window_size": 50,
            "probe_interval_sec": 30.0,
            "recovery_count": 3,
        }

        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = True
        router.rate_limit_params = {"max_changes": 5, "window_seconds": 10}
        rtt_measurement = MagicMock()
        logger = MagicMock()

        with patch.object(WANController, "load_state"):
            ctrl = WANController(
                wan_name="TestWAN",
                config=config,
                router=router,
                rtt_measurement=rtt_measurement,
                logger=logger,
            )
        return ctrl, config, logger

    def test_median_two_hosts_partial_success(self, controller_with_mocks):
        """When 3 active hosts but only 2 return RTT, average-of-2 is used.

        With reflector scoring, measure_rtt uses ping_hosts_with_results
        and applies graceful degradation: 2 results = average-of-2.
        """
        ctrl, config, logger = controller_with_mocks

        # 3 active hosts, but one fails
        ctrl.rtt_measurement.ping_hosts_with_results.return_value = {
            "1.1.1.1": 10.0,
            "8.8.8.8": 15.0,
            "9.9.9.9": None,
        }

        result = ctrl.measure_rtt()

        # Average of [10.0, 15.0] = 12.5 (graceful degradation: 2 results)
        assert result == 12.5
        ctrl.rtt_measurement.ping_hosts_with_results.assert_called_once()

    def test_median_one_host_minimal_success(self, controller_with_mocks):
        """When only 1 host returns RTT, that single value is returned.

        Graceful degradation: 1 result = single value.
        """
        ctrl, config, logger = controller_with_mocks

        # Only 1 host succeeds
        ctrl.rtt_measurement.ping_hosts_with_results.return_value = {
            "1.1.1.1": 10.0,
            "8.8.8.8": None,
            "9.9.9.9": None,
        }

        result = ctrl.measure_rtt()

        assert result == 10.0

    def test_median_all_hosts_fail_returns_none(self, controller_with_mocks):
        """When all hosts fail, None is returned and warning logged."""
        ctrl, config, logger = controller_with_mocks

        # All hosts fail
        ctrl.rtt_measurement.ping_hosts_with_results.return_value = {
            "1.1.1.1": None,
            "8.8.8.8": None,
            "9.9.9.9": None,
        }

        result = ctrl.measure_rtt()

        assert result is None
        # Warning should be logged
        logger.warning.assert_called_once()
        warning_msg = logger.warning.call_args[0][0]
        assert "All pings failed" in warning_msg

    def test_single_host_active(self, controller_with_mocks):
        """When only 1 host is active, single ping value returned.

        With reflector scoring, host selection is via get_active_hosts().
        Even with 1 active host, ping_hosts_with_results is used.
        """
        ctrl, config, logger = controller_with_mocks

        # Simulate single active host via reflector scorer
        ctrl._reflector_scorer._deprioritized = {"8.8.8.8", "9.9.9.9"}
        ctrl.rtt_measurement.ping_hosts_with_results.return_value = {"1.1.1.1": 22.5}

        result = ctrl.measure_rtt()

        assert result == 22.5
        ctrl.rtt_measurement.ping_hosts_with_results.assert_called_once()

    def test_median_three_hosts_all_success(self, controller_with_mocks):
        """When all 3 hosts return RTT, median of 3 values is returned.

        Validates core median-of-N behavior with reflector scoring.
        """
        ctrl, config, logger = controller_with_mocks

        # All 3 hosts respond
        ctrl.rtt_measurement.ping_hosts_with_results.return_value = {
            "1.1.1.1": 10.0,
            "8.8.8.8": 20.0,
            "9.9.9.9": 15.0,
        }

        result = ctrl.measure_rtt()

        # Median of [10.0, 20.0, 15.0] = 15.0
        assert result == 15.0
        logger.debug.assert_called()

    def test_two_hosts_active_average(self, controller_with_mocks):
        """When 2 hosts active and both succeed, average-of-2 is returned.

        Graceful degradation: 2 results = average (not median).
        """
        ctrl, config, logger = controller_with_mocks

        # Deprioritize one host so only 2 are active
        ctrl._reflector_scorer._deprioritized = {"9.9.9.9"}
        ctrl.rtt_measurement.ping_hosts_with_results.return_value = {
            "1.1.1.1": 10.0,
            "8.8.8.8": 20.0,
        }

        result = ctrl.measure_rtt()

        # Average of [10.0, 20.0] = 15.0
        assert result == 15.0


class TestRefractoryPeriod:
    """Tests for Phase 160 CAKE signal refractory period in WANController.

    DETECT-03: After dwell bypass, refractory counter masks CAKE snapshots
    for N cycles to prevent cascading rate reductions.
    """

    @pytest.fixture
    def mock_config(self, mock_autorate_config):
        """Delegate to shared mock_autorate_config from conftest.py."""
        return mock_autorate_config

    @pytest.fixture
    def mock_router(self):
        """Create a mock router."""
        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = True
        router.rate_limit_params = {"max_changes": 5, "window_seconds": 10}
        return router

    @pytest.fixture
    def controller(self, mock_config, mock_router):
        """Create a WANController with mocked dependencies for refractory tests."""
        from wanctl.wan_controller import WANController

        with patch.object(WANController, "load_state"):
            ctrl = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=mock_router,
                rtt_measurement=MagicMock(),
                logger=MagicMock(),
            )
        # Set baseline values needed for _run_congestion_assessment
        ctrl.baseline_rtt = 25.0
        ctrl.load_rtt = 30.0
        ctrl.green_threshold = 9.0
        ctrl.soft_red_threshold = 45.0
        ctrl.hard_red_threshold = 80.0
        ctrl.target_delta = 15.0
        ctrl.warn_delta = 45.0
        return ctrl

    def _make_snapshot(self):
        """Create a minimal CakeSignalSnapshot for testing."""
        from wanctl.cake_signal import CakeSignalSnapshot

        return CakeSignalSnapshot(
            drop_rate=20.0,
            total_drop_rate=25.0,
            backlog_bytes=5000,
            peak_delay_us=100,
            tins=(),
            cold_start=False,
        )

    def test_refractory_set_after_dwell_bypass(self, controller):
        """After dwell bypass, refractory counter set to configured value."""
        controller._refractory_cycles = 40
        controller._dl_refractory_remaining = 0
        controller._dl_cake_snapshot = self._make_snapshot()
        controller._ul_cake_snapshot = None

        # Mock download.adjust_4state to simulate normal return
        controller.download.adjust_4state = MagicMock(return_value=("GREEN", 800_000_000, None))
        controller.upload.adjust = MagicMock(return_value=("GREEN", 40_000_000, None))

        # Simulate dwell bypass happening during adjust_4state
        controller.download._dwell_bypassed_this_cycle = True
        controller.upload._dwell_bypassed_this_cycle = False

        controller._run_congestion_assessment()

        assert controller._dl_refractory_remaining == 40
        assert controller._ul_refractory_remaining == 0

    def test_refractory_masks_snapshot(self, controller):
        """During refractory, cake_snapshot passed as None (masked)."""
        controller._dl_refractory_remaining = 5
        controller._dl_cake_snapshot = self._make_snapshot()
        controller._ul_cake_snapshot = None

        controller.download.adjust_4state = MagicMock(return_value=("GREEN", 800_000_000, None))
        controller.upload.adjust = MagicMock(return_value=("GREEN", 40_000_000, None))
        controller.download._dwell_bypassed_this_cycle = False
        controller.upload._dwell_bypassed_this_cycle = False

        controller._run_congestion_assessment()

        # DL should have been called with cake_snapshot=None (masked)
        call_kwargs = controller.download.adjust_4state.call_args
        assert call_kwargs.kwargs.get("cake_snapshot") is None or call_kwargs[1].get("cake_snapshot") is None

    def test_refractory_decrements(self, controller):
        """Refractory counter decrements each cycle."""
        controller._dl_refractory_remaining = 3
        controller._dl_cake_snapshot = None
        controller._ul_cake_snapshot = None

        controller.download.adjust_4state = MagicMock(return_value=("GREEN", 800_000_000, None))
        controller.upload.adjust = MagicMock(return_value=("GREEN", 40_000_000, None))
        controller.download._dwell_bypassed_this_cycle = False
        controller.upload._dwell_bypassed_this_cycle = False

        controller._run_congestion_assessment()

        assert controller._dl_refractory_remaining == 2

    def test_refractory_zero_passes_snapshot(self, controller):
        """After refractory expires, cake_snapshot passed normally."""
        snapshot = self._make_snapshot()
        controller._dl_refractory_remaining = 0
        controller._dl_cake_snapshot = snapshot
        controller._ul_cake_snapshot = None

        controller.download.adjust_4state = MagicMock(return_value=("GREEN", 800_000_000, None))
        controller.upload.adjust = MagicMock(return_value=("GREEN", 40_000_000, None))
        controller.download._dwell_bypassed_this_cycle = False
        controller.upload._dwell_bypassed_this_cycle = False

        controller._run_congestion_assessment()

        # DL should have been called with the actual snapshot
        call_kwargs = controller.download.adjust_4state.call_args
        passed_snapshot = call_kwargs.kwargs.get("cake_snapshot") or call_kwargs[1].get("cake_snapshot")
        assert passed_snapshot is snapshot

    def test_dl_ul_refractory_independent(self, controller):
        """DL and UL refractory counters are independent."""
        snapshot = self._make_snapshot()
        controller._dl_refractory_remaining = 5
        controller._ul_refractory_remaining = 0
        controller._dl_cake_snapshot = snapshot
        controller._ul_cake_snapshot = snapshot

        controller.download.adjust_4state = MagicMock(return_value=("GREEN", 800_000_000, None))
        controller.upload.adjust = MagicMock(return_value=("GREEN", 40_000_000, None))
        controller.download._dwell_bypassed_this_cycle = False
        controller.upload._dwell_bypassed_this_cycle = False

        controller._run_congestion_assessment()

        # DL should be masked (refractory > 0)
        dl_kwargs = controller.download.adjust_4state.call_args
        dl_snap = dl_kwargs.kwargs.get("cake_snapshot") or dl_kwargs[1].get("cake_snapshot")
        assert dl_snap is None

        # UL should pass the snapshot (refractory == 0)
        ul_kwargs = controller.upload.adjust.call_args
        ul_snap = ul_kwargs.kwargs.get("cake_snapshot") or ul_kwargs[1].get("cake_snapshot")
        assert ul_snap is snapshot

    def test_refractory_reset_on_disable(self, controller):
        """Disabling cake_signal via SIGUSR1 resets refractory to 0."""
        import yaml

        from wanctl.cake_signal import CakeSignalConfig, CakeSignalProcessor
        from wanctl.wan_controller import WANController

        controller._dl_refractory_remaining = 15
        controller._ul_refractory_remaining = 10
        controller._cake_signal_supported = True
        controller._dl_cake_signal = CakeSignalProcessor(
            config=CakeSignalConfig(enabled=True)
        )
        controller._ul_cake_signal = CakeSignalProcessor(
            config=CakeSignalConfig(enabled=True)
        )

        # Write a YAML file that disables cake_signal
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"cake_signal": {"enabled": False}}, f)
            config_file = f.name

        try:
            controller.config.config_file_path = config_file
            # Bind real methods
            controller._parse_cake_signal_config = (
                WANController._parse_cake_signal_config.__get__(controller, WANController)
            )
            controller._reload_cake_signal_config = (
                WANController._reload_cake_signal_config.__get__(controller, WANController)
            )

            controller._reload_cake_signal_config()

            assert controller._dl_refractory_remaining == 0
            assert controller._ul_refractory_remaining == 0
        finally:
            os.unlink(config_file)


class TestBaselineRttBoundsRejection:
    """Tests for WANController._update_baseline_if_idle() bounds rejection.

    Covers lines 955-960: Security bounds check that rejects corrupted/invalid
    baseline values outside the [baseline_rtt_min, baseline_rtt_max] range.
    """

    @pytest.fixture
    def controller_with_mocks(self):
        """Create a WANController with all dependencies accessible."""
        from wanctl.wan_controller import WANController

        config = MagicMock()
        config.wan_name = "TestWAN"
        config.baseline_rtt_initial = 25.0
        config.download_floor_green = 800_000_000
        config.download_floor_yellow = 600_000_000
        config.download_floor_soft_red = 500_000_000
        config.download_floor_red = 400_000_000
        config.download_ceiling = 920_000_000
        config.download_step_up = 10_000_000
        config.download_factor_down = 0.85
        config.upload_floor_green = 35_000_000
        config.upload_floor_yellow = 30_000_000
        config.upload_floor_red = 25_000_000
        config.upload_ceiling = 40_000_000
        config.upload_step_up = 1_000_000
        config.upload_factor_down = 0.85
        config.target_bloat_ms = 15.0
        config.warn_bloat_ms = 45.0
        config.hard_red_bloat_ms = 80.0
        config.alpha_baseline = 0.1  # 10% weight for faster testing
        config.alpha_load = 0.1
        config.baseline_update_threshold_ms = 3.0
        config.baseline_rtt_min = 5.0  # Minimum sane baseline
        config.baseline_rtt_max = 100.0  # Maximum sane baseline
        config.accel_threshold_ms = 15.0
        config.accel_confirm_cycles = 3
        config.download_green_required = 5
        config.upload_green_required = 5
        config.ping_hosts = ["1.1.1.1"]
        config.use_median_of_three = False
        config.fallback_enabled = True
        config.fallback_check_gateway = True
        config.fallback_check_tcp = True
        config.fallback_gateway_ip = "10.0.0.1"
        config.fallback_tcp_targets = [["1.1.1.1", 443], ["8.8.8.8", 443]]
        config.fallback_mode = "graceful_degradation"
        config.fallback_max_cycles = 3
        config.metrics_enabled = False
        config.state_file = MagicMock()
        config.alerting_config = None
        config.signal_processing_config = {
            "hampel_window_size": 7,
            "hampel_sigma_threshold": 3.0,
            "jitter_time_constant_sec": 2.0,
            "variance_time_constant_sec": 5.0,
        }
        config.reflector_quality_config = {
            "min_score": 0.8,
            "window_size": 50,
            "probe_interval_sec": 30.0,
            "recovery_count": 3,
        }

        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = True
        router.rate_limit_params = {"max_changes": 5, "window_seconds": 10}
        rtt_measurement = MagicMock()
        logger = MagicMock()

        with patch.object(WANController, "load_state"):
            ctrl = WANController(
                wan_name="TestWAN",
                config=config,
                router=router,
                rtt_measurement=rtt_measurement,
                logger=logger,
            )
        return ctrl, config, logger

    def test_baseline_below_min_bound_rejected(self, controller_with_mocks):
        """Baseline RTT below min bound is rejected with warning.

        Covers lines 955-960: new_baseline < baseline_rtt_min case.

        Formula: new_baseline = (1 - alpha) * baseline + alpha * measured
        With alpha=0.1, baseline=10.0, we need measured_rtt that gives new < 5.0
        new = 0.9 * 10 + 0.1 * measured < 5
        9 + 0.1 * measured < 5
        0.1 * measured < -4  -> measured < -40

        This test uses a very low measured_rtt to push baseline below min.
        """
        ctrl, config, logger = controller_with_mocks
        ctrl.baseline_rtt = 10.0
        ctrl.load_rtt = 10.0  # delta = 0, so update will be attempted
        ctrl.baseline_update_threshold = 3.0
        ctrl.alpha_baseline = 0.1
        ctrl.baseline_rtt_min = 5.0
        ctrl.baseline_rtt_max = 100.0

        original_baseline = ctrl.baseline_rtt

        # measured_rtt = -50 would give new_baseline = 0.9*10 + 0.1*(-50) = 9 - 5 = 4.0 < 5.0
        ctrl._update_baseline_if_idle(-50.0)

        # Baseline should NOT be updated
        assert ctrl.baseline_rtt == original_baseline

        # Warning should be logged
        logger.warning.assert_called_once()
        warning_msg = logger.warning.call_args[0][0]
        assert "outside bounds" in warning_msg
        assert f"[{ctrl.baseline_rtt_min}-{ctrl.baseline_rtt_max}ms]" in warning_msg

    def test_baseline_above_max_bound_rejected(self, controller_with_mocks):
        """Baseline RTT above max bound is rejected with warning.

        Covers lines 955-960: new_baseline > baseline_rtt_max case.

        Uses a high alpha and baseline near max so that icmp_rtt can be within
        threshold distance of baseline while still pushing new_baseline over max.
        Formula: new_baseline = (1 - alpha) * baseline + alpha * icmp_rtt
        With alpha=0.5, baseline=99.0: new = 0.5*99 + 0.5*icmp_rtt
        icmp_rtt=101.5 -> delta=101.5-99=2.5 < 3.0 (passes freeze gate)
        new = 49.5 + 50.75 = 100.25 > 100.0 (exceeds max bound)
        """
        ctrl, config, logger = controller_with_mocks
        ctrl.baseline_rtt = 99.0
        ctrl.baseline_update_threshold = 3.0
        ctrl.alpha_baseline = 0.5
        ctrl.baseline_rtt_min = 5.0
        ctrl.baseline_rtt_max = 100.0

        original_baseline = ctrl.baseline_rtt

        # icmp_rtt=101.5: delta=101.5-99=2.5 < 3.0, new=0.5*99+0.5*101.5=100.25 > 100
        ctrl._update_baseline_if_idle(101.5)

        # Baseline should NOT be updated
        assert ctrl.baseline_rtt == original_baseline

        # Warning should be logged
        logger.warning.assert_called_once()
        warning_msg = logger.warning.call_args[0][0]
        assert "outside bounds" in warning_msg

    def test_baseline_within_bounds_accepted(self, controller_with_mocks):
        """Baseline RTT within bounds is accepted and updated.

        Validates that normal updates work when new_baseline is within bounds.
        icmp_rtt=27.0 with baseline=25.0: delta=27-25=2.0 < 3.0 (passes freeze gate).
        new_baseline = 0.9*25 + 0.1*27 = 22.5 + 2.7 = 25.2
        """
        ctrl, config, logger = controller_with_mocks
        ctrl.baseline_rtt = 25.0
        ctrl.baseline_update_threshold = 3.0
        ctrl.alpha_baseline = 0.1
        ctrl.baseline_rtt_min = 5.0
        ctrl.baseline_rtt_max = 100.0

        # icmp_rtt=27.0: delta=27-25=2.0 < 3.0, new=0.9*25+0.1*27=25.2
        ctrl._update_baseline_if_idle(27.0)

        # Baseline SHOULD be updated
        expected = 0.9 * 25.0 + 0.1 * 27.0  # 25.2
        assert ctrl.baseline_rtt == pytest.approx(expected, abs=0.01)

        # Debug log should be called (not warning)
        logger.debug.assert_called()
        logger.warning.assert_not_called()

    def test_baseline_at_exact_min_bound_accepted(self, controller_with_mocks):
        """Baseline RTT at exactly min bound is accepted (boundary condition).

        Tests the >= part of: baseline_rtt_min <= new_baseline
        """
        ctrl, config, logger = controller_with_mocks
        ctrl.baseline_rtt = 10.0
        ctrl.load_rtt = 10.0
        ctrl.baseline_update_threshold = 3.0
        ctrl.alpha_baseline = 0.5  # 50% weight to make math simpler
        ctrl.baseline_rtt_min = 5.0
        ctrl.baseline_rtt_max = 100.0

        # With alpha=0.5, baseline=10: new = 0.5*10 + 0.5*measured
        # To get exactly 5.0: 5 + 0.5*measured = 5 -> measured = 0
        ctrl._update_baseline_if_idle(0.0)

        # new_baseline = 0.5*10 + 0.5*0 = 5.0 which equals min, should be accepted
        assert ctrl.baseline_rtt == 5.0
        logger.warning.assert_not_called()

    def test_baseline_at_exact_max_bound_accepted(self, controller_with_mocks):
        """Baseline RTT at exactly max bound is accepted (boundary condition).

        Tests the <= part of: new_baseline <= baseline_rtt_max
        icmp_rtt=101.0 with baseline=99.0: delta=101-99=2.0 < 3.0 (passes freeze gate).
        new_baseline = 0.5*99 + 0.5*101 = 49.5 + 50.5 = 100.0 (exactly max, accepted).
        """
        ctrl, config, logger = controller_with_mocks
        ctrl.baseline_rtt = 99.0
        ctrl.baseline_update_threshold = 3.0
        ctrl.alpha_baseline = 0.5  # 50% weight
        ctrl.baseline_rtt_min = 5.0
        ctrl.baseline_rtt_max = 100.0

        # icmp_rtt=101.0: delta=101-99=2.0 < 3.0, new=0.5*99+0.5*101=100.0 (=max)
        ctrl._update_baseline_if_idle(101.0)

        # new_baseline = 100.0 which equals max, should be accepted
        assert ctrl.baseline_rtt == 100.0
        logger.warning.assert_not_called()


class TestBurstDetection:
    """Tests for corroborated burst detection in WANController."""

    @pytest.fixture
    def controller(self, mock_autorate_config):
        from wanctl.wan_controller import WANController

        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = True
        router.rate_limit_params = {"max_changes": 5, "window_seconds": 10}
        rtt_measurement = MagicMock()
        logger = MagicMock()

        with patch.object(WANController, "load_state"):
            ctrl = WANController(
                wan_name="TestWAN",
                config=mock_autorate_config,
                router=router,
                rtt_measurement=rtt_measurement,
                logger=logger,
            )
        return ctrl

    def test_run_spike_detection_arms_burst_when_delta_also_elevated(self, controller):
        controller.previous_load_rtt = 25.0
        controller.load_rtt = 42.5
        controller.baseline_rtt = 20.0
        controller._spike_streak = 2

        controller._run_spike_detection()

        assert controller._dl_burst_pending is True
        assert controller._dl_burst_reason is not None

    def test_run_spike_detection_requires_non_green_delta(self, controller):
        controller.previous_load_rtt = 5.0
        controller.load_rtt = 24.5
        controller.baseline_rtt = 20.0
        controller._spike_streak = 2

        controller._run_spike_detection()

        assert controller._dl_burst_pending is False
        assert controller._dl_burst_reason is None

    def test_run_spike_detection_latches_candidate_until_delta_corroborates(self, controller):
        controller.previous_load_rtt = 20.0
        controller.load_rtt = 40.0
        controller.baseline_rtt = 25.0
        controller._spike_streak = 2

        controller._run_spike_detection()

        assert controller._dl_burst_pending is False
        assert controller._dl_burst_candidate_cycles == 2

        controller.load_rtt = 42.0
        controller._run_spike_detection()

        assert controller._dl_burst_pending is True
        assert controller._dl_burst_reason is not None
        assert controller._dl_burst_trigger_count == 1


    def test_run_spike_detection_blocks_sustained_soft_red_burst_rearm(self, controller):
        controller.previous_load_rtt = 25.0
        controller.load_rtt = 42.5
        controller.baseline_rtt = 20.0
        controller._spike_streak = 2
        controller.download.soft_red_streak = controller.download.soft_red_required

        controller._run_spike_detection()

        assert controller._dl_burst_pending is False
        assert controller._dl_burst_reason is None


class TestBackgroundRttWiring:
    """Tests for background RTT thread cadence wiring."""

    @pytest.fixture
    def controller(self, mock_autorate_config):
        """Create a WANController with mocked dependencies."""
        from wanctl.wan_controller import WANController

        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = True
        router.rate_limit_params = {"max_changes": 5, "window_seconds": 10}
        rtt_measurement = MagicMock()
        logger = MagicMock()

        with patch.object(WANController, "load_state"):
            ctrl = WANController(
                wan_name="TestWAN",
                config=mock_autorate_config,
                router=router,
                rtt_measurement=rtt_measurement,
                logger=logger,
            )
        return ctrl

    def test_start_background_rtt_caps_probe_cadence(self, controller):
        """Background RTT cadence should not outrun the reflector probe floor."""
        shutdown_event = threading.Event()

        with (
            patch("wanctl.wan_controller.BackgroundRTTThread") as mock_thread_cls,
            patch("wanctl.wan_controller.concurrent.futures.ThreadPoolExecutor") as mock_pool_cls,
        ):
            mock_thread = MagicMock()
            mock_thread_cls.return_value = mock_thread

            controller.start_background_rtt(shutdown_event)

        _, pool_kwargs = mock_pool_cls.call_args
        _, kwargs = mock_thread_cls.call_args
        assert pool_kwargs["max_workers"] == max(3, len(controller.config.ping_hosts))
        assert kwargs["cadence_sec"] == pytest.approx(BACKGROUND_RTT_MIN_CADENCE_SECONDS)
        mock_thread.start.assert_called_once()

    def test_background_rtt_cadence_uses_controller_interval_when_slower(self, controller):
        """Controllers slower than the floor keep their own measurement cadence."""
        controller._cycle_interval_ms = 1000.0

        assert controller._background_rtt_cadence_sec() == pytest.approx(1.0)


class TestProtocolDeprioritizationFusionAwareCooldown:
    """Coverage for fusion-aware protocol deprioritization log cooldowns."""

    def _make_controller(
        self,
        mock_autorate_config,
        *,
        fusion_enabled=True,
        healer_present=True,
        healer_state=HealState.ACTIVE,
    ):
        from wanctl.wan_controller import WANController

        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = True
        router.rate_limit_params = {"max_changes": 5, "window_seconds": 10}
        logger = MagicMock()

        with patch.object(WANController, "load_state"):
            ctrl = WANController(
                wan_name="TestWAN",
                config=mock_autorate_config,
                router=router,
                rtt_measurement=MagicMock(),
                logger=logger,
            )

        ctrl.load_rtt = 48.0
        ctrl._irtt_thread = MagicMock()
        ctrl._irtt_thread.get_latest.return_value = MagicMock(rtt_mean_ms=24.0)
        ctrl._fusion_enabled = fusion_enabled
        ctrl._fusion_healer = (
            MagicMock(state=healer_state)
            if healer_present
            else None
        )
        return ctrl

    def _install_monotonic(self, monkeypatch, start):
        clock = {"now": float(start)}
        monkeypatch.setattr("wanctl.wan_controller.time.monotonic", lambda: clock["now"])
        return clock

    def test_first_occurrence_emits_info_when_fusion_active(
        self, mock_autorate_config, monkeypatch
    ):
        controller = self._make_controller(mock_autorate_config, healer_state=HealState.ACTIVE)
        clock = self._install_monotonic(monkeypatch, 100.0)

        controller._check_protocol_correlation(1.8)

        assert controller.logger.info.call_count == 1
        assert controller._irtt_deprioritization_logged is True
        assert controller._irtt_deprioritization_last_transition_ts == pytest.approx(clock["now"])

    def test_first_occurrence_emits_info_when_fusion_suspended(
        self, mock_autorate_config, monkeypatch
    ):
        controller = self._make_controller(
            mock_autorate_config,
            healer_state=HealState.SUSPENDED,
        )
        self._install_monotonic(monkeypatch, 100.0)

        controller._check_protocol_correlation(1.8)

        assert controller.logger.info.call_count == 1
        assert controller._irtt_deprioritization_logged is True

    def test_normal_cooldown_5s_when_fusion_active(
        self, mock_autorate_config, monkeypatch
    ):
        controller = self._make_controller(mock_autorate_config, healer_state=HealState.ACTIVE)
        clock = self._install_monotonic(monkeypatch, 100.0)

        controller._check_protocol_correlation(1.8)
        controller.logger.reset_mock()

        clock["now"] = 104.0
        controller._check_protocol_correlation(1.9)
        assert controller.logger.info.call_count == 0
        assert controller.logger.debug.call_count == 1
        assert controller._irtt_deprioritization_logged is True

        controller.logger.reset_mock()
        clock["now"] = 106.0
        controller._check_protocol_correlation(2.0)
        assert controller.logger.info.call_count == 0
        assert controller.logger.debug.call_count == 1
        assert controller._irtt_deprioritization_logged is True

    def test_stretched_cooldown_60s_when_fusion_suspended(
        self, mock_autorate_config, monkeypatch
    ):
        controller = self._make_controller(
            mock_autorate_config,
            healer_state=HealState.SUSPENDED,
        )
        clock = self._install_monotonic(monkeypatch, 100.0)

        controller._check_protocol_correlation(1.8)
        controller.logger.reset_mock()

        clock["now"] = 110.0
        controller._check_protocol_correlation(1.9)
        assert controller.logger.info.call_count == 0
        assert controller.logger.debug.call_count == 1
        assert controller._irtt_deprioritization_logged is True

        controller.logger.reset_mock()
        clock["now"] = 170.0
        controller._check_protocol_correlation(2.0)
        assert controller.logger.info.call_count == 0
        assert controller.logger.debug.call_count == 1
        assert controller._irtt_deprioritization_logged is True

    def test_recovery_path_uses_normal_cooldown_when_active(
        self, mock_autorate_config, monkeypatch
    ):
        controller = self._make_controller(mock_autorate_config, healer_state=HealState.ACTIVE)
        clock = self._install_monotonic(monkeypatch, 100.0)

        controller._check_protocol_correlation(1.8)
        controller.logger.reset_mock()

        clock["now"] = 104.0
        controller._check_protocol_correlation(1.0)
        assert controller.logger.info.call_count == 0
        assert controller._irtt_deprioritization_logged is False

        controller.logger.reset_mock()
        controller._irtt_deprioritization_logged = True
        controller._irtt_deprioritization_last_transition_ts = 100.0
        clock["now"] = 106.0
        controller._check_protocol_correlation(1.0)

        assert controller.logger.info.call_count == 1
        assert controller._irtt_deprioritization_logged is False

    def test_recovery_path_uses_stretched_cooldown_when_suspended(
        self, mock_autorate_config, monkeypatch
    ):
        controller = self._make_controller(
            mock_autorate_config,
            healer_state=HealState.SUSPENDED,
        )
        clock = self._install_monotonic(monkeypatch, 100.0)
        controller._irtt_deprioritization_logged = True
        controller._irtt_deprioritization_last_transition_ts = 100.0

        clock["now"] = 110.0
        controller._check_protocol_correlation(1.0)
        assert controller.logger.info.call_count == 0
        assert controller._irtt_deprioritization_logged is False

        controller.logger.reset_mock()
        controller._irtt_deprioritization_logged = True
        controller._irtt_deprioritization_last_transition_ts = 100.0
        clock["now"] = 161.0
        controller._check_protocol_correlation(1.0)

        assert controller.logger.info.call_count == 1
        assert controller._irtt_deprioritization_logged is False

    def test_fusion_transition_does_not_reset_latch(self, mock_autorate_config, monkeypatch):
        controller = self._make_controller(mock_autorate_config, healer_state=HealState.ACTIVE)
        clock = self._install_monotonic(monkeypatch, 100.0)

        controller._check_protocol_correlation(1.8)
        controller.logger.reset_mock()

        controller._fusion_healer.state = HealState.SUSPENDED
        clock["now"] = 110.0
        controller._check_protocol_correlation(1.8)

        assert controller._irtt_deprioritization_logged is True
        assert controller.logger.info.call_count == 0

    def test_fusion_state_transitions_never_mutate_latch(self, mock_autorate_config):
        controller = self._make_controller(mock_autorate_config, healer_state=HealState.ACTIVE)
        controller._irtt_deprioritization_logged = True

        for state in [HealState.SUSPENDED, HealState.RECOVERING, HealState.ACTIVE]:
            controller._fusion_healer.state = state
            assert controller._irtt_deprioritization_logged is True

    def test_none_healer_treated_as_not_actionable(self, mock_autorate_config, monkeypatch):
        controller = self._make_controller(
            mock_autorate_config,
            healer_present=False,
        )
        clock = self._install_monotonic(monkeypatch, 100.0)

        controller._check_protocol_correlation(1.8)
        controller.logger.reset_mock()

        clock["now"] = 110.0
        controller._check_protocol_correlation(1.9)
        assert controller.logger.info.call_count == 0
        assert controller.logger.debug.call_count == 1

    def test_fusion_disabled_treated_as_not_actionable(
        self, mock_autorate_config, monkeypatch
    ):
        controller = self._make_controller(
            mock_autorate_config,
            fusion_enabled=False,
            healer_state=HealState.ACTIVE,
        )
        clock = self._install_monotonic(monkeypatch, 100.0)

        controller._check_protocol_correlation(1.8)
        controller.logger.reset_mock()

        clock["now"] = 110.0
        controller._check_protocol_correlation(1.9)
        assert controller.logger.info.call_count == 0
        assert controller.logger.debug.call_count == 1

    def test_healer_recovering_treated_as_actionable(self, mock_autorate_config, monkeypatch):
        controller = self._make_controller(
            mock_autorate_config,
            healer_state=HealState.RECOVERING,
        )
        clock = self._install_monotonic(monkeypatch, 100.0)
        controller._irtt_deprioritization_logged = True
        controller._irtt_deprioritization_last_transition_ts = 100.0

        clock["now"] = 106.0
        controller._check_protocol_correlation(1.0)

        assert controller.logger.info.call_count == 1
        assert controller._irtt_deprioritization_logged is False


class TestZeroSuccessCycle:
    """Phase 187 zero-success cycle coverage for WANController.measure_rtt()."""

    @pytest.fixture
    def mock_wan_controller(self):
        wc = MagicMock()
        wc.wan_name = "spectrum"
        wc.logger = MagicMock()
        wc._reflector_scorer = MagicMock()
        wc._should_skip_scorer_update = lambda cycle_status: cycle_status.successful_count == 0
        wc._rtt_thread = MagicMock(spec=BackgroundRTTThread)
        wc._persist_reflector_events = MagicMock()
        wc._last_raw_rtt = None
        wc._last_raw_rtt_ts = None
        wc._last_active_reflector_hosts = []
        wc._last_successful_reflector_hosts = []
        wc._record_live_rtt_snapshot = MagicMock()
        wc.handle_icmp_failure = MagicMock()
        wc.icmp_unavailable_cycles = 0
        wc._zero_success_blackout_active = False
        wc._zero_success_blackout_started_ts = None
        wc._zero_success_blackout_cycles = 0
        wc._zero_success_last_log_ts = 0.0
        wc._zero_success_log_cooldown_sec = 1.0
        return wc

    def test_zero_success_preserves_cached_rtt_within_5s(self, mock_wan_controller):
        """Zero-success current cycle + cached snapshot <5s => return cached rtt_ms."""
        from wanctl.wan_controller import WANController

        snap = RTTSnapshot(
            rtt_ms=11.0,
            per_host_results={"a": 10.0, "b": 12.0, "c": 11.0},
            timestamp=time.monotonic() - 2.0,
            measurement_ms=30.0,
            active_hosts=("a", "b", "c"),
            successful_hosts=("a", "b", "c"),
        )
        status = RTTCycleStatus(
            successful_count=0,
            active_hosts=("a", "b", "c"),
            successful_hosts=(),
            cycle_timestamp=time.monotonic(),
        )
        mock_wan_controller._rtt_thread.get_latest.return_value = snap
        mock_wan_controller._rtt_thread.get_cycle_status.return_value = status

        result = WANController.measure_rtt(mock_wan_controller)

        assert result == 11.0

    def test_zero_success_overrides_successful_hosts(self, mock_wan_controller):
        """Zero-success current cycle => empty successful_hosts and current active_hosts."""
        from wanctl.wan_controller import WANController

        snap = RTTSnapshot(
            rtt_ms=11.0,
            per_host_results={"a": 10.0, "b": 12.0, "c": 11.0},
            timestamp=time.monotonic() - 1.0,
            measurement_ms=30.0,
            active_hosts=("a", "b", "c"),
            successful_hosts=("a", "b", "c"),
        )
        status = RTTCycleStatus(
            successful_count=0,
            active_hosts=("a", "b", "c"),
            successful_hosts=(),
            cycle_timestamp=time.monotonic(),
        )
        mock_wan_controller._rtt_thread.get_latest.return_value = snap
        mock_wan_controller._rtt_thread.get_cycle_status.return_value = status

        WANController.measure_rtt(mock_wan_controller)

        mock_wan_controller._record_live_rtt_snapshot.assert_called_once()
        kwargs = mock_wan_controller._record_live_rtt_snapshot.call_args.kwargs
        assert kwargs["successful_hosts"] == []
        assert kwargs["active_hosts"] == ["a", "b", "c"]

    def test_zero_success_does_not_touch_raw_rtt_timestamp(self, mock_wan_controller):
        """Phase 186 D-11 guardrail: timestamp must equal snap.timestamp."""
        from wanctl.wan_controller import WANController

        cached_ts = time.monotonic() - 1.5
        snap = RTTSnapshot(
            rtt_ms=11.0,
            per_host_results={"a": 10.0, "b": 12.0, "c": 11.0},
            timestamp=cached_ts,
            measurement_ms=30.0,
            active_hosts=("a", "b", "c"),
            successful_hosts=("a", "b", "c"),
        )
        status = RTTCycleStatus(
            successful_count=0,
            active_hosts=("a", "b", "c"),
            successful_hosts=(),
            cycle_timestamp=time.monotonic(),
        )
        mock_wan_controller._rtt_thread.get_latest.return_value = snap
        mock_wan_controller._rtt_thread.get_cycle_status.return_value = status

        WANController.measure_rtt(mock_wan_controller)

        kwargs = mock_wan_controller._record_live_rtt_snapshot.call_args.kwargs
        assert kwargs["timestamp"] == cached_ts
        assert kwargs["rtt_ms"] == 11.0

    def test_zero_success_does_not_invoke_handle_icmp_failure(self, mock_wan_controller):
        """SAFE-02: zero-success cycle does not escalate into ICMP fallback."""
        from wanctl.wan_controller import WANController

        snap = RTTSnapshot(
            rtt_ms=11.0,
            per_host_results={"a": 10.0, "b": 12.0, "c": 11.0},
            timestamp=time.monotonic() - 1.0,
            measurement_ms=30.0,
            active_hosts=("a", "b", "c"),
            successful_hosts=("a", "b", "c"),
        )
        status = RTTCycleStatus(
            successful_count=0,
            active_hosts=("a", "b", "c"),
            successful_hosts=(),
            cycle_timestamp=time.monotonic(),
        )
        mock_wan_controller._rtt_thread.get_latest.return_value = snap
        mock_wan_controller._rtt_thread.get_cycle_status.return_value = status

        WANController.measure_rtt(mock_wan_controller)

        mock_wan_controller.handle_icmp_failure.assert_not_called()
        assert mock_wan_controller.icmp_unavailable_cycles == 0

    def test_cycle_status_none_matches_today_behavior(self, mock_wan_controller):
        """First-cycle sentinel keeps pre-187 cached-host behavior intact."""
        from wanctl.wan_controller import WANController

        snap = RTTSnapshot(
            rtt_ms=11.0,
            per_host_results={"a": 10.0, "b": 12.0, "c": 11.0},
            timestamp=time.monotonic(),
            measurement_ms=30.0,
            active_hosts=("a", "b", "c"),
            successful_hosts=("a", "b", "c"),
        )
        mock_wan_controller._rtt_thread.get_latest.return_value = snap
        mock_wan_controller._rtt_thread.get_cycle_status.return_value = None

        result = WANController.measure_rtt(mock_wan_controller)

        assert result == 11.0
        kwargs = mock_wan_controller._record_live_rtt_snapshot.call_args.kwargs
        assert kwargs["successful_hosts"] == ["a", "b", "c"]
        assert kwargs["active_hosts"] == ["a", "b", "c"]

    def test_reflector_scorer_skipped_on_zero_success(self, mock_wan_controller):
        """Zero-success cycles should not replay cached per-host results into the scorer."""
        from wanctl.wan_controller import WANController

        snap = RTTSnapshot(
            rtt_ms=11.0,
            per_host_results={"a": 10.0, "b": 12.0, "c": 11.0},
            timestamp=time.monotonic() - 1.0,
            measurement_ms=30.0,
            active_hosts=("a", "b", "c"),
            successful_hosts=("a", "b", "c"),
        )
        status = RTTCycleStatus(
            successful_count=0,
            active_hosts=("a", "b", "c"),
            successful_hosts=(),
            cycle_timestamp=time.monotonic(),
        )
        mock_wan_controller._rtt_thread.get_latest.return_value = snap
        mock_wan_controller._rtt_thread.get_cycle_status.return_value = status

        WANController.measure_rtt(mock_wan_controller)

        assert mock_wan_controller._reflector_scorer.record_results.call_count == 0

    def test_zero_success_log_is_rate_limited_during_blackout(self, mock_wan_controller):
        """Repeated zero-success cycles should not spam warning logs every controller cycle."""
        from wanctl.wan_controller import WANController

        snap = RTTSnapshot(
            rtt_ms=11.0,
            per_host_results={"a": 10.0, "b": 12.0, "c": 11.0},
            timestamp=100.0,
            measurement_ms=30.0,
            active_hosts=("a", "b", "c"),
            successful_hosts=("a", "b", "c"),
        )
        status = RTTCycleStatus(
            successful_count=0,
            active_hosts=("a", "b", "c"),
            successful_hosts=(),
            cycle_timestamp=101.0,
        )
        mock_wan_controller._rtt_thread.get_latest.return_value = snap
        mock_wan_controller._rtt_thread.get_cycle_status.return_value = status

        with patch("wanctl.wan_controller.time.monotonic", side_effect=[101.0, 101.0, 101.2, 101.2]):
            WANController.measure_rtt(mock_wan_controller)
            WANController.measure_rtt(mock_wan_controller)

        assert mock_wan_controller.logger.warning.call_count == 1
        assert mock_wan_controller._zero_success_blackout_cycles == 2

    def test_success_after_zero_success_logs_recovery(self, mock_wan_controller):
        """First successful cycle after blackout should log a single recovery message."""
        from wanctl.wan_controller import WANController

        snap = RTTSnapshot(
            rtt_ms=11.0,
            per_host_results={"a": 10.0, "b": 12.0, "c": 11.0},
            timestamp=100.0,
            measurement_ms=30.0,
            active_hosts=("a", "b", "c"),
            successful_hosts=("a", "b", "c"),
        )
        zero_status = RTTCycleStatus(
            successful_count=0,
            active_hosts=("a", "b", "c"),
            successful_hosts=(),
            cycle_timestamp=101.0,
        )
        ok_status = RTTCycleStatus(
            successful_count=3,
            active_hosts=("a", "b", "c"),
            successful_hosts=("a", "b", "c"),
            cycle_timestamp=102.0,
        )
        mock_wan_controller._rtt_thread.get_latest.return_value = snap
        mock_wan_controller._rtt_thread.get_cycle_status.side_effect = [zero_status, ok_status]

        with patch("wanctl.wan_controller.time.monotonic", side_effect=[101.0, 101.0, 102.5, 102.5]):
            WANController.measure_rtt(mock_wan_controller)
            WANController.measure_rtt(mock_wan_controller)

        mock_wan_controller.logger.info.assert_called_once()
        assert mock_wan_controller._zero_success_blackout_active is False
        assert mock_wan_controller._zero_success_blackout_cycles == 0


class TestReflectorScorerBlackoutGate:
    """Authoritative controller x scorer regression coverage for blackout gating."""

    @pytest.fixture
    def controller(self, mock_autorate_config):
        from wanctl.wan_controller import WANController

        mock_autorate_config.wan_name = "TestWAN"
        mock_autorate_config.ping_hosts = ["h1", "h2", "h3"]
        mock_autorate_config.use_median_of_three = True

        router = MagicMock()
        router.set_limits.return_value = True
        router.needs_rate_limiting = True
        router.rate_limit_params = {"max_changes": 5, "window_seconds": 10}
        rtt_measurement = MagicMock()
        logger = MagicMock()

        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_autorate_config,
                router=router,
                rtt_measurement=rtt_measurement,
                logger=logger,
            )

        controller._reflector_scorer = ReflectorScorer(
            hosts=["h1", "h2", "h3"],
            min_score=0.8,
            window_size=50,
            probe_interval_sec=30.0,
            recovery_count=3,
            logger=logger,
            wan_name="TestWAN",
        )
        return controller

    @staticmethod
    def _window_lengths(controller):
        return {host: len(controller._reflector_scorer._windows[host]) for host in ["h1", "h2", "h3"]}

    @staticmethod
    def _success_counts(controller):
        return {host: controller._reflector_scorer._success_counts[host] for host in ["h1", "h2", "h3"]}

    def test_zero_success_cycle_skips_reflector_scorer_update(self, controller):
        snapshot = RTTSnapshot(
            rtt_ms=11.0,
            per_host_results={"h1": 10.0, "h2": None, "h3": 15.0},
            timestamp=time.monotonic(),
            measurement_ms=30.0,
            active_hosts=("h1", "h2", "h3"),
            successful_hosts=("h1", "h3"),
        )
        cycle_status = RTTCycleStatus(
            successful_count=0,
            active_hosts=("h1", "h2", "h3"),
            successful_hosts=(),
            cycle_timestamp=time.monotonic(),
        )
        controller._rtt_thread = MagicMock(spec=BackgroundRTTThread)
        controller._rtt_thread.get_latest.return_value = snapshot
        controller._rtt_thread.get_cycle_status.return_value = cycle_status

        before_lengths = self._window_lengths(controller)
        before_success_counts = self._success_counts(controller)

        result = controller.measure_rtt()

        assert result == 11.0
        assert self._window_lengths(controller) == before_lengths
        assert self._success_counts(controller) == before_success_counts

    def test_partial_success_cycle_still_updates_reflector_scorer(self, controller):
        snapshot = RTTSnapshot(
            rtt_ms=12.0,
            per_host_results={"h1": 10.0, "h2": None, "h3": 14.0},
            timestamp=time.monotonic(),
            measurement_ms=30.0,
            active_hosts=("h1", "h2", "h3"),
            successful_hosts=("h1", "h3"),
        )
        cycle_status = RTTCycleStatus(
            successful_count=2,
            active_hosts=("h1", "h2", "h3"),
            successful_hosts=("h1", "h3"),
            cycle_timestamp=time.monotonic(),
        )
        controller._rtt_thread = MagicMock(spec=BackgroundRTTThread)
        controller._rtt_thread.get_latest.return_value = snapshot
        controller._rtt_thread.get_cycle_status.return_value = cycle_status

        before_lengths = self._window_lengths(controller)

        controller.measure_rtt()

        after_lengths = self._window_lengths(controller)
        for host in snapshot.per_host_results:
            assert after_lengths[host] == before_lengths[host] + 1

    def test_blocking_path_all_fail_skips_scorer(self, controller):
        controller._rtt_thread = None
        controller.rtt_measurement.ping_hosts_with_results.return_value = {
            "h1": None,
            "h2": None,
            "h3": None,
        }

        before_lengths = self._window_lengths(controller)
        before_success_counts = self._success_counts(controller)

        result = controller.measure_rtt()

        assert result is None
        assert self._window_lengths(controller) == before_lengths
        assert self._success_counts(controller) == before_success_counts

    def test_blocking_path_partial_success_updates_scorer(self, controller):
        controller._rtt_thread = None
        controller.rtt_measurement.ping_hosts_with_results.return_value = {
            "h1": 10.0,
            "h2": None,
            "h3": 14.0,
        }

        before_lengths = self._window_lengths(controller)

        result = controller.measure_rtt()

        assert result == 12.0
        after_lengths = self._window_lengths(controller)
        for host in ["h1", "h2", "h3"]:
            assert after_lengths[host] == before_lengths[host] + 1

    def test_zero_success_cycle_still_drains_pending_scorer_events(self, controller, tmp_path):
        MetricsWriter._reset_instance()
        controller._metrics_writer = MetricsWriter(tmp_path / "reflector-events.db")
        controller._io_worker = None

        for _ in range(10):
            controller._reflector_scorer.record_result("h1", False)
        assert controller._reflector_scorer.has_pending_events() is True

        before_row_count = controller._metrics_writer.connection.execute(
            "SELECT COUNT(*) FROM reflector_events"
        ).fetchone()[0]

        snapshot = RTTSnapshot(
            rtt_ms=11.0,
            per_host_results={"h1": 10.0, "h2": None, "h3": 15.0},
            timestamp=time.monotonic(),
            measurement_ms=30.0,
            active_hosts=("h1", "h2", "h3"),
            successful_hosts=("h1", "h3"),
        )
        cycle_status = RTTCycleStatus(
            successful_count=0,
            active_hosts=("h1", "h2", "h3"),
            successful_hosts=(),
            cycle_timestamp=time.monotonic(),
        )
        controller._rtt_thread = MagicMock(spec=BackgroundRTTThread)
        controller._rtt_thread.get_latest.return_value = snapshot
        controller._rtt_thread.get_cycle_status.return_value = cycle_status

        before_lengths = self._window_lengths(controller)

        controller.measure_rtt()

        after_row_count = controller._metrics_writer.connection.execute(
            "SELECT COUNT(*) FROM reflector_events"
        ).fetchone()[0]
        assert controller._reflector_scorer.has_pending_events() is False
        assert after_row_count > before_row_count
        assert self._window_lengths(controller) == before_lengths
        MetricsWriter._reset_instance()
