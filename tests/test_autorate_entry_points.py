"""Tests for autorate_continuous main() entry points and signal integration.

Covers:
- validate-config mode (success, invalid, multiple files)
- oneshot mode (single cycle, debug flag)
- daemon mode startup (lock acquisition, signal handlers, servers)
- daemon mode shutdown (state save, lock release, connection close, server stop)
- control loop behavior (cycle execution, failure tracking, watchdog)
- signal handler integration (SIGTERM, SIGINT, shutdown event)

Coverage target: lines 1511-1808 (main() function) and signal integration paths.
"""

import argparse
import signal
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from wanctl.signal_utils import reset_shutdown_state


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def valid_config_yaml() -> str:
    """Minimal valid YAML config string for autorate_continuous."""
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
    - "8.8.8.8"
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
def invalid_config_yaml() -> str:
    """Invalid YAML config missing required fields."""
    return """
wan_name: TestWAN
# Missing router section
# Missing queues section
# Missing continuous_monitoring section
logging:
  main_log: "/tmp/test.log"
  debug_log: "/tmp/test_debug.log"

lock_file: "/tmp/test.lock"
lock_timeout: 300
"""


@pytest.fixture
def mock_controller():
    """Mock ContinuousAutoRate controller that returns successfully."""
    controller = MagicMock()
    controller.run_cycle.return_value = True
    controller.get_lock_paths.return_value = [Path("/tmp/test.lock")]
    controller.wan_controllers = [
        {
            "controller": MagicMock(),
            "config": MagicMock(
                lock_file=Path("/tmp/test.lock"),
                lock_timeout=300,
                metrics_enabled=False,
                health_check_enabled=False,
            ),
            "logger": MagicMock(),
        }
    ]
    return controller


# =============================================================================
# TestValidateConfigMode
# =============================================================================


class TestValidateConfigMode:
    """Tests for --validate-config mode."""

    def test_validate_config_success(self, valid_config_yaml, tmp_path, capsys):
        """Valid config prints success message and returns 0."""
        config_file = tmp_path / "valid.yaml"
        config_file.write_text(valid_config_yaml)

        with patch("sys.argv", ["autorate", "--config", str(config_file), "--validate-config"]):
            from wanctl.autorate_continuous import main

            result = main()

        assert result == 0
        captured = capsys.readouterr()
        assert "Configuration valid" in captured.out
        assert str(config_file) in captured.out

    def test_validate_config_invalid(self, invalid_config_yaml, tmp_path, capsys):
        """Invalid config prints error message and returns 1."""
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text(invalid_config_yaml)

        with patch("sys.argv", ["autorate", "--config", str(config_file), "--validate-config"]):
            from wanctl.autorate_continuous import main

            result = main()

        assert result == 1
        captured = capsys.readouterr()
        assert "Configuration INVALID" in captured.out

    def test_validate_config_multiple_files_all_valid(self, valid_config_yaml, tmp_path, capsys):
        """Multiple valid configs returns 0."""
        config1 = tmp_path / "valid1.yaml"
        config2 = tmp_path / "valid2.yaml"
        config1.write_text(valid_config_yaml)
        config2.write_text(valid_config_yaml.replace("TestWAN", "TestWAN2"))

        with patch(
            "sys.argv",
            ["autorate", "--config", str(config1), str(config2), "--validate-config"],
        ):
            from wanctl.autorate_continuous import main

            result = main()

        assert result == 0
        captured = capsys.readouterr()
        assert "Configuration valid" in captured.out

    def test_validate_config_multiple_files_one_invalid(
        self, valid_config_yaml, invalid_config_yaml, tmp_path, capsys
    ):
        """Mixed valid/invalid configs returns 1."""
        valid_file = tmp_path / "valid.yaml"
        invalid_file = tmp_path / "invalid.yaml"
        valid_file.write_text(valid_config_yaml)
        invalid_file.write_text(invalid_config_yaml)

        with patch(
            "sys.argv",
            ["autorate", "--config", str(valid_file), str(invalid_file), "--validate-config"],
        ):
            from wanctl.autorate_continuous import main

            result = main()

        assert result == 1
        captured = capsys.readouterr()
        assert "Configuration INVALID" in captured.out

    def test_validate_config_prints_wan_details(self, valid_config_yaml, tmp_path, capsys):
        """Validation output includes WAN name, transport, and floor details."""
        config_file = tmp_path / "valid.yaml"
        config_file.write_text(valid_config_yaml)

        with patch("sys.argv", ["autorate", "--config", str(config_file), "--validate-config"]):
            from wanctl.autorate_continuous import main

            main()

        captured = capsys.readouterr()
        assert "WAN: TestWAN" in captured.out
        assert "Transport: ssh" in captured.out
        assert "Floors:" in captured.out
        assert "GREEN=" in captured.out


# =============================================================================
# TestOneshotMode
# =============================================================================


class TestOneshotMode:
    """Tests for --oneshot mode."""

    def test_oneshot_runs_single_cycle(self, valid_config_yaml, tmp_path):
        """Oneshot mode calls run_cycle(use_lock=True) exactly once."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(valid_config_yaml)

        mock_controller = MagicMock()
        mock_controller.run_cycle.return_value = True

        with (
            patch("sys.argv", ["autorate", "--config", str(config_file), "--oneshot"]),
            patch(
                "wanctl.autorate_continuous.ContinuousAutoRate", return_value=mock_controller
            ),
        ):
            from wanctl.autorate_continuous import main

            main()

        mock_controller.run_cycle.assert_called_once_with(use_lock=True)

    def test_oneshot_returns_none_on_success(self, valid_config_yaml, tmp_path):
        """Oneshot mode returns None on success."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(valid_config_yaml)

        mock_controller = MagicMock()
        mock_controller.run_cycle.return_value = True

        with (
            patch("sys.argv", ["autorate", "--config", str(config_file), "--oneshot"]),
            patch(
                "wanctl.autorate_continuous.ContinuousAutoRate", return_value=mock_controller
            ),
        ):
            from wanctl.autorate_continuous import main

            result = main()

        assert result is None

    def test_oneshot_with_debug_flag(self, valid_config_yaml, tmp_path):
        """Debug flag is passed to controller in oneshot mode."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(valid_config_yaml)

        with (
            patch("sys.argv", ["autorate", "--config", str(config_file), "--oneshot", "--debug"]),
            patch("wanctl.autorate_continuous.ContinuousAutoRate") as MockController,
        ):
            mock_controller = MagicMock()
            mock_controller.run_cycle.return_value = True
            MockController.return_value = mock_controller

            from wanctl.autorate_continuous import main

            main()

        # Verify ContinuousAutoRate was called with debug=True
        MockController.assert_called_once()
        call_args = MockController.call_args
        assert call_args[1]["debug"] is True


# =============================================================================
# TestDaemonModeStartup
# =============================================================================


class TestDaemonModeStartup:
    """Tests for daemon mode startup sequence."""

    def test_daemon_acquires_lock_on_startup(self, valid_config_yaml, tmp_path):
        """Daemon mode calls validate_and_acquire_lock for each WAN."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(valid_config_yaml)

        mock_controller = MagicMock()
        mock_controller.get_lock_paths.return_value = [Path("/tmp/test.lock")]
        mock_controller.wan_controllers = [
            {
                "controller": MagicMock(),
                "config": MagicMock(
                    lock_timeout=300,
                    metrics_enabled=False,
                    health_check_enabled=False,
                ),
                "logger": MagicMock(),
            }
        ]

        with (
            patch("sys.argv", ["autorate", "--config", str(config_file)]),
            patch(
                "wanctl.autorate_continuous.ContinuousAutoRate", return_value=mock_controller
            ),
            patch(
                "wanctl.autorate_continuous.validate_and_acquire_lock", return_value=True
            ) as mock_lock,
            patch("wanctl.autorate_continuous.register_signal_handlers"),
            patch("wanctl.autorate_continuous.is_shutdown_requested", side_effect=[False, True]),
            patch("wanctl.autorate_continuous.time.sleep"),
        ):
            from wanctl.autorate_continuous import main

            main()

        mock_lock.assert_called_once()

    def test_daemon_refuses_start_when_locked(self, valid_config_yaml, tmp_path):
        """Daemon returns 1 if another instance is running (lock held)."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(valid_config_yaml)

        mock_controller = MagicMock()
        mock_controller.get_lock_paths.return_value = [Path("/tmp/test.lock")]
        mock_controller.wan_controllers = [
            {
                "controller": MagicMock(),
                "config": MagicMock(lock_timeout=300),
                "logger": MagicMock(),
            }
        ]

        with (
            patch("sys.argv", ["autorate", "--config", str(config_file)]),
            patch(
                "wanctl.autorate_continuous.ContinuousAutoRate", return_value=mock_controller
            ),
            patch("wanctl.autorate_continuous.validate_and_acquire_lock", return_value=False),
        ):
            from wanctl.autorate_continuous import main

            result = main()

        assert result == 1

    def test_daemon_registers_signal_handlers(self, valid_config_yaml, tmp_path):
        """Daemon mode registers signal handlers."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(valid_config_yaml)

        mock_controller = MagicMock()
        mock_controller.get_lock_paths.return_value = [Path("/tmp/test.lock")]
        mock_controller.wan_controllers = [
            {
                "controller": MagicMock(),
                "config": MagicMock(
                    lock_timeout=300,
                    metrics_enabled=False,
                    health_check_enabled=False,
                ),
                "logger": MagicMock(),
            }
        ]

        with (
            patch("sys.argv", ["autorate", "--config", str(config_file)]),
            patch(
                "wanctl.autorate_continuous.ContinuousAutoRate", return_value=mock_controller
            ),
            patch("wanctl.autorate_continuous.validate_and_acquire_lock", return_value=True),
            patch(
                "wanctl.autorate_continuous.register_signal_handlers"
            ) as mock_register_signals,
            patch("wanctl.autorate_continuous.is_shutdown_requested", side_effect=[False, True]),
            patch("wanctl.autorate_continuous.time.sleep"),
        ):
            from wanctl.autorate_continuous import main

            main()

        mock_register_signals.assert_called_once()

    def test_daemon_starts_metrics_server_when_enabled(self, valid_config_yaml, tmp_path):
        """Daemon starts metrics server when metrics_enabled=True."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(valid_config_yaml)

        mock_controller = MagicMock()
        mock_controller.get_lock_paths.return_value = [Path("/tmp/test.lock")]
        mock_controller.wan_controllers = [
            {
                "controller": MagicMock(),
                "config": MagicMock(
                    lock_timeout=300,
                    metrics_enabled=True,
                    metrics_host="127.0.0.1",
                    metrics_port=9100,
                    health_check_enabled=False,
                ),
                "logger": MagicMock(),
            }
        ]

        mock_metrics_server = MagicMock()

        with (
            patch("sys.argv", ["autorate", "--config", str(config_file)]),
            patch(
                "wanctl.autorate_continuous.ContinuousAutoRate", return_value=mock_controller
            ),
            patch("wanctl.autorate_continuous.validate_and_acquire_lock", return_value=True),
            patch("wanctl.autorate_continuous.register_signal_handlers"),
            patch(
                "wanctl.autorate_continuous.start_metrics_server",
                return_value=mock_metrics_server,
            ) as mock_start_metrics,
            patch("wanctl.autorate_continuous.is_shutdown_requested", side_effect=[False, True]),
            patch("wanctl.autorate_continuous.time.sleep"),
        ):
            from wanctl.autorate_continuous import main

            main()

        mock_start_metrics.assert_called_once_with(host="127.0.0.1", port=9100)

    def test_daemon_starts_health_server_when_enabled(self, valid_config_yaml, tmp_path):
        """Daemon starts health server when health_check_enabled=True."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(valid_config_yaml)

        mock_controller = MagicMock()
        mock_controller.get_lock_paths.return_value = [Path("/tmp/test.lock")]
        mock_controller.wan_controllers = [
            {
                "controller": MagicMock(),
                "config": MagicMock(
                    lock_timeout=300,
                    metrics_enabled=False,
                    health_check_enabled=True,
                    health_check_host="127.0.0.1",
                    health_check_port=9101,
                ),
                "logger": MagicMock(),
            }
        ]

        mock_health_server = MagicMock()

        with (
            patch("sys.argv", ["autorate", "--config", str(config_file)]),
            patch(
                "wanctl.autorate_continuous.ContinuousAutoRate", return_value=mock_controller
            ),
            patch("wanctl.autorate_continuous.validate_and_acquire_lock", return_value=True),
            patch("wanctl.autorate_continuous.register_signal_handlers"),
            patch(
                "wanctl.autorate_continuous.start_health_server",
                return_value=mock_health_server,
            ) as mock_start_health,
            patch("wanctl.autorate_continuous.is_shutdown_requested", side_effect=[False, True]),
            patch("wanctl.autorate_continuous.time.sleep"),
        ):
            from wanctl.autorate_continuous import main

            main()

        mock_start_health.assert_called_once_with(
            host="127.0.0.1",
            port=9101,
            controller=mock_controller,
        )


# =============================================================================
# TestDaemonModeShutdown
# =============================================================================


class TestDaemonModeShutdown:
    """Tests for daemon mode shutdown sequence."""

    def setup_method(self):
        """Reset shutdown state before each test."""
        reset_shutdown_state()

    def teardown_method(self):
        """Reset shutdown state after each test."""
        reset_shutdown_state()

    def test_shutdown_on_sigterm(self, valid_config_yaml, tmp_path):
        """Signal handler sets shutdown_event, causing loop to exit."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(valid_config_yaml)

        mock_controller = MagicMock()
        mock_controller.run_cycle.return_value = True
        mock_controller.get_lock_paths.return_value = [Path("/tmp/test.lock")]
        mock_wan_controller = MagicMock()
        mock_controller.wan_controllers = [
            {
                "controller": mock_wan_controller,
                "config": MagicMock(
                    lock_timeout=300,
                    metrics_enabled=False,
                    health_check_enabled=False,
                ),
                "logger": MagicMock(),
            }
        ]

        # Simulate: run 2 cycles, then shutdown requested
        with (
            patch("sys.argv", ["autorate", "--config", str(config_file)]),
            patch(
                "wanctl.autorate_continuous.ContinuousAutoRate", return_value=mock_controller
            ),
            patch("wanctl.autorate_continuous.validate_and_acquire_lock", return_value=True),
            patch("wanctl.autorate_continuous.register_signal_handlers"),
            patch(
                "wanctl.autorate_continuous.is_shutdown_requested",
                side_effect=[False, False, True, True],
            ),
            patch("wanctl.autorate_continuous.time.sleep"),
        ):
            from wanctl.autorate_continuous import main

            result = main()

        # Should exit cleanly
        assert result is None
        # Should have run cycles
        assert mock_controller.run_cycle.call_count >= 1

    def test_shutdown_saves_state(self, valid_config_yaml, tmp_path):
        """Shutdown calls save_state(force=True) for all WANs."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(valid_config_yaml)

        mock_wan_controller = MagicMock()
        mock_controller = MagicMock()
        mock_controller.run_cycle.return_value = True
        mock_controller.get_lock_paths.return_value = [Path("/tmp/test.lock")]
        mock_controller.wan_controllers = [
            {
                "controller": mock_wan_controller,
                "config": MagicMock(
                    lock_timeout=300,
                    metrics_enabled=False,
                    health_check_enabled=False,
                ),
                "logger": MagicMock(),
            }
        ]

        with (
            patch("sys.argv", ["autorate", "--config", str(config_file)]),
            patch(
                "wanctl.autorate_continuous.ContinuousAutoRate", return_value=mock_controller
            ),
            patch("wanctl.autorate_continuous.validate_and_acquire_lock", return_value=True),
            patch("wanctl.autorate_continuous.register_signal_handlers"),
            patch("wanctl.autorate_continuous.is_shutdown_requested", side_effect=[False, True]),
            patch("wanctl.autorate_continuous.time.sleep"),
        ):
            from wanctl.autorate_continuous import main

            main()

        # Verify save_state(force=True) was called in finally block
        mock_wan_controller.save_state.assert_called_with(force=True)

    def test_shutdown_releases_locks(self, valid_config_yaml, tmp_path):
        """Shutdown releases (unlinks) all lock files."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(valid_config_yaml)

        # Create actual lock file to verify it gets removed
        lock_file = tmp_path / "test.lock"
        lock_file.touch()

        mock_controller = MagicMock()
        mock_controller.run_cycle.return_value = True
        mock_controller.get_lock_paths.return_value = [lock_file]
        mock_controller.wan_controllers = [
            {
                "controller": MagicMock(),
                "config": MagicMock(
                    lock_timeout=300,
                    metrics_enabled=False,
                    health_check_enabled=False,
                ),
                "logger": MagicMock(),
            }
        ]

        with (
            patch("sys.argv", ["autorate", "--config", str(config_file)]),
            patch(
                "wanctl.autorate_continuous.ContinuousAutoRate", return_value=mock_controller
            ),
            patch("wanctl.autorate_continuous.validate_and_acquire_lock", return_value=True),
            patch("wanctl.autorate_continuous.register_signal_handlers"),
            patch("wanctl.autorate_continuous.is_shutdown_requested", side_effect=[False, True]),
            patch("wanctl.autorate_continuous.time.sleep"),
        ):
            from wanctl.autorate_continuous import main

            main()

        # Lock file should be removed
        assert not lock_file.exists()

    def test_shutdown_closes_router_connections(self, valid_config_yaml, tmp_path):
        """Shutdown closes SSH/REST router connections."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(valid_config_yaml)

        mock_router = MagicMock()
        mock_router.ssh = MagicMock()
        mock_wan_controller = MagicMock()
        mock_wan_controller.router = mock_router

        mock_controller = MagicMock()
        mock_controller.run_cycle.return_value = True
        mock_controller.get_lock_paths.return_value = [Path("/tmp/test.lock")]
        mock_controller.wan_controllers = [
            {
                "controller": mock_wan_controller,
                "config": MagicMock(
                    lock_timeout=300,
                    metrics_enabled=False,
                    health_check_enabled=False,
                ),
                "logger": MagicMock(),
            }
        ]

        with (
            patch("sys.argv", ["autorate", "--config", str(config_file)]),
            patch(
                "wanctl.autorate_continuous.ContinuousAutoRate", return_value=mock_controller
            ),
            patch("wanctl.autorate_continuous.validate_and_acquire_lock", return_value=True),
            patch("wanctl.autorate_continuous.register_signal_handlers"),
            patch("wanctl.autorate_continuous.is_shutdown_requested", side_effect=[False, True]),
            patch("wanctl.autorate_continuous.time.sleep"),
        ):
            from wanctl.autorate_continuous import main

            main()

        # Verify router.ssh.close() was called in finally block
        mock_router.ssh.close.assert_called_once()

    def test_shutdown_stops_servers(self, valid_config_yaml, tmp_path):
        """Shutdown stops metrics and health servers."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(valid_config_yaml)

        mock_controller = MagicMock()
        mock_controller.run_cycle.return_value = True
        mock_controller.get_lock_paths.return_value = [Path("/tmp/test.lock")]
        mock_controller.wan_controllers = [
            {
                "controller": MagicMock(),
                "config": MagicMock(
                    lock_timeout=300,
                    metrics_enabled=True,
                    metrics_host="127.0.0.1",
                    metrics_port=9100,
                    health_check_enabled=True,
                    health_check_host="127.0.0.1",
                    health_check_port=9101,
                ),
                "logger": MagicMock(),
            }
        ]

        mock_metrics_server = MagicMock()
        mock_health_server = MagicMock()

        with (
            patch("sys.argv", ["autorate", "--config", str(config_file)]),
            patch(
                "wanctl.autorate_continuous.ContinuousAutoRate", return_value=mock_controller
            ),
            patch("wanctl.autorate_continuous.validate_and_acquire_lock", return_value=True),
            patch("wanctl.autorate_continuous.register_signal_handlers"),
            patch(
                "wanctl.autorate_continuous.start_metrics_server",
                return_value=mock_metrics_server,
            ),
            patch(
                "wanctl.autorate_continuous.start_health_server",
                return_value=mock_health_server,
            ),
            patch("wanctl.autorate_continuous.is_shutdown_requested", side_effect=[False, True]),
            patch("wanctl.autorate_continuous.time.sleep"),
        ):
            from wanctl.autorate_continuous import main

            main()

        # Verify servers were stopped in finally block
        mock_metrics_server.stop.assert_called_once()
        mock_health_server.shutdown.assert_called_once()


# =============================================================================
# TestDaemonControlLoop
# =============================================================================


class TestDaemonControlLoop:
    """Tests for daemon control loop behavior."""

    def setup_method(self):
        """Reset shutdown state before each test."""
        reset_shutdown_state()

    def teardown_method(self):
        """Reset shutdown state after each test."""
        reset_shutdown_state()

    def test_control_loop_runs_cycles_until_shutdown(self, valid_config_yaml, tmp_path):
        """Control loop runs cycles until shutdown_event is set."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(valid_config_yaml)

        mock_controller = MagicMock()
        mock_controller.run_cycle.return_value = True
        mock_controller.get_lock_paths.return_value = [Path("/tmp/test.lock")]
        mock_controller.wan_controllers = [
            {
                "controller": MagicMock(),
                "config": MagicMock(
                    lock_timeout=300,
                    metrics_enabled=False,
                    health_check_enabled=False,
                ),
                "logger": MagicMock(),
            }
        ]

        # Run 5 cycles then shutdown
        shutdown_sequence = [False, False, False, False, False, True, True]

        with (
            patch("sys.argv", ["autorate", "--config", str(config_file)]),
            patch(
                "wanctl.autorate_continuous.ContinuousAutoRate", return_value=mock_controller
            ),
            patch("wanctl.autorate_continuous.validate_and_acquire_lock", return_value=True),
            patch("wanctl.autorate_continuous.register_signal_handlers"),
            patch(
                "wanctl.autorate_continuous.is_shutdown_requested",
                side_effect=shutdown_sequence,
            ),
            patch("wanctl.autorate_continuous.time.sleep"),
        ):
            from wanctl.autorate_continuous import main

            main()

        # Should have run cycles (at least 3)
        assert mock_controller.run_cycle.call_count >= 3

    def test_control_loop_tracks_consecutive_failures(self, valid_config_yaml, tmp_path):
        """Control loop tracks consecutive failure count."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(valid_config_yaml)

        mock_controller = MagicMock()
        # Fail first 2 cycles, then shutdown
        mock_controller.run_cycle.side_effect = [False, False, False]
        mock_controller.get_lock_paths.return_value = [Path("/tmp/test.lock")]
        mock_logger = MagicMock()
        mock_controller.wan_controllers = [
            {
                "controller": MagicMock(),
                "config": MagicMock(
                    lock_timeout=300,
                    metrics_enabled=False,
                    health_check_enabled=False,
                ),
                "logger": mock_logger,
            }
        ]

        with (
            patch("sys.argv", ["autorate", "--config", str(config_file)]),
            patch(
                "wanctl.autorate_continuous.ContinuousAutoRate", return_value=mock_controller
            ),
            patch("wanctl.autorate_continuous.validate_and_acquire_lock", return_value=True),
            patch("wanctl.autorate_continuous.register_signal_handlers"),
            patch(
                "wanctl.autorate_continuous.is_shutdown_requested",
                side_effect=[False, False, False, True, True],
            ),
            patch("wanctl.autorate_continuous.time.sleep"),
            patch("wanctl.autorate_continuous.notify_watchdog"),
            patch("wanctl.autorate_continuous.notify_degraded"),
        ):
            from wanctl.autorate_continuous import main

            main()

        # Should have logged warnings about failures
        warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
        failure_logged = any("Cycle failed" in str(c) for c in warning_calls)
        assert failure_logged

    def test_control_loop_notifies_watchdog_on_success(self, valid_config_yaml, tmp_path):
        """Control loop calls notify_watchdog when cycle succeeds."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(valid_config_yaml)

        mock_controller = MagicMock()
        mock_controller.run_cycle.return_value = True
        mock_controller.get_lock_paths.return_value = [Path("/tmp/test.lock")]
        mock_controller.wan_controllers = [
            {
                "controller": MagicMock(),
                "config": MagicMock(
                    lock_timeout=300,
                    metrics_enabled=False,
                    health_check_enabled=False,
                ),
                "logger": MagicMock(),
            }
        ]

        with (
            patch("sys.argv", ["autorate", "--config", str(config_file)]),
            patch(
                "wanctl.autorate_continuous.ContinuousAutoRate", return_value=mock_controller
            ),
            patch("wanctl.autorate_continuous.validate_and_acquire_lock", return_value=True),
            patch("wanctl.autorate_continuous.register_signal_handlers"),
            patch(
                "wanctl.autorate_continuous.is_shutdown_requested",
                side_effect=[False, False, True, True],
            ),
            patch("wanctl.autorate_continuous.time.sleep"),
            patch("wanctl.autorate_continuous.notify_watchdog") as mock_watchdog,
        ):
            from wanctl.autorate_continuous import main

            main()

        # Watchdog should be notified on success
        assert mock_watchdog.call_count >= 1

    def test_control_loop_notifies_degraded_on_max_failures(self, valid_config_yaml, tmp_path):
        """Control loop calls notify_degraded after MAX_CONSECUTIVE_FAILURES."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(valid_config_yaml)

        mock_controller = MagicMock()
        # Fail MAX_CONSECUTIVE_FAILURES (3) times
        mock_controller.run_cycle.return_value = False
        mock_controller.get_lock_paths.return_value = [Path("/tmp/test.lock")]
        mock_controller.wan_controllers = [
            {
                "controller": MagicMock(),
                "config": MagicMock(
                    lock_timeout=300,
                    metrics_enabled=False,
                    health_check_enabled=False,
                ),
                "logger": MagicMock(),
            }
        ]

        with (
            patch("sys.argv", ["autorate", "--config", str(config_file)]),
            patch(
                "wanctl.autorate_continuous.ContinuousAutoRate", return_value=mock_controller
            ),
            patch("wanctl.autorate_continuous.validate_and_acquire_lock", return_value=True),
            patch("wanctl.autorate_continuous.register_signal_handlers"),
            patch(
                "wanctl.autorate_continuous.is_shutdown_requested",
                side_effect=[False, False, False, False, True, True],
            ),
            patch("wanctl.autorate_continuous.time.sleep"),
            patch("wanctl.autorate_continuous.notify_watchdog"),
            patch("wanctl.autorate_continuous.notify_degraded") as mock_degraded,
        ):
            from wanctl.autorate_continuous import main

            main()

        # notify_degraded should be called after 3 consecutive failures
        assert mock_degraded.call_count >= 1

    def test_control_loop_sleeps_remainder_of_interval(self, valid_config_yaml, tmp_path):
        """Control loop sleeps for remainder of cycle interval."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(valid_config_yaml)

        mock_controller = MagicMock()
        mock_controller.run_cycle.return_value = True
        mock_controller.get_lock_paths.return_value = [Path("/tmp/test.lock")]
        mock_controller.wan_controllers = [
            {
                "controller": MagicMock(),
                "config": MagicMock(
                    lock_timeout=300,
                    metrics_enabled=False,
                    health_check_enabled=False,
                ),
                "logger": MagicMock(),
            }
        ]

        with (
            patch("sys.argv", ["autorate", "--config", str(config_file)]),
            patch(
                "wanctl.autorate_continuous.ContinuousAutoRate", return_value=mock_controller
            ),
            patch("wanctl.autorate_continuous.validate_and_acquire_lock", return_value=True),
            patch("wanctl.autorate_continuous.register_signal_handlers"),
            patch(
                "wanctl.autorate_continuous.is_shutdown_requested",
                side_effect=[False, False, True, True],
            ),
            patch("wanctl.autorate_continuous.time.sleep") as mock_sleep,
            patch("wanctl.autorate_continuous.time.monotonic", side_effect=[0, 0.01, 0.02, 0.03]),
        ):
            from wanctl.autorate_continuous import main

            main()

        # Sleep should be called with positive remainder
        assert mock_sleep.call_count >= 1


# =============================================================================
# TestSignalIntegration
# =============================================================================


class TestSignalIntegration:
    """Tests for signal handler integration with daemon control loop."""

    def setup_method(self):
        """Reset shutdown state before each test."""
        reset_shutdown_state()

    def teardown_method(self):
        """Reset shutdown state after each test."""
        reset_shutdown_state()

    def test_sigterm_triggers_graceful_shutdown(self, valid_config_yaml, tmp_path):
        """SIGTERM causes graceful shutdown via shutdown_event."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(valid_config_yaml)

        from wanctl.signal_utils import _signal_handler, is_shutdown_requested

        # Initially not shutdown
        assert not is_shutdown_requested()

        # Simulate SIGTERM
        _signal_handler(signal.SIGTERM, None)

        # Should now be shutdown
        assert is_shutdown_requested()

    def test_sigint_triggers_graceful_shutdown(self, valid_config_yaml, tmp_path):
        """SIGINT (Ctrl+C) causes graceful shutdown via shutdown_event."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(valid_config_yaml)

        from wanctl.signal_utils import _signal_handler, is_shutdown_requested

        # Initially not shutdown
        reset_shutdown_state()
        assert not is_shutdown_requested()

        # Simulate SIGINT
        _signal_handler(signal.SIGINT, None)

        # Should now be shutdown
        assert is_shutdown_requested()

    def test_shutdown_event_checked_each_iteration(self, valid_config_yaml, tmp_path):
        """is_shutdown_requested is called in each loop iteration."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(valid_config_yaml)

        mock_controller = MagicMock()
        mock_controller.run_cycle.return_value = True
        mock_controller.get_lock_paths.return_value = [Path("/tmp/test.lock")]
        mock_controller.wan_controllers = [
            {
                "controller": MagicMock(),
                "config": MagicMock(
                    lock_timeout=300,
                    metrics_enabled=False,
                    health_check_enabled=False,
                ),
                "logger": MagicMock(),
            }
        ]

        call_count = [0]
        original_side_effect = [False, False, False, True, True]

        def counting_is_shutdown():
            call_count[0] += 1
            if call_count[0] <= len(original_side_effect):
                return original_side_effect[call_count[0] - 1]
            return True

        with (
            patch("sys.argv", ["autorate", "--config", str(config_file)]),
            patch(
                "wanctl.autorate_continuous.ContinuousAutoRate", return_value=mock_controller
            ),
            patch("wanctl.autorate_continuous.validate_and_acquire_lock", return_value=True),
            patch("wanctl.autorate_continuous.register_signal_handlers"),
            patch(
                "wanctl.autorate_continuous.is_shutdown_requested",
                side_effect=counting_is_shutdown,
            ),
            patch("wanctl.autorate_continuous.time.sleep"),
        ):
            from wanctl.autorate_continuous import main

            main()

        # is_shutdown_requested should be called multiple times (at least once per iteration)
        assert call_count[0] >= 3
