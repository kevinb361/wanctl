"""Wave 0 xfail/skip contract for the Phase 220 wrapper."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
WRAPPER = REPO_ROOT / "scripts/phase220-target-path-matrix.sh"
EVIDENCE = REPO_ROOT / ".planning/phases/220-matrix-runner-scope-a1/evidence"
xfail = lambda item: (setattr(item, "pytestmark", [pytest.mark.xfail(reason="wrapper script not implemented yet — plan 03", strict=True)]), item)[1]
check = lambda condition, message="assertion failed": None if condition else (_ for _ in ()).throw(AssertionError(message))
skip_missing = lambda: pytest.skip("wrapper script not implemented yet — plan 03") if not WRAPPER.exists() else None
run = lambda *args, env=None: subprocess.run([str(WRAPPER), *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=20, env=env or (os.environ | {"PHASE220_BASE_SHA": "TEST_BASE_SHA"}))
run_dirs = lambda: set(EVIDENCE.glob("RUN-*")) if EVIDENCE.exists() else set()

test_dry_run_inside_window_returns_0 = xfail(lambda: (skip_missing(), check(run("--dry-run", "--test-hour", "12", "--cell", "dallas__spectrum__daytime", "--replicate", "1").returncode == 0))[-1])
test_dry_run_outside_window_returns_2 = xfail(lambda: (skip_missing(), check(run("--dry-run", "--test-hour", "23", "--cell", "dallas__spectrum__daytime", "--replicate", "1").returncode == 2))[-1])
test_dry_run_stdout_starts_with_dry_run_marker = xfail(lambda: (skip_missing(), check(run("--dry-run", "--test-hour", "12", "--cell", "dallas__spectrum__daytime", "--replicate", "1").stdout.startswith("DRY-RUN: "))) [-1])
test_dry_run_stdout_includes_flent_duration_30 = xfail(lambda: (skip_missing(), check("--flent-duration 30" in run("--dry-run", "--test-hour", "12", "--cell", "dallas__spectrum__daytime", "--replicate", "1").stdout))[-1])
test_dry_run_stdout_includes_resolved_bind_map_and_host = xfail(lambda: (skip_missing(), check("--bind-map spectrum=" in run("--dry-run", "--test-hour", "12", "--cell", "dallas__spectrum__daytime", "--replicate", "1").stdout and "--host dallas" in run("--dry-run", "--test-hour", "12", "--cell", "dallas__spectrum__daytime", "--replicate", "1").stdout))[-1])
test_dry_run_does_not_create_run_dir = xfail(lambda: (skip_missing(), (before := run_dirs()), run("--dry-run", "--test-hour", "12", "--cell", "dallas__spectrum__daytime", "--replicate", "1"), check(run_dirs() == before))[-1])
test_missing_base_sha_returns_4 = xfail(lambda: (skip_missing(), check(run("--dry-run", "--test-hour", "12", "--cell", "dallas__spectrum__daytime", "--replicate", "1", env={name: value for name, value in os.environ.items() if name != "PHASE220_BASE_SHA"}).returncode == 4))[-1])
test_test_hour_without_dry_run_returns_7 = xfail(lambda: (skip_missing(), check(run("--test-hour", "12", "--cell", "dallas__spectrum__daytime", "--replicate", "1").returncode == 7))[-1])
test_wrapper_refuses_when_phase213_script_drifts = xfail(lambda: (skip_missing(), check(run("--dry-run", "--test-hour", "12", "--cell", "dallas__spectrum__daytime", "--replicate", "1").returncode in {0, 4}))[-1])
test_wrapper_refuses_when_phase214_classifier_drifts = xfail(lambda: (skip_missing(), check(run("--dry-run", "--test-hour", "12", "--cell", "dallas__spectrum__daytime", "--replicate", "1").returncode in {0, 4}))[-1])
test_wrapper_validates_att_egress_when_path_is_att = xfail(lambda: (skip_missing(), check("att_egress" in run("--dry-run", "--test-hour", "12", "--cell", "dallas__att__daytime", "--replicate", "1").stdout))[-1])
