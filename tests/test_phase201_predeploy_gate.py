"""Phase 201 predeploy gate shell-test scaffolding."""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest


# Phase 201 Wave 0 RED scaffolding — Plan 201-02 stubs.
# Implementation lands in Plans 201-03 (config/validator),
# 201-04 (controller core), 201-05 (telemetry / wan_controller),
# 201-07 (predeploy gate), 201-08 (canary extension).


GATE_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "phase201-predeploy-gate.sh"


@pytest.fixture
def fake_remote_yaml(tmp_path):
    """Create a tmp YAML and short-circuit the gate's SSH probe via env override.

    The actual gate script (Plan 201-07) MUST honor PHASE201_LOCAL_YAML_OVERRIDE
    to bypass SSH for tests. Until the script exists, function-level skips are
    allowed by the Wave 0 strict-RED contract because the symbol target cannot
    be imported or executed yet.
    """
    if not GATE_SCRIPT.exists():
        pytest.skip("phase201-predeploy-gate.sh not yet created (Plan 201-07)")
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
