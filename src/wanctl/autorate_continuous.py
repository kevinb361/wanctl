#!/usr/bin/env python3
"""Continuous CAKE Auto-Tuning System daemon entry point and orchestrator.

Manages daemon lifecycle: argument parsing, storage initialization, lock
acquisition, server startup, and the main control loop. Delegates WAN
control to WANController instances via ContinuousAutoRate.
"""

import argparse
import atexit
import logging
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from wanctl.autorate_config import Config
from wanctl.config_base import ConfigValidationError, get_storage_config
from wanctl.config_validation_utils import validate_retention_tuner_compat
from wanctl.daemon_utils import check_cleanup_deadline
from wanctl.health_check import start_health_server, update_health_status
from wanctl.irtt_measurement import IRTTMeasurement
from wanctl.irtt_thread import IRTTThread
from wanctl.lock_utils import LockAcquisitionError, LockFile, validate_and_acquire_lock
from wanctl.logging_utils import setup_logging
from wanctl.metrics import (
    start_metrics_server,
)
from wanctl.router_client import clear_router_password
from wanctl.routeros_interface import RouterOS
from wanctl.rtt_measurement import (
    RTTAggregationStrategy,
    RTTMeasurement,
)
from wanctl.signal_utils import (
    SHUTDOWN_TIMEOUT_SECONDS,
    get_shutdown_event,
    is_reload_requested,
    is_shutdown_requested,
    register_signal_handlers,
    reset_reload_state,
)
from wanctl.storage import MetricsWriter
from wanctl.systemd_utils import (
    is_systemd_available,
    notify_degraded,
    notify_watchdog,
)
from wanctl.tuning.models import TuningConfig
from wanctl.wan_controller import (
    CYCLE_INTERVAL_SECONDS,
    WANController,
    _apply_tuning_to_controller,
)

# =============================================================================
# CONSTANTS
# =============================================================================

# Periodic maintenance interval (seconds) - cleanup/downsample/vacuum every hour
MAINTENANCE_INTERVAL = 3600


# =============================================================================
# MAIN CONTROLLER
# =============================================================================


class ContinuousAutoRate:
    """Main controller managing one or more WANs"""

    def __init__(self, config_files: list[str], debug: bool = False):
        self.wan_controllers: list[dict[str, Any]] = []
        self.debug = debug

        # Load each WAN config and create controller
        for config_file in config_files:
            config = Config(config_file)
            logger = setup_logging(config, "cake_continuous", debug)

            logger.info(f"=== Continuous CAKE Controller - {config.wan_name} ===")
            dl_green = config.download_floor_green / 1e6
            dl_yellow = config.download_floor_yellow / 1e6
            dl_soft_red = config.download_floor_soft_red / 1e6
            dl_red = config.download_floor_red / 1e6
            dl_ceil = config.download_ceiling / 1e6
            dl_step = config.download_step_up / 1e6
            logger.info(
                f"Download: GREEN={dl_green:.0f}M, YELLOW={dl_yellow:.0f}M, "
                f"SOFT_RED={dl_soft_red:.0f}M, RED={dl_red:.0f}M, "
                f"ceiling={dl_ceil:.0f}M, step={dl_step:.1f}M, "
                f"factor={config.download_factor_down}"
            )
            ul_green = config.upload_floor_green / 1e6
            ul_yellow = config.upload_floor_yellow / 1e6
            ul_red = config.upload_floor_red / 1e6
            ul_ceil = config.upload_ceiling / 1e6
            ul_step = config.upload_step_up / 1e6
            logger.info(
                f"Upload: GREEN={ul_green:.0f}M, YELLOW={ul_yellow:.0f}M, "
                f"RED={ul_red:.0f}M, ceiling={ul_ceil:.0f}M, "
                f"step={ul_step:.1f}M, factor={config.upload_factor_down}"
            )
            logger.info(
                f"Download Thresholds: GREEN→YELLOW={config.target_bloat_ms}ms, "
                f"YELLOW→SOFT_RED={config.warn_bloat_ms}ms, "
                f"SOFT_RED→RED={config.hard_red_bloat_ms}ms"
            )
            logger.info(
                f"Upload Thresholds: GREEN→YELLOW={config.target_bloat_ms}ms, "
                f"YELLOW→RED={config.warn_bloat_ms}ms"
            )
            logger.info(
                f"EWMA: baseline_alpha={config.alpha_baseline}, load_alpha={config.alpha_load}"
            )
            logger.info(
                f"Ping: hosts={config.ping_hosts}, median-of-three={config.use_median_of_three}"
            )

            # Create shared instances -- select backend based on transport config
            # Safety check: detect cake_params + non-linux-cake transport mismatch
            has_cake_params = isinstance(config.data.get("cake_params"), dict)
            if has_cake_params and config.router_transport != "linux-cake":
                logger.error(
                    "FATAL: cake_params section present but transport is '%s' (not 'linux-cake'). "
                    "CAKE qdiscs will NOT be created. Fix router.transport in YAML config.",
                    config.router_transport,
                )
                raise SystemExit(1)

            if config.router_transport == "linux-cake":
                from wanctl.backends.linux_cake_adapter import LinuxCakeAdapter

                router = LinuxCakeAdapter.from_config(config, logger)
            else:
                router = RouterOS(config, logger)
            clear_router_password(config)
            # Use unified RTTMeasurement with AVERAGE aggregation and sample stats logging
            rtt_measurement = RTTMeasurement(
                logger,
                timeout_ping=config.timeout_ping,
                aggregation_strategy=RTTAggregationStrategy.AVERAGE,
                log_sample_stats=True,  # Log min/max for debugging
                source_ip=config.ping_source_ip,
            )

            # Create WAN controller
            wan_controller = WANController(config.wan_name, config, router, rtt_measurement, logger)

            self.wan_controllers.append(
                {"controller": wan_controller, "config": config, "logger": logger}
            )

    def run_cycle(self, use_lock: bool = True) -> bool:
        """Run one cycle for all WANs

        Args:
            use_lock: If True, acquire lock per-cycle (oneshot mode).
                     If False, assume lock is already held (daemon mode).

        Returns:
            True if ALL WANs successfully completed cycle
            False if ANY WAN failed
        """
        all_success = True

        for wan_info in self.wan_controllers:
            controller = wan_info["controller"]
            config = wan_info["config"]
            logger = wan_info["logger"]

            try:
                if use_lock:
                    with LockFile(config.lock_file, config.lock_timeout, logger):
                        success = controller.run_cycle()
                        all_success = all_success and success
                else:
                    # Lock already held by daemon - just run the cycle
                    success = controller.run_cycle()
                    all_success = all_success and success
            except LockAcquisitionError:
                # Another instance is running - this is normal, not an error
                logger.debug("Skipping cycle - another instance is running")
                all_success = False
            except Exception as e:
                logger.error(f"Cycle error: {e}")
                logger.debug(traceback.format_exc())
                all_success = False

        return all_success

    def get_lock_paths(self) -> list[Path]:
        """Return lock file paths for all configured WANs"""
        return [wan_info["config"].lock_file for wan_info in self.wan_controllers]


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


def validate_config_mode(config_files: list[str]) -> int:
    """Validate configuration files and print details.

    Args:
        config_files: List of config file paths to validate.

    Returns:
        0 if all configs valid, 1 if any invalid.
    """
    all_valid = True
    for config_file in config_files:
        try:
            config = Config(config_file)
            print(f"Configuration valid: {config_file}")
            print(f"  WAN: {config.wan_name}")
            print(f"  Transport: {config.router_transport}")
            print(f"  Router: {config.router_host}:{config.router_user}")
            dl_min = config.download_floor_red / 1e6
            dl_max = config.download_ceiling / 1e6
            print(f"  Download: {dl_min:.0f}M - {dl_max:.0f}M")
            print(
                f"    Floors: GREEN={config.download_floor_green / 1e6:.0f}M, "
                f"YELLOW={config.download_floor_yellow / 1e6:.0f}M, "
                f"SOFT_RED={config.download_floor_soft_red / 1e6:.0f}M, "
                f"RED={config.download_floor_red / 1e6:.0f}M"
            )
            ul_min = config.upload_floor_red / 1e6
            ul_max = config.upload_ceiling / 1e6
            print(f"  Upload: {ul_min:.0f}M - {ul_max:.0f}M")
            print(
                f"    Floors: GREEN={config.upload_floor_green / 1e6:.0f}M, "
                f"YELLOW={config.upload_floor_yellow / 1e6:.0f}M, "
                f"RED={config.upload_floor_red / 1e6:.0f}M"
            )
            print(
                f"  Thresholds: GREEN<={config.target_bloat_ms}ms, "
                f"SOFT_RED<={config.warn_bloat_ms}ms, RED>{config.hard_red_bloat_ms}ms"
            )
            print(f"  Ping hosts: {config.ping_hosts}")
            print(f"  Queue names: {config.queue_down}, {config.queue_up}")
        except Exception as e:
            print(f"Configuration INVALID: {config_file}")
            print(f"  Error: {e}")
            all_valid = False
    return 0 if all_valid else 1


def _parse_autorate_args() -> argparse.Namespace:
    """Parse command-line arguments for the autorate daemon.

    Returns:
        Parsed argument namespace with config, debug, oneshot, validate_config,
        and profile flags.
    """
    parser = argparse.ArgumentParser(
        description="Continuous CAKE Auto-Tuning Daemon with 50ms Control Loop"
    )
    parser.add_argument(
        "--config",
        nargs="+",
        required=True,
        help="One or more config files (supports single-WAN or multi-WAN)",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug logging to console and debug log file"
    )
    parser.add_argument(
        "--oneshot", action="store_true", help="Run one cycle and exit (for testing/manual runs)"
    )
    parser.add_argument(
        "--validate-config",
        action="store_true",
        help="Validate configuration and exit (dry-run mode for CI/CD)",
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Enable periodic profiling reports (INFO level)",
    )
    return parser.parse_args()


def _init_storage(
    controller: "ContinuousAutoRate",
) -> tuple[Any, dict]:
    """Initialize storage, record config snapshot, and run startup maintenance.

    Args:
        controller: The ContinuousAutoRate instance (for config/logger access).

    Returns:
        Tuple of (maintenance_conn, maintenance_retention_config).
        maintenance_conn is None if storage is not enabled.
        maintenance_retention_config is the per-granularity retention dict.
    """
    first_config = controller.wan_controllers[0]["config"]
    storage_config = get_storage_config(first_config.data)
    db_path = storage_config.get("db_path")
    maintenance_conn = None
    default_retention = {
        "raw_age_seconds": 3600,
        "aggregate_1m_age_seconds": 86400,
        "aggregate_5m_age_seconds": 604800,
        "prometheus_compensated": False,
    }
    retention_raw = storage_config.get("retention")
    # Guard against MagicMock in tests (isinstance(dict) check)
    maintenance_retention_config = (
        retention_raw if isinstance(retention_raw, dict) else default_retention
    )

    # Cross-section validation: retention vs tuner data availability
    startup_logger = controller.wan_controllers[0]["logger"]
    validate_retention_tuner_compat(
        maintenance_retention_config,
        first_config.data.get("tuning") if isinstance(first_config.data, dict) else None,
        logger=startup_logger,
    )

    # Only record snapshot if db_path is a valid string (not MagicMock in tests)
    if db_path and isinstance(db_path, str):
        from wanctl.storage import MetricsWriter, record_config_snapshot, run_startup_maintenance

        writer = MetricsWriter(Path(db_path))
        maintenance_conn = writer.connection
        record_config_snapshot(writer, first_config.wan_name, first_config.data, "startup")

        # Run startup maintenance (cleanup + downsampling)
        # Pass watchdog callback and time budget to prevent exceeding WatchdogSec=30s
        maint_result = run_startup_maintenance(
            maintenance_conn,
            retention_config=maintenance_retention_config,
            log=startup_logger,
            watchdog_fn=notify_watchdog,
            max_seconds=20,
        )
        if maint_result.get("error"):
            startup_logger.warning(
                f"Startup maintenance error: {maint_result['error']}"
            )

    return maintenance_conn, maintenance_retention_config


def _acquire_daemon_locks(
    controller: "ContinuousAutoRate",
) -> tuple[list[Path], int | None]:
    """Acquire exclusive locks for all WAN controllers.

    Args:
        controller: The ContinuousAutoRate instance.

    Returns:
        Tuple of (lock_files, error_code). error_code is None on success,
        1 if lock acquisition failed.
    """
    lock_files: list[Path] = []
    for lock_path in controller.get_lock_paths():
        logger = controller.wan_controllers[0]["logger"]
        lock_timeout = controller.wan_controllers[0]["config"].lock_timeout
        try:
            if not validate_and_acquire_lock(lock_path, lock_timeout, logger):
                for wan_info in controller.wan_controllers:
                    wan_info["logger"].error("Another instance is running, refusing to start")
                return lock_files, 1
            lock_files.append(lock_path)
        except RuntimeError as e:
            for wan_info in controller.wan_controllers:
                wan_info["logger"].error(f"Failed to validate lock: {e}")
            return lock_files, 1
    return lock_files, None


def _start_servers(
    controller: "ContinuousAutoRate",
) -> tuple[Any, Any]:
    """Start optional metrics and health check servers.

    Args:
        controller: The ContinuousAutoRate instance.

    Returns:
        Tuple of (metrics_server, health_server). Either may be None if
        not configured or if startup fails (non-fatal).
    """
    metrics_server = None
    health_server = None
    first_config = controller.wan_controllers[0]["config"]

    if first_config.metrics_enabled:
        try:
            metrics_server = start_metrics_server(
                host=first_config.metrics_host,
                port=first_config.metrics_port,
            )
            for wan_info in controller.wan_controllers:
                wan_info["logger"].info(
                    f"Prometheus metrics available at "
                    f"http://{first_config.metrics_host}:{first_config.metrics_port}/metrics"
                )
        except OSError as e:
            for wan_info in controller.wan_controllers:
                wan_info["logger"].warning(f"Failed to start metrics server: {e}")

    if first_config.health_check_enabled:
        try:
            health_server = start_health_server(
                host=first_config.health_check_host,
                port=first_config.health_check_port,
                controller=controller,
            )
        except OSError as e:
            for wan_info in controller.wan_controllers:
                wan_info["logger"].warning(f"Failed to start health check server: {e}")

    return metrics_server, health_server


def _start_irtt_thread(
    controller: "ContinuousAutoRate",
) -> IRTTThread | None:
    """Start IRTT background measurement thread if IRTT is available.

    Returns None if IRTT is disabled or unavailable.
    """
    first_config = controller.wan_controllers[0]["config"]
    logger = controller.wan_controllers[0]["logger"]

    measurement = IRTTMeasurement(first_config.irtt_config, logger)
    if not measurement.is_available():
        return None

    shutdown_event = get_shutdown_event()
    cadence_sec = first_config.irtt_config.get("cadence_sec", 10.0)
    thread = IRTTThread(measurement, cadence_sec, shutdown_event, logger)
    thread.start()
    return thread


def main() -> int | None:
    """Main entry point for continuous CAKE auto-tuning daemon.

    Runs persistent bandwidth control with adaptive rate adjustment based on real-time
    latency measurements. Supports both single-WAN and multi-WAN configurations with
    concurrent control loops for each interface.

    The daemon operates in several modes:
    - **Daemon mode** (default): Runs continuous control loop at 50ms intervals,
      monitoring latency and adjusting CAKE queue limits to prevent bufferbloat while
      maximizing throughput. Handles SIGTERM/SIGINT gracefully and integrates with
      systemd watchdog for automatic recovery.
    - **Oneshot mode** (--oneshot): Executes single measurement and adjustment cycle,
      useful for testing and manual verification.
    - **Validation mode** (--validate-config): Validates configuration files and exits,
      ideal for CI/CD pipelines and pre-deployment checks.

    Startup sequence:
    1. Parse command-line arguments and load YAML configurations
    2. Initialize ContinuousAutoRate controller with per-WAN state machines
    3. Acquire exclusive locks to prevent concurrent instances
    4. Register signal handlers for graceful shutdown
    5. Start optional metrics (Prometheus) and health check servers
    6. Enter control loop with automatic watchdog notification

    Shutdown sequence (on SIGTERM/SIGINT):
    1. Stop accepting new cycles (shutdown_event set)
    2. Release all lock files
    3. Close router connections (SSH/REST)
    4. Shut down metrics and health servers
    5. Log clean shutdown and exit

    Returns:
        int | None: Exit code indicating daemon termination reason:
            - 0: Configuration validation passed (--validate-config mode)
            - 1: Configuration validation failed or lock acquisition failed
            - 130: Interrupted by signal (SIGINT/Ctrl+C)
            - None: Clean shutdown in daemon mode (SIGTERM or oneshot completion)
    """
    args = _parse_autorate_args()

    # Validate-config mode: check configuration and exit
    if args.validate_config:
        return validate_config_mode(args.config)

    # Create controller
    controller = ContinuousAutoRate(args.config, debug=args.debug)

    # Enable profiling on all WAN controllers if --profile flag set
    if args.profile:
        for wan_info in controller.wan_controllers:
            wan_info["controller"]._profiling_enabled = True

    # Initialize storage, record config snapshot, and run startup maintenance
    maintenance_conn, maintenance_retention_config = _init_storage(controller)

    # Oneshot mode for testing - use per-cycle locking
    if args.oneshot:
        controller.run_cycle(use_lock=True)
        return None

    # Daemon mode: continuous loop with 50ms cycle time
    # Acquire locks once at startup and hold for entire run
    lock_files, lock_error = _acquire_daemon_locks(controller)
    if lock_error is not None:
        return lock_error

    # Register emergency cleanup handler for abnormal termination (e.g., SIGKILL)
    # atexit handlers run on normal exit, sys.exit(), and unhandled exceptions
    # but NOT on SIGKILL - that's unavoidable. However, this covers more cases
    # than relying solely on the finally block.
    def emergency_lock_cleanup() -> None:
        """Emergency cleanup - runs via atexit if finally block doesn't complete."""
        for lock_path in lock_files:
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass  # Best effort - nothing we can do

    atexit.register(emergency_lock_cleanup)

    # Register signal handlers for graceful shutdown
    register_signal_handlers()

    consecutive_failures = 0
    MAX_CONSECUTIVE_FAILURES = 3
    watchdog_enabled = True
    last_maintenance = time.monotonic()
    last_tuning = time.monotonic()

    # Start optional servers (metrics, health check)
    metrics_server, health_server = _start_servers(controller)

    # Start IRTT background measurement thread (if configured)
    irtt_thread = _start_irtt_thread(controller)

    # Pass irtt_thread reference to each WAN controller
    for wan_info in controller.wan_controllers:
        wan_info["controller"]._irtt_thread = irtt_thread
        wan_info["controller"]._init_fusion_healer()

    # Start background RTT measurement threads (Phase 132: PERF-02)
    rtt_shutdown = get_shutdown_event()
    for wan_info in controller.wan_controllers:
        wan_info["controller"].start_background_rtt(rtt_shutdown)

    # Log startup
    for wan_info in controller.wan_controllers:
        wan_info["logger"].info(
            f"Starting daemon mode with {CYCLE_INTERVAL_SECONDS}s cycle interval"
        )
        if is_systemd_available():
            wan_info["logger"].info("Systemd watchdog support enabled")

    # Get shutdown event for interruptible sleep (instant signal responsiveness)
    shutdown_event = get_shutdown_event()

    try:
        while not is_shutdown_requested():
            cycle_start = time.monotonic()

            # Run cycle - returns True if successful
            cycle_success = controller.run_cycle(use_lock=False)  # Lock already held

            elapsed = time.monotonic() - cycle_start

            # Track consecutive failures
            if cycle_success:
                consecutive_failures = 0
                # Re-enable watchdog if previously surrendered (recovery)
                if not watchdog_enabled:
                    watchdog_enabled = True
                    for wan_info in controller.wan_controllers:
                        wan_info["logger"].info(
                            "Cycle recovered after watchdog surrender. "
                            "Re-enabling watchdog notifications."
                        )
            else:
                consecutive_failures += 1

                for wan_info in controller.wan_controllers:
                    wan_info["logger"].warning(
                        f"Cycle failed ({consecutive_failures}/{MAX_CONSECUTIVE_FAILURES})"
                    )

                # Check if we've exceeded failure threshold
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES and watchdog_enabled:
                    watchdog_enabled = False
                    for wan_info in controller.wan_controllers:
                        wan_info["logger"].error(
                            f"Sustained failure: {consecutive_failures} consecutive "
                            f"failed cycles. Stopping watchdog - systemd will terminate us."
                        )
                    notify_degraded("consecutive failures exceeded threshold")

            # Update health check endpoint with current failure count
            update_health_status(consecutive_failures)

            # Determine if failure is router-only (daemon healthy, router down)
            router_only_failure = False
            if not cycle_success:
                all_routers_unreachable = all(
                    not wan_info["controller"].router_connectivity.is_reachable
                    for wan_info in controller.wan_controllers
                )
                any_auth_failure = any(
                    wan_info["controller"].router_connectivity.last_failure_type == "auth_failure"
                    for wan_info in controller.wan_controllers
                )
                router_only_failure = all_routers_unreachable and not any_auth_failure

            # Notify systemd watchdog with router failure distinction (ERRR-04)
            if watchdog_enabled and cycle_success:
                notify_watchdog()
            elif watchdog_enabled and router_only_failure:
                notify_watchdog()
                for wan_info in controller.wan_controllers:
                    wan_info["logger"].info(
                        f"Router unreachable ({consecutive_failures} cycles), watchdog continues"
                    )
            elif not watchdog_enabled:
                notify_degraded(f"{consecutive_failures} consecutive failures")

            # Periodic maintenance: cleanup + downsample + vacuum every hour
            if maintenance_conn is not None:
                now = time.monotonic()
                if now - last_maintenance >= MAINTENANCE_INTERVAL:
                    maint_logger = controller.wan_controllers[0]["logger"]
                    try:
                        from wanctl.storage.downsampler import (
                            downsample_metrics,
                            get_downsample_thresholds,
                        )
                        from wanctl.storage.retention import cleanup_old_metrics, vacuum_if_needed

                        deleted = cleanup_old_metrics(
                            maintenance_conn,
                            retention_config=maintenance_retention_config,
                            watchdog_fn=notify_watchdog,
                        )
                        notify_watchdog()

                        custom_thresholds = get_downsample_thresholds(
                            raw_age_seconds=maintenance_retention_config["raw_age_seconds"],
                            aggregate_1m_age_seconds=maintenance_retention_config["aggregate_1m_age_seconds"],
                            aggregate_5m_age_seconds=maintenance_retention_config["aggregate_5m_age_seconds"],
                        )
                        downsampled = downsample_metrics(
                            maintenance_conn,
                            watchdog_fn=notify_watchdog,
                            thresholds=custom_thresholds,
                        )
                        notify_watchdog()

                        vacuumed = vacuum_if_needed(maintenance_conn, deleted)
                        notify_watchdog()

                        # Truncate WAL file to reclaim disk/page-cache
                        wal_result = maintenance_conn.execute(
                            "PRAGMA wal_checkpoint(TRUNCATE)"
                        ).fetchone()
                        wal_truncated = wal_result and wal_result[1] and wal_result[1] > 0
                        notify_watchdog()

                        total_ds = sum(downsampled.values())
                        if deleted > 0 or total_ds > 0 or vacuumed or wal_truncated:
                            maint_logger.info(
                                "Periodic maintenance: deleted=%d, downsampled=%d, vacuumed=%s, wal_truncated=%s",
                                deleted,
                                total_ds,
                                vacuumed,
                                wal_truncated,
                            )
                    except Exception as e:
                        maint_logger.error("Periodic maintenance failed: %s", e)

                    last_maintenance = now

            # Adaptive tuning (runs after maintenance, on its own cadence)
            tuning_config = getattr(
                controller.wan_controllers[0]["controller"],
                "tuning_config",
                None,
            )
            if isinstance(tuning_config, TuningConfig) and tuning_config.enabled:
                now = time.monotonic()
                tuning_cadence = tuning_config.cadence_sec
                if now - last_tuning >= tuning_cadence:
                    from wanctl.tuning.analyzer import run_tuning_analysis
                    from wanctl.tuning.applier import (
                        apply_tuning_results,
                        persist_revert_record,
                    )
                    from wanctl.tuning.safety import (
                        DEFAULT_MIN_CONGESTION_RATE,
                        DEFAULT_REVERT_COOLDOWN_SEC,
                        DEFAULT_REVERT_THRESHOLD,
                        PendingObservation,
                        check_and_revert,
                        is_parameter_locked,
                        lock_parameter,
                        measure_congestion_rate,
                    )
                    from wanctl.tuning.strategies.advanced import (
                        tune_baseline_bounds_max,
                        tune_baseline_bounds_min,
                        tune_fusion_weight,
                        tune_reflector_min_score,
                    )
                    from wanctl.tuning.strategies.congestion_thresholds import (
                        calibrate_target_bloat,
                        calibrate_warn_bloat,
                    )
                    from wanctl.tuning.strategies.response import (
                        check_oscillation_lockout,
                        tune_dl_factor_down,
                        tune_dl_green_required,
                        tune_dl_step_up,
                        tune_ul_factor_down,
                        tune_ul_green_required,
                        tune_ul_step_up,
                    )
                    from wanctl.tuning.strategies.signal_processing import (
                        tune_alpha_load,
                        tune_hampel_sigma,
                        tune_hampel_window,
                    )

                    first_config = controller.wan_controllers[0]["config"]
                    storage_config = get_storage_config(first_config.data)
                    db_path = storage_config.get("db_path", "")
                    metrics_writer = controller.wan_controllers[0]["controller"]._metrics_writer

                    # Layer definitions for bottom-up tuning (SIGP-04)
                    SIGNAL_LAYER = [
                        ("hampel_sigma_threshold", tune_hampel_sigma),
                        ("hampel_window_size", tune_hampel_window),
                    ]
                    EWMA_LAYER = [
                        ("load_time_constant_sec", tune_alpha_load),
                    ]
                    THRESHOLD_LAYER = [
                        ("target_bloat_ms", calibrate_target_bloat),
                        ("warn_bloat_ms", calibrate_warn_bloat),
                    ]
                    ADVANCED_LAYER = [
                        ("fusion_icmp_weight", tune_fusion_weight),
                        ("reflector_min_score", tune_reflector_min_score),
                        ("baseline_rtt_min", tune_baseline_bounds_min),
                        ("baseline_rtt_max", tune_baseline_bounds_max),
                    ]
                    RESPONSE_LAYER = [
                        ("dl_step_up_mbps", tune_dl_step_up),
                        ("ul_step_up_mbps", tune_ul_step_up),
                        ("dl_factor_down", tune_dl_factor_down),
                        ("ul_factor_down", tune_ul_factor_down),
                        ("dl_green_required", tune_dl_green_required),
                        ("ul_green_required", tune_ul_green_required),
                    ]
                    ALL_LAYERS = [SIGNAL_LAYER, EWMA_LAYER, THRESHOLD_LAYER, ADVANCED_LAYER, RESPONSE_LAYER]

                    for wan_info in controller.wan_controllers:
                        wc = wan_info["controller"]
                        if not wc._tuning_enabled:
                            continue

                        # Step 1: Check pending observation from previous cycle
                        try:
                            reverts = check_and_revert(
                                wc._pending_observation,
                                db_path,
                                wc.wan_name,
                                revert_threshold=DEFAULT_REVERT_THRESHOLD,
                                min_congestion_rate=DEFAULT_MIN_CONGESTION_RATE,
                            )
                            if reverts:
                                _apply_tuning_to_controller(wc, reverts)
                                for rv in reverts:
                                    persist_revert_record(rv, metrics_writer)
                                    lock_parameter(
                                        wc._parameter_locks,
                                        rv.parameter,
                                        DEFAULT_REVERT_COOLDOWN_SEC,
                                    )
                                    wan_info["logger"].error(
                                        "[TUNING] %s: %s",
                                        wc.wan_name,
                                        rv.rationale,
                                    )
                        except Exception as e:
                            wan_info["logger"].error(
                                "[TUNING] Revert check failed for %s: %s",
                                wc.wan_name,
                                e,
                            )
                        wc._pending_observation = None  # Clear regardless

                        # Step 2: Select active layer via round-robin (SIGP-04)
                        active_layer = ALL_LAYERS[wc._tuning_layer_index % len(ALL_LAYERS)]
                        wc._tuning_layer_index += 1

                        # Step 2.5: Oscillation lockout for response layer (RTUN-04)
                        if active_layer is RESPONSE_LAYER:
                            try:
                                from wanctl.tuning.analyzer import _query_wan_metrics

                                osc_metrics = _query_wan_metrics(
                                    db_path, wc.wan_name, tuning_config.lookback_hours
                                )
                                check_oscillation_lockout(
                                    osc_metrics,
                                    wc._parameter_locks,
                                    getattr(wc, "_oscillation_threshold", 0.1),
                                    getattr(wc, "_alert_engine", None),
                                    wc.wan_name,
                                )
                            except Exception as e:
                                wan_info["logger"].debug(
                                    "[TUNING] %s: oscillation check failed: %s",
                                    wc.wan_name,
                                    e,
                                )

                        # Step 3: Filter excluded and locked parameters from active layer
                        excluded = tuning_config.exclude_params
                        active_strategies = [
                            (pname, sfn)
                            for pname, sfn in active_layer
                            if pname not in excluded
                            and not is_parameter_locked(wc._parameter_locks, pname)
                        ]
                        for pname, _ in active_layer:
                            if pname in excluded:
                                wan_info["logger"].debug(
                                    "[TUNING] %s: %s excluded via config",
                                    wc.wan_name,
                                    pname,
                                )
                            elif is_parameter_locked(wc._parameter_locks, pname):
                                wan_info["logger"].info(
                                    "[TUNING] %s: %s locked until revert cooldown expires",
                                    wc.wan_name,
                                    pname,
                                )

                        # Step 4: Run analysis with active (unlocked) strategies
                        current_params = {
                            "target_bloat_ms": wc.green_threshold,
                            "warn_bloat_ms": wc.soft_red_threshold,
                            "hard_red_bloat_ms": wc.hard_red_threshold,
                            "alpha_load": wc.alpha_load,
                            "alpha_baseline": wc.alpha_baseline,
                            "hampel_sigma_threshold": wc.signal_processor._sigma_threshold,
                            "hampel_window_size": float(wc.signal_processor._window_size),
                            "load_time_constant_sec": 0.05 / wc.alpha_load,
                            "fusion_icmp_weight": wc._fusion_icmp_weight,
                            "reflector_min_score": wc._reflector_scorer._min_score,
                            "baseline_rtt_min": wc.baseline_rtt_min,
                            "baseline_rtt_max": wc.baseline_rtt_max,
                            "dl_step_up_mbps": wc.download.step_up_bps / 1e6,
                            "ul_step_up_mbps": wc.upload.step_up_bps / 1e6,
                            "dl_factor_down": wc.download.factor_down,
                            "ul_factor_down": wc.upload.factor_down,
                            "dl_green_required": float(wc.download.green_required),
                            "ul_green_required": float(wc.upload.green_required),
                        }
                        try:
                            results = run_tuning_analysis(
                                wan_name=wc.wan_name,
                                db_path=db_path,
                                tuning_config=tuning_config,
                                current_params=current_params,
                                strategies=active_strategies,
                            )
                            if results:
                                applied = apply_tuning_results(
                                    results, tuning_config, metrics_writer
                                )
                                if applied:
                                    _apply_tuning_to_controller(wc, applied)
                                    # Step 5: Snapshot pre-adjustment congestion rate
                                    pre_rate = measure_congestion_rate(
                                        db_path,
                                        wc.wan_name,
                                        start_ts=int(time.time()) - tuning_config.cadence_sec,
                                        end_ts=int(time.time()),
                                    )
                                    if pre_rate is not None:
                                        wc._pending_observation = PendingObservation(
                                            applied_ts=int(time.time()),
                                            pre_congestion_rate=pre_rate,
                                            applied_results=tuple(applied),
                                        )
                        except Exception as e:
                            wan_info["logger"].error(
                                "[TUNING] Analysis failed for %s: %s",
                                wc.wan_name,
                                e,
                            )
                    last_tuning = now

            # Check for config reload signal (SIGUSR1)
            if is_reload_requested():
                for wan_info in controller.wan_controllers:
                    wan_info["logger"].info("SIGUSR1 received, reloading config")
                    wan_info["controller"]._reload_fusion_config()
                    wan_info["controller"]._reload_tuning_config()
                    wan_info["controller"]._reload_hysteresis_config()
                    wan_info["controller"]._reload_cycle_budget_config()
                    wan_info["controller"]._reload_suppression_alert_config()

                # Reload retention config
                try:
                    reload_wan = controller.wan_controllers[0]
                    new_storage_config = get_storage_config(reload_wan["config"].data)
                    new_retention = new_storage_config.get("retention")
                    validate_retention_tuner_compat(
                        new_retention,
                        reload_wan["config"].data.get("tuning"),
                        logger=reload_wan["logger"],
                    )
                    maintenance_retention_config = new_retention
                    reload_wan["logger"].info("Retention config reloaded via SIGUSR1")
                except ConfigValidationError as e:
                    controller.wan_controllers[0]["logger"].error(
                        "Retention config reload failed, keeping previous config: %s", e
                    )

                reset_reload_state()

            # Sleep for remainder of cycle interval
            sleep_time = max(0, CYCLE_INTERVAL_SECONDS - elapsed)
            if sleep_time > 0 and not is_shutdown_requested():
                shutdown_event.wait(timeout=sleep_time)

        # Log shutdown when detected (safe - in main loop, not signal handler)
        if is_shutdown_requested():
            for wan_info in controller.wan_controllers:
                wan_info["logger"].info("Shutdown requested, exiting gracefully...")

    finally:
        # CLEANUP PRIORITY: state > locks > connections > servers > metrics
        cleanup_start = time.monotonic()
        deadline = cleanup_start + SHUTDOWN_TIMEOUT_SECONDS
        _cleanup_log = logging.getLogger(__name__)
        _cleanup_log.info("Shutting down daemon...")

        # 0. Force save state for all WANs (preserve EWMA/counters on shutdown)
        t0 = time.monotonic()
        for wan_info in controller.wan_controllers:
            try:
                wan_info["controller"].save_state(force=True)
            except Exception:
                pass  # nosec B110 - Best effort shutdown cleanup, failure is acceptable
        check_cleanup_deadline(
            "state_save", t0, deadline, SHUTDOWN_TIMEOUT_SECONDS, _cleanup_log, now=time.monotonic()
        )

        # 0.5. Stop IRTT background thread
        t0 = time.monotonic()
        if irtt_thread is not None:
            try:
                irtt_thread.stop()
            except Exception as e:
                _cleanup_log.debug(f"Error stopping IRTT thread: {e}")
        check_cleanup_deadline(
            "irtt_thread",
            t0,
            deadline,
            SHUTDOWN_TIMEOUT_SECONDS,
            _cleanup_log,
            now=time.monotonic(),
        )

        # 0.6. Stop background RTT threads and persistent pools (Phase 132)
        t0 = time.monotonic()
        for wan_info in controller.wan_controllers:
            wc = wan_info["controller"]
            try:
                if wc._rtt_thread is not None:
                    wc._rtt_thread.stop()
            except Exception as e:
                _cleanup_log.debug(f"Error stopping RTT thread: {e}")
            try:
                if wc._rtt_pool is not None:
                    wc._rtt_pool.shutdown(wait=True, cancel_futures=True)
            except Exception as e:
                _cleanup_log.debug(f"Error shutting down RTT pool: {e}")
        check_cleanup_deadline(
            "rtt_thread",
            t0,
            deadline,
            SHUTDOWN_TIMEOUT_SECONDS,
            _cleanup_log,
            now=time.monotonic(),
        )

        # 1. Clean up lock files (highest priority for restart capability)
        for lock_path in lock_files:
            try:
                lock_path.unlink(missing_ok=True)
                for wan_info in controller.wan_controllers:
                    wan_info["logger"].debug(f"Lock released: {lock_path}")
            except OSError:
                pass  # Best effort - may already be gone

        # Unregister atexit handler since we've cleaned up successfully
        try:
            atexit.unregister(emergency_lock_cleanup)
        except Exception:
            pass  # nosec B110 - Not critical if this fails during shutdown

        # 2. Clean up SSH/REST connections
        t0 = time.monotonic()
        for wan_info in controller.wan_controllers:
            try:
                router = wan_info["controller"].router
                # Handle both SSH and REST transports
                if hasattr(router, "client") and router.client:
                    router.client.close()
                if hasattr(router, "close"):
                    router.close()
            except Exception as e:
                wan_info["logger"].debug(f"Error closing router connection: {e}")
        check_cleanup_deadline(
            "router_close",
            t0,
            deadline,
            SHUTDOWN_TIMEOUT_SECONDS,
            _cleanup_log,
            now=time.monotonic(),
        )

        # 3. Shut down metrics server
        t0 = time.monotonic()
        if metrics_server:
            try:
                metrics_server.stop()
            except Exception as e:
                for wan_info in controller.wan_controllers:
                    wan_info["logger"].debug(f"Error shutting down metrics server: {e}")
        check_cleanup_deadline(
            "metrics_server",
            t0,
            deadline,
            SHUTDOWN_TIMEOUT_SECONDS,
            _cleanup_log,
            now=time.monotonic(),
        )

        # 4. Shut down health check server
        t0 = time.monotonic()
        if health_server:
            try:
                health_server.shutdown()
            except Exception as e:
                for wan_info in controller.wan_controllers:
                    wan_info["logger"].debug(f"Error shutting down health server: {e}")
        check_cleanup_deadline(
            "health_server",
            t0,
            deadline,
            SHUTDOWN_TIMEOUT_SECONDS,
            _cleanup_log,
            now=time.monotonic(),
        )

        # 5. Close MetricsWriter (SQLite connection)
        t0 = time.monotonic()
        try:
            if MetricsWriter._instance is not None:
                MetricsWriter._instance.close()
                _cleanup_log.debug("MetricsWriter connection closed")
        except Exception as e:
            _cleanup_log.debug(f"Error closing MetricsWriter: {e}")
        check_cleanup_deadline(
            "metrics_writer",
            t0,
            deadline,
            SHUTDOWN_TIMEOUT_SECONDS,
            _cleanup_log,
            now=time.monotonic(),
        )

        # Log clean shutdown
        total = time.monotonic() - cleanup_start
        for wan_info in controller.wan_controllers:
            wan_info["logger"].info(f"Daemon shutdown complete ({total:.1f}s)")

    return None


if __name__ == "__main__":
    sys.exit(main())
