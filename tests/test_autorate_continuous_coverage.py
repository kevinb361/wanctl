from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from wanctl import autorate_continuous as mod
from wanctl.config_base import ConfigValidationError
from wanctl.tuning.models import TuningConfig, TuningResult


def _tuning_config(**overrides: object) -> TuningConfig:
    data = {
        "enabled": True,
        "cadence_sec": 10,
        "lookback_hours": 1,
        "warmup_hours": 1,
        "max_step_pct": 10.0,
        "bounds": {},
    }
    data.update(overrides)
    return TuningConfig(**data)


def _wan_info(wc: object | None = None, config: object | None = None, logger: MagicMock | None = None):
    return {
        "controller": wc if wc is not None else MagicMock(),
        "config": config if config is not None else SimpleNamespace(lock_timeout=1, data={}),
        "logger": logger if logger is not None else MagicMock(),
    }


def _controller(*wan_infos: dict[str, object]):
    c = SimpleNamespace()
    c.wan_controllers = list(wan_infos) or [_wan_info()]
    c.get_lock_paths = lambda: [Path("/tmp/a.lock"), Path("/tmp/b.lock")]
    return c


def test_validate_config_mode_success_and_failure(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    good = SimpleNamespace(
        wan_name="att",
        router_transport="routeros",
        router_host="router",
        router_user="user",
        download_floor_red=100_000_000,
        download_ceiling=500_000_000,
        download_floor_green=400_000_000,
        download_floor_yellow=300_000_000,
        download_floor_soft_red=200_000_000,
        upload_floor_red=10_000_000,
        upload_ceiling=40_000_000,
        upload_floor_green=30_000_000,
        upload_floor_yellow=20_000_000,
        target_bloat_ms=10,
        warn_bloat_ms=20,
        hard_red_bloat_ms=30,
        ping_hosts=["1.1.1.1"],
        queue_down="down",
        queue_up="up",
    )

    def fake_config(path: str) -> object:
        if path == "bad.yml":
            raise ValueError("bad config")
        return good

    monkeypatch.setattr(mod, "Config", fake_config)

    assert mod.validate_config_mode(["good.yml", "bad.yml"]) == 1
    out = capsys.readouterr().out
    assert "Configuration valid: good.yml" in out
    assert "Configuration INVALID: bad.yml" in out


def test_parse_autorate_args(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["wanctl", "--config", "a.yml", "b.yml", "--debug", "--oneshot", "--profile"],
    )

    args = mod._parse_autorate_args()

    assert args.config == ["a.yml", "b.yml"]
    assert args.debug is True
    assert args.oneshot is True
    assert args.profile is True


def test_create_wan_components_rejects_cake_params_on_routeros() -> None:
    logger = MagicMock()
    config = SimpleNamespace(data={"cake_params": {}}, router_transport="routeros")

    with pytest.raises(SystemExit) as excinfo:
        mod._create_wan_components(config, logger)

    assert excinfo.value.code == 1
    logger.error.assert_called_once()


def test_create_wan_components_linux_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    logger = MagicMock()
    config = SimpleNamespace(
        data={"cake_params": {}},
        router_transport="linux-cake",
        ping_source_ip="10.0.0.1",
        wan_name="att",
    )
    router = object()
    backend = object()
    monkeypatch.setattr(mod.LinuxCakeAdapter, "from_config", lambda cfg, log: router)
    monkeypatch.setattr(mod, "build_rtt_backend", lambda *args, **kwargs: backend)
    clear = MagicMock()
    monkeypatch.setattr(mod, "clear_router_password", clear)

    assert mod._create_wan_components(config, logger) == (router, backend)
    clear.assert_called_once_with(config)


def test_acquire_daemon_locks_success_failure_and_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = _controller(_wan_info(logger=MagicMock(), config=SimpleNamespace(lock_timeout=5)))
    calls: list[Path] = []
    monkeypatch.setattr(
        mod,
        "validate_and_acquire_lock",
        lambda path, timeout, logger: calls.append(path) or True,
    )
    locks, err = mod._acquire_daemon_locks(controller)
    assert err is None
    assert locks == [Path("/tmp/a.lock"), Path("/tmp/b.lock")]

    monkeypatch.setattr(mod, "validate_and_acquire_lock", lambda *args: False)
    assert mod._acquire_daemon_locks(controller)[1] == 1

    def raise_runtime(*args: object) -> bool:
        raise RuntimeError("invalid")

    monkeypatch.setattr(mod, "validate_and_acquire_lock", raise_runtime)
    assert mod._acquire_daemon_locks(controller)[1] == 1


def test_start_servers_success_and_nonfatal_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    logger = MagicMock()
    config = SimpleNamespace(
        metrics_enabled=True,
        metrics_host="127.0.0.1",
        metrics_port=9000,
        health_check_enabled=True,
        health_check_host="127.0.0.1",
        health_check_port=9001,
        data={"storage": {"db_path": "/tmp/metrics.db"}},
    )
    controller = _controller(_wan_info(config=config, logger=logger))
    metrics = object()
    health = object()
    monkeypatch.setattr(mod, "start_metrics_server", lambda **kwargs: metrics)
    monkeypatch.setattr(mod, "start_health_server", lambda **kwargs: health)
    registered = MagicMock()
    monkeypatch.setattr(mod, "register_scrape_callback", registered)

    assert mod._start_servers(controller) == (metrics, health)
    registered.assert_called_once()

    monkeypatch.setattr(mod, "start_metrics_server", MagicMock(side_effect=OSError("busy")))
    monkeypatch.setattr(mod, "start_health_server", MagicMock(side_effect=OSError("busy")))
    assert mod._start_servers(controller) == (None, None)
    assert logger.warning.call_count >= 2


def test_start_irtt_thread_available_and_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    logger = MagicMock()
    config = SimpleNamespace(irtt_config={"cadence_sec": 2.5})
    controller = _controller(_wan_info(config=config, logger=logger))
    measurement = MagicMock()
    measurement.is_available.return_value = False
    monkeypatch.setattr(mod, "IRTTMeasurement", lambda cfg, log: measurement)
    assert mod._start_irtt_thread(controller) is None

    measurement.is_available.return_value = True
    thread = MagicMock()
    monkeypatch.setattr(mod, "IRTTThread", lambda *args: thread)
    assert mod._start_irtt_thread(controller) is thread
    thread.start.assert_called_once()


def test_configure_controller_flags_enables_profiling() -> None:
    wc = MagicMock()
    mod._configure_controller_flags(_controller(_wan_info(wc=wc)), SimpleNamespace(profile=True))
    wc.enable_profiling.assert_called_once_with(True)


def test_setup_daemon_state_starts_background_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    wc = MagicMock()
    writer = object()
    wc.get_metrics_writer.return_value = writer
    io_worker = MagicMock()
    monkeypatch.setattr(mod, "DeferredIOWorker", lambda **kwargs: io_worker)

    result = mod._setup_daemon_state(_controller(_wan_info(wc=wc, logger=MagicMock())), irtt_thread=None)

    assert result is io_worker
    wc.set_irtt_thread.assert_called_once_with(None)
    wc.init_fusion_healer.assert_called_once()
    wc.start_background_rtt.assert_called_once()
    wc.start_background_cake_stats.assert_called_once()
    wc.set_io_worker.assert_called_once_with(io_worker)
    io_worker.start.assert_called_once()


def test_track_cycle_failures_and_watchdog_degrade(monkeypatch: pytest.MonkeyPatch) -> None:
    logger = MagicMock()
    degraded = MagicMock()
    monkeypatch.setattr(mod, "notify_degraded", degraded)
    controller = _controller(_wan_info(logger=logger))

    assert mod._track_cycle_failures(controller, True, 2, False) == (0, True)
    assert logger.info.called
    assert mod._track_cycle_failures(controller, False, 0, True) == (1, True)
    assert mod._track_cycle_failures(controller, False, 2, True) == (3, False)
    degraded.assert_called_once()


def test_notify_watchdog_distinguishes_router_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    notify = MagicMock()
    degraded = MagicMock()
    monkeypatch.setattr(mod, "notify_watchdog", notify)
    monkeypatch.setattr(mod, "notify_degraded", degraded)
    wc = SimpleNamespace(
        router_connectivity=SimpleNamespace(is_reachable=False, last_failure_type="timeout")
    )
    controller = _controller(_wan_info(wc=wc, logger=MagicMock()))

    mod._notify_watchdog_with_distinction(controller, False, 2, True)
    notify.assert_called_once()

    mod._notify_watchdog_with_distinction(controller, False, 3, False)
    degraded.assert_called_once_with("3 consecutive failures")


def test_build_current_params() -> None:
    wc = SimpleNamespace(
        green_threshold=10.0,
        soft_red_threshold=20.0,
        hard_red_threshold=30.0,
        alpha_load=0.5,
        alpha_baseline=0.25,
        baseline_rtt_min=5.0,
        baseline_rtt_max=50.0,
        download=SimpleNamespace(step_up_bps=10_000_000, factor_down=0.8, green_required=3),
        upload=SimpleNamespace(step_up_bps=1_000_000, factor_down=0.7, green_required=2),
        get_current_params=lambda: {"custom": 1.0},
    )

    params = mod._build_current_params(wc)

    assert params["custom"] == 1.0
    assert params["load_time_constant_sec"] == 0.1
    assert params["dl_step_up_mbps"] == 10.0


def test_maybe_run_tuning_respects_cadence(monkeypatch: pytest.MonkeyPatch) -> None:
    tuning = _tuning_config(cadence_sec=10)
    wc = SimpleNamespace(config=SimpleNamespace(tuning_config=tuning))
    controller = _controller(_wan_info(wc=wc))
    run = MagicMock()
    monkeypatch.setattr(mod, "_run_adaptive_tuning", run)
    monkeypatch.setattr(mod.time, "monotonic", lambda: 100.0)

    assert mod._maybe_run_tuning(controller, 95.0) == 95.0
    assert mod._maybe_run_tuning(controller, 80.0) == 100.0
    run.assert_called_once_with(controller)


def test_run_adaptive_tuning_skips_disabled_and_runs_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    tuning = _tuning_config()
    enabled = MagicMock(config=SimpleNamespace(tuning_config=tuning), is_tuning_enabled=True)
    disabled = MagicMock(config=SimpleNamespace(tuning_config=tuning), is_tuning_enabled=False)
    config = SimpleNamespace(data={"storage": {"db_path": "/tmp/metrics.db"}})
    controller = _controller(_wan_info(wc=enabled, config=config), _wan_info(wc=disabled, config=config))
    run = MagicMock()
    monkeypatch.setattr(mod, "_build_tuning_layers", lambda: [[("p", lambda: None)]])
    monkeypatch.setattr(mod, "_run_tuning_for_wan", run)

    mod._run_adaptive_tuning(controller)

    run.assert_called_once()


def test_handle_sigusr1_reload_success_and_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    logger = MagicMock()
    wc = MagicMock()
    config = SimpleNamespace(
        data={
            "storage": {
                "retention": {"raw_age_seconds": 1},
                "maintenance_interval_seconds": 7,
            },
            "tuning": {},
        }
    )
    controller = _controller(_wan_info(wc=wc, config=config, logger=logger))
    reset = MagicMock()
    monkeypatch.setattr(mod, "reset_reload_state", reset)

    retention, interval = mod._handle_sigusr1_reload(controller, {"old": True}, 1)
    assert retention["raw_age_seconds"] == 1
    assert retention["aggregate_1m_age_seconds"] == 86400
    assert interval == 7
    wc.reload.assert_called_once()
    reset.assert_called_once()

    monkeypatch.setattr(
        mod,
        "validate_retention_tuner_compat",
        MagicMock(side_effect=ConfigValidationError("bad")),
    )
    retention, interval = mod._handle_sigusr1_reload(controller, {"old": True}, 1)
    assert retention == {"old": True}
    assert interval == 1
    assert logger.error.called


def test_shutdown_helpers_are_best_effort(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    logger = MagicMock()
    router = SimpleNamespace(client=MagicMock(), close=MagicMock(side_effect=RuntimeError("close")))
    wc = MagicMock(router=router)
    wc.save_state.side_effect = RuntimeError("save")
    wc.shutdown_threads.side_effect = RuntimeError("threads")
    controller = _controller(_wan_info(wc=wc, logger=logger))
    monkeypatch.setattr(mod, "check_cleanup_deadline", MagicMock())
    lock = tmp_path / "wan.lock"
    lock.write_text("x")

    mod._save_controller_state(controller, deadline=999999.0, logger=logger)
    mod._stop_background_threads(controller, MagicMock(stop=MagicMock(side_effect=RuntimeError("irtt"))), 999999.0, logger)
    mod._close_router_connections(controller, 999999.0, logger)
    mod._release_daemon_locks(controller, [lock], lambda: None)
    mod._stop_daemon_servers(
        controller,
        MagicMock(stop=MagicMock(side_effect=RuntimeError("metrics"))),
        MagicMock(shutdown=MagicMock(side_effect=RuntimeError("health"))),
        999999.0,
        logger,
    )

    assert not lock.exists()
    assert logger.debug.called


def test_build_tuning_layers_includes_expected_layers() -> None:
    layers = mod._build_tuning_layers()

    names = [[name for name, _ in layer] for layer in layers]
    assert names[0] == ["hampel_sigma_threshold", "hampel_window_size"]
    assert names[1] == ["load_time_constant_sec"]
    assert "target_bloat_ms" in names[2]
    assert "fusion_icmp_weight" in names[3]
    assert "dl_step_up_mbps" in names[4]


def test_init_storage_records_snapshot_and_handles_busy_lock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import wanctl.storage as storage_mod
    import wanctl.storage.maintenance as maintenance_mod

    logger = MagicMock()
    config = SimpleNamespace(
        wan_name="att",
        data={
            "storage": {
                "db_path": str(tmp_path / "metrics.db"),
                "maintenance_interval_seconds": 5,
                "retention": {"raw_age_seconds": 1},
            }
        },
    )
    controller = _controller(_wan_info(config=config, logger=logger))
    writer = MagicMock(connection=object())
    monkeypatch.setattr(storage_mod, "MetricsWriter", lambda path: writer)
    snapshot = MagicMock()
    startup = MagicMock(return_value={"cleanup_deleted": 1, "downsampling": {}, "error": "warn"})
    monkeypatch.setattr(storage_mod, "record_config_snapshot", snapshot)
    monkeypatch.setattr(storage_mod, "run_startup_maintenance", startup)

    class _Lock:
        def __enter__(self) -> bool:
            return True

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(maintenance_mod, "maintenance_lock", lambda *args: _Lock())
    conn, retention, interval = mod._init_storage(controller)
    assert conn is writer.connection
    assert retention["raw_age_seconds"] == 1
    assert interval == 5
    snapshot.assert_called_once()
    startup.assert_called_once()
    logger.warning.assert_called_once()

    class _BusyLock:
        def __enter__(self) -> bool:
            return False

        def __exit__(self, *args: object) -> None:
            return None

    skip = MagicMock()
    monkeypatch.setattr(mod, "record_storage_maintenance_lock_skip", skip)
    monkeypatch.setattr(maintenance_mod, "maintenance_lock", lambda *args: _BusyLock())
    mod._init_storage(controller)
    skip.assert_called_once_with("autorate")


def test_check_pending_reverts_applies_and_clears(monkeypatch: pytest.MonkeyPatch) -> None:
    import wanctl.tuning.applier as applier_mod
    import wanctl.tuning.safety as safety_mod

    result = TuningResult("target_bloat_ms", 10, 11, 0.9, "revert", 20, "att")
    wc = MagicMock(wan_name="att")
    wc.get_pending_observation.return_value = object()
    monkeypatch.setattr(safety_mod, "check_and_revert", lambda *args, **kwargs: [result])
    lock_parameter = MagicMock()
    persist = MagicMock()
    monkeypatch.setattr(safety_mod, "lock_parameter", lock_parameter)
    monkeypatch.setattr(applier_mod, "persist_revert_record", persist)
    apply = MagicMock()
    monkeypatch.setattr(mod, "_apply_tuning_to_controller", apply)

    mod._check_pending_reverts(wc, _wan_info(logger=MagicMock()), "/tmp/db", object())

    apply.assert_called_once_with(wc, [result])
    persist.assert_called_once()
    lock_parameter.assert_called_once()
    wc.clear_pending_observation.assert_called_once()


def test_check_pending_reverts_logs_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    import wanctl.tuning.safety as safety_mod

    logger = MagicMock()
    wc = MagicMock(wan_name="att")
    monkeypatch.setattr(safety_mod, "check_and_revert", MagicMock(side_effect=RuntimeError("boom")))

    mod._check_pending_reverts(wc, _wan_info(logger=logger), "/tmp/db", object())

    logger.error.assert_called_once()
    wc.clear_pending_observation.assert_called_once()


def test_check_oscillation_lockout_success_and_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    import wanctl.tuning.analyzer as analyzer_mod
    import wanctl.tuning.strategies.response as response_mod

    wc = MagicMock(wan_name="att", _oscillation_threshold=0.2, _alert_engine=object())
    logger = MagicMock()
    tuning = _tuning_config(lookback_hours=6)
    monkeypatch.setattr(analyzer_mod, "_query_wan_metrics", lambda *args: [object()])
    check = MagicMock()
    monkeypatch.setattr(response_mod, "check_oscillation_lockout", check)

    mod._check_oscillation_lockout(wc, _wan_info(logger=logger), tuning, "/tmp/db")
    check.assert_called_once()

    monkeypatch.setattr(analyzer_mod, "_query_wan_metrics", MagicMock(side_effect=RuntimeError("bad")))
    mod._check_oscillation_lockout(wc, _wan_info(logger=logger), tuning, "/tmp/db")
    logger.debug.assert_called_once()


def test_analyze_and_apply_tuning_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    import wanctl.tuning.analyzer as analyzer_mod
    import wanctl.tuning.applier as applier_mod
    import wanctl.tuning.safety as safety_mod

    wc = SimpleNamespace(
        wan_name="att",
        green_threshold=10.0,
        soft_red_threshold=20.0,
        hard_red_threshold=30.0,
        alpha_load=0.5,
        alpha_baseline=0.25,
        baseline_rtt_min=5.0,
        baseline_rtt_max=50.0,
        download=SimpleNamespace(step_up_bps=10_000_000, factor_down=0.8, green_required=3),
        upload=SimpleNamespace(step_up_bps=1_000_000, factor_down=0.7, green_required=2),
        get_current_params=lambda: {},
        set_pending_observation=MagicMock(),
    )
    logger = MagicMock()
    result = TuningResult("target_bloat_ms", 10, 11, 0.9, "raise", 20, "att")
    monkeypatch.setattr(analyzer_mod, "run_tuning_analysis", lambda **kwargs: [result])
    monkeypatch.setattr(applier_mod, "apply_tuning_results", lambda *args: [result])
    monkeypatch.setattr(safety_mod, "measure_congestion_rate", lambda *args, **kwargs: 0.2)
    apply = MagicMock()
    monkeypatch.setattr(mod, "_apply_tuning_to_controller", apply)

    mod._analyze_and_apply_tuning(wc, _wan_info(logger=logger), _tuning_config(), "/tmp/db", object(), [])
    apply.assert_called_once_with(wc, [result])
    wc.set_pending_observation.assert_called_once()

    monkeypatch.setattr(analyzer_mod, "run_tuning_analysis", lambda **kwargs: [])
    mod._analyze_and_apply_tuning(wc, _wan_info(logger=logger), _tuning_config(), "/tmp/db", object(), [])
    logger.info.assert_any_call("[TUNING] %s: no adjustments needed", "att")

    monkeypatch.setattr(analyzer_mod, "run_tuning_analysis", MagicMock(side_effect=RuntimeError("bad")))
    mod._analyze_and_apply_tuning(wc, _wan_info(logger=logger), _tuning_config(), "/tmp/db", object(), [])
    logger.error.assert_called()


def test_run_tuning_for_wan_filters_and_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    import wanctl.tuning.safety as safety_mod

    logger = MagicMock()
    wc = MagicMock(wan_name="att", tuning_layer_index=4)
    wc.get_parameter_locks.return_value = {}
    tuning = _tuning_config(exclude_params=frozenset({"skip"}))
    layers = [[("skip", object()), ("locked", object()), ("run", object())] for _ in range(5)]
    monkeypatch.setattr(safety_mod, "is_parameter_locked", lambda locks, name: name == "locked")
    oscillation = MagicMock()
    analyze = MagicMock()
    mark = MagicMock()
    monkeypatch.setattr(mod, "_check_oscillation_lockout", oscillation)
    monkeypatch.setattr(mod, "_analyze_and_apply_tuning", analyze)
    monkeypatch.setattr(mod, "_mark_tuning_executed", mark)

    mod._run_tuning_for_wan(wc, _wan_info(logger=logger), tuning, "/tmp/db", object(), layers)

    oscillation.assert_called_once()
    analyze.assert_called_once()
    active = analyze.call_args.args[5]
    assert [name for name, _ in active] == ["run"]
    mark.assert_called_once_with(wc)
    logger.info.assert_called()
