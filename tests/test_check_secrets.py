"""Regression tests for the fail-closed, value-redacting secret gate."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "check_secrets.py"


def _tool(name: str) -> str:
    sibling = Path(sys.executable).with_name(name)
    path = str(sibling) if sibling.is_file() else shutil.which(name)
    if path is None:
        pytest.fail(f"required test tool missing: {name}")
    return path


def _create_baseline(tmp_path: Path, fixture: Path) -> Path:
    baseline = tmp_path / ".secrets.baseline"
    result = subprocess.run(
        [_tool("detect-secrets"), "scan", fixture.name],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    baseline.write_text(result.stdout)
    return baseline


def _run_gate(
    tmp_path: Path, baseline: Path, fixture: Path, *extra: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--baseline",
            baseline.name,
            *extra,
            fixture.name,
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )


def test_clean_file_passes(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.env"
    fixture.write_text("ordinary = value\n")
    baseline = _create_baseline(tmp_path, fixture)

    result = _run_gate(tmp_path, baseline, fixture)

    assert result.returncode == 0
    assert "Secret scan passed" in result.stdout


def test_new_secret_fails_without_value_or_baseline_mutation(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.env"
    fixture.write_text("ordinary = value\n")
    baseline = _create_baseline(tmp_path, fixture)
    before = hashlib.sha256(baseline.read_bytes()).hexdigest()
    candidate = "correct-horse-battery-staple-REM001"
    fixture.write_text(f"password = {candidate}\n")

    result = _run_gate(tmp_path, baseline, fixture)

    assert result.returncode == 1
    assert hashlib.sha256(baseline.read_bytes()).hexdigest() == before
    output = result.stdout + result.stderr
    assert "fixture.env:1: Secret Keyword" in output
    assert candidate not in output


def test_baseline_mutation_is_rejected(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.env"
    fixture.write_text("ordinary = value\n")
    baseline = _create_baseline(tmp_path, fixture)
    scanner = tmp_path / "mutating-scanner"
    scanner.write_text(
        "#!/usr/bin/env python3\n"
        "import json, pathlib, sys\n"
        "p = pathlib.Path(sys.argv[sys.argv.index('--baseline') + 1])\n"
        "p.write_text(p.read_text() + '\\n')\n"
        "print(json.dumps({'results': {}}))\n"
    )
    scanner.chmod(0o755)

    result = _run_gate(tmp_path, baseline, fixture, "--scanner", str(scanner))

    assert result.returncode == 1
    assert "scanner modified the baseline" in result.stderr


def test_invalid_scanner_output_is_not_echoed(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.env"
    fixture.write_text("ordinary = value\n")
    baseline = _create_baseline(tmp_path, fixture)
    scanner = tmp_path / "invalid-scanner"
    scanner.write_text("#!/bin/sh\nprintf 'candidate-value-that-must-not-escape\\n'\nexit 1\n")
    scanner.chmod(0o755)

    result = _run_gate(tmp_path, baseline, fixture, "--scanner", str(scanner))

    output = result.stdout + result.stderr
    assert result.returncode == 2
    assert "scanner returned invalid output" in output
    assert "candidate-value-that-must-not-escape" not in output


def test_public_tree_tracks_only_planning_boundary_notice() -> None:
    result = subprocess.run(
        [
            "git",
            "ls-files",
            ".planning",
            "configs/att.yaml",
            "configs/spectrum.yaml",
            "configs/steering.yaml",
        ],
        cwd=SCRIPT.parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.splitlines() == [".planning/README.md"]


def test_required_ci_runs_secret_gate() -> None:
    root = SCRIPT.parents[1]
    makefile = (root / "Makefile").read_text()
    ci_line = next(line for line in makefile.splitlines() if line.startswith("ci:"))

    assert "security-secrets" in ci_line.split()
    for workflow in (root / ".gitea/workflows/ci.yml", root / ".github/workflows/ci.yml"):
        assert "make ci" in workflow.read_text()
