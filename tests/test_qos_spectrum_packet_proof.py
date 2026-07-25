from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "qos-spectrum-packet-proof.sh"
ANALYZER = ROOT / "scripts" / "qos_packet_proof_analyzer.py"


def load_analyzer() -> ModuleType:
    spec = importlib.util.spec_from_file_location("qos_packet_proof_analyzer", ANALYZER)
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


def test_dry_run_renders_four_class_plan_without_creating_output(tmp_path: Path) -> None:
    output_dir = tmp_path / "proof"

    result = run_script(
        "--output-dir",
        str(output_dir),
        "--probe-target",
        "203.0.113.10",
        "--source-ip",
        "10.10.110.226",
        "--source-ssh-host",
        "source-host",
        "--dry-run",
    )

    assert result.returncode == 0, result.stderr
    assert "POSTURE=DRY_RUN_NO_TRAFFIC" in result.stdout
    assert "CAPTURE=cake-shaper/spec-router DIRECTION=in" in result.stdout
    assert "CLASS=EF PROTO=tcp DST_PORT=22 EXPECTED_DSCP=46" in result.stdout
    assert "CLASS=AF31 PROTO=tcp DST_PORT=443 EXPECTED_DSCP=26" in result.stdout
    assert "CLASS=CS1 PROTO=tcp DST_PORT=119 EXPECTED_DSCP=8" in result.stdout
    assert "CLASS=CS0 PROTO=udp DST_PORT=9 EXPECTED_DSCP=0" in result.stdout
    assert "TCP_CAPTURE=SYN_ONLY" in result.stdout
    assert not output_dir.exists()


def test_rejects_unsafe_remote_tokens_before_dry_run(tmp_path: Path) -> None:
    result = run_script(
        "--output-dir",
        str(tmp_path / "proof"),
        "--probe-target",
        "203.0.113.10;reboot",
        "--source-ip",
        "10.10.110.226",
        "--source-ssh-host",
        "source-host",
        "--dry-run",
    )

    assert result.returncode == 2
    assert "unsupported probe target" in result.stderr.lower()
    assert result.stdout == ""


def test_analyzer_requires_each_expected_class_on_its_selector() -> None:
    analyzer = load_analyzer()
    capture = (
        """
12:00:00 IP (tos 0xb8, ttl 63) 10.10.110.226.50001 > 203.0.113.10.22: Flags [S]
12:00:01 IP (tos 0x68, ttl 63) 10.10.110.226.50002 > 203.0.113.10.443: Flags [S]
12:00:02 IP (tos 0x20, ttl 63) 10.10.110.226.50003 > 203.0.113.10.119: Flags [S]
12:00:03 IP (tos 0x0, ttl 63) 10.10.110.226.50004 > 203.0.113.10.9: UDP, length 4
"""
        * 5
    )

    report = analyzer.analyze_capture(capture)

    assert report["overall_pass"] is True
    assert {item["class"]: item["observed_dscp"] for item in report["classes"]} == {
        "EF": [46],
        "AF31": [26],
        "CS1": [8],
        "CS0": [0],
    }


def test_analyzer_parses_multiline_tcpdump_and_ignores_established_tcp() -> None:
    analyzer = load_analyzer()
    capture = (
        """
12:00:00 IP (tos 0xb8, ttl 63, proto TCP (6), length 60)
    198.51.100.10.50001 > 203.0.113.10.22: Flags [S], length 0
12:00:01 IP (tos 0x8, ttl 63, proto TCP (6), length 104)
    198.51.100.10.40000 > 203.0.113.10.22: Flags [P.], length 52
12:00:02 IP (tos 0x68, ttl 63, proto TCP (6), length 60)
    198.51.100.10.50002 > 203.0.113.10.443: Flags [S], length 0
12:00:03 IP (tos 0x20, ttl 63, proto TCP (6), length 60)
    198.51.100.10.50003 > 203.0.113.10.119: Flags [S], length 0
12:00:04 IP (tos 0x0, ttl 63, proto UDP (17), length 31)
    198.51.100.10.50004 > 203.0.113.10.9: UDP, length 3
"""
        * 5
    )

    report = analyzer.analyze_capture(capture)

    assert report["overall_pass"] is True
    assert report["classes"][0]["observed_dscp"] == [46]
    assert report["classes"][0]["packets"] == 5


@pytest.mark.parametrize("packet_count", [1, 4, 6])
def test_analyzer_rejects_non_exact_packet_counts(packet_count: int) -> None:
    analyzer = load_analyzer()
    capture = (
        """
12:00:00 IP (tos 0xb8) 198.51.100.10.50001 > 203.0.113.10.22: Flags [S]
12:00:01 IP (tos 0x68) 198.51.100.10.50002 > 203.0.113.10.443: Flags [S]
12:00:02 IP (tos 0x20) 198.51.100.10.50003 > 203.0.113.10.119: Flags [S]
12:00:03 IP (tos 0x0) 198.51.100.10.50004 > 203.0.113.10.9: UDP, length 3
"""
        * packet_count
    )

    report = analyzer.analyze_capture(capture)

    assert report["overall_pass"] is False
    assert all(item["packets"] == packet_count for item in report["classes"])


def test_generator_manifest_requires_exact_expected_flows() -> None:
    analyzer = load_analyzer()
    manifest = {
        "target": "203.0.113.10",
        "source": "10.10.110.226",
        "probes": [
            {"class": "EF", "destination_port": 22, "flows_attempted": 5},
            {"class": "AF31", "destination_port": 443, "flows_attempted": 5},
            {"class": "CS1", "destination_port": 119, "flows_attempted": 5},
            {"class": "CS0", "destination_port": 9, "flows_attempted": 5},
        ],
    }

    assert analyzer.generator_manifest_valid(
        manifest, expected_target="203.0.113.10", expected_source="10.10.110.226"
    )
    manifest["probes"][0]["flows_attempted"] = 4
    assert not analyzer.generator_manifest_valid(
        manifest, expected_target="203.0.113.10", expected_source="10.10.110.226"
    )


@pytest.mark.parametrize(
    ("qdisc", "health", "expected_error"),
    [
        (
            "qdisc cake 8004: root bandwidth 30Mbit diffserv4",
            '{"status":"degraded"}',
            "before Spectrum health is not healthy",
        ),
        (
            "qdisc cake 8004: root bandwidth 30Mbit besteffort",
            '{"status":"healthy"}',
            "before CAKE diffserv4 missing",
        ),
    ],
)
def test_execute_stops_before_generator_when_preflight_is_invalid(
    tmp_path: Path, qdisc: str, health: str, expected_error: str
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    marker = tmp_path / "generator-ran"
    fake_ssh = fake_bin / "ssh"
    fake_ssh.write_text(
        f"""#!/usr/bin/env bash
set -eu
command="${{*: -1}}"
case "$command" in
  *"tc -d qdisc"*) echo '{qdisc}' ;;
  *"curl -fsS"*) echo '{health}' ;;
  *"python3 -"*) cat >/dev/null; touch '{marker}' ;;
esac
"""
    )
    fake_ssh.chmod(0o755)

    result = subprocess.run(
        [
            str(SCRIPT),
            "--output-dir",
            str(tmp_path / "proof"),
            "--probe-target",
            "203.0.113.10",
            "--source-ip",
            "10.10.110.226",
            "--source-ssh-host",
            "source-host",
            "--execute",
            "--confirm-controlled-traffic",
            "QVT-002",
            "--confirm-no-saturation",
            "SAFE-25",
        ],
        cwd=ROOT,
        env={**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert expected_error in result.stderr
    assert not marker.exists()


def test_execute_collects_after_snapshots_when_analysis_fails(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_ssh = fake_bin / "ssh"
    fake_ssh.write_text(
        """#!/usr/bin/env bash
set -eu
command="${*: -1}"
case "$command" in
  *"tc -d qdisc"*) echo 'qdisc cake 8004: root bandwidth 30Mbit diffserv4' ;;
  *"curl -fsS"*) echo '{"status":"healthy"}' ;;
  *"tcpdump"*) cat <<'EOF'
12:00:00 IP (tos 0xb8, proto TCP (6), length 60)
    198.51.100.10.50001 > 203.0.113.10.22: Flags [S], length 0
12:00:01 IP (tos 0x68, proto TCP (6), length 60)
    198.51.100.10.50002 > 203.0.113.10.443: Flags [S], length 0
12:00:02 IP (tos 0x20, proto TCP (6), length 60)
    198.51.100.10.50003 > 203.0.113.10.119: Flags [S], length 0
EOF
    ;;
  *"python3 -"*) cat >/dev/null; echo '{"probes":[]}' ;;
esac
"""
    )
    fake_ssh.chmod(0o755)
    output_dir = tmp_path / "proof"

    result = subprocess.run(
        [
            str(SCRIPT),
            "--output-dir",
            str(output_dir),
            "--probe-target",
            "203.0.113.10",
            "--source-ip",
            "10.10.110.226",
            "--source-ssh-host",
            "source-host",
            "--execute",
            "--confirm-controlled-traffic",
            "QVT-002",
            "--confirm-no-saturation",
            "SAFE-25",
        ],
        cwd=ROOT,
        env={**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert (output_dir / "spec-modem-qdisc-after.txt").is_file()
    assert (output_dir / "spectrum-health-after.json").is_file()


def test_execute_requires_both_exact_confirmation_tokens(tmp_path: Path) -> None:
    output_dir = tmp_path / "proof"
    result = run_script(
        "--output-dir",
        str(output_dir),
        "--probe-target",
        "203.0.113.10",
        "--source-ip",
        "10.10.110.226",
        "--source-ssh-host",
        "source-host",
        "--execute",
        "--confirm-controlled-traffic",
        "QVT-002",
    )

    assert result.returncode == 2
    assert "requires --confirm-controlled-traffic qvt-002" in result.stderr.lower()
    assert not output_dir.exists()
