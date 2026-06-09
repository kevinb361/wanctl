from __future__ import annotations

import json
import os
import re
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEPLOY = REPO_ROOT / "scripts" / "deploy.sh"
STATE_BRIDGE = REPO_ROOT / "deploy" / "scripts" / "cake-autorate-att-state-bridge"
QDISC_INIT = REPO_ROOT / "deploy" / "scripts" / "cake-autorate-att-qdisc-init"
CAKE_SERVICE = REPO_ROOT / "deploy" / "systemd" / "cake-autorate-att.service"
BRIDGE_SERVICE = REPO_ROOT / "deploy" / "systemd" / "cake-autorate-att-state-bridge.service"
WATCHDOG_SERVICE = (
    REPO_ROOT / "deploy" / "systemd" / "silicom-bypass-watchdog-cake-autorate-att.service"
)
CAKE_CONFIG = REPO_ROOT / "configs" / "cake-autorate" / "config.att.sh"

ATT_ARTIFACTS = {
    "configs/cake-autorate/config.att.sh",
    "deploy/scripts/cake-autorate-att-qdisc-init",
    "deploy/scripts/cake-autorate-att-state-bridge",
    "deploy/systemd/cake-autorate-att.service",
    "deploy/systemd/cake-autorate-att-state-bridge.service",
    "deploy/systemd/silicom-bypass-watchdog-cake-autorate-att.service",
}

def free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_deploy_script_has_external_att_mode() -> None:
    text = DEPLOY.read_text(encoding="utf-8")

    assert "--with-att-cake-autorate" in text
    assert "deploy_att_cake_autorate" in text
    assert "cake-autorate-att.service" in text
    assert "cake-autorate-att-state-bridge.service" in text


def test_att_cake_autorate_artifacts_are_repo_owned() -> None:
    assert CAKE_SERVICE.exists()
    assert BRIDGE_SERVICE.exists()
    assert WATCHDOG_SERVICE.exists()
    assert QDISC_INIT.exists()
    assert STATE_BRIDGE.exists()
    assert CAKE_CONFIG.exists()

    service = CAKE_SERVICE.read_text(encoding="utf-8")
    assert "Conflicts=wanctl@att.service" in service
    assert "ExecStart=/opt/cake-autorate/cake-autorate.sh /etc/cake-autorate/config.att.sh" in service
    assert "ExecStartPre=/usr/local/sbin/cake-autorate-att-qdisc-init" in service

    bridge_service = BRIDGE_SERVICE.read_text(encoding="utf-8")
    assert "Wants=cake-autorate-att.service" in bridge_service
    assert "Environment=WANCTL_EXTERNAL_WAN_NAME=att" in bridge_service
    assert "Environment=WANCTL_EXTERNAL_DL_IF=att-router" in bridge_service
    assert "Environment=WANCTL_EXTERNAL_UL_IF=att-modem" in bridge_service
    assert "Environment=WANCTL_EXTERNAL_STATE_PATH=/var/lib/wanctl/att_state.json" in bridge_service
    assert "Environment=WANCTL_EXTERNAL_METRICS_DB=/var/lib/wanctl/metrics-att.db" in bridge_service
    assert "Environment=WANCTL_EXTERNAL_BASELINE_RTT=28.42043789020452" in bridge_service
    assert "Environment=CAKE_AUTORATE_BRIDGE_HEALTH_HOST=10.10.110.227" in bridge_service
    assert "ExecStart=/usr/local/sbin/cake-autorate-att-state-bridge" in bridge_service

    qdisc = QDISC_INIT.read_text(encoding="utf-8")
    assert "dev att-router root cake bandwidth 95000Kbit" in qdisc
    assert "dev att-modem root cake bandwidth 19000Kbit" in qdisc
    assert "diffserv4" in qdisc
    assert "ingress" in qdisc
    assert "egress" in qdisc
    assert "ack-filter" in qdisc
    assert "ptm" in qdisc
    assert "overhead 22 mpu 64" in qdisc
    assert "rtt 35ms" in qdisc
    assert "nowash" in qdisc
    assert "memlimit 32Mb" in qdisc

    config = CAKE_CONFIG.read_text(encoding="utf-8")
    assert "dl_if=att-router" in config
    assert "ul_if=att-modem" in config
    assert "adjust_dl_shaper_rate=1" in config
    assert "adjust_ul_shaper_rate=0" in config
    assert "base_dl_shaper_rate_kbps=95000" in config
    assert "base_ul_shaper_rate_kbps=19000" in config
    assert "pinger_method=fping" in config
    assert 'ping_extra_args="-S 10.10.110.227"' in config

    watchdog = WATCHDOG_SERVICE.read_text(encoding="utf-8")
    assert "Requires=bpctl-silicom.service" in watchdog
    assert "Environment=IFACE=att-modem" in watchdog
    assert "Environment=WANCTL_UNIT=cake-autorate-att.service" in watchdog
    assert "ExecStart=/usr/local/sbin/wanctl-bpctl-watchdog-petter" in watchdog
    assert "ExecStop=/usr/local/sbin/wanctl-bpctl-watchdog-bypass" in watchdog


def test_state_bridge_parses_att_summary_and_writes_wanctl_state(tmp_path: Path) -> None:
    log_dir = tmp_path / "log"
    state_dir = tmp_path / "state"
    log_dir.mkdir()
    state_dir.mkdir()
    log_path = log_dir / "cake-autorate.att.log"
    state_path = state_dir / "att_state.json"
    log_path.write_text(
        "LOAD; 0; 0; 0; 0; 0; 95000; 19000\n"
        "SUMMARY; 0; 0; 0; 0; 0; 0; 0; 0; dl_idle; ul_idle; 94500; 18900\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env.update(
        {
            "CAKE_AUTORATE_BRIDGE_LOG": str(log_path),
            "WANCTL_EXTERNAL_WAN_NAME": "att",
            "WANCTL_EXTERNAL_DL_IF": "att-router",
            "WANCTL_EXTERNAL_UL_IF": "att-modem",
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
    assert state["download"]["current_rate"] == 94_500_000
    assert state["upload"]["current_rate"] == 18_900_000
    assert state["congestion"] == {"dl_state": "GREEN", "ul_state": "GREEN"}
    assert state["last_applied"] == {"dl_rate": 94_500_000, "ul_rate": 18_900_000}


def test_state_bridge_writes_att_metrics_database(tmp_path: Path) -> None:
    log_path = tmp_path / "cake-autorate.att.log"
    state_path = tmp_path / "att_state.json"
    metrics_path = tmp_path / "metrics-att.db"
    log_path.write_text(
        "SUMMARY; 0; 0; 0; 0; 0; 0; 0; 0; dl_high; ul_idle; 95000; 19000\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env.update(
        {
            "CAKE_AUTORATE_BRIDGE_LOG": str(log_path),
            "WANCTL_EXTERNAL_WAN_NAME": "att",
            "WANCTL_EXTERNAL_DL_IF": "att-router",
            "WANCTL_EXTERNAL_UL_IF": "att-modem",
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
        "att",
        "wanctl_rate_download_mbps",
        95.0,
        None,
        "raw",
    )
    assert by_metric["wanctl_rate_upload_mbps"] == (
        "att",
        "wanctl_rate_upload_mbps",
        19.0,
        None,
        "raw",
    )
    assert by_metric["wanctl_rtt_ms"][0] == "att"
    assert by_metric["wanctl_rtt_ms"][2] > 0
    assert by_metric["wanctl_rtt_delta_ms"][0] == "att"
    assert by_metric["wanctl_rtt_delta_ms"][2] >= 0
    assert json.loads(by_metric["wanctl_state"][3]) == {"source": "cake-autorate-state-bridge"}


def test_state_bridge_serves_att_health_endpoint(tmp_path: Path) -> None:
    log_path = tmp_path / "cake-autorate.att.log"
    state_path = tmp_path / "att_state.json"
    port = free_tcp_port()
    log_path.write_text(
        "LOAD; 0; 0; 0; 0; 0; 95000; 19000\n"
        "SUMMARY; 0; 0; 0; 0; 0; 0; 0; 0; dl_idle; ul_idle; 95000; 19000\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env.update(
        {
            "CAKE_AUTORATE_BRIDGE_LOG": str(log_path),
            "WANCTL_EXTERNAL_WAN_NAME": "att",
            "WANCTL_EXTERNAL_DL_IF": "att-router",
            "WANCTL_EXTERNAL_UL_IF": "att-modem",
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
        assert wan["name"] == "att"
        assert wan["measurement"]["available"] is True
        assert wan["measurement"]["raw_rtt_ms"] > 0
        assert wan["measurement"]["staleness_sec"] <= 5
        assert wan["download"]["state"] == "GREEN"
        assert wan["upload"]["state"] == "GREEN"
        assert wan["download"]["qdisc_bandwidth"] == "95Mbit"
        assert wan["upload"]["qdisc_bandwidth"] == "19Mbit"
        assert wan["last_applied"] == {"dl_rate": 95_000_000, "ul_rate": 19_000_000}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def _att_deploy_function_body(deploy_text: str) -> str:
    match = re.search(r"^deploy_att_cake_autorate\(\) \{\n(?P<body>.*?)^\}", deploy_text, re.S | re.M)
    assert match is not None, "deploy_att_cake_autorate() function not found"
    return match.group("body")


def _att_systemd_array_entries(deploy_text: str) -> set[str]:
    match = re.search(r"^ATT_CAKE_AUTORATE_SYSTEMD=\(\n(?P<body>.*?)^\)", deploy_text, re.S | re.M)
    assert match is not None, "ATT_CAKE_AUTORATE_SYSTEMD array not found"
    return set(re.findall(r'"(deploy/systemd/[^"]+)"', match.group("body")))


def test_deploy_att_file_list_matches_repo() -> None:
    deploy_text = DEPLOY.read_text(encoding="utf-8")
    function_body = _att_deploy_function_body(deploy_text)

    function_paths = set(re.findall(r'\$PROJECT_ROOT/([^"\s]+)', function_body))
    parsed = function_paths | _att_systemd_array_entries(deploy_text)

    extra = parsed - ATT_ARTIFACTS
    missing = ATT_ARTIFACTS - parsed
    nonexistent = {path for path in parsed if not (REPO_ROOT / path).exists()}

    assert not nonexistent, "deploy.sh ATT path references missing repo file(s): " + ", ".join(
        sorted(nonexistent)
    )
    assert not missing, "repo ATT artifact(s) unreferenced by deploy.sh ATT path: " + ", ".join(
        sorted(missing)
    )
    assert not extra, "deploy.sh ATT path references unexpected ATT artifact(s): " + ", ".join(
        sorted(extra)
    )
    assert parsed == ATT_ARTIFACTS
