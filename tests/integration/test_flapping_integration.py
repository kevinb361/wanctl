"""Integration tests for WANController flapping alert behavior."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wanctl.storage.writer import MetricsWriter
from wanctl.wan_controller import WANController


def _drive_dl_transitions(
    controller: WANController,
    *,
    start_ts: float,
    transition_count: int,
    step_sec: float = 3.0,
    initial_zone: str = "GREEN",
) -> str:
    """Drive a precise number of DL zone transitions through the real controller path."""
    current_zone = initial_zone
    with (
        patch("wanctl.wan_controller.time.monotonic", return_value=start_ts),
        patch("wanctl.alert_engine.time.monotonic", return_value=start_ts),
    ):
        controller._check_flapping_alerts(current_zone, "GREEN")

    for idx in range(1, transition_count + 1):
        current_zone = "RED" if current_zone == "GREEN" else "GREEN"
        ts = start_ts + idx * step_sec
        with (
            patch("wanctl.wan_controller.time.monotonic", return_value=ts),
            patch("wanctl.alert_engine.time.monotonic", return_value=ts),
        ):
            controller._check_flapping_alerts(current_zone, "GREEN")
    return current_zone


def _query_flapping_alerts(db_path: Path) -> list[sqlite3.Row]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, timestamp, alert_type, details
            FROM alerts
            WHERE alert_type = 'flapping_dl'
            ORDER BY id ASC
            """
        ).fetchall()
    finally:
        conn.close()
    return rows


@pytest.fixture
def flapping_controller(tmp_path: Path, mock_autorate_config: MagicMock) -> tuple[WANController, Path]:
    """Create a real WANController with persistent alerting enabled."""
    MetricsWriter._reset_instance()

    db_path = tmp_path / "metrics-spectrum.db"
    mock_autorate_config.state_file = str(tmp_path / "state.json")
    mock_autorate_config.data = {"storage": {"db_path": str(db_path)}}
    mock_autorate_config.alerting_config = {
        "enabled": True,
        "webhook_url": "",
        "default_cooldown_sec": 300,
        "default_sustained_sec": 60,
        "rules": {
            "congestion_flapping": {
                "enabled": True,
                "cooldown_sec": 600,
                "severity": "warning",
                "flap_threshold": 30,
                "flap_window_sec": 120,
                "min_hold_sec": 0,
            }
        },
        "mention_role_id": None,
        "mention_severity": "critical",
        "max_webhooks_per_minute": 20,
    }

    router = MagicMock()
    router.needs_rate_limiting = False
    rtt_measurement = MagicMock()
    logger = MagicMock()

    with patch.object(WANController, "load_state"):
        controller = WANController(
            wan_name="spectrum",
            config=mock_autorate_config,
            router=router,
            rtt_measurement=rtt_measurement,
            logger=logger,
        )

    controller.alert_engine._delivery_callback = None
    yield controller, db_path
    MetricsWriter._reset_instance()


def test_peak_transition_count_reflects_oscillation_intensity(
    flapping_controller: tuple[WANController, Path],
) -> None:
    """Peak count survives pruning so the emitted payload reflects earlier intensity."""
    controller, db_path = flapping_controller
    controller.alert_engine._rules["congestion_flapping"]["flap_threshold"] = 40

    last_zone = _drive_dl_transitions(
        controller,
        start_ts=1000.0,
        transition_count=35,
        step_sec=3.0,
    )
    assert controller._dl_peak_transitions == 35

    controller.alert_engine._rules["congestion_flapping"]["flap_threshold"] = 30
    next_zone = "GREEN" if last_zone == "RED" else "RED"
    fire_ts = 1139.0
    with (
        patch("wanctl.wan_controller.time.monotonic", return_value=fire_ts),
        patch("wanctl.alert_engine.time.monotonic", return_value=fire_ts),
    ):
        controller._check_flapping_alerts(next_zone, "GREEN")

    alerts = _query_flapping_alerts(db_path)
    assert len(alerts) == 1
    details = json.loads(alerts[0]["details"])
    assert details["transition_count"] == 30
    assert details["peak_transition_count"] > details["transition_count"]
    assert details["peak_transition_count"] == 35


def test_flapping_cooldown_suppresses_second_alert_within_window(
    flapping_controller: tuple[WANController, Path],
) -> None:
    """A second flapping episode inside cooldown must not persist another alert."""
    controller, db_path = flapping_controller

    _drive_dl_transitions(
        controller,
        start_ts=2000.0,
        transition_count=30,
        step_sec=3.0,
    )
    first_alerts = _query_flapping_alerts(db_path)
    assert len(first_alerts) == 1
    assert controller.alert_engine.fire_count == 1

    _drive_dl_transitions(
        controller,
        start_ts=2200.0,
        transition_count=30,
        step_sec=3.0,
    )
    second_alerts = _query_flapping_alerts(db_path)
    assert len(second_alerts) == 1
    assert controller.alert_engine.fire_count == 1
