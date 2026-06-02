"""Pytest wiring for the offline steering replay harness."""

from __future__ import annotations

import copy
import json
import logging
import socket
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Literal
from unittest.mock import patch

import pytest
import yaml

from wanctl.steering.cake_stats import CakeStats
from wanctl.steering.daemon import (
    RTTAggregationStrategy,
    RTTMeasurement,
    SteeringConfig,
    SteeringDaemon,
    SteeringStateManager,
    create_steering_state_schema,
)

from .fake_cake_reader import FakeCakeReader
from .fake_live_rtt_source import FixtureBaselineLoader
from .fake_router_transport import FakeRouterTransport

PRODUCTION_ROOTS = (
    Path("/var/lib/wanctl"),
    Path("/etc/wanctl"),
    Path("/var/log/wanctl"),
    Path("/run/wanctl"),
)


@pytest.fixture
def staging_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "steering-replay"
    workspace.mkdir()
    (workspace / "steering_state.json").write_text("{}")
    (workspace / "spectrum_state.json").write_text(
        json.dumps({"ewma": {"baseline_rtt": 25.0}, "congestion": {"dl_state": "GREEN"}})
    )
    return workspace


@pytest.fixture
def fake_router() -> FakeRouterTransport:
    return FakeRouterTransport(initial_enabled=False)


@pytest.fixture
def fake_cake_reader() -> FakeCakeReader:
    reader = FakeCakeReader(default_stats=CakeStats())

    def script(cycle_to_stats: dict[int, CakeStats | None | type[Exception]]) -> FakeCakeReader:
        reader.script.update(cycle_to_stats)
        return reader

    reader.script_helper = script  # type: ignore[attr-defined]
    return reader


@pytest.fixture
def fixture_baseline_loader(staging_workspace: Path):
    def _factory(config, logger=None) -> FixtureBaselineLoader:
        return FixtureBaselineLoader(
            config,
            logger or logging.getLogger(__name__),
            staging_workspace / "spectrum_state.json",
        )

    return _factory


@pytest.fixture
def baseline_loader_spy(fixture_baseline_loader):
    return fixture_baseline_loader


@pytest.fixture(autouse=True)
def _seal_urlopen(monkeypatch: pytest.MonkeyPatch):
    calls: list[str] = []

    def denied(*args, **_kwargs):
        calls.append(str(args[0]) if args else "<unknown>")
        raise RuntimeError("steering_replay harness: no HTTP calls allowed")

    monkeypatch.setattr(urllib.request, "urlopen", denied)
    yield calls


@pytest.fixture(autouse=True)
def _seal_socket(monkeypatch: pytest.MonkeyPatch):
    calls: list[str] = []

    def denied(self, address):
        calls.append(str(address))
        raise RuntimeError("steering_replay harness: no socket calls allowed")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    yield calls


def _under_production_root(path: Path) -> bool:
    resolved = path.resolve()
    return any(resolved == root or root in resolved.parents for root in PRODUCTION_ROOTS)


def build_replay_config(workspace: Path, harness_mode: str = "hysteresis-only") -> SteeringConfig:
    source = yaml.safe_load(Path("configs/steering.yaml").read_text())
    data = copy.deepcopy(source)
    data["topology"]["primary_wan_config"] = str(workspace / "primary.yaml")
    data["cake_state_sources"]["primary"] = str(workspace / "spectrum_state.json")
    data["state"]["file"] = str(workspace / "steering_state.json")
    data["storage"]["db_path"] = ""
    data["logging"]["main_log"] = str(workspace / "steering.log")
    data["logging"]["debug_log"] = str(workspace / "steering_debug.log")
    data["lock_file"] = str(workspace / "steering.lock")
    data["measurement"]["interval_seconds"] = 0.05
    if harness_mode == "hysteresis-only":
        data["mode"]["use_confidence_scoring"] = False
    elif harness_mode == "confidence":
        data["mode"]["use_confidence_scoring"] = True
        data.setdefault("confidence", {})["dry_run"] = False
    else:
        raise ValueError(f"unknown harness_mode: {harness_mode}")

    (workspace / "primary.yaml").write_text(
        yaml.safe_dump({"router": {"transport": "rest"}, "health_check": {"port": 9101}})
    )
    config_path = workspace / "steering.yaml"
    config_path.write_text(yaml.safe_dump(data))
    return SteeringConfig(str(config_path))


@pytest.fixture
def daemon_factory(
    staging_workspace: Path,
    fake_router: FakeRouterTransport,
    fake_cake_reader: FakeCakeReader,
    fixture_baseline_loader,
) -> Callable[[Literal["hysteresis-only", "confidence"]], SteeringDaemon]:
    def _factory(
        harness_mode: Literal["hysteresis-only", "confidence"] = "hysteresis-only",
    ) -> SteeringDaemon:
        logger = logging.getLogger("steering_replay")
        config = build_replay_config(staging_workspace, harness_mode)
        state_mgr = SteeringStateManager(
            staging_workspace / "steering_state.json",
            create_steering_state_schema(config),
            logger,
            history_maxlen=config.history_size,
        )
        state_mgr.load()
        baseline_loader = fixture_baseline_loader(config, logger)
        rtt_measurement = RTTMeasurement(
            logger,
            timeout_ping=config.timeout_ping,
            aggregation_strategy=RTTAggregationStrategy.MEDIAN,
        )
        with patch("wanctl.steering.daemon.CakeStatsReader"):
            daemon = SteeringDaemon(
                config=config,
                state=state_mgr,
                router=fake_router,
                rtt_measurement=rtt_measurement,
                baseline_loader=baseline_loader,
                logger=logger,
            )
        daemon.cake_reader = fake_cake_reader
        assert daemon.router is fake_router
        assert daemon.cake_reader is fake_cake_reader
        assert daemon.baseline_loader is baseline_loader
        assert daemon._metrics_writer is None
        checked_paths = [state_mgr.state_file, baseline_loader.spectrum_state_path]
        if daemon._storage_db_path:
            checked_paths.append(Path(daemon._storage_db_path))
        for path in checked_paths:
            if _under_production_root(path):
                raise AssertionError(f"production path escaped replay harness: {path}")
        if harness_mode == "hysteresis-only":
            assert daemon.config.use_confidence_scoring is False
        return daemon

    return _factory
