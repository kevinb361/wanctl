from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "qos-iot-wash-proof.sh"
ANALYZER = ROOT / "scripts" / "qos_iot_wash_analyzer.py"
CANARY = "CANARY: DSCP WASH IoT source subnet"
LEGACY = "DSCP WASH: IoT VLAN"


def load_analyzer() -> ModuleType:
    spec = importlib.util.spec_from_file_location("qos_iot_wash_analyzer", ANALYZER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def canary_row(packets: int, byte_count: int) -> dict[str, object]:
    return {
        "comment": CANARY,
        "chain": "prerouting",
        "action": "change-dscp",
        "new-dscp": "0",
        "passthrough": True,
        "src-address": "10.10.120.0/24",
        "packets": packets,
        "bytes": byte_count,
    }


def rows(canary_packets: int, canary_bytes: int) -> list[dict[str, object]]:
    return [
        canary_row(canary_packets, canary_bytes),
        {"comment": LEGACY, "packets": 0, "bytes": 0},
        {"comment": "Trust EF", "in-interface": "!vlan120-IOT", "packets": 100},
        {
            "comment": "Trust AF4x",
            "in-interface": "!vlan120-IOT",
            "dscp": 34,
            "packets": 200,
        },
    ]


def source_capture() -> str:
    return (
        "12:00:00 IP (tos 0xb8, ttl 64, proto ICMP (1), length 84)\n"
        "    10.10.120.2 > 10.10.120.1: ICMP echo request\n"
    )


def test_dry_run_renders_one_packet_canary_plan_without_creating_output(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "proof"

    result = run_script(
        "--output-dir",
        str(output_dir),
        "--source-ssh-host",
        "iot-source",
        "--source-iface",
        "eth0.120",
        "--source-ip",
        "10.10.120.2",
        "--target-ip",
        "10.10.120.1",
        "--expected-mangle-sha256",
        "a" * 64,
        "--dry-run",
    )

    assert result.returncode == 0, result.stderr
    assert "POSTURE=DRY_RUN_NO_TRAFFIC" in result.stdout
    assert "SOURCE=iot-source/eth0.120/10.10.120.2" in result.stdout
    assert "TARGET=10.10.120.1" in result.stdout
    assert "PACKETS=1" in result.stdout
    assert "PROTO=icmp" in result.stdout
    assert "SOURCE_DSCP=46" in result.stdout
    assert "EXPECTED_CANARY_DELTA=1" in result.stdout
    assert "EXPECTED_MANGLE_SHA256=" + "a" * 64 in result.stdout
    assert "TRUST_EXCLUDES_IOT=true" in result.stdout
    assert "COUNTER_SOURCE=routeros_stats_detail" in result.stdout
    assert "MUTATION=false" in result.stdout
    assert not output_dir.exists()


def test_analyzer_requires_one_exact_canary_hit() -> None:
    analyzer = load_analyzer()

    report = analyzer.analyze(rows(7, 588), rows(8, 672), source_capture())

    assert report["overall_pass"] is True
    assert report["canary_rule_shape_valid"] is True
    assert report["canary_order_valid"] is True
    assert report["source_ef_proven"] is True
    assert report["canary_packet_delta"] == 1
    assert report["canary_byte_delta"] == 84
    assert report["legacy_wash_packet_delta"] == 0
    assert report["trust_ef_packet_delta"] == 0
    assert report["trust_af4x_packet_delta"] == 0


def test_analyzer_rejects_legacy_only_hit() -> None:
    analyzer = load_analyzer()
    before = rows(7, 588)
    after = rows(7, 588)
    after[1]["packets"] = 1
    after[1]["bytes"] = 84

    report = analyzer.analyze(before, after, source_capture())

    assert report["overall_pass"] is False
    assert report["canary_packet_delta"] == 0
    assert report["legacy_wash_packet_delta"] == 1


def test_analyzer_rejects_canary_shape_or_order_drift() -> None:
    analyzer = load_analyzer()
    bad_shape = rows(8, 672)
    bad_shape[0]["src-address"] = "10.10.0.0/16"
    bad_order = rows(8, 672)
    bad_order[0], bad_order[1] = bad_order[1], bad_order[0]

    shape_report = analyzer.analyze(rows(7, 588), bad_shape, source_capture())
    order_report = analyzer.analyze(rows(7, 588), bad_order, source_capture())

    assert shape_report["overall_pass"] is False
    assert shape_report["canary_rule_shape_valid"] is False
    assert order_report["overall_pass"] is False
    assert order_report["canary_order_valid"] is False


def test_analyzer_does_not_fail_on_unrelated_trust_counter_growth() -> None:
    analyzer = load_analyzer()
    before = rows(10, 840)
    after = rows(11, 924)
    after[2]["packets"] = 103
    after[3]["packets"] = 240

    report = analyzer.analyze(before, after, source_capture())

    assert report["overall_pass"] is True
    assert report["trust_excludes_iot"] is True
    assert report["trust_ef_packet_delta"] == 3
    assert report["trust_af4x_packet_delta"] == 40
