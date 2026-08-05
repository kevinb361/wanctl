from __future__ import annotations

import json
import runpy
import sqlite3
import time
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
    monkeypatch.setenv("WANCTL_EXTERNAL_STATE_PATH", str(tmp_path / "state" / f"{wan}.json"))
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
def test_previous_state_snapshot_is_shared_by_rtt_and_cake_extractors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bridge: Path
) -> None:
    namespace = _load_bridge(monkeypatch, tmp_path, bridge)
    state_path = namespace["STATE"]
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "ewma": {"baseline_rtt": 20.0, "load_rtt": 22.0},
                "cake_stats": {"directions": {"download": {"bytes": 123}}},
            }
        ),
        encoding="utf-8",
    )

    snapshot = namespace["previous_state_snapshot"]()
    state_path.unlink()

    assert namespace["old_rtt"](snapshot) == (20.0, 22.0)
    assert namespace["previous_cake_directions"](snapshot) == {
        "download": {"bytes": 123}
    }
    namespace["old_rtt"].__globals__["_PREVIOUS_STATE_CACHE"] = namespace[
        "_READ_PREVIOUS_STATE"
    ]
    assert namespace["old_rtt"]() == (
        namespace["DEFAULT_BASELINE_RTT"],
        namespace["DEFAULT_BASELINE_RTT"],
    )


@pytest.mark.parametrize("bridge", BRIDGES, ids=("spectrum", "att"))
def test_bridge_state_write_recovers_missing_parent_and_partial_writes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bridge: Path
) -> None:
    namespace = _load_bridge(monkeypatch, tmp_path, bridge)
    state_path = namespace["STATE"]
    assert not state_path.parent.exists()

    state = _state()
    real_write = namespace["os"].write

    def partial_write(fd: int, payload: bytes) -> int:
        return real_write(fd, payload[:7])

    monkeypatch.setattr(namespace["os"], "write", partial_write)
    namespace["write_state"](state)
    monkeypatch.setattr(namespace["os"], "write", real_write)

    assert namespace["previous_state_snapshot"]() is state
    assert state_path.stat().st_mode & 0o777 == 0o600
    assert state_path.read_text(encoding="utf-8") == json.dumps(
        state, separators=(",", ":")
    ) + "\n"


@pytest.mark.parametrize("bridge", BRIDGES, ids=("spectrum", "att"))
def test_bridge_downsampling_preserves_avg_counts_and_partial_buckets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bridge: Path
) -> None:
    namespace = _load_bridge(monkeypatch, tmp_path, bridge)
    base = ((int(time.time()) - 7_200) // 60) * 60
    with sqlite3.connect(namespace["METRICS_DB"]) as conn:
        namespace["ensure_metrics_schema"](conn)
        conn.executemany(
            """
            INSERT INTO metrics
                (timestamp, wan_name, metric_name, value, labels, granularity)
            VALUES (?, 'test', ?, ?, NULL, 'raw')
            """,
            [
                (base + 1, "metric_a", 1.0),
                (base + 2, "metric_a", 3.0),
                (base + 61, "metric_a", 10.0),
                (base + 1, "metric_b", 8.0),
            ],
        )
    monkeypatch.setattr(namespace["subprocess"], "run", lambda *_args, **_kwargs: None)

    namespace["downsample_raw_to_1m"]()

    with sqlite3.connect(namespace["METRICS_DB"]) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM metrics WHERE granularity='raw'"
        ).fetchone() == (0,)
        rows = conn.execute(
            "SELECT timestamp, metric_name, value, labels FROM metrics "
            "WHERE granularity='1m' ORDER BY metric_name, timestamp"
        ).fetchall()
    assert rows == [
        (base, "metric_a", 2.0, '{"downsampled_from":2}'),
        (base + 60, "metric_a", 10.0, '{"downsampled_from":1}'),
        (base, "metric_b", 8.0, '{"downsampled_from":1}'),
    ]


@pytest.mark.parametrize("bridge", BRIDGES, ids=("spectrum", "att"))
def test_bridge_reuses_metrics_connection_for_downsampling_and_bounds_cleanup(
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

    assert len(opened) == 2
    assert opened[0].closed is False
    assert opened[0].execute("PRAGMA synchronous").fetchone() == (1,)
    assert opened[1].closed is True
    namespace["close_metrics_connection"]()
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
    assert opened[0].closed is True
    assert opened[1].closed is False
    namespace["close_metrics_connection"]()
    assert all(conn.closed for conn in opened)
    with real_connect(namespace["METRICS_DB"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM metrics").fetchone() == (6,)


def _summary_row(sequence: int, dl_kbps: int, ul_kbps: int) -> str:
    fields = [
        "SUMMARY",
        str(sequence),
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "dl_idle",
        "ul_idle",
        str(dl_kbps),
        str(ul_kbps),
    ]
    return "; ".join(fields) + "\n"


@pytest.mark.parametrize("bridge", BRIDGES, ids=("spectrum", "att"))
def test_startup_log_scan_expands_past_malformed_tail(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bridge: Path
) -> None:
    namespace = _load_bridge(monkeypatch, tmp_path, bridge)
    log = tmp_path / "cake-autorate.log"
    namespace["latest_parsed_row"].__globals__["LOG"] = log
    log.write_bytes(
        _summary_row(1, 100_000, 20_000).encode("utf-8")
        + (b"malformed filler line\n" * 4_000)
    )

    assert namespace["latest_parsed_row"]() == (
        100_000_000,
        20_000_000,
        "dl_idle",
        "ul_idle",
    )


@pytest.mark.parametrize("bridge", BRIDGES, ids=("spectrum", "att"))
def test_incremental_log_reader_handles_idle_append_partial_truncate_and_rotation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bridge: Path
) -> None:
    namespace = _load_bridge(monkeypatch, tmp_path, bridge)
    log = tmp_path / "cake-autorate.log"
    namespace["latest_parsed_row"].__globals__["LOG"] = log

    log.write_text(_summary_row(1, 100_000, 20_000), encoding="utf-8")
    assert namespace["latest_parsed_row"]() == (100_000_000, 20_000_000, "dl_idle", "ul_idle")
    assert namespace["latest_parsed_row"]() == (100_000_000, 20_000_000, "dl_idle", "ul_idle")

    with log.open("a", encoding="utf-8") as handle:
        handle.write(_summary_row(2, 110_000, 21_000))
    assert namespace["latest_parsed_row"]() == (110_000_000, 21_000_000, "dl_idle", "ul_idle")

    partial = _summary_row(3, 120_000, 22_000)
    split_at = len(partial) // 2
    with log.open("a", encoding="utf-8") as handle:
        handle.write(partial[:split_at])
    assert namespace["latest_parsed_row"]() == (110_000_000, 21_000_000, "dl_idle", "ul_idle")
    with log.open("a", encoding="utf-8") as handle:
        handle.write(partial[split_at:])
    assert namespace["latest_parsed_row"]() == (120_000_000, 22_000_000, "dl_idle", "ul_idle")

    # Detect copytruncate even if the rewritten file regrows beyond the old offset.
    rewritten = (_summary_row(4, 130_000, 23_000) * 8) + _summary_row(5, 131_000, 23_100)
    log.write_text(rewritten, encoding="utf-8")
    assert namespace["latest_parsed_row"]() == (131_000_000, 23_100_000, "dl_idle", "ul_idle")

    replacement = tmp_path / "replacement.log"
    replacement.write_text(_summary_row(6, 140_000, 24_000), encoding="utf-8")
    replacement.replace(log)
    assert namespace["latest_parsed_row"]() == (140_000_000, 24_000_000, "dl_idle", "ul_idle")


@pytest.mark.parametrize("bridge", BRIDGES, ids=("spectrum", "att"))
def test_bridge_reopens_persistent_connection_after_database_replacement(
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
    for suffix in ("", "-wal", "-shm"):
        Path(f"{namespace['METRICS_DB']}{suffix}").unlink(missing_ok=True)
    namespace["write_metrics"](_state())

    assert len(opened) == 2
    assert opened[0].closed is True
    with real_connect(namespace["METRICS_DB"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM metrics").fetchone() == (6,)
    namespace["close_metrics_connection"]()


def test_external_bridge_metrics_storage_is_durable_by_contract() -> None:
    for wan, service in SERVICES.items():
        text = service.read_text(encoding="utf-8")
        assert f"WANCTL_EXTERNAL_METRICS_DB=/var/lib/wanctl/metrics-{wan}.db" in text
        assert f"/run/wanctl/metrics-{wan}.db" not in text

    deployment = " ".join(DEPLOYMENT_DOC.read_text(encoding="utf-8").split())
    assert "must remain regular files under `/var/lib/wanctl`" in deployment
    assert "Symlinking them into `/run/wanctl` is unsupported" in deployment
