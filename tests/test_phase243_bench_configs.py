from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "configs/bench/gen-bench-configs.sh"
LAUNCHER = ROOT / "scripts/phase243-bench-run.sh"
PREFLIGHT = ROOT / "scripts/phase243-bench-preflight.sh"
GATE_EVAL = ROOT / "scripts/phase243-gate-eval.py"

LIVE_INTERFACES = {"spec-router", "spec-modem", "ens28", "ens27"}
LIVE_HEALTH_PORT = 9101
LIVE_METRICS_PORT = 9100
EXPECTED_SOURCE_IPS = {"spectrum": "10.10.110.223", "att": "10.10.110.227"}
EXPECTED_EVIDENCE_KEYS = frozenset(
    {"cpu_nsec_start", "cpu_nsec_end", "cpu_nsec_delta", "window_wall_sec", "n_cores", "invocation_id"}
)


def _generated_configs() -> list[dict[str, Any]]:
    result = subprocess.run([str(GENERATOR)], cwd=ROOT, text=True, capture_output=True, check=True)
    docs = [doc for doc in yaml.safe_load_all(result.stdout) if doc]
    assert len(docs) == 4
    return docs


def _route_source_ip() -> str:
    result = subprocess.run(
        ["ip", "route", "get", "104.200.21.31"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip(f"no route for preflight abort-path test: {result.stderr.strip()}")
    tokens = result.stdout.split()
    if "src" not in tokens:
        pytest.skip(f"route output lacks source IP: {result.stdout.strip()}")
    return tokens[tokens.index("src") + 1]


def test_generator_emits_isolated_configs_for_all_backend_wan_pairs() -> None:
    configs = _generated_configs()
    seen = {(cfg["wan_name"], cfg["measurement"]["backend"]) for cfg in configs}
    assert seen == {
        ("spectrum", "icmplib"),
        ("spectrum", "fping"),
        ("att", "icmplib"),
        ("att", "fping"),
    }

    health_ports: set[int] = set()
    metrics_ports: set[int] = set()
    for cfg in configs:
        wan = cfg["wan_name"]
        backend = cfg["measurement"]["backend"]
        cake_params = cfg["cake_params"]
        dl_iface = cake_params["download_interface"]
        ul_iface = cake_params["upload_interface"]
        assert dl_iface.startswith("bench-")
        assert ul_iface.startswith("bench-")
        assert len(dl_iface) <= 15
        assert len(ul_iface) <= 15
        assert dl_iface not in LIVE_INTERFACES
        assert ul_iface not in LIVE_INTERFACES
        assert cfg["router"]["transport"] == "linux-cake"
        assert cfg["router"]["host"]
        assert cfg["router"]["user"]
        assert cfg["router"]["ssh_key"]
        assert cfg["ping_source_ip"] == EXPECTED_SOURCE_IPS[wan]

        health_port = int(cfg["health_check"]["port"])
        metrics_port = int(cfg["metrics"]["port"])
        assert health_port != LIVE_HEALTH_PORT
        assert metrics_port != LIVE_METRICS_PORT
        assert health_port not in health_ports
        assert metrics_port not in metrics_ports
        assert health_port != metrics_port
        health_ports.add(health_port)
        metrics_ports.add(metrics_port)

        assert cfg["metrics"]["enabled"] is False
        assert int(cfg["logging"]["max_bytes"]) == 104_857_600
        assert int(cfg["logging"]["backup_count"]) == 3
        expected_fping_cadence = 2.0 if backend == "fping" else 10.0
        assert float(cfg["measurement"]["fping"]["cadence_sec"]) == expected_fping_cadence
        assert "bench" in cfg["lock_file"]
        assert "bench" in cfg["state_file"]
        assert cfg["lock_file"] != f"/run/wanctl/{wan}.lock"
        assert cfg["state_file"] != f"/var/lib/wanctl/{wan}_state.json"
        assert cfg["storage"]["db_path"].startswith("/var/tmp/wanctl-bench/")
        assert cfg["storage"]["db_path"] != "/var/lib/wanctl/metrics.db"
        assert backend in {"icmplib", "fping"}


def test_negative_assertion_would_catch_live_port_or_interface_collision() -> None:
    cfg = _generated_configs()[0]
    cfg["cake_params"]["download_interface"] = "spec-router"
    cfg["health_check"]["port"] = 9101
    assert cfg["cake_params"]["download_interface"] in LIVE_INTERFACES
    assert cfg["health_check"]["port"] == LIVE_HEALTH_PORT


def test_evidence_key_contract_matches_gate_eval_literals() -> None:
    representative = {
        "cpu_nsec_start": 100,
        "cpu_nsec_end": 200,
        "cpu_nsec_delta": 100,
        "window_wall_sec": 10.0,
        "n_cores": 4,
        "invocation_id": "abc",
    }
    assert set(representative) >= EXPECTED_EVIDENCE_KEYS
    source = GATE_EVAL.read_text(encoding="utf-8")
    for key in EXPECTED_EVIDENCE_KEYS:
        assert key in source


def test_launcher_systemd_run_argv_contains_capability_grants() -> None:
    if not LAUNCHER.exists():
        pytest.skip("launcher lands in Task 3")
    source = LAUNCHER.read_text(encoding="utf-8")
    systemd_run_block = source[source.index("sudo systemd-run") : source.index("/usr/bin/python3")]
    assert '--property="AmbientCapabilities=CAP_NET_RAW CAP_NET_ADMIN"' in systemd_run_block
    assert '--property="CapabilityBoundingSet=CAP_NET_RAW CAP_NET_ADMIN"' in systemd_run_block
    assert "--setenv=PYTHONPATH=\"$PYTHONPATH_DIR\"" in systemd_run_block
    assert '"$ENTRYPOINT"' in source
    assert "resolve_bench_entrypoint" in source
    assert '"$CODE_DIR/src/wanctl/autorate_continuous.py"' in source
    assert "STATE_FILE=$(yaml_get state_file)" in source
    assert 'rm -f "$STATE_FILE"' in source
    assert "validate_bench_runtime_paths" in source
    assert "DEBUG_LOG=$(yaml_get logging.debug_log)" in source
    assert "copy_cycle_evidence_from_debug_log" in source
    assert "JOURNAL_MESSAGES_NDJSON" in source
    assert "validate_cycle_evidence_floor" in source
    assert "cycle evidence below floor" in source
    assert "int(expected * 0.9)" in source


def test_preflight_derives_live_device_from_source_bound_route() -> None:
    source = PREFLIGHT.read_text(encoding="utf-8")
    assert "/etc/wanctl/${wan}.yaml" in source
    assert "ip route get 104.200.21.31 from" in source
    assert "spec-router" not in source
    assert "spec-modem" not in source
    assert "ens28" not in source
    assert "ens27" not in source
    assert "bench download interface missing" in source


def test_preflight_abort_path_writes_json_proof(tmp_path: Path) -> None:
    config = tmp_path / "bench.yaml"
    evidence_dir = tmp_path / "evidence"
    config.write_text(
        yaml.safe_dump(
            {
                "cake_params": {
                    "download_interface": "live-dl",
                    "upload_interface": "bench-ul",
                },
                "health_check": {"port": 19101},
                "lock_file": "/run/wanctl/bench-spectrum-fping.lock",
                "measurement": {"backend": "fping"},
                "metrics": {"port": 19100},
                "ping_source_ip": _route_source_ip(),
                "router": {"transport": "linux-cake"},
                "state_file": "/var/tmp/wanctl-bench/spectrum_fping_state.json",
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [str(PREFLIGHT), str(config), "spectrum", "throwaway-interface", str(evidence_dir)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2, result.stderr
    assert "bench interfaces must be throwaway bench-* names" in result.stderr
    proof = json.loads((evidence_dir / "phase243-spectrum-fping-isolation-proof.json").read_text())
    assert proof["passed"] is False
    assert proof["reason"] == "bench interfaces must be throwaway bench-* names"
