from __future__ import annotations

import json
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
def test_bridge_downsampling_averages_only_complete_buckets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bridge: Path
) -> None:
    namespace = _load_bridge(monkeypatch, tmp_path, bridge)
    now = 1_000_000
    complete_cutoff = ((now - 3_600) // 60) * 60
    base = complete_cutoff - 60
    monkeypatch.setattr(namespace["time"], "time", lambda: now)
    with sqlite3.connect(namespace["METRICS_DB"]) as conn:
        namespace["ensure_metrics_schema"](conn)
        conn.executemany(
            """
            INSERT INTO metrics
                (timestamp, wan_name, metric_name, value, labels, granularity)
            VALUES (?, 'test', 'metric_a', ?, NULL, 'raw')
            """,
            [
                (base + 1, 1.0),
                (base + 2, 3.0),
                (complete_cutoff + 1, 10.0),
            ],
        )
    monkeypatch.setattr(namespace["subprocess"], "run", lambda *_args, **_kwargs: None)

    namespace["downsample_raw_to_1m"]()

    with sqlite3.connect(namespace["METRICS_DB"]) as conn:
        raw_rows = conn.execute(
            "SELECT timestamp, value FROM metrics WHERE granularity='raw'"
        ).fetchall()
        aggregate_rows = conn.execute(
            "SELECT timestamp, metric_name, value, labels FROM metrics WHERE granularity='1m'"
        ).fetchall()
    assert raw_rows == [(complete_cutoff + 1, 10.0)]
    assert aggregate_rows == [(base, "metric_a", 2.0, None)]


@pytest.mark.parametrize("bridge", BRIDGES, ids=("spectrum", "att"))
def test_bridge_downsampling_preserves_labels_uses_mode_and_avoids_duplicates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bridge: Path
) -> None:
    namespace = _load_bridge(monkeypatch, tmp_path, bridge)
    now = 1_000_000
    base = ((now - 7_200) // 60) * 60
    monkeypatch.setattr(namespace["time"], "time", lambda: now)
    rows = [
        (base + 1, "wanctl_cake_tin_delay_us", 10.0, '{"tin":"bulk","ignored":1}', "raw"),
        (base + 2, "wanctl_cake_tin_delay_us", 30.0, '{"ignored":2,"tin":"bulk"}', "raw"),
        (base + 3, "wanctl_cake_tin_delay_us", 100.0, '{"tin":"video"}', "raw"),
        (base + 4, "wanctl_state", 0.0, '{"source":"bridge","direction":"download"}', "raw"),
        (base + 5, "wanctl_state", 1.0, '{"direction":"download","source":"bridge"}', "raw"),
        (
            base + 6,
            "wanctl_state",
            1.0,
            '{"reason":"busy","source":"bridge","direction":"download"}',
            "raw",
        ),
        (
            base + 7,
            "wanctl_state",
            0.0,
            '{"reason":"stable","direction":"download","source":"bridge"}',
            "raw",
        ),
        (base + 8, "wanctl_state", 0.0, '{"source":"bridge"}', "raw"),
        (base + 9, "metric_existing", 1.0, None, "raw"),
        (base, "metric_existing", 99.0, None, "1m"),
    ]
    with sqlite3.connect(namespace["METRICS_DB"]) as conn:
        namespace["ensure_metrics_schema"](conn)
        conn.executemany(
            """
            INSERT INTO metrics
                (timestamp, wan_name, metric_name, value, labels, granularity)
            VALUES (?, 'test', ?, ?, ?, ?)
            """,
            rows,
        )
    monkeypatch.setattr(namespace["subprocess"], "run", lambda *_args, **_kwargs: None)

    traced_statements: list[str] = []
    namespace["metrics_connection"]().set_trace_callback(traced_statements.append)
    namespace["downsample_raw_to_1m"]()
    assert any("timestamp BETWEEN" in statement for statement in traced_statements)

    traced_statements.clear()
    namespace["downsample_raw_to_1m"]()
    assert not any("granularity = '1m'" in statement for statement in traced_statements)

    with sqlite3.connect(namespace["METRICS_DB"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM metrics WHERE granularity='raw'").fetchone() == (
            0,
        )
        aggregate_rows = conn.execute(
            "SELECT metric_name, value, labels FROM metrics "
            "WHERE granularity='1m' ORDER BY metric_name, labels"
        ).fetchall()
    assert aggregate_rows == [
        ("metric_existing", 99.0, None),
        ("wanctl_cake_tin_delay_us", 20.0, '{"tin":"bulk"}'),
        ("wanctl_cake_tin_delay_us", 100.0, '{"tin":"video"}'),
        ("wanctl_state", 1.0, '{"direction":"download","source":"bridge"}'),
        ("wanctl_state", 0.0, '{"source":"bridge"}'),
    ]


@pytest.mark.parametrize("bridge", BRIDGES, ids=("spectrum", "att"))
def test_bridge_reuses_metrics_connection_for_downsampling(
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

    assert len(opened) == 1
    assert opened[0].closed is False
    assert opened[0].execute("PRAGMA synchronous").fetchone() == (1,)
    namespace["close_metrics_connection"]()
    assert opened[0].closed is True


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
    # Use a different state so fire-on-change doesn't skip the second write.
    changed_state = _state()
    changed_state["ewma"] = {"baseline_rtt": 20.0, "load_rtt": 23.0}
    namespace["write_metrics"](changed_state)

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
