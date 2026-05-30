"""Phase 219 Wave 0 tests for the cron-callable ingestion digest script."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "phase219_ingestion_digest.py"
MAX_SNAPSHOTS_DEFAULT = 288


def _load_script():
    if not SCRIPT_PATH.exists():
        pytest.skip("Wave 3 script not yet implemented")
    spec = importlib.util.spec_from_file_location("phase219_digest", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _invoke_main(module, *args: str) -> int:
    return module.main(list(args))


class TestPhase219IngestionDigest:
    """Pins atomic write, retention, tolerance, permissions, and defaults."""

    @pytest.mark.xfail(reason="scripts/phase219_ingestion_digest.py lands in plan 04", strict=False)
    def test_atomic_rename_writes_exactly_one_file(self, tmp_path, monkeypatch):
        """atomic_rename/os.replace path leaves exactly one JSON and no *.tmp."""
        module = _load_script()
        monkeypatch.setattr(module, "_call_history", lambda *_args, **_kwargs: '{"rows": []}')

        rc = _invoke_main(
            module,
            "--snapshot-dir",
            str(tmp_path),
            "--max-snapshots",
            "10",
            "--payload-from-stdin",
        )

        assert rc == 0
        assert len(list(tmp_path.glob("*.json"))) == 1
        assert not list(tmp_path.glob("*.tmp"))

    @pytest.mark.xfail(reason="scripts/phase219_ingestion_digest.py lands in plan 04", strict=False)
    def test_retention_keeps_max_files(self, tmp_path, monkeypatch):
        module = _load_script()
        monkeypatch.setattr(module, "_call_history", lambda *_args, **_kwargs: '{"rows": []}')

        for snapshot_ts in range(5):
            assert (
                _invoke_main(
                    module,
                    "--snapshot-dir",
                    str(tmp_path),
                    "--max-snapshots",
                    "3",
                    "--payload-from-stdin",
                    "--inject-timestamp",
                    str(snapshot_ts),
                )
                == 0
            )

        retained = sorted(path.name for path in tmp_path.glob("*.json"))
        assert len(retained) == 3
        assert retained == sorted(retained)[-3:]

    @pytest.mark.xfail(reason="scripts/phase219_ingestion_digest.py lands in plan 04", strict=False)
    def test_subprocess_failure_returns_1_does_not_raise(self, tmp_path, monkeypatch):
        module = _load_script()

        def fail_history(*_args, **_kwargs):
            raise subprocess.TimeoutExpired("wanctl-history", timeout=30)

        monkeypatch.setattr(module, "_call_history", fail_history)
        rc = _invoke_main(module, "--snapshot-dir", str(tmp_path))

        assert rc == 1
        assert not list(tmp_path.glob("*.tmp"))

    @pytest.mark.xfail(reason="scripts/phase219_ingestion_digest.py lands in plan 04", strict=False)
    def test_snapshot_dir_created_with_mode_0o755(self, tmp_path, monkeypatch):
        module = _load_script()
        monkeypatch.setattr(
            module, "_call_history", lambda *_args, **_kwargs: json.dumps({"rows": []})
        )
        snapshot_dir = tmp_path / "ingestion"

        rc = _invoke_main(module, "--snapshot-dir", str(snapshot_dir), "--payload-from-stdin")

        assert rc == 0
        assert snapshot_dir.exists()
        assert snapshot_dir.stat().st_mode & 0o777 == 0o755

    @pytest.mark.xfail(reason="scripts/phase219_ingestion_digest.py lands in plan 04", strict=False)
    def test_default_max_snapshots_is_288(self):
        module = _load_script()
        assert module.MAX_SNAPSHOTS_DEFAULT == MAX_SNAPSHOTS_DEFAULT
