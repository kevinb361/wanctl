"""Phase 219 Wave 0 tests for the cron-callable ingestion digest script."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "phase219_ingestion_digest.py"
MAX_SNAPSHOTS_DEFAULT = 288


def _load_script():
    spec = importlib.util.spec_from_file_location("phase219_digest", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _run_script(*args: str, input_text: str = '{"schema_version":1,"rows":[]}'):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=input_text,
        capture_output=True,
        text=True,
        timeout=15,
    )


class TestPhase219IngestionDigest:
    """Pins atomic write, retention, tolerance, permissions, and defaults."""

    def test_atomic_rename_writes_exactly_one_file(self, tmp_path):
        """atomic_write_json path leaves exactly one JSON and no temp residue."""
        result = _run_script(
            "--snapshot-dir",
            str(tmp_path),
            "--max-snapshots",
            "10",
            "--payload-from-stdin",
        )

        assert result.returncode == 0, result.stderr
        paths = list(tmp_path.glob("*.json"))
        assert len(paths) == 1
        assert not list(tmp_path.glob("*.tmp"))
        assert not list(tmp_path.glob(".*"))
        assert json.loads(paths[0].read_text())["schema_version"] == 1

    def test_retention_keeps_max_files(self, tmp_path):
        for snapshot_ts in range(1000, 1005):
            result = _run_script(
                "--snapshot-dir",
                str(tmp_path),
                "--max-snapshots",
                "3",
                "--payload-from-stdin",
                "--inject-timestamp",
                str(snapshot_ts),
            )
            assert result.returncode == 0, result.stderr

        retained = sorted(path.name for path in tmp_path.glob("*.json"))
        assert len(retained) == 3
        assert retained == ["1002.json", "1003.json", "1004.json"]

    def test_subprocess_failure_returns_1_does_not_raise(self, tmp_path):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--snapshot-dir", str(tmp_path)],
            cwd=str(tmp_path),
            env={"PATH": os.defpath, "PYTHONPATH": "/nonexistent"},
            capture_output=True,
            text=True,
            timeout=15,
        )

        assert result.returncode != 0
        assert not list(tmp_path.glob("*.tmp"))
        assert not list(tmp_path.glob("*.json"))

    def test_snapshot_dir_created_with_mode_0o755(self, tmp_path):
        snapshot_dir = tmp_path / "nested" / "ingestion"

        result = _run_script("--snapshot-dir", str(snapshot_dir), "--payload-from-stdin")

        assert result.returncode == 0, result.stderr
        assert snapshot_dir.exists()
        assert snapshot_dir.stat().st_mode & 0o777 == 0o755

    def test_default_max_snapshots_is_288(self):
        module = _load_script()
        assert module.MAX_SNAPSHOTS_DEFAULT == MAX_SNAPSHOTS_DEFAULT

    def test_malformed_json_payload_returns_1_no_file_written(self, tmp_path):
        result = _run_script(
            "--snapshot-dir",
            str(tmp_path),
            "--payload-from-stdin",
            input_text="this is not json",
        )

        assert result.returncode == 1
        assert "malformed JSON" in result.stderr
        assert not list(tmp_path.glob("*.json"))
