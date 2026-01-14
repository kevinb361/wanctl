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
        with patch.object(controller, "verify_connectivity_fallback", return_value=True):
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

        with patch.object(controller, "verify_connectivity_fallback", return_value=True):
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

        with patch.object(controller, "verify_connectivity_fallback", return_value=True):
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

        with patch.object(controller, "verify_connectivity_fallback", return_value=True):
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

        with patch.object(controller, "verify_connectivity_fallback", return_value=True):
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

        with patch.object(controller, "verify_connectivity_fallback", return_value=True):
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

        with patch.object(controller, "verify_connectivity_fallback", return_value=True):
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

        with patch.object(controller, "verify_connectivity_fallback", return_value=True):
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

        with patch.object(controller, "verify_connectivity_fallback", return_value=True):
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

        with patch.object(controller, "verify_connectivity_fallback", return_value=False):
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

            with patch.object(controller, "verify_connectivity_fallback", return_value=False):
                should_continue, measured_rtt = controller.handle_icmp_failure()

            assert should_continue is False, f"Mode {mode} should fail on total loss"
            assert measured_rtt is None

    # =========================================================================
    # Unknown mode tests
    # =========================================================================

    def test_unknown_mode_returns_false(self, controller):
        """Unknown fallback mode should return (False, None) and log error."""
        controller.config.fallback_mode = "invalid_mode"
        controller.icmp_unavailable_cycles = 0
        controller.load_rtt = 28.5

        with patch.object(controller, "verify_connectivity_fallback", return_value=True):
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
            patch.object(controller, "verify_connectivity_fallback", return_value=True),
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
            patch.object(controller, "verify_connectivity_fallback", return_value=True),
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
