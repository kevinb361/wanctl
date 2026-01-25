"""Tests for WANController class in autorate_continuous module."""

from unittest.mock import MagicMock, patch

import pytest


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
    def mock_config(self):
        """Create a mock config for WANController."""
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
        config.download_green_required = 5
        config.upload_green_required = 5
        config.ping_hosts = ["1.1.1.1"]
        config.use_median_of_three = False
        config.fallback_enabled = True
        config.fallback_check_gateway = True
        config.fallback_check_tcp = True
        config.fallback_gateway_ip = "10.10.110.1"
        config.fallback_tcp_targets = [["1.1.1.1", 443], ["8.8.8.8", 443]]
        config.fallback_mode = "graceful_degradation"
        config.fallback_max_cycles = 3
        config.metrics_enabled = False
        config.state_file = MagicMock()
        return config

    @pytest.fixture
    def mock_router(self):
        """Create a mock router."""
        router = MagicMock()
        router.set_limits.return_value = True
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
        from wanctl.autorate_continuous import WANController

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

            with patch.object(controller, "verify_connectivity_fallback", return_value=(False, None)):
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
            patch("wanctl.autorate_continuous.record_ping_failure") as mock_record,
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
            patch("wanctl.autorate_continuous.record_ping_failure") as mock_record,
        ):
            controller.handle_icmp_failure()

        mock_record.assert_not_called()


class TestIcmpRecovery:
    """Tests for ICMP recovery behavior in run_cycle()."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock config for WANController."""
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
        config.download_green_required = 5
        config.upload_green_required = 5
        config.ping_hosts = ["1.1.1.1"]
        config.use_median_of_three = False
        config.fallback_enabled = True
        config.fallback_check_gateway = True
        config.fallback_check_tcp = True
        config.fallback_gateway_ip = "10.10.110.1"
        config.fallback_tcp_targets = [["1.1.1.1", 443], ["8.8.8.8", 443]]
        config.fallback_mode = "graceful_degradation"
        config.fallback_max_cycles = 3
        config.metrics_enabled = False
        config.state_file = MagicMock()
        return config

    @pytest.fixture
    def mock_router(self):
        """Create a mock router."""
        router = MagicMock()
        router.set_limits.return_value = True
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
        from wanctl.autorate_continuous import WANController

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
    def mock_config(self):
        """Create a mock config for WANController."""
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
        config.download_green_required = 5
        config.upload_green_required = 5
        config.ping_hosts = ["1.1.1.1"]
        config.use_median_of_three = False
        config.fallback_enabled = True
        config.fallback_check_gateway = True
        config.fallback_check_tcp = True
        config.fallback_gateway_ip = "10.10.110.1"
        config.fallback_tcp_targets = [["1.1.1.1", 443], ["8.8.8.8", 443]]
        config.fallback_mode = "graceful_degradation"
        config.fallback_max_cycles = 3
        config.metrics_enabled = False
        config.state_file = MagicMock()
        return config

    @pytest.fixture
    def mock_router(self):
        """Create a mock router."""
        router = MagicMock()
        router.set_limits.return_value = True
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
        from wanctl.autorate_continuous import WANController

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
            patch("wanctl.autorate_continuous.record_rate_limit_event") as mock_metric,
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
            patch("wanctl.autorate_continuous.record_rate_limit_event") as mock_metric,
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

        with patch("wanctl.autorate_continuous.record_router_update") as mock_metric:
            controller.apply_rate_changes_if_needed(90_000_000, 18_000_000)

        mock_metric.assert_called_once_with("TestWAN")

    def test_success_no_metric_when_disabled(self, controller, mock_router):
        """Successful update should not record metric when disabled."""
        controller.config.metrics_enabled = False
        controller.last_applied_dl_rate = 100_000_000
        controller.last_applied_ul_rate = 20_000_000

        with patch("wanctl.autorate_continuous.record_router_update") as mock_metric:
            controller.apply_rate_changes_if_needed(90_000_000, 18_000_000)

        mock_metric.assert_not_called()


class TestUpdateBaselineIfIdle:
    """Tests for WANController._update_baseline_if_idle() baseline protection.

    These tests validate the PROTECTED ZONE invariant: baseline RTT only updates
    when the line is idle (delta < threshold). This prevents baseline drift under
    load, which would mask true bloat detection.
    """

    @pytest.fixture
    def mock_config(self):
        """Create a mock config for WANController."""
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
        config.download_green_required = 5
        config.upload_green_required = 5
        config.ping_hosts = ["1.1.1.1"]
        config.use_median_of_three = False
        config.fallback_enabled = True
        config.fallback_check_gateway = True
        config.fallback_check_tcp = True
        config.fallback_gateway_ip = "10.10.110.1"
        config.fallback_tcp_targets = [["1.1.1.1", 443], ["8.8.8.8", 443]]
        config.fallback_mode = "graceful_degradation"
        config.fallback_max_cycles = 3
        config.metrics_enabled = False
        config.state_file = MagicMock()
        return config

    @pytest.fixture
    def mock_router(self):
        """Create a mock router."""
        router = MagicMock()
        router.set_limits.return_value = True
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
        from wanctl.autorate_continuous import WANController

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
    def mock_config(self):
        """Create a mock config for WANController."""
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
        config.download_green_required = 5
        config.upload_green_required = 5
        config.ping_hosts = ["1.1.1.1"]
        config.use_median_of_three = False
        config.fallback_enabled = True
        config.fallback_check_gateway = True
        config.fallback_check_tcp = True
        config.fallback_gateway_ip = "10.10.110.1"
        config.fallback_tcp_targets = [["1.1.1.1", 443], ["8.8.8.8", 443]]
        config.fallback_mode = "graceful_degradation"
        config.fallback_max_cycles = 3
        config.metrics_enabled = False
        config.state_file = MagicMock()
        return config

    @pytest.fixture
    def mock_router(self):
        """Create a mock router."""
        router = MagicMock()
        router.set_limits.return_value = True
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
        from wanctl.autorate_continuous import WANController

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
    def mock_config(self):
        """Create a mock config for WANController."""
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
        config.download_factor_down_yellow = 0.96
        config.download_green_required = 5
        config.upload_floor_green = 35_000_000
        config.upload_floor_yellow = 30_000_000
        config.upload_floor_red = 25_000_000
        config.upload_ceiling = 40_000_000
        config.upload_step_up = 1_000_000
        config.upload_factor_down = 0.85
        config.upload_factor_down_yellow = 0.94
        config.upload_green_required = 5
        config.target_bloat_ms = 15.0
        config.warn_bloat_ms = 45.0
        config.hard_red_bloat_ms = 80.0
        config.alpha_baseline = 0.001
        config.alpha_load = 0.1
        config.baseline_update_threshold_ms = 3.0
        config.baseline_rtt_min = 10.0
        config.baseline_rtt_max = 60.0
        config.accel_threshold_ms = 15.0
        config.ping_hosts = ["1.1.1.1"]
        config.use_median_of_three = False
        config.fallback_enabled = True
        config.fallback_check_gateway = True
        config.fallback_check_tcp = True
        config.fallback_gateway_ip = "10.10.110.1"
        config.fallback_tcp_targets = [["1.1.1.1", 443], ["8.8.8.8", 443]]
        config.fallback_mode = "graceful_degradation"
        config.fallback_max_cycles = 3
        config.metrics_enabled = False
        config.state_file = MagicMock()
        return config

    @pytest.fixture
    def mock_router(self):
        """Create a mock router."""
        router = MagicMock()
        router.set_limits.return_value = True
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
        from wanctl.autorate_continuous import WANController

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
        """Info log should contain zone and rates."""
        with (
            patch.object(controller, "measure_rtt", return_value=25.0),
            patch.object(controller, "save_state"),
        ):
            controller.run_cycle()

        # Check for info log with zone and rates
        info_calls = [str(call) for call in mock_logger.info.call_args_list]
        # Should contain zone info like "GREEN" or "YELLOW" and rate info like "DL="
        assert any("DL=" in call and "UL=" in call for call in info_calls)


class TestRunCycleMetrics:
    """Tests for run_cycle metrics recording."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock config for WANController with metrics enabled."""
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
        config.download_factor_down_yellow = 0.96
        config.download_green_required = 5
        config.upload_floor_green = 35_000_000
        config.upload_floor_yellow = 30_000_000
        config.upload_floor_red = 25_000_000
        config.upload_ceiling = 40_000_000
        config.upload_step_up = 1_000_000
        config.upload_factor_down = 0.85
        config.upload_factor_down_yellow = 0.94
        config.upload_green_required = 5
        config.target_bloat_ms = 15.0
        config.warn_bloat_ms = 45.0
        config.hard_red_bloat_ms = 80.0
        config.alpha_baseline = 0.001
        config.alpha_load = 0.1
        config.baseline_update_threshold_ms = 3.0
        config.baseline_rtt_min = 10.0
        config.baseline_rtt_max = 60.0
        config.accel_threshold_ms = 15.0
        config.ping_hosts = ["1.1.1.1"]
        config.use_median_of_three = False
        config.fallback_enabled = True
        config.fallback_check_gateway = True
        config.fallback_check_tcp = True
        config.fallback_gateway_ip = "10.10.110.1"
        config.fallback_tcp_targets = [["1.1.1.1", 443], ["8.8.8.8", 443]]
        config.fallback_mode = "graceful_degradation"
        config.fallback_max_cycles = 3
        config.metrics_enabled = True  # Enabled for these tests
        config.state_file = MagicMock()
        return config

    @pytest.fixture
    def mock_router(self):
        """Create a mock router."""
        router = MagicMock()
        router.set_limits.return_value = True
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
        from wanctl.autorate_continuous import WANController

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
            patch("wanctl.autorate_continuous.record_autorate_cycle") as mock_record,
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
            patch("wanctl.autorate_continuous.record_autorate_cycle") as mock_record,
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
        from wanctl.autorate_continuous import WANController

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

        router = MagicMock()
        router.set_limits.return_value = True
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
        from wanctl.autorate_continuous import WANController

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

        router = MagicMock()
        router.set_limits.return_value = True
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
        """When 2 hosts return RTT, median of 2 values is returned.

        Covers lines 897-902: len(rtts) >= 2 path with 2 values.
        """
        ctrl, config, logger = controller_with_mocks
        config.use_median_of_three = True
        config.ping_hosts = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
        ctrl.use_median_of_three = True
        ctrl.ping_hosts = config.ping_hosts

        # 2 hosts respond
        ctrl.rtt_measurement.ping_hosts_concurrent.return_value = [10.0, 15.0]

        result = ctrl.measure_rtt()

        # Median of [10.0, 15.0] = 12.5
        assert result == 12.5
        ctrl.rtt_measurement.ping_hosts_concurrent.assert_called_once()

    def test_median_one_host_minimal_success(self, controller_with_mocks):
        """When only 1 host returns RTT, that single value is returned.

        Covers lines 903-904: len(rtts) == 1 path.
        """
        ctrl, config, logger = controller_with_mocks
        config.use_median_of_three = True
        config.ping_hosts = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
        ctrl.use_median_of_three = True
        ctrl.ping_hosts = config.ping_hosts

        # Only 1 host responds
        ctrl.rtt_measurement.ping_hosts_concurrent.return_value = [10.0]

        result = ctrl.measure_rtt()

        assert result == 10.0

    def test_median_all_hosts_fail_returns_none(self, controller_with_mocks):
        """When all hosts fail, None is returned and warning logged.

        Covers lines 905-907: len(rtts) == 0 (empty) path.
        """
        ctrl, config, logger = controller_with_mocks
        config.use_median_of_three = True
        config.ping_hosts = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
        ctrl.use_median_of_three = True
        ctrl.ping_hosts = config.ping_hosts

        # All hosts fail
        ctrl.rtt_measurement.ping_hosts_concurrent.return_value = []

        result = ctrl.measure_rtt()

        assert result is None
        # Warning should be logged
        logger.warning.assert_called_once()
        warning_msg = logger.warning.call_args[0][0]
        assert "All pings failed" in warning_msg
        assert "median-of-three" in warning_msg

    def test_single_host_ping_path(self, controller_with_mocks):
        """When use_median_of_three=False, ping_host is used instead.

        Covers lines 908-910: else branch for single host ping.
        """
        ctrl, config, logger = controller_with_mocks
        config.use_median_of_three = False
        config.ping_hosts = ["1.1.1.1"]
        ctrl.use_median_of_three = False
        ctrl.ping_hosts = config.ping_hosts

        ctrl.rtt_measurement.ping_host.return_value = 22.5

        result = ctrl.measure_rtt()

        assert result == 22.5
        # ping_host should be called, not ping_hosts_concurrent
        ctrl.rtt_measurement.ping_host.assert_called_once_with("1.1.1.1", count=1)
        ctrl.rtt_measurement.ping_hosts_concurrent.assert_not_called()

    def test_median_three_hosts_all_success(self, controller_with_mocks):
        """When all 3 hosts return RTT, median of 3 values is returned.

        Validates core median-of-three behavior.
        """
        ctrl, config, logger = controller_with_mocks
        config.use_median_of_three = True
        config.ping_hosts = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
        ctrl.use_median_of_three = True
        ctrl.ping_hosts = config.ping_hosts

        # All 3 hosts respond
        ctrl.rtt_measurement.ping_hosts_concurrent.return_value = [10.0, 20.0, 15.0]

        result = ctrl.measure_rtt()

        # Median of [10.0, 20.0, 15.0] = 15.0
        assert result == 15.0
        logger.debug.assert_called()

    def test_median_fewer_than_three_hosts_in_config(self, controller_with_mocks):
        """When fewer than 3 ping_hosts configured, falls back to single ping.

        Covers line 890: condition check for len(ping_hosts) >= 3.
        """
        ctrl, config, logger = controller_with_mocks
        config.use_median_of_three = True
        config.ping_hosts = ["1.1.1.1", "8.8.8.8"]  # Only 2 hosts
        ctrl.use_median_of_three = True
        ctrl.ping_hosts = config.ping_hosts

        ctrl.rtt_measurement.ping_host.return_value = 18.0

        result = ctrl.measure_rtt()

        # Should fall back to single host ping
        assert result == 18.0
        ctrl.rtt_measurement.ping_host.assert_called_once()
        ctrl.rtt_measurement.ping_hosts_concurrent.assert_not_called()
