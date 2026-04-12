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
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

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
    record_runtime_pressure,
    record_storage_checkpoint,
    record_storage_maintenance_lock_skip,
    register_scrape_callback,
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
from wanctl.storage.deferred_writer import DeferredIOWorker
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
    _mark_tuning_executed,
)

if TYPE_CHECKING:
    from wanctl.backends.linux_cake_adapter import LinuxCakeAdapter

# =============================================================================
# CONSTANTS
# =============================================================================

# Default periodic maintenance interval (seconds). Configurable via
# storage.maintenance_interval_seconds.
DEFAULT_MAINTENANCE_INTERVAL = 900


# =============================================================================
# MAIN CONTROLLER
# =============================================================================


def _log_startup_config(config: "Config", logger: logging.Logger) -> None:
    """Log startup configuration summary for a WAN."""
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
        f"Download Thresholds: GREEN\u2192YELLOW={config.target_bloat_ms}ms, "
        f"YELLOW\u2192SOFT_RED={config.warn_bloat_ms}ms, "
        f"SOFT_RED\u2192RED={config.hard_red_bloat_ms}ms"
    )
    logger.info(
        f"Upload Thresholds: GREEN\u2192YELLOW={config.target_bloat_ms}ms, "
        f"YELLOW\u2192RED={config.warn_bloat_ms}ms"
    )
    logger.info(f"EWMA: baseline_alpha={config.alpha_baseline}, load_alpha={config.alpha_load}")
    logger.info(f"Ping: hosts={config.ping_hosts}, median-of-three={config.use_median_of_three}")


def _create_wan_components(config: "Config", logger: logging.Logger) -> tuple[Any, RTTMeasurement]:
    """Create router backend and RTT measurement for a WAN.

    Validates transport/cake_params compatibility and selects the appropriate
    router backend (LinuxCakeAdapter or RouterOS).
    """
    has_cake_params = isinstance(config.data.get("cake_params"), dict)
    linux_cake_transports = ("linux-cake", "linux-cake-netlink")
    if has_cake_params and config.router_transport not in linux_cake_transports:
        logger.error(
            "FATAL: cake_params section present but transport is '%s' (not linux-cake). "
            "CAKE qdiscs will NOT be created. Fix router.transport in YAML config.",
            config.router_transport,
        )
        raise SystemExit(1)

    router: "LinuxCakeAdapter | RouterOS"  # noqa: UP037
    if config.router_transport in linux_cake_transports:
        from wanctl.backends.linux_cake_adapter import LinuxCakeAdapter

        router = LinuxCakeAdapter.from_config(config, logger)
    else:
        router = RouterOS(config, logger)
    clear_router_password(config)

    rtt_measurement = RTTMeasurement(
        logger,
        timeout_ping=config.timeout_ping,
        aggregation_strategy=RTTAggregationStrategy.AVERAGE,
        log_sample_stats=True,
        source_ip=config.ping_source_ip,
    )
    return router, rtt_measurement


class ContinuousAutoRate:
    """Main controller managing one or more WANs"""

    def __init__(self, config_files: list[str], debug: bool = False):
        self.wan_controllers: list[dict[str, Any]] = []
        self.debug = debug

        for config_file in config_files:
            config = Config(config_file)
            logger = setup_logging(config, "cake_continuous", debug)
            _log_startup_config(config, logger)
            router, rtt_measurement = _create_wan_components(config, logger)
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
) -> tuple[Any, Mapping[str, Any], int]:
    """Initialize storage, record config snapshot, and run startup maintenance.

    Args:
        controller: The ContinuousAutoRate instance (for config/logger access).

    Returns:
        Tuple of (maintenance_conn, maintenance_retention_config, maintenance_interval_seconds).
        maintenance_conn is None if storage is not enabled.
        maintenance_retention_config is the per-granularity retention dict.
    """
    first_config = controller.wan_controllers[0]["config"]
    storage_config = get_storage_config(first_config.data)
    db_path = storage_config.get("db_path")
    maintenance_conn = None
    maintenance_interval_seconds = DEFAULT_MAINTENANCE_INTERVAL
    default_retention: Mapping[str, Any] = {
        "raw_age_seconds": 900,
        "aggregate_1m_age_seconds": 86400,
        "aggregate_5m_age_seconds": 604800,
        "prometheus_compensated": False,
    }
    retention_raw = storage_config.get("retention")
    maintenance_interval_seconds = int(
        storage_config.get("maintenance_interval_seconds", DEFAULT_MAINTENANCE_INTERVAL)
    )
    # Guard against MagicMock in tests (isinstance(dict) check)
    maintenance_retention_config: Mapping[str, Any] = (
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
        from wanctl.storage.maintenance import maintenance_lock

        writer = MetricsWriter(Path(db_path))
        writer.set_process_role("autorate")
        maintenance_conn = writer.connection
        record_config_snapshot(writer, first_config.wan_name, first_config.data, "startup")

        # Run startup maintenance (cleanup + downsampling)
        # Pass watchdog callback and time budget to prevent exceeding WatchdogSec=30s
        with maintenance_lock(db_path, startup_logger) as acquired:
            if acquired:
                maint_result = run_startup_maintenance(
                    maintenance_conn,
                    retention_config=maintenance_retention_config,
                    log=startup_logger,
                    watchdog_fn=notify_watchdog,
                    max_seconds=20,
                )
                if maint_result.get("error"):
                    startup_logger.warning(f"Startup maintenance error: {maint_result['error']}")
            else:
                record_storage_maintenance_lock_skip("autorate")

    return maintenance_conn, maintenance_retention_config, maintenance_interval_seconds


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
            storage_config = get_storage_config(first_config.data)
            db_path = storage_config.get("db_path")
            register_scrape_callback(
                "autorate_runtime_pressure",
                lambda: record_runtime_pressure(
                    "autorate",
                    db_path if isinstance(db_path, str) else None,
                ),
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


def _configure_controller_flags(
    controller: "ContinuousAutoRate",
    args: argparse.Namespace,
) -> None:
    """Apply --profile and --dry-run CLI flags to all WAN controllers."""
    if args.profile:
        for wan_info in controller.wan_controllers:
            wan_info["controller"].enable_profiling(True)


def _setup_daemon_state(
    controller: "ContinuousAutoRate",
    irtt_thread: IRTTThread | None,
) -> DeferredIOWorker | None:
    """Wire IRTT thread, start background RTT, create I/O worker, and log startup info.

    Returns:
        DeferredIOWorker instance if MetricsWriter is available, else None.
    """
    for wan_info in controller.wan_controllers:
        wan_info["controller"].set_irtt_thread(irtt_thread)
        wan_info["controller"].init_fusion_healer()

    rtt_shutdown = get_shutdown_event()
    for wan_info in controller.wan_controllers:
        wan_info["controller"].start_background_rtt(rtt_shutdown)
        wan_info["controller"].start_background_cake_stats(get_shutdown_event())

    # Create deferred I/O worker for background SQLite writes (Phase 155: CYCLE-02)
    io_worker: DeferredIOWorker | None = None
    metrics_writer = controller.wan_controllers[0]["controller"].get_metrics_writer()
    if metrics_writer is not None:
        io_worker = DeferredIOWorker(
            writer=metrics_writer,
            shutdown_event=get_shutdown_event(),
            logger=logging.getLogger("wanctl.io_worker"),
            process_role="autorate",
        )
        io_worker.start()
        for wan_info in controller.wan_controllers:
            wan_info["controller"].set_io_worker(io_worker)

    for wan_info in controller.wan_controllers:
        wan_info["logger"].info(
            f"Starting daemon mode with {CYCLE_INTERVAL_SECONDS}s cycle interval"
        )
        if is_systemd_available():
            wan_info["logger"].info("Systemd watchdog support enabled")

    return io_worker


def _track_cycle_failures(
    controller: "ContinuousAutoRate",
    cycle_success: bool,
    consecutive_failures: int,
    watchdog_enabled: bool,
) -> tuple[int, bool]:
    """Track consecutive cycle failures and manage watchdog state.

    Returns updated (consecutive_failures, watchdog_enabled).
    """
    max_consecutive_failures = 3

    if cycle_success:
        if not watchdog_enabled:
            for wan_info in controller.wan_controllers:
                wan_info["logger"].info(
                    "Cycle recovered after watchdog surrender. Re-enabling watchdog notifications."
                )
        return 0, True

    consecutive_failures += 1
    for wan_info in controller.wan_controllers:
        wan_info["logger"].warning(
            f"Cycle failed ({consecutive_failures}/{max_consecutive_failures})"
        )

    if consecutive_failures >= max_consecutive_failures and watchdog_enabled:
        watchdog_enabled = False
        for wan_info in controller.wan_controllers:
            wan_info["logger"].error(
                f"Sustained failure: {consecutive_failures} consecutive "
                f"failed cycles. Stopping watchdog - systemd will terminate us."
            )
        notify_degraded("consecutive failures exceeded threshold")

    return consecutive_failures, watchdog_enabled


def _notify_watchdog_with_distinction(
    controller: "ContinuousAutoRate",
    cycle_success: bool,
    consecutive_failures: int,
    watchdog_enabled: bool,
) -> None:
    """Notify systemd watchdog with router failure distinction (ERRR-04)."""
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


def _run_maintenance(
    controller: "ContinuousAutoRate",
    maintenance_conn: Any,
    maintenance_retention_config: Mapping[str, Any],
) -> None:
    """Run periodic maintenance: cleanup, downsample, vacuum, WAL truncate.

    Retries once on SystemError for CPython sqlite3 edge cases during
    maintenance operations.
    """
    maint_logger = controller.wan_controllers[0]["logger"]
    for attempt in range(2):
        try:
            from wanctl.storage.downsampler import (
                downsample_metrics,
                get_downsample_thresholds,
            )
            from wanctl.storage.maintenance import maintenance_lock
            from wanctl.storage.retention import cleanup_old_metrics, vacuum_if_needed

            db_path = get_storage_config(controller.wan_controllers[0]["config"].data).get("db_path")
            if not isinstance(db_path, str):
                return

            with maintenance_lock(db_path, maint_logger) as acquired:
                if not acquired:
                    record_storage_maintenance_lock_skip("autorate")
                    return

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

                wal_result = maintenance_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
                busy = int(wal_result[0]) if wal_result else 0
                wal_pages = int(wal_result[1]) if wal_result else 0
                checkpointed_pages = int(wal_result[2]) if wal_result else 0
                record_storage_checkpoint(
                    "autorate",
                    busy=busy,
                    wal_pages=wal_pages,
                    checkpointed_pages=checkpointed_pages,
                )
                wal_truncated = wal_pages > 0
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
            return
        except SystemError as e:
            if attempt == 0:
                maint_logger.warning(
                    "Maintenance SystemError (attempt %d/2, retrying): %s",
                    attempt + 1,
                    str(e),
                )
                continue
            maint_logger.error(
                "Maintenance SystemError persisted after retry, skipping cycle: %s",
                str(e),
            )
            return
        except Exception as e:
            maint_logger.error("Periodic maintenance failed: %s", str(e))
            return


def _build_tuning_layers() -> list[list[tuple[str, Any]]]:
    """Build layer definitions for bottom-up tuning (SIGP-04).

    Lazy-imports tuning strategy modules.
    """
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

    _layer_t = list[tuple[str, Any]]
    signal: _layer_t = [
        ("hampel_sigma_threshold", tune_hampel_sigma),
        ("hampel_window_size", tune_hampel_window),
    ]
    ewma: _layer_t = [("load_time_constant_sec", tune_alpha_load)]
    threshold: _layer_t = [
        ("target_bloat_ms", calibrate_target_bloat),
        ("warn_bloat_ms", calibrate_warn_bloat),
    ]
    advanced: _layer_t = [
        ("fusion_icmp_weight", tune_fusion_weight),
        ("reflector_min_score", tune_reflector_min_score),
        ("baseline_rtt_min", tune_baseline_bounds_min),
        ("baseline_rtt_max", tune_baseline_bounds_max),
    ]
    response: _layer_t = [
        ("dl_step_up_mbps", tune_dl_step_up),
        ("ul_step_up_mbps", tune_ul_step_up),
        ("dl_factor_down", tune_dl_factor_down),
        ("ul_factor_down", tune_ul_factor_down),
        ("dl_green_required", tune_dl_green_required),
        ("ul_green_required", tune_ul_green_required),
    ]
    return [signal, ewma, threshold, advanced, response]


def _check_pending_reverts(
    wc: Any,
    wan_info: dict[str, Any],
    db_path: str,
    metrics_writer: Any,
) -> None:
    """Check and apply pending observation reverts for a WAN controller."""
    from wanctl.tuning.applier import persist_revert_record
    from wanctl.tuning.safety import (
        DEFAULT_MIN_CONGESTION_RATE,
        DEFAULT_REVERT_COOLDOWN_SEC,
        DEFAULT_REVERT_THRESHOLD,
        check_and_revert,
        lock_parameter,
    )

    try:
        reverts = check_and_revert(
            wc.get_pending_observation(),
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
                    wc.get_parameter_locks(),
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
    wc.clear_pending_observation()  # Clear regardless


def _check_oscillation_lockout(
    wc: Any,
    wan_info: dict[str, Any],
    tuning_config: TuningConfig,
    db_path: str,
) -> None:
    """Check oscillation lockout for response layer (RTUN-04)."""
    from wanctl.tuning.analyzer import _query_wan_metrics
    from wanctl.tuning.strategies.response import check_oscillation_lockout

    try:
        osc_metrics = _query_wan_metrics(db_path, wc.wan_name, tuning_config.lookback_hours)
        check_oscillation_lockout(
            osc_metrics,
            wc.get_parameter_locks(),
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


def _analyze_and_apply_tuning(
    wc: Any,
    wan_info: dict[str, Any],
    tuning_config: TuningConfig,
    db_path: str,
    metrics_writer: Any,
    active_strategies: list[tuple[str, Any]],
) -> None:
    """Run tuning analysis and apply results for a single WAN controller."""
    from wanctl.tuning.analyzer import run_tuning_analysis
    from wanctl.tuning.applier import apply_tuning_results
    from wanctl.tuning.safety import PendingObservation, measure_congestion_rate

    current_params = _build_current_params(wc)
    try:
        results = run_tuning_analysis(
            wan_name=wc.wan_name,
            db_path=db_path,
            tuning_config=tuning_config,
            current_params=current_params,
            strategies=active_strategies,
        )
        if results:
            applied = apply_tuning_results(results, tuning_config, metrics_writer)
            if applied:
                wan_info["logger"].info(
                    "[TUNING] %s: applied %d adjustment(s): %s",
                    wc.wan_name,
                    len(applied),
                    ", ".join(f"{r.parameter}={r.new_value}" for r in applied),
                )
                _apply_tuning_to_controller(wc, applied)
                pre_rate = measure_congestion_rate(
                    db_path,
                    wc.wan_name,
                    start_ts=int(time.time()) - tuning_config.cadence_sec,
                    end_ts=int(time.time()),
                )
                if pre_rate is not None:
                    wc.set_pending_observation(PendingObservation(
                        applied_ts=int(time.time()),
                        pre_congestion_rate=pre_rate,
                        applied_results=tuple(applied),
                    ))
        else:
            wan_info["logger"].info(
                "[TUNING] %s: no adjustments needed",
                wc.wan_name,
            )
    except Exception as e:
        wan_info["logger"].error(
            "[TUNING] Analysis failed for %s: %s",
            wc.wan_name,
            e,
        )


def _run_tuning_for_wan(
    wc: Any,
    wan_info: dict[str, Any],
    tuning_config: TuningConfig,
    db_path: str,
    metrics_writer: Any,
    all_layers: list[list[tuple[str, Any]]],
) -> None:
    """Run one adaptive tuning pass for a single WAN controller."""
    from wanctl.tuning.safety import is_parameter_locked

    _check_pending_reverts(wc, wan_info, db_path, metrics_writer)

    # Select active layer via round-robin (SIGP-04)
    active_layer = all_layers[wc.tuning_layer_index % len(all_layers)]
    wc.tuning_layer_index += 1

    # Oscillation lockout for response layer (RTUN-04)
    if active_layer is all_layers[-1]:
        _check_oscillation_lockout(wc, wan_info, tuning_config, db_path)

    # Filter excluded and locked parameters
    excluded = tuning_config.exclude_params
    active_strategies = [
        (pname, sfn)
        for pname, sfn in active_layer
        if pname not in excluded and not is_parameter_locked(wc.get_parameter_locks(), pname)
    ]
    _log_excluded_params(wc, wan_info, active_layer, excluded)

    layer_idx = (wc.tuning_layer_index - 1) % len(all_layers)
    wan_info["logger"].info(
        "[TUNING] %s: executing layer %d/%d (%d strategies)",
        wc.wan_name,
        layer_idx + 1,
        len(all_layers),
        len(active_strategies),
    )

    _analyze_and_apply_tuning(
        wc, wan_info, tuning_config, db_path, metrics_writer, active_strategies
    )

    _mark_tuning_executed(wc)

    # Heartbeat: always log cycle completion so silence never means "broken"
    layer_names = ["signal", "EWMA", "threshold", "advanced"]
    layer_name = layer_names[layer_idx] if layer_idx < len(layer_names) else f"layer-{layer_idx}"
    wan_info["logger"].info(
        "[TUNING] %s: cycle %d complete (layer: %s, strategies: %d)",
        wc.wan_name,
        wc.tuning_layer_index,
        layer_name,
        len(active_strategies),
    )


def _log_excluded_params(
    wc: Any,
    wan_info: dict[str, Any],
    active_layer: list[tuple[str, Any]],
    excluded: frozenset[str] | set[str],
) -> None:
    """Log parameter exclusion/lockout status for the active layer."""
    from wanctl.tuning.safety import is_parameter_locked

    for pname, _ in active_layer:
        if pname in excluded:
            wan_info["logger"].debug(
                "[TUNING] %s: %s excluded via config",
                wc.wan_name,
                pname,
            )
        elif is_parameter_locked(wc.get_parameter_locks(), pname):
            wan_info["logger"].info(
                "[TUNING] %s: %s locked until revert cooldown expires",
                wc.wan_name,
                pname,
            )


def _build_current_params(wc: Any) -> dict[str, float]:
    """Build current parameter snapshot from a WAN controller."""
    current = wc.get_current_params()
    return {
        "target_bloat_ms": wc.green_threshold,
        "warn_bloat_ms": wc.soft_red_threshold,
        "hard_red_bloat_ms": wc.hard_red_threshold,
        "alpha_load": wc.alpha_load,
        "alpha_baseline": wc.alpha_baseline,
        **current,
        "load_time_constant_sec": 0.05 / wc.alpha_load,
        "baseline_rtt_min": wc.baseline_rtt_min,
        "baseline_rtt_max": wc.baseline_rtt_max,
        "dl_step_up_mbps": wc.download.step_up_bps / 1e6,
        "ul_step_up_mbps": wc.upload.step_up_bps / 1e6,
        "dl_factor_down": wc.download.factor_down,
        "ul_factor_down": wc.upload.factor_down,
        "dl_green_required": float(wc.download.green_required),
        "ul_green_required": float(wc.upload.green_required),
    }


def _maybe_run_tuning(controller: "ContinuousAutoRate", last_tuning: float) -> float:
    """Run adaptive tuning if cadence elapsed. Returns updated last_tuning."""
    tuning_config = getattr(
        controller.wan_controllers[0]["controller"].config,
        "tuning_config",
        None,
    )
    if isinstance(tuning_config, TuningConfig) and tuning_config.enabled:
        now = time.monotonic()
        if now - last_tuning >= tuning_config.cadence_sec:
            _run_adaptive_tuning(controller)
            return now
    return last_tuning


def _run_adaptive_tuning(controller: "ContinuousAutoRate") -> None:
    """Execute one adaptive tuning pass across all WAN controllers."""
    tuning_config = getattr(
        controller.wan_controllers[0]["controller"].config,
        "tuning_config",
        None,
    )
    if not isinstance(tuning_config, TuningConfig) or not tuning_config.enabled:
        return

    all_layers = _build_tuning_layers()

    first_config = controller.wan_controllers[0]["config"]
    storage_config = get_storage_config(first_config.data)
    db_path = storage_config.get("db_path", "")
    metrics_writer = controller.wan_controllers[0]["controller"].get_metrics_writer()

    for wan_info in controller.wan_controllers:
        wc = wan_info["controller"]
        if not wc.is_tuning_enabled:
            continue
        _run_tuning_for_wan(wc, wan_info, tuning_config, db_path, metrics_writer, all_layers)


def _handle_sigusr1_reload(
    controller: "ContinuousAutoRate",
    maintenance_retention_config: Mapping[str, Any],
    maintenance_interval_seconds: int,
) -> tuple[Mapping[str, Any], int]:
    """Handle SIGUSR1 config reload. Returns updated retention config and interval."""
    for wan_info in controller.wan_controllers:
        wan_info["logger"].info("SIGUSR1 received, reloading config")
        wan_info["controller"].reload()

    try:
        reload_wan = controller.wan_controllers[0]
        new_storage_config = get_storage_config(reload_wan["config"].data)
        new_retention = new_storage_config["retention"]
        validate_retention_tuner_compat(
            new_retention,
            reload_wan["config"].data.get("tuning"),
            logger=reload_wan["logger"],
        )
        maintenance_retention_config = new_retention
        maintenance_interval_seconds = int(
            new_storage_config.get("maintenance_interval_seconds", DEFAULT_MAINTENANCE_INTERVAL)
        )
        reload_wan["logger"].info(
            "Storage config reloaded via SIGUSR1 (maintenance_interval=%ss)",
            maintenance_interval_seconds,
        )
    except ConfigValidationError as e:
        controller.wan_controllers[0]["logger"].error(
            "Retention config reload failed, keeping previous config: %s", e
        )

    reset_reload_state()
    return maintenance_retention_config, maintenance_interval_seconds


def _save_controller_state(
    controller: "ContinuousAutoRate",
    deadline: float,
    logger: logging.Logger,
) -> None:
    """Force-save state for all WANs (preserve EWMA/counters on shutdown)."""
    t0 = time.monotonic()
    for wan_info in controller.wan_controllers:
        try:
            wan_info["controller"].save_state(force=True)
        except Exception:
            pass  # nosec B110 - Best effort shutdown cleanup
    check_cleanup_deadline(
        "state_save", t0, deadline, SHUTDOWN_TIMEOUT_SECONDS, logger, now=time.monotonic()
    )


def _stop_background_threads(
    controller: "ContinuousAutoRate",
    irtt_thread: IRTTThread | None,
    deadline: float,
    logger: logging.Logger,
) -> None:
    """Stop IRTT thread, background RTT threads, and persistent pools."""
    t0 = time.monotonic()
    if irtt_thread is not None:
        try:
            irtt_thread.stop()
        except Exception as e:
            logger.debug(f"Error stopping IRTT thread: {e}")
    check_cleanup_deadline(
        "irtt_thread", t0, deadline, SHUTDOWN_TIMEOUT_SECONDS, logger, now=time.monotonic()
    )

    t0 = time.monotonic()
    for wan_info in controller.wan_controllers:
        wc = wan_info["controller"]
        try:
            wc.shutdown_threads()
        except Exception as e:
            logger.debug(f"Error shutting down threads: {e}")
    check_cleanup_deadline(
        "rtt_thread", t0, deadline, SHUTDOWN_TIMEOUT_SECONDS, logger, now=time.monotonic()
    )


def _release_daemon_locks(
    controller: "ContinuousAutoRate",
    lock_files: list[Path],
    emergency_lock_cleanup: Any,
) -> None:
    """Release lock files and unregister atexit handler."""
    for lock_path in lock_files:
        try:
            lock_path.unlink(missing_ok=True)
            for wan_info in controller.wan_controllers:
                wan_info["logger"].debug(f"Lock released: {lock_path}")
        except OSError:
            pass  # Best effort - may already be gone

    try:
        atexit.unregister(emergency_lock_cleanup)
    except Exception:
        pass  # nosec B110 - Not critical if this fails during shutdown


def _close_router_connections(
    controller: "ContinuousAutoRate",
    deadline: float,
    logger: logging.Logger,
) -> None:
    """Close SSH/REST router connections."""
    t0 = time.monotonic()
    for wan_info in controller.wan_controllers:
        try:
            router = wan_info["controller"].router
            if hasattr(router, "client") and router.client:
                router.client.close()
            if hasattr(router, "close"):
                router.close()
        except Exception as e:
            wan_info["logger"].debug(f"Error closing router connection: {e}")
    check_cleanup_deadline(
        "router_close", t0, deadline, SHUTDOWN_TIMEOUT_SECONDS, logger, now=time.monotonic()
    )


def _stop_daemon_servers(
    controller: "ContinuousAutoRate",
    metrics_server: Any,
    health_server: Any,
    deadline: float,
    logger: logging.Logger,
) -> None:
    """Stop metrics and health check servers."""
    t0 = time.monotonic()
    if metrics_server:
        try:
            metrics_server.stop()
        except Exception as e:
            for wan_info in controller.wan_controllers:
                wan_info["logger"].debug(f"Error shutting down metrics server: {e}")
    check_cleanup_deadline(
        "metrics_server", t0, deadline, SHUTDOWN_TIMEOUT_SECONDS, logger, now=time.monotonic()
    )

    t0 = time.monotonic()
    if health_server:
        try:
            health_server.shutdown()
        except Exception as e:
            for wan_info in controller.wan_controllers:
                wan_info["logger"].debug(f"Error shutting down health server: {e}")
    check_cleanup_deadline(
        "health_server", t0, deadline, SHUTDOWN_TIMEOUT_SECONDS, logger, now=time.monotonic()
    )


def _close_metrics_writer(
    deadline: float,
    logger: logging.Logger,
) -> None:
    """Close MetricsWriter SQLite connection."""
    t0 = time.monotonic()
    try:
        instance = MetricsWriter.get_instance()
        if instance is not None:
            instance.close()
            logger.debug("MetricsWriter connection closed")
    except Exception as e:
        logger.debug(f"Error closing MetricsWriter: {e}")
    check_cleanup_deadline(
        "metrics_writer", t0, deadline, SHUTDOWN_TIMEOUT_SECONDS, logger, now=time.monotonic()
    )


def _cleanup_daemon(
    controller: "ContinuousAutoRate",
    lock_files: list[Path],
    irtt_thread: IRTTThread | None,
    metrics_server: Any,
    health_server: Any,
    emergency_lock_cleanup: Any,
    io_worker: DeferredIOWorker | None = None,
) -> None:
    """Ordered daemon shutdown: state > threads > locks > connections > servers > io_worker > metrics."""
    cleanup_start = time.monotonic()
    deadline = cleanup_start + SHUTDOWN_TIMEOUT_SECONDS
    _cleanup_log = logging.getLogger(__name__)
    _cleanup_log.info("Shutting down daemon...")

    _save_controller_state(controller, deadline, _cleanup_log)
    _stop_background_threads(controller, irtt_thread, deadline, _cleanup_log)
    _release_daemon_locks(controller, lock_files, emergency_lock_cleanup)
    _close_router_connections(controller, deadline, _cleanup_log)
    _stop_daemon_servers(controller, metrics_server, health_server, deadline, _cleanup_log)
    if io_worker is not None:
        t0 = time.monotonic()
        try:
            io_worker.stop()
        except Exception as e:
            _cleanup_log.debug(f"Error stopping I/O worker: {e}")
        check_cleanup_deadline(
            "io_worker", t0, deadline, SHUTDOWN_TIMEOUT_SECONDS, _cleanup_log, now=time.monotonic()
        )
    _close_metrics_writer(deadline, _cleanup_log)

    total = time.monotonic() - cleanup_start
    for wan_info in controller.wan_controllers:
        wan_info["logger"].info(f"Daemon shutdown complete ({total:.1f}s)")


def _run_daemon_loop(
    controller: "ContinuousAutoRate",
    maintenance_conn: Any,
    maintenance_retention_config: Mapping[str, Any],
    maintenance_interval_seconds: int,
) -> None:
    """Main daemon control loop with cycle management, maintenance, and tuning."""
    consecutive_failures = 0
    watchdog_enabled = True
    last_maintenance = time.monotonic()
    last_tuning = time.monotonic()
    shutdown_event = get_shutdown_event()

    while not is_shutdown_requested():
        cycle_start = time.monotonic()

        cycle_success = controller.run_cycle(use_lock=False)  # Lock already held
        elapsed = time.monotonic() - cycle_start

        consecutive_failures, watchdog_enabled = _track_cycle_failures(
            controller, cycle_success, consecutive_failures, watchdog_enabled
        )
        update_health_status(consecutive_failures)
        _notify_watchdog_with_distinction(
            controller, cycle_success, consecutive_failures, watchdog_enabled
        )

        # Periodic maintenance: cleanup + downsample + vacuum on configured cadence
        if maintenance_conn is not None:
            now = time.monotonic()
            if now - last_maintenance >= maintenance_interval_seconds:
                _run_maintenance(controller, maintenance_conn, maintenance_retention_config)
                last_maintenance = now

        # Adaptive tuning (runs after maintenance, on its own cadence)
        last_tuning = _maybe_run_tuning(controller, last_tuning)

        # Check for config reload signal (SIGUSR1)
        if is_reload_requested():
            maintenance_retention_config, maintenance_interval_seconds = _handle_sigusr1_reload(
                controller, maintenance_retention_config, maintenance_interval_seconds
            )

        # Sleep for remainder of cycle interval
        sleep_time = max(0, CYCLE_INTERVAL_SECONDS - elapsed)
        if sleep_time > 0 and not is_shutdown_requested():
            shutdown_event.wait(timeout=sleep_time)

    # Log shutdown when detected (safe - in main loop, not signal handler)
    if is_shutdown_requested():
        for wan_info in controller.wan_controllers:
            wan_info["logger"].info("Shutdown requested, exiting gracefully...")


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

    if args.validate_config:
        return validate_config_mode(args.config)

    controller = ContinuousAutoRate(args.config, debug=args.debug)
    _configure_controller_flags(controller, args)
    maintenance_conn, maintenance_retention_config, maintenance_interval_seconds = _init_storage(controller)

    if args.oneshot:
        controller.run_cycle(use_lock=True)
        return None

    lock_files, lock_error = _acquire_daemon_locks(controller)
    if lock_error is not None:
        return lock_error

    # Register emergency cleanup handler for abnormal termination
    def emergency_lock_cleanup() -> None:
        """Emergency cleanup - runs via atexit if finally block doesn't complete."""
        for lock_path in lock_files:
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass  # Best effort

    atexit.register(emergency_lock_cleanup)
    register_signal_handlers()

    metrics_server, health_server = _start_servers(controller)
    irtt_thread = _start_irtt_thread(controller)
    io_worker = _setup_daemon_state(controller, irtt_thread)

    try:
        _run_daemon_loop(
            controller,
            maintenance_conn,
            maintenance_retention_config,
            maintenance_interval_seconds,
        )
    finally:
        _cleanup_daemon(
            controller,
            lock_files,
            irtt_thread,
            metrics_server,
            health_server,
            emergency_lock_cleanup,
            io_worker=io_worker,
        )

    return None


if __name__ == "__main__":
    sys.exit(main())
