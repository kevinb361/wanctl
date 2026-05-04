"""Phase 201 predeploy gate shell-test scaffolding."""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest


GATE_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "phase201-predeploy-gate.sh"
DEPLOY_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "deploy.sh"


@pytest.fixture
def fake_remote_yaml(tmp_path):
    """Create tmp YAML and short-circuit the gate's SSH probe via env override."""
    assert GATE_SCRIPT.exists()
    return tmp_path


def _run_gate(yaml_path: Path) -> subprocess.CompletedProcess[bytes]:
    env = {"PHASE201_LOCAL_YAML_OVERRIDE": str(yaml_path), "PATH": "/usr/bin:/bin"}
    return subprocess.run(["bash", str(GATE_SCRIPT)], env=env, capture_output=True, timeout=15)


class TestPredeployGate:
    def test_clean_yaml_passes(self, fake_remote_yaml):
        yaml_path = fake_remote_yaml / "spectrum.yaml"
        yaml_path.write_text(
            textwrap.dedent(
                """
                continuous_monitoring:
                  upload:
                    docsis_mode: true
                    setpoint_mbps: 12
                    factor_down_yellow: 1.0
                    consecutive_yellow_decay_clamp: 40
                """
            ).strip()
        )
        result = _run_gate(yaml_path)
        assert result.returncode == 0, result.stderr.decode()

    def test_target_bloat_ms_in_upload_blocks(self, fake_remote_yaml):
        yaml_path = fake_remote_yaml / "spectrum.yaml"
        yaml_path.write_text(
            textwrap.dedent(
                """
                continuous_monitoring:
                  upload:
                    docsis_mode: true
                    setpoint_mbps: 12
                    target_bloat_ms: 42
                """
            ).strip()
        )
        result = _run_gate(yaml_path)
        assert result.returncode == 1
        assert b"target_bloat_ms" in result.stdout + result.stderr

    def test_warn_bloat_ms_in_upload_blocks(self, fake_remote_yaml):
        yaml_path = fake_remote_yaml / "spectrum.yaml"
        yaml_path.write_text("continuous_monitoring:\n  upload:\n    warn_bloat_ms: 105\n")
        result = _run_gate(yaml_path)
        assert result.returncode == 1
        assert b"warn_bloat_ms" in result.stdout + result.stderr

    def test_docsis_mode_true_without_setpoint_blocks(self, fake_remote_yaml):
        yaml_path = fake_remote_yaml / "spectrum.yaml"
        yaml_path.write_text("continuous_monitoring:\n  upload:\n    docsis_mode: true\n")
        result = _run_gate(yaml_path)
        assert result.returncode == 1
        assert b"setpoint_mbps" in result.stdout + result.stderr

    def test_factor_down_yellow_alone_passes(self, fake_remote_yaml):
        yaml_path = fake_remote_yaml / "spectrum.yaml"
        yaml_path.write_text("continuous_monitoring:\n  upload:\n    factor_down_yellow: 1.0\n")
        result = _run_gate(yaml_path)
        assert result.returncode == 0

    def test_consecutive_yellow_decay_clamp_alone_passes(self, fake_remote_yaml):
        yaml_path = fake_remote_yaml / "spectrum.yaml"
        yaml_path.write_text(
            "continuous_monitoring:\n  upload:\n    consecutive_yellow_decay_clamp: 40\n"
        )
        result = _run_gate(yaml_path)
        assert result.returncode == 0


def _write_executable(path: Path, body: str) -> None:
    path.write_text(textwrap.dedent(body).lstrip())
    path.chmod(0o755)


@pytest.fixture
def fake_deploy_path(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(
        bin_dir / "ssh",
        """
        #!/usr/bin/env bash
        exit 0
        """,
    )
    _write_executable(
        bin_dir / "scp",
        """
        #!/usr/bin/env bash
        exit 0
        """,
    )
    return bin_dir


def _run_deploy(
    tmp_path: Path,
    fake_deploy_path: Path,
    gate_body: str | None,
    *,
    wan_name: str = "spectrum",
    rsync_rc: int = 0,
) -> subprocess.CompletedProcess[bytes]:
    _write_executable(
        fake_deploy_path / "rsync",
        f"""
        #!/usr/bin/env bash
        exit {rsync_rc}
        """,
    )
    env = {
        "PATH": f"{fake_deploy_path}:/usr/bin:/bin",
    }
    if gate_body is not None:
        gate_path = tmp_path / "gate-stub.sh"
        _write_executable(gate_path, gate_body)
        env["PREDEPLOY_GATE"] = str(gate_path)
    else:
        env["PREDEPLOY_GATE"] = str(tmp_path / "missing-gate.sh")
    return subprocess.run(
        ["bash", str(DEPLOY_SCRIPT), wan_name, "cake-shaper"],
        env=env,
        cwd=DEPLOY_SCRIPT.parent.parent,
        capture_output=True,
        timeout=15,
    )


class TestDeployPredeployGateIntegration:
    def test_static_wiring_is_before_rsync_and_fail_closed(self):
        deploy_text = DEPLOY_SCRIPT.read_text()
        assert "phase201-predeploy-gate.sh" in deploy_text
        assert "predeploy gate" in deploy_text
        assert "D-15" in deploy_text
        assert "WARNING" not in deploy_text or "WARNING.*skipping Phase 201 gate" not in deploy_text
        assert "|| gate_rc=$?" in deploy_text
        assert "if !" not in deploy_text or "phase201-predeploy-gate" not in deploy_text.split("if !", 1)[-1].split("\n", 1)[0]

        gate_line = deploy_text.index("phase201-predeploy-gate.sh")
        rsync_line = deploy_text.index("rsync $rsync_opts")
        assert gate_line < rsync_line

    @pytest.mark.parametrize("gate_rc", [1, 2])
    def test_spectrum_gate_exit_code_propagates(self, tmp_path, fake_deploy_path, gate_rc):
        gate_log = tmp_path / "gate-env.txt"
        result = _run_deploy(
            tmp_path,
            fake_deploy_path,
            f"""
            #!/usr/bin/env bash
            printf '%s|%s\n' "$REMOTE_SSH_TARGET" "$REMOTE_YAML_PATH" > {gate_log}
            exit {gate_rc}
            """,
        )
        assert result.returncode == gate_rc, result.stderr.decode() + result.stdout.decode()
        assert gate_log.read_text().strip() == "cake-shaper|/etc/wanctl/spectrum.yaml"
        assert b"ABORTING" in result.stdout + result.stderr

    def test_missing_gate_aborts_spectrum_deploy(self, tmp_path, fake_deploy_path):
        result = _run_deploy(tmp_path, fake_deploy_path, None)
        combined = result.stdout + result.stderr
        assert result.returncode == 2
        assert b"ABORTING" in combined
        assert b"D-15" in combined

    def test_non_spectrum_deploy_skips_gate_without_inspecting_spectrum_yaml(self, tmp_path, fake_deploy_path):
        gate_log = tmp_path / "gate-called.txt"
        result = _run_deploy(
            tmp_path,
            fake_deploy_path,
            f"""
            #!/usr/bin/env bash
            touch {gate_log}
            exit 99
            """,
            wan_name="att",
            rsync_rc=77,
        )
        assert result.returncode == 77
        assert not gate_log.exists()
        assert b"skipping Phase 201 predeploy gate" in result.stdout + result.stderr
