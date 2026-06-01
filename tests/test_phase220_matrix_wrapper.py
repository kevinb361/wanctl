"""Executable tests for the Phase 220 per-cell wrapper.

The wrapper reads ``scripts/phase220-matrix.yaml`` as the source of truth. Tests
therefore pass the YAML ``base_sha`` as ``PHASE220_BASE_SHA`` only as a matching
traceability echo; disagreement must fail closed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WRAPPER = REPO_ROOT / "scripts/phase220-target-path-matrix.sh"
MATRIX_YAML = REPO_ROOT / "scripts/phase220-matrix.yaml"
EVIDENCE = REPO_ROOT / ".planning/phases/220-matrix-runner-scope-a1/evidence"


def _yaml_data(path: Path = MATRIX_YAML) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _base_sha() -> str:
    return str(_yaml_data()["base_sha"])


def _env(**overrides: str) -> dict[str, str]:
    env = os.environ.copy()
    env["PHASE220_BASE_SHA"] = _base_sha()
    env.update(overrides)
    return env


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(WRAPPER), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        env=env or _env(),
    )


def _dry_run(cell: str = "dallas__spectrum__daytime", hour: str = "12") -> subprocess.CompletedProcess[str]:
    return _run("--dry-run", "--test-hour", hour, "--cell", cell, "--replicate", "1")


def _run_dirs() -> set[Path]:
    return set(EVIDENCE.glob("RUN-*")) if EVIDENCE.exists() else set()


def _git(*args: str, check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    if check and result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr}")
    return result


def _append_marker(path: Path) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n# phase220 wrapper drift test mutation\n")


def _restore_path(path: Path) -> None:
    _git("reset", "HEAD", str(path.relative_to(REPO_ROOT)), check=False)
    _git("restore", str(path.relative_to(REPO_ROOT)), check=False)


def _assert_no_leftover_throwaway_branches() -> None:
    branches = _git("branch", "--list", "phase220-test-throwaway-*").stdout.strip()
    assert branches == ""


def test_dry_run_inside_window_returns_0() -> None:
    result = _dry_run()
    assert result.returncode == 0, result.stderr


def test_dry_run_outside_window_returns_2() -> None:
    result = _dry_run(hour="23")
    assert result.returncode == 2
    assert "outside daytime window" in result.stderr


def test_dry_run_stdout_starts_with_dry_run_marker() -> None:
    result = _dry_run()
    assert result.stdout.startswith("DRY-RUN:")
    assert "bash scripts/phase213-baseline-capture.sh" in result.stdout


def test_dry_run_stdout_includes_flent_duration_30() -> None:
    result = _dry_run()
    assert "--flent-duration 30" in result.stdout


def test_dry_run_stdout_includes_resolved_bind_map_and_host() -> None:
    result = _dry_run()
    assert "--bind-map spectrum=" in result.stdout
    assert "--host dallas" in result.stdout


def test_dry_run_does_not_create_run_dir() -> None:
    before = _run_dirs()
    result = _dry_run()
    assert result.returncode == 0, result.stderr
    assert _run_dirs() == before


def test_missing_base_sha_in_yaml_returns_4(tmp_path: Path) -> None:
    """YAML is authoritative; missing YAML base_sha fails even if env is absent."""
    clone = tmp_path / "phase220-matrix.yaml"
    data = _yaml_data()
    data["base_sha"] = ""
    clone.write_text(yaml.safe_dump(data), encoding="utf-8")
    env = os.environ.copy()
    env.pop("PHASE220_BASE_SHA", None)
    env["PHASE220_MATRIX_YAML"] = str(clone)
    result = _run("--dry-run", "--test-hour", "12", "--cell", "dallas__spectrum__daytime", "--replicate", "1", env=env)
    assert result.returncode == 4
    assert "base_sha" in result.stderr


def test_env_base_sha_disagrees_with_yaml_returns_4() -> None:
    result = _run(
        "--dry-run",
        "--test-hour",
        "12",
        "--cell",
        "dallas__spectrum__daytime",
        "--replicate",
        "1",
        env=_env(PHASE220_BASE_SHA="0000000000000000000000000000000000000000"),
    )
    assert result.returncode == 4
    assert "YAML is authoritative" in result.stderr


def test_test_hour_without_dry_run_returns_7() -> None:
    result = _run("--test-hour", "12", "--cell", "dallas__spectrum__daytime", "--replicate", "1")
    assert result.returncode == 7


@pytest.mark.parametrize(
    ("script_rel", "expected"),
    [
        ("scripts/phase213-baseline-capture.sh", "scripts/phase213-* has unstaged diff"),
        ("scripts/phase214-classify.py", "scripts/phase214-* has unstaged diff"),
    ],
)
def test_wrapper_refuses_script_drift_unstaged(script_rel: str, expected: str) -> None:
    path = REPO_ROOT / script_rel
    try:
        _append_marker(path)
        result = _dry_run()
        assert result.returncode == 4
        assert expected in result.stderr
    finally:
        _restore_path(path)


def test_wrapper_refuses_when_phase213_script_drifts_unstaged() -> None:
    test_wrapper_refuses_script_drift_unstaged("scripts/phase213-baseline-capture.sh", "scripts/phase213-* has unstaged diff")


def test_wrapper_refuses_when_phase214_classifier_drifts_unstaged() -> None:
    test_wrapper_refuses_script_drift_unstaged("scripts/phase214-classify.py", "scripts/phase214-* has unstaged diff")


@pytest.mark.parametrize(
    ("script_rel", "expected"),
    [
        ("scripts/phase213-baseline-capture.sh", "scripts/phase213-* has staged diff"),
        ("scripts/phase214-classify.py", "scripts/phase214-* has staged diff"),
    ],
)
def test_wrapper_refuses_script_drift_staged(script_rel: str, expected: str) -> None:
    path = REPO_ROOT / script_rel
    try:
        _append_marker(path)
        _git("add", script_rel)
        result = _dry_run()
        assert result.returncode == 4
        assert expected in result.stderr
    finally:
        _restore_path(path)


def test_wrapper_refuses_when_phase213_script_drifts_staged() -> None:
    test_wrapper_refuses_script_drift_staged("scripts/phase213-baseline-capture.sh", "scripts/phase213-* has staged diff")


def test_wrapper_refuses_when_phase214_classifier_drifts_staged() -> None:
    test_wrapper_refuses_script_drift_staged("scripts/phase214-classify.py", "scripts/phase214-* has staged diff")


@pytest.mark.parametrize(
    ("script_rel", "expected"),
    [
        ("scripts/phase213-baseline-capture.sh", "scripts/phase213-* has committed diff since base_sha"),
        ("scripts/phase214-classify.py", "scripts/phase214-* has committed diff since base_sha"),
    ],
)
def test_wrapper_refuses_script_drift_committed_since_base(script_rel: str, expected: str) -> None:
    current_branch = _git("branch", "--show-current").stdout.strip()
    branch = f"phase220-test-throwaway-{os.getpid()}-{Path(script_rel).stem}"
    path = REPO_ROOT / script_rel
    try:
        _git("checkout", "-b", branch)
        _append_marker(path)
        _git("add", script_rel)
        _git(
            "commit",
            "-m",
            "TEST FIXTURE — phase220 wrapper drift test",
            env=os.environ | {"SKIP_DOC_CHECK": "1"},
        )
        result = _dry_run()
        assert result.returncode == 4
        assert expected in result.stderr
    finally:
        _git("checkout", current_branch)
        _restore_path(path)
        _git("branch", "-D", branch, check=False)
        _assert_no_leftover_throwaway_branches()


def test_wrapper_refuses_when_phase213_script_drifts_committed_since_base() -> None:
    test_wrapper_refuses_script_drift_committed_since_base(
        "scripts/phase213-baseline-capture.sh",
        "scripts/phase213-* has committed diff since base_sha",
    )


def test_wrapper_refuses_when_phase214_classifier_drifts_committed_since_base() -> None:
    test_wrapper_refuses_script_drift_committed_since_base(
        "scripts/phase214-classify.py",
        "scripts/phase214-* has committed diff since base_sha",
    )


def test_wrapper_validates_att_egress_when_path_is_att_dry_run() -> None:
    result = _dry_run(cell="dallas__att__daytime")
    assert result.returncode == 0, result.stderr
    assert "att_egress_check:" in result.stdout
    assert "DRY-RUN" in result.stdout


def test_wrapper_generates_phase214_signal_sheet_after_delegate() -> None:
    source = WRAPPER.read_text(encoding="utf-8")
    assert "scripts/phase214-align.py" in source
    assert "scripts/phase214-classify.py" in source
    assert '--output-json "$TEST_DIR/signal-sheet.json"' in source


def test_wrapper_phase220_cell_sidecar_uses_jq_variables() -> None:
    source = WRAPPER.read_text(encoding="utf-8")
    assert "schema_version: $schema_version" in source
    assert "phase: $phase" in source
    assert "target_kind: $target_kind" in source
    assert "canonical_control_p99_kill_ms: $canonical_control_p99_kill_ms" in source


def test_wrapper_hard_fails_when_att_egress_signature_missing_in_yaml(tmp_path: Path) -> None:
    clone = tmp_path / "phase220-matrix.yaml"
    data = _yaml_data()
    for path in data["paths"]:
        if path["name"] == "att":
            path["egress_signature"] = ""
    clone.write_text(yaml.safe_dump(data), encoding="utf-8")
    result = _run(
        "--dry-run",
        "--test-hour",
        "12",
        "--cell",
        "dallas__att__daytime",
        "--replicate",
        "1",
        env=_env(PHASE220_MATRIX_YAML=str(clone)),
    )
    assert result.returncode == 4
    assert "REFUSED" in result.stderr
    assert "egress_signature" in result.stderr


def test_no_leftover_phase220_throwaway_branches() -> None:
    _assert_no_leftover_throwaway_branches()


def test_shutil_import_kept_for_precommit_doc_classifier() -> None:
    assert shutil.which("git")
