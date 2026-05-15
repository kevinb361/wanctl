"""Phase 206 predeploy gate shell-integration tests."""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GATE_SCRIPT = REPO_ROOT / "scripts" / "phase206-predeploy-gate.sh"
BASELINE = REPO_ROOT / "tests" / "fixtures" / "phase206_baseline_v143.json"
SOAK = REPO_ROOT / "tests" / "fixtures" / "phase206_soak_synthetic.ndjson"
VENV_PY = REPO_ROOT / ".venv" / "bin" / "python3"


def _run_gate(
    args: list[str], extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[bytes]:
    assert GATE_SCRIPT.exists(), GATE_SCRIPT
    env = {"PATH": "/usr/bin:/bin", "VENV_PY": str(VENV_PY)}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(GATE_SCRIPT), *args],
        env=env,
        capture_output=True,
        timeout=15,
        check=False,
    )


def _make_candidate(tmp_path: Path, **post_overrides: object) -> Path:
    baseline = json.loads(BASELINE.read_text())
    candidate = copy.deepcopy(baseline)
    for key, value in post_overrides.items():
        candidate["post"][key] = value
    out = tmp_path / "candidate.json"
    out.write_text(json.dumps(candidate, indent=2))
    return out


def _make_baseline_with(
    tmp_path: Path, name: str = "baseline_override.json", **gate_baseline_overrides: object
) -> Path:
    baseline = json.loads(BASELINE.read_text())
    baseline["gate_baseline"].update(gate_baseline_overrides)
    out = tmp_path / name
    out.write_text(json.dumps(baseline, indent=2))
    return out


def _make_baseline_without(
    tmp_path: Path, *fields: str, name: str = "baseline_stripped.json"
) -> Path:
    baseline = json.loads(BASELINE.read_text())
    for field in fields:
        baseline.get("gate_baseline", {}).pop(field, None)
    out = tmp_path / name
    out.write_text(json.dumps(baseline, indent=2))
    return out


class TestGateDryRun:
    def test_baseline_vs_self_passes(self) -> None:
        result = _run_gate(["--baseline", str(BASELINE), "--candidate", str(BASELINE)])
        assert result.returncode == 0, (result.stdout + result.stderr).decode()


class TestRrulP99Block:
    def test_p99_regression_above_5pct_blocks(self, tmp_path: Path) -> None:
        baseline = json.loads(BASELINE.read_text())
        candidate = _make_candidate(
            tmp_path,
            rrul_p99_latency_ms=baseline["post"]["rrul_p99_latency_ms"] * 1.10,
        )
        result = _run_gate(["--baseline", str(BASELINE), "--candidate", str(candidate)])
        assert result.returncode == 1, (result.stdout + result.stderr).decode()
        assert b"RRUL p99" in result.stdout

    def test_p99_regression_at_5pct_boundary_does_not_block(self, tmp_path: Path) -> None:
        baseline = json.loads(BASELINE.read_text())
        candidate = _make_candidate(
            tmp_path,
            rrul_p99_latency_ms=baseline["post"]["rrul_p99_latency_ms"] * 1.05,
        )
        result = _run_gate(["--baseline", str(BASELINE), "--candidate", str(candidate)])
        assert result.returncode == 0, (result.stdout + result.stderr).decode()


class TestRestartRateBlock:
    def test_restart_rate_above_10pct_increase_blocks(self, tmp_path: Path) -> None:
        baseline = _make_baseline_with(tmp_path, restart_rate_per_hour_baseline=1.0)
        result = _run_gate(
            [
                "--baseline",
                str(baseline),
                "--candidate",
                str(BASELINE),
                "--restart-counter-start",
                "0",
                "--restart-counter-end",
                "5",
                "--window-hours",
                "1",
            ]
        )
        assert result.returncode == 1, (result.stdout + result.stderr).decode()
        assert b"Daemon restart-rate" in result.stdout

    def test_zero_baseline_any_restart_blocks(self) -> None:
        result = _run_gate(
            [
                "--baseline",
                str(BASELINE),
                "--candidate",
                str(BASELINE),
                "--restart-counter-start",
                "0",
                "--restart-counter-end",
                "1",
                "--window-hours",
                "1",
            ]
        )
        assert result.returncode == 1, (result.stdout + result.stderr).decode()
        assert b"zero-baseline policy" in result.stdout


class TestTransitionRateBlock:
    def test_transition_rate_above_10pct_increase_blocks(self, tmp_path: Path) -> None:
        baseline = _make_baseline_with(tmp_path, transition_rate_per_hour_baseline=5.0)
        result = _run_gate(
            [
                "--baseline",
                str(baseline),
                "--candidate",
                str(BASELINE),
                "--soak-ndjson",
                str(SOAK),
            ]
        )
        assert result.returncode == 1, (result.stdout + result.stderr).decode()
        assert b"Pressure-state transition-rate" in result.stdout


class TestGateAbort:
    def test_missing_baseline_aborts(self) -> None:
        result = _run_gate(["--baseline", "/nonexistent.json", "--candidate", str(BASELINE)])
        assert result.returncode == 2

    def test_invalid_ssh_target_aborts(self) -> None:
        result = _run_gate(
            [
                "--baseline",
                str(BASELINE),
                "--candidate",
                str(BASELINE),
                "--ssh-target",
                "evil;rm -rf /",
            ]
        )
        assert result.returncode == 2


class TestFailClosed:
    def test_aborts_when_soak_provided_but_gate_baseline_missing_transition_rate(
        self, tmp_path: Path
    ) -> None:
        stripped = _make_baseline_without(
            tmp_path, "transition_rate_per_hour_baseline", name="baseline_no_transition.json"
        )
        result = _run_gate(
            [
                "--baseline",
                str(stripped),
                "--candidate",
                str(BASELINE),
                "--soak-ndjson",
                str(SOAK),
            ]
        )
        assert result.returncode == 2, (result.stdout + result.stderr).decode()
        assert (
            b"--soak-ndjson provided but gate_baseline missing "
            b"transition_rate_per_hour_baseline; cannot enforce TOPO-05"
        ) in result.stderr

    def test_aborts_when_restart_counter_provided_but_gate_baseline_missing_restart_rate(
        self, tmp_path: Path
    ) -> None:
        stripped = _make_baseline_without(
            tmp_path, "restart_rate_per_hour_baseline", name="baseline_no_restart.json"
        )
        result = _run_gate(
            [
                "--baseline",
                str(stripped),
                "--candidate",
                str(BASELINE),
                "--restart-counter-start",
                "0",
                "--restart-counter-end",
                "0",
                "--window-hours",
                "1",
            ]
        )
        assert result.returncode == 2, (result.stdout + result.stderr).decode()
        assert (
            b"--restart-counter-start/--restart-counter-end provided but "
            b"gate_baseline missing restart_rate_per_hour_baseline; cannot enforce TOPO-05"
        ) in result.stderr

    def test_info_skip_when_both_baseline_and_inputs_absent(self, tmp_path: Path) -> None:
        stripped = _make_baseline_without(
            tmp_path,
            "restart_rate_per_hour_baseline",
            "transition_rate_per_hour_baseline",
            name="baseline_no_optional_gates.json",
        )
        result = _run_gate(["--baseline", str(stripped), "--candidate", str(BASELINE)])
        assert result.returncode == 0, (result.stdout + result.stderr).decode()
        assert b"transition-rate check skipped" in result.stderr
        assert b"restart-rate check skipped" in result.stderr


class TestPostSoakRequiresAll:
    def test_post_soak_missing_soak_ndjson_aborts(self) -> None:
        result = _run_gate(
            ["--mode", "post-soak", "--baseline", str(BASELINE), "--candidate", str(BASELINE)]
        )
        assert result.returncode == 2, (result.stdout + result.stderr).decode()
        assert b"ERROR: --mode post-soak requires --soak-ndjson" in result.stderr

    def test_post_soak_missing_restart_counters_aborts(self) -> None:
        result = _run_gate(
            [
                "--mode",
                "post-soak",
                "--baseline",
                str(BASELINE),
                "--candidate",
                str(BASELINE),
                "--soak-ndjson",
                str(SOAK),
            ]
        )
        assert result.returncode == 2, (result.stdout + result.stderr).decode()
        assert (
            b"ERROR: --mode post-soak requires --restart-counter-start and "
            b"--restart-counter-end and --window-hours"
        ) in result.stderr

    def test_post_soak_missing_gate_baseline_aborts(self, tmp_path: Path) -> None:
        stripped = _make_baseline_without(
            tmp_path,
            "restart_rate_per_hour_baseline",
            "transition_rate_per_hour_baseline",
            name="baseline_no_gate.json",
        )
        result = _run_gate(
            [
                "--mode",
                "post-soak",
                "--baseline",
                str(stripped),
                "--candidate",
                str(BASELINE),
                "--soak-ndjson",
                str(SOAK),
                "--restart-counter-start",
                "0",
                "--restart-counter-end",
                "0",
                "--window-hours",
                "1",
            ]
        )
        assert result.returncode == 2, (result.stdout + result.stderr).decode()
        assert b"ERROR: --mode post-soak requires gate_baseline with both" in result.stderr

    def test_post_soak_full_inputs_passes(self, tmp_path: Path) -> None:
        baseline = _make_baseline_with(
            tmp_path, name="baseline_high_transition.json", transition_rate_per_hour_baseline=1000.0
        )
        result = _run_gate(
            [
                "--mode",
                "post-soak",
                "--baseline",
                str(baseline),
                "--candidate",
                str(BASELINE),
                "--soak-ndjson",
                str(SOAK),
                "--restart-counter-start",
                "0",
                "--restart-counter-end",
                "0",
                "--window-hours",
                "1",
            ]
        )
        assert result.returncode in (0, 1), (result.stdout + result.stderr).decode()


class TestPostSoakAbortMalformed:
    """G1 closure: empty/malformed/insufficient soak NDJSON must rc=2 in post-soak mode."""

    def _post_soak_args(self, baseline_path: Path, soak_path: Path) -> list[str]:
        return [
            "--mode",
            "post-soak",
            "--baseline",
            str(baseline_path),
            "--candidate",
            str(baseline_path),
            "--soak-ndjson",
            str(soak_path),
            "--restart-counter-start",
            "0",
            "--restart-counter-end",
            "0",
            "--window-hours",
            "1",
        ]

    def test_empty_soak_file_aborts(self, tmp_path: Path) -> None:
        soak = tmp_path / "empty.ndjson"
        soak.write_text("")
        result = _run_gate(self._post_soak_args(BASELINE, soak))
        assert result.returncode == 2, (result.stdout + result.stderr).decode()
        assert b"insufficient valid soak samples" in result.stderr

    def test_all_malformed_json_aborts(self, tmp_path: Path) -> None:
        soak = tmp_path / "malformed.ndjson"
        soak.write_text("not json\n{also not json\n[]not-json-either\n")
        result = _run_gate(self._post_soak_args(BASELINE, soak))
        assert result.returncode == 2, (result.stdout + result.stderr).decode()
        err = result.stderr
        assert b"insufficient valid soak samples" in err or b"no valid soak rows" in err

    def test_rows_missing_last_zone_aborts(self, tmp_path: Path) -> None:
        soak = tmp_path / "no_zone.ndjson"
        soak.write_text(
            '{"t_monotonic": 1.0}\n'
            '{"t_monotonic": 2.0}\n'
            '{"t_monotonic": 3.0}\n'
        )
        result = _run_gate(self._post_soak_args(BASELINE, soak))
        assert result.returncode == 2, (result.stdout + result.stderr).decode()
        assert b"insufficient valid soak samples" in result.stderr

    def test_rows_missing_t_monotonic_aborts(self, tmp_path: Path) -> None:
        soak = tmp_path / "no_t.ndjson"
        soak.write_text(
            '{"last_zone": "GREEN"}\n'
            '{"last_zone": "YELLOW"}\n'
            '{"last_zone": "GREEN"}\n'
        )
        result = _run_gate(self._post_soak_args(BASELINE, soak))
        assert result.returncode == 2, (result.stdout + result.stderr).decode()
        err = result.stderr
        assert b"soak rows missing t_monotonic" in err or b"insufficient valid soak samples" in err

    def test_single_valid_sample_aborts(self, tmp_path: Path) -> None:
        soak = tmp_path / "one_sample.ndjson"
        soak.write_text('{"last_zone": "GREEN", "t_monotonic": 1.0}\n')
        result = _run_gate(self._post_soak_args(BASELINE, soak))
        assert result.returncode == 2, (result.stdout + result.stderr).decode()
        assert b"insufficient valid soak samples" in result.stderr


class TestGateBaselineSchema:
    def test_gate_baseline_schema_version_is_1(self) -> None:
        baseline = json.loads(BASELINE.read_text())
        assert baseline["gate_baseline"]["gate_baseline_schema_version"] == 1

    def test_gate_baseline_required_fields_present(self) -> None:
        baseline = json.loads(BASELINE.read_text())
        gb = baseline["gate_baseline"]
        assert "restart_rate_per_hour_baseline" in gb
        assert "transition_rate_per_hour_baseline" in gb
        assert "_provenance" in gb
        assert gb["_provenance"]["restart_rate_per_hour_baseline_source"]
        assert gb["_provenance"]["transition_rate_per_hour_baseline_source"]
