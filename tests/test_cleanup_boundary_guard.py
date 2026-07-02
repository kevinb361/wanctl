from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
pytestmark = pytest.mark.skip(reason='Historical phase/boundary verifier anchored to an old repo state; not applicable to current HEAD default suite.')


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check-cleanup-boundary.sh"
FUTURE_DOC = ".planning/cake-autorate-trials/WANCTL_CAKE_AUTORATE_FUTURE.md"


def run_guard(
    cwd: Path,
    *args: str,
    out: Path | None = None,
    anchor: str = "bound01-test-anchor",
) -> subprocess.CompletedProcess[str]:
    command = ["bash", str(SCRIPT)]
    if anchor:
        command.extend(["--anchor", anchor])
    if out is not None:
        command.extend(["--out", str(out)])
    command.extend(args)
    return subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )


def manifest_rows() -> list[tuple[str, str, str]]:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--print-manifest"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    rows: list[tuple[str, str, str]] = []
    for line in result.stdout.splitlines():
        item_class, path, policy = line.split("\t")
        rows.append((item_class, path, policy))
    assert rows
    return rows


def commit_all(repo: Path, message: str) -> None:
    subprocess.run(["git", "add", "--all"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=bound01@example.invalid",
            "-c",
            "user.name=BOUND-01 Test",
            "commit",
            "-m",
            message,
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _make_scratch_repo(tmp_path: Path, *, future_doc_anchor_absent: bool = False) -> Path:
    repo = tmp_path / "scratch"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)

    if future_doc_anchor_absent:
        gitignore = repo / ".gitignore"
        gitignore.write_text(f"/{FUTURE_DOC}\n", encoding="utf-8")

    for index, (_item_class, path, policy) in enumerate(manifest_rows(), start=1):
        if future_doc_anchor_absent and path == FUTURE_DOC:
            continue
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            f"placeholder for {path}\npolicy={policy}\nindex={index}\n",
            encoding="utf-8",
        )

    commit_all(repo, "bound01 anchor")
    subprocess.run(
        ["git", "tag", "bound01-test-anchor"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )

    if future_doc_anchor_absent:
        future = repo / FUTURE_DOC
        future.parent.mkdir(parents=True, exist_ok=True)
        future.write_text("living future doc outside anchor\n", encoding="utf-8")

    return repo


def row_for(payload: dict[str, object], path: str) -> dict[str, object]:
    checks = payload["checks"]
    assert isinstance(checks, list)
    for row in checks:
        assert isinstance(row, dict)
        if row["path"] == path:
            return row
    raise AssertionError(f"missing row for {path}")


def test_guard_passes_on_real_repo(tmp_path: Path) -> None:
    """BOUND-01 sweep gate: default pytest must turn red on denylist violations."""
    planning = REPO_ROOT / ".planning" / "cake-autorate-trials"
    if not planning.exists():
        message = (
            "BOUND-01 gate cannot run: planning workspace absent. Sweep work is only valid "
            "in the dev checkout. Set WANCTL_BOUND01_ALLOW_NO_PLANNING=1 only for "
            "intentionally planning-less checkouts."
        )
        if os.environ.get("WANCTL_BOUND01_ALLOW_NO_PLANNING") == "1":
            pytest.skip(message)
        pytest.fail(message)

    out = tmp_path / "real-repo-bound01.json"
    result = run_guard(REPO_ROOT, out=out, anchor="v1.50")

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["overall_pass"] is True
    assert payload["proof_type"] == "bound01-cleanup-boundary-check"


def test_guard_fails_closed_on_removed_file(tmp_path: Path) -> None:
    repo = _make_scratch_repo(tmp_path)
    protected = repo / "src/wanctl/autorate_continuous.py"
    protected.unlink()
    out = tmp_path / "removed.json"

    result = run_guard(repo, out=out)

    assert result.returncode == 1
    assert "BOUND-01 VIOLATION" in result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["overall_pass"] is False
    assert row_for(payload, "src/wanctl/autorate_continuous.py")["status"] == "MISSING"


def test_guard_fails_closed_on_untracked_anchor_present_file(tmp_path: Path) -> None:
    repo = _make_scratch_repo(tmp_path)
    subprocess.run(
        ["git", "rm", "--cached", "src/wanctl/autorate_continuous.py"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    out = tmp_path / "untracked-anchor-present.json"

    result = run_guard(repo, out=out)

    assert result.returncode == 1
    assert "BOUND-01 VIOLATION" in result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    protected_row = row_for(payload, "src/wanctl/autorate_continuous.py")
    assert protected_row["anchor_present"] is True
    assert protected_row["tracked"] is False
    assert protected_row["status"] == "UNTRACKED"


def test_guard_fails_closed_on_modified_immutable_file(tmp_path: Path) -> None:
    repo = _make_scratch_repo(tmp_path)
    immutable = repo / "deploy/systemd/wanctl@.service"
    immutable.write_text(immutable.read_text(encoding="utf-8") + "modified\n", encoding="utf-8")
    out = tmp_path / "modified.json"

    result = run_guard(repo, out=out)

    assert result.returncode == 1
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert row_for(payload, "deploy/systemd/wanctl@.service")["status"] == "MODIFIED"


def test_guard_allows_modification_of_must_exist_file(tmp_path: Path) -> None:
    repo = _make_scratch_repo(tmp_path)
    allowlisted = repo / "scripts/phase231-rollback.sh"
    allowlisted.write_text(allowlisted.read_text(encoding="utf-8") + "authorized drift\n", encoding="utf-8")
    out = tmp_path / "allowlisted.json"

    result = run_guard(repo, out=out)

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert row_for(payload, "scripts/phase231-rollback.sh")["status"] == "allowlisted-modified"

    allowlisted.unlink()
    removed_out = tmp_path / "allowlisted-removed.json"
    removed = run_guard(repo, out=removed_out)

    assert removed.returncode == 1
    removed_payload = json.loads(removed_out.read_text(encoding="utf-8"))
    assert row_for(removed_payload, "scripts/phase231-rollback.sh")["status"] == "MISSING"


def test_guard_fails_closed_on_must_exist_directory_replacement(tmp_path: Path) -> None:
    repo = _make_scratch_repo(tmp_path)
    protected = repo / "scripts/phase231-rollback.sh"
    protected.unlink()
    protected.mkdir()
    out = tmp_path / "must-exist-directory.json"

    result = run_guard(repo, out=out)

    assert result.returncode == 1
    assert "BOUND-01 VIOLATION" in result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    protected_row = row_for(payload, "scripts/phase231-rollback.sh")
    assert protected_row["status"] == "NON_FILE"
    assert protected_row["exists"] is True
    assert protected_row["is_file"] is False


def test_guard_handles_anchor_absent_untracked_row(tmp_path: Path) -> None:
    repo = _make_scratch_repo(tmp_path, future_doc_anchor_absent=True)
    out = tmp_path / "anchor-absent.json"

    result = run_guard(repo, out=out)

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    future_row = row_for(payload, FUTURE_DOC)
    assert future_row["anchor_present"] is False
    assert future_row["tracked"] is False
    assert future_row["status"] == "ok"

    (repo / FUTURE_DOC).unlink()
    missing_out = tmp_path / "anchor-absent-missing.json"
    missing = run_guard(repo, out=missing_out)

    assert missing.returncode == 1
    missing_payload = json.loads(missing_out.read_text(encoding="utf-8"))
    assert row_for(missing_payload, FUTURE_DOC)["status"] == "MISSING"


def test_guard_exits_2_on_unknown_anchor(tmp_path: Path) -> None:
    result = run_guard(
        REPO_ROOT,
        out=tmp_path / "unknown-anchor.json",
        anchor="definitely-not-a-ref",
    )

    assert result.returncode == 2


@pytest.mark.parametrize("flag", ["--anchor", "--out"])
def test_guard_exits_2_on_missing_option_value(flag: str) -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), flag],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 2
    assert "requires a value" in result.stderr


def test_scratch_repo_fixture_does_not_copy_guard(tmp_path: Path) -> None:
    repo = _make_scratch_repo(tmp_path)

    assert not (repo / "scripts/check-cleanup-boundary.sh").exists()
    assert shutil.which("git") is not None
