from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from pathlib import Path
from unittest.mock import patch

from wanctl.irtt_measurement import IRTTMeasurement


def _completed_process() -> subprocess.CompletedProcess[str]:
    payload = {
        "stats": {
            "rtt": {"mean": 25_000_000, "median": 24_000_000},
            "ipdv_round_trip": {"mean": 1_000_000},
            "send_delay": {"median": 12_000_000},
            "receive_delay": {"median": 13_000_000},
            "upstream_loss_percent": 0.0,
            "downstream_loss_percent": 0.0,
            "packets_sent": 10,
            "packets_received": 10,
        }
    }
    return subprocess.CompletedProcess(args=["irtt"], returncode=0, stdout=json.dumps(payload))


def _config(server: str) -> dict:
    return {
        "enabled": True,
        "server": server,
        "port": 2112,
        "duration_sec": 1.0,
        "interval_ms": 100,
    }


def test_measure_serializes_same_target_across_instances(tmp_path: Path) -> None:
    active = 0
    max_active = 0
    lock = threading.Lock()

    def fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.1)
        with lock:
            active -= 1
        return _completed_process()

    with (
        patch("wanctl.irtt_measurement.shutil.which", return_value="/usr/bin/irtt"),
        patch.dict("os.environ", {"WANCTL_RUN_DIR": str(tmp_path)}),
        patch("wanctl.irtt_measurement.subprocess.run", side_effect=fake_run),
    ):
        measurement_a = IRTTMeasurement(_config("104.200.21.31"), logger=threading_logger())
        measurement_b = IRTTMeasurement(_config("104.200.21.31"), logger=threading_logger())

        threads = [
            threading.Thread(target=measurement_a.measure),
            threading.Thread(target=measurement_b.measure),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2.0)

    assert max_active == 1


def test_measure_allows_different_targets_to_run_concurrently(tmp_path: Path) -> None:
    active = 0
    max_active = 0
    gate = threading.Barrier(2)
    lock = threading.Lock()

    def fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal active, max_active
        gate.wait(timeout=2.0)
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.1)
        with lock:
            active -= 1
        return _completed_process()

    with (
        patch("wanctl.irtt_measurement.shutil.which", return_value="/usr/bin/irtt"),
        patch.dict("os.environ", {"WANCTL_RUN_DIR": str(tmp_path)}),
        patch("wanctl.irtt_measurement.subprocess.run", side_effect=fake_run),
    ):
        measurement_a = IRTTMeasurement(_config("104.200.21.31"), logger=threading_logger())
        measurement_b = IRTTMeasurement(_config("104.200.21.32"), logger=threading_logger())

        threads = [
            threading.Thread(target=measurement_a.measure),
            threading.Thread(target=measurement_b.measure),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2.0)

    assert max_active == 2


def threading_logger():
    return logging.getLogger("test_irtt_measurement")
