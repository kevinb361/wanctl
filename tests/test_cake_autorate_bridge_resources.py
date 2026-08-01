from __future__ import annotations

import runpy
import sqlite3
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGES = (
    REPO_ROOT / "deploy" / "scripts" / "cake-autorate-spectrum-state-bridge",
    REPO_ROOT / "deploy" / "scripts" / "cake-autorate-att-state-bridge",
)
SERVICES = {
    "spectrum": REPO_ROOT / "deploy" / "systemd" / "cake-autorate-spectrum-state-bridge.service",
    "att": REPO_ROOT / "deploy" / "systemd" / "cake-autorate-att-state-bridge.service",
}
DEPLOYMENT_DOC = REPO_ROOT / "docs" / "DEPLOYMENT.md"


def _load_bridge(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bridge: Path) -> dict[str, Any]:
    wan = "att" if "-att-" in bridge.name else "spectrum"
    monkeypatch.setenv("WANCTL_EXTERNAL_WAN_NAME", wan)
    monkeypatch.setenv("WANCTL_EXTERNAL_METRICS_DB", str(tmp_path / f"metrics-{wan}.db"))
    monkeypatch.setenv("WANCTL_EXTERNAL_METRICS_ENABLED", "1")
    monkeypatch.setenv("WANCTL_STATE_CHOWN", "0")
    return runpy.run_path(str(bridge))


def _state() -> dict[str, Any]:
    return {
        "ewma": {"baseline_rtt": 20.0, "load_rtt": 22.0},
        "last_applied": {"dl_rate": 100_000_000, "ul_rate": 20_000_000},
        "congestion": {"dl_state": "GREEN", "ul_state": "GREEN"},
    }


class TrackingConnection(sqlite3.Connection):
    closed = False

    def close(self) -> None:
        self.closed = True
        super().close()


class LockedConnection(TrackingConnection):
    def execute(self, sql: str, parameters: tuple[Any, ...] = (), /) -> sqlite3.Cursor:
        raise sqlite3.OperationalError("database is locked")


@pytest.mark.parametrize("bridge", BRIDGES, ids=("spectrum", "att"))
def test_bridge_closes_every_metrics_connection_on_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bridge: Path
) -> None:
    namespace = _load_bridge(monkeypatch, tmp_path, bridge)
    real_connect = sqlite3.connect
    opened: list[TrackingConnection] = []

    def tracked_connect(*args: Any, **kwargs: Any) -> TrackingConnection:
        kwargs["factory"] = TrackingConnection
        conn = real_connect(*args, **kwargs)
        assert isinstance(conn, TrackingConnection)
        opened.append(conn)
        return conn

    monkeypatch.setattr(sqlite3, "connect", tracked_connect)

    namespace["write_metrics"](_state())
    namespace["downsample_raw_to_1m"]()
    namespace["cleanup_old_metrics"]()

    assert len(opened) == 3
    assert all(conn.closed for conn in opened)


@pytest.mark.parametrize("bridge", BRIDGES, ids=("spectrum", "att"))
def test_bridge_closes_locked_connection_before_retry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bridge: Path
) -> None:
    namespace = _load_bridge(monkeypatch, tmp_path, bridge)
    real_connect = sqlite3.connect
    opened: list[TrackingConnection] = []
    attempts = 0

    def retrying_connect(*args: Any, **kwargs: Any) -> TrackingConnection:
        nonlocal attempts
        attempts += 1
        kwargs["factory"] = LockedConnection if attempts == 1 else TrackingConnection
        conn = real_connect(*args, **kwargs)
        assert isinstance(conn, TrackingConnection)
        opened.append(conn)
        return conn

    monkeypatch.setattr(sqlite3, "connect", retrying_connect)
    monkeypatch.setattr(namespace["time"], "sleep", lambda _seconds: None)

    namespace["write_metrics"](_state())

    assert attempts == 2
    assert all(conn.closed for conn in opened)
    with real_connect(namespace["METRICS_DB"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM metrics").fetchone() == (6,)


def test_external_bridge_metrics_storage_is_durable_by_contract() -> None:
    for wan, service in SERVICES.items():
        text = service.read_text(encoding="utf-8")
        assert f"WANCTL_EXTERNAL_METRICS_DB=/var/lib/wanctl/metrics-{wan}.db" in text
        assert f"/run/wanctl/metrics-{wan}.db" not in text

    deployment = " ".join(DEPLOYMENT_DOC.read_text(encoding="utf-8").split())
    assert "must remain regular files under `/var/lib/wanctl`" in deployment
    assert "Symlinking them into `/run/wanctl` is unsupported" in deployment
