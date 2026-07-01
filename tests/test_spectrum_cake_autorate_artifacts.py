from __future__ import annotations

import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEPLOY = REPO_ROOT / "scripts" / "deploy.sh"
STATE_BRIDGE = REPO_ROOT / "deploy" / "scripts" / "cake-autorate-spectrum-state-bridge"
QDISC_INIT = REPO_ROOT / "deploy" / "scripts" / "cake-autorate-spectrum-qdisc-init"
CAKE_SERVICE = REPO_ROOT / "deploy" / "systemd" / "cake-autorate-spectrum.service"
BRIDGE_SERVICE = REPO_ROOT / "deploy" / "systemd" / "cake-autorate-spectrum-state-bridge.service"
CAKE_CONFIG = REPO_ROOT / "configs" / "cake-autorate" / "config.spectrum.sh"


def free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_deploy_script_has_external_spectrum_mode() -> None:
    text = DEPLOY.read_text(encoding="utf-8")

    assert "--with-spectrum-cake-autorate" in text
    assert "deploy_spectrum_cake_autorate" in text
    assert "cake-autorate-spectrum.service" in text
    assert "cake-autorate-spectrum-state-bridge.service" in text


def test_spectrum_cake_autorate_artifacts_are_repo_owned() -> None:
    assert CAKE_SERVICE.exists()
    assert BRIDGE_SERVICE.exists()
    assert QDISC_INIT.exists()
    assert STATE_BRIDGE.exists()
    assert CAKE_CONFIG.exists()

    service = CAKE_SERVICE.read_text(encoding="utf-8")
    assert "Conflicts=wanctl@spectrum.service" in service
    assert (
        "ExecStart=/opt/cake-autorate/cake-autorate.sh /etc/cake-autorate/config.spectrum.sh"
        in service
    )
    assert "ExecStartPre=/usr/local/sbin/cake-autorate-spectrum-qdisc-init" in service

    bridge_service = BRIDGE_SERVICE.read_text(encoding="utf-8")
    assert "Wants=cake-autorate-spectrum.service" in bridge_service
    assert "Environment=CAKE_AUTORATE_BRIDGE_HEALTH_HOST=10.10.110.223" in bridge_service
    assert "Environment=WANCTL_EXTERNAL_PING_SOURCE_IP=10.10.110.223" in bridge_service
    assert "Environment=WANCTL_EXTERNAL_PING_HOSTS=1.1.1.1,9.9.9.9,208.67.222.222" in bridge_service
    assert "ExecStart=/usr/local/sbin/cake-autorate-spectrum-state-bridge" in bridge_service

    qdisc = QDISC_INIT.read_text(encoding="utf-8")
    assert "dev spec-router root cake bandwidth 550000Kbit" in qdisc
    assert "dev spec-modem root cake bandwidth 18000Kbit" in qdisc
    assert "diffserv4" in qdisc
    assert "overhead 18 mpu 64" in qdisc

    config = CAKE_CONFIG.read_text(encoding="utf-8")
    assert "dl_if=spec-router" in config
    assert "ul_if=spec-modem" in config
    assert "adjust_dl_shaper_rate=1" in config
    assert "adjust_ul_shaper_rate=1" in config
    assert "pinger_method=fping" in config
    assert 'ping_extra_args="-S 10.10.110.223"' in config


def test_state_bridge_parses_cake_autorate_summary_and_writes_wanctl_state(tmp_path: Path) -> None:
    log_dir = tmp_path / "log"
    state_dir = tmp_path / "state"
    log_dir.mkdir()
    state_dir.mkdir()
    log_path = log_dir / "cake-autorate.spectrum.log"
    state_path = state_dir / "spectrum_state.json"
    log_path.write_text(
        "LOAD; 0; 0; 0; 0; 0; 550000; 18000\n"
        "SUMMARY; 0; 0; 0; 0; 0; 0; 0; 0; dl_idle; ul_idle; 549500; 17900\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env.update(
        {
            "CAKE_AUTORATE_BRIDGE_LOG": str(log_path),
            "WANCTL_EXTERNAL_STATE_PATH": str(state_path),
            "CAKE_AUTORATE_BRIDGE_ONESHOT": "1",
            "WANCTL_STATE_CHOWN": "0",
            "WANCTL_EXTERNAL_METRICS_ENABLED": "0",
        }
    )
    result = subprocess.run(
        [sys.executable, str(STATE_BRIDGE)],
        cwd=str(REPO_ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["source"] == "cake-autorate-state-bridge"
    assert state["download"]["current_rate"] == 549_500_000
    assert state["upload"]["current_rate"] == 17_900_000
    assert state["congestion"] == {"dl_state": "GREEN", "ul_state": "GREEN"}
    assert state["last_applied"] == {"dl_rate": 549_500_000, "ul_rate": 17_900_000}


def test_state_bridge_writes_metrics_database_when_configured(tmp_path: Path) -> None:
    log_path = tmp_path / "cake-autorate.spectrum.log"
    state_path = tmp_path / "spectrum_state.json"
    metrics_path = tmp_path / "metrics-spectrum.db"
    log_path.write_text(
        "SUMMARY; 0; 0; 0; 0; 0; 0; 0; 0; dl_high; ul_idle; 600000; 18000\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env.update(
        {
            "CAKE_AUTORATE_BRIDGE_LOG": str(log_path),
            "WANCTL_EXTERNAL_STATE_PATH": str(state_path),
            "WANCTL_EXTERNAL_METRICS_DB": str(metrics_path),
            "CAKE_AUTORATE_BRIDGE_ONESHOT": "1",
            "WANCTL_STATE_CHOWN": "0",
        }
    )
    result = subprocess.run(
        [sys.executable, str(STATE_BRIDGE)],
        cwd=str(REPO_ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    with sqlite3.connect(metrics_path) as conn:
        rows = conn.execute(
            "select wan_name, metric_name, value, labels, granularity from metrics order by metric_name"
        ).fetchall()

    by_metric = {row[1]: row for row in rows}
    assert by_metric["wanctl_rate_download_mbps"] == (
        "spectrum",
        "wanctl_rate_download_mbps",
        600.0,
        None,
        "raw",
    )
    assert by_metric["wanctl_rate_upload_mbps"] == (
        "spectrum",
        "wanctl_rate_upload_mbps",
        18.0,
        None,
        "raw",
    )
    assert by_metric["wanctl_rtt_ms"][2] > 0
    assert by_metric["wanctl_rtt_delta_ms"][2] >= 0
    assert json.loads(by_metric["wanctl_state"][3]) == {"source": "cake-autorate-state-bridge"}


def test_state_bridge_serves_wanctl_compatible_health_endpoint(tmp_path: Path) -> None:
    log_path = tmp_path / "cake-autorate.spectrum.log"
    state_path = tmp_path / "spectrum_state.json"
    port = free_tcp_port()
    log_path.write_text(
        "SUMMARY; 0; 0; 0; 0; 0; 0; 0; 0; dl_idle; ul_idle; 549500; 17900\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env.update(
        {
            "CAKE_AUTORATE_BRIDGE_LOG": str(log_path),
            "WANCTL_EXTERNAL_STATE_PATH": str(state_path),
            "WANCTL_STATE_CHOWN": "0",
            "WANCTL_EXTERNAL_METRICS_ENABLED": "0",
            "CAKE_AUTORATE_BRIDGE_POLL_INTERVAL": "0.05",
            "CAKE_AUTORATE_BRIDGE_HEALTH_PORT": str(port),
        }
    )
    proc = subprocess.Popen(
        [sys.executable, str(STATE_BRIDGE)],
        cwd=str(REPO_ROOT),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.time() + 5
        payload = None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=0.2) as resp:
                    payload = json.loads(resp.read().decode())
                if payload.get("status") == "healthy":
                    break
            except OSError:
                pass
            time.sleep(0.05)
        assert payload is not None
        wan = payload["wans"][0]
        assert payload["source"] == "cake-autorate-state-bridge"
        assert payload["status"] == "healthy"
        assert payload["version"] == "cake-autorate-trial"
        assert wan["name"] == "spectrum"
        expected_measurement_order = ["available", "raw_rtt_ms", "staleness_sec"]
        assert list(wan["measurement"].keys())[: len(expected_measurement_order)] == (
            expected_measurement_order
        )
        assert wan["measurement"]["available"] is True
        assert wan["measurement"]["raw_rtt_ms"] > 0
        assert wan["measurement"]["staleness_sec"] <= 5
        assert wan["measurement"]["producer"] == "cake-autorate-bridge"
        assert wan["measurement"]["backend"] is None
        assert wan["measurement"]["source_ip"] is None
        assert wan["download"]["state"] == "GREEN"
        assert wan["upload"]["state"] == "GREEN"
        assert wan["download"]["qdisc_bandwidth"] == "550Mbit"
        assert wan["upload"]["qdisc_bandwidth"] == "18Mbit"
        assert wan["last_applied"] == {"dl_rate": 549_500_000, "ul_rate": 17_900_000}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def test_state_bridge_serves_degraded_health_endpoint_without_state(tmp_path: Path) -> None:
    log_path = tmp_path / "cake-autorate.spectrum.log"
    state_path = tmp_path / "missing-spectrum-state.json"
    port = free_tcp_port()
    log_path.write_text("", encoding="utf-8")

    env = os.environ.copy()
    env.update(
        {
            "CAKE_AUTORATE_BRIDGE_LOG": str(log_path),
            "WANCTL_EXTERNAL_STATE_PATH": str(state_path),
            "WANCTL_STATE_CHOWN": "0",
            "WANCTL_EXTERNAL_METRICS_ENABLED": "0",
            "CAKE_AUTORATE_BRIDGE_POLL_INTERVAL": "60",
            "CAKE_AUTORATE_BRIDGE_HEALTH_PORT": str(port),
        }
    )
    proc = subprocess.Popen(
        [sys.executable, str(STATE_BRIDGE)],
        cwd=str(REPO_ROOT),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.time() + 5
        payload = None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=0.2) as resp:
                    payload = json.loads(resp.read().decode())
                break
            except OSError:
                time.sleep(0.05)
        assert payload is not None
        wan = payload["wans"][0]
        assert payload["source"] == "cake-autorate-state-bridge"
        assert payload["status"] == "degraded"
        assert wan["name"] == "spectrum"
        expected_measurement_order = ["available", "raw_rtt_ms", "staleness_sec"]
        assert list(wan["measurement"].keys())[: len(expected_measurement_order)] == (
            expected_measurement_order
        )
        assert wan["measurement"]["available"] is False
        assert wan["measurement"]["raw_rtt_ms"] is None
        assert wan["measurement"]["staleness_sec"] is None
        assert wan["measurement"]["producer"] == "cake-autorate-bridge"
        assert wan["measurement"]["backend"] is None
        assert wan["measurement"]["source_ip"] is None
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def test_state_bridge_measures_rtt_with_fping(tmp_path: Path) -> None:
    log_path = tmp_path / "cake-autorate.spectrum.log"
    state_path = tmp_path / "spectrum_state.json"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fping = fake_bin / "fping"
    fping.write_text(
        "#!/bin/sh\n"
        "echo '1.1.1.1 : [0], 64 bytes, 20.0 ms (20.0 avg, 0% loss)'\n"
        "echo '9.9.9.9 : [0], 64 bytes, 25.0 ms (25.0 avg, 0% loss)'\n"
        "echo '208.67.222.222 : [0], 64 bytes, 30.0 ms (30.0 avg, 0% loss)'\n"
        "exit 0\n",
        encoding="utf-8",
    )
    fping.chmod(0o755)
    log_path.write_text(
        "SUMMARY; 0; 0; 0; 0; 0; 0; 0; 0; dl_idle; ul_idle; 550000; 18000\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env.update(
        {
            "CAKE_AUTORATE_BRIDGE_LOG": str(log_path),
            "WANCTL_EXTERNAL_STATE_PATH": str(state_path),
            "CAKE_AUTORATE_BRIDGE_ONESHOT": "1",
            "WANCTL_STATE_CHOWN": "0",
            "WANCTL_EXTERNAL_METRICS_ENABLED": "0",
            "WANCTL_EXTERNAL_BASELINE_RTT": "22.0",
            "WANCTL_EXTERNAL_PING_SOURCE_IP": "10.10.110.223",
            "WANCTL_EXTERNAL_PING_HOSTS": "1.1.1.1,9.9.9.9,208.67.222.222",
            "PATH": f"{fake_bin}:{env.get('PATH', '')}",
        }
    )
    result = subprocess.run(
        [sys.executable, str(STATE_BRIDGE)],
        cwd=str(REPO_ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["ewma"]["load_rtt"] == 25.0
    assert 22.0 < state["ewma"]["baseline_rtt"] < 25.0
    assert state["measurement"]["backend"] == "fping"
    assert state["measurement"]["source_ip"] == "10.10.110.223"
    assert state["measurement"]["hosts"] == ["1.1.1.1", "9.9.9.9", "208.67.222.222"]
